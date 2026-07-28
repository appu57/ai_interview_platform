import asyncio
import logging
import random
import time
import uuid
from datetime import datetime, timezone

from groq import AsyncGroq

from backend.agents.graph.state import TutorSystemDesignState
from backend.agents.nodes.tutor_nodes.guardrails import check_output
from backend.agents.nodes.tutor_nodes.observability import (
    record_guardrail_block,
    record_fallback,
    timed,
)
from backend.core.security import get_settings

logger = logging.getLogger("mockai-tutor-system-design")
UTC = timezone.utc
QUESTION_MODEL = "openai/gpt-oss-120b"
_client = AsyncGroq(api_key=get_settings().groq_api_key)

SYSTEM_PROMPT = (
    "You are an elite Principal/Staff System Design Interviewer. "
    "Generate ONE enterprise-scale system design scenario targeted at a senior software engineer with 5-7 years experience. "
    "Draw broadly from modern backend engineering -- microservices architecture, distributed systems, real-time data "
    "platforms, event-driven systems, or similar -- and pick a genuinely different domain each time you're asked. "
    "Keep it strictly to 1-3 sentences, phrased as a conversational prompt spoken aloud by an interviewer. "
    "Do not include hints, background context, boilerplate setups, or structural markdown (no lists, headings, or bullet points). Plain text only."
)

USER_PROMPT_BASE = (
    "Formulate exactly ONE fresh, hyper-focused system design question tailored for a Staff Engineer level, "
    "the kind asked in interviews across various companies. Choose your own domain -- microservices architecture, "
    "distributed systems, retrieval-augmented generation (RAG) pipelines, or real-time data platforms are all fair "
    "game. The question should demand complex data-flow patterns, edge-case mitigation, or real-time distributed "
    "processing, firmly grounded in whichever domain you pick."
)

_FALLBACK_QUESTIONS = [
    "Design a URL shortener like bit.ly. Sketch the core components on the whiteboard.",
    "Design a scalable notification system that sends push, email, and SMS. Sketch your architecture.",
    "Design the backend for a real-time chat app like WhatsApp. Sketch the components and how messages flow.",
    "Design a rate limiter that sits in front of a public API. Sketch where it lives and how it makes decisions.",
    "Design a distributed file storage system like Dropbox. Sketch upload, sync, and versioning.",
    "Design a multi-region active-active ledger system for a global banking platform that guarantees strict serializability under high network partition risks.",
    "Design a real-time analytics ingestion pipeline capable of processing 10 million telemetry events per second with out-of-order data correction and sub-second window aggregations.",
    "Design a multi-tenant rate limiting and traffic shaping engine that operates globally at the edge layer without introducing centralized Redis bottlenecks.",
    "Design a distributed orchestration engine similar to Temporal that ensures exactly-once execution guarantees for highly complex, long-running multi-service workflows.",
]


def _avoid_repeats_directive(recent_questions: list[str]) -> str:
    if not recent_questions:
        return ""
    listed = "\n".join(f"- {q}" for q in recent_questions)
    return (
        "\n\nDo not ask any of the following questions again, and don't ask "
        f"something that's just a small variation of one of them:\n{listed}"
    )


def _recent_prior_questions(messages: list, max_recent: int = 4) -> list[str]:
    return [
        m["content"] for m in messages
        if m.get("role") == "assistant" and m.get("kind") == "system_design_question"
    ][-max_recent:]


async def _call_question_model(recent_questions: list[str]) -> str | None:
    max_retries = 3
    base_delay = 1.0
    user_prompt = USER_PROMPT_BASE + _avoid_repeats_directive(recent_questions)

    for attempt in range(max_retries):
        try:
            with timed("question_gen"):
                completion = await _client.chat.completions.create(
                    model=QUESTION_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=1.1,
                    top_p=1.0,
                    max_tokens=400,
                    reasoning_effort="medium",
                    frequency_penalty=0.5,
                    presence_penalty=0.5,
                    timeout=10.0,
                )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"[SystemDesignGraph] All {max_retries} attempts failed. Tracing last exception: {e}", exc_info=True)
                return None
            delay = (base_delay * (2 ** attempt)) + random.random()
            logger.warning(f"[SystemDesignGraph] Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f} seconds...")
            await asyncio.sleep(delay)
    return None


async def system_design_question_node(state: TutorSystemDesignState) -> dict:
    prior_questions = _recent_prior_questions(state.get("messages", []))

    question_text = await _call_question_model(prior_questions)

    if question_text:
        ok, reason = check_output(question_text)
        if not ok:
            logger.error(f"[SystemDesignGraph] Output guardrail blocked generated question: {reason}")
            record_guardrail_block("question_gen", "output", reason)
            question_text = None

    if not question_text:
        logger.info("[SystemDesignGraph] Reverting to static fallback collection questions.")
        record_fallback("question_gen", "no valid question after retries/guardrail")
        pool = [q for q in _FALLBACK_QUESTIONS if q not in prior_questions] or _FALLBACK_QUESTIONS
        question_text = random.choice(pool)

    message = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": question_text,
        "timestamp": datetime.now(UTC).isoformat(),
        "kind": "system_design_question",
    }

    return {
        "system_design_question": question_text,
        "messages": [message],
        "review_count": 0,
    }