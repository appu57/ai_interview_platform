#!/bin/bash
# ============================================================
# AI Interview Platform — Combined Project Scaffold
# Backend  : project-file-structure.md (agents/RAG/finetune) + infra/ + missing dirs from images
# Frontend : from uploaded images (LiveKit/WebRTC/Excalidraw/Monaco stack)
#
# Run from: ~/projects/ai_interview_platform
#   bash setup_project_structure.sh
# ============================================================

set -e
ROOT="$(pwd)"
echo "Scaffolding project at: $ROOT"

# ----------------------------------------------------------
# ROOT FILES
# ----------------------------------------------------------
touch README.md .env .env.example .gitignore docker-compose.yml Makefile

# ----------------------------------------------------------
# BACKEND (FastAPI) — merged from .md + image agent/rag/db detail
# ----------------------------------------------------------
mkdir -p backend/api/routes
mkdir -p backend/agents/graph
mkdir -p backend/agents/nodes
mkdir -p backend/agents/tools
mkdir -p backend/webrtc
mkdir -p backend/rag
mkdir -p backend/db/migrations
mkdir -p backend/local_model
mkdir -p backend/guardrails
mkdir -p backend/core
mkdir -p backend/tests

# -- backend root --
touch backend/main.py            # FastAPI entrypoint, mounts routers, CORS, lifespan
touch backend/config.py          # env vars, model paths, API keys, ports
touch backend/requirements.txt   # pinned Python deps
touch backend/Dockerfile

# -- core (from .md) --
touch backend/core/security.py     # JWT verify, RBAC deps
touch backend/core/rate_limit.py   # per-tenant rate limiting
touch backend/core/cost_tracker.py # API usage/cost logging

# -- api/routes (from images) --
touch backend/api/routes/interview.py   # /start /submit-code /next-round /end
touch backend/api/routes/practice.py    # /ask /explain-video /topic-graph
touch backend/api/routes/auth.py        # JWT login, tenant isolation
touch backend/api/routes/websocket.py   # WS endpoint, real-time transcript
touch backend/api/deps.py               # db session, current user

# -- agents/graph (LangGraph state machines, from images) --
touch backend/agents/graph/interview_graph.py  # StateGraph for mock interview mode
touch backend/agents/graph/practice_graph.py   # StateGraph for tutor/practice mode
touch backend/agents/graph/state.py            # TypedDict: messages, transcript, round, scores, plan

# -- agents/nodes (from images, mapped onto .md's agent roles) --
touch backend/agents/nodes/scraper_node.py        # company rounds + question bank (use licensed datasets, not live scrape)
touch backend/agents/nodes/planner_node.py        # builds round schedule (interviewer_agent equivalent)
touch backend/agents/nodes/router_node.py         # conditional edge: routes on state.round_index
touch backend/agents/nodes/oa_node.py             # OA round: DSA Qs, code sandbox, evaluate
touch backend/agents/nodes/interviewer_node.py    # technical/behavioural round, cloud LLM + interrupt()
touch backend/agents/nodes/whiteboard_node.py     # canvas PNG -> vision model -> notes + transcript
touch backend/agents/nodes/evaluator_node.py      # score rubric, per-round feedback, state write
touch backend/agents/nodes/tutor_node.py          # RAG retrieval + local model call + TTS stream
touch backend/agents/nodes/dsa_tutor_node.py      # Socratic DSA explainer
touch backend/agents/nodes/sysdesign_tutor_node.py # HLD/LLD tutor, whiteboard-aware
touch backend/agents/nodes/video_explainer_node.py # transcript -> RAG -> local model answer

# -- agents/tools (merged from .md + images) --
touch backend/agents/tools/code_executor.py   # sandbox/Judge0 wrapper, test runner, timeout
touch backend/agents/tools/tts_tool.py        # TTS wrapper, streams audio
touch backend/agents/tools/stt_tool.py        # faster-whisper, VAD chunking
touch backend/agents/tools/github_tool.py     # GitHub API: scrape profile + push assignment repo
touch backend/agents/tools/youtube_transcript.py # transcript fetch + chunk
touch backend/agents/tools/company_rounds.py  # company -> round-structure mapping

# -- webrtc (LiveKit-based real-time voice, from images) --
touch backend/webrtc/signaling.py     # FastAPI WebSocket: SDP offer/answer, ICE (fallback path)
touch backend/webrtc/livekit_client.py # LiveKit Python SDK: subscribe candidate mic, publish TTS track
touch backend/webrtc/audio_pipeline.py # Opus decode -> whisper chunks -> transcript events

