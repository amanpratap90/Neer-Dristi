from pathlib import Path
import shutil
import json
import numpy as np
import pandas as pd

ROOT = Path("data/processed/master")
PHASE11_DIR = ROOT / "phase11"
PHASE12_DIR = ROOT / "phase12"

INPUT = PHASE11_DIR / "chetakai_v1_master_phase11.csv"

BACKUP = PHASE12_DIR / "chetakai_v1_master_phase11_backup.csv"
FINAL_MASTER = PHASE12_DIR / "chetakai_v1_master_phase12.csv"

TRAIN_OUT = PHASE12_DIR / "chetakai_v1_train_final.csv"
VAL_OUT = PHASE12_DIR / "chetakai_v1_validation_final.csv"
TEST_OUT = PHASE12_DIR / "chetakai_v1_test_final.csv"

X_TRAIN_OUT = PHASE12_DIR / "X_train.csv"
X_VAL_OUT = PHASE12_DIR / "X_validation.csv"
X_TEST_OUT = PHASE12_DIR / "X_test.csv"

Y_TRAIN_OUT = PHASE12_DIR / "y_train.csv"
Y_VAL_OUT = PHASE12_DIR / "y_validation.csv"
Y_TEST_OUT = PHASE12_DIR / "y_test.csv"

FEATURE_REPORT = PHASE12_DIR / "phase12_feature_governance.csv"
CORRELATION_REPORT = PHASE12_DIR / "phase12_correlation_report.csv"
MISSINGNESS_REPORT = PHASE12_DIR / "phase12_missingness_report.csv"
PREPROCESS_REPORT = PHASE12_DIR / "phase12_preprocessing_report.csv"
MANIFEST = PHASE12_DIR / "phase12_ml_manifest.json"

TARGET = "target_flood"

print("=" * 110)
print("CHETAKAI V1 — PHASE 12 FINAL ML DATASET FINALIZATION")
print("=" * 110)

PHASE12_DIR.mkdir(parents=True, exist_ok=True)

if not INPUT.exists():
    raise FileNotFoundError(f"Phase 11 master not found:\n{INPUT}")

print("\nLOADING FROZEN PHASE 11 MASTER")
print("-" * 110)

df = pd.read_csv(INPUT)

original_rows = len(df)
original_columns = list(df.columns)

print("Rows    :", len(df))
print("Columns :", len(df.columns))

if len(original_columns) != len(set(original_columns)):
    duplicated_columns = pd.Series(original_columns)[
        pd.Series(original_columns).duplicated()
    ].tolist()
    raise ValueError(
        f"Duplicate column names detected: {duplicated_columns}"
    )

print("\nBACKUP")
print("-" * 110)

if not BACKUP.exists():
    shutil.copy2(INPUT, BACKUP)
    print("Backup created:")
else:
    print("Backup already exists:")

print(BACKUP)

required = [
    "canonical_basin_id",
    "timestamp",
    TARGET,
]

missing = [c for c in required if c not in df.columns]

if missing:
    raise ValueError(f"Missing required columns: {missing}")

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)

if df["timestamp"].isna().any():
    raise ValueError("Invalid timestamps detected.")

if df[TARGET].isna().any():
    raise ValueError("Missing target values detected.")

if not set(df[TARGET].unique()).issubset({0, 1}):
    raise ValueError("target_flood must contain only 0/1.")

duplicate_keys = df.duplicated(
    ["canonical_basin_id", "timestamp"]
).sum()

if duplicate_keys:
    raise ValueError(
        f"Duplicate basin/timestamp keys: {duplicate_keys}"
    )

train = df[df["timestamp"].dt.year <= 2022].copy()

validation = df[
    df["timestamp"].dt.year.isin([2023, 2024])
].copy()

test = df[
    df["timestamp"].dt.year == 2025
].copy()

if len(train) == 0 or len(validation) == 0 or len(test) == 0:
    raise ValueError("Invalid temporal split.")

