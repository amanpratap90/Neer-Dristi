from pathlib import Path
import json
import pandas as pd
import numpy as np

print("=" * 110)
print("CHETAKAI V1 — PHASE 18 PHYSICAL FLOOD HAZARD FEATURE CONTRACT")
print("=" * 110)

BASE = Path("data/processed/training/phase15_1")
OUT = Path("data/processed/models/phase18")
OUT.mkdir(parents=True, exist_ok=True)

TRAIN_PATH = BASE / "train.csv"
VAL_PATH = BASE / "validation.csv"
TEST_PATH = BASE / "test.csv"
MANIFEST_PATH = BASE / "feature_manifest.json"

train = pd.read_csv(TRAIN_PATH)
validation = pd.read_csv(VAL_PATH)
test = pd.read_csv(TEST_PATH)

with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
    manifest = json.load(f)

print()
print("LOADING DATA")
print("-" * 110)
print(f"Train      : {train.shape}")
print(f"Validation : {validation.shape}")
print(f"Test       : {test.shape}")

TARGET = "target_flood"

print()
print("TARGET")
print("-" * 110)

for name, df in [
    ("TRAIN", train),
    ("VALIDATION", validation),
    ("TEST", test),
]:
    positives = int(df[TARGET].sum())
    rows = len(df)
    rate = positives / rows if rows else 0

    print(
        f"{name:<12} rows={rows:4d} "
        f"floods={positives:4d} "
        f"rate={rate:.2%}"
    )

# ---------------------------------------------------------------------
# FEATURE CONTRACT
# ---------------------------------------------------------------------

manifest_features = manifest.get("model_features", [])

if not manifest_features:
    manifest_features = manifest.get("features", [])

numeric_features = [
    c for c in train.columns
    if c != TARGET and pd.api.types.is_numeric_dtype(train[c])
]

print()
print("FEATURE CONTRACT")
print("-" * 110)
print(f"Manifest feature count : {len(manifest_features)}")
print(f"Actual numeric count   : {len(numeric_features)}")

if len(manifest_features) != len(numeric_features):
    print("WARNING: manifest/numeric feature count mismatch")

# ---------------------------------------------------------------------
# PHYSICAL FEATURE REMOVAL
# ---------------------------------------------------------------------

REMOVE_FEATURES = {
    # Administrative / metadata-derived
    "adm1_feature_count",
    "adm1_intersected_area_km2",
    "adm2_feature_count",
    "adm2_intersected_area_km2",
    "administrative_feature_count",

    # Calendar / aggregate identifiers
    "annual_rainfall_mm",

    # String/identity representations that should not become model inputs
    "basin_name",
    "dem__basin_name",

    # Processing metadata
    "dem_tile_count",
    "lulc__basin_area_km2",
    "lulc_rasters_used",
    "lulc_valid_pixels",

    # Redundant observational ratio proxies
    "obs_extreme_rain_ratio_proxy",
    "obs_heavy_rain_ratio_proxy",

    # Population exposure is handled downstream by the risk engine.
    "population_density_per_km2",
    "population_max_pixel_value",
    "population_mean_pixel_value",
    "population_min_pixel_value",
    "population_total",
    "population_valid_pixels",

    # Dataset/source availability metadata
    "river_feature_count",
    "satellite_available",

    # Spatial raster processing metadata
    "valid_pixels",
}

physical_features = [
    f for f in numeric_features
    if f not in REMOVE_FEATURES
]

removed_features = [
    f for f in numeric_features
    if f in REMOVE_FEATURES
]

print()
print("PHYSICAL FEATURE CONTRACT")
print("-" * 110)
print(f"Original numeric candidates : {len(numeric_features)}")
print(f"Physical hazard features    : {len(physical_features)}")
print(f"Removed                      : {len(removed_features)}")

print()
print("REMOVED FEATURES")
print("-" * 110)

for feature in removed_features:
    print(f" - {feature}")

print()
print("FINAL PHYSICAL FEATURES")
print("-" * 110)

for i, feature in enumerate(physical_features, 1):
    print(f"{i:3d}. {feature}")

