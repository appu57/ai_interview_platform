import asyncio
from contextlib import asynccontextmanager
import logging
import os
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, FastAPI
from backend.core.security import get_settings
from backend.middleware.cors_csrf import add_csrf_middleware, add_cors_middleware
from backend.middleware.error_handler import add_error_handlers
from backend.api.routes.auth import router as auth_router
from backend.db.session import close_db, get_db, Base, get_engine
from backend.db.models import User
from backend.db.repository import UserRepository

logger = logging.getLogger(__name__)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing system: checking and building database tables...")
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schemas verified and ready!")
    except Exception as e:
        logger.error(f"Critical failure during database boot-up synchronization: {e}")
        raise e

    yield # --- WEB TRAFFIC OCCURS DURING THIS YIELD ---

    logger.info("Shutting down system: Disposing active connection pools...")
    await close_db()
    logger.info("System clean shut-down complete.")

app =  FastAPI(
    title= "AI Interview platform",
    version="1.0.0",
    description="",
    lifespan= lifespan
)

add_csrf_middleware(app)
add_cors_middleware(app)
add_error_handlers(app)

app.include_router(auth_router)
