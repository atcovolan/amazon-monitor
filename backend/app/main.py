import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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
    logger.info("Iniciando API do Monitor de Precos Amazon...")

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
    logger.info("Encerrando API do Monitor de Precos Amazon...")
    monitor_srv.shutdown()

app = FastAPI(
    title="Amazon Price Monitor API",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development, can be customized in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "running", "service": "Amazon Price Monitor API"}


# Serve the built frontend (single-service deployment).
# In production the Docker build copies the compiled React app here.
_default_frontend = os.path.join(os.path.dirname(__file__), "..", "..", "frontend_dist")
FRONTEND_DIR = os.path.abspath(os.environ.get("FRONTEND_DIR", _default_frontend))

if os.path.isdir(FRONTEND_DIR):
    logger.info("Servindo frontend estatico de %s", FRONTEND_DIR)
    # html=True makes "/" serve index.html and handles static assets.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    logger.info("Frontend estatico nao encontrado em %s (modo dev).", FRONTEND_DIR)

    @app.get("/")
    def read_root():
        return {"status": "running", "service": "Amazon Price Monitor API"}
