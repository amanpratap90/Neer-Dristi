from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("data/processed")

MASTER = ROOT / "master" / "chetakai_v1_master_phase9.csv"

OUT_DIR = ROOT / "master" / "phase10"

TRAIN_OUT = OUT_DIR / "chetakai_v1_train.csv"
VAL_OUT = OUT_DIR / "chetakai_v1_validation.csv"
TEST_OUT = OUT_DIR / "chetakai_v1_test.csv"

AUDIT_REPORT = OUT_DIR / "phase10_ml_audit_report.csv"
LEAKAGE_REPORT = OUT_DIR / "phase10_leakage_report.csv"

BACKUP = OUT_DIR / "chetakai_v1_master_phase9_backup.csv"


print("=" * 110)
print("CHETAKAI V1 — PHASE 10 ML DATASET AUDIT & TEMPORAL SPLIT")
print("=" * 110)


# ------------------------------------------------------------------
# PATH VALIDATION
# ------------------------------------------------------------------

if not MASTER.exists():
    raise FileNotFoundError(
        f"Phase 9 master dataset not found:\n{MASTER}"
    )


OUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ------------------------------------------------------------------
# LOAD MASTER
# ------------------------------------------------------------------

print("\nLOADING PHASE 9 MASTER")
print("-" * 110)

df = pd.read_csv(MASTER)

print(
    f"Rows: {len(df)}"
)

print(
    f"Columns: {len(df.columns)}"
)


# ------------------------------------------------------------------
# REQUIRED COLUMNS
# ------------------------------------------------------------------

required_columns = [
    "canonical_basin_id",
    "timestamp",
    "target_flood",
]

missing_columns = [
    c for c in required_columns
    if c not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )


# ------------------------------------------------------------------
# TIMESTAMP VALIDATION
# ------------------------------------------------------------------

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)

if df["timestamp"].isna().any():
    raise ValueError(
        "Invalid timestamp values detected."
    )


# ------------------------------------------------------------------
# TARGET VALIDATION
# ------------------------------------------------------------------

print("\nTARGET DETECTION")
print("-" * 110)

TARGET = "target_flood"

print(
    "Target column:",
    TARGET
)

print(
    "Target dtype:",
    df[TARGET].dtype
)

target_values = sorted(
    df[TARGET].dropna().unique().tolist()
)

print(
    "Target values:",
    target_values
)

if set(target_values) - {0, 1}:
    raise ValueError(
        "target_flood must contain only binary 0/1 values."
    )

if df[TARGET].isna().any():
    raise ValueError(
        "Missing target_flood values detected."
    )

df[TARGET] = df[TARGET].astype(int)


# ------------------------------------------------------------------
# BASIC DATASET VALIDATION
# ------------------------------------------------------------------

print("\nDATASET STRUCTURE")
print("-" * 110)

print(
    "Basins:",
    df["canonical_basin_id"].nunique()
)

print(
    "Date range:",
    df["timestamp"].min(),
    "→",
    df["timestamp"].max()
)

duplicate_keys = df.duplicated(
    subset=[
        "canonical_basin_id",
        "timestamp",
    ]
).sum()

print(
    "Duplicate basin/timestamp keys:",
    duplicate_keys
)

if duplicate_keys:
    raise ValueError(
        "Duplicate basin/timestamp keys detected."
    )


# ------------------------------------------------------------------
# TARGET DISTRIBUTION
# ------------------------------------------------------------------

print("\nTARGET DISTRIBUTION")
print("-" * 110)

target_counts = (
    df[TARGET]
    .value_counts()
    .sort_index()
)

for value, count in target_counts.items():

    percentage = (
        count / len(df)
    ) * 100

    label = (
        "FLOOD"
        if value == 1
        else "NO FLOOD"
    )

    print(
        f"{label:10} : "
        f"{count:5} rows "
        f"({percentage:.2f}%)"
    )


print(
    "Positive basins:",
    df.loc[
        df[TARGET] == 1,
        "canonical_basin_id"
    ].nunique()
)


# ------------------------------------------------------------------
# PHASE 9 BACKUP
# ------------------------------------------------------------------

if not BACKUP.exists():

    df.to_csv(
        BACKUP,
        index=False
    )

    print(
        "\nPhase 9 backup created:"
    )

    print(
        BACKUP.resolve()
    )

else:

    print(
        "\nPhase 9 backup already exists:"
    )

    print(
        BACKUP.resolve()
    )


# ------------------------------------------------------------------
# LABEL-LEAKAGE FEATURES
# ------------------------------------------------------------------

print("\nLABEL LEAKAGE ANALYSIS")
print("-" * 110)

