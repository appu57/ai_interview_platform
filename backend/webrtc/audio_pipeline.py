import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
)
from livekit.agents.voice import AgentSession, Agent
from livekit.agents.stt import StreamAdapter
from livekit.plugins import silero, openai, groq

from backend.agents.graph.interview_graph import build_interview_graph
from backend.agents.graph.practice_graph import build_tutor_graph
from backend.db.checkpointer import init_checkpointer, close_checkpointer
from backend.db.session import get_db
from backend.webrtc.custom_edge_tts import EdgeTTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mockai-audio-pipeline")

UTC = timezone.utc


_interview_graph = None
_tutor_graph = None

async def _get_interview_graph():
    global _interview_graph
    if _interview_graph is None:
        checkpointer = await init_checkpointer()
        _interview_graph = build_interview_graph(checkpointer)
    return _interview_graph

async def _get_tutor_graph():
    global _tutor_graph
    if _tutor_graph is None:
        checkpointer = await init_checkpointer()
        _tutor_graph = build_tutor_graph(checkpointer)
    return _tutor_graph

async def entrypoint(ctx: JobContext):
    session_id = ctx.room.name #We get ctx metadata from livekit_client while creating token for frontend
    
    raw_metadata = ctx.job.metadata
    config = json.loads(raw_metadata) if raw_metadata else {}
    graph_type = config.get("mode", "tutor")

    interview_graph = await _get_interview_graph()
    tutor_graph = await _get_tutor_graph()

    interview_config = {"configurable": {"thread_id": session_id}}
    tutor_config = {"configurable": {"thread_id": session_id}}


    # Figures out which graph owns this room BEFORE doing anything else.
    # Both entry points (save_preferences for interview mode,
    # /api/system-design/session for tutor mode) create their graph's
    # checkpoint before the candidate's browser ever requests a WebRTC
    # token / joins this room so by the time this entrypoint runs,
    # exactly one of the two graphs already has a paused checkpoint for
    # this thread_id.
    tutor_snapshot = await tutor_graph.aget_state(tutor_config)
    is_tutor_session = bool(
        tutor_snapshot and tutor_snapshot.values and tutor_snapshot.values.get("system_design_question")
    )
    

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    participant = await ctx.wait_for_participant()

    vad = ctx.proc.userdata["vad"]
    local_stt = groq.STT(model="whisper-large-v3-turbo", language="en")

    session = AgentSession(   #no seperate llm because using langgraph
        vad=vad,
        stt=StreamAdapter(stt=local_stt, vad=vad),
        tts=EdgeTTS(voice="en-US-AriaNeural"),
        allow_interruptions=True,
        min_endpointing_delay=0.6,
    )

    async def _execute_interview_turn(transcript: str):
        try:
            await send_data_event(ctx.room, {
                "type": "state_update",
                "data": {"status": "processing", "message": "Evaluating Response..."}
            })
 
            current_snapshot = await interview_graph.aget_state(interview_config)
            active_round = (
                current_snapshot.values.get("active_round_node")
                if current_snapshot and current_snapshot.values
                else None
            )
 
            candidate_message = {
                "id": str(uuid.uuid4()),
                "role": "user",
                "content": transcript,
                "round": active_round,
                "timestamp": datetime.now(UTC).isoformat(),
            }
 
            await interview_graph.aupdate_state(interview_config, {"messages": [candidate_message]})
            output_state = await interview_graph.ainvoke(None, config=interview_config)
 
            latest_turn = output_state["messages"][-1] if output_state.get("messages") else {}
            ai_reply = latest_turn.get("content", "")
            tutor_hint = latest_turn.get("correction", None)
 
            if tutor_hint:
                await send_data_event(ctx.room, {
                    "type": "tutor_hint",
                    "data": {"id": str(uuid.uuid4()), "hint": tutor_hint}
                })
 
            if ai_reply:
                await send_data_event(ctx.room, {
                    "type": "state_update",
                    "data": {"status": "speaking", "message": "Speaking..."}
                })
                await session.say(ai_reply, allow_interruptions=True)
 
        except Exception as err:
            logger.error(f"[Graph Turn Failure] Failed to process voice turn: {err}", exc_info=True)
            await session.say("I experienced a connection delay. Could you repeat your last thought?", allow_interruptions=True)

    async def _execute_tutor_turn(transcript: str):
        try:
            await send_data_event(ctx.room, {
                "type": "state_update",
                "data": {"status": "processing", "message": "Thinking..."}
            })
            candidate_message = {
                "id": str(uuid.uuid4()),
                "role": "user",
                "content": transcript,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            await tutor_graph.aupdate_state(tutor_config, {
                "user_question": transcript,
                "user_action": "ask_question",
                "messages":[candidate_message]
            })
        
            output_state = await tutor_graph.ainvoke(None, config=tutor_config)
            feedback = output_state.get("validation_feedback")
            if feedback:
                await send_data_event(ctx.room, {
                    "type": "state_update",
                    "data": {"status": "speaking", "message": "Speaking..."}
                })
                await session.say(feedback, allow_interruptions=True)
 
        except Exception as err:
            logger.error(f"[Tutor Turn Failure] Failed to process voice turn: {err}", exc_info=True)
            await session.say("I experienced a connection delay. Could you repeat your question?", allow_interruptions=True)

    
    @session.on("user_input_transcribed")
    def on_user_speech(event):
        if not event.transcript:
            return
        if is_tutor_session:  #or use mode (graph_type) from ctx.job.metadata 
            asyncio.create_task(_execute_tutor_turn(event.transcript))
        else:
            asyncio.create_task(_execute_interview_turn(event.transcript))

    def on_data_received(data: rtc.DataPacket):
        if data.participant and data.participant.identity == ctx.room.local_participant.identity:
            return
        try:
            payload = json.loads(data.data.decode("utf-8"))
            if payload.get("type") != "speak_request":
                return
            text = payload.get("data", {}).get("text")
            if text:
                asyncio.create_task(session.say(text, allow_interruptions=True))
        except Exception as e:
            logger.error(f"[ExternalTTS] Failed to handle inbound speak_request: {e}", exc_info=True)
 
    ctx.room.on("data_received", on_data_received)


    async def on_shutdown():
        logger.info(f"[Room Disconnect] Session ended for {session_id}.")
        if is_tutor_session:
            return
        async for db_session in get_db():
            try:
                from sqlalchemy import select
                from backend.db.models import InterviewSession
 
                result = await db_session.execute(
                    select(InterviewSession).where(InterviewSession.id == uuid.UUID(session_id))
                )
                row = result.scalars().first()
                if row and row.status == "active":
                    row.status = "abandoned"
                    await db_session.commit()
                    logger.info(f"Marked session {session_id} as abandoned on disconnect.")
            except Exception as e:
                logger.error(f"Post-disconnect bookkeeping failed: {e}", exc_info=True)
            break
 
    ctx.add_shutdown_callback(on_shutdown)

    agent = Agent(
        instructions=(
            "You are a helpful AI DSA and system design tutor." if is_tutor_session
            else "You are a helpful AI interviewer."
        )
    )
    await session.start(room=ctx.room, agent=agent)

    if is_tutor_session:
        opening_line = tutor_snapshot.values.get("system_design_question")
        await session.say(opening_line, allow_interruptions=True)
    else:
        await session.say(
            "Hello! I have loaded your workspace context. Let me know when you are ready to start!",
            allow_interruptions=True
        )
 
    while ctx.room.isconnected():
        await asyncio.sleep(1)

async def send_data_event(room: rtc.Room, event: dict):
    try:
        data = json.dumps(event).encode("utf-8")
        await room.local_participant.publish_data(
            data,
            reliable=True,
            topic="agent_events"
        )
    except Exception as e:
        logger.error(f"Failed to publish telemetry event {event['type']}: {e}")


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load(
        min_silence_duration=0.6,
        min_speech_duration=0.15,
    )

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )


# meta-llama/llama-4-scout-17b-16e-instruct (Recommended: Incredible 2026 mixture-of-experts model, great context, 500K TPD).
# openai/gpt-oss-20b (Extremely fast conversational model, 200K TPD).
# llama-3.1-8b-instant (The classic light workhorse, 500K TPD).