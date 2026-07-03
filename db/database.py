import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

logger = logging.getLogger(__name__)

# A warm connection pool avoids paying the TCP+TLS handshake to Railway on every query.
# pre_ping drops dead connections (Railway closes idle ones) before they cause errors;
# recycle refreshes them before Railway's idle timeout.
engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=30,
    connect_args={"timeout": 10, "command_timeout": 20},
)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Composite indexes matching the exact `WHERE user_id=? AND date=?` filters used across the
# app. Postgres does not auto-index foreign-key columns, so these are created explicitly.
_COMPOSITE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_diary_items_user_date ON diary_items (user_id, date)",
    "CREATE INDEX IF NOT EXISTS ix_meals_user_date ON meals (user_id, date)",
    "CREATE INDEX IF NOT EXISTS ix_weight_log_user_date ON weight_log (user_id, date)",
)


async def init_db(retries: int = 5, delay: float = 1.5):
    """Create tables and indexes. Retries because Railway's private network
    (`*.railway.internal`) can become resolvable a moment after container boot."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                for stmt in _COMPOSITE_INDEXES:
                    await conn.execute(text(stmt))
            return
        except Exception as e:  # noqa: BLE001 — retry on any connection/DNS error
            last_error = e
            logger.warning("init_db attempt %d/%d failed: %s", attempt, retries, e)
            if attempt < retries:
                await asyncio.sleep(delay)
    raise RuntimeError(f"Database init failed after {retries} attempts") from last_error


async def get_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session
