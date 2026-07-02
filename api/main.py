import asyncio
import logging
import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

    @app.get("/")
    async def serve_index():
        return FileResponse(str(WEBAPP_DIR / "index.html"))

    @app.get("/app")
    async def serve_app():
        return FileResponse(str(WEBAPP_DIR / "index.html"))


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