print("\nTEMPORAL SPLIT")
print("-" * 110)

for name, part in [
    ("TRAIN", train),
    ("VALIDATION", validation),
    ("TEST", test),
]:
    print(
        f"{name:<12} "
        f"rows={len(part):4} "
        f"flood={int(part[TARGET].sum()):4} "
        f"positive_rate={part[TARGET].mean():.4f}"
    )

label_features = [
    c for c in df.columns
    if c.startswith("flood_") and c != TARGET
]

metadata = {
    "canonical_basin_id",
    "timestamp",
    "basin",
    "date",
}

temporal_features = {
    "year",
    "month",
    "month_sin",
    "month_cos",
}

constant_features = []

for c in df.columns:
    if c == TARGET:
        continue

    if df[c].nunique(dropna=False) <= 1:
        constant_features.append(c)

excluded = set()

excluded.add(TARGET)
excluded.update(label_features)
excluded.update(metadata)
excluded.update(constant_features)

candidate_features = [
    c for c in df.columns
    if c not in excluded
]

numeric_candidates = [
    c for c in candidate_features
    if pd.api.types.is_numeric_dtype(df[c])
]

if TARGET in candidate_features:
    raise ValueError(
        "CRITICAL: target_flood entered candidate_features."
    )

if TARGET in numeric_candidates:
    raise ValueError(
        "CRITICAL: target_flood entered numeric_candidates."
    )

print("\nFEATURE INVENTORY")
print("-" * 110)
print("Original columns       :", len(original_columns))
print("Candidate features     :", len(candidate_features))
print("Numeric candidates     :", len(numeric_candidates))
print("Label-derived excluded :", len(label_features))
print("Constant excluded      :", len(constant_features))

print("\nCORRELATION REDUNDANCY ANALYSIS")
print("-" * 110)

corr = train[numeric_candidates].corr()

pairs = []

for i, a in enumerate(corr.columns):
    for b in corr.columns[i + 1:]:
        value = corr.loc[a, b]

        if pd.notna(value) and abs(value) >= 0.995:
            pairs.append({
                "feature_a": a,
                "feature_b": b,
                "correlation": float(value),
            })

corr_report = pd.DataFrame(pairs)

if len(corr_report):
    corr_report = corr_report.sort_values(
        "correlation",
        key=lambda s: s.abs(),
        ascending=False,
    )

corr_report.to_csv(
    CORRELATION_REPORT,
    index=False
)

print("Highly correlated pairs:", len(corr_report))

def feature_priority(name):
    if name in temporal_features:
        return 1

    if name.startswith("rainfall_"):
        return 2

    if name.startswith("nwp_"):
        return 3

    if name.startswith("radar_"):
        return 4

    if name.startswith("obs_"):
        return 5

    if name.startswith("satellite_"):
        return 6

    environmental = {
        "mean_elevation_m",
        "min_elevation_m",
        "max_elevation_m",
        "median_elevation_m",
        "elevation_std_m",
        "relief_m",
        "mean_slope_deg",
        "max_slope_deg",
        "basin_area_km2",
        "river_area_km2",
        "river_area_fraction_pct",
        "river_length_km",
        "river_density_km_per_km2",
        "tree_cover_pct",
        "shrubland_pct",
        "grassland_pct",
        "cropland_pct",
        "built_up_pct",
        "bare_sparse_pct",
        "water_pct",
        "wetland_pct",
        "natural_vegetation_pct",
        "population_total",
        "population_density_per_km2",
        "reservoir_count",
        "reservoir_area_km2",
        "reservoir_area_fraction_pct",
        "reservoir_density_per_1000km2",
        "sand_mean",
        "clay_mean",
        "silt_mean",
        "soc_mean",
        "bdod_mean",
        "phh2o_mean",
        "cec_mean",
        "cfvo_mean",
        "soil_property_availability_pct",
        "sand_fraction_pct",
        "clay_fraction_pct",
        "silt_fraction_pct",
        "soil_runoff_proxy",
        "soil_texture_proxy",
    }

    if name in environmental:
        return 7

    return 8


