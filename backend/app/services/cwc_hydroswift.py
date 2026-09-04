"""
CWC Water Level Service via HydroSwift.

Uses HydroSwift as the CWC data-access layer for:
  1. Station discovery (1641+ CWC flood-forecast stations)
  2. Water-level retrieval from CWC FFS (India-WRIS)
  3. Classification against station-specific thresholds

Architecture:
  React → Node.js → Python FastAPI → HydroSwift → CWC FFS / India-WRIS

NEVER fabricates, estimates, or hardcodes CWC observations.
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.utils.geo import haversine_distance_km

logger = logging.getLogger("cwc_hydroswift")

# ---------------------------------------------------------------------------
# Module-level station cache (loaded once from HydroSwift packaged metadata)
# ---------------------------------------------------------------------------
_stations_df: Optional[pd.DataFrame] = None
_stations_loaded: bool = False

# Observation cache (TTL-based)
_observation_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes
STALE_THRESHOLD_HOURS = 24
MAX_SEARCH_RADIUS_KM = 150.0


def _load_stations() -> pd.DataFrame:
    """
    Load CWC station metadata from HydroSwift's packaged catalogue.
    This reads from the bundled cwc_meta.csv — no network call required.
    Returns a DataFrame with 1641+ stations.
    """
    global _stations_df, _stations_loaded

    if _stations_loaded and _stations_df is not None:
        return _stations_df

    try:
        import hydroswift
        df = hydroswift.cwc.stations()
        # Ensure numeric types for lat/lon/thresholds
        for col in ["lat", "lon", "warning_level", "danger_level", "hfl", "rl_zero"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        _stations_df = df
        _stations_loaded = True
        logger.info(
            f"[CWC/HYDROSWIFT] Loaded {len(df)} CWC stations from HydroSwift metadata."
        )
        return df
    except Exception as exc:
        logger.error(f"[CWC/HYDROSWIFT] Failed to load stations: {exc}")
        raise RuntimeError(f"HydroSwift station metadata unavailable: {exc}")


def get_cwc_stations() -> List[Dict[str, Any]]:
    """Return all CWC stations as a list of dicts."""
    df = _load_stations()
    return df.to_dict(orient="records")


def find_nearest_cwc_station(
    latitude: float,
    longitude: float,
    max_distance_km: float = MAX_SEARCH_RADIUS_KM,
) -> Tuple[Optional[Dict[str, Any]], Optional[float]]:
    """
    Find the nearest CWC gauge station using Haversine distance.

    Returns (station_dict, distance_km) or (None, None) if none within radius.
    Uses the full HydroSwift station catalogue (1641+ stations).
    """
    df = _load_stations()

    # Filter out rows with missing lat/lon
    valid = df.dropna(subset=["lat", "lon"]).copy()
    if valid.empty:
        logger.warning("[CWC/HYDROSWIFT] No stations with valid coordinates.")
        return None, None

    # Vectorized Haversine computation for speed
    lat1 = math.radians(latitude)
    lon1 = math.radians(longitude)
    lat2 = valid["lat"].apply(math.radians)
    lon2 = valid["lon"].apply(math.radians)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        (dlat / 2).apply(math.sin) ** 2
        + math.cos(lat1) * lat2.apply(math.cos) * (dlon / 2).apply(math.sin) ** 2
    )
    c = 2 * a.apply(lambda x: math.atan2(math.sqrt(x), math.sqrt(1 - x)))
    distances = 6371.0 * c

    min_idx = distances.idxmin()
    min_dist = round(distances[min_idx], 2)

    if min_dist > max_distance_km:
        logger.info(
            f"[CWC/HYDROSWIFT] Nearest station is {min_dist} km away (beyond {max_distance_km} km radius)."
        )
        return None, None

    station_row = valid.loc[min_idx]
    station_dict = station_row.to_dict()

    # Convert numpy types to native Python for JSON serialization
    for key, val in station_dict.items():
        if hasattr(val, "item"):
            station_dict[key] = val.item()

    logger.info(
        f"[CWC/HYDROSWIFT] Nearest station: {station_dict.get('name')} "
        f"({station_dict.get('code')}) at {min_dist} km."
    )

    return station_dict, min_dist


def get_cwc_water_level(
    station_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Fetch CWC water-level time series via HydroSwift's internal CWC FFS API client.

    Uses the same CWC FFS endpoint as HydroSwift:
      https://ffs.india-water.gov.in/iam/api/new-entry-data/specification/sorted

    Returns a DataFrame with columns [station_code, time, water_level] or None.
    """
    try:
        # Import the internal fetch function from HydroSwift's CWC module
        from swift_app.cwc import fetch_station_data

        logger.info(
            f"[CWC/HYDROSWIFT] Fetching water level for {station_code} "
            f"from {start_date} to {end_date}..."
        )

        df = fetch_station_data(
            code=station_code,
            start_date=start_date,
            end_date=end_date,
            retries=2,
        )

        if df is not None and not df.empty:
            logger.info(
                f"[CWC/HYDROSWIFT] Got {len(df)} water level records for {station_code}."
            )
            return df
        else:
            logger.info(
                f"[CWC/HYDROSWIFT] No water level data returned for {station_code}."
            )
            return None

    except Exception as exc:
        logger.error(
            f"[CWC/HYDROSWIFT] Exception fetching water level for {station_code}: "
            f"{type(exc).__name__}: {exc}"
        )
        return None


