import logging
import pathlib
import re
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, ORJSONResponse
from fastapi.staticfiles import StaticFiles

from api.routers import goal, meals, profile_api, state, weight
import db.models  # noqa: F401 — must be imported so SQLAlchemy registers all tables

logger = logging.getLogger(__name__)

# ORJSONResponse serializes API JSON noticeably faster than the stdlib default.
app = FastAPI(
    title="FitBot Mini App API",
    docs_url=None,
    redoc_url=None,
    default_response_class=ORJSONResponse,
)

# GZip shrinks the ~200KB JS bundle and the /state payload by 60-75% over mobile.
app.add_middleware(GZipMiddleware, minimum_size=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(state.router, prefix="/api")
app.include_router(meals.router, prefix="/api")
app.include_router(weight.router, prefix="/api")
app.include_router(profile_api.router, prefix="/api")
app.include_router(goal.router, prefix="/api")

# Serve webapp static files
WEBAPP_DIR = pathlib.Path(__file__).parent.parent / "webapp"

if WEBAPP_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR)), name="static")

    # Telegram's in-app WebView can keep a previously opened Mini App alive in memory
    # (or otherwise cache aggressively) regardless of HTTP cache headers. A version tag
    # that changes on every process start (deploy/restart) forces every asset URL —
    # including the JS files loaded from the HTML — to be treated as brand new.
    _ASSET_VERSION = str(int(time.time()))
    _NO_CACHE_HEADERS = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }

    def _load_index_html() -> str:
        html = (WEBAPP_DIR / "index.html").read_text(encoding="utf-8")
        return re.sub(
            r'(src="/static/[^"]+\.js)"',
            rf'\1?v={_ASSET_VERSION}"',
            html,
        )

    _INDEX_HTML = _load_index_html()

    @app.get("/")
    async def serve_index():
        return HTMLResponse(_INDEX_HTML, headers=_NO_CACHE_HEADERS)

    @app.get("/app")
    async def serve_app():
        return HTMLResponse(_INDEX_HTML, headers=_NO_CACHE_HEADERS)


@app.on_event("startup")
async def startup():
    # Schema is initialized once by bot.py before the server starts (see bot.py:main),
    # so no init_db() call here — avoids running create_all twice on boot.
    logger.info("Mini App API started.")


if __name__ == "__main__":
    # Standalone run (dev only). Production launches via bot.py, which runs init_db first.
    import asyncio
    import os
    import uvicorn

    from db.database import init_db

    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_db())
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port)
