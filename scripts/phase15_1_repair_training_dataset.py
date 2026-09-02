from pathlib import Path
import json
import numpy as np
import pandas as pd


ROOT = Path("data/processed")
PHASE12 = ROOT / "master" / "phase12" / "chetakai_v1_master_phase12.csv"
FLOOD_EVENTS = ROOT / "flood_events" / "flood_events_model_ready.csv"

OUT_DIR = ROOT / "training" / "phase15_1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MASTER_OUT = OUT_DIR / "clean_supervised_master.csv"
TRAIN_OUT = OUT_DIR / "train.csv"
VAL_OUT = OUT_DIR / "validation.csv"
TEST_OUT = OUT_DIR / "test.csv"
UNLABELED_OUT = OUT_DIR / "unlabeled_inference.csv"
MANIFEST_OUT = OUT_DIR / "feature_manifest.json"
REPORT_OUT = OUT_DIR / "phase15_1_report.txt"


TARGET = "target_flood"

LEAKAGE_COLUMNS = {
    "target_flood",
    "flood_event_flag",
    "flood_event_count",
    "flood_severity_score",
    "flood_area_affected",
    "flood_fatalities",
    "flood_injured",
    "flood_displaced",
    "flood_animal_fatalities",
    "flood_duration_days",
}

IDENTITY_COLUMNS = {
    "canonical_basin_id",
    "basin_id",
    "ba_code",
}

CALENDAR_COLUMNS = {
    "year",
    "month",
    "day",
    "day_of_year",
    "week",
    "weekofyear",
    "quarter",
    "calendar_year",
    "fiscal_year",
}

TEXT_COLUMNS = {
    "reservoir_geometry_type",
    "soil_texture_proxy",
}


print("=" * 110)
print("CHETAKAI V1 — PHASE 15.1 LABEL + FEATURE REPAIR")
print("=" * 110)


# ------------------------------------------------------------------
# LOAD
# ------------------------------------------------------------------

if not PHASE12.exists():
    raise FileNotFoundError(f"Phase 12 master not found:\n{PHASE12}")

if not FLOOD_EVENTS.exists():
    raise FileNotFoundError(f"Flood inventory not found:\n{FLOOD_EVENTS}")

master = pd.read_csv(PHASE12)
events = pd.read_csv(FLOOD_EVENTS)

print("\nINPUT")
print("-" * 110)
print("Phase 12 rows    :", len(master))
print("Phase 12 columns :", len(master.columns))
print("Flood events     :", len(events))


# ------------------------------------------------------------------
# BASIC VALIDATION
# ------------------------------------------------------------------

required = [
    "canonical_basin_id",
    "timestamp",
    TARGET,
]

missing = [c for c in required if c not in master.columns]

if missing:
    raise ValueError(f"Missing required columns: {missing}")

master["timestamp"] = pd.to_datetime(
    master["timestamp"],
    errors="coerce"
)

events["start_date"] = pd.to_datetime(
    events["start_date"],
    errors="coerce"
)

if master["timestamp"].isna().any():
    raise ValueError("Invalid timestamps found in Phase 12.")

if events["start_date"].isna().all():
    raise ValueError("Flood inventory contains no valid dates.")


# ------------------------------------------------------------------
# DETERMINE LABEL COVERAGE FROM ACTUAL FLOOD INVENTORY
# ------------------------------------------------------------------

inventory_min_year = int(events["start_date"].dt.year.min())
inventory_max_year = int(events["start_date"].dt.year.max())

print("\nFLOOD INVENTORY COVERAGE")
print("-" * 110)
print("Inventory start year :", inventory_min_year)
print("Inventory end year   :", inventory_max_year)

master_min_year = int(master["timestamp"].dt.year.min())
master_max_year = int(master["timestamp"].dt.year.max())

if inventory_max_year < master_max_year:
    print(
        f"\nWARNING: Master extends to {master_max_year}, "
        f"but flood inventory ends at {inventory_max_year}."
    )


# ------------------------------------------------------------------
# RECONSTRUCT TARGET ONLY INSIDE OBSERVED LABEL COVERAGE
# ------------------------------------------------------------------

master["label_available"] = (
    master["timestamp"].dt.year <= inventory_max_year
).astype("int8")


# Existing Phase 9/12 target is trusted ONLY inside label coverage.
# Outside coverage it becomes missing/unlabeled.