def get_latest_cwc_observation(station_code: str) -> Dict[str, Any]:
    """
    Get the latest CWC water-level observation for a station.

    Queries the last 7 days of data via HydroSwift's CWC FFS API,
    then extracts the most recent valid reading.

    Returns a dict with keys:
      - status: AVAILABLE | UNAVAILABLE | STALE
      - water_level_m: float or None
      - timestamp: ISO string or None
      - reason: failure explanation or None
    """
    now = datetime.now(timezone.utc)

    # Check cache first
    cached = _observation_cache.get(station_code)
    if cached:
        age = (now - cached["cached_at"]).total_seconds()
        if age < CACHE_TTL_SECONDS:
            logger.info(
                f"[CWC/HYDROSWIFT] Cache hit for {station_code} (age={age:.0f}s)."
            )
            return cached["data"]

    # Query last 7 days to maximize chance of getting a reading
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    logger.info(
        f"[CWC/HYDROSWIFT] get_latest_cwc_observation: "
        f"station={station_code}, range={start_date} to {end_date}"
    )

    try:
        df = get_cwc_water_level(station_code, start_date, end_date)
    except Exception as exc:
        result = {
            "status": "UNAVAILABLE",
            "water_level_m": None,
            "timestamp": None,
            "reason": f"HydroSwift exception: {type(exc).__name__}: {exc}",
        }
        _observation_cache[station_code] = {"cached_at": now, "data": result}
        return result

    if df is None or df.empty:
        result = {
            "status": "UNAVAILABLE",
            "water_level_m": None,
            "timestamp": None,
            "reason": "No water level data available from CWC FFS for this station",
        }
        _observation_cache[station_code] = {"cached_at": now, "data": result}
        return result

    # Get the latest valid reading (last row after sorting by time)
    try:
        df = df.sort_values("time", ascending=True)
        latest = df.iloc[-1]

        water_level = float(latest["water_level"])
        obs_time = latest["time"]

        # Convert to ISO string
        if isinstance(obs_time, pd.Timestamp):
            obs_time_str = obs_time.isoformat()
            obs_dt = obs_time.to_pydatetime()
            if obs_dt.tzinfo is None:
                # Assume IST (UTC+5:30)
                from datetime import timezone as tz
                obs_dt = obs_dt.replace(tzinfo=tz(timedelta(hours=5, minutes=30)))
        else:
            obs_time_str = str(obs_time)
            obs_dt = now  # Can't parse, assume recent

        # Check staleness
        age_hours = (now - obs_dt).total_seconds() / 3600.0
        if age_hours > STALE_THRESHOLD_HOURS:
            status = "STALE"
            reason = f"Telemetry is {age_hours:.1f} hours old (stale threshold: {STALE_THRESHOLD_HOURS}h)"
        else:
            status = "AVAILABLE"
            reason = None

        logger.info(
            f"[CWC/HYDROSWIFT] Latest observation for {station_code}: "
            f"water_level={water_level}m, time={obs_time_str}, status={status}, "
            f"total_records={len(df)}"
        )

        result = {
            "status": status,
            "water_level_m": water_level,
            "timestamp": obs_time_str,
            "reason": reason,
        }

    except Exception as exc:
        logger.error(
            f"[CWC/HYDROSWIFT] Error parsing water level data: "
            f"{type(exc).__name__}: {exc}"
        )
        result = {
            "status": "UNAVAILABLE",
            "water_level_m": None,
            "timestamp": None,
            "reason": f"Data parsing error: {type(exc).__name__}: {exc}",
        }

    _observation_cache[station_code] = {"cached_at": now, "data": result}
    return result


def classify_cwc_stage(
    stage: Optional[float],
    warning_level: Optional[float],
    danger_level: Optional[float],
    extreme_level: Optional[float],
) -> str:
    """
    Classify observed river stage against station-specific thresholds.

    Returns: NORMAL | ELEVATED | HIGH | CRITICAL | UNAVAILABLE
    """
    if stage is None or not isinstance(stage, (int, float)) or not math.isfinite(stage):
        return "UNAVAILABLE"

    if extreme_level is not None and math.isfinite(extreme_level) and stage >= extreme_level:
        return "CRITICAL"
    if danger_level is not None and math.isfinite(danger_level) and stage >= danger_level:
        return "HIGH"
    if warning_level is not None and math.isfinite(warning_level) and stage >= warning_level:
        return "ELEVATED"

    return "NORMAL"