selected = []
removed_redundant = []

for feature in sorted(
    numeric_candidates,
    key=lambda x: (feature_priority(x), x)
):
    if feature == TARGET:
        continue

    keep = True

    for existing in selected:
        pair = corr.loc[feature, existing]

        if pd.notna(pair) and abs(pair) >= 0.999:
            keep = False

            removed_redundant.append({
                "feature": feature,
                "kept_feature": existing,
                "correlation": float(pair),
                "reason": "near_exact_duplicate",
            })

            break

    if keep:
        selected.append(feature)

selected = [
    c for c in selected
    if c != TARGET
]

print("\nREDUNDANCY REDUCTION")
print("-" * 110)
print("Selected before missingness:", len(selected))
print("Redundant removed         :", len(removed_redundant))

MAX_MISSING_RATE = 0.70

high_missing = []

for c in selected:
    rate = train[c].isna().mean()

    if rate > MAX_MISSING_RATE:
        high_missing.append(c)

selected = [
    c for c in selected
    if c not in high_missing
]

print("High-missing removed       :", len(high_missing))
print("Final candidate features  :", len(selected))

if TARGET in selected:
    raise ValueError(
        "CRITICAL: target_flood remains in selected features."
    )

missing_rows = []

for c in selected:
    train_missing = int(train[c].isna().sum())
    val_missing = int(validation[c].isna().sum())
    test_missing = int(test[c].isna().sum())

    missing_rows.append({
        "feature": c,
        "train_missing": train_missing,
        "validation_missing": val_missing,
        "test_missing": test_missing,
        "train_missing_pct": train_missing / len(train),
        "validation_missing_pct": val_missing / len(validation),
        "test_missing_pct": test_missing / len(test),
    })

missing_report = pd.DataFrame(missing_rows)

missing_report.to_csv(
    MISSINGNESS_REPORT,
    index=False
)

print("\nTRAIN-ONLY IMPUTATION")
print("-" * 110)

preprocess_rows = []

train_processed = train.copy()
val_processed = validation.copy()
test_processed = test.copy()

for c in selected:

    median_value = train_processed[c].median()

    if pd.isna(median_value):
        median_value = 0.0

    train_processed[c] = train_processed[c].fillna(
        median_value
    )

    val_processed[c] = val_processed[c].fillna(
        median_value
    )

    test_processed[c] = test_processed[c].fillna(
        median_value
    )

    preprocess_rows.append({
        "feature": c,
        "method": "train_median",
        "train_median": float(median_value),
    })

preprocess_report = pd.DataFrame(preprocess_rows)

preprocess_report.to_csv(
    PREPROCESS_REPORT,
    index=False
)

X_train = train_processed[selected].copy()
X_val = val_processed[selected].copy()
X_test = test_processed[selected].copy()

y_train = train_processed[
    [
        "canonical_basin_id",
        "timestamp",
        TARGET,
    ]
].copy()

y_val = val_processed[
    [
        "canonical_basin_id",
        "timestamp",
        TARGET,
    ]
].copy()

y_test = test_processed[
    [
        "canonical_basin_id",
        "timestamp",
        TARGET,
    ]
].copy()

print("\nHARD ML SAFETY VALIDATION")
print("-" * 110)

for name, X in [
    ("X_train", X_train),
    ("X_validation", X_val),
    ("X_test", X_test),
]:

    if TARGET in X.columns:
        raise ValueError(
            f"CRITICAL TARGET LEAKAGE: {TARGET} found in {name}"
        )

    leaked_labels = [
        c for c in X.columns
        if c.startswith("flood_")
    ]

    if leaked_labels:
        raise ValueError(
            f"CRITICAL LABEL LEAKAGE in {name}: {leaked_labels}"
        )

    if X.isna().any().any():
        raise ValueError(
            f"NaNs remain in {name}."
        )

