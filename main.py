from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import uuid
import logging
import os
import time
import psutil
from contextlib import asynccontextmanager

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

# Robust Import
SeleniumWorker = None
try:
    logger.info("Attempting to import SeleniumWorker...")
    from worker import SeleniumWorker
    logger.info("SeleniumWorker imported successfully.")
except Exception as e:
    logger.error(f"Failed to import SeleniumWorker: {e}")
    SeleniumWorker = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    port = os.environ.get("PORT", "Not Set")
    logger.info(f"Lifespan Startup: Application starting on port {port}")
    yield
    # Shutdown
    logger.info("Lifespan Shutdown: Cleaning up resources")
    for session_id, worker in workers.items():
        try:
            worker.stop_session()
            logger.info(f"Stopped session {session_id}")
        except Exception:
            pass
    workers.clear()
    last_activity.clear()

app = FastAPI(title="Gestor de Impresión API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response Status: {response.status_code}")
    return response

# --- Configuration ---
MAX_SESSIONS = int(os.environ.get("MAX_SESSIONS", 3))
SESSION_IDLE_TIMEOUT = int(os.environ.get("SESSION_IDLE_TIMEOUT", 600))  # 10 min default

# --- Global State ---
workers = {}  # session_id -> SeleniumWorker
last_activity = {}  # session_id -> timestamp of last call


def cleanup_idle_sessions():
    """Remove sessions that have been idle longer than SESSION_IDLE_TIMEOUT."""
    now = time.time()
    to_remove = [
        sid for sid, ts in last_activity.items()
        if now - ts > SESSION_IDLE_TIMEOUT
    ]
    for sid in to_remove:
        idle_time = int(now - last_activity.pop(sid, now))
        worker = workers.pop(sid, None)
        if worker:
            try:
                worker.stop_session()
            except Exception:
                pass
            logger.info(f"Auto-closed idle session {sid} (inactive {idle_time}s)")
    return len(to_remove)

# --- Models ---
class LoginRequest(BaseModel):
    user: str
    password: str
    fecha_desde: str
    fecha_hasta: str
    headless: bool = True

class ProcessRequest(BaseModel):
    session_id: str
    nai: str

class StopRequest(BaseModel):
    session_id: str

# --- Endpoints ---

@app.get("/")
def home():
    return {"message": "Gestor de Impresión API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/start-session")
def start_session(req: LoginRequest):
    if not SeleniumWorker:
        raise HTTPException(status_code=503, detail="SeleniumWorker not available (Import failed)")

    # Clean up idle sessions before checking the limit
    cleanup_idle_sessions()

    if len(workers) >= MAX_SESSIONS:
        raise HTTPException(
            status_code=429,
            detail=f"Max sessions reached ({MAX_SESSIONS}). Stop an existing session or wait for idle cleanup."
        )

    session_id = str(uuid.uuid4())
    worker = SeleniumWorker()

    try:
        worker.start_session(
            user=req.user,
            password=req.password,
            fecha_desde=req.fecha_desde,
            fecha_hasta=req.fecha_hasta,
            headless=req.headless
        )
        workers[session_id] = worker
        last_activity[session_id] = time.time()
        logger.info(f"Session {session_id} started for user {req.user}")
        return {"status": "Session started successfully", "session_id": session_id}
    except Exception as e:
        worker.stop_session()
        logger.error(f"Error starting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop-session")
def stop_session(req: StopRequest):
    worker = workers.pop(req.session_id, None)
    last_activity.pop(req.session_id, None)
    if not worker:
        raise HTTPException(status_code=404, detail="Session not found")

    worker.stop_session()
    logger.info(f"Session {req.session_id} stopped")
    return {"status": "Session stopped"}

@app.post("/process-nai")
def process_nai(req: ProcessRequest):
    worker = workers.get(req.session_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Session not found. Call /start-session first.")

    if not worker.is_running:
        raise HTTPException(status_code=400, detail="Session not active.")

    try:
        last_activity[req.session_id] = time.time()
        result = worker.process_nai(nai=req.nai)
        return result
    except Exception as e:
        logger.error(f"Error processing NAI {req.nai} in session {req.session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
def get_status():
    cleanup_idle_sessions()

    now = time.time()
    process = psutil.Process()
    mem = process.memory_info()

    sessions = []
    for session_id, worker in workers.items():
        idle_seconds = int(now - last_activity.get(session_id, now))
        sessions.append({
            "session_id": session_id,
            "is_running": worker.is_running,
            "has_driver": worker.driver is not None,
            "idle_seconds": idle_seconds,
            "idle_timeout_in": max(0, SESSION_IDLE_TIMEOUT - idle_seconds),
        })

    return {
        "active_sessions": len(sessions),
        "max_sessions": MAX_SESSIONS,
        "memory": {
            "rss_mb": round(mem.rss / 1024 / 1024, 1),
            "vms_mb": round(mem.vms / 1024 / 1024, 1),
        },
        "idle_timeout_seconds": SESSION_IDLE_TIMEOUT,
        "sessions": sessions,
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting uvicorn on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
