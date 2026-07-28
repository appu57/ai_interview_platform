import uuid
import logging
from datetime import datetime, UTC
from typing import Dict, Any

from backend.agents.graph.state import InterviewState

logger = logging.getLogger("mockai-adaptive-graph")


async def early_termination_node(state: InterviewState) -> Dict[str, Any]:
    reason = state.get("session_terminated_early", "policy_violation")
    logger.error(f"[Termination] Session {state['session_id']} ending early — reason={reason}.")

    closing_message = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": "This interview session has been ended due to a policy violation. Thank you for your time.",
        "round": state.get("active_round_node"),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    rounds_total = len(state["rounds_blueprint"].get("rounds", []))

    return {
        "messages": [closing_message],
        "pending_question": None,
        "active_oa_payload": None,
        "current_round_index": rounds_total,
    }
