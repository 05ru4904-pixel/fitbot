import base64
import json
import logging
from pathlib import Path

from openai import AsyncOpenAI

from config import settings
from models.schemas import RecognitionResult

logger = logging.getLogger(__name__)

_RECOGNIZE_PROMPT = (Path(__file__).parent.parent / "prompts" / "recognize.txt").read_text(encoding="utf-8")

_cache: dict[str, RecognitionResult] = {}
_MAX_CACHE = 200

MODEL = "google/gemini-2.5-flash-lite"
BASE_URL = "https://polza.ai/api/v1"

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.gemini_api_key, base_url=BASE_URL)
    return _client


def _strip_markdown(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _parse_recognition(raw: str) -> RecognitionResult:
    cleaned = _strip_markdown(raw)
    data = json.loads(cleaned)
    if "error" in data:
        raise ValueError(data.get("message", "Не удалось распознать еду на фото"))
    return RecognitionResult(**data)


async def recognize_food(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    file_unique_id: str | None = None,
) -> RecognitionResult:
    if file_unique_id and file_unique_id in _cache:
        logger.debug("Cache hit: %s", file_unique_id)
        return _cache[file_unique_id]

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    for attempt in range(2):
        try:
            response = await _get_client().chat.completions.create(
                model=MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": _RECOGNIZE_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                            },
                            {"type": "text", "text": "Определи состав блюда на фото."},
                        ],
                    },
                ],
            )
            raw = response.choices[0].message.content
            logger.debug("Vision raw (attempt %d): %s", attempt + 1, raw)
            result = _parse_recognition(raw)
            if file_unique_id:
                if len(_cache) >= _MAX_CACHE:
                    _cache.clear()
                _cache[file_unique_id] = result
            return result
        except ValueError:
            raise
        except Exception as e:
            logger.warning("Vision parse error (attempt %d): %s", attempt + 1, e)
            if attempt == 1:
                raise RuntimeError(f"Не удалось обработать ответ: {e}") from e


async def update_composition(current_dishes: list[dict], correction_text: str) -> RecognitionResult:
    current_json = json.dumps({"dishes": current_dishes}, ensure_ascii=False, indent=2)
    user_message = (
        f"Текущий состав:\n{current_json}\n\n"
        f"Правка пользователя: {correction_text}\n\n"
        "Обнови JSON с учётом правки и верни полный обновлённый JSON."
    )

    for attempt in range(2):
        try:
            response = await _get_client().chat.completions.create(
                model=MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": _RECOGNIZE_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
            raw = response.choices[0].message.content
            logger.debug("Correction raw (attempt %d): %s", attempt + 1, raw)
            return _parse_recognition(raw)
        except Exception as e:
            logger.warning("Correction parse error (attempt %d): %s", attempt + 1, e)
            if attempt == 1:
                raise RuntimeError(f"Не удалось применить правку: {e}") from e
