from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

# Labels for the persistent reply-keyboard menu (bottom of the chat).
BTN_ANALYSIS = "📸 Посчитать калории"
BTN_TODAY = "🍽 Сегодня"
BTN_WEEK = "📊 Неделя"
BTN_PROFILE = "👤 Профиль"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ANALYSIS)],
            [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_WEEK)],
            [KeyboardButton(text=BTN_PROFILE)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def build_composition_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Верно", callback_data="confirm"),
            InlineKeyboardButton(text="✏️ Исправить", callback_data="correct"),
        ]
    ])


def format_composition_message(dishes: list[dict]) -> str:
    lines = ["Вижу на фото:"]
    for dish in dishes:
        lines.append(f"• {dish['name']} — ~{dish['estimated_weight_g']} г")
    lines.append("")
    lines.append("Всё верно?")
    return "\n".join(lines)
