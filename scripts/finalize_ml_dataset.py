import pandas as pd
import numpy as np
from pathlib import Path

INPUT = Path("data/ml/chetakai_master_dataset.parquet")
OUT_PARQUET = Path("data/ml/chetakai_v1_ml_ready.parquet")
OUT_CSV = Path("data/ml/chetakai_v1_ml_ready.csv")
SUMMARY = Path("data/ml/chetakai_v1_ml_ready_summary.json")

print("=" * 80)
print("CHETAKAI V1 — FINAL ML DATASET CLEANUP")
print("=" * 80)

df = pd.read_parquet(INPUT)

print("INPUT:", df.shape)

# ------------------------------------------------------------
# 1. BASIC SORTING
# ------------------------------------------------------------

df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["basin", "date"]).reset_index(drop=True)

# ------------------------------------------------------------
# 2. REMOVE EXACT DUPLICATE COLUMNS
# ------------------------------------------------------------

feature_cols = [c for c in df.columns if c not in ["basin", "date", "flood_event"]]

seen = {}
drop_cols = []

for c in feature_cols:
    key = df[c].astype(str).fillna("__NA__").to_numpy().tobytes()
    if key in seen:
        drop_cols.append(c)
    else:
        seen[key] = c

if drop_cols:
    df = df.drop(columns=drop_cols)

print("Duplicate columns removed:", len(drop_cols))

# ------------------------------------------------------------
# 3. REMOVE ACCIDENTAL SOURCE-DATA DUPLICATES
# ------------------------------------------------------------

bad_prefixes = [
    "chetakai_v1_master_ml_dataset_",
    "chirps_monthly_basin_features_"
]

# Keep canonical temporal columns and remove repeated source copies.
remove = []

for c in df.columns:
    if any(c.startswith(p) for p in bad_prefixes):
        if c not in [
            "chetakai_v1_master_ml_dataset_year",
            "chetakai_v1_master_ml_dataset_month_number",
            "chetakai_v1_master_ml_dataset_monsoon"
        ]:
            remove.append(c)

df = df.drop(columns=remove, errors="ignore")

print("Redundant source columns removed:", len(remove))

# ------------------------------------------------------------
# 4. IDENTIFY FEATURE TYPES
# ------------------------------------------------------------

id_cols = ["basin", "date", "flood_event"]

numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

numeric_feature_cols = [
    c for c in numeric_cols
    if c not in ["flood_event"]
]

# ------------------------------------------------------------
# 5. DROP FEATURES THAT ARE COMPLETELY EMPTY
# ------------------------------------------------------------

all_missing = [
    c for c in numeric_feature_cols
    if df[c].isna().all()
]

df = df.drop(columns=all_missing)

print("Completely empty features removed:", len(all_missing))

# ------------------------------------------------------------
# 6. REMOVE CONSTANT FEATURES
# ------------------------------------------------------------

numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

constant_cols = [
    c for c in numeric_cols
    if c != "flood_event" and df[c].nunique(dropna=True) <= 1
]

df = df.drop(columns=constant_cols)

print("Constant features removed:", len(constant_cols))

# ------------------------------------------------------------
# 7. BASIN-LEVEL STATIC FEATURES
# ------------------------------------------------------------

# Fill features independently inside each basin.
# Keep basin/date columns untouched.

feature_cols = [
    c for c in df.columns
    if c not in ["basin", "date", "flood_event"]
]

df[feature_cols] = (
    df.groupby("basin", sort=False)[feature_cols]
      .ffill()
      .bfill()
)

# ------------------------------------------------------------
# 8. TEMPORAL RAINFALL / DYNAMIC FEATURES
# ------------------------------------------------------------

# Dynamic numerical features are filled within each basin.
# We use interpolation followed by forward/backward filling.

numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

for c in numeric_cols:
    if c == "flood_event":
        continue

    df[c] = (
        df.groupby("basin")[c]
        .transform(lambda x: x.interpolate(limit_direction="both"))
    )

# ------------------------------------------------------------
# 9. FINAL NUMERIC SANITIZATION
# ------------------------------------------------------------

numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

for c in numeric_cols:
    if c == "flood_event":
        continue

    df[c] = df[c].replace(
        [np.inf, -np.inf],
        np.nan
    )

# Remaining missing numeric values:
# use global median as final MVP fallback.

for c in numeric_cols:
    if c == "flood_event":
        continue

    if df[c].isna().any():
        median = df[c].median()

        if pd.isna(median):
            median = 0.0

        df[c] = df[c].fillna(median)

# ------------------------------------------------------------
# 10. FLOOD LABEL
# ------------------------------------------------------------

df["flood_event"] = df["flood_event"].fillna(0).astype(int)

# ------------------------------------------------------------
# 11. FINAL COLUMN ORDER
# ------------------------------------------------------------

first = ["basin", "date", "flood_event"]

others = [
    c for c in df.columns
    if c not in first
]

df = df[first + others]

# ------------------------------------------------------------
# 12. FINAL VALIDATION
# ------------------------------------------------------------

missing = int(df.isna().sum().sum())
duplicates = int(df.duplicated(["basin", "date"]).sum())

summary = {
    "rows": int(len(df)),
    "columns": int(len(df.columns)),
    "basins": int(df["basin"].nunique()),
    "date_min": str(df["date"].min()),
    "date_max": str(df["date"].max()),
    "flood_positive": int(df["flood_event"].sum()),
    "flood_negative": int((df["flood_event"] == 0).sum()),
    "missing_values": missing,
    "duplicate_basin_dates": duplicates,
    "numeric_features": int(
        len(df.select_dtypes(include=[np.number]).columns) - 1
    )
}

# ------------------------------------------------------------
# 13. SAVE
# ------------------------------------------------------------

OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)

df.to_parquet(
    OUT_PARQUET,
    index=False
)

df.to_csv(
    OUT_CSV,
    index=False
)

import json

with open(SUMMARY, "w") as f:
    json.dump(summary, f, indent=2)

# ------------------------------------------------------------
# REPORT
# ------------------------------------------------------------

print()
print("=" * 80)
print("FINAL ML DATASET READY")
print("=" * 80)

print("ROWS:", summary["rows"])
print("COLUMNS:", summary["columns"])
print("BASINS:", summary["basins"])
print("DATE:", summary["date_min"], "->", summary["date_max"])
print("FLOOD POSITIVE:", summary["flood_positive"])
print("FLOOD NEGATIVE:", summary["flood_negative"])
print("MISSING VALUES:", summary["missing_values"])
print("DUPLICATE BASIN-DATES:", summary["duplicate_basin_dates"])
print("NUMERIC FEATURES:", summary["numeric_features"])

print()
print("PARQUET:", OUT_PARQUET)
print("CSV:", OUT_CSV)
print("SUMMARY:", SUMMARY)

if missing == 0 and duplicates == 0:
    print()
    print("STATUS: ✅ DATA ENGINEERING SIGN-OFF READY")
else:
    print()
    print("STATUS: ⚠️ REVIEW REQUIRED")

print("=" * 80)