async def get_cwc_status(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Canonical function: obtain normalized CWC ground truth for given coordinates.

    Uses HydroSwift for:
      1. Station discovery (1641+ stations via Haversine search)
      2. Water-level retrieval (CWC FFS API via HydroSwift internals)
      3. Stage classification (station-specific thresholds)

    Returns one of three states:
      A. STATION_NOT_FOUND — No CWC station within search radius
      B. STATION_FOUND_TELEMETRY_UNAVAILABLE — Station matched, no live data
      C. OBSERVED — Valid water-level observation retrieved

    NEVER fabricates or estimates CWC data.
    """
    logger.info(
        f"[CWC/HYDROSWIFT DEBUG] Input: lat={latitude}, lon={longitude}"
    )

    # --- Step 1: Station discovery ---
    try:
        station, distance_km = find_nearest_cwc_station(latitude, longitude)
    except Exception as exc:
        logger.error(f"[CWC/HYDROSWIFT] Station search failed: {exc}")
        return {
            "source": "CWC",
            "status": "STATION_NOT_FOUND",
            "station": None,
            "observation": {"water_level_m": None, "timestamp": None},
            "thresholds": {
                "warning_level_m": None,
                "danger_level_m": None,
                "hfl_m": None,
            },
            "condition": "UNAVAILABLE",
            "reason": f"Station search error: {exc}",
            "data_source": "HydroSwift → CWC",
        }

    station_count = len(_stations_df) if _stations_df is not None else 0
    logger.info(f"[CWC/HYDROSWIFT DEBUG] Station count={station_count}")

    # STATE A: No station found
    if station is None:
        logger.info(
            f"[CWC/HYDROSWIFT DEBUG] No CWC station within "
            f"{MAX_SEARCH_RADIUS_KM} km of ({latitude}, {longitude})."
        )
        return {
            "source": "CWC",
            "status": "STATION_NOT_FOUND",
            "station": None,
            "observation": {"water_level_m": None, "timestamp": None},
            "thresholds": {
                "warning_level_m": None,
                "danger_level_m": None,
                "hfl_m": None,
            },
            "condition": "UNAVAILABLE",
            "reason": f"No CWC gauge found within {MAX_SEARCH_RADIUS_KM} km radius",
            "data_source": "HydroSwift → CWC",
        }

    station_code = station.get("code", "")
    station_name = station.get("name", "Unknown")
    river = station.get("river", "Unknown")
    warning_level = station.get("warning_level")
    danger_level = station.get("danger_level")
    hfl = station.get("hfl")
    station_lat = station.get("lat")
    station_lon = station.get("lon")

    logger.info(
        f"[CWC/HYDROSWIFT DEBUG] Nearest station={station_name}, "
        f"Station ID={station_code}, Distance={distance_km} km"
    )

    # --- Step 2: Fetch live water-level data ---
    obs = get_latest_cwc_observation(station_code)
    water_level = obs.get("water_level_m")
    obs_status = obs.get("status", "UNAVAILABLE")
    obs_time = obs.get("timestamp")
    obs_reason = obs.get("reason")

    logger.info(
        f"[CWC/HYDROSWIFT DEBUG] HydroSwift response: "
        f"telemetry_status={obs_status}, water_level={water_level}, "
        f"latest_timestamp={obs_time}"
    )

    # --- Step 3: Classify ---
    condition = classify_cwc_stage(water_level, warning_level, danger_level, hfl)

    # Determine overall status
    if obs_status == "AVAILABLE":
        overall_status = "OBSERVED"
        telemetry_status = "AVAILABLE"
    elif obs_status == "STALE":
        overall_status = "OBSERVED"
        telemetry_status = "STALE"
    else:
        # STATE B: Station found but telemetry unavailable
        overall_status = "STATION_FOUND_TELEMETRY_UNAVAILABLE"
        telemetry_status = "UNAVAILABLE"

    if obs_reason is None and overall_status == "STATION_FOUND_TELEMETRY_UNAVAILABLE":
        obs_reason = "CWC station matched — live telemetry unavailable"

    return {
        "source": "CWC",
        "status": overall_status,
        "station": {
            "id": station_code,
            "code": station_code,
            "name": station_name,
            "river": river,
            "basin": station.get("basin"),
            "state": station.get("state"),
            "district": station.get("district"),
            "latitude": station_lat,
            "longitude": station_lon,
            "distance_km": distance_km,
        },
        "observation": {
            "water_level_m": water_level,
            "timestamp": obs_time,
        },
        "thresholds": {
            "warning_level_m": warning_level,
            "danger_level_m": danger_level,
            "hfl_m": hfl,
        },
        "condition": condition,
        "telemetry_status": telemetry_status,
        "reason": obs_reason,
        "data_source": "HydroSwift → CWC",
    }


# Preload stations on module import
try:
    _load_stations()
except Exception as exc:
    logger.warning(f"[CWC/HYDROSWIFT] Deferred station loading: {exc}")
