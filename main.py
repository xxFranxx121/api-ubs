from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import uuid
import logging
import os
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

# --- Global State ---
workers = {}  # session_id -> SeleniumWorker

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
        logger.info(f"Session {session_id} started for user {req.user}")
        return {"status": "Session started successfully", "session_id": session_id}
    except Exception as e:
        worker.stop_session()
        logger.error(f"Error starting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop-session")
def stop_session(req: StopRequest):
    worker = workers.pop(req.session_id, None)
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
        result = worker.process_nai(nai=req.nai)
        return result
    except Exception as e:
        logger.error(f"Error processing NAI {req.nai} in session {req.session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
def get_status():
    sessions = []
    for session_id, worker in workers.items():
        sessions.append({
            "session_id": session_id,
            "is_running": worker.is_running,
            "has_driver": worker.driver is not None
        })
    return {"active_sessions": len(sessions), "sessions": sessions}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting uvicorn on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
