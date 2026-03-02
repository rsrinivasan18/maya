"""
MAYA Web Interface — Session 11
=================================
FastAPI app: serves the chat UI, handles WebSocket connections, exposes REST APIs.

Run with:
    uvicorn src.maya.web.app:app --reload --host 0.0.0.0 --port 8000

Then open:  http://localhost:8000

WebSocket protocol
------------------
Client → Server:
    {"text": "What is gravity?", "model": "auto", "agent": "auto"}

Server → Client (in order):
    {"type": "connected", "user_name": "Srinika", "session_count": 5}
    {"type": "thinking"}
    {"type": "response", "text": "...", "intent": "question",
                          "language": "english", "steps": [...], "is_online": true}
    {"type": "error", "text": "Something went wrong: ..."}

LEARNING NOTES for Srinivasan:
--------------------------------
Why asyncio.to_thread()?
  maya_graph.invoke() is a SYNCHRONOUS blocking function — it calls Ollama/Sarvam
  and waits for the LLM to respond. Running it directly in an async function would
  freeze the entire server (block the event loop) while the LLM thinks.

  asyncio.to_thread() runs the blocking call in a thread-pool worker, keeping the
  event loop free to handle other WebSocket messages, API requests, etc.

Why WebSocket instead of HTTP POST?
  HTTP POST: client sends → waits → server responds (one round trip).
  WebSocket: persistent bidirectional channel. We can push "thinking..." immediately
  before the LLM responds, then push the response when ready. The client sees
  real-time status without polling.

Why is session_id important?
  Each WebSocket connection = one learning session.
  store.start_session() increments session_count in SQLite.
  session_id is passed to save_memory so turns are logged under the right session.
  Next session, greet_response shows "Welcome back! You explored gravity last time."
"""

import asyncio
import json
import warnings
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.maya.agents.memory_store import MemoryStore
from src.maya.config.settings import settings
from src.maya.graph.hello_world_graph import maya_graph

# Suppress LiteLLM's "no current event loop" warning in thread-pool workers
warnings.filterwarnings("ignore", message="There is no current event loop", category=DeprecationWarning)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="MAYA – Your Learning Companion", version="11.0")

# Serve static files at /static/*
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Serve the main chat UI."""
    return FileResponse(STATIC_DIR / "index.html")


# ── REST APIs ─────────────────────────────────────────────────────────────────

@app.get("/api/models")
async def get_models():
    """
    Return available LLM models based on which API keys are configured.
    The UI uses this to populate the model selector dropdown.
    "auto" is always first (tiered fallback chain).
    "ollama" is always last (local, no key needed).
    """
    available = ["auto"]
    if settings.HAS_SARVAM_KEY:
        available.append("sarvam")
    if settings.HAS_ANTHROPIC_KEY:
        available.append("claude")
    if settings.HAS_OPENAI_KEY:
        available.append("openai")
    available.append("ollama")
    return {"models": available}


@app.get("/api/history")
async def get_history():
    """
    Return sidebar data: user profile, recent topics, mastery summary.
    Called by the frontend after each response to refresh the sidebar.
    """
    store = MemoryStore()
    return {
        "profile":       store.get_profile(),
        "recent_topics": store.get_recent_topics(limit=5),
        "mastery":       store.get_mastery_summary(limit=8),
    }


@app.get("/api/health")
async def health():
    """Health check endpoint — useful for monitoring and RPi startup scripts."""
    return {"status": "ok", "version": "11.0"}


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main chat endpoint. One WebSocket connection = one learning session.

    Lifecycle:
        connect → send "connected" (with session info)
        loop:
            receive user message
            send "thinking" (avatar animates)
            invoke graph in thread pool (blocking LLM call)
            send "response" (with text + metadata)
        disconnect → session ends (background summary fires on farewell)
    """
    await websocket.accept()

    # Start a new session: increments session_count in SQLite
    store = MemoryStore()
    session_id = store.start_session()
    profile = store.get_profile()   # now has updated session_count

    # Tell the frontend who's here and which session this is
    await websocket.send_json({
        "type":          "connected",
        "user_name":     profile["user_name"],
        "session_count": profile["session_count"],
    })

    # message_history accumulates across turns (same pattern as chat_loop.py)
    message_history: list[dict] = []

    try:
        while True:
            # Wait for next message from the browser
            try:
                raw = await websocket.receive_text()
                data = json.loads(raw)
            except Exception:
                break

            user_text      = data.get("text", "").strip()
            preferred_model = data.get("model", "auto")
            agent_override  = data.get("agent", "auto")

            if not user_text:
                continue

            # Immediately signal "thinking" so the avatar animates and the UI
            # shows the dots indicator — before the (potentially slow) LLM call
            await websocket.send_json({"type": "thinking"})

            # Build state for this turn (same structure as chat_loop.py)
            # Add user message to history BEFORE invoking (graph appends assistant)
            history_with_user = message_history + [{"role": "user", "content": user_text}]

            state = {
                "user_input":      user_text,
                "language":        "",
                "intent":          "",
                "response":        "",
                "steps":           [],
                "message_history": history_with_user,
                "session_id":      session_id,
                "preferred_model": preferred_model,
                "agent_override":  agent_override,
            }

            try:
                # Run blocking graph call in a thread pool — keeps event loop free
                result = await asyncio.to_thread(maya_graph.invoke, state)

                # Accumulate history for next turn
                message_history = result["message_history"]

                await websocket.send_json({
                    "type":      "response",
                    "text":      result["response"],
                    "intent":    result.get("intent", "general"),
                    "language":  result.get("language", "english"),
                    "steps":     result.get("steps", []),
                    "is_online": result.get("is_online", False),
                })

            except Exception as exc:
                await websocket.send_json({
                    "type": "error",
                    "text": f"Something went wrong: {exc}",
                })

    except WebSocketDisconnect:
        pass  # Normal — browser closed tab or navigated away
    except Exception:
        pass  # Network error — connection already gone
