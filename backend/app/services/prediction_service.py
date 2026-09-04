import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.utils.geo import clamp, round_safe

# Path to the serialized calibrated tree model artifact
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "production_flood_model.json"

_model_artifact: Optional[Dict[str, Any]] = None
_is_loaded = False


def load_model() -> Optional[Dict[str, Any]]:
    """Loads the trained Calibrated Decision Forest artifact into memory."""
    global _model_artifact, _is_loaded
    if _is_loaded and _model_artifact:
        return _model_artifact

    try:
        if MODEL_PATH.exists():
            with open(MODEL_PATH, "r", encoding="utf-8") as f:
                _model_artifact = json.load(f)
                _is_loaded = True
                print(f"[ML-Model] Loaded {_model_artifact.get('model_name')} (v{_model_artifact.get('version')}) with {_model_artifact.get('n_estimators', 30)} trees.")
                return _model_artifact
        else:
            print(f"[ML-Model] Warning: Model artifact not found at {MODEL_PATH}")
    except Exception as exc:
        print(f"[ML-Model] Error loading model artifact: {exc}")

    return None


# Preload model on module import
load_model()


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None and not (isinstance(value, float) and math.isnan(value)):
            return value
    return None


def evaluate_tree(tree: Dict[str, Any], feature_vector: List[float]) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Evaluates a single decision tree on the given feature vector.
    Returns (probability, decision_path_steps).
    """
    node = 0
    left = tree["children_left"]
    right = tree["children_right"]
    feature = tree["feature"]
    threshold = tree["threshold"]
    values = tree["values"]

    path_features = []

    while left[node] != -1 and right[node] != -1:
        feat_idx = feature[node]
        feat_val = feature_vector[feat_idx]
        thresh = threshold[node]

        went_right = feat_val > thresh
        path_features.append({"featureIndex": feat_idx, "wentRight": went_right})

        if feat_val <= thresh:
            node = left[node]
        else:
            node = right[node]

    counts = values[node]
    total = counts[0] + counts[1]
    prob = counts[1] / total if total > 0 else 0.0

    return prob, path_features


def build_feature_vector(inputs: Dict[str, Any], catchment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds the 30-dimensional feature vector exactly matching production_flood_model.json.
    """
    model = load_model()
    rain = inputs.get("rainfall", {})
    current = inputs.get("current", {})
    flood = inputs.get("flood", {})
    soil = catchment.get("soil", {})
    land_cover = catchment.get("land_cover", {})

    def get_float(val: Any) -> Optional[float]:
        if val is not None:
            try:
                num = float(val)
                if math.isfinite(num):
                    return num
            except (ValueError, TypeError):
                pass
        return None

    rain1h = get_float(rain.get("h1"))
    rain3h = get_float(rain.get("h3"))
    rain6h = get_float(rain.get("h6"))
    rain12h = get_float(rain.get("h12"))
    rain24h = get_float(rain.get("h24"))
    rain72h = get_float(rain.get("h72"))
    api = get_float(rain.get("antecedentPrecipitationIndex"))

    sm0_1 = get_float(current.get("soilMoisture0_1"))
    sm1_3 = get_float(current.get("soilMoisture1_3"))
    sm3_9 = get_float(current.get("soilMoisture3_9"))
    sm9_27 = get_float(current.get("soilMoisture9_27"))
    root_zone = get_float(current.get("rootZoneSoilMoisture"))

    evap72h = get_float(rain.get("evapotranspiration72h"))

    clay = get_float(soil.get("clay_fraction_pct"))
    sand = get_float(soil.get("sand_fraction_pct"))
    silt = get_float(soil.get("silt_fraction_pct"))

    elevation = get_float(inputs.get("elevation"))
    slope = get_float(catchment.get("slope_deg"))
    relief = get_float(catchment.get("relief_m"))
    drainage_density = get_float(catchment.get("drainage_density_km_km2"))
    cn = get_float(catchment.get("curve_number"))

    potential_s = (25400.0 / cn - 254.0) if cn and cn > 0 else None
    scs_runoff = None
    if rain72h is not None and potential_s is not None:
        initial_abstraction = 0.2 * potential_s
        excess_p = max(0.0, rain72h - initial_abstraction)
        denom = rain72h + 0.8 * potential_s
        scs_runoff = (excess_p * excess_p) / denom if (excess_p > 0 and denom > 0) else 0.0

    discharge_mean = get_float(flood.get("dischargeMean"))
    discharge_now = get_float(flood.get("dischargeNow"))
    discharge_ratio = (discharge_now / discharge_mean) if (discharge_now is not None and discharge_mean is not None and discharge_mean > 0) else None
    discharge_exceedance = clamp((discharge_ratio - 1.0) * 45.0, 0.0, 100.0) if discharge_ratio is not None else None

    cropland = get_float(land_cover.get("cropland_pct"))
    built_up = get_float(land_cover.get("built_up_pct"))
    water = get_float(land_cover.get("water_pct"))

    forecast24h = get_float(rain.get("forecast24h"))
    forecast72h = get_float(rain.get("forecast72h"))

    historical_context = inputs.get("historical_flood_context") or {}
    hist_count = _coalesce(
        historical_context.get("event_count_5y"),
        historical_context.get("nearby_events"),
        0
    )
    hist_days = _coalesce(
        historical_context.get("days_since_last_flood"),
        3650
    )
    hist_severity = _coalesce(
        historical_context.get("recent_severity_index"),
        0.0
    )
    recurrence = _coalesce(
        historical_context.get("recurrence_risk_factor"),
        historical_context.get("historical_flood_risk"),
        0.0
    )

    feature_map: Dict[str, Any] = {
        "rainfall_1h_mm": rain1h,
        "rainfall_3h_mm": rain3h,
        "rainfall_6h_mm": rain6h,
        "rainfall_12h_mm": rain12h,
        "rainfall_24h_mm": rain24h,
        "rainfall_72h_mm": rain72h,
        "forecast_24h_mm": forecast24h,
        "forecast_72h_mm": forecast72h,
        "antecedent_precipitation_index_7d": api,
        "evapotranspiration_72h_mm": evap72h,
        "soil_moisture_0_to_1cm": sm0_1,
        "soil_moisture_1_to_3cm": sm1_3,
        "soil_moisture_3_to_9cm": sm3_9,
        "soil_moisture_9_to_27cm": sm9_27,
        "root_zone_soil_moisture": root_zone,
        "clay_fraction_pct": clay,
        "sand_fraction_pct": sand,
        "silt_fraction_pct": silt,
        "elevation_m": elevation,
        "mean_slope_deg": slope,
        "relief_m": relief,
        "drainage_density_km_km2": drainage_density,
        "curve_number": cn,
        "potential_retention_s_mm": potential_s,
        "scs_runoff_depth_mm": scs_runoff,
        "discharge_ratio": discharge_ratio,
        "discharge_exceedance_pct": discharge_exceedance,
        "cropland_pct": cropland,
        "built_up_pct": built_up,
        "water_pct": water,
        "historical_flood_count_5y": float(hist_count) if hist_count is not None else None,
        "days_since_last_flood": float(hist_days) if hist_days is not None else None,
        "historical_severity_index": float(hist_severity) if hist_severity is not None else None,
        "recurrence_risk_factor": float(recurrence) if recurrence is not None else None,
    }

    model_features = model.get("features", []) if model else []
    missing = [f for f in model_features if feature_map.get(f) is None]

    if missing:
        return {
            "status": "INSUFFICIENT_DATA",
            "probability": None,
            "probabilityPercent": None,
            "riskClass": "UNKNOWN",
            "modelName": model.get("model_name", "UNKNOWN") if model else "UNKNOWN",
            "version": model.get("version", "UNKNOWN") if model else "UNKNOWN",
            "sourceType": "MODELLED",
            "featuresUsed": [f for f in model_features if feature_map.get(f) is not None],
            "featuresMissing": missing,
            "confidencePct": None
        }

    return feature_map


