import base64
import uuid
from typing import Optional
import logging
import json

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from livekit import api
from datetime import datetime, timezone

from backend.core.security import get_settings


logger = logging.getLogger("mockai-tutor-api")
router = APIRouter(prefix="/api/system-design", tags=["system-design"])

UTC = timezone.utc

def get_tutor_graph(request: Request):
    return request.app.state.tutor_graph


class AskRequest(BaseModel):
    question: str

 
settings = get_settings()
LIVEKIT_API_KEY = settings.livekit_api_key
LIVEKIT_API_SECRET = settings.livekit_secret_key
LIVEKIT_URL = settings.livekit_url
 
async def _require_paused_checkpoint(graph, config: dict, thread_id: str):
    snapshot = await graph.aget_state(config)
    if snapshot is None or not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No paused system-design checkpoint found for session {thread_id}. "
                   "Call GET /api/system-design/session first.",
        )
    return snapshot
 
 
async def _publish_room_data(room_name: str, event: dict) -> None:
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        logger.error("[system-design] LiveKit credentials not configured -- cannot publish room data.")
        return
 
    http_url = LIVEKIT_URL.replace("ws://", "http://").replace("wss://", "https://")
    lkapi = api.LiveKitAPI(url=http_url, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
 
    try:
        payload = json.dumps(event).encode("utf-8")
        await lkapi.room.send_data(
            api.RoomSendDataRequest(
                room=room_name,
                data=payload,
                kind=api.DataPacket.Kind.RELIABLE,
                topic="agent_events",
            )
        )
    except Exception as e:
        logger.error(f"[system-design] Failed to publish to room {room_name}: {e}", exc_info=True)
    finally:
        await lkapi.aclose()
 
 
# This is used to send data from any channel, so client livekit on data arriving on the room's data channel from any sender — that includes the browser/frontend,  to inject a packet into the room from outside 
# Not using as of now because currently planning on showing feedback though http and not voice
async def _publish_feedback_speech(thread_id: str, feedback: Optional[str]) -> None:
    if not feedback:
        return
    try:
        await _publish_room_data(thread_id, {
            "type": "speak_request",
            "data": {"text": feedback},
        })
    except Exception as e:
        logger.error(f"[system-design] Failed to publish TTS request for {thread_id}: {e}", exc_info=True)


@router.get("/session")
async def start_session(user_id: str, graph = Depends(get_tutor_graph)):
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}
    result = await graph.ainvoke({"session_id": session_id, "user_id": user_id}, config=config)
    return {"session_id": session_id, "question": result.get("system_design_question"), "hints": result.get("hints")}

@router.post("/session/{thread_id}/submit")
async def submit_whiteboard(thread_id: str, image: UploadFile = File(...), graph = Depends(get_tutor_graph)):
    config = {"configurable": {"thread_id": thread_id}}
    await _require_paused_checkpoint(graph, config, thread_id)
    image_b64 = base64.b64encode(await image.read()).decode("utf-8")
    await graph.aupdate_state(config, {"whiteboard_image": image_b64, "user_action": "submit_image"})
    result = await graph.ainvoke(None, config=config)
    feedback = result.get("validation_feedback")
    return {"whiteboard_json": result.get("whiteboard_json"), "feedback_text": feedback}

@router.post("/session/{thread_id}/ask-concept")
async def ask_concept(thread_id: str, body: AskRequest, graph = Depends(get_tutor_graph)):
    config = {"configurable": {"thread_id": thread_id}}
    await _require_paused_checkpoint(graph, config, thread_id)
    candidate_message = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": body.question,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    await graph.aupdate_state(config, {
        "user_question": body.question,
        "messages": [candidate_message],
        "user_action": "ask_concept",
    })
    result = await graph.ainvoke(None, config=config)
    return {"answer": result.get("validation_feedback")}

@router.post("/session/{thread_id}/stop")
async def stop_session(thread_id: str, graph = Depends(get_tutor_graph)):
    config = {"configurable": {"thread_id": thread_id}}
    await _require_paused_checkpoint(graph, config, thread_id)
    await graph.aupdate_state(config, {"user_action": "stop"})
    result = await graph.ainvoke(None, config=config)
    return {"status": "ended", "final_feedback": result.get("validation_feedback")}