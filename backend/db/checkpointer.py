import logging
from typing import Optional

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from backend.core.security import get_settings

logger = logging.getLogger("mockai-adaptive-graph")

_checkpoint_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None

_CONNECTION_KWARGS = {
    "autocommit": True,
    "prepare_threshold": 0,
}


def _to_psycopg_dsn(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + database_url[len("postgresql+asyncpg://"):]
    if database_url.startswith("postgres+asyncpg://"):
        return "postgresql://" + database_url[len("postgres+asyncpg://"):]
    return database_url


async def init_checkpointer() -> AsyncPostgresSaver:
    global _checkpoint_pool, _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    settings = get_settings()
    dsn = _to_psycopg_dsn(settings.database_url)

    logger.info("Initializing LangGraph checkpoint connection pool...")
    _checkpoint_pool = AsyncConnectionPool(
        conninfo=dsn,
        max_size=20,
        kwargs=_CONNECTION_KWARGS,
        open=False,
    )
    await _checkpoint_pool.open()

    _checkpointer = AsyncPostgresSaver(_checkpoint_pool)
    await _checkpointer.setup()
    logger.info("LangGraph checkpoint tables verified/created.")

    return _checkpointer


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError(
            "Checkpointer not initialized — init_checkpointer() must run in "
            "the app's lifespan startup before any request can use the "
            "interview graph."
        )
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpoint_pool, _checkpointer
    if _checkpoint_pool is not None:
        await _checkpoint_pool.close()
        _checkpoint_pool = None
        _checkpointer = None
        logger.info("LangGraph checkpoint connection pool closed.")
