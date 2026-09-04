from typing import Any, Dict, Optional


def evaluate_environmental_fallback(
    live: Dict[str, Any],
    catchment: Optional[Dict[str, Any]] = None,
    nearest_station_distance_km: Optional[float] = None
) -> Dict[str, Any]:
    """
    Evaluates independent physical environmental hazard when CWC ground-truth
    gauge telemetry is UNAVAILABLE, STALE, or in an ERROR state.

    CRITICAL HONESTY RULES:
    1. NEVER label this as CWC data.
    2. Strictly source-tagged as FALLBACK_ENVIRONMENTAL.
    3. Evaluates real physical inputs: rainfall, NWP forecast, soil moisture, and river proximity.
    """
    if catchment is None:
        catchment = {}

    rainfall = live.get("rainfall", {})
    flood = live.get("flood", {})
    current = live.get("current", {})

    r24 = float(rainfall.get("h24") or 0.0)
    r72 = float(rainfall.get("h72") or 0.0)
    f72 = float(rainfall.get("forecast72h") or 0.0)
    soil_m = float(current.get("rootZoneSoilMoisture") or 0.3)
    d_ratio = float(flood.get("ratio") or 1.0)

    # Determine river proximity category
    dist = nearest_station_distance_km if nearest_station_distance_km is not None else 10.0
    if dist <= 5.0:
        river_prox = "NEAR"
    elif dist <= 15.0:
        river_prox = "MODERATE"
    else:
        river_prox = "FAR"

    # Multi-factor physical risk scoring (0-100)
    score = 0

    # 1. 24h & 72h Cumulative Precipitation
    if r24 >= 75.0 or r72 >= 150.0:
        score += 40
    elif r24 >= 40.0 or r72 >= 80.0:
        score += 25
    elif r24 >= 15.0 or r72 >= 35.0:
        score += 12

    # 2. 72h Numerical Weather Prediction Forecast
    if f72 >= 100.0:
        score += 30
    elif f72 >= 50.0:
        score += 20
    elif f72 >= 20.0:
        score += 10

    # 3. Soil Saturation
    if soil_m >= 0.42:
        score += 15
    elif soil_m >= 0.35:
        score += 8

    # 4. GloFAS Runoff / Discharge Ratio
    if d_ratio >= 2.0:
        score += 20
    elif d_ratio >= 1.4:
        score += 12

    # 5. Proximity to drainage channel / major river
    if river_prox == "NEAR":
        score += 10
    elif river_prox == "MODERATE":
        score += 5

    # Determine risk category
    if score >= 50:
        risk = "HIGH"
        summary = "Elevated environmental risk: significant cumulative rainfall and river proximity."
    elif score >= 25:
        risk = "MEDIUM"
        summary = "Moderate environmental risk: moderate precipitation loading observed."
    else:
        risk = "LOW"
        summary = "Low environmental risk: precipitation and soil saturation within baseline limits."

    return {
        "source": "FALLBACK_ENVIRONMENTAL",
        "status": "AVAILABLE",
        "risk": risk,
        "score": score,
        "rainfall_mm": r24,
        "rainfall_72h_mm": r72,
        "forecast_rainfall_mm": f72,
        "river_proximity": river_prox,
        "soil_moisture": round(soil_m, 3),
        "discharge_ratio": round(d_ratio, 2),
        "summary": summary
    }
