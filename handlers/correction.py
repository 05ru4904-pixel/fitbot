import json
import logging
from datetime import date

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from db.database import AsyncSessionFactory
from db.models import Meal
from handlers.common import build_composition_keyboard, format_composition_message
from models.schemas import CalorieResult
from services import calorie_calc, vision
from states import FoodStates

logger = logging.getLogger(__name__)
router = Router()


def _format_result_message(result: CalorieResult) -> str:
    lines = ["🍽 Результат:", ""]
    for item in result.items:
        lines.append(f"• {item.name} ({item.weight_g}г) — {int(item.calories)} ккал")
    lines.append("")
    lines.append(f"Итого: ~{result.calorie_range} ккал")
    t = result.total
    lines.append(f"Б: {t.protein_g:.0f}г | Ж: {t.fat_g:.0f}г | У: {t.carbs_g:.0f}г")
    return "\n".join(lines)


def _save_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="save_meal"),
            InlineKeyboardButton(text="❌ Нет", callback_data="skip_meal"),
        ]
    ])


@router.callback_query(F.data == "confirm", FoodStates.confirming_composition)
async def handle_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    dishes = data.get("dishes", [])

    await callback.message.edit_text("⏳ Считаю калории...")

    try:
        result = await calorie_calc.calculate_calories(dishes)

        meal_data = {
            "calories": result.total.calories,
            "protein_g": result.total.protein_g,
            "fat_g": result.total.fat_g,
            "carbs_g": result.total.carbs_g,
            "items": [item.model_dump() for item in result.items],
        }
        await state.update_data(last_meal=meal_data)
        await state.set_state(FoodStates.done)

        await callback.message.edit_text(_format_result_message(result))
        await callback.message.answer(
            "Добавить этот приём в сегодняшнюю сводку?",
            reply_markup=_save_keyboard(),
        )
    except Exception as e:
        logger.error("Calorie calculation error: %s", e)
        await callback.message.edit_text(
            "😔 Не удалось рассчитать калории. Попробуй отправить фото заново."
        )
        await state.clear()


@router.callback_query(F.data == "save_meal", FoodStates.done)
async def handle_save_meal(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    meal_data = data.get("last_meal")

    async with AsyncSessionFactory() as session:
        meal = Meal(
            user_id=callback.from_user.id,
            date=date.today(),
            calories=meal_data["calories"],
            protein_g=meal_data["protein_g"],
            fat_g=meal_data["fat_g"],
            carbs_g=meal_data["carbs_g"],
            items_json=json.dumps(meal_data["items"], ensure_ascii=False),
        )
        session.add(meal)
        await session.commit()

    await callback.message.edit_text("✅ Добавлено в дневник! Посмотреть: /today")
    await callback.message.answer("📸 Отправь следующее фото, когда будешь готов!")


@router.callback_query(F.data == "skip_meal", FoodStates.done)
async def handle_skip_meal(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Не добавлено.")
    await callback.message.answer("📸 Отправь следующее фото, когда будешь готов!")


@router.callback_query(F.data == "correct", FoodStates.confirming_composition)
async def handle_correct_button(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(FoodStates.correcting)
    await callback.message.answer(
        "✏️ Напиши, что не так (например: «рис был 300г, а не 200»):"
    )


@router.message(FoodStates.correcting, F.text)
async def handle_correction_text(message: Message, state: FSMContext):
    data = await state.get_data()
    dishes = data.get("dishes", [])

    processing_msg = await message.answer("⏳ Обновляю состав...")

    try:
        result = await vision.update_composition(dishes, message.text)
        updated_dishes = [d.model_dump() for d in result.dishes]
        await state.update_data(dishes=updated_dishes)
        await state.set_state(FoodStates.confirming_composition)

        await processing_msg.edit_text(
            format_composition_message(updated_dishes),
            reply_markup=build_composition_keyboard(),
        )
    except Exception as e:
        logger.error("Correction error: %s", e)
        await processing_msg.edit_text(
            "😔 Не удалось применить правку. Попробуй снова или отправь новое фото."
        )
        await state.set_state(FoodStates.confirming_composition)
