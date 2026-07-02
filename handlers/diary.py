import json
import logging
from collections import defaultdict
from datetime import date, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from db.database import AsyncSessionFactory
from db.models import Meal
from handlers.common import BTN_TODAY, BTN_WEEK

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("today"))
@router.message(F.text == BTN_TODAY)
async def handle_today(message: Message):
    today = date.today()

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Meal)
            .where(Meal.user_id == message.from_user.id, Meal.date == today)
            .order_by(Meal.created_at)
        )
        meals = result.scalars().all()

    if not meals:
        await message.answer(
            f"📅 {today.strftime('%d.%m.%Y')} — дневник пуст.\n\n"
            "Отправь фото еды и добавь приём в сводку!"
        )
        return

    lines = [f"📅 Сегодня, {today.strftime('%d.%m.%Y')}:\n"]
    total_cal = total_p = total_f = total_c = 0.0

    for i, meal in enumerate(meals, 1):
        items = json.loads(meal.items_json)
        lines.append(f"🍽 Приём {i}:")
        for item in items:
            lines.append(f"  • {item['name']} ({item['weight_g']}г) — {int(item['calories'])} ккал")
        lines.append(
            f"  Итого: {int(meal.calories)} ккал | "
            f"Б:{meal.protein_g:.0f} Ж:{meal.fat_g:.0f} У:{meal.carbs_g:.0f}\n"
        )
        total_cal += meal.calories
        total_p += meal.protein_g
        total_f += meal.fat_g
        total_c += meal.carbs_g

    lines.append("📊 Итого за день:")
    lines.append(f"Калории: {int(total_cal)} ккал")
    lines.append(f"Б: {total_p:.0f}г | Ж: {total_f:.0f}г | У: {total_c:.0f}г")

    await message.answer("\n".join(lines))


@router.message(Command("week"))
@router.message(F.text == BTN_WEEK)
async def handle_week(message: Message):
    today = date.today()
    week_ago = today - timedelta(days=6)

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Meal)
            .where(
                Meal.user_id == message.from_user.id,
                Meal.date >= week_ago,
                Meal.date <= today,
            )
            .order_by(Meal.date)
        )
        meals = result.scalars().all()

    if not meals:
        await message.answer("За последние 7 дней в дневнике нет записей.")
        return

    days: dict[date, list[Meal]] = defaultdict(list)
    for meal in meals:
        days[meal.date].append(meal)

    lines = [
        f"📅 Сводка за 7 дней "
        f"({week_ago.strftime('%d.%m')} — {today.strftime('%d.%m.%Y')}):\n"
    ]
    total_cal = total_p = total_f = total_c = 0.0

    for d in sorted(days.keys()):
        day_meals = days[d]
        day_cal = sum(m.calories for m in day_meals)
        day_p = sum(m.protein_g for m in day_meals)
        day_f = sum(m.fat_g for m in day_meals)
        day_c = sum(m.carbs_g for m in day_meals)

        lines.append(
            f"📆 {d.strftime('%d.%m')} — {int(day_cal)} ккал | "
            f"Б:{day_p:.0f} Ж:{day_f:.0f} У:{day_c:.0f}"
        )
        total_cal += day_cal
        total_p += day_p
        total_f += day_f
        total_c += day_c

    lines.append(f"\n📊 Итого за неделю:")
    lines.append(f"Калории: {int(total_cal)} ккал")
    lines.append(f"Б: {total_p:.0f}г | Ж: {total_f:.0f}г | У: {total_c:.0f}г")

    await message.answer("\n".join(lines))
