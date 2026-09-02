from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PHASE21 = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase21"
    / "latest_risk_snapshot.json"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase22"
)

OUTPUT = OUTPUT_DIR / "latest_risk_engine.json"
AUDIT = OUTPUT_DIR / "phase22_audit.jsonl"


def finite(value):
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def number(data, key):
    value = data.get(key)

    if finite(value):
        return float(value)

    return None


def clamp(value, minimum=0.0, maximum=100.0):
    return max(minimum, min(maximum, float(value)))


def average(values):
    values = [v for v in values if v is not None]

    if not values:
        return None

    return sum(values) / len(values)


def risk_class(score):
    if score >= 80:
        return "SEVERE"

    if score >= 65:
        return "HIGH"

    if score >= 40:
        return "MODERATE"

    return "LOW"


def probability_class(probability):
    if probability >= 0.80:
        return "SEVERE"

    if probability >= 0.60:
        return "HIGH"

    if probability >= 0.35:
        return "MODERATE"

    return "LOW"


# ---------------------------------------------------------------------
# RAINFALL
# ---------------------------------------------------------------------

def rainfall_score(current):
    scores = []

    thresholds = {
        "rainfall_1h_proxy": 20.0,
        "rainfall_6h_proxy": 60.0,
        "rainfall_24h_proxy": 100.0,
        "rainfall_72h_proxy": 200.0,
    }

    for feature, threshold in thresholds.items():
        value = number(current, feature)

        if value is not None:
            scores.append(
                clamp(
                    value / threshold * 100.0
                )
            )

    return average(scores)


# ---------------------------------------------------------------------
# FORECAST / NWP
# ---------------------------------------------------------------------

def forecast_score(current):
    scores = []

    thresholds = {
        "nwp_rain_1h_proxy": 20.0,
        "nwp_rain_6h_proxy": 60.0,
        "nwp_rain_12h_proxy": 100.0,
        "nwp_rain_24h_proxy": 140.0,
    }

    for feature, threshold in thresholds.items():
        value = number(current, feature)

        if value is not None:
            scores.append(
                clamp(
                    value / threshold * 100.0
                )
            )

    return average(scores)


# ---------------------------------------------------------------------
# HYDROLOGY
# ---------------------------------------------------------------------

def hydrology_score(current):
    values = []

    loading = str(
        current.get("hydrological_loading", "")
    ).upper()

    loading_map = {
        "LOW": 25.0,
        "MEDIUM": 50.0,
        "HIGH": 85.0,
        "SEVERE": 100.0,
    }

    if loading in loading_map:
        values.append(loading_map[loading])

    trend = str(
        current.get("river_level_trend", "")
    ).upper()

    trend_map = {
        "FALLING": 20.0,
        "STABLE": 40.0,
        "RISING": 85.0,
    }

    if trend in trend_map:
        values.append(trend_map[trend])

    change = number(
        current,
        "river_level_change"
    )

    if change is not None:
        values.append(
            clamp(
                50.0 + change * 100.0
            )
        )

    return average(values)


# ---------------------------------------------------------------------
# TERRAIN
# ---------------------------------------------------------------------

def terrain_score(current):
    values = []

    slope = number(
        current,
        "mean_slope_deg"
    )

    if slope is not None:
        values.append(
            clamp(
                slope / 8.0 * 100.0
            )
        )

    relief = number(
        current,
        "elevation_range_ratio"
    )

    if relief is not None:
        values.append(
            clamp(
                relief / 10.0 * 100.0
            )
        )

    minimum_elevation = number(
        current,
        "min_elevation_m"
    )

    if minimum_elevation is not None:
        values.append(
            clamp(
                70.0
                - minimum_elevation / 100.0 * 20.0
            )
        )

    return average(values)


# ---------------------------------------------------------------------
# SURFACE / SOIL
# ---------------------------------------------------------------------

def surface_soil_score(current):
    values = []

    runoff_proxy = number(
        current,
        "soil_runoff_proxy"
    )

    if runoff_proxy is not None:
        values.append(
            clamp(runoff_proxy)
        )

    wetness = str(
        current.get("surface_wetness", "")
    ).upper()

    wetness_map = {
        "LOW": 25.0,
        "MEDIUM": 55.0,
        "HIGH": 90.0,
    }

    if wetness in wetness_map:
        values.append(wetness_map[wetness])

    runoff = str(
        current.get("runoff_potential", "")
    ).upper()

    runoff_map = {
        "LOW": 25.0,
        "MEDIUM": 55.0,
        "HIGH": 90.0,
    }

    if runoff in runoff_map:
        values.append(runoff_map[runoff])

    return average(values)


