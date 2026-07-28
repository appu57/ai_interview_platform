import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger("mockai-latency-budget")

# If nobody has called mark_model_warm() in this long, treat the next
# call as a cold start -- the Ollama model has likely been evicted.
COLD_START_IDLE_THRESHOLD_SECONDS = 6 * 60.0
_warmth_lock = threading.Lock()
_last_model_activity_at: Optional[float] = None
_last_ping_failure_at: Optional[float] = None


def mark_model_warm() -> None:
    global _last_model_activity_at, _last_ping_failure_at
    with _warmth_lock:
        _last_model_activity_at = time.monotonic()
        _last_ping_failure_at = None


def mark_ping_failed() -> None:
    global _last_ping_failure_at
    with _warmth_lock:
        _last_ping_failure_at = time.monotonic()


def _model_is_cold() -> bool:
    with _warmth_lock:
        if _last_model_activity_at is None:
            return True
        return (time.monotonic() - _last_model_activity_at) > COLD_START_IDLE_THRESHOLD_SECONDS


def _model_confirmed_unresponsive() -> bool:
    with _warmth_lock:
        return _last_ping_failure_at is not None


@dataclass
class _ResponseTimeTracker:
    new_sample_weight: float = 0.125   # how much one new sample moves the average
    new_swing_weight: float = 0.25     # how much one new sample moves the swing
    safety_margin: float = 4.0         # timeout = average + safety_margin * swing

    average: Optional[float] = None
    swing: Optional[float] = None
    sample_count: int = 0

    def add_sample(self, seconds: float) -> None:
        if self.average is None:
            self.average = seconds
            self.swing = seconds / 2.0
        else:
            diff = abs(self.average - seconds)
            self.swing = (1 - self.new_swing_weight) * self.swing + self.new_swing_weight * diff
            self.average = (1 - self.new_sample_weight) * self.average + self.new_sample_weight * seconds
        self.sample_count += 1

    def suggested_timeout(self) -> Optional[float]:
        if self.average is None:
            return None
        return self.average + self.safety_margin * self.swing


class AdaptiveLatencyBudget:
    def __init__(self, name: str, prior_warm_seconds: float, prior_cold_seconds: float,
                 floor_seconds: float, ceiling_seconds: float):
        self.name = name
        self.ceiling_seconds = ceiling_seconds
        self._prior_warm = prior_warm_seconds
        self._prior_cold = prior_cold_seconds
        self._floor = floor_seconds
        self._warm = _ResponseTimeTracker()
        self._cold = _ResponseTimeTracker()
        self._lock = threading.Lock()  # multiple requests can hit this node concurrently

    def is_cold_start(self) -> bool:
        return _model_is_cold()

    def record_sample(self, seconds: float, was_cold: bool) -> None:
        with self._lock:
            (self._cold if was_cold else self._warm).add_sample(seconds)
        mark_model_warm()

    def get_call_timeout(self, cold: Optional[bool] = None) -> float:
        if cold is None:
            cold = self.is_cold_start()

        if cold and _model_confirmed_unresponsive():
            logger.warning(
                "[latency_budget] %s: last keep-alive ping failed -- skipping the normal cold "
                "estimate and using the ceiling (%.1fs) instead.", self.name, self.ceiling_seconds,
            )
            return self.ceiling_seconds

        tracker = self._cold if cold else self._warm
        prior = self._prior_cold if cold else self._prior_warm

        suggested = tracker.suggested_timeout()
        timeout = suggested if suggested is not None else prior
        timeout = max(self._floor, min(self.ceiling_seconds, timeout))

        if suggested is None:
            logger.info("[latency_budget] %s: no %s samples yet -- using default %.1fs.",
                        self.name, "cold" if cold else "warm", timeout)
        return timeout

    def snapshot(self) -> dict:
        with self._lock:
            warm_est = self._warm.suggested_timeout()
            cold_est = self._cold.suggested_timeout()
            return {
                "node": self.name,
                "warm_estimate_s": round(warm_est, 2) if warm_est else None,
                "warm_samples": self._warm.sample_count,
                "cold_estimate_s": round(cold_est, 2) if cold_est else None,
                "cold_samples": self._cold.sample_count,
                "currently_cold": self.is_cold_start(),
                "floor_s": self._floor,
                "ceiling_s": self.ceiling_seconds,
            }

_registry: Dict[str, AdaptiveLatencyBudget] = {}
_registry_lock = threading.Lock()


def get_or_create_budget(name: str, prior_warm_seconds: float, prior_cold_seconds: float,
                          floor_seconds: float, ceiling_seconds: float) -> AdaptiveLatencyBudget:
    """Idempotent -- same object returned every call for a given name."""
    with _registry_lock:
        if name not in _registry:
            _registry[name] = AdaptiveLatencyBudget(name, prior_warm_seconds, prior_cold_seconds, floor_seconds, ceiling_seconds)
        return _registry[name]


def get_all_budget_snapshots() -> Dict[str, dict]:
    with _registry_lock:
        return {name: b.snapshot() for name, b in _registry.items()}