# ---------------------------------------------------------------------
# ACTUAL TARGET LEAKAGE AUDIT
# ---------------------------------------------------------------------
#
# IMPORTANT:
# A feature containing the word "flood" is NOT automatically leakage.
#
# Example:
#   rainfall_flood_stress_proxy
#   flash_flood_precipitation_proxy
#
# are valid if calculated only from weather/rainfall conditions.
#
# Actual leakage means the feature directly contains information derived
# from the flood label/event outcome.
# ---------------------------------------------------------------------

ACTUAL_LEAKAGE_FEATURES = {
    "target_flood",
    "flood_event_flag",
    "flood_event_count",
    "flood_severity_score",
    "flood_area_affected",
    "flood_duration_days",
    "flood_fatalities",
    "flood_injured",
    "flood_displaced",
    "flood_animal_fatalities",
}

potential_leakage = [
    f for f in physical_features
    if f in ACTUAL_LEAKAGE_FEATURES
]

print()
print("TARGET LEAKAGE AUDIT")
print("-" * 110)

if potential_leakage:
    print("ERROR: Actual target leakage detected:")

    for feature in potential_leakage:
        print(f" - {feature}")

    raise ValueError(
        "Actual target leakage detected in physical feature contract."
    )

print("No actual target leakage detected.")

# Explicitly report flood-named physical predictors
flood_named_predictors = [
    f for f in physical_features
    if "flood" in f.lower()
]

print()
print("FLOOD-NAMED PREDICTOR AUDIT")
print("-" * 110)

if flood_named_predictors:
    print(
        "These features contain 'flood' in their name but are retained "
        "because they are predictor features rather than target labels:"
    )

    for feature in flood_named_predictors:
        print(f" - {feature}")

else:
    print("No flood-named predictor features.")

# ---------------------------------------------------------------------
# VERIFY TARGET IS NOT IN FEATURE CONTRACT
# ---------------------------------------------------------------------

if TARGET in physical_features:
    raise ValueError(
        "CRITICAL: target_flood exists inside physical feature contract."
    )

# ---------------------------------------------------------------------
# VERIFY FEATURES EXIST IN ALL DATASETS
# ---------------------------------------------------------------------

print()
print("FEATURE AVAILABILITY AUDIT")
print("-" * 110)

missing_train = [f for f in physical_features if f not in train.columns]
missing_val = [f for f in physical_features if f not in validation.columns]
missing_test = [f for f in physical_features if f not in test.columns]

if missing_train:
    print("Missing from train:")
    for f in missing_train:
        print(f" - {f}")

if missing_val:
    print("Missing from validation:")
    for f in missing_val:
        print(f" - {f}")

if missing_test:
    print("Missing from test:")
    for f in missing_test:
        print(f" - {f}")

if missing_train or missing_val or missing_test:
    raise ValueError(
        "Physical feature contract contains features missing from one "
        "or more datasets."
    )

print("All physical features exist in train/validation/test.")

# ---------------------------------------------------------------------
# INFINITY AUDIT
# ---------------------------------------------------------------------

print()
print("INFINITY AUDIT")
print("-" * 110)

for name, df in [
    ("TRAIN", train),
    ("VALIDATION", validation),
    ("TEST", test),
]:
    values = df[physical_features].to_numpy(dtype=float)

    inf_count = int(np.isinf(values).sum())

    print(f"{name:<12} infinity={inf_count}")

    if inf_count > 0:
        raise ValueError(
            f"Infinity detected in {name} physical feature matrix."
        )

# ---------------------------------------------------------------------
# MISSINGNESS AUDIT
# ---------------------------------------------------------------------

print()
print("MISSINGNESS AUDIT")
print("-" * 110)

for name, df in [
    ("TRAIN", train),
    ("VALIDATION", validation),
    ("TEST", test),
]:
    missing = int(df[physical_features].isna().sum().sum())
    total = len(df) * len(physical_features)
    rate = missing / total if total else 0

    print(
        f"{name:<12} missing={missing:6d} "
        f"rate={rate:.2%}"
    )

# ---------------------------------------------------------------------
# LOW VARIANCE AUDIT
# ---------------------------------------------------------------------

