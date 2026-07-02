import logging
from io import BytesIO

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from handlers.common import (
    build_composition_keyboard,
    format_composition_message,
    main_menu_keyboard,
    BTN_ANALYSIS,
)
from services import vision
from states import FoodStates

logger = logging.getLogger(__name__)
router = Router()

WELCOME_TEXT = (
    "Привет! 👋\n\n"
    "Я помогу тебе считать калории по фото еды.\n\n"
    "Просто отправь мне фотографию блюда — я определю состав, "
    "ты подтвердишь или поправишь, и получишь калории и БЖУ."
)

ANALYSIS_TEXT = (
    "Отправь мне фото своей еды — "
    "я определю состав, посчитаю калории и БЖУ 📸"
)


@router.message(Command("start"))
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("analysis"))
@router.message(F.text == BTN_ANALYSIS)
async def handle_analysis(message: Message, state: FSMContext):
    await state.set_state(FoodStates.waiting_for_photo)
    await message.answer(ANALYSIS_TEXT)


@router.callback_query(F.data == "start_analysis")
async def handle_start_analysis(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(FoodStates.waiting_for_photo)
    await callback.message.answer(ANALYSIS_TEXT)


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext, bot: Bot):
    await state.clear()

    processing_msg = await message.answer("⏳ Анализирую фото...")

    try:
        photo = message.photo[-1]
        buf = BytesIO()
        await bot.download(photo, destination=buf)
        image_bytes = buf.getvalue()

        result = await vision.recognize_food(
            image_bytes,
            file_unique_id=photo.file_unique_id,
        )

        dishes = [d.model_dump() for d in result.dishes]
        await state.update_data(dishes=dishes)
        await state.set_state(FoodStates.confirming_composition)

        await processing_msg.edit_text(
            format_composition_message(dishes),
            reply_markup=build_composition_keyboard(),
        )

    except ValueError as e:
        await processing_msg.edit_text(
            f"🙈 {e}\n\nПопробуй сфотографировать еду ещё раз."
        )
        await state.clear()
    except Exception as e:
        logger.error("Photo processing error: %s", e)
        await processing_msg.edit_text(
            "😔 Что-то пошло не так при анализе фото. Попробуй ещё раз."
        )
        await state.clear()
