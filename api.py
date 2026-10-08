"""
Pluto Local Backend Service (FastAPI)
Path: /home/jenil/Pluto/api.py
"""
import os
import sys
import socket
import logging
from datetime import datetime
import asyncio
from typing import Optional

# Suppress excessive third-party logging
os.environ["LOG_LEVEL"] = "ERROR"
os.environ["COGNEE_LOG_LEVEL"] = "ERROR"

# 1. Prefer IPv4 over IPv6 to avoid DNS timeouts on misconfigured networks
_orig_getaddrinfo = socket.getaddrinfo
def patched_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    return sorted(res, key=lambda x: x[0] == socket.AF_INET, reverse=True)
socket.getaddrinfo = patched_getaddrinfo

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pluto.api")

# 2. Dynamic import of Pluto core engine with graceful fallback
CORE_AVAILABLE = False
CORE_INIT_ERROR: Optional[str] = None
generate_response = None
run_tool_loop = None
save_messages = None

try:
    from pluto.core import generate_response as _gen_resp, run_tool_loop as _tool_loop
    from pluto.memory.chat_history import (
        save_messages as _save_msgs,
        generate_summary as _generate_summary,
        get_messages_since_last_summary as _get_msgs_since
    )
    from pluto.security.confirmation import get_pending_command, resolve_confirmation
    generate_response = _gen_resp
    run_tool_loop = _tool_loop
    save_messages = _save_msgs
    generate_summary = _generate_summary
    get_messages_since_last_summary = _get_msgs_since
    CORE_AVAILABLE = True
    logger.info("Pluto core engine loaded successfully.")
except Exception as exc:
    CORE_AVAILABLE = False
    CORE_INIT_ERROR = str(exc)
    logger.warning("Pluto core engine unavailable, running in fallback mode: %s", exc)

# Concurrency lock for stateful chat session
agent_lock = asyncio.Lock()

# 3. FastAPI Initialization
app = FastAPI(
    title="Pluto API",
    description="Local backend service for Pluto AI OS",
    version="1.0.0"
)

# 4. CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Data Models
class HealthResponse(BaseModel):
    status: str = Field(default="ok", example="ok")
    service: str = Field(default="pluto-api", example="pluto-api")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User prompt or query")
    session_id: str = Field(default="main", description="Session ID for isolated memory routing")

class ChatResponse(BaseModel):
    reply: str = Field(..., description="Assistant response text")
    state: str = Field(default="idle", description="Current agent state")

# 6. Helper: Local Fallback Generator
def generate_local_fallback(message: str, reason: str = "") -> str:
    import re
    msg_lower = message.strip().lower()
    now = datetime.now()

    if re.search(r'\b(time|clock)\b', msg_lower) and not reason:
        return f"It is currently {now.strftime('%I:%M %p')}, Sir."
    if re.search(r'\b(date|today)\b', msg_lower) and not reason:
        return f"Today is {now.strftime('%A, %B %d, %Y')}, Sir."
    if any(q in msg_lower for q in ["who are you", "what is pluto", "introduce"]):
        return "I am Pluto, your intelligent, local-first engineering partner."
    if any(q in msg_lower for q in ["status", "health", "system"]):
        core_status = "Online" if CORE_AVAILABLE else f"Offline ({reason or 'Fallback mode'})"
        return f"Pluto local backend is active. Core engine status: {core_status}."

    return (
        "I am currently operating in local fallback mode because external AI model access "
        f"is unavailable ({reason or 'network/key error'}). All local services remain active. "
        "Please check your GEMINI_API_KEY in .env and network connection."
    )

async def _process_core_query(query: str, session_id: str = "main") -> Optional[str]:
    """Helper to process query through Pluto core and tool loop with dynamic session context."""
    if generate_response is None:
        return None
    resp = await generate_response(query, session_id=session_id)
    if not resp:
        return None
    if run_tool_loop:
        resp = await run_tool_loop(resp, session_id=session_id)
    if resp and hasattr(resp, "text") and resp.text:
        return resp.text
    return None

# 7. Endpoints
class ConfirmRequest(BaseModel):
    allow: bool

@app.get("/api/pending_confirmation")
async def check_pending_confirmation():
    if not CORE_AVAILABLE:
        return {"pending": False, "command": None}
    cmd = get_pending_command()
    return {"pending": bool(cmd), "command": cmd}

@app.post("/api/confirm")
async def confirm_command(req: ConfirmRequest):
    if CORE_AVAILABLE:
        resolve_confirmation(req.allow)
    return {"status": "ok"}

@app.get("/api/health", response_model=HealthResponse)
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint returning status and service identity."""
    return HealthResponse(status="ok", service="pluto-api")

from fastapi import BackgroundTasks
from pluto.config import PLUTO_API_TIMEOUT

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    """Chat endpoint processing user queries via Pluto core or local fallback."""
    user_text = request.message.strip()
    session_id = request.session_id
    if not user_text:
        return ChatResponse(reply="Please provide a valid query.", state="idle")

    reply_text = ""
    timestamp = datetime.now().isoformat()

    async with agent_lock:
        if not CORE_AVAILABLE or generate_response is None:
            reply_text = generate_local_fallback(user_text, reason=CORE_INIT_ERROR or "Core not loaded")
        else:
            try:
                if PLUTO_API_TIMEOUT > 0:
                    reply_text = await asyncio.wait_for(_process_core_query(user_text, session_id=session_id), timeout=float(PLUTO_API_TIMEOUT))
                else:
                    reply_text = await _process_core_query(user_text, session_id=session_id)

                if not reply_text:
                    reply_text = generate_local_fallback(user_text, reason="No response returned from model")
            except asyncio.TimeoutError:
                logger.warning(f"Pluto core query processing exceeded configured timeout threshold ({PLUTO_API_TIMEOUT}s)")
                reply_text = generate_local_fallback(user_text, reason=f"Query processing time exceeded {PLUTO_API_TIMEOUT} seconds")
            except Exception as exc:
                logger.exception("Error while processing message through Pluto core: %s", exc)
                reply_text = generate_local_fallback(user_text, reason=str(exc))

    # Persist conversation to SQLite chat history if available
    if save_messages:
        try:
            save_messages([
                ("user", user_text, timestamp),
                ("model", reply_text, datetime.now().isoformat())
            ], session_id=session_id)
            
            # Auto-compaction: Trigger summary generation in the background if threshold exceeded
            if get_messages_since_last_summary:
                new_msgs = get_messages_since_last_summary(session_id=session_id)
                if new_msgs >= 10:
                    logger.info(f"Threshold reached ({new_msgs} new messages for session {session_id}). Triggering auto-compaction.")
                    # Pass session_id explicitly to the background task
                    background_tasks.add_task(generate_summary, session_id=session_id)
                    
        except Exception as db_err:
            logger.warning("Failed to persist conversation history: %s", db_err)

    return ChatResponse(reply=reply_text, state="idle")

# 8. Serve Frontend Static Files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIST_DIR = os.path.join(BASE_DIR, "ui/dist")

app.mount("/assets", StaticFiles(directory=os.path.join(UI_DIST_DIR, "assets")), name="assets")

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    dist_path = os.path.join(UI_DIST_DIR, full_path)
    if full_path and os.path.isfile(dist_path):
        return FileResponse(dist_path)
    return FileResponse(os.path.join(UI_DIST_DIR, "index.html"))

# 9. Script Entrypoint
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
