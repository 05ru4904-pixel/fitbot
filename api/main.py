import asyncio
import logging
import pathlib
import re
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.routers import meals, profile_api, state, weight
from db.database import init_db
import db.models  # noqa: F401 — must be imported so SQLAlchemy registers all tables

logger = logging.getLogger(__name__)

app = FastAPI(title="FitBot Mini App API", docs_url=None, redoc_url=None)

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
    await init_db()
    logger.info("Mini App API started, DB initialized.")


if __name__ == "__main__":
    import os
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port)