print("X_train target leakage       : PASS")
print("X_validation target leakage   : PASS")
print("X_test target leakage         : PASS")
print("Label-derived leakage         : PASS")
print("NaN validation                : PASS")

if set(X_train.columns) != set(X_val.columns):
    raise ValueError("Train/validation feature mismatch.")

if set(X_train.columns) != set(X_test.columns):
    raise ValueError("Train/test feature mismatch.")

if len(X_train) != len(y_train):
    raise ValueError("X_train/y_train row mismatch.")

if len(X_val) != len(y_val):
    raise ValueError("X_val/y_val row mismatch.")

if len(X_test) != len(y_test):
    raise ValueError("X_test/y_test row mismatch.")

if train["timestamp"].max() >= validation["timestamp"].min():
    raise ValueError("Train overlaps validation.")

if validation["timestamp"].max() >= test["timestamp"].min():
    raise ValueError("Validation overlaps test.")

print("Feature alignment              : PASS")
print("Temporal separation            : PASS")

print("\nTEST SET CLASS DISTRIBUTION")
print("-" * 110)

if y_test[TARGET].sum() == 0:
    print("WARNING: 2025 test set contains ZERO flood positives.")
    print("Temporal test is retained unchanged.")
    print("Phase 13 must report this limitation.")
else:
    print(
        "Test positive rate:",
        f"{y_test[TARGET].mean():.4f}"
    )

print("\nFINAL MASTER")
print("-" * 110)

final_master = df.copy()

final_master.to_csv(
    FINAL_MASTER,
    index=False
)

train_processed.to_csv(
    TRAIN_OUT,
    index=False
)

val_processed.to_csv(
    VAL_OUT,
    index=False
)

test_processed.to_csv(
    TEST_OUT,
    index=False
)

X_train.to_csv(
    X_TRAIN_OUT,
    index=False
)

X_val.to_csv(
    X_VAL_OUT,
    index=False
)

X_test.to_csv(
    X_TEST_OUT,
    index=False
)

y_train.to_csv(
    Y_TRAIN_OUT,
    index=False
)

y_val.to_csv(
    Y_VAL_OUT,
    index=False
)

y_test.to_csv(
    Y_TEST_OUT,
    index=False
)

governance = []

for c in original_columns:

    if c == TARGET:
        category = "TARGET"
        ml_use = "TARGET"

    elif c in label_features:
        category = "LABEL_DERIVED"
        ml_use = "EXCLUDE"

    elif c in metadata:
        category = "METADATA"
        ml_use = "INDEX"

    elif c in constant_features:
        category = "CONSTANT"
        ml_use = "EXCLUDE"

    elif c in high_missing:
        category = "HIGH_MISSINGNESS"
        ml_use = "EXCLUDE"

    elif c in removed_redundant:
        category = "REDUNDANT"
        ml_use = "EXCLUDE"

    elif c in selected:

        if c.startswith("nwp_"):
            category = "NWP_PROXY"

        elif c.startswith("radar_"):
            category = "RADAR_PROXY"

        elif c.startswith("obs_"):
            category = "OBSERVATIONAL_PROXY"

        elif c.startswith("satellite_"):
            category = "SATELLITE_PROXY"

        elif c.startswith("rainfall_"):
            category = "RAINFALL"

        elif c in temporal_features:
            category = "TEMPORAL"

        else:
            category = "ENVIRONMENTAL"

        ml_use = "FINAL"

    else:
        category = "EXCLUDED"
        ml_use = "EXCLUDE"

    governance.append({
        "feature": c,
        "category": category,
        "ml_use": ml_use,
        "dtype": str(df[c].dtype),
        "missing_total": int(df[c].isna().sum()),
    })

governance_df = pd.DataFrame(governance)

governance_df.to_csv(
    FEATURE_REPORT,
    index=False
)

