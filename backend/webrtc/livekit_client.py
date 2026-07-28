import json
import os
import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from livekit import api

from backend.core.security import get_settings

settings = get_settings()

LIVEKIT_API_KEY = settings.livekit_api_key
LIVEKIT_API_SECRET = settings.livekit_secret_key
LIVEKIT_URL = settings.livekit_url

router = APIRouter(prefix="/api/webrtc", tags=["webrtc"])

@router.get("/token/{session_id}")
async def generate_livekit_token(
    session_id:str,
    identity: str = "candidate_user",
    role:str ="candidate",
    mode:str="tutor"
):
    try:
        token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        token.with_identity(identity)
        token.with_name(f"Mock.ai Participant - {role}")
        
        grants = api.VideoGrants(
            room_join=True,
            room=session_id,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True
        )
        token.with_grants(grants)

        metadata_payload = {
        "session_id": session_id,
        "mode": mode
        }

        token.with_metadata(json.dumps(metadata_payload))
        
        return {"token": token.to_jwt()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate secure WebRTC token: {str(e)}"
        )