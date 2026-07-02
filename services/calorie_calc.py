import json
import logging
from pathlib import Path

from openai import AsyncOpenAI

from config import settings
from models.schemas import CalorieResult

logger = logging.getLogger(__name__)

_CALCULATE_PROMPT = (Path(__file__).parent.parent / "prompts" / "calculate.txt").read_text(encoding="utf-8")

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


async def calculate_calories(dishes: list[dict]) -> CalorieResult:
    dishes_text = "\n".join(
        f"- {d['name']}: {d['estimated_weight_g']} г" for d in dishes
    )

    for attempt in range(2):
        try:
            response = await _get_client().chat.completions.create(
                model=MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": _CALCULATE_PROMPT},
                    {"role": "user", "content": f"Рассчитай КБЖУ для:\n{dishes_text}"},
                ],
            )
            raw = response.choices[0].message.content
            logger.debug("Calorie raw (attempt %d): %s", attempt + 1, raw)
            cleaned = _strip_markdown(raw)
            data = json.loads(cleaned)
            return CalorieResult(**data)
        except Exception as e:
            logger.warning("Calorie parse error (attempt %d): %s", attempt + 1, e)
            if attempt == 1:
                raise RuntimeError(f"Не удалось рассчитать калории: {e}") from e
