from pathlib import Path
import json
import pandas as pd

ROOT = Path("data")
PROCESSED = ROOT / "processed"
MASTER = PROCESSED / "master"
PHASE13 = MASTER / "phase13"

MASTER_PHASE12 = MASTER / "phase12" / "chetakai_v1_master_phase12.csv"

PRODUCTION_DIR = PHASE13 / "production"

OUTPUT_JSON = PRODUCTION_DIR / "production_feature_contract.json"
OUTPUT_CSV = PRODUCTION_DIR / "production_feature_availability.csv"


STATIC_FEATURES = {
    "location": [
        "latitude",
        "longitude",
        "basin_id",
        "timestamp",
    ],

    "administration": [
        "country",
        "state",
        "district",
        "subdistrict",
        "block",
    ],

    "terrain": [
        "elevation",
        "slope",
        "flow_accumulation",
        "distance_to_river",
        "relief",
    ],

    "hydrography": [
        "river_distance",
        "river_density",
        "river_area_fraction",
    ],

    "lulc": [
        "land_cover",
        "tree_cover_pct",
        "shrubland_pct",
        "grassland_pct",
        "cropland_pct",
        "built_up_pct",
        "bare_sparse_pct",
        "water_pct",
        "wetland_pct",
        "natural_vegetation_pct",
    ],

    "soil": [
        "soil_texture",
        "sand_pct",
        "clay_pct",
        "silt_pct",
        "soc",
        "bulk_density",
        "soil_ph",
        "cec",
        "soil_runoff_proxy",
    ],

    "population": [
        "population_total",
        "population_density",
    ],

    "infrastructure": [
        "road_length_km",
        "railway_length_km",
        "bridge_count",
        "building_count",
        "school_count",
        "hospital_count",
        "critical_infrastructure_count",
    ],
}


DYNAMIC_FEATURES = {
    "weather": [
        "rain_1h",
        "rain_3h",
        "rain_6h",
        "rain_24h",
        "rain_72h",
        "temperature",
        "humidity",
        "pressure",
        "wind_speed",
    ],

    "nwp": [
        "nwp_rain_1h",
        "nwp_rain_3h",
        "nwp_rain_6h",
        "nwp_rain_12h",
        "nwp_rain_24h",
        "nwp_spread",
    ],

    "hydrology": [
        "river_level",
        "river_level_change",
        "river_level_trend",
        "river_discharge",
    ],

    "remote_sensing": [
        "radar_rainfall",
        "satellite_rainfall",
        "ndvi",
        "ndwi",
        "soil_moisture",
        "radar_available",
        "satellite_available",
        "gauge_available",
        "river_available",
    ],
}


OUTPUT_FEATURES = {
    "flood_probability": "calibrated probability from Phase-13 production classifier",
    "flood_label": "classification derived from production threshold",
    "risk_level": "operational risk category",
}


def flatten(d):
    result = []

    for group, features in d.items():
        for feature in features:
            result.append({
                "group": group,
                "feature": feature
            })

    return result


