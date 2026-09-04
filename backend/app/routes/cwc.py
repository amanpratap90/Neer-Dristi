from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query

from app.services.cwc_service import get_cwc_stations, get_cwc_status

router = APIRouter(prefix="/api/cwc", tags=["CWC Telemetry"])


@router.get("/status")
async def get_cwc_telemetry_status(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180")
) -> Dict[str, Any]:
    """
    Independent CWC Ground Truth Telemetry Endpoint (Section 16).
    Returns real observed river stage and surveyed thresholds for nearest station.
    """
    try:
        return await get_cwc_status(latitude=lat, longitude=lon)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CWC telemetry lookup failed: {str(exc)}")


@router.get("/stations")
async def list_cwc_stations() -> List[Dict[str, Any]]:
    """
    Returns registered CWC hydrological stations across Indian river basins
    with surveyed warning, danger, and HFL thresholds.
    """
    return get_cwc_stations()