master["supervised_target"] = master[TARGET].where(
    master["label_available"] == 1,
    np.nan
)


# ------------------------------------------------------------------
# TARGET VALIDATION
# ------------------------------------------------------------------

supervised = master[
    master["label_available"] == 1
].copy()

unlabeled = master[
    master["label_available"] == 0
].copy()

print("\nLABEL COVERAGE")
print("-" * 110)
print("Supervised rows :", len(supervised))
print("Unlabeled rows  :", len(unlabeled))
print(
    "Supervised period:",
    supervised["timestamp"].min().date(),
    "->",
    supervised["timestamp"].max().date()
)
print(
    "Unlabeled period :",
    (
        unlabeled["timestamp"].min().date()
        if len(unlabeled)
        else "NONE"
    ),
    "->",
    (
        unlabeled["timestamp"].max().date()
        if len(unlabeled)
        else "NONE"
    )
)

print("\nSUPERVISED TARGET")
print("-" * 110)
print(
    supervised["supervised_target"]
    .value_counts()
    .sort_index()
)

positive = int(
    (supervised["supervised_target"] == 1).sum()
)

negative = int(
    (supervised["supervised_target"] == 0).sum()
)

print("Flood positives :", positive)
print("Flood negatives :", negative)
print(
    "Flood rate      :",
    f"{positive / len(supervised) * 100:.2f}%"
)


# ------------------------------------------------------------------
# REMOVE TARGET-RELATED COLUMNS
# ------------------------------------------------------------------

drop_leakage = [
    c for c in LEAKAGE_COLUMNS
    if c in master.columns
]

print("\nLEAKAGE REMOVAL")
print("-" * 110)
print("Removed:", len(drop_leakage))

for c in drop_leakage:
    print(" -", c)


# ------------------------------------------------------------------
# FEATURE INVENTORY
# ------------------------------------------------------------------

protected = {
    "timestamp",
    "label_available",
    "supervised_target",
}

candidate_columns = [
    c for c in master.columns
    if c not in drop_leakage
    and c not in protected
]

# Remove explicit calendar features.
calendar_removed = [
    c for c in candidate_columns
    if c.lower() in CALENDAR_COLUMNS
]

candidate_columns = [
    c for c in candidate_columns
    if c.lower() not in CALENDAR_COLUMNS
]

# Remove identity fields.
identity_removed = [
    c for c in candidate_columns
    if c.lower() in IDENTITY_COLUMNS
]

candidate_columns = [
    c for c in candidate_columns
    if c.lower() not in IDENTITY_COLUMNS
]


# ------------------------------------------------------------------
# NUMERIC FEATURES
# ------------------------------------------------------------------

numeric_features = []

non_numeric_features = []

for c in candidate_columns:
    if pd.api.types.is_numeric_dtype(master[c]):
        numeric_features.append(c)
    else:
        non_numeric_features.append(c)


print("\nFEATURE INVENTORY")
print("-" * 110)
print("Candidates             :", len(candidate_columns))
print("Numeric                :", len(numeric_features))
print("Non-numeric            :", len(non_numeric_features))
print("Calendar removed       :", calendar_removed)
print("Identity removed       :", identity_removed)

if non_numeric_features:
    print("\nNon-numeric excluded:")
    for c in non_numeric_features:
        print(" -", c)


# ------------------------------------------------------------------
# MISSINGNESS AUDIT
# ------------------------------------------------------------------

missing_pct = (
    master[numeric_features]
    .isna()
    .mean()
    .mul(100)
)

high_missing = missing_pct[
    missing_pct >= 50
].index.tolist()

print("\nMISSINGNESS")
print("-" * 110)
print("Numeric features:", len(numeric_features))
print(">=50% missing   :", len(high_missing))

for c in high_missing:
    print(
        f" - {c}: {missing_pct[c]:.2f}%"
    )


# ------------------------------------------------------------------
# REMOVE HIGH-MISSING FEATURES
# ------------------------------------------------------------------

usable_features = [
    c for c in numeric_features
    if c not in high_missing
]


# ------------------------------------------------------------------
# INFINITY AUDIT
# ------------------------------------------------------------------

infinity_features = []

for c in usable_features:
    values = pd.to_numeric(
        master[c],
        errors="coerce"
    )

    if np.isinf(values.to_numpy()).any():
        infinity_features.append(c)

