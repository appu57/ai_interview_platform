import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from backend.core.security import get_settings
from backend.middleware.cors_csrf import add_csrf_middleware, add_cors_middleware
from backend.middleware.error_handler import add_error_handlers
from backend.api.routes.auth import router as auth_router
from backend.api.routes.interview import router as user_preferences_router
from backend.api.routes.interview import interview_router
from backend.agents.tools.code_executor import router as code_router
from backend.webrtc.livekit_client import router as livekit_router
from backend.db.session import close_db, get_engine, Base
from backend.db.checkpointer import init_checkpointer, close_checkpointer
from backend.agents.graph.interview_graph import build_interview_graph
from backend.agents.graph.practice_graph import build_tutor_graph
from backend.api.routes.practice import router as practice_router
from backend.agents.nodes.tutor_nodes.ollama_warmkeeper import warmkeeper_loop

logger = logging.getLogger(__name__)

get_settings()


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
        raise

    app.state.warmkeeper_task = asyncio.create_task(warmkeeper_loop())

    logger.info("Initializing LangGraph Postgres checkpointer...")
    checkpointer = await init_checkpointer()
    app.state.interview_graph = build_interview_graph(checkpointer)
    app.state.tutor_graph = build_tutor_graph(checkpointer=checkpointer)
    logger.info("LangGraph interview_graph compiled with durable Postgres checkpointing.")

    yield

    logger.info("Shutting down system: Disposing active connection pools...")

    app.state.warmkeeper_task.cancel()
    try:
        await app.state.warmkeeper_task
    except asyncio.CancelledError:
        pass

    await close_checkpointer()
    await close_db()
    logger.info("System clean shut-down complete.")


app = FastAPI(
    title="AI Interview platform",
    version="1.0.0",
    description="",
    lifespan=lifespan,
)

add_csrf_middleware(app)
add_cors_middleware(app)
add_error_handlers(app)

app.include_router(auth_router)
app.include_router(user_preferences_router)
app.include_router(interview_router)
app.include_router(livekit_router)
app.include_router(code_router)
app.include_router(practice_router)


@app.get("/health")
async def health() -> dict:
    warmkeeper_task = getattr(app.state, "warmkeeper_task", None)
    warmkeeper_alive = bool(warmkeeper_task) and not warmkeeper_task.done()
    graphs_ready = hasattr(app.state, "tutor_graph") and hasattr(app.state, "interview_graph")
    ok = warmkeeper_alive and graphs_ready
    body = {
        "status": "ok" if ok else "degraded",
        "warmkeeper_alive": warmkeeper_alive,
        "graphs_ready": graphs_ready,
    }
    return JSONResponse(content=body, status_code=200 if ok else 503)