from fastapi import FastAPI, HTTPException, Body, Request
from pydantic import BaseModel
# from worker import SeleniumWorker
import threading
import uuid
import logging
import os
from contextlib import asynccontextmanager

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    port = os.environ.get("PORT", "Not Set")
    logger.info(f"Lifespan Startup: Application starting on port {port}")
    # Worker checks disabled
    yield
    # Shutdown
    logger.info("Lifespan Shutdown: Cleaning up resources")

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
    # worker = SeleniumWorker()
    worker = None # Temporarily disabled for debugging
    logger.info("Worker DISABLED for debugging")
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

# Worker logic temporarily disabled for "Hello World" test
# ... (rest of the file content commented out or unused)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting uvicorn on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
