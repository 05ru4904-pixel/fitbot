from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


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
