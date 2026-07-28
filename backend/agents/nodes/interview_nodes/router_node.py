import logging
import time
from datetime import datetime
from typing import Optional

from backend.agents.graph.state import InterviewState

logger = logging.getLogger("mockai-adaptive-graph")

ROUND_TYPE_TO_NODE = {
    "oa": "oa_agent_node",
    "onlineassessment": "oa_agent_node",
    "technical": "technical_agent_node",
    "techdsa": "technical_agent_node",
    "dsa": "technical_agent_node",
    "sysdesign": "system_design_agent_node",
    "systemdesign": "system_design_agent_node",
    "behavioral": "behavioral_agent_node",
    "behavioural": "behavioral_agent_node",
    "hr": "behavioral_agent_node",
}


def _normalize_round_type(raw_type: str) -> str:
    """'Tech_DSA' -> 'techdsa', 'Sys_Design' -> 'sysdesign', 'OA' -> 'oa'."""
    return (raw_type or "").strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def _round_duration_seconds(round_config: dict) -> Optional[int]:
    digits = "".join(ch for ch in str(round_config.get("duration", "")) if ch.isdigit())
    if not digits:
        return None
    return int(digits) * 60


def _get_current_round_start_time(state: InterviewState) -> Optional[float]:
    active_round_node = state.get("active_round_node")
    if not active_round_node:
        return None

    messages = state.get("messages") or []
    if not messages:
        return None

    opening_message = None

    for m in reversed(messages):
        if m.get("role") not in ("assistant", "interviewer"):
            continue  # skip user/candidate turns

        msg_round = m.get("round")

        if msg_round is None:
            logger.debug(
                "[Router] Assistant message with no 'round' tag encountered during "
                "start-time scan — skipping but continuing backward scan."
            )
            continue

        if msg_round != active_round_node:
            break

        opening_message = m

    if opening_message is None:
        logger.warning(
            f"[Router] No assistant message found tagged round='{active_round_node}' "
            "in current message history. Skipping time-budget check for this turn."
        )
        return None

    boundary_ts = opening_message.get("timestamp")
    if not boundary_ts:
        logger.warning(
            f"[Router] Opening message for round '{active_round_node}' has no timestamp field."
        )
        return None

    try:
        return datetime.fromisoformat(boundary_ts).timestamp()
    except (TypeError, ValueError) as e:
        logger.warning(
            f"[Router] Could not parse timestamp '{boundary_ts}' for round "
            f"'{active_round_node}': {e}"
        )
        return None


def is_round_time_exhausted(state: InterviewState, round_config: dict) -> bool:
    started_at = _get_current_round_start_time(state)
    if not started_at:
        return False

    duration_seconds = _round_duration_seconds(round_config)
    if duration_seconds is None:
        return False

    elapsed_seconds = time.time() - started_at
    logger.debug(
        f"[Router] Round '{state.get('active_round_node')}' elapsed={elapsed_seconds:.0f}s "
        f"/ budget={duration_seconds}s"
    )
    return elapsed_seconds >= duration_seconds


def route_after_guardrail(state: InterviewState) -> str:
    if state.get("session_terminated_early"):
        logger.error(
            f"[Router] session_terminated_early='{state['session_terminated_early']}' "
            "— routing to early_termination_node."
        )
        return "early_termination_node"

    active_round_node = state.get("active_round_node")
    round_turn_count = state.get("round_turn_count", 0)
    current_round_index = state.get("current_round_index", 0)
    rounds_list = state["rounds_blueprint"].get("rounds", [])

    current_round_config = (
        rounds_list[current_round_index] if current_round_index < len(rounds_list) else {}
    )

    if not is_round_time_exhausted(state, current_round_config):
        next_node = ROUND_TYPE_TO_NODE.get(_normalize_round_type(active_round_node))
        if not next_node:
            logger.error(
                f"[Router] active_round_node='{active_round_node}' has no known node mapping — "
                "defaulting to technical_agent_node."
            )
            return "technical_agent_node"
        logger.info(
            f"[Router] Round '{active_round_node}' turn {round_turn_count}, "
            "time budget not yet exhausted — continuing round."
        )
        return next_node

    logger.info(
        f"[Router] Round '{active_round_node}' turn {round_turn_count}: "
        "time budget exhausted — routing to evaluator."
    )
    return "evaluator_agent_node"


WEAKNESS_SCORE_THRESHOLD = 50


def route_after_evaluator(state: InterviewState) -> str:
    rounds_list = state["rounds_blueprint"].get("rounds", [])
    current_round_index = state.get("current_round_index", 0)

    if current_round_index >= len(rounds_list):
        logger.info("[Router] All rounds complete — routing to feedback_agent_node.")
        return "feedback_agent_node"

    round_scores = state.get("round_scores", [])
    just_finished_score = round_scores[-1] if round_scores else None
    score = just_finished_score.get("score", 0) if just_finished_score else 0
    is_weak = score < WEAKNESS_SCORE_THRESHOLD

    if is_weak:
        logger.info(
            f"[Router] Round scored {score} (< {WEAKNESS_SCORE_THRESHOLD}) — "
            "routing to planner_agent_node to update strategy."
        )
        return "planner_agent_node"

    logger.info(
        f"[Router] Round scored {score} (>= {WEAKNESS_SCORE_THRESHOLD}) — "
        "dispatching to next round directly."
    )
    return dispatch_round_node_for_index(state)


def dispatch_round_node_for_index(state: InterviewState) -> str:
    rounds_list = state["rounds_blueprint"].get("rounds", [])
    current_round_index = state.get("current_round_index", 0)

    if current_round_index >= len(rounds_list):
        logger.warning(
            "[Router] dispatch_round_node_for_index called with no rounds left — "
            "routing to feedback_agent_node."
        )
        return "feedback_agent_node"

    round_type = rounds_list[current_round_index].get("type")
    node_name = ROUND_TYPE_TO_NODE.get(_normalize_round_type(round_type))

    if not node_name:
        logger.error(
            f"[Router] Unknown round type '{round_type}' at index {current_round_index} — "
            "defaulting to technical_agent_node."
        )
        return "technical_agent_node"

    logger.info(
        f"[Router] Dispatching to '{node_name}' for round index {current_round_index} "
        f"(type='{round_type}')."
    )
    return node_name