import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.config import settings
from app.utils.geo import haversine_distance_km

logger = logging.getLogger("cwc_service")

# ---------------------------------------------------------
# Station Metadata Registry
# Curated based on HydroSwift / CWC FFS station catalogues
# ---------------------------------------------------------
CWC_STATION_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "CWC_006-MGD3VNS",
        "code": "006-MGD3VNS",
        "name": "Varanasi",
        "river": "Ganga",
        "basin": "Ganga",
        "state": "Uttar Pradesh",
        "district": "Varanasi",
        "latitude": 25.323611,
        "longitude": 83.037500,
        "warning_level_m": 70.262,
        "danger_level_m": 71.262,
        "hfl_m": 73.901,
        "hfl_date": "1978-09-09"
    },
    {
        "id": "CWC_007-MGD4PTN",
        "code": "007-MGD4PTN",
        "name": "Khagaria",
        "river": "Burhi Gandak",
        "basin": "Ganga",
        "state": "Bihar",
        "district": "Khagaria",
        "latitude": 25.501111,
        "longitude": 86.480556,
        "warning_level_m": 36.58,
        "danger_level_m": 37.58,
        "hfl_m": 39.46,
        "hfl_date": "1987-08-14"
    },
    {
        "id": "CWC_027-MGD5PTN",
        "code": "027-MGD5PTN",
        "name": "Maner",
        "river": "Sone",
        "basin": "Ganga",
        "state": "Bihar",
        "district": "Patna",
        "latitude": 25.650000,
        "longitude": 84.828611,
        "warning_level_m": 52.00,
        "danger_level_m": 53.00,
        "hfl_m": 54.55,
        "hfl_date": "1975-08-25"
    },
    {
        "id": "CWC_001-MGD4PTN",
        "code": "001-MGD4PTN",
        "name": "Patna (Dighaghat)",
        "river": "Ganga",
        "basin": "Ganga",
        "state": "Bihar",
        "district": "Patna",
        "latitude": 25.594100,
        "longitude": 85.137600,
        "warning_level_m": 50.00,
        "danger_level_m": 50.52,
        "hfl_m": 52.52,
        "hfl_date": "1994-08-20"
    },
    {
        "id": "CWC_010-BGP1GHY",
        "code": "010-BGP1GHY",
        "name": "Guwahati",
        "river": "Brahmaputra",
        "basin": "Brahmaputra",
        "state": "Assam",
        "district": "Kamrup Metropolitan",
        "latitude": 26.144500,
        "longitude": 91.736200,
        "warning_level_m": 49.68,
        "danger_level_m": 50.68,
        "hfl_m": 51.46,
        "hfl_date": "2004-07-24"
    },
    {
        "id": "CWC_015-GPG1BIH",
        "code": "015-GPG1BIH",
        "name": "Gopalganj",
        "river": "Gandak",
        "basin": "Ganga",
        "state": "Bihar",
        "district": "Gopalganj",
        "latitude": 26.470000,
        "longitude": 84.440000,
        "warning_level_m": 64.80,
        "danger_level_m": 65.80,
        "hfl_m": 67.25,
        "hfl_date": "2001-08-12"
    },
    {
        "id": "CWC_003-YMN1DEL",
        "code": "003-YMN1DEL",
        "name": "Delhi Railway Bridge",
        "river": "Yamuna",
        "basin": "Ganga",
        "state": "Delhi",
        "district": "Central Delhi",
        "latitude": 28.663300,
        "longitude": 77.247800,
        "warning_level_m": 204.50,
        "danger_level_m": 205.33,
        "hfl_m": 208.66,
        "hfl_date": "2023-07-13"
    },
    {
        "id": "CWC_040-CDJAPR",
        "code": "040-CDJAPR",
        "name": "Perur",
        "river": "Godavari",
        "basin": "Godavari",
        "state": "Andhra Pradesh",
        "district": "East Godavari",
        "latitude": 18.633300,
        "longitude": 80.366700,
        "warning_level_m": 63.50,
        "danger_level_m": 65.00,
        "hfl_m": 67.80,
        "hfl_date": "2006-08-08"
    }
]

# In-memory cache for live observations (TTL: 5 minutes)
_observation_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300
STALE_THRESHOLD_HOURS = 24


def get_cwc_stations() -> List[Dict[str, Any]]:
    """Return all registered CWC stations with official surveyed thresholds."""
    return CWC_STATION_REGISTRY


def find_nearest_station(
    latitude: float,
    longitude: float,
    max_distance_km: float = 150.0
) -> Tuple[Optional[Dict[str, Any]], Optional[float]]:
    """
    Find nearest CWC gauge station using the Haversine formula.
    Returns (station_dict, distance_km) or (None, None) if none within max_distance_km.
    """
    nearest_station = None
    min_distance = float("inf")

    for station in CWC_STATION_REGISTRY:
        dist = haversine_distance_km(
            latitude, longitude, station["latitude"], station["longitude"]
        )
        if dist < min_distance:
            min_distance = dist
            nearest_station = station

    if nearest_station is not None and min_distance <= max_distance_km:
        return nearest_station, min_distance

    return None, None


def classify_cwc_stage(
    stage: Optional[float],
    warning_level: Optional[float],
    danger_level: Optional[float],
    hfl: Optional[float]
) -> str:
    """
    Classify observed river stage against official surveyed thresholds.
    """
    if stage is None or not isinstance(stage, (int, float)):
        return "UNAVAILABLE"

    if hfl is not None and stage >= hfl:
        return "ABOVE_EXTREME"
    if danger_level is not None and stage >= danger_level:
        return "ABOVE_DANGER"
    if warning_level is not None and stage >= warning_level:
        return "ABOVE_WARNING"

    return "BELOW_WARNING"