# ---------------------------------------------------------------------
# EXPOSURE
# ---------------------------------------------------------------------

def exposure_score(current):
    values = []

    population = number(
        current,
        "estimated_exposed_population"
    )

    if population is not None:
        values.append(
            clamp(
                population / 10000.0 * 100.0
            )
        )

    buildings = number(
        current,
        "buildings_exposed"
    )

    if buildings is not None:
        values.append(
            clamp(
                buildings / 5000.0 * 100.0
            )
        )

    roads = number(
        current,
        "roads_exposed_km"
    )

    if roads is not None:
        values.append(
            clamp(
                roads / 50.0 * 100.0
            )
        )

    return average(values)


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="ChetakAI Phase 22 Risk Engine"
    )

    parser.add_argument(
        "--strict",
        action="store_true"
    )

    args = parser.parse_args()

    print("=" * 110)
    print("CHETAKAI V1 — PHASE 22 RISK ENGINE")
    print("=" * 110)

    if not PHASE21.exists():
        raise FileNotFoundError(
            f"Phase 21 snapshot not found:\n{PHASE21}"
        )

    payload = json.loads(
        PHASE21.read_text(
            encoding="utf-8"
        )
    )

    if payload.get("phase") != "21":
        raise ValueError(
            "Input file is not a Phase 21 snapshot."
        )

    prediction = payload.get(
        "prediction",
        {}
    )

    state = payload.get(
        "state",
        {}
    )

    current = state.get(
        "current",
        {}
    )

    probability = number(
        prediction,
        "flood_probability"
    )

    if probability is None:
        raise ValueError(
            "Phase 21 flood_probability is missing."
        )

    consistency = bool(
        payload
        .get("data_quality", {})
        .get(
            "basin_state_consistency",
            False
        )
    )

    if args.strict and not consistency:
        raise ValueError(
            "STRICT MODE: basin/state consistency failed."
        )

    # ---------------------------------------------------------------
    # COMPONENTS
    # ---------------------------------------------------------------

    components = {
        "model_probability":
            clamp(
                probability * 100.0
            ),

        "rainfall":
            rainfall_score(current),

        "forecast":
            forecast_score(current),

        "hydrology":
            hydrology_score(current),

        "terrain":
            terrain_score(current),

        "surface_soil":
            surface_soil_score(current),

        "exposure":
            exposure_score(current),
    }

    # ---------------------------------------------------------------
    # DETERMINISTIC FUSION
    # ---------------------------------------------------------------

    weights = {
        "model_probability": 0.50,
        "rainfall": 0.15,
        "forecast": 0.10,
        "hydrology": 0.10,
        "terrain": 0.05,
        "surface_soil": 0.05,
        "exposure": 0.05,
    }

    weighted_sum = 0.0
    total_weight = 0.0

    for component, weight in weights.items():

        value = components.get(component)

        if value is None:
            continue

        weighted_sum += value * weight
        total_weight += weight

    if total_weight == 0:
        raise ValueError(
            "No valid risk components available."
        )

    risk_score = (
        weighted_sum / total_weight
    )

    model_band = probability_class(
        probability
    )

    fused_band = risk_class(
        risk_score
    )

    rank = {
        "LOW": 0,
        "MODERATE": 1,
        "HIGH": 2,
        "SEVERE": 3,
    }

    # Supporting layers may increase risk,
    # but never downgrade the ML classification.

    if rank[fused_band] >= rank[model_band]:
        final_band = fused_band
    else:
        final_band = model_band

    priority = {
        "LOW": "P4",
        "MODERATE": "P3",
        "HIGH": "P2",
        "SEVERE": "P1",
    }[final_band]

    missing = [
        key
        for key, value in components.items()
        if value is None
    ]

    completeness = (
        1.0
        - len(missing)
        / len(components)
    )

    confidence = (
        probability * 0.70
        + completeness * 0.20
        + (0.10 if consistency else 0.0)
    )

    confidence = max(
        0.0,
        min(
            1.0,
            confidence
        )
    )

    # ---------------------------------------------------------------
    # DRIVERS
    # ---------------------------------------------------------------

    driver_names = {
        "model_probability":
            "ML flood probability",

        "rainfall":
            "rainfall loading",

        "forecast":
            "forecast/NWP loading",

        "hydrology":
            "hydrological loading",

        "terrain":
            "terrain susceptibility",

        "surface_soil":
            "surface/soil runoff conditions",

        "exposure":
            "population/infrastructure exposure",
    }

    drivers = []

    for component, value in components.items():

        if value is None:
            continue

        drivers.append(
            {
                "factor":
                    driver_names[component],

                "score":
                    round(value, 3),

                "weight":
                    weights[component],

            }
        )

    drivers.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    basin = payload.get(
        "basin",
        {}
    )

    result = {

        "phase": "22",

        "engine":
            "ChetakAI Risk Engine",

        "schema_version":
            "1.1",

        "timestamp":
            timestamp,

        "source": {

            "phase21_snapshot":
                str(PHASE21),

            "coordinate":
                payload.get(
                    "coordinate",
                    {}
                ),

            "basin_id":
                basin.get(
                    "basin_id"
                ),

            "basin_name":
                basin.get(
                    "basin_name"
                ) or basin.get(
                    "basin_id"
                ),

            "state_basin_id":
                state.get(
                    "state_basin_id"
                ),

            "basin_state_consistency":
                consistency,
        },

        "risk": {

            "model_probability":
                round(
                    probability,
                    6
                ),

            "model_probability_pct":
                round(
                    probability * 100.0,
                    2
                ),

            "risk_score":
                round(
                    risk_score,
                    3
                ),

            "risk_score_pct":
                round(
                    risk_score,
                    2
                ),

            "risk_class":
                final_band,

            "severity":
                final_band,

            "confidence":
                round(
                    confidence,
                    6
                ),

            "confidence_pct":
                round(
                    confidence * 100.0,
                    2
                ),

            "alert_priority":
                priority,
        },

        "components":
            components,

        "drivers":
            drivers,

        "data_quality": {

            "phase21_status":
                payload
                .get("data_quality", {})
                .get(
                    "production_status"
                ),

            "coordinate_resolution":
                basin.get(
                    "coordinate_resolution"
                ),

            "state_resolution":
                state.get(
                    "state_resolution"
                ),

            "feature_contract":
                payload
                .get("feature_audit", {})
                .get(
                    "contract_status"
                ),

            "missing_components":
                missing,

            "component_completeness_pct":
                round(
                    completeness * 100.0,
                    2
                ),
        },

        "contract": {

            "strict":
                bool(args.strict),

            "model_probability_preserved":
                True,

            "no_cross_basin_prediction":
                True,

            "deterministic_fusion":
                True,

            "phase21_authoritative":
                True,

            "missing_values_not_invented":
                True,
        },
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    audit_record = {

        "timestamp":
            timestamp,

        "phase":
            "22",

        "status":
            "PASS",

        "basin_id":
            result["source"]["basin_id"],

        "risk_class":
            final_band,

        "risk_score":
            round(
                risk_score,
                3
            ),

        "model_probability":
            probability,

        "missing_components":
            missing,
    }

    with AUDIT.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            json.dumps(
                audit_record
            )
            + "\n"
        )

    # ---------------------------------------------------------------
    # TERMINAL REPORT
    # ---------------------------------------------------------------

    print()
    print("BASIN")
    print("-" * 110)

    print(
        f"Basin                 : "
        f"{result['source']['basin_name']}"
    )

    print(
        f"Basin ID              : "
        f"{result['source']['basin_id']}"
    )

    print(
        f"State basin           : "
        f"{result['source']['state_basin_id']}"
    )

    print(
        f"Consistency           : "
        f"{consistency}"
    )

    print()

    print("RISK")
    print("-" * 110)

    print(
        f"Model probability     : "
        f"{probability * 100:.2f}%"
    )

    print(
        f"Risk engine score     : "
        f"{risk_score:.2f}%"
    )

    print(
        f"Risk class            : "
        f"{final_band}"
    )

    print(
        f"Severity              : "
        f"{final_band}"
    )

    print(
        f"Confidence            : "
        f"{confidence * 100:.2f}%"
    )

    print(
        f"Alert priority        : "
        f"{priority}"
    )

    print()

    print("TOP RISK DRIVERS")
    print("-" * 110)

    for driver in drivers[:7]:

        print(
            f"{driver['factor']:<42}"
            f"{driver['score']:>8.2f}"
        )

    print()

    print("DATA QUALITY")
    print("-" * 110)

    print(
        f"Component completeness : "
        f"{completeness * 100:.2f}%"
    )

    print(
        f"Missing components     : "
        f"{len(missing)}"
    )

    print()

    print("OUTPUT")
    print("-" * 110)

    print(
        f"Snapshot              : "
        f"{OUTPUT}"
    )

    print(
        f"Audit                 : "
        f"{AUDIT}"
    )

    print()

    print(
        "PHASE 22 STATUS       : PASS"
    )

    print("=" * 110)


if __name__ == "__main__":
    main()