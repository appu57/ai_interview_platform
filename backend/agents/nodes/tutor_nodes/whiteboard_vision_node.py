import logging
import json
import re
import io
import base64
import os
from typing import List, Literal, Optional
from groq import AsyncGroq
from pydantic import BaseModel, Field, ValidationError, field_validator
from PIL import Image

from backend.agents.graph.state import TutorSystemDesignState
from backend.agents.nodes.tutor_nodes.guardrails import check_input
from backend.agents.nodes.tutor_nodes.observability import (
    record_guardrail_block,
    record_parse_failure,
    timed,
)

logger = logging.getLogger("mockai-tutor-graph")

VISION_MODEL = "qwen/qwen3.6-27b"

MAX_IMAGE_DIMENSION = 1280

class CanvasNode(BaseModel):
    id: str = Field(description="Unique snake_case identifier for the block (e.g., load_balancer_1)")
    type: Literal["server", "database", "client", "cloud", "cache", "queue", "storage"] = Field(
        description="The physical or logical category of the infrastructure element."
    )
    label: str = Field(description="The exact text or service name labeled inside the shape.")
    role: str = Field(description="Detailed engineering function within the high-level architecture.")
    technical_details: Optional[str] = Field(
        default=None,
        description="Implicit or explicit technology choices, protocols, storage schemas, or mechanisms."
    )


class CanvasEdge(BaseModel):
    source: str = Field(description="The source node ID where the communication arrow begins.")
    target: str = Field(description="The target node ID where the communication arrow points.")
    label: Optional[str] = Field(default=None, description="The text along the data stream line (e.g., HTTPS, gRPC, CDC).")
    is_async: bool = Field(default=False, description="True if the connection stream uses asynchronous non-blocking patterns.")



class DiagramSchema(BaseModel):
    nodes: List[CanvasNode] = Field(default_factory=list, description="Comprehensive flat listing of every microservice or structural shape discovered.")
    edges: List[CanvasEdge] = Field(default_factory=list, description="The structural topological data flow networks connecting the elements.")
    architectural_gaps: List[str] = Field(
        default_factory=list,
        description="Missing resilience configurations, single points of failure, or security bottlenecks seen on the board."
    )
    notes: Optional[str] = Field(default=None, description="General structural summary or items difficult to parse completely.")

    @field_validator("notes", mode="before")
    @classmethod
    def _coerce_notes_to_string(cls, v):
        if isinstance(v, list):
            return " ".join(str(item) for item in v if item)
        return v


# _client = AsyncOpenAI(base_url=LOCAL_LLM_URL, api_key="ollama")
_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

VISION_SYSTEM_PROMPT = (
    "You are an expert system design architect transcribing complex whiteboard system diagrams into comprehensive, highly "
    "detailed schema blueprints. Thoroughly analyze the topology, inspect all textual nuances -- including any handwritten "
    "notes, labels, or technical annotations anywhere on the image -- identify structural connections, and output a "
    "structural model mapping exactly to the requested payload definitions. Capture everything legible on the board, even "
    "partial or ambiguous notes -- put anything that doesn't cleanly fit a node or edge into `notes` rather than dropping it. "
    "Respond with ONLY a single valid JSON object matching this exact schema, no markdown fences, no commentary:\n\n"
    f"{json.dumps(DiagramSchema.model_json_schema(), indent=2)}"
)


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _strip_data_url_prefix(image_b64: str) -> str:
    if image_b64.startswith("data:"):
        return image_b64.split(",", 1)[1]
    return image_b64

def _downscale_image_b64(image_b64: str, max_dimension: int = MAX_IMAGE_DIMENSION) -> str:
    try:
        raw_bytes = base64.b64decode(image_b64)
        with Image.open(io.BytesIO(raw_bytes)) as img:
            width, height = img.size
            longest_side = max(width, height)
            if longest_side <= max_dimension:
                return image_b64

            scale = max_dimension / longest_side
            new_size = (int(width * scale), int(height * scale))
            resized = img.convert("RGB").resize(new_size, Image.LANCZOS)

            buffer = io.BytesIO()
            resized.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        logger.warning(f"[tutor] Failed to downscale whiteboard image, sending original: {e}")
        return image_b64
    
def _empty_diagram(notes: str) -> dict:
    return {"whiteboard_json": {"nodes": [], "edges": [], "architectural_gaps": [], "notes": notes}}


def _clean_text(value: Optional[str], field_desc: str) -> Optional[str]:
    ok, reason = check_input(value or "")
    if not ok:
        logger.error(f"[tutor] Redacted whiteboard {field_desc}: {reason}")
        record_guardrail_block("vision", "input", f"{field_desc}: {reason}")
        return "[redacted: flagged content]"
    return value


def _sanitize_diagram(diagram: DiagramSchema) -> DiagramSchema:
    for node in diagram.nodes:
        node.label = _clean_text(node.label, f"node label ({node.id})") or node.label
        node.role = _clean_text(node.role, f"node role ({node.id})") or node.role
        node.technical_details = _clean_text(node.technical_details, f"node technical_details ({node.id})")

    for edge in diagram.edges:
        edge.label = _clean_text(edge.label, f"edge label ({edge.source}->{edge.target})")

    diagram.notes = _clean_text(diagram.notes, "notes")
    diagram.architectural_gaps = [
        _clean_text(gap, "architectural_gaps entry") or gap for gap in diagram.architectural_gaps
    ]
    return diagram


async def whiteboard_vision_node(state: TutorSystemDesignState) -> dict:
    snapshot = state.get("whiteboard_image")
    if not snapshot:
        logger.warning("[tutor] whiteboard_vision_node invoked with no whiteboard_image in state.")
        return _empty_diagram("NO_SNAPSHOT_SUBMITTED")

    image_b64 = _strip_data_url_prefix(snapshot)
    image_b64 = _downscale_image_b64(image_b64)

    try:
        with timed("vision"):
            response = await _client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {"role": "system", "content": VISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze and reverse-engineer this whiteboard system diagram in deep architectural detail."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        ],
                    },
                ],
                temperature=0.1,
                max_tokens=2500,
                response_format={"type": "json_object"},
                timeout=30.0,
            )

        raw_output = response.choices[0].message.content or "{}"
        cleaned = _strip_json_fences(raw_output)
        parsed = json.loads(cleaned)

        diagram = DiagramSchema.model_validate(parsed)
        diagram = _sanitize_diagram(diagram)

    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"[tutor] Vision output didn't match the expected schema: {e}", exc_info=True)
        record_parse_failure("vision", str(e))
        return _empty_diagram(f"VISION_PARSE_FAILED: {str(e)}")
    except Exception as e:
        logger.error(f"[tutor] Vision API call failed: {e}", exc_info=True)
        return _empty_diagram(f"VISION_CALL_FAILED: {str(e)}")

    logger.info(f"[tutor] Parsed {len(diagram.nodes)} nodes / {len(diagram.edges)} edges from whiteboard.")

    return {"whiteboard_json": diagram.model_dump()}