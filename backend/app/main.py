import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes import cwc, flood, intelligence, location
from app.services.prediction_service import load_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("chetakai_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown events."""
    logger.info("Initializing ChetakAI FastAPI Flood Intelligence Engine...")
    # Pre-load ML model
    model = load_model()
    if model:
        logger.info(f"Loaded ML model: {model.get('model_name')} ({model.get('n_estimators')} trees)")
    else:
        logger.warning("ML model artifact not loaded; heuristic fallback active.")

    yield
    logger.info("Shutting down ChetakAI Engine...")


app = FastAPI(
    title="ChetakAI Flood Intelligence Engine",
    description="Multi-signal flood forecasting and ground-truth telemetry API for India river basins.",
    version="2.0.0",
    lifespan=lifespan
)

# ---------------------------------------------------------
# CORS Configuration (React Frontend Support)
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Route Registration
# ---------------------------------------------------------
# Canonical REST routes per task specifications
app.include_router(flood.router)
app.include_router(cwc.router)

# Backward-compatible routes matching React frontend contracts
app.include_router(intelligence.router)
app.include_router(location.router)


# ---------------------------------------------------------
# Root & Health Check Endpoints
# ---------------------------------------------------------
@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "service": "ChetakAI Flood Intelligence API",
        "status": "online",
        "runtime": "Python / FastAPI",
        "version": "2.0.0"
    }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "chetakai-fastapi-backend",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ---------------------------------------------------------
# Global Exception Handler
# ---------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "Internal server error"}
    )
