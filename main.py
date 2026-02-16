from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from worker import SeleniumWorker
import threading
import uuid
import logging
import os

# --- Configuration ---
from fastapi import FastAPI, HTTPException, Body, Request
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    port = os.environ.get("PORT", "Not Set")
    logger.info(f"Lifespan Startup: Application starting on port {port}")
    if worker:
        logger.info("Worker instance is ready (lazy init)")
    else:
        logger.error("Worker instance failed to initialize")
    yield
    # Shutdown
    logger.info("Lifespan Shutdown: Cleaning up resources")
    if worker and worker.driver:
        worker.stop_session()

app = FastAPI(title="Gestor de Impresión API", version="1.0.0", lifespan=lifespan)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response Status: {response.status_code}")
    return response

# --- Global State ---
# In a production app, we might use a dependency injection or a singleton manager.
# For simplicity here, we use a global instance.
try:
    worker = SeleniumWorker()
except Exception as e:
    logger.error(f"Failed to initialize worker: {e}")
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
    worker.stop_session()
    return {"status": "Session stopped"}

@app.post("/process-nai")
def process_nai(req: ProcessRequest):
    """
    Processes a single NAI synchronously (for now).
    Blocks until the NAI is processed. 
    In a more advanced version, this would add to a queue and return a Task ID.
    """
    if not worker.is_running:
        raise HTTPException(status_code=400, detail="Session not started. Call /start-session first.")

    try:
        # For this version, we run it directly. 
        # If concurrency is needed, we need to manage locking or a queue on the worker.
        # Since Selenium is single-threaded per driver, we must lock or just run one by one.
        
        # Simple lock mechanism could be added here if multiple requests come in.
        
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
    return {
        "is_running": worker.is_running,
        "has_driver": worker.driver is not None
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting uvicorn on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