label_derived_features = [
    "flood_event_count",
    "flood_severity_score",
    "flood_area_affected",
    "flood_fatalities",
    "flood_injured",
    "flood_displaced",
    "flood_animal_fatalities",
    "flood_duration_days",
    "flood_event_flag",
    "target_flood",
]

leakage_rows = []

for col in label_derived_features:

    if col not in df.columns:
        continue

    leakage_rows.append(
        {
            "feature": col,
            "category": "label_derived",
            "action": "exclude_from_ml_features",
            "reason": "Derived from flood event labels/outcomes",
        }
    )

    print(
        f"  EXCLUDE: {col}"
    )


# ------------------------------------------------------------------
# IDENTIFY ID / METADATA FEATURES
# ------------------------------------------------------------------

print("\nIDENTIFIER / METADATA ANALYSIS")
print("-" * 110)

identifier_features = [
    "canonical_basin_id",
    "timestamp",
    "basin",
    "date",
    "year",
    "month",
]

for col in identifier_features:

    if col in df.columns:

        print(
            f"  METADATA: {col}"
        )


# ------------------------------------------------------------------
# TEMPORAL FEATURE POLICY
# ------------------------------------------------------------------

print("\nTEMPORAL FEATURE POLICY")
print("-" * 110)

print(
    "Year/month columns retained as model features."
)

print(
    "Timestamp and basin ID retained for dataset indexing."
)

print(
    "Random train/test splitting is NOT used."
)


# ------------------------------------------------------------------
# BUILD ML FEATURE LIST
# ------------------------------------------------------------------

excluded_columns = set(
    label_derived_features
)

excluded_columns.update(
    [
        "canonical_basin_id",
        "timestamp",
    ]
)

ml_feature_columns = [
    c
    for c in df.columns
    if c not in excluded_columns
]


# ------------------------------------------------------------------
# NUMERIC ML FEATURES
# ------------------------------------------------------------------

numeric_ml_features = (
    df[ml_feature_columns]
    .select_dtypes(
        include=[np.number]
    )
    .columns
    .tolist()
)

non_numeric_ml_features = [
    c
    for c in ml_feature_columns
    if c not in numeric_ml_features
]


print("\nML FEATURE INVENTORY")
print("-" * 110)

print(
    "Total candidate ML features:",
    len(ml_feature_columns)
)

print(
    "Numeric ML features:",
    len(numeric_ml_features)
)

print(
    "Non-numeric ML features:",
    len(non_numeric_ml_features)
)

if non_numeric_ml_features:

    print(
        "\nNon-numeric features requiring encoding:"
    )

    for col in non_numeric_ml_features:

        print(
            f"  {col}"
        )


# ------------------------------------------------------------------
# MISSINGNESS AUDIT
# ------------------------------------------------------------------

print("\nMISSINGNESS AUDIT")
print("-" * 110)

missing_rows = []

for col in ml_feature_columns:

    null_count = int(
        df[col].isna().sum()
    )

    if null_count > 0:

        percentage = (
            null_count / len(df)
        ) * 100

        missing_rows.append(
            {
                "feature": col,
                "null_count": null_count,
                "null_percentage": percentage,
            }
        )

        print(
            f"  {col}: "
            f"{null_count} nulls "
            f"({percentage:.2f}%)"
        )


print(
    "Features with missing values:",
    len(missing_rows)
)


# ------------------------------------------------------------------
# TEMPORAL SPLIT
# ------------------------------------------------------------------

print("\nTEMPORAL TRAIN / VALIDATION / TEST SPLIT")
print("-" * 110)

print(
    "Strategy:"
)

print(
    "TRAIN      = 2015–2022"
)

print(
    "VALIDATION = 2023–2024"
)

print(
    "TEST       = 2025"
)


train = df[
    df["timestamp"].dt.year <= 2022
].copy()

validation = df[
    df["timestamp"].dt.year.isin(
        [2023, 2024]
    )
].copy()

test = df[
    df["timestamp"].dt.year == 2025
].copy()


# ------------------------------------------------------------------
# SPLIT VALIDATION
# ------------------------------------------------------------------

print("\nSPLIT DISTRIBUTION")
print("-" * 110)


def print_split_stats(
    name,
    data
):

    positives = int(
        data[TARGET].sum()
    )

    negatives = (
        len(data) - positives
    )

    positive_rate = (
        positives / len(data) * 100
        if len(data)
        else 0
    )

    print(
        f"\n{name}"
    )

    print(
        f"  Rows       : {len(data)}"
    )

    print(
        f"  Basins     : "
        f"{data['canonical_basin_id'].nunique()}"
    )

    print(
        f"  Date range : "
        f"{data['timestamp'].min()} → "
        f"{data['timestamp'].max()}"
    )

    print(
        f"  Flood      : {positives}"
    )

    print(
        f"  No flood   : {negatives}"
    )

    print(
        f"  Positive % : "
        f"{positive_rate:.2f}%"
    )