def main():

    print("=" * 110)
    print("CHETAKAI V1 — PHASE 14C PRODUCTION FEATURE CONTRACT")
    print("=" * 110)

    print("\nLOADING PHASE 12 MASTER")
    print("-" * 110)

    if not MASTER_PHASE12.exists():
        raise FileNotFoundError(
            f"Missing master dataset: {MASTER_PHASE12}"
        )

    df = pd.read_csv(MASTER_PHASE12)

    print(f"Master dataset : {MASTER_PHASE12}")
    print(f"Rows           : {len(df)}")
    print(f"Columns        : {len(df.columns)}")

    print("\nPRODUCTION MODEL")
    print("-" * 110)

    model_candidates = [
        PHASE13 / "production" /
        "chetakai_v1_flood_classifier_production.joblib",

        PHASE13 / "phase13b" / "models" /
        "chetakai_v1_flood_classifier_phase13b_best.joblib",

        PHASE13 / "models" /
        "chetakai_v1_flood_classifier_baseline.joblib",
    ]

    production_model = None

    for candidate in model_candidates:
        if candidate.exists():
            production_model = candidate
            break

    if production_model:
        print(f"Production model : {production_model}")
        print("Model status     : FOUND")
    else:
        print("Production model : NOT FOUND")
        print("Model status     : CHECK REQUIRED")

    print("\nFEATURE CONTRACT")
    print("-" * 110)

    contract_rows = []

    for row in flatten(STATIC_FEATURES):
        contract_rows.append({
            "group": row["group"],
            "feature": row["feature"],
            "type": "static",
            "resolution": "location-dependent",
            "required_for_classifier": False,
            "status": "PLANNED"
        })

    for row in flatten(DYNAMIC_FEATURES):
        contract_rows.append({
            "group": row["group"],
            "feature": row["feature"],
            "type": "dynamic",
            "resolution": "timestamp-dependent",
            "required_for_classifier": False,
            "status": "PLANNED"
        })

    contract_df = pd.DataFrame(contract_rows)

    print(f"Contract features : {len(contract_df)}")

    print("\nPHASE 12 COLUMN AVAILABILITY")
    print("-" * 110)

    master_columns = set(df.columns)

    availability = []

    for row in contract_rows:

        feature = row["feature"]

        direct_match = feature in master_columns

        related_matches = [
            c for c in master_columns
            if feature.lower() in c.lower()
            or c.lower() in feature.lower()
        ]

        if direct_match:
            status = "DIRECT"
        elif related_matches:
            status = "RELATED"
        else:
            status = "NOT_IN_MASTER"

        availability.append({
            "group": row["group"],
            "feature": feature,
            "type": row["type"],
            "status": status,
            "related_master_columns": ";".join(
                related_matches[:10]
            )
        })

    availability_df = pd.DataFrame(availability)

    print(
        availability_df["status"]
        .value_counts()
        .to_string()
    )

    print("\nIMPORTANT CLASSIFIER TARGET")
    print("-" * 110)

    target_columns = [
        "target_flood",
        "flood_event_flag",
        "flood_severity_score",
        "flood_event_count",
        "flood_duration_days",
        "flood_area_affected",
    ]

    for col in target_columns:
        if col in master_columns:
            print(f"{col:30} PRESENT")

    print("\nDEPTH STATUS")
    print("-" * 110)

    if "flood_area_affected" in master_columns:
        unique_values = df["flood_area_affected"].nunique(dropna=False)
        maximum = df["flood_area_affected"].max()

        print(f"flood_area_affected unique values : {unique_values}")
        print(f"flood_area_affected maximum       : {maximum}")

        if unique_values <= 1 or maximum == 0:
            print("Depth/inundation target            : NOT AVAILABLE")
        else:
            print("Depth/inundation target            : REQUIRES VALIDATION")
    else:
        print("Depth/inundation target            : NOT AVAILABLE")

    print("\nSAVING CONTRACT")
    print("-" * 110)

    PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)

    contract = {
        "project": "CHETAKAI V1",
        "phase": "14C",
        "purpose": "Production LAT/LON feature contract",
        "classifier_model": (
            str(production_model)
            if production_model else None
        ),
        "static_feature_groups": STATIC_FEATURES,
        "dynamic_feature_groups": DYNAMIC_FEATURES,
        "output_features": OUTPUT_FEATURES,
        "input_rule": {
            "latitude": "required",
            "longitude": "required",
            "timestamp": "recommended for dynamic data"
        },
        "depth_model_status": "NOT_AVAILABLE",
        "training_required_during_inference": False,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(contract, f, indent=2)

    availability_df.to_csv(
        OUTPUT_CSV,
        index=False
    )

    print(f"Contract saved      : {OUTPUT_JSON}")
    print(f"Availability report : {OUTPUT_CSV}")

    print("\n" + "=" * 110)
    print("PHASE 14C FINAL VALIDATION")
    print("=" * 110)

    print(f"Master dataset loaded       : PASS")
    print(f"Feature contract generated  : PASS")
    print(f"Static feature groups       : {len(STATIC_FEATURES)}")
    print(f"Dynamic feature groups      : {len(DYNAMIC_FEATURES)}")
    print(f"Contract features           : {len(contract_rows)}")
    print(
        f"Production model discovered : "
        f"{'PASS' if production_model else 'CHECK'}"
    )
    print("Inference retraining         : NO")
    print("Depth model                  : NOT YET AVAILABLE")

    print("\n" + "=" * 110)
    print("🔥 PHASE 14C PASS — PRODUCTION FEATURE CONTRACT CREATED")
    print("=" * 110)


if __name__ == "__main__":
    main()