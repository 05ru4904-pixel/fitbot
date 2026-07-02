import hashlib
import hmac
import json
from urllib.parse import parse_qsl, unquote

from fastapi import Header, HTTPException

from config import settings


def _validate_init_data(raw: str) -> dict:
    vals = dict(parse_qsl(unquote(raw), keep_blank_values=True))
    received_hash = vals.pop("hash", "")
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash in initData")

    data_check = "\n".join(f"{k}={v}" for k, v in sorted(vals.items()))
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=settings.telegram_bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    computed = hmac.new(
        key=secret_key,
        msg=data_check.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    user_json = vals.get("user", "{}")
    return json.loads(user_json)


async def get_telegram_user(
    x_telegram_init_data: str | None = Header(default=None),
) -> dict:
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data header")
    return _validate_init_data(x_telegram_init_data)