print_split_stats(
    "TRAIN",
    train
)

print_split_stats(
    "VALIDATION",
    validation
)

print_split_stats(
    "TEST",
    test
)


# ------------------------------------------------------------------
# EMPTY SPLIT VALIDATION
# ------------------------------------------------------------------

if len(train) == 0:
    raise ValueError(
        "Training split is empty."
    )

if len(validation) == 0:
    raise ValueError(
        "Validation split is empty."
    )

if len(test) == 0:
    raise ValueError(
        "Test split is empty."
    )


# ------------------------------------------------------------------
# TEMPORAL ORDER VALIDATION
# ------------------------------------------------------------------

print("\nTEMPORAL ORDER VALIDATION")
print("-" * 110)

if train["timestamp"].max() >= validation["timestamp"].min():

    raise ValueError(
        "Temporal leakage detected between train and validation."
    )

if validation["timestamp"].max() >= test["timestamp"].min():

    raise ValueError(
        "Temporal leakage detected between validation and test."
    )

print(
    "Train → Validation → Test ordering: PASS"
)


# ------------------------------------------------------------------
# BASIN COVERAGE VALIDATION
# ------------------------------------------------------------------

train_basins = set(
    train["canonical_basin_id"]
)

validation_basins = set(
    validation["canonical_basin_id"]
)

test_basins = set(
    test["canonical_basin_id"]
)

print(
    "\nBASIN COVERAGE"
)

print(
    "Train basins:",
    len(train_basins)
)

print(
    "Validation basins:",
    len(validation_basins)
)

print(
    "Test basins:",
    len(test_basins)
)

print(
    "Validation basins unseen in train:",
    len(
        validation_basins - train_basins
    )
)

print(
    "Test basins unseen in train:",
    len(
        test_basins - train_basins
    )
)


# ------------------------------------------------------------------
# SAVE SPLITS
# ------------------------------------------------------------------

train.to_csv(
    TRAIN_OUT,
    index=False
)

validation.to_csv(
    VAL_OUT,
    index=False
)

test.to_csv(
    TEST_OUT,
    index=False
)


# ------------------------------------------------------------------
# SAVE LEAKAGE REPORT
# ------------------------------------------------------------------

leakage_report = pd.DataFrame(
    leakage_rows
)

leakage_report.to_csv(
    LEAKAGE_REPORT,
    index=False
)


# ------------------------------------------------------------------
# SAVE AUDIT REPORT
# ------------------------------------------------------------------

audit_rows = []

for name, data in [
    ("train", train),
    ("validation", validation),
    ("test", test),
]:

    audit_rows.append(
        {
            "split": name,
            "rows": len(data),
            "basins": data[
                "canonical_basin_id"
            ].nunique(),
            "positive_rows": int(
                data[TARGET].sum()
            ),
            "negative_rows": int(
                (data[TARGET] == 0).sum()
            ),
            "positive_percentage": (
                data[TARGET].mean() * 100
            ),
            "start_date": data[
                "timestamp"
            ].min(),
            "end_date": data[
                "timestamp"
            ].max(),
        }
    )


audit_report = pd.DataFrame(
    audit_rows
)

audit_report.to_csv(
    AUDIT_REPORT,
    index=False
)


# ------------------------------------------------------------------
# FINAL REPORT
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("🔥 PHASE 10 ML DATASET AUDIT COMPLETE")
print("=" * 110)

print(
    "Total rows:",
    len(df)
)

print(
    "Total columns:",
    len(df.columns)
)

print(
    "ML numeric features:",
    len(numeric_ml_features)
)

print(
    "Label-derived features excluded:",
    len(leakage_rows)
)

print(
    "Train rows:",
    len(train)
)

print(
    "Validation rows:",
    len(validation)
)

print(
    "Test rows:",
    len(test)
)

print(
    "Temporal leakage:",
    "NONE"
)

print(
    "Duplicate keys:",
    df.duplicated(
        subset=[
            "canonical_basin_id",
            "timestamp",
        ]
    ).sum()
)

print("\nOUTPUT FILES")

print(
    "TRAIN:"
)

print(
    TRAIN_OUT.resolve()
)

print(
    "\nVALIDATION:"
)

print(
    VAL_OUT.resolve()
)

print(
    "\nTEST:"
)

print(
    TEST_OUT.resolve()
)

print(
    "\nAUDIT REPORT:"
)

print(
    AUDIT_REPORT.resolve()
)

print(
    "\nLEAKAGE REPORT:"
)

print(
    LEAKAGE_REPORT.resolve()
)

print("\n" + "=" * 110)
print("🔥🔥 PHASE 10 PASS")
print("=" * 110)
