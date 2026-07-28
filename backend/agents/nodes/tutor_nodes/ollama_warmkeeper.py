import asyncio
import logging
import os

import httpx

from backend.agents.nodes.tutor_nodes.latency_budget import mark_model_warm, mark_ping_failed

logger = logging.getLogger("mockai-ollama-warmkeeper")

OLLAMA_NATIVE_URL = os.getenv("OLLAMA_NATIVE_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("FINE_TUNED_TUTOR_MODEL", "mockai-tutor-new:latest")
KEEP_ALIVE_DURATION = "10m"
PING_INTERVAL_SECONDS = 4 * 60.0

_client = httpx.AsyncClient(timeout=15.0)


async def _ping_once() -> bool:
    try:
        resp = await _client.post(
            f"{OLLAMA_NATIVE_URL}/api/generate",
            json={"model": MODEL_NAME, "prompt": "", "keep_alive": KEEP_ALIVE_DURATION, "stream": False},
        )
        resp.raise_for_status()
        mark_model_warm()
        return True
    except Exception as e:
        logger.error("[ollama_warmkeeper] keep-alive ping failed: %s: %s", type(e).__name__, e or "(no message)")
        mark_ping_failed()
        return False


async def warmkeeper_loop() -> None:
    logger.info("[ollama_warmkeeper] starting, pinging %s every %.0fs", MODEL_NAME, PING_INTERVAL_SECONDS)
    ok = await _ping_once()
    logger.info("[ollama_warmkeeper] initial warm-up %s", "succeeded" if ok else "failed -- will retry on next tick")
    while True:
        await asyncio.sleep(PING_INTERVAL_SECONDS)
        await _ping_once()