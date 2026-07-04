"""POST /api/weight — log or update today's weight.
   DELETE /api/weight — remove today's weight entry.
"""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from api.auth import get_telegram_user
from api.routers.goal import profile_kwargs
from db.database import AsyncSessionFactory
from db.models import User, WeightLog
from services.goal_plan import compute_plan

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

        # Safeguard #4: today's weight becomes the current weight; if the user has an
        # active goal, recompute the calorie target from the new weight.
        if log_date == date.today():
            user = await session.get(User, user_id)
            if user is not None:
                user.weight_kg = payload.weight
                if user.goal in ("lose", "gain") and user.target_weight_kg and user.pace_kg_per_week:
                    plan = compute_plan(
                        target_weight=user.target_weight_kg,
                        pace=user.pace_kg_per_week,
                        **profile_kwargs(user, weight_override=payload.weight),
                    )
                    user.target_kcal = plan["daily_kcal"]
                    user.target_protein_g = plan["macros"]["p"]
                    user.target_fat_g = plan["macros"]["f"]
                    user.target_carbs_g = plan["macros"]["c"]

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
