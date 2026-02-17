from fastapi import FastAPI, HTTPException, Body, Request
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
    
    global worker
    if SeleniumWorker:
        try:
            worker = SeleniumWorker()
            logger.info("Worker instance initialized.")
        except Exception as e:
            logger.error(f"Worker init failed: {e}")
            worker = None
    else:
        logger.warning("SeleniumWorker class not available (import failed).")
        worker = None

    yield
    # Shutdown
    logger.info("Lifespan Shutdown: Cleaning up resources")
    if worker and hasattr(worker, 'stop_session'):
        worker.stop_session()

app = FastAPI(title="Gestor de Impresión API", version="1.0.0", lifespan=lifespan)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response Status: {response.status_code}")
    return response

# --- Global State ---
worker = None

# --- Models ---
class LoginRequest(BaseModel):
    user: str
    password: str
    fecha_desde: str
    fecha_hasta: str
    headless: bool = True

class ProcessRequest(BaseModel):
    nai: str

class TaskResponse(BaseModel):
    task_id: str
    status: str

# --- Endpoints ---

@app.get("/")
def home():
    return {"message": "Gestor de Impresión API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/start-session")
def start_session(req: LoginRequest):
    """
    Initializes the Selenium WebDriver and logs into the system.
    """
    if not worker:
        raise HTTPException(status_code=503, detail="Worker not initialized (Import/Startup failed)")

    if worker.driver:
        return {"status": "Already running"}
    
    try:
        worker.start_session(
            user=req.user,
            password=req.password,
            fecha_desde=req.fecha_desde,
            fecha_hasta=req.fecha_hasta,
            headless=req.headless
        )
        return {"status": "Session started successfully"}
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop-session")
def stop_session():
    """
    Closes the browser and ends the session.
    """
    if not worker:
        return {"status": "Worker not initialized"}
        
    worker.stop_session()
    return {"status": "Session stopped"}

@app.post("/process-nai")
def process_nai(req: ProcessRequest):
    """
    Processes a single NAI synchronously (for now).
    """
    if not worker:
        raise HTTPException(status_code=503, detail="Worker not initialized")

    if not worker.is_running:
        raise HTTPException(status_code=400, detail="Session not started. Call /start-session first.")

    try:
        result = worker.process_nai(
            nai=req.nai
        )
        return result
        
    except Exception as e:
        logger.error(f"Error processing NAI {req.nai}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
def get_status():
    """
    Returns the current status of the worker.
    """
    if not worker:
        return {"status": "Worker not initialized", "is_running": False}

    return {
        "is_running": worker.is_running,
        "has_driver": worker.driver is not None
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting uvicorn on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