# -- rag (vector store + Neo4j knowledge graph) --
touch backend/rag/chroma_client.py        # ChromaDB init, upsert, top-k query
touch backend/rag/embedder.py             # sentence-transformers embed + upsert pipeline
touch backend/rag/neo4j_client.py         # Neo4j driver, Cypher queries, concept graph traversal
touch backend/rag/graph_rag.py            # parallel: vector search + Neo4j KG traverse -> merged context
touch backend/rag/knowledge_graph_seed.py # one-time: creates DSA concept nodes + edges in Neo4j

# -- db (merged: .md's models/schemas/session + images' migration detail) --
touch backend/db/models.py     # SQLAlchemy: Tenant, Candidate, Session, Round, Score
touch backend/db/schemas.py    # Pydantic schemas
touch backend/db/session.py    # DB engine + session factory (Postgres/Supabase)
touch backend/db/migrations/.gitkeep

# -- local_model (calls your self-quantized llama-server) --
touch backend/local_model/llama_client.py  # OpenAI-compat client -> localhost:8080, streaming

# -- guardrails (from .md) --
touch backend/guardrails/input_filter.py   # prompt-injection / moderation pre-check
touch backend/guardrails/output_filter.py  # response safety/leak check

# -- tests (from .md) --
touch backend/tests/test_orchestrator.py
touch backend/tests/test_agents.py
touch backend/tests/test_guardrails.py

# ----------------------------------------------------------
# FRONTEND (Next.js) — from uploaded images
# ----------------------------------------------------------
# Create core project directories
mkdir -p frontend/src/assets
mkdir -p frontend/src/components
mkdir -p frontend/src/hooks
mkdir -p frontend/src/lib
mkdir -p frontend/src/pages
mkdir -p frontend/src/store

# Root configuration files for standard React + Vite + TS setup
touch frontend/package.json
touch frontend/vite.config.ts
touch frontend/tsconfig.json
touch frontend/index.html
touch frontend/src/main.tsx
touch frontend/src/App.tsx
touch frontend/src/index.css

# -- pages --
# Loaded via react-router-dom in App.tsx
touch frontend/src/pages/Interview.tsx      # mock interview UI: video, code editor, whiteboard
touch frontend/src/pages/Practice.tsx       # practice/tutor UI: chat, topic graph, video input

# -- components --
touch frontend/src/components/VideoPanel.tsx        # candidate + AI video tiles (LiveKit React SDK)
touch frontend/src/components/WhiteboardCanvas.tsx  # Excalidraw embedded, PNG export on demand
touch frontend/src/components/CodeEditor.tsx        # Monaco Editor, language selector, run button
touch frontend/src/components/TranscriptPanel.tsx   # live scrolling STT transcript w/ speaker labels
touch frontend/src/components/RoundBadge.tsx        # current round, progress through plan
touch frontend/src/components/FeedbackCard.tsx      # per-round score + improvement tips
touch frontend/src/components/TopicGraph.tsx        # D3 force graph of DSA concepts
touch frontend/src/components/VideoInput.tsx        # YouTube URL input -> video_explainer_node

# -- hooks --
touch frontend/src/hooks/useWebRTC.ts       # RTCPeerConnection, SDP offer/answer, ICE
touch frontend/src/hooks/useLiveKit.ts      # LiveKit room, publish mic, subscribe AI audio
touch frontend/src/hooks/useWhiteboard.ts   # Excalidraw export loop, PNG blob -> WS send
touch frontend/src/hooks/useTranscript.ts   # WebSocket consumer, appends transcript lines

# -- store --
touch frontend/src/store/interviewStore.ts  # Zustand: session state, round, scores, messages

# -- lib --
touch frontend/src/lib/apiClient.ts     # Axios instance, auth headers, base URL
touch frontend/src/lib/geminiClient.ts  # whiteboard PNG -> Gemini vision call

echo "React + Vite frontend file structure initialized successfully! Create React App (CRA) deprecated"

# ----------------------------------------------------------
# VOICE (STT/TTS engines — invoked from backend/webrtc/audio_pipeline.py)
# ----------------------------------------------------------
mkdir -p voice
touch voice/stt_service.py  # faster-whisper (consumed by audio_pipeline.py)
touch voice/tts_service.py  # Piper/edge-tts (output published via livekit_client.py)
touch voice/vad.py          # voice activity detection (silero-vad)

