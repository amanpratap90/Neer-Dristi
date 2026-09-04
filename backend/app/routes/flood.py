from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query

from app.services.intelligence_service import generate_flood_intelligence

router = APIRouter(prefix="/api", tags=["Flood Monitoring"])


@router.get("/flood-monitoring")
async def get_flood_monitoring(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180"),
    language: str = Query("en", description="Language code (en, hi, etc.)"),
    demoScenario: Optional[int] = Query(None, ge=1, le=5, description="Demo scenario (1-5)")
) -> Dict[str, Any]:
    """
    Canonical Main Flood Monitoring API.
    Returns multi-source environmental and AI-based signals without requiring CWC.
    """
    try:
        full = await generate_flood_intelligence(
            latitude=lat,
            longitude=lon,
            language=language,
            demo_scenario=demoScenario
        )

        ai_data = full.get("ai_risk_status", {})
        fallback_data = full.get("fallback_environmental", {})
        overall_data = full.get("overall_monitoring", {})
        weather_data = full.get("current_weather", {})
        rf24 = weather_data.get("rainfall_24h", {}).get("value") or fallback_data.get("rainfall_mm") or 0.0
        rf_fc = fallback_data.get("forecast_rainfall_mm") or 0.0

        return {
            "location": {
                "latitude": lat,
                "longitude": lon,
                "name": full.get("location", {}).get("display_name"),
                "basin": full.get("location", {}).get("basin_name")
            },
            "ai": {
                "source": "AI_MODEL",
                "probability": ai_data.get("probability"),
                "probability_pct": ai_data.get("probability_pct"),
                "risk": ai_data.get("risk"),
                "model_name": ai_data.get("model_name")
            },
            "weather": {
                "source": "WEATHER_API",
                "rainfall_mm": rf24,
                "forecast_rainfall_mm": rf_fc,
                "risk": fallback_data.get("risk", "LOW")
            },
            "historical_flood_context": full.get("historical_flood_context", {}),
            "overall": {
                "status": overall_data.get("status"),
                "confidence": overall_data.get("confidence"),
                "basis": overall_data.get("basis", ["AI_MODEL"]),
                "explanation": overall_data.get("explanation")
            },
            "is_demo": full.get("is_demo", False),
            "demo_banner": full.get("demo_banner")
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Flood monitoring analysis failed: {str(exc)}")