manifest = {
    "phase": "12",
    "dataset": "ChetakAI V1",
    "input": str(INPUT),
    "final_master": str(FINAL_MASTER),

    "rows": int(len(df)),
    "original_columns": int(len(original_columns)),
    "final_ml_features": int(len(selected)),

    "train_rows": int(len(train)),
    "validation_rows": int(len(validation)),
    "test_rows": int(len(test)),

    "train_period": "2015-2022",
    "validation_period": "2023-2024",
    "test_period": "2025",

    "train_positive": int(train[TARGET].sum()),
    "validation_positive": int(validation[TARGET].sum()),
    "test_positive": int(test[TARGET].sum()),

    "duplicate_keys": int(duplicate_keys),

    "label_derived_excluded": int(len(label_features)),
    "constant_excluded": int(len(constant_features)),
    "high_missingness_excluded": int(len(high_missing)),
    "near_exact_redundant_excluded": int(len(removed_redundant)),

    "remaining_missing_values": 0,

    "preprocessing_fit_on": "TRAIN ONLY",
    "random_split": False,

    "proxy_features_are_real_observations": False,

    "phase8_9_10_11_overwritten": False,

    "target_column": TARGET,

    "target_in_X_train": TARGET in X_train.columns,
    "target_in_X_validation": TARGET in X_val.columns,
    "target_in_X_test": TARGET in X_test.columns,

    "test_has_positive_examples": bool(
        y_test[TARGET].sum() > 0
    ),
}

with open(
    MANIFEST,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        manifest,
        f,
        indent=2
    )

print("\n")
print("=" * 110)
print("PHASE 12 FINAL VALIDATION")
print("=" * 110)

print("\nDATASET")
print("-" * 110)
print("Rows                  :", len(df))
print("Original columns      :", len(original_columns))
print("Final ML features     :", len(selected))
print("Duplicate keys        :", duplicate_keys)

print("\nSPLITS")
print("-" * 110)
print("Train rows            :", len(train))
print("Validation rows       :", len(validation))
print("Test rows             :", len(test))

print("\nTARGET")
print("-" * 110)
print("Train positives       :", int(train[TARGET].sum()))
print("Validation positives  :", int(validation[TARGET].sum()))
print("Test positives        :", int(test[TARGET].sum()))

print("\nFEATURE REDUCTION")
print("-" * 110)
print("Label-derived excluded :", len(label_features))
print("Constant excluded      :", len(constant_features))
print("High-missing excluded  :", len(high_missing))
print("Redundant excluded     :", len(removed_redundant))

print("\nMISSING VALUES")
print("-" * 110)
print("X_train NaNs           :", int(X_train.isna().sum().sum()))
print("X_validation NaNs      :", int(X_val.isna().sum().sum()))
print("X_test NaNs            :", int(X_test.isna().sum().sum()))

print("\nTARGET SAFETY")
print("-" * 110)
print("target_flood in X_train      :", TARGET in X_train.columns)
print("target_flood in X_validation :", TARGET in X_val.columns)
print("target_flood in X_test       :", TARGET in X_test.columns)

print("\nTEMPORAL SAFETY")
print("-" * 110)
print("Train → Validation → Test: PASS")

print("\nOUTPUTS")
print("-" * 110)
print("Final master       :", FINAL_MASTER)
print("Train              :", TRAIN_OUT)
print("Validation         :", VAL_OUT)
print("Test               :", TEST_OUT)
print("X_train            :", X_TRAIN_OUT)
print("X_validation       :", X_VAL_OUT)
print("X_test             :", X_TEST_OUT)
print("y_train            :", Y_TRAIN_OUT)
print("y_validation       :", Y_VAL_OUT)
print("y_test             :", Y_TEST_OUT)
print("Feature governance :", FEATURE_REPORT)
print("Correlation report :", CORRELATION_REPORT)
print("Missingness report  :", MISSINGNESS_REPORT)
print("Preprocessing      :", PREPROCESS_REPORT)
print("Manifest           :", MANIFEST)

print("\n")
print("=" * 110)
print("🔥🔥 PHASE 12 PASS — ML DATASET READY FOR PHASE 13")
print("=" * 110)