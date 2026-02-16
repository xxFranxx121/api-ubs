from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from worker import SeleniumWorker
import threading
import uuid
import logging
import os

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

app = FastAPI(title="Gestor de Impresión API", version="1.0.0")

# --- Global State ---
# In a production app, we might use a dependency injection or a singleton manager.
# For simplicity here, we use a global instance.
worker = SeleniumWorker()

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
    # To run: uvicorn futuraapi:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)