def predict_flood_risk(inputs: Dict[str, Any], catchment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes real-time calibrated Random Forest inference on the feature vector.
    Preserves exact mathematical parity with the Node.js implementation.
    """
    try:
        model = load_model()
        if not model or not model.get("trees"):
            return {"status": "ML_UNAVAILABLE", "error": "Model artifact not loaded or missing trees."}

        feature_map = build_feature_vector(inputs, catchment)
        if feature_map.get("status") == "INSUFFICIENT_DATA":
            feature_map["status"] = "ML_UNAVAILABLE"
            feature_map["error"] = f"Missing features: {feature_map.get('featuresMissing')}"
            return feature_map

        feature_list = model["features"]
        vector = [float(feature_map.get(f, 0.0) or 0.0) for f in feature_list]

        trees = model["trees"]
        tree_count = len(trees)
        prob_sum = 0.0
        tree_probs = []
        feature_contributions = [0.0] * len(feature_list)

        for tree in trees:
            prob, path = evaluate_tree(tree, vector)
            prob_sum += prob
            tree_probs.append(prob)

            if prob > 0.4:
                for step in path:
                    if step["wentRight"]:
                        feature_contributions[step["featureIndex"]] += (prob - 0.4)

        raw_probability = prob_sum / tree_count
        probability_pct = round(raw_probability * 100.0, 2)

        # Ensemble variance for confidence estimation
        variance = sum((p - raw_probability) ** 2 for p in tree_probs) / tree_count
        std_dev = math.sqrt(variance)
        agreement_factor = max(0.0, 1.0 - std_dev * 2.2)
        confidence_pct = round(70.0 + agreement_factor * 30.0, 1)

        # Risk class definition
        risk_class = "LOW"
        if raw_probability >= 0.72:
            risk_class = "SEVERE"
        elif raw_probability >= 0.50:
            risk_class = "HIGH"
        elif raw_probability >= 0.25:
            risk_class = "MODERATE"

        # Local feature drivers
        global_weights = model.get("global_feature_importances", {})
        driver_scores = []
        for idx, feat_name in enumerate(feature_list):
            global_imp = float(global_weights.get(feat_name, 0.03))
            local_hit = feature_contributions[idx] / max(1, tree_count)
            importance = round(global_imp * 0.6 + local_hit * 0.4, 3)
            driver_scores.append({
                "feature": feat_name,
                "model_importance": max(0.04, importance),
                "value": feature_map.get(feat_name)
            })

        driver_scores.sort(key=lambda x: x["model_importance"], reverse=True)
        top_drivers = driver_scores[:6]

        # 6-pillar components (0-100)
        r72 = feature_map.get("rainfall_72h_mm") or 0.0
        r24 = feature_map.get("rainfall_24h_mm") or 0.0
        f72 = feature_map.get("forecast_72h_mm") or 0.0
        d_ratio = feature_map.get("discharge_ratio") or 1.0
        d_exc = feature_map.get("discharge_exceedance_pct") or 0.0
        slope = feature_map.get("mean_slope_deg") or 2.0
        elev = feature_map.get("elevation_m") or 50.0
        soil_m = feature_map.get("root_zone_soil_moisture") or 0.3
        clay = feature_map.get("clay_fraction_pct") or 25.0
        built = feature_map.get("built_up_pct") or 5.0

        rain_comp = round(clamp((r72 / 250.0) * 80.0 + (r24 / 100.0) * 20.0, 8.0, 100.0))
        forecast_comp = round(clamp((f72 / 200.0) * 85.0, 8.0, 100.0))
        hydro_comp = round(clamp((d_ratio / 2.5) * 80.0 + d_exc * 0.3, 12.0, 100.0))
        terrain_comp = round(clamp((6.0 / max(0.8, slope)) * 25.0 + (30.0 if elev < 30.0 else 10.0), 10.0, 100.0))
        soil_comp = round(clamp(soil_m * 150.0 + (clay / 50.0) * 20.0, 15.0, 100.0))
        exposure_comp = round(clamp(built * 4.5 + (25.0 if elev < 40.0 else 10.0), 15.0, 90.0))

        return {
            "status": "OK",
            "probability": raw_probability,
            "flood_probability_pct": probability_pct,
            "riskClass": risk_class,
            "modelName": model.get("model_name", "ChetakAI Decision Forest"),
            "version": model.get("version", "1.0.0"),
            "sourceType": "MODELLED",
            "featuresUsed": feature_list,
            "featuresMissing": [],
            "confidencePct": confidence_pct,
            "drivers": top_drivers,
            "components": {
                "model_probability": probability_pct,
                "rainfall": rain_comp,
                "forecast": forecast_comp,
                "hydrology": hydro_comp,
                "terrain": terrain_comp,
                "surface_soil": soil_comp,
                "exposure": exposure_comp
            },
            "raw_features": feature_map,
            "metrics": model.get("metrics", {}),
            "debug": {
                "treeVariance": round(variance, 6),
                "stdDev": round(std_dev, 6),
                "agreementFactor": round(agreement_factor, 4)
            }
        }
    except Exception as e:
        return {
            "status": "ML_UNAVAILABLE",
            "probability": None,
            "error": str(e)
        }
