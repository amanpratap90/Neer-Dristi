from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.services.geocoding_service import reverse_geocode, search_locations
from app.services.weather_service import get_live_intelligence_inputs

router = APIRouter(prefix="/api/v1/location", tags=["Location"])


class LocationCoordinatesRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


@router.get("/search")
async def search_location(
    q: Optional[str] = Query(None, description="Search query string"),
    query: Optional[str] = Query(None, description="Alternative query param")
) -> Dict[str, Any]:
    """
    Geocoding location search for autocomplete in React frontend.
    """
    search_term = (q or query or "").strip()
    if len(search_term) < 2:
        return {
            "status": "success",
            "query": search_term,
            "results": []
        }

    try:
        results = await search_locations(search_term)
        return {
            "status": "success",
            "query": search_term,
            "results": results
        }
    except Exception as exc:
        return {
            "status": "success",
            "query": search_term,
            "results": []
        }


@router.get("")
@router.get("/")
async def get_location_root(
    q: Optional[str] = Query(None),
    query: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Root location endpoint; redirects to search if query provided."""
    if q or query:
        return await search_location(q=q, query=query)
    return {
        "service": "ChetakAI Location Service",
        "status": "online"
    }


@router.post("")
@router.post("/")
async def post_location(payload: LocationCoordinatesRequest) -> Dict[str, Any]:
    """
    Processes location coordinates and returns reverse geocode metadata.
    """
    try:
        place_task = reverse_geocode(payload.latitude, payload.longitude)
        live_task = get_live_intelligence_inputs(payload.latitude, payload.longitude)

        place, live = await place_task, await live_task

        addr = place.get("reverseGeocode", {})
        rf = live.get("rainfall", {})

        return {
            "status": "success",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "location": {
                "latitude": payload.latitude,
                "longitude": payload.longitude,
                "administrative_area": addr.get("state"),
                "district": addr.get("district"),
                "city": addr.get("city"),
                "display_name": place.get("displayName")
            },
            "current_weather": live.get("current", {}),
            "forecast": {
                "rainfall": rf.get("forecast24h"),
                "nwp_spread": round(float(rf.get("forecast24h") or 0) * 0.15, 1),
                "confidence": 85.0,
                "daily_rainfall": live.get("daily", {})
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Location analysis failed: {str(exc)}")
