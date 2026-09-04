import json
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Request

from app.models.schemas import AnalyzeRequest, ChatRequest
from app.services.intelligence_service import generate_flood_intelligence
from app.services.llm_service import chat_with_copilot

router = APIRouter(prefix="/api/v1/intelligence", tags=["Intelligence"])

# Path to glossary JSON
CURRENT_DIR = Path(__file__).resolve().parent
GLOSSARY_PATH = CURRENT_DIR.parent.parent / "data" / "glossary.json"


@router.post("/analyze")
async def analyze_location(payload: AnalyzeRequest) -> Dict[str, Any]:
    """
    Main analysis endpoint invoked directly by the React frontend.
    Returns the comprehensive multi-signal flood intelligence payload.
    """
    try:
        lang = payload.language or payload.lang or "en"
        return await generate_flood_intelligence(
            latitude=payload.latitude,
            longitude=payload.longitude,
            language=lang,
            demo_scenario=payload.demoScenario
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis pipeline error: {str(exc)}")


@router.get("/debug/analysis")
async def debug_analyze(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    language: str = Query("en"),
    demoScenario: Optional[int] = Query(None)
) -> Dict[str, Any]:
    """GET debug endpoint for quick browser inspection of the full intelligence payload."""
    try:
        return await generate_flood_intelligence(
            latitude=lat,
            longitude=lon,
            language=language,
            demo_scenario=demoScenario
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Debug analysis error: {str(exc)}")


@router.post("/chat")
async def chat_copilot(payload: ChatRequest) -> Dict[str, Any]:
    """Conversational copilot for contextual flood intelligence decision support."""
    try:
        return await chat_with_copilot(
            message=payload.message,
            telemetry=payload.telemetry or {},
            language=payload.language or "en",
            history=payload.history or []
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Copilot chat error: {str(exc)}")


@router.get("/glossary")
async def get_glossary() -> Dict[str, Any]:
    """Returns technical metric explanations for the frontend explainer modal."""
    try:
        if GLOSSARY_PATH.exists():
            with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load glossary: {str(exc)}")
