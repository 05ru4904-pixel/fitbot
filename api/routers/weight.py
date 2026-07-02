"""POST /api/weight — log or update today's weight.
   DELETE /api/weight — remove today's weight entry.
"""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from api.auth import get_telegram_user
from db.database import AsyncSessionFactory
from db.models import WeightLog

router = APIRouter()


class WeightPayload(BaseModel):
    weight: float
    date: str | None = None


@router.post("/weight")
async def log_weight(
    payload: WeightPayload,
    tg_user: dict = Depends(get_telegram_user),
):
    user_id: int = tg_user["id"]
    log_date = date.today()
    if payload.date:
        try:
            log_date = date.fromisoformat(payload.date)
        except ValueError:
            pass

    async with AsyncSessionFactory() as session:
        # Upsert: insert or update on (user_id, date)
        existing = await session.execute(
            select(WeightLog).where(WeightLog.user_id == user_id, WeightLog.date == log_date)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.weight_kg = payload.weight
        else:
            session.add(WeightLog(user_id=user_id, date=log_date, weight_kg=payload.weight))
        await session.commit()

    return {"ok": True}


@router.delete("/weight")
async def clear_today_weight(tg_user: dict = Depends(get_telegram_user)):
    user_id: int = tg_user["id"]
    today = date.today()
    async with AsyncSessionFactory() as session:
        await session.execute(
            delete(WeightLog).where(WeightLog.user_id == user_id, WeightLog.date == today)
        )
        await session.commit()
    return {"ok": True}
