import asyncio
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings

# In-memory geocode cache
_geocode_cache: Dict[str, Any] = {}

HEADERS = {
    "User-Agent": "ChetakAI-Flood-Intelligence/1.0 (contact: admin@chetakai.ai)"
}


async def search_locations(query: str) -> List[Dict[str, Any]]:
    """
    Search for locations matching the query using Open-Meteo Geocoding
    with automatic fallback to OpenStreetMap Nominatim.
    """
    query = query.strip()
    if len(query) < 2:
        return []

    cache_key = f"search_{query.lower()}"
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    results = []

    # 1. Attempt Open-Meteo Geocoding API
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {
            "name": query,
            "count": 6,
            "language": "en",
            "countryCode": "IN"
        }
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url, params=params, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("results", [])
                if items:
                    for item in items:
                        name_parts = [item.get("name"), item.get("admin1"), item.get("country")]
                        display_name = ", ".join([p for p in name_parts if p])
                        results.append({
                            "placeId": str(item.get("id")),
                            "name": display_name,
                            "latitude": float(item["latitude"]),
                            "longitude": float(item["longitude"]),
                            "type": item.get("feature_code"),
                            "address": {
                                "city": item.get("name"),
                                "district": item.get("admin2") or item.get("admin1"),
                                "state": item.get("admin1"),
                                "country": item.get("country")
                            }
                        })
                    _geocode_cache[cache_key] = results
                    return results
    except Exception:
        pass

    # 2. Fallback to OpenStreetMap Nominatim
    try:
        url = f"{settings.NOMINATIM_URL}/search"
        params = {
            "q": query,
            "format": "json",
            "addressdetails": 1,
            "countrycodes": "in",
            "limit": 6
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params, headers=HEADERS)
            if resp.status_code == 200:
                items = resp.json()
                for item in items:
                    addr = item.get("address", {})
                    results.append({
                        "placeId": str(item.get("place_id")),
                        "name": item.get("display_name"),
                        "latitude": float(item["lat"]),
                        "longitude": float(item["lon"]),
                        "type": item.get("type"),
                        "address": {
                            "city": addr.get("city") or addr.get("town") or addr.get("village"),
                            "district": addr.get("state_district") or addr.get("county"),
                            "state": addr.get("state"),
                            "country": addr.get("country")
                        }
                    })
                _geocode_cache[cache_key] = results
                return results
    except Exception:
        pass

    return results


async def reverse_geocode(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Reverse geocodes coordinates into administrative area, district, and city.
    """
    cache_key = f"rev_{round(latitude, 4)}_{round(longitude, 4)}"
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    try:
        url = f"{settings.NOMINATIM_URL}/reverse"
        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "zoom": 10
        }
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url, params=params, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                addr = data.get("address", {})
                res = {
                    "displayName": data.get("display_name"),
                    "reverseGeocode": {
                        "city": addr.get("city") or addr.get("town") or addr.get("village"),
                        "district": addr.get("state_district") or addr.get("county"),
                        "state": addr.get("state"),
                        "country": addr.get("country")
                    }
                }
                _geocode_cache[cache_key] = res
                return res
    except Exception:
        pass

    fallback = {
        "displayName": f"Location ({round(latitude, 4)}°N, {round(longitude, 4)}°E)",
        "reverseGeocode": {
            "city": None,
            "district": None,
            "state": None,
            "country": "India"
        }
    }
    _geocode_cache[cache_key] = fallback
    return fallback
