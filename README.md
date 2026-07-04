# FitBot — Telegram-бот и Mini App для подсчёта калорий

Телеграм-бот, который распознаёт еду по фото и считает калории + КБЖУ, плюс встроенное
Mini App — дневник питания с онбордингом, кольцом калорий, графиками веса и статистикой.

## Возможности

**Бот:**
- Отправь фото еды → бот определяет состав блюда, ты подтверждаешь или правишь → получаешь калории и БЖУ, затем можешь сохранить приём в дневник
- Меню действий на reply-клавиатуре: «Посчитать калории», «Сегодня», «Неделя», «Профиль»
- Кнопка ≡ открывает Mini App («Открыть дневник»)

**Команды:** `/start`, `/analysis` (посчитать калории), `/profile`, `/today` (что съедено сегодня), `/week` (сводка за неделю).

**Mini App (дневник питания):**
- Онбординг: пол, цель, возраст/вес/рост, активность → расчёт суточной нормы
- Главная: кольцо калорий, полоски КБЖУ, рацион по приёмам пищи
- Статистика: график веса, история КБЖУ, средние показатели
- Учёт веса, синхронизация с ботом через общую базу

### Как работает распознавание по фото

```
Фото еды
   │  vision.recognize_food()  (gemini vision)
   ▼
Состав блюда  ─►  [✅ Верно]        [✏️ Исправить]
   │                 │                   │  текст правки
   │                 │                   ▼
   │                 │            vision.update_composition() ─► обратно к составу
   │                 ▼
   │   calorie_calc.calculate_calories()  ─►  калории + КБЖУ
   │                 ▼
   │        «Добавить в сводку?»  ─►  [✅ Да] сохранить в таблицу meals
   ▼
Приём виден в /today, /week и в Mini App (дневник)
```

Два обращения к модели: сначала распознавание состава (vision), затем расчёт КБЖУ по
составу (text). Сохранённые через бота приёмы и записи из Mini App живут в общей базе.

## Стек

- **Python 3.11+**
- **aiogram 3.29+** — Telegram-бот (FSM in-memory)
- **OpenAI SDK** через агрегатор [polza.ai](https://polza.ai), модель `google/gemini-2.5-flash-lite` — vision для распознавания еды
- **FastAPI + uvicorn** — REST API для Mini App
- **SQLAlchemy 2.0 (async) + asyncpg** — PostgreSQL
- **Telegram WebApp** — Mini App с валидацией `initData` (HMAC-SHA256)
- Фронтенд Mini App — компонентный фреймворк DC Logic (React, self-hosted)

Бот и Mini App API работают **в одном процессе**: `bot.py` запускает и long-polling
aiogram, и uvicorn-сервер одновременно (`asyncio.gather`).

## Структура

```
FitBot/
├── bot.py                  # точка входа: бот + Mini App API в одном процессе
├── config.py               # настройки из .env (+ конвертация URL для asyncpg)
├── states.py               # FSM states
├── Dockerfile              # сборка для Railway
├── handlers/               # хендлеры бота
│   ├── common.py           # reply-клавиатура, форматтеры
│   ├── photo.py            # приём фото, /start
│   ├── correction.py       # подтверждение / правка состава
│   ├── diary.py            # /today, /week
│   └── profile.py          # /profile, редактирование профиля
├── services/
│   ├── vision.py           # распознавание еды (vision) + правка состава
│   └── calorie_calc.py     # расчёт КБЖУ
├── api/                    # FastAPI Mini App API
│   ├── main.py             # приложение, gzip, статика, версионирование ассетов
│   ├── auth.py             # валидация Telegram initData
│   └── routers/            # /state, /meals, /weight, /profile
├── db/
│   ├── database.py         # async engine, пул соединений, init_db
│   └── models.py           # User, Meal, DiaryItem, WeightLog
├── webapp/                 # Mini App (self-hosted)
│   ├── index.html          # приложение (DC Logic + inline UI)
│   ├── support.js          # DC-runtime
│   └── react*.min.js       # React (локально, без CDN)
├── models/schemas.py       # Pydantic-модели ответов модели
├── prompts/                # системные промпты
└── tests/test_vision.py    # автономный тест распознавания
```

## Переменные окружения

Скопируй `.env.example` в `.env` и заполни:

```env
TELEGRAM_BOT_TOKEN=...              # токен бота от @BotFather
GEMINI_API_KEY=...                  # ключ polza.ai
DATABASE_URL=postgresql://...       # PostgreSQL (Railway даёт автоматически)
WEBAPP_URL=https://your-app/app     # публичный URL Mini App (после деплоя)
```

## Локальный запуск

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate        # Linux / macOS
pip install -r requirements.txt

python bot.py                      # запускает бота и Mini App API
```

Mini App будет доступен на `http://localhost:8000` (для Telegram нужен HTTPS — см. деплой).

## API Mini App

Все запросы требуют заголовок `X-Telegram-Init-Data` (проверка подписи Telegram).

| Метод  | Путь                | Назначение                             |
|--------|---------------------|----------------------------------------|
| GET    | `/api/state`        | Профиль, рацион на сегодня, история, вес |
| DELETE | `/api/state`        | Сброс данных (возврат к онбордингу)    |
| PUT    | `/api/meals/today`  | Обновить сегодняшний рацион            |
| POST   | `/api/weight`       | Записать вес за день                   |
| DELETE | `/api/weight`       | Удалить сегодняшний вес                |
| PUT    | `/api/profile`      | Обновить профиль и нормы КБЖУ          |

## База данных

- `users` — профиль, цель, суточные нормы КБЖУ
- `meals` — приёмы пищи из фото-анализа бота
- `diary_items` — записи дневника Mini App по слотам (завтрак/обед/ужин/перекус)
- `weight_log` — журнал веса

## Деплой (Railway)

1. Запушить репозиторий на GitHub
2. Railway → **New Project** → **Deploy from GitHub repo**
3. Добавить **PostgreSQL** (переменная `DATABASE_URL` появится сама)
4. Прописать переменные `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`
5. После деплоя сгенерировать домен, вписать его + `/app` в `WEBAPP_URL`
6. Кнопка-меню Mini App регистрируется автоматически при старте бота

Сборка идёт по `Dockerfile` (Python 3.11-slim). Ассеты Mini App версионируются при каждом
старте, чтобы Telegram не отдавал закэшированную версию.

## Тест распознавания без бота

```bash
python tests/test_vision.py path/to/food_photo.jpg
```