# ----------------------------------------------------------
# FINE-TUNING PIPELINE (from .md, matches earlier QLoRA/GGUF docs)
# ----------------------------------------------------------
mkdir -p finetune/scripts
mkdir -p finetune/configs
mkdir -p finetune/dataset
mkdir -p finetune/adapter
mkdir -p finetune/merged
mkdir -p finetune/gguf

touch finetune/scripts/build_dataset.py    # merge sources, dedup, validate -> train.jsonl
touch finetune/scripts/train.py            # Unsloth QLoRA fine-tune -> adapter/
touch finetune/scripts/merge.py            # merge LoRA into base -> merged/ (BF16, run on CPU)
touch finetune/scripts/convert_to_gguf.py  # calls llama.cpp convert_hf_to_gguf.py -> F16 GGUF
touch finetune/scripts/quantize.py         # llama-quantize F16 -> Q4_K_M (+ imatrix)
touch finetune/scripts/bench.py            # llama-bench wrapper / eval
touch finetune/configs/training_config.yaml

# dataset placeholders
touch finetune/dataset/train.jsonl   # 400-500 ChatML/Alpaca instruction-output pairs
touch finetune/dataset/eval.jsonl    # held-out validation examples

# NOTE: finetune/adapter/, finetune/merged/, finetune/gguf/ are gitignored output dirs

# ----------------------------------------------------------
# DATASETS (RAG corpora + company round data, from .md)
# ----------------------------------------------------------
mkdir -p datasets
touch datasets/dsa_chunks.jsonl
touch datasets/os_cn_chunks.jsonl
touch datasets/sysdesign_chunks.jsonl
touch datasets/company_rounds.json
touch datasets/SOURCES.md

# ----------------------------------------------------------
# BASE MODEL (downloaded HF weights, gitignored)
# ----------------------------------------------------------
mkdir -p base_model

# ----------------------------------------------------------
# OUTPUTS (general fine-tune artifacts if not using finetune/gguf above)
# ----------------------------------------------------------
mkdir -p outputs

# ----------------------------------------------------------
# INFRA (from images: docker, nginx, livekit + .md's model-matrix/prompts)
# ----------------------------------------------------------
mkdir -p infra/docker
mkdir -p infra/nginx
mkdir -p infra/livekit
mkdir -p infra/prompts
mkdir -p infra/deploy

touch infra/docker/Dockerfile.backend   # Python 3.11, installs requirements, runs uvicorn
touch infra/docker/Dockerfile.frontend  # Node 20, builds Next.js, serves on 3000
touch infra/docker/Dockerfile.livekit   # LiveKit server, coturn STUN/TURN config

touch infra/nginx/nginx.conf  # reverse proxy: /api -> :8000, / -> :3000, /ws -> :7880
touch infra/livekit/livekit.yaml  # room config, TURN credentials, port bindings

touch infra/model-matrix.md  # model roles / VRAM / fallback chain
touch infra/prompts/interviewer_system_prompt.md
touch infra/prompts/tutor_system_prompt.md
touch infra/prompts/evaluator_system_prompt.md

touch infra/deploy/railway.json
touch infra/deploy/vercel.json

# ----------------------------------------------------------
# .gitignore content
# ----------------------------------------------------------
cat > .gitignore << 'EOF'
# Models & large artifacts
base_model/
outputs/
finetune/adapter/
finetune/merged/
finetune/gguf/
llama.cpp/

# RAG store (vector DB; Neo4j data lives in Docker volume, not here)
backend/rag/rag_store/

# Python
venv/
__pycache__/
*.pyc

# Node
node_modules/
.next/

# Env
.env
EOF
echo "Done. Structure created under: $ROOT"
echo ""
echo "Notes: Jai Hanuman"
echo "  - backend/agents/nodes/scraper_node.py: use licensed datasets (MBPP/APPS/CodeContests +"
echo "    company-tagged HF datasets), NOT live scraping LeetCode/GFG (ToS risk)."
echo "  - Neo4j + LiveKit + coturn run as Docker services (see docker-compose.yml)."
echo "    These are CPU/RAM services and do NOT consume your 4GB VRAM, but check total"
echo "    system RAM: llama-server + Neo4j + LiveKit + coturn + Postgres + Redis"
echo "    concurrently wants ~8-16GB RAM."
echo "  - finetune/gguf/model-Q4_K_M.gguf is your production-served model (~2.3-2.5GB at"
echo "    standard Q4_K_M for Qwen3-4B; verify against your actual quantization output)."