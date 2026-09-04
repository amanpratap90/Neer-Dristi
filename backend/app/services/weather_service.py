import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings

# In-memory weather cache (TTL: 90 seconds)
_weather_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 90


def _sum_window(hourly: Dict[str, Any], field: str, hours_back: int, hours_ahead: int = 0) -> float:
    """Calculates rainfall summation over a sliding temporal window."""
    times = hourly.get("time", [])
    values = hourly.get(field, []) or hourly.get("precipitation", [])
    if not times or not values:
        return 0.0

    now_ms = time.time() * 1000.0
    start_ms = now_ms - hours_back * 3600.0 * 1000.0
    end_ms = now_ms + hours_ahead * 3600.0 * 1000.0

    total = 0.0
    for t_str, val in zip(times, values):
        try:
            # Parse ISO timestamp to epoch ms
            dt = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
            t_ms = dt.timestamp() * 1000.0
            if start_ms <= t_ms <= end_ms and val is not None:
                total += float(val)
        except Exception:
            continue

    return round(total, 2)


async def get_live_intelligence_inputs(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Retrieves real-time physical inputs:
    - High-resolution precipitation & soil moisture from Open-Meteo Forecast
    - DEM terrain elevation from Open-Meteo Elevation
    - Modelled river discharge from GloFAS Flood API
    """
    cache_key = f"{round(latitude, 4)}_{round(longitude, 4)}"
    now_ts = time.time()

    if cache_key in _weather_cache:
        entry = _weather_cache[cache_key]
        if now_ts - entry["timestamp"] < CACHE_TTL_SECONDS:
            return entry["data"]

    forecast_params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "surface_pressure",
            "wind_speed_10m",
            "precipitation"
        ],
        "hourly": [
            "precipitation",
            "temperature_2m",
            "relative_humidity_2m",
            "surface_pressure",
            "wind_speed_10m",
            "soil_moisture_0_to_1cm",
            "soil_moisture_1_to_3cm",
            "soil_moisture_3_to_9cm",
            "soil_moisture_9_to_27cm",
            "et0_fao_evapotranspiration"
        ],
        "daily": [
            "precipitation_sum",
            "precipitation_hours",
            "wind_speed_10m_max"
        ],
        "timezone": "auto"
    }

    elevation_params = {
        "latitude": latitude,
        "longitude": longitude
    }

    flood_params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": [
            "river_discharge",
            "river_discharge_mean",
            "river_discharge_median",
            "river_discharge_max",
            "river_discharge_min"
        ],
        "forecast_days": 7
    }

    async with httpx.AsyncClient(timeout=8.0) as client:
        # Concurrent async requests
        forecast_task = client.get(settings.OPEN_METEO_FORECAST_URL, params=forecast_params)
        elevation_task = client.get(settings.OPEN_METEO_ELEVATION_URL, params=elevation_params)
        flood_task = client.get(settings.OPEN_METEO_FLOOD_URL, params=flood_params)

        results = await asyncio.gather(forecast_task, elevation_task, flood_task, return_exceptions=True)

    forecast_res = results[0] if not isinstance(results[0], Exception) and results[0].status_code == 200 else None
    elevation_res = results[1] if not isinstance(results[1], Exception) and results[1].status_code == 200 else None
    flood_res = results[2] if not isinstance(results[2], Exception) and results[2].status_code == 200 else None

    forecast_json = forecast_res.json() if forecast_res else {}
    elevation_json = elevation_res.json() if elevation_res else {}
    flood_json = flood_res.json() if flood_res else {}

    hourly = forecast_json.get("hourly", {})
    current = forecast_json.get("current", {})
    daily = forecast_json.get("daily", {})

    # Compute sliding rainfall windows
    r1h = _sum_window(hourly, "precipitation", 1)
    r3h = _sum_window(hourly, "precipitation", 3)
    r6h = _sum_window(hourly, "precipitation", 6)
    r12h = _sum_window(hourly, "precipitation", 12)
    r24h = _sum_window(hourly, "precipitation", 24)
    r72h = _sum_window(hourly, "precipitation", 72)
    evap72h = _sum_window(hourly, "et0_fao_evapotranspiration", 72)

    # 24h & 72h Forecast sums
    f24h = _sum_window(hourly, "precipitation", 0, 24)
    f72h = _sum_window(hourly, "precipitation", 0, 72)

    # Antecedent Precipitation Index (API 7d)
    r_day1 = _sum_window(hourly, "precipitation", 24)
    r_day2 = _sum_window(hourly, "precipitation", 48) - r_day1
    r_day3 = _sum_window(hourly, "precipitation", 72) - _sum_window(hourly, "precipitation", 48)
    api = round(r_day1 + 0.85 * max(0.0, r_day2) + 0.70 * max(0.0, r_day3), 2)

    # Soil moisture series (extract latest available reading)
    sm0_1 = hourly.get("soil_moisture_0_to_1cm", [0.28])[-1] if hourly.get("soil_moisture_0_to_1cm") else 0.28
    sm1_3 = hourly.get("soil_moisture_1_to_3cm", [0.30])[-1] if hourly.get("soil_moisture_1_to_3cm") else 0.30
    sm3_9 = hourly.get("soil_moisture_3_to_9cm", [0.32])[-1] if hourly.get("soil_moisture_3_to_9cm") else 0.32
    sm9_27 = hourly.get("soil_moisture_9_to_27cm", [0.35])[-1] if hourly.get("soil_moisture_9_to_27cm") else 0.35
    root_zone = round((float(sm0_1 or 0) * 0.1 + float(sm1_3 or 0) * 0.2 + float(sm3_9 or 0) * 0.3 + float(sm9_27 or 0) * 0.4), 3)

    # DEM Elevation
    elevation_val = elevation_json.get("elevation", [None])
    elevation_m = float(elevation_val[0]) if isinstance(elevation_val, list) and elevation_val and elevation_val[0] is not None else 65.0

    # GloFAS discharge
    flood_daily = flood_json.get("daily", {})
    discharges = [float(v) for v in flood_daily.get("river_discharge", []) if v is not None]
    means = [float(v) for v in flood_daily.get("river_discharge_mean", []) if v is not None]

    discharge_now = discharges[0] if discharges else None
    discharge_mean = means[0] if means else None

    data = {
        "rainfall": {
            "h1": r1h,
            "h3": r3h,
            "h6": r6h,
            "h12": r12h,
            "h24": r24h,
            "h72": r72h,
            "forecast1h": round(f24h / 24.0, 2),
            "forecast3h": round((f24h / 24.0) * 3, 2),
            "forecast6h": round((f24h / 24.0) * 6, 2),
            "forecast12h": round((f24h / 24.0) * 12, 2),
            "forecast24h": f24h,
            "forecast72h": f72h,
            "antecedentPrecipitationIndex": api,
            "evapotranspiration72h": evap72h
        },
        "current": {
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "pressure": current.get("surface_pressure"),
            "wind": current.get("wind_speed_10m"),
            "soilMoisture0_1": sm0_1,
            "soilMoisture1_3": sm1_3,
            "soilMoisture3_9": sm3_9,
            "soilMoisture9_27": sm9_27,
            "rootZoneSoilMoisture": root_zone
        },
        "daily": daily,
        "elevation": elevation_m,
        "flood": {
            "dischargeNow": discharge_now,
            "dischargeMean": discharge_mean,
            "ratio": round(discharge_now / discharge_mean, 2) if (discharge_now is not None and discharge_mean and discharge_mean > 0) else None
        }
    }

    _weather_cache[cache_key] = {
        "timestamp": now_ts,
        "data": data
    }

    return data