async def fetch_station_observation(station_id: str) -> Dict[str, Any]:
    """
    Retrieve live observation for a specific CWC gauge from NWIC / CWC FFS API.
    Handles network timeouts, HTTP errors, stale detections, and unreachability gracefully.
    NEVER returns fabricated water levels.
    """
    now = datetime.now(timezone.utc)
    cached_entry = _observation_cache.get(station_id)

    if cached_entry:
        age_seconds = (now - cached_entry["cached_at"]).total_seconds()
        if age_seconds < CACHE_TTL_SECONDS:
            return cached_entry["data"]

    # Match station metadata
    station_meta = next((s for s in CWC_STATION_REGISTRY if s["id"] == station_id or s.get("code") == station_id), None)
    if not station_meta:
        return {
            "status": "UNAVAILABLE",
            "water_level_m": None,
            "timestamp": None,
            "reason": f"Station {station_id} not registered"
        }

    # Attempt query to National Water Informatics Centre (NWIC) Datastore Search
    headers = {
        "User-Agent": "ChetakAI-Flood-Intelligence/1.0 (India-CWC-Integration; admin@chetakai.ai)",
        "Accept": "application/json"
    }

    water_level: Optional[float] = None
    observation_time: Optional[str] = None
    telemetry_status = "UNAVAILABLE"
    failure_reason = None

    try:
        url = settings.CWC_API_URL
        params = {
            "resource_id": settings.CWC_RESOURCE_ID,
            "q": station_meta.get("code") or station_meta["name"],
            "limit": 5
        }

        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                records = data.get("result", {}).get("records", [])
                if records:
                    latest = records[0]
                    val = latest.get("water_level") or latest.get("stage_m") or latest.get("WL")
                    if val is not None:
                        water_level = float(val)
                        observation_time = latest.get("timestamp") or latest.get("date_time") or now.isoformat()
                        telemetry_status = "AVAILABLE"
            else:
                failure_reason = f"NWIC upstream returned HTTP {resp.status_code}"
    except httpx.TimeoutException:
        failure_reason = "CWC / NWIC telemetry API connection timeout"
        telemetry_status = "UNAVAILABLE"
    except Exception as exc:
        failure_reason = f"CWC API query error: {str(exc)}"
        telemetry_status = "ERROR"

    # If live telemetry is unreachable, check HydroSwift / CWC FFS layer-station API
    if water_level is None and telemetry_status != "ERROR":
        try:
            ffs_url = f"{settings.CWC_LAYER_STATION_BASE}/{station_meta.get('code')}"
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(ffs_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict):
                        val = data.get("waterLevel") or data.get("currentStage")
                        if val is not None:
                            water_level = float(val)
                            observation_time = data.get("readingTime") or now.isoformat()
                            telemetry_status = "AVAILABLE"
        except Exception:
            pass  # Expected when network access to internal CWC FFS gateway is restricted

    # Check for stale observation (>24 hours old)
    if water_level is not None and observation_time:
        try:
            obs_dt = datetime.fromisoformat(observation_time.replace("Z", "+00:00"))
            if (now - obs_dt).total_seconds() > STALE_THRESHOLD_HOURS * 3600:
                telemetry_status = "STALE"
                failure_reason = "Telemetry older than 24 hours (stale observation)"
        except Exception:
            pass

    if water_level is None and not failure_reason:
        failure_reason = "No real-time telemetry published for this gauge"
        telemetry_status = "UNAVAILABLE"

    result = {
        "status": telemetry_status,
        "water_level_m": water_level,
        "timestamp": observation_time,
        "reason": failure_reason
    }

    _observation_cache[station_id] = {
        "cached_at": now,
        "data": result
    }

    return result


async def get_cwc_status(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Canonical function to obtain normalized CWC ground truth for given coordinates.
    Returns the exact normalized schema specified in Section 8 of the requirements.
    """
    nearest_station, distance_km = find_nearest_station(latitude, longitude)

    if not nearest_station:
        return {
            "source": "CWC",
            "status": "UNAVAILABLE",
            "station": None,
            "observation": {
                "water_level_m": None,
                "timestamp": None
            },
            "thresholds": {
                "warning_level_m": None,
                "danger_level_m": None,
                "hfl_m": None
            },
            "condition": "UNAVAILABLE",
            "reason": "No registered CWC gauge found within 150 km radius",
            "data_source": "NWIC / CWC River Water Level (Telemetry - Hourly)"
        }

    # Fetch live telemetry for matched station
    obs = await fetch_station_observation(nearest_station["id"])
    water_level = obs.get("water_level_m")
    status = obs.get("status", "UNAVAILABLE")
    reason = obs.get("reason")
    timestamp = obs.get("timestamp")

    condition = classify_cwc_stage(
        water_level,
        nearest_station.get("warning_level_m"),
        nearest_station.get("danger_level_m"),
        nearest_station.get("hfl_m")
    )

    return {
        "source": "CWC",
        "status": status,
        "station": {
            "id": nearest_station["id"],
            "code": nearest_station.get("code"),
            "name": nearest_station["name"],
            "river": nearest_station["river"],
            "basin": nearest_station.get("basin"),
            "state": nearest_station.get("state"),
            "latitude": nearest_station["latitude"],
            "longitude": nearest_station["longitude"],
            "distance_km": distance_km
        },
        "observation": {
            "water_level_m": water_level,
            "timestamp": timestamp
        },
        "thresholds": {
            "warning_level_m": nearest_station.get("warning_level_m"),
            "danger_level_m": nearest_station.get("danger_level_m"),
            "hfl_m": nearest_station.get("hfl_m")
        },
        "condition": condition,
        "reason": reason,
        "data_source": "NWIC / CWC River Water Level (Telemetry - Hourly)"
    }
