# FitBot — Telegram-бот для распознавания калорий по фото

Отправь фото еды — бот определит состав блюда, ты подтвердишь или поправишь, и получишь калории + БЖУ.

## Стек

- Python 3.11+
- aiogram 3.x (FSM in-memory)
- Claude API (anthropic SDK) — vision для распознавания, text для расчёта

## Установка

```bash
cd d:\VS\FitBot

# Создать и активировать виртуальное окружение
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux / macOS

pip install -r requirements.txt
```

## Настройка

Скопируй `.env.example` в `.env` и заполни токены:

```bash
cp .env.example .env
```

```env
TELEGRAM_BOT_TOKEN=...
ANTHROPIC_API_KEY=...
```

## Запуск бота

```bash
python bot.py
```

## Тест промптов без бота

```bash
python tests/test_vision.py path/to/food_photo.jpg
```

Скрипт прогоняет оба промпта (распознавание + расчёт калорий) и выводит результат в консоль.

## Структура проекта

```
FitBot/
├── bot.py                   # точка входа
├── config.py                # загрузка токенов из .env
├── states.py                # FSM states
├── handlers/
│   ├── common.py            # shared keyboard / formatters
│   ├── photo.py             # приём фото, /start
│   └── correction.py        # подтверждение / правка / расчёт
├── services/
│   ├── vision.py            # Claude vision: распознавание и правка состава
│   └── calorie_calc.py      # Claude text: расчёт КБЖУ
├── models/
│   └── schemas.py           # Pydantic-модели для JSON-ответов Claude
├── prompts/
│   ├── recognize.txt        # системный промпт для распознавания и правки
│   └── calculate.txt        # системный промпт для расчёта калорий
└── tests/
    └── test_vision.py       # автономный тест промптов
```

## FSM-диалог

```
/start или новое фото
       │
       ▼
 waiting_for_photo
       │ (фото получено)
       ▼
 recognize_food() ──► показать состав с кнопками
       │
       ▼
confirming_composition
       │
  ✅ Верно          ✏️ Исправить
       │                  │
       ▼                  ▼
calculate_calories()   correcting
       │                  │ (текст правки)
       ▼                  ▼
     done           update_composition()
       │                  │
       ▼                  └──► confirming_composition
 показать результат
```
