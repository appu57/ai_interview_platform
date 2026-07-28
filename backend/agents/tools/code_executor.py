import logging
import os
import sys
import json
import asyncio
import subprocess
from typing import Any, Optional
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_interview_graph
from backend.db.session import get_db
from backend.models.pydantic_models import RespondRequest
from backend.api.routes.interview import respond_to_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/code", tags=["Code Execution"])

LOCAL_TIMEOUT_SECONDS = float(os.getenv("CODE_TIMEOUT_SECONDS", "15"))

SUPPORTED_LANGUAGES = {"python"}

LANGUAGE_ALIAS_MAP: dict[str, str] = {
    "py": "python",
    "py3": "python",
}

KNOWN_UNSUPPORTED_LANGUAGES = {
    "javascript", "typescript", "java", "cpp", "c++", "c", "go", "golang", "rust",
    "node", "nodejs",
}


def _resolve_language(raw_language: str) -> str:
    lang = (raw_language or "python").strip().lower()
    lang = LANGUAGE_ALIAS_MAP.get(lang, lang)

    if lang in SUPPORTED_LANGUAGES:
        return lang

    if lang in KNOWN_UNSUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{raw_language}' execution isn't supported yet -- only Python is currently runnable. "
                   "Please switch the language selector to Python 3 to Run or Submit.",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported language '{raw_language}'. Supported: {sorted(SUPPORTED_LANGUAGES)}",
    )

class RunCodeRequest(BaseModel):
    language: str = Field(default="python")
    source_code: str
    stdin: Optional[str] = Field(default=None)
    args: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    compile_stdout: str = ""
    compile_stderr: str = ""
    runtime_ms: Optional[int] = None


class RunCodeResponse(BaseModel):
    status: str
    result: ExecutionResult


class SubmitCodeRequest(BaseModel):
    language: str = Field(default="python")
    source_code: str
    stdin: Optional[str] = None
    args: list[str] = Field(default_factory=list)
    accompanying_message: str = Field(default="")
    whiteboard_snapshot: Optional[str] = None
    is_timer_submission: bool = Field(default=False)


async def _execute_python_locally(source_code: str, stdin: Optional[str]) -> ExecutionResult:
    try:
        start_time = datetime.now(UTC)
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", source_code,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdin_bytes = (stdin or "").encode("utf-8")
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=stdin_bytes),
                timeout=LOCAL_TIMEOUT_SECONDS
            )
            runtime = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

            return ExecutionResult(
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=proc.returncode if proc.returncode is not None else 0,
                timed_out=False,
                runtime_ms=runtime,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return ExecutionResult(
                stdout="",
                stderr=f"Execution timed out after {LOCAL_TIMEOUT_SECONDS} seconds.",
                exit_code=124,
                timed_out=True,
            )
    except Exception as e:
        logger.error(f"Local Python execution engine failure: {e}", exc_info=True)
        return ExecutionResult(
            stdout="",
            stderr=f"Runtime environment exception: {str(e)}",
            exit_code=1,
        )


async def _execute_code_locally(language: str, source_code: str, stdin: Optional[str]) -> ExecutionResult:
    resolved_lang = _resolve_language(language)
    return await _execute_python_locally(source_code, stdin)

@router.post("/run", response_model=RunCodeResponse, summary="Scratch-execute candidate code")
async def run_code(body: RunCodeRequest) -> RunCodeResponse:
    if not body.source_code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_code is empty.")

    try:
        result = await _execute_code_locally(body.language, body.source_code, body.stdin)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unhandled error during /run: {e}", exc_info=True)
        return RunCodeResponse(
            status="success",
            result=ExecutionResult(stdout="", stderr=f"Execution failed: {str(e)}", exit_code=1),
        )

    return RunCodeResponse(status="success", result=result)


@router.post("/{session_id}/submit", summary="Execute + submit code as the candidate's turn")
async def submit_code(
    session_id: str,
    body: SubmitCodeRequest,
    session: AsyncSession = Depends(get_db),
    interview_graph=Depends(get_interview_graph),
):
    if not body.source_code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_code is empty.")

    try:
        execution_result = await _execute_code_locally(body.language, body.source_code, body.stdin)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unhandled error during /submit execution for session {session_id}: {e}", exc_info=True)
        execution_result = ExecutionResult(stdout="", stderr=f"Execution failed: {str(e)}", exit_code=1)

    respond_body = RespondRequest(
        content=body.accompanying_message or "[Candidate submitted a code solution]",
        code_in_editor=body.source_code,
        code_submission={
            "language": body.language,
            "source_code": body.source_code,
        },
        execution_result=execution_result.model_dump(),
        whiteboard_snapshot=body.whiteboard_snapshot,
        is_timer_submission=body.is_timer_submission,
    )

    import uuid as _uuid
    return await respond_to_question(
        session_id=_uuid.UUID(session_id),
        body=respond_body,
        session=session,
        interview_graph=interview_graph,
    )