print("\nINFINITY AUDIT")
print("-" * 110)
print("Features containing infinity:", len(infinity_features))

for c in infinity_features:
    print(" -", c)


# ------------------------------------------------------------------
# CLEAN INF
# ------------------------------------------------------------------

for c in usable_features:
    master[c] = pd.to_numeric(
        master[c],
        errors="coerce"
    )

master[usable_features] = master[
    usable_features
].replace(
    [np.inf, -np.inf],
    np.nan
)


# ------------------------------------------------------------------
# CONSTANT FEATURES
# ------------------------------------------------------------------

constant_features = []

for c in usable_features:
    if master[c].nunique(dropna=True) <= 1:
        constant_features.append(c)

usable_features = [
    c for c in usable_features
    if c not in constant_features
]

print("\nCONSTANT FEATURES")
print("-" * 110)
print("Removed:", len(constant_features))

for c in constant_features:
    print(" -", c)


# ------------------------------------------------------------------
# FINAL FEATURE LIST
# ------------------------------------------------------------------

print("\nFINAL MODEL FEATURE CONTRACT")
print("-" * 110)
print("Final numeric features:", len(usable_features))

for i, c in enumerate(usable_features, 1):
    print(f"{i:3d}. {c}")


# ------------------------------------------------------------------
# BUILD SUPERVISED DATASET
# ------------------------------------------------------------------

supervised = master[
    master["label_available"] == 1
].copy()

supervised[TARGET] = (
    supervised["supervised_target"]
    .astype("int8")
)


# ------------------------------------------------------------------
# TEMPORAL SPLIT
#
# 2015-2021 TRAIN
# 2022 VALIDATION
# 2023 TEST
# ------------------------------------------------------------------

supervised_year = supervised[
    "timestamp"
].dt.year

train = supervised[
    supervised_year <= 2021
].copy()

validation = supervised[
    supervised_year == 2022
].copy()

test = supervised[
    supervised_year == 2023
].copy()


if train.empty or validation.empty or test.empty:
    raise RuntimeError(
        "One or more temporal splits are empty."
    )


# ------------------------------------------------------------------
# SHUFFLE TRAIN ONLY
# ------------------------------------------------------------------

train = train.sample(
    frac=1,
    random_state=42
).reset_index(drop=True)

validation = validation.sort_values(
    ["timestamp", "canonical_basin_id"]
).reset_index(drop=True)

test = test.sort_values(
    ["timestamp", "canonical_basin_id"]
).reset_index(drop=True)


# ------------------------------------------------------------------
# SELECT MODEL COLUMNS
# ------------------------------------------------------------------

metadata_columns = [
    "canonical_basin_id",
    "timestamp",
]

model_columns = (
    metadata_columns
    + usable_features
    + [TARGET]
)


train_out = train[
    model_columns
].copy()

validation_out = validation[
    model_columns
].copy()

test_out = test[
    model_columns
].copy()


# ------------------------------------------------------------------
# UNLABELED INFERENCE DATA
# ------------------------------------------------------------------

unlabeled_out = unlabeled[
    metadata_columns + usable_features
].copy()

unlabeled_out = unlabeled_out.sort_values(
    ["timestamp", "canonical_basin_id"]
).reset_index(drop=True)


# ------------------------------------------------------------------
# FINAL DATA QUALITY CHECK
# ------------------------------------------------------------------

print("\nFINAL DATA QUALITY")
print("-" * 110)

for name, df in [
    ("TRAIN", train_out),
    ("VALIDATION", validation_out),
    ("TEST", test_out),
]:

    X = df[usable_features]

    print(
        f"{name:<12}",
        "rows=", len(df),
        "features=", len(usable_features),
        "missing=", int(X.isna().sum().sum()),
        "inf=", int(
            np.isinf(
                X.to_numpy(
                    dtype=float,
                    na_value=np.nan
                )
            ).sum()
        ),
        "flood=", int(df[TARGET].sum()),
        "rate=",
        f"{df[TARGET].mean() * 100:.2f}%"
    )


# ------------------------------------------------------------------
# SAVE
# ------------------------------------------------------------------

clean_master = supervised[
    metadata_columns
    + usable_features
    + [TARGET]
].copy()

clean_master.to_csv(
    MASTER_OUT,
    index=False
)

