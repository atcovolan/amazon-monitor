import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.routes import api
from backend.app.storage.json_storage import JsonStorage
from backend.app.services.monitor import MonitorService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Iniciando API do Monitor de Preços Amazon...")
    
    # Configure directories
    data_dir = os.environ.get("DATA_DIR", "data")
    storage = JsonStorage(data_dir=data_dir)
    monitor_srv = MonitorService(storage=storage)
    
    # Inject dependencies to routes
    api._storage = storage
    api._monitor_service = monitor_srv
    
    # Start scheduler
    monitor_srv.start()
    
    yield
    
    # Shutdown
    logger.info("Encerrando API do Monitor de Preços Amazon...")
    monitor_srv.shutdown()

app = FastAPI(
    title="Amazon Price Monitor API",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for development, can be customized in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api.router, prefix="/api")

@app.get("/")
def read_root():
    return {"status": "running", "service": "Amazon Price Monitor API"}
