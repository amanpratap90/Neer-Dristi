from typing import Any, Dict, List, Optional, Tuple


def map_ai_risk(probability_or_pct: float) -> str:
    """
    Standardized mapping of AI flood probability to risk category:
    0.00 - 0.30 (0 - 30%) = LOW
    0.30 - 0.60 (30 - 60%) = MEDIUM
    0.60 - 0.80 (60 - 80%) = HIGH
    0.80 - 1.00 (80 - 100%) = VERY HIGH
    """
    prob = probability_or_pct / 100.0 if probability_or_pct > 1.0 else probability_or_pct

    if prob >= 0.80:
        return "VERY HIGH"
    if prob >= 0.60:
        return "HIGH"
    if prob >= 0.30:
        return "MEDIUM"
    return "LOW"


def calculate_overall_risk(
    ai_signal: Dict[str, Any],
    cwc_signal: Optional[Dict[str, Any]] = None,
    fallback_signal: Optional[Dict[str, Any]] = None,
    historical_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    CWC-independent risk aggregation engine.

    The prediction pipeline is driven by independent environmental and hydrologic
    signals: AI model probability, rainfall, forecast, GloFAS discharge, soil
    moisture, terrain, and satellite observations when available.
    Historical flood recurrence is treated as memory evidence, not as a hard dependency.
    """
    ai_prob = float(ai_signal.get("probability", 0.0) or 0.0)
    ai_risk = ai_signal.get("risk") or map_ai_risk(ai_prob)

    fallback_signal = fallback_signal or {}
    fallback_status = fallback_signal.get("status", "UNAVAILABLE")
    fallback_risk = fallback_signal.get("risk", "LOW")

    historical_context = historical_context or {}
    historical_risk = float(historical_context.get("historical_flood_risk", 0.0) or 0.0)
    recurrence_factor = float(historical_context.get("recurrence_risk_factor", 0.0) or 0.0)

    signal_basis = ["AI_MODEL"]
    if fallback_signal.get("rainfall_mm") is not None or fallback_signal.get("rainfall_72h_mm") is not None:
        signal_basis.append("RAINFALL")
    if fallback_signal.get("forecast_rainfall_mm") is not None:
        signal_basis.append("FORECAST")
    if fallback_signal.get("discharge_ratio") is not None:
        signal_basis.append("GLOFAS")
    if fallback_signal.get("soil_moisture") is not None:
        signal_basis.append("SOIL_MOISTURE")
    if fallback_signal.get("terrain_risk") or fallback_signal.get("river_proximity"):
        signal_basis.append("TERRAIN")
    if fallback_signal.get("satellite_status") == "AVAILABLE":
        signal_basis.append("SATELLITE")
    if historical_context.get("available"):
        signal_basis.append("HISTORICAL_FLOOD_MEMORY")

    if len(signal_basis) == 1:
        signal_basis = ["AI_MODEL"]

    effective_prob = ai_prob + (historical_risk * 0.18) + (recurrence_factor * 0.10)
    effective_prob = min(effective_prob, 1.0)
    effective_risk = map_ai_risk(effective_prob)

    if effective_risk in ["HIGH", "VERY HIGH"] or effective_prob >= 0.65:
        status = "HIGH ALERT"
        explanation = "High flood probability from the AI model, reinforced by recurrent flood history and current environmental indicators."
        confidence = "HIGH CONFIDENCE" if len(signal_basis) >= 5 else "MEDIUM CONFIDENCE"
    elif effective_risk == "MEDIUM" or effective_prob >= 0.40:
        status = "WATCH" if fallback_risk in ["LOW", "MEDIUM"] else "HIGH ALERT"
        explanation = "Moderate flood probability with recurrent historical flood evidence requiring continued monitoring."
        confidence = "MEDIUM CONFIDENCE" if len(signal_basis) >= 4 else "LIMITED CONFIDENCE"
    else:
        if fallback_risk == "HIGH" or fallback_signal.get("score", 0) >= 50 or historical_risk >= 0.45:
            status = "WATCH"
            explanation = "Environmental and historical flood memory indicators remain elevated despite a lower instantaneous model probability."
            confidence = "MEDIUM CONFIDENCE" if len(signal_basis) >= 4 else "LIMITED CONFIDENCE"
        else:
            status = "NORMAL"
            explanation = "Risk remains in the baseline range based on independent environmental and hydrologic inputs."
            confidence = "HIGH CONFIDENCE" if len(signal_basis) >= 5 else "MEDIUM CONFIDENCE"

    if fallback_status == "UNAVAILABLE" and len(signal_basis) <= 2:
        confidence = "LIMITED CONFIDENCE"

    return {
        "status": status,
        "confidence": confidence,
        "basis": signal_basis,
        "cwc_status": "NOT_USED",
        "explanation": explanation,
        "historical_flood_risk": round(historical_risk, 4),
        "recurrence_risk_factor": round(recurrence_factor, 4),
    }


def build_demo_scenario(
    scenario_num: int,
    latitude: float,
    longitude: float,
    language: str = "en",
    place: Optional[str] = "Varanasi (Ganga)"
) -> Dict[str, Any]:
    """
    Generates presentation demonstration scenarios with synthetic data.
    Clearly marks all fields as synthetic and displays the required warning banner:
    '⚠ DEMO MODE — SYNTHETIC DATA — NOT LIVE OBSERVATION'
    """
    demo_banner = "⚠ DEMO MODE — SYNTHETIC DATA — NOT LIVE OBSERVATION"

    scenarios = {
        1: {
            "name": "Scenario 1: Baseline Normal Hydrology",
            "ai_prob": 6.7,
            "ai_risk": "LOW",
            "cwc_status": "AVAILABLE",
            "cwc_stage": 68.20,
            "cwc_cond": "BELOW_WARNING",
            "cwc_reason": None,
            "fallback_risk": "LOW",
            "rainfall_24h": 4.2,
            "forecast_72h": 12.0,
            "river_prox": "NEAR",
            "overall_status": "NORMAL",
            "confidence": "HIGH CONFIDENCE",
            "explanation": "NORMAL: Both AI model and CWC ground-truth observations confirm normal water levels."
        },
        2: {
            "name": "Scenario 2: Moderate Model Risk + High Environmental Fallback",
            "ai_prob": 45.0,
            "ai_risk": "MEDIUM",
            "cwc_status": "UNAVAILABLE",
            "cwc_stage": None,
            "cwc_cond": "UNKNOWN",
            "cwc_reason": "Gauge telemetry transmission offline / not published",
            "fallback_risk": "HIGH",
            "rainfall_24h": 85.0,
            "forecast_72h": 110.0,
            "river_prox": "NEAR",
            "overall_status": "HIGH ALERT",
            "confidence": "MEDIUM CONFIDENCE",
            "explanation": "HIGH ALERT: Elevated by severe rainfall and near-river exposure while CWC telemetry is unavailable."
        },
        3: {
            "name": "Scenario 3: High AI Model Flood Risk + High Environmental Fallback",
            "ai_prob": 72.5,
            "ai_risk": "HIGH",
            "cwc_status": "UNAVAILABLE",
            "cwc_stage": None,
            "cwc_cond": "UNKNOWN",
            "cwc_reason": "Gauge telemetry transmission offline / not published",
            "fallback_risk": "HIGH",
            "rainfall_24h": 95.0,
            "forecast_72h": 140.0,
            "river_prox": "NEAR",
            "overall_status": "HIGH ALERT",
            "confidence": "MEDIUM CONFIDENCE",
            "explanation": "HIGH ALERT: High inundation probability confirmed by extreme rainfall loading; live CWC gauge is unavailable."
        },
        4: {
            "name": "Scenario 4: Confirmed Severe Inundation (High AI + CWC Above Danger)",
            "ai_prob": 78.4,
            "ai_risk": "HIGH",
            "cwc_status": "AVAILABLE",
            "cwc_stage": 71.85,
            "cwc_cond": "ABOVE_DANGER",
            "cwc_reason": None,
            "fallback_risk": "HIGH",
            "rainfall_24h": 115.0,
            "forecast_72h": 160.0,
            "river_prox": "NEAR",
            "overall_status": "CRITICAL",
            "confidence": "HIGH CONFIDENCE",
            "explanation": "CRITICAL: Severe flood verified by official CWC gauge telemetry above danger level and high AI model flood risk."
        },
        5: {
            "name": "Scenario 5: River Gauge Surge Override (Low AI + CWC Above Danger)",
            "ai_prob": 6.7,
            "ai_risk": "LOW",
            "cwc_status": "AVAILABLE",
            "cwc_stage": 71.80,
            "cwc_cond": "ABOVE_DANGER",
            "cwc_reason": None,
            "fallback_risk": "HIGH",
            "rainfall_24h": 85.0,
            "forecast_72h": 110.0,
            "river_prox": "NEAR",
            "overall_status": "HIGH ALERT",
            "confidence": "MEDIUM CONFIDENCE",
            "explanation": "HIGH ALERT: CWC river gauge has breached danger mark due to upstream release, overriding low local AI prediction."
        }
    }

    sc = scenarios.get(scenario_num, scenarios[1])

    ai_sig = {
        "source": "AI_MODEL",
        "probability": sc["ai_prob"],
        "risk": sc["ai_risk"],
        "label": sc["ai_risk"],
        "sourceType": "SYNTHETIC_DEMO"
    }

    cwc_sig = {
        "source": "CWC",
        "status": sc["cwc_status"],
        "station": {
            "id": "CWC_006-MGD3VNS",
            "name": "Varanasi",
            "river": "Ganga",
            "latitude": 25.323611,
            "longitude": 83.037500,
            "distance_km": 0.0
        },
        "observation": {
            "water_level_m": sc["cwc_stage"],
            "timestamp": "2026-09-03T10:00:00Z" if sc["cwc_stage"] is not None else None
        },
        "thresholds": {
            "warning_level_m": 70.262,
            "danger_level_m": 71.262,
            "hfl_m": 73.901
        },
        "station_id": "CWC_006-MGD3VNS",
        "station_name": "Varanasi",
        "river": "Ganga",
        "distance_km": 0.0,
        "water_level_m": sc["cwc_stage"],
        "warning_level_m": 70.262,
        "danger_level_m": 71.262,
        "extreme_level_m": 73.901,
        "condition": sc["cwc_cond"],
        "updated_at": "2026-09-03T10:00:00Z" if sc["cwc_stage"] is not None else None,
        "reason": sc["cwc_reason"],
        "data_source": "SYNTHETIC DEMO SIMULATION (NOT LIVE OBSERVATION)"
    }

    fallback_sig = {
        "source": "FALLBACK_ENVIRONMENTAL",
        "status": "AVAILABLE",
        "risk": sc["fallback_risk"],
        "rainfall_mm": sc["rainfall_24h"],
        "forecast_rainfall_mm": sc["forecast_72h"],
        "river_proximity": sc["river_prox"],
        "soil_moisture": 0.42 if sc["fallback_risk"] == "HIGH" else 0.28,
        "discharge_ratio": 2.1 if sc["fallback_risk"] == "HIGH" else 1.0,
        "summary": f"Synthetic demo environmental condition: {sc['fallback_risk']} hazard."
    }

    overall_sig = {
        "status": sc["overall_status"],
        "confidence": sc["confidence"],
        "basis": ["AI_MODEL", "CWC"] if sc["cwc_status"] == "AVAILABLE" else ["AI_MODEL", "FALLBACK_ENVIRONMENTAL"],
        "cwc_status": sc["cwc_status"],
        "explanation": sc["explanation"]
    }

    return {
        "is_demo": True,
        "demo_scenario": scenario_num,
        "demo_banner": demo_banner,
        "scenario_name": sc["name"],
        "ai_risk_status": ai_sig,
        "cwc_ground_truth": cwc_sig,
        "fallback_environmental": fallback_sig,
        "overall_monitoring": overall_sig
    }
