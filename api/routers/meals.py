"""PUT /api/meals/today — replace today's diary items from Mini App."""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete

from api.auth import get_telegram_user
from db.database import AsyncSessionFactory
from db.models import DiaryItem

router = APIRouter()

VALID_SLOTS = {"breakfast", "lunch", "dinner", "snack"}


class FoodItem(BaseModel):
    name: str
    grams: int | None = None
    kcal: float
    p: float = 0
    f: float = 0
    c: float = 0


class TodayMealsPayload(BaseModel):
    meals: dict[str, list[FoodItem]]


@router.put("/meals/today")
async def replace_today_meals(
    payload: TodayMealsPayload,
    tg_user: dict = Depends(get_telegram_user),
):
    user_id: int = tg_user["id"]
    today = date.today()

    async with AsyncSessionFactory() as session:
        # Delete existing diary items for today (Mini App entries)
        await session.execute(
            delete(DiaryItem).where(DiaryItem.user_id == user_id, DiaryItem.date == today)
        )

        # Insert new items
        for slot, items in payload.meals.items():
            if slot not in VALID_SLOTS:
                continue
            for item in items:
                entry = DiaryItem(
                    user_id=user_id,
                    date=today,
                    slot=slot,
                    name=item.name,
                    grams=item.grams,
                    kcal=item.kcal,
                    protein_g=item.p,
                    fat_g=item.f,
                    carbs_g=item.c,
                )
                session.add(entry)

        await session.commit()

    return {"ok": True}