print()
print("LOW-VARIANCE FEATURES")
print("-" * 110)

low_variance = []

for feature in physical_features:
    unique_count = train[feature].nunique(dropna=True)

    if unique_count <= 2:
        low_variance.append(
            (feature, unique_count)
        )

if low_variance:
    for feature, unique_count in low_variance:
        print(
            f"{feature:<45} "
            f"unique_values={unique_count}"
        )
else:
    print("None")

# ---------------------------------------------------------------------
# DUPLICATE AUDIT
# ---------------------------------------------------------------------

print()
print("DUPLICATE AUDIT")
print("-" * 110)

for name, df in [
    ("TRAIN", train),
    ("VALIDATION", validation),
    ("TEST", test),
]:
    duplicates = int(df[physical_features].duplicated().sum())

    print(
        f"{name:<12} duplicate_feature_vectors={duplicates}"
    )

# ---------------------------------------------------------------------
# TEMPORAL METADATA AUDIT
# ---------------------------------------------------------------------

print()
print("TEMPORAL METADATA AUDIT")
print("-" * 110)

for name, df in [
    ("TRAIN", train),
    ("VALIDATION", validation),
    ("TEST", test),
]:
    if "timestamp" in df.columns:
        timestamps = pd.to_datetime(
            df["timestamp"],
            errors="coerce"
        )

        print(
            f"{name:<12} "
            f"{timestamps.min()} -> {timestamps.max()}"
        )

# ---------------------------------------------------------------------
# PHYSICAL FEATURE GROUPS
# ---------------------------------------------------------------------

groups = {
    "rainfall": [],
    "terrain": [],
    "hydrology": [],
    "land_surface": [],
    "soil": [],
    "observed_rainfall": [],
    "radar": [],
    "nwp": [],
    "antecedent_runoff": [],
    "other": [],
}

for feature in physical_features:
    f = feature.lower()

    if (
        "rainfall" in f
        or "rain_" in f
        or "rain" in f and "radar" not in f and "nwp" not in f
    ):
        groups["rainfall"].append(feature)

    elif any(
        x in f
        for x in [
            "elevation",
            "slope",
            "relief",
            "terrain",
            "basin_area",
        ]
    ):
        groups["terrain"].append(feature)

    elif any(
        x in f
        for x in [
            "river_",
            "hydrological",
            "runoff",
            "wetness",
        ]
    ):
        groups["hydrology"].append(feature)

    elif any(
        x in f
        for x in [
            "tree_",
            "shrub",
            "grass",
            "crop",
            "built",
            "water_pct",
            "wetland",
            "mangrove",
            "vegetation",
            "bare_",
            "snow_",
            "natural_",
        ]
    ):
        groups["land_surface"].append(feature)

    elif any(
        x in f
        for x in [
            "sand",
            "clay",
            "silt",
            "soc_",
            "bdod",
            "phh2o",
            "cec_",
            "cfvo",
            "soil_",
        ]
    ):
        groups["soil"].append(feature)

    elif f.startswith("obs_"):
        groups["observed_rainfall"].append(feature)

    elif f.startswith("radar_"):
        groups["radar"].append(feature)

    elif f.startswith("nwp_"):
        groups["nwp"].append(feature)

    elif any(
        x in f
        for x in [
            "pressure",
            "antecedent",
            "momentum",
            "prev_",
            "lag_",
            "stress",
            "flash_flood",
        ]
    ):
        groups["antecedent_runoff"].append(feature)

    else:
        groups["other"].append(feature)

print()
print("PHYSICAL FEATURE GROUPS")
print("-" * 110)

for group_name, features in groups.items():
    print(f"{group_name:<25}: {len(features)}")

# ---------------------------------------------------------------------
# CREATE OUTPUT DATASETS
# ---------------------------------------------------------------------

print()
print("BUILDING PHYSICAL DATASETS")
print("-" * 110)

train_physical = pd.concat(
    [
        train[["canonical_basin_id", "timestamp"]],
        train[physical_features],
        train[[TARGET]],
    ],
    axis=1,
)

validation_physical = pd.concat(
    [
        validation[["canonical_basin_id", "timestamp"]],
        validation[physical_features],
        validation[[TARGET]],
    ],
    axis=1,
)

