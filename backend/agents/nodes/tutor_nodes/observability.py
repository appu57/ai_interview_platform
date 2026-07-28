import atexit
import json
import logging
import os
import queue
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, List, Optional

logger = logging.getLogger("mockai-tutor-observability")
UTC = timezone.utc

EVAL_LOG_PATH = os.getenv("TUTOR_EVAL_LOG_PATH", "logs/tutor_eval_events.jsonl")
_log_dir = os.path.dirname(EVAL_LOG_PATH)
if _log_dir:
    os.makedirs(_log_dir, exist_ok=True)

_log_queue: "queue.Queue[Optional[dict]]" = queue.Queue()


def _writer_loop() -> None:
    f = None
    try:
        f = open(EVAL_LOG_PATH, "a", buffering=1)  # line-buffered
    except Exception as e:
        logger.error(f"[observability] Could not open eval log at {EVAL_LOG_PATH!r}: {e}")

    while True:
        record = _log_queue.get()
        if record is None:  # shutdown sentinel
            break
        if f is None:
            continue
        try:
            f.write(json.dumps(record, default=str) + "\n")
        except Exception as e:
            logger.error(f"[observability] Failed to write eval log event: {e}")

    if f is not None:
        f.close()


_writer_thread = threading.Thread(target=_writer_loop, name="eval-log-writer", daemon=True)
_writer_thread.start()


def _shutdown_writer() -> None:
    _log_queue.put(None)
    _writer_thread.join(timeout=2.0)


atexit.register(_shutdown_writer)


def log_event(event_type: str, **fields) -> None:
    record = {"ts": datetime.now(UTC).isoformat(), "event": event_type, **fields}
    try:
        _log_queue.put_nowait(record)
    except Exception as e:
        logger.error(f"[observability] Failed to enqueue eval log event {event_type!r}: {e}")


try:
    from prometheus_client import Counter, Histogram
    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False
    logger.warning(
        "[observability] prometheus_client not installed -- Prometheus export "
        "disabled, JSON eval log at %s still fully active. `pip install "
        "prometheus_client` to enable /metrics export.", EVAL_LOG_PATH,
    )

if _PROM_AVAILABLE:
    LATENCY = Histogram(
        "tutor_llm_call_duration_seconds",
        "Latency of an LLM call in the tutor graph",
        ["node", "outcome"],
        buckets=(0.5, 1, 2, 5, 10, 20, 30, 45, 60, 90, 120, 180),
    )
    JUDGE_DECISIONS = Counter(
        "tutor_judge_decisions_total", "groundedness judge decisions", ["branch", "outcome"]
    )
    PARSE_FAILURES = Counter(
        "tutor_parse_failures_total", "freeform model output failed to parse into schema", ["node"]
    )
    FALLBACKS = Counter(
        "tutor_fallback_used_total", "static fallback content served instead of model output", ["node"]
    )
    BEST_EFFORT_USED = Counter(
        "tutor_best_effort_used_total",
        "real model output served that never independently passed the judge -- "
        "either a single unverified candidate, or the winner of a two-candidate "
        "comparison. Distinct from tutor_fallback_used_total: this is NOT canned "
        "content, and a rising rate here means judge pass rate is degrading even "
        "though candidates are no longer seeing static filler.",
        ["node", "reason"],
    )
    GUARDRAIL_BLOCKS = Counter(
        "tutor_guardrail_blocks_total", "check_input/check_output blocked content", ["node", "direction"]
    )

def observe_latency(node: str, outcome: str, seconds: float) -> None:
    """outcome: 'success' | 'timeout' | 'error'."""
    log_event("latency", node=node, outcome=outcome, duration_ms=round(seconds * 1000, 1))
    if _PROM_AVAILABLE:
        LATENCY.labels(node=node, outcome=outcome).observe(seconds)


def record_judge_decision(branch: str, passed: bool, issue: str, claims: List[str]) -> None:
    outcome = "passed" if passed else "failed"
    log_event("judge_decision", branch=branch, outcome=outcome, issue=issue, claims=claims)
    if _PROM_AVAILABLE:
        JUDGE_DECISIONS.labels(branch=branch, outcome=outcome).inc()


def record_judge_error(branch: str, error: str) -> None:
    log_event("judge_error", branch=branch, error=error)
    if _PROM_AVAILABLE:
        JUDGE_DECISIONS.labels(branch=branch, outcome="error_fail_open").inc()


def record_parse_failure(node: str, raw_output_snippet: str) -> None:
    log_event("parse_failure", node=node, raw_output_snippet=raw_output_snippet[:300])
    if _PROM_AVAILABLE:
        PARSE_FAILURES.labels(node=node).inc()


def record_fallback(node: str, reason: str) -> None:
    log_event("fallback_used", node=node, reason=reason)
    if _PROM_AVAILABLE:
        FALLBACKS.labels(node=node).inc()


def record_best_effort_used(node: str, reason: str) -> None:
    log_event("best_effort_used", node=node, reason=reason)
    if _PROM_AVAILABLE:
        BEST_EFFORT_USED.labels(node=node, reason=reason).inc()


def record_tiebreak_decision(
    node: str, winner_attempt: int, total_candidates: int,
    winner_issue: str, all_issues: List[str], reason: str,
) -> None:
    log_event(
        "tiebreak_decision", node=node, winner_attempt=winner_attempt,
        total_candidates=total_candidates, winner_issue=winner_issue,
        all_issues=all_issues, reason=reason,
    )


def record_guardrail_block(node: str, direction: str, reason: str) -> None:
    log_event("guardrail_block", node=node, direction=direction, reason=reason)
    if _PROM_AVAILABLE:
        GUARDRAIL_BLOCKS.labels(node=node, direction=direction).inc()


@contextmanager
def timed(node: str) -> Iterator[None]:
    start = time.monotonic()
    try:
        yield
        observe_latency(node, "success", time.monotonic() - start)
    except Exception:
        observe_latency(node, "error", time.monotonic() - start)
        raise