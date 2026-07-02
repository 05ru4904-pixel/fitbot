"""GET /api/state — full app state for Mini App startup.
   DELETE /api/state — reset (clear diary items and weight log for this user).
"""

import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select

from api.auth import get_telegram_user
from db.database import AsyncSessionFactory
from db.models import DiaryItem, Meal, User, WeightLog

router = APIRouter()


def _r(n: float) -> int:
    return round(n)


@router.get("/state")
async def get_state(tg_user: dict = Depends(get_telegram_user)):
    user_id: int = tg_user["id"]
    today = date.today()
    week_ago = today - timedelta(days=29)

    async with AsyncSessionFactory() as session:
        # Load user profile
        user = await session.get(User, user_id)

        # Today's diary items
        result = await session.execute(
            select(DiaryItem)
            .where(DiaryItem.user_id == user_id, DiaryItem.date == today)
            .order_by(DiaryItem.created_at)
        )
        items = result.scalars().all()

        # Build today's meals dict (slot → list of items)
        meals: dict[str, list] = {
            "breakfast": [], "lunch": [], "dinner": [], "snack": []
        }
        for it in items:
            slot = it.slot if it.slot in meals else "snack"
            meals[slot].append({
                "name": it.name,
                "grams": it.grams,
                "kcal": it.kcal,
                "p": it.protein_g,
                "f": it.fat_g,
                "c": it.carbs_g,
            })

        # Also pull today's bot-tracked meals (merge into any empty slot)
        bot_result = await session.execute(
            select(Meal)
            .where(Meal.user_id == user_id, Meal.date == today)
            .order_by(Meal.created_at)
        )
        bot_meals = bot_result.scalars().all()
        for m in bot_meals:
            bot_items = json.loads(m.items_json)
            for bi in bot_items:
                meals["lunch"].append({
                    "name": bi.get("name", ""),
                    "grams": bi.get("weight_g"),
                    "kcal": _r(bi.get("calories", 0)),
                    "p": round(bi.get("protein_g", 0), 1),
                    "f": round(bi.get("fat_g", 0), 1),
                    "c": round(bi.get("carbs_g", 0), 1),
                })

        # 30-day history from diary_items (daily totals)
        hist_result = await session.execute(
            select(DiaryItem)
            .where(DiaryItem.user_id == user_id, DiaryItem.date >= week_ago, DiaryItem.date < today)
            .order_by(DiaryItem.date)
        )
        hist_items = hist_result.scalars().all()

        history_by_date: dict[date, dict] = {}
        for it in hist_items:
            d = it.date
            if d not in history_by_date:
                history_by_date[d] = {"date": d.isoformat(), "kcal": 0, "p": 0, "f": 0, "c": 0}
            history_by_date[d]["kcal"] += _r(it.kcal)
            history_by_date[d]["p"] += it.protein_g
            history_by_date[d]["f"] += it.fat_g
            history_by_date[d]["c"] += it.carbs_g

        # Round macro history
        history = []
        for d in sorted(history_by_date):
            h = history_by_date[d]
            history.append({
                "date": h["date"],
                "kcal": h["kcal"],
                "p": round(h["p"], 1),
                "f": round(h["f"], 1),
                "c": round(h["c"], 1),
            })

        # Weight log (last 30 days)
        wlog_result = await session.execute(
            select(WeightLog)
            .where(WeightLog.user_id == user_id, WeightLog.date >= week_ago)
            .order_by(WeightLog.date)
        )
        weight_entries = wlog_result.scalars().all()
        weight_log = [{"date": w.date.isoformat(), "weight": w.weight_kg} for w in weight_entries]

        # Today's weight entry
        today_weight = next((w for w in weight_entries if w.date == today), None)

    if not user:
        return {
            "targets": None,
            "meals": meals,
            "history": history,
            "weightLog": weight_log,
            "todayWeightDate": today_weight.date.isoformat() if today_weight else None,
            "todayWeightValue": today_weight.weight_kg if today_weight else None,
        }

    targets = None
    if user.target_kcal:
        targets = {
            "kcal": _r(user.target_kcal),
            "p": _r(user.target_protein_g or 0),
            "f": _r(user.target_fat_g or 0),
            "c": _r(user.target_carbs_g or 0),
        }

    return {
        "name": user.first_name or "",
        "gender": user.gender or "female",
        "goal": user.goal or "maintain",
        "age": user.age or 28,
        "weight": user.weight_kg or 70,
        "height": user.height_cm or 170,
        "activity": user.activity_level or "moderate",
        "targets": targets,
        "meals": meals,
        "history": history,
        "weightLog": weight_log,
        "todayWeightDate": today_weight.date.isoformat() if today_weight else None,
        "todayWeightValue": today_weight.weight_kg if today_weight else None,
    }


@router.delete("/state")
async def reset_state(tg_user: dict = Depends(get_telegram_user)):
    user_id: int = tg_user["id"]
    today = date.today()
    async with AsyncSessionFactory() as session:
        await session.execute(
            delete(DiaryItem).where(DiaryItem.user_id == user_id, DiaryItem.date == today)
        )
        await session.execute(
            delete(WeightLog).where(WeightLog.user_id == user_id, WeightLog.date == today)
        )
        await session.commit()
    return {"ok": True}