train_out.to_csv(
    TRAIN_OUT,
    index=False
)

validation_out.to_csv(
    VAL_OUT,
    index=False
)

test_out.to_csv(
    TEST_OUT,
    index=False
)

unlabeled_out.to_csv(
    UNLABELED_OUT,
    index=False
)


# ------------------------------------------------------------------
# MANIFEST
# ------------------------------------------------------------------

manifest = {
    "phase": "15.1",
    "purpose": "label repair and ML feature contract",
    "source_master": str(PHASE12),
    "source_flood_inventory": str(FLOOD_EVENTS),
    "inventory_start_year": inventory_min_year,
    "inventory_end_year": inventory_max_year,
    "master_start_year": master_min_year,
    "master_end_year": master_max_year,
    "label_rule": (
        "supervised labels are valid only through the "
        "latest year covered by the flood inventory"
    ),
    "unlabeled_years": sorted(
        unlabeled["timestamp"].dt.year.unique().tolist()
    ),
    "target": TARGET,
    "leakage_columns_removed": drop_leakage,
    "calendar_columns_removed": calendar_removed,
    "identity_columns_removed": identity_removed,
    "non_numeric_columns_removed": non_numeric_features,
    "high_missing_columns_removed": high_missing,
    "constant_columns_removed": constant_features,
    "model_feature_count": len(usable_features),
    "model_features": usable_features,
    "splits": {
        "train": {
            "period": "2015-2021",
            "rows": len(train_out),
            "positive": int(train_out[TARGET].sum()),
            "negative": int(
                (train_out[TARGET] == 0).sum()
            ),
        },
        "validation": {
            "period": "2022",
            "rows": len(validation_out),
            "positive": int(validation_out[TARGET].sum()),
            "negative": int(
                (validation_out[TARGET] == 0).sum()
            ),
        },
        "test": {
            "period": "2023",
            "rows": len(test_out),
            "positive": int(test_out[TARGET].sum()),
            "negative": int(
                (test_out[TARGET] == 0).sum()
            ),
        },
        "unlabeled_inference": {
            "rows": len(unlabeled_out),
            "period": (
                f"{unlabeled_out.timestamp.min()}"
                f" -> "
                f"{unlabeled_out.timestamp.max()}"
                if len(unlabeled_out)
                else None
            ),
        },
    },
}


with open(
    MANIFEST_OUT,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        manifest,
        f,
        indent=2
    )


# ------------------------------------------------------------------
# REPORT
# ------------------------------------------------------------------

report = f"""
CHETAKAI V1 — PHASE 15.1 REPORT

INPUT
Phase 12 rows: {len(master)}
Phase 12 columns: {len(master.columns)}

FLOOD INVENTORY
Coverage: {inventory_min_year} -> {inventory_max_year}

LABEL COVERAGE
Supervised rows: {len(supervised)}
Unlabeled rows: {len(unlabeled)}

SUPERVISED TARGET
Positive: {positive}
Negative: {negative}
Positive rate: {positive / len(supervised) * 100:.2f}%

FEATURE CONTRACT
Final features: {len(usable_features)}
High missing removed: {len(high_missing)}
Constant removed: {len(constant_features)}
Non-numeric removed: {len(non_numeric_features)}
Calendar removed: {len(calendar_removed)}
Identity removed: {len(identity_removed)}

SPLITS
Train: 2015-2021 = {len(train_out)}
Validation: 2022 = {len(validation_out)}
Test: 2023 = {len(test_out)}
Unlabeled inference = {len(unlabeled_out)}

OUTPUTS
{MASTER_OUT}
{TRAIN_OUT}
{VAL_OUT}
{TEST_OUT}
{UNLABELED_OUT}
{MANIFEST_OUT}

STATUS
PASS — Phase 15.1 repaired training contract.
"""

REPORT_OUT.write_text(
    report.strip(),
    encoding="utf-8"
)

print("\n" + "=" * 110)
print("PHASE 15.1 COMPLETE")
print("=" * 110)
print("Clean master       :", MASTER_OUT)
print("Train              :", TRAIN_OUT)
print("Validation         :", VAL_OUT)
print("Test               :", TEST_OUT)
print("Unlabeled inference:", UNLABELED_OUT)
print("Manifest           :", MANIFEST_OUT)
print("\nSTATUS: PASS")
print("=" * 110)
