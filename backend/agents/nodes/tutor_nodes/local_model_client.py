import asyncio
import logging
import os
import time
from typing import List, Optional

import httpx

from backend.agents.nodes.tutor_nodes.observability import observe_latency

logger = logging.getLogger("mockai-local-model")


LOCAL_LLM_HOST = os.getenv("LOCAL_LLM_HOST", "http://localhost:11434")
MODEL_NAME = os.getenv("FINE_TUNED_TUTOR_MODEL", "mockai-tutor-new:latest")

KEEP_ALIVE = "30m"

_client = httpx.AsyncClient(base_url=LOCAL_LLM_HOST, timeout=None)


async def call_fine_tuned_model(
    system_prompt: str,
    user_content: str,
    stop_marker: str,
    max_tokens: int,
    hard_timeout_seconds: float,
    log_label: str,
    num_ctx: int = 2048,
    extra_messages: Optional[List[dict]] = None,
) -> Optional[str]:
    messages = [{"role": "system", "content": system_prompt}]
    if extra_messages:
        messages.extend(extra_messages)
    messages.append({"role": "user", "content": user_content})


    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": True,
        "options": {
            "num_ctx": num_ctx,
            "num_gpu": 36,
            "num_predict": max_tokens,
            "temperature": 0.4,
            "stop": [stop_marker],
        },
        "keep_alive": KEEP_ALIVE,
    }

    start = time.monotonic()
    try:
        response = await asyncio.wait_for(
            _client.post("/api/chat", json=payload),
            timeout=hard_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        elapsed = time.monotonic() - start
        logger.info("[local_model] %s call succeeded in %.2fs.", log_label, elapsed)
        observe_latency(log_label, "success", elapsed)
        return data.get("message", {}).get("content") or ""
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start
        logger.error(
            "[local_model] %s call exceeded hard timeout of %.0fs (ran %.2fs).",
            log_label, hard_timeout_seconds, elapsed,
        )
        observe_latency(log_label, "timeout", elapsed)
        return None
    except httpx.HTTPStatusError as e:
        elapsed = time.monotonic() - start
        logger.error(
            "[local_model] %s call returned HTTP %d after %.2fs: %s",
            log_label, e.response.status_code, elapsed, e.response.text[:500],
        )
        observe_latency(log_label, "error", elapsed)
        return None
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("[local_model] %s call failed after %.2fs: %s", log_label, elapsed, e, exc_info=True)
        observe_latency(log_label, "error", elapsed)
        return None