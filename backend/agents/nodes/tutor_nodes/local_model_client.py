import asyncio
import logging
import os
import time
from typing import List, Optional

from openai import AsyncOpenAI

from backend.agents.nodes.tutor_nodes.observability import observe_latency

logger = logging.getLogger("mockai-local-model")

LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1")
MODEL_NAME = os.getenv("FINE_TUNED_TUTOR_MODEL", "mockai-tutor-new:latest")

_client = AsyncOpenAI(base_url=LOCAL_LLM_URL, api_key="ollama", max_retries=0)

KEEP_ALIVE = "30m"


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

    start = time.monotonic()
    try:
        response = await asyncio.wait_for(
            _client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.4,
                max_tokens=max_tokens,
                extra_body={"options": {"num_ctx": num_ctx}, "keep_alive": KEEP_ALIVE},
            ),
            timeout=hard_timeout_seconds,
        )
        elapsed = time.monotonic() - start
        logger.info("[local_model] %s call succeeded in %.2fs.", log_label, elapsed)
        observe_latency(log_label, "success", elapsed)
        return response.choices[0].message.content or ""
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start
        logger.error(
            "[local_model] %s call exceeded hard timeout of %.0fs (ran %.2fs).",
            log_label, hard_timeout_seconds, elapsed,
        )
        observe_latency(log_label, "timeout", elapsed)
        return None
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("[local_model] %s call failed after %.2fs: %s", log_label, elapsed, e, exc_info=True)
        observe_latency(log_label, "error", elapsed)
        return None