import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from db.database import AsyncSessionFactory
from db.models import User
from states import ProfileStates

logger = logging.getLogger(__name__)
router = Router()

ACTIVITY_LABELS = {
    "sedentary": "🪑 Сидячий (нет спорта)",
    "light": "🚶 Лёгкий (1–2 раза в неделю)",
    "moderate": "🏃 Умеренный (3–5 раз в неделю)",
    "active": "💪 Активный (6–7 раз в неделю)",
    "very_active": "🔥 Очень активный (спорт + физ. работа)",
}


def _gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male"),
            InlineKeyboardButton(text="👩 Женский", callback_data="gender_female"),
        ]
    ])


def _activity_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"activity_{key}")]
        for key, label in ACTIVITY_LABELS.items()
    ])


def _format_profile(user: User) -> str:
    gender = "Мужской" if user.gender == "male" else "Женский"
    activity = ACTIVITY_LABELS.get(user.activity_level, user.activity_level)
    return (
        f"👤 Твой профиль:\n\n"
        f"Пол: {gender}\n"
        f"Возраст: {user.age} лет\n"
        f"Вес: {user.weight_kg} кг\n"
        f"Рост: {user.height_cm} см\n"
        f"Активность: {activity}"
    )


async def _get_user(telegram_id: int) -> User | None:
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()


async def _save_user(user: User):
    async with AsyncSessionFactory() as session:
        await session.merge(user)
        await session.commit()


@router.message(Command("profile"))
async def handle_profile(message: Message, state: FSMContext):
    user = await _get_user(message.from_user.id)
    if user and user.gender:
        edit_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_profile")]
        ])
        await message.answer(_format_profile(user), reply_markup=edit_keyboard)
    else:
        await state.set_state(ProfileStates.entering_gender)
        await message.answer(
            "Заполним твой профиль — это нужно для точного расчёта нормы калорий.\n\n"
            "Выбери пол:",
            reply_markup=_gender_keyboard(),
        )


@router.callback_query(F.data == "edit_profile")
async def handle_edit_profile(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ProfileStates.entering_gender)
    await callback.message.answer("Выбери пол:", reply_markup=_gender_keyboard())


@router.callback_query(F.data.in_({"gender_male", "gender_female"}), ProfileStates.entering_gender)
async def handle_gender(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    gender = "male" if callback.data == "gender_male" else "female"
    await state.update_data(gender=gender)
    await state.set_state(ProfileStates.entering_age)
    await callback.message.answer("Сколько тебе лет? (введи число)")


@router.message(ProfileStates.entering_age, F.text)
async def handle_age(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (10 <= int(message.text) <= 100):
        await message.answer("Введи возраст числом от 10 до 100:")
        return
    await state.update_data(age=int(message.text))
    await state.set_state(ProfileStates.entering_weight)
    await message.answer("Какой у тебя вес? (кг, например: 75)")


@router.message(ProfileStates.entering_weight, F.text)
async def handle_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text.replace(",", "."))
        assert 30 <= weight <= 300
    except (ValueError, AssertionError):
        await message.answer("Введи вес числом от 30 до 300 кг:")
        return
    await state.update_data(weight_kg=weight)
    await state.set_state(ProfileStates.entering_height)
    await message.answer("Какой у тебя рост? (см, например: 175)")


@router.message(ProfileStates.entering_height, F.text)
async def handle_height(message: Message, state: FSMContext):
    try:
        height = float(message.text.replace(",", "."))
        assert 100 <= height <= 250
    except (ValueError, AssertionError):
        await message.answer("Введи рост числом от 100 до 250 см:")
        return
    await state.update_data(height_cm=height)
    await state.set_state(ProfileStates.entering_activity)
    await message.answer("Выбери уровень физической активности:", reply_markup=_activity_keyboard())


@router.callback_query(F.data.startswith("activity_"), ProfileStates.entering_activity)
async def handle_activity(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    activity = callback.data.replace("activity_", "")
    data = await state.get_data()
    await state.clear()

    user = User(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        gender=data["gender"],
        age=data["age"],
        weight_kg=data["weight_kg"],
        height_cm=data["height_cm"],
        activity_level=activity,
    )
    await _save_user(user)

    await callback.message.answer(
        _format_profile(user) + "\n\n✅ Профиль сохранён!"
    )