test_physical = pd.concat(
    [
        test[["canonical_basin_id", "timestamp"]],
        test[physical_features],
        test[[TARGET]],
    ],
    axis=1,
)

train_out = OUT / "train_physical.csv"
validation_out = OUT / "validation_physical.csv"
test_out = OUT / "test_physical.csv"

train_physical.to_csv(train_out, index=False)
validation_physical.to_csv(validation_out, index=False)
test_physical.to_csv(test_out, index=False)

# ---------------------------------------------------------------------
# SAVE FEATURE CONTRACT
# ---------------------------------------------------------------------

feature_contract = {
    "project": "CHETAKAI V1",
    "phase": "18",
    "contract_name": "physical_flood_hazard_features",

    "target": TARGET,

    "model_feature_count": len(physical_features),

    "model_features": physical_features,

    "removed_features": removed_features,

    "actual_leakage_features": sorted(
        ACTUAL_LEAKAGE_FEATURES
    ),

    "flood_named_predictors_retained": flood_named_predictors,

    "feature_groups": {
        key: value
        for key, value in groups.items()
    },

    "metadata_features": [
        "canonical_basin_id",
        "timestamp",
    ],

    "notes": [
        "Year is not used as a model feature.",
        "Timestamp is metadata only.",
        "canonical_basin_id is metadata only.",
        "Features derived from rainfall conditions are allowed.",
        "Features are considered leakage only when they directly encode flood outcomes/events.",
        "Population and infrastructure exposure are handled downstream by the risk engine.",
        "Physical hazard prediction is separated from exposure/risk estimation.",
    ],
}

contract_path = OUT / "physical_feature_contract.json"

with open(contract_path, "w", encoding="utf-8") as f:
    json.dump(
        feature_contract,
        f,
        indent=2
    )

# ---------------------------------------------------------------------
# SAVE AUDIT REPORT
# ---------------------------------------------------------------------

report_lines = []

report_lines.append(
    "CHETAKAI V1 — PHASE 18 PHYSICAL FLOOD HAZARD FEATURE CONTRACT"
)

report_lines.append("")
report_lines.append(
    f"Original numeric candidates : {len(numeric_features)}"
)

report_lines.append(
    f"Physical hazard features    : {len(physical_features)}"
)

report_lines.append(
    f"Removed features            : {len(removed_features)}"
)

report_lines.append("")
report_lines.append("RETAINED FLOOD-NAMED PREDICTORS")

for feature in flood_named_predictors:
    report_lines.append(f" - {feature}")

report_lines.append("")
report_lines.append("ACTUAL LEAKAGE FEATURES")

for feature in sorted(ACTUAL_LEAKAGE_FEATURES):
    report_lines.append(f" - {feature}")

report_lines.append("")
report_lines.append("FEATURE GROUPS")

for group_name, features in groups.items():
    report_lines.append(
        f"{group_name}: {len(features)}"
    )

report_lines.append("")
report_lines.append("DATASETS")

report_lines.append(
    f"Train      : {train_physical.shape}"
)

report_lines.append(
    f"Validation : {validation_physical.shape}"
)

report_lines.append(
    f"Test       : {test_physical.shape}"
)

report_lines.append("")
report_lines.append("STATUS: PASS")

report_path = OUT / "phase18_physical_feature_audit.txt"

with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

# ---------------------------------------------------------------------
# FINAL
# ---------------------------------------------------------------------

print()
print("=" * 110)
print("PHASE 18 COMPLETE")
print("=" * 110)

print(f"Physical features : {len(physical_features)}")
print(f"Train             : {train_out}")
print(f"Validation        : {validation_out}")
print(f"Test              : {test_out}")
print(f"Contract          : {contract_path}")
print(f"Audit             : {report_path}")

print()
print("TARGET LEAKAGE")
print("-" * 110)
print("NONE")

print()
print("RETAINED FLOOD-NAMED PHYSICAL PREDICTORS")
print("-" * 110)

for feature in flood_named_predictors:
    print(f" - {feature}")

print()
print("STATUS: PASS")
print("=" * 110)