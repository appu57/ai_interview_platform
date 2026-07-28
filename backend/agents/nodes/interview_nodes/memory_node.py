import logging
from typing import Dict, Any, List

from backend.agents.graph.state import InterviewState
from backend.db.repository import ConversationRepository
from backend.db.session import get_db

logger = logging.getLogger("mockai-adaptive-graph")

_ROLE_TO_DB = {
    "assistant": "interviewer",
    "interviewer": "interviewer",
    "user": "candidate",
    "candidate": "candidate",
}


def _map_role(role: str) -> str:
    return _ROLE_TO_DB.get(role, role)


async def memory_sync_node(state: InterviewState) -> Dict[str, Any]:
    session_id = state["session_id"]
    messages: List[Dict[str, Any]] = state.get("messages", [])
    persisted_count = state.get("persisted_message_count", 0)
    new_messages = messages[persisted_count:]

    if not new_messages:
        return {}

    current_round_index = state.get("current_round_index", 0)
    guardrail_flag = state.get("last_guardrail_flag")

    rows = []
    for i, m in enumerate(new_messages):
        is_last = i == len(new_messages) - 1
        rows.append({
            "session_id": session_id,
            "round_index": current_round_index,
            "role": _map_role(m.get("role", "unknown")),
            "message_text": m.get("content", "") or "(empty)",
            "ai_feedback_correction": guardrail_flag if (is_last and guardrail_flag) else None,
        })

    async for db_session in get_db():
        if not db_session:
            logger.error("[Memory] No DB session available — skipping sync this turn, will retry next turn.")
            return {}
        try:
            convo_repo = ConversationRepository(db_session)
            await convo_repo.bulk_create_messages(rows)
            await db_session.commit()
        except Exception as e:
            await db_session.rollback()
            logger.error(f"[Memory] Sync failed, pointer NOT advanced (will retry next turn): {e}")
            return {}


    return {"persisted_message_count": len(messages)}
