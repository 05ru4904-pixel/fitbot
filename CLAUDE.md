# CLAUDE.md — FitBot (контекст проекта для новых сессий)

Этот файл читается автоматически в начале сессии. Здесь — суть проекта, состояние
деплоя и выученные подводные камни, чтобы не терять контекст между чатами.

## Что это
Telegram-бот для подсчёта калорий по фото еды + встроенное Mini App (дневник питания:
онбординг, кольцо калорий, графики веса, статистика). Интерфейс — русский.

## Архитектура (важно)
- **Бот и Mini App API работают в ОДНОМ процессе.** `bot.py` через `asyncio.gather`
  запускает одновременно long-polling aiogram и uvicorn-сервер FastAPI. Один сервис на Railway.
- Vision-распознавание: **OpenAI SDK → агрегатор polza.ai** (`base_url=https://polza.ai/api/v1`),
  модель `google/gemini-2.5-flash-lite`. Два вызова: `vision.recognize_food` (состав) →
  `calorie_calc.calculate_calories` (КБЖУ).
- База: **PostgreSQL**, SQLAlchemy 2.0 async + asyncpg. Таблицы: `users`, `meals`
  (приёмы из бота), `diary_items` (записи Mini App по слотам), `weight_log`.
- Mini App: `webapp/index.html` — фреймворк **DC Logic** (React) от claude.ai/design.
  `support.js` — DC-runtime. React **self-hosted** в `webapp/react*.min.js` (не CDN).
- Фронтенд Mini App — один большой файл с inline-стилями + `<script type="text/x-dc">`
  (класс `Component extends DCLogic`). Шаблоны: `sc-if`, `sc-for`, `{{ }}`. НЕ ломать эту логику.

## Деплой
- **Railway** (free tier, 500MB RAM), деплой из **GitHub** (репозиторий
  `05ru4904-pixel/fitbot`). Сборка по `Dockerfile` (python:3.11-slim), НЕ nixpacks.
- Переменные Railway: `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `DATABASE_URL`, `WEBAPP_URL`.
- `WEBAPP_URL` = публичный домен сервиса + `/app`. Пока он не задан (или начинается с
  `https://example`), кнопка дневника в боте скрыта.
- Кнопка-меню ≡ Mini App регистрируется автоматически при старте бота (в `bot.py`),
  с версией `?v=<время>` в URL — против кэша Telegram.

## Выученные подводные камни (НЕ повторять ошибки)
- **Telegram агрессивно кэширует Mini App.** HTTP `no-cache` не спасает — клиент держит
  WebView в памяти. Решение уже внедрено: `api/main.py` добавляет `?v=<время старта>` к
  URL ассетов (`support.js`, React) в HTML, а `bot.py` — к самому `WEBAPP_URL`. После
  деплоя для проверки НАДО полностью закрыть Telegram и открыть заново.
- **Статику Mini App отдавать только по `/static/...`** — относительные `./` пути дают 404
  на сервере (ломает всё, кнопки «мёртвые», виден сырой шаблон с `{{ }}`).
- **DB: используется ПУБЛИЧНЫЙ `DATABASE_URL`** (`...proxy.rlwy.net`). Внутренний
  `postgres.railway.internal` НЕ резолвится в этом проекте (`Name or service not known`)
  даже с ретраями — не тратить время, оставить публичный. Пул соединений (в `db/database.py`)
  уже даёт основной выигрыш скорости (тёплые соединения: 277мс→~0-16мс).
- **Кэш Mini App привязан к Telegram user id** (`fd_state_v1_<id>` в localStorage) —
  чтобы данные не утекали между аккаунтами на одном устройстве.
- **Онбординг vs главный экран:** сервер — источник правды (`/api/state`). Есть загрузочный
  сплэш и мгновенная гидратация из кэша, чтобы у зарегистрированных не мелькал экран «Начать».
- **git push из РФ:** бывает `schannel: failed to receive handshake`. Фикс:
  `git config --global http.sslBackend openssl`, иногда нужен VPN.

## Последние крупные работы
- Оптимизация бэкенда: пул соединений БД + ретраи `init_db`, параллельные запросы в
  `GET /api/state` (`asyncio.gather`), GZip, ORJSON, составные индексы.
- Полировка UI Mini App (скилл `ui-ux-pro-max`): дизайн-токены `:root`, табличные цифры,
  контраст, press-feedback `scale(.97)`, Telegram haptics, `prefers-reduced-motion`,
  свечение кольца, сетка на графиках, тач-цели, focus-visible. Гамма прежняя (фиолетовый+лайм).

## Команды
- Локальный запуск: `python bot.py` (поднимает и бота, и Mini App API на :8000).
- Тест распознавания: `python tests/test_vision.py path/to/photo.jpg`.
- Деплой: коммит + `git push` → Railway пересобирает сам.

## Стиль общения
Пользователь — не программист, объяснять простыми словами по-русски, по шагам, без жаргона.
Он работает с Railway/GitHub через веб-интерфейс и PowerShell; команды давать готовыми.

## Секреты
`.env` в `.gitignore` — токены НИКОГДА не коммитить. `.env.example` — шаблон без значений.
