from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

BASE = Path("data/processed/training/phase15_1")

TRAIN = BASE / "train.csv"
VAL = BASE / "validation.csv"
TEST = BASE / "test.csv"
MANIFEST = BASE / "feature_manifest.json"

OUT = Path("data/processed/models/phase17")
OUT.mkdir(parents=True, exist_ok=True)

REPORT = OUT / "phase17_readiness_report.txt"


def section(title):
    print("\n" + "=" * 110)
    print(title)
    print("=" * 110)


def fmt(x):
    if pd.isna(x):
        return "NA"
    return f"{x:.4f}"


print("=" * 110)
print("CHETAKAI V1 — PHASE 17 MODEL READINESS & GENERALIZATION AUDIT")
print("=" * 110)

print("\nLOADING DATA")
print("-" * 110)

train = pd.read_csv(TRAIN)
val = pd.read_csv(VAL)
test = pd.read_csv(TEST)

with open(MANIFEST, "r", encoding="utf-8") as f:
    manifest = json.load(f)

print(f"Train      : {train.shape}")
print(f"Validation : {val.shape}")
print(f"Test       : {test.shape}")

TARGET = "target_flood"
META = ["canonical_basin_id", "timestamp"]

for df in [train, val, test]:
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

feature_cols = [
    c for c in train.columns
    if c not in META + [TARGET]
    and pd.api.types.is_numeric_dtype(train[c])
]

report = []

def log(line=""):
    print(line)
    report.append(str(line))


# =============================================================================
# 1. BASIC CONTRACT
# =============================================================================

section("1. FEATURE CONTRACT")

log(f"Manifest feature count : {manifest.get('model_feature_count')}")
log(f"Actual numeric features: {len(feature_cols)}")
log(f"Target                 : {TARGET}")
log(f"Metadata               : {META}")

if len(feature_cols) == manifest.get("model_feature_count"):
    log("STATUS: PASS — feature count matches manifest")
else:
    log("STATUS: FAIL — feature count mismatch")


# =============================================================================
# 2. YEAR DISTRIBUTION
# =============================================================================

section("2. TEMPORAL DISTRIBUTION")

log("TRAIN")
log(train["timestamp"].dt.year.value_counts().sort_index().to_string())

log("\nVALIDATION")
log(val["timestamp"].dt.year.value_counts().sort_index().to_string())

log("\nTEST")
log(test["timestamp"].dt.year.value_counts().sort_index().to_string())


# =============================================================================
# 3. TARGET BY YEAR
# =============================================================================

section("3. FLOOD RATE BY YEAR")

all_data = pd.concat(
    [
        train.assign(split="train"),
        val.assign(split="validation"),
        test.assign(split="test"),
    ],
    ignore_index=True
)

year_table = (
    all_data
    .groupby(all_data["timestamp"].dt.year)
    .agg(
        rows=(TARGET, "size"),
        floods=(TARGET, "sum"),
        flood_rate=(TARGET, "mean")
    )
)

log(year_table.to_string())


# =============================================================================
# 4. TARGET BY MONTH
# =============================================================================

section("4. FLOOD RATE BY MONTH")

month_table = (
    all_data
    .groupby(all_data["timestamp"].dt.month)
    .agg(
        rows=(TARGET, "size"),
        floods=(TARGET, "sum"),
        flood_rate=(TARGET, "mean")
    )
)

log(month_table.to_string())


# =============================================================================
# 5. BASIN DISTRIBUTION
# =============================================================================

section("5. BASIN DISTRIBUTION")

for name, df in [
    ("TRAIN", train),
    ("VALIDATION", val),
    ("TEST", test),
]:
    log(f"\n{name}")
    log(
        df["canonical_basin_id"]
        .value_counts()
        .sort_index()
        .to_string()
    )


# =============================================================================
# 6. BASIN FLOOD RATE
# =============================================================================

section("6. FLOOD RATE BY BASIN")

basin_table = (
    all_data
    .groupby("canonical_basin_id")
    .agg(
        rows=(TARGET, "size"),
        floods=(TARGET, "sum"),
        flood_rate=(TARGET, "mean")
    )
    .sort_values("flood_rate", ascending=False)
)

log(basin_table.to_string())


# =============================================================================
# 7. BASIN × SPLIT
# =============================================================================

section("7. BASIN × SPLIT")

basin_split = pd.crosstab(
    all_data["canonical_basin_id"],
    all_data["split"]
)

log(basin_split.to_string())


# =============================================================================
# 8. FEATURE DISTRIBUTION SHIFT
# =============================================================================

section("8. FEATURE DISTRIBUTION SHIFT")

rows = []

for col in feature_cols:
    tr = pd.to_numeric(train[col], errors="coerce")
    va = pd.to_numeric(val[col], errors="coerce")
    te = pd.to_numeric(test[col], errors="coerce")

    tr_mean = tr.mean()
    va_mean = va.mean()
    te_mean = te.mean()

    tr_std = tr.std()
    va_std = va.std()
    te_std = te.std()

    mean_shift_val = abs(va_mean - tr_mean) / (abs(tr_mean) + 1e-9)
    mean_shift_test = abs(te_mean - tr_mean) / (abs(tr_mean) + 1e-9)

    missing_train = tr.isna().mean()
    missing_val = va.isna().mean()
    missing_test = te.isna().mean()

    rows.append({
        "feature": col,
        "train_mean": tr_mean,
        "val_mean": va_mean,
        "test_mean": te_mean,
        "mean_shift_val": mean_shift_val,
        "mean_shift_test": mean_shift_test,
        "train_missing": missing_train,
        "val_missing": missing_val,
        "test_missing": missing_test,
    })

shift = pd.DataFrame(rows)

shift = shift.sort_values(
    "mean_shift_val",
    ascending=False
)

log("\nTOP 30 VALIDATION DISTRIBUTION SHIFTS")
log(
    shift[
        [
            "feature",
            "mean_shift_val",
            "train_mean",
            "val_mean",
            "train_missing",
            "val_missing"
        ]
    ]
    .head(30)
    .to_string(index=False)
)


# =============================================================================
# 9. MISSINGNESS SHIFT
# =============================================================================

section("9. MISSINGNESS SHIFT")

missing_rows = []

for col in feature_cols:
    a = train[col].isna().mean()
    b = val[col].isna().mean()
    c = test[col].isna().mean()

    missing_rows.append({
        "feature": col,
        "train_missing": a,
        "validation_missing": b,
        "test_missing": c,
        "val_minus_train": b - a,
        "test_minus_train": c - a,
    })

missing = pd.DataFrame(missing_rows)

log(
    missing
    .sort_values("val_minus_train", ascending=False)
    .head(30)
    .to_string(index=False)
)


# =============================================================================
# 10. FEATURE CORRELATION WITH TARGET
# =============================================================================

section("10. TARGET ASSOCIATION")

corr_rows = []

for col in feature_cols:
    try:
        x = train[col]
        y = train[TARGET]

        corr = x.corr(y)

        corr_rows.append({
            "feature": col,
            "correlation": corr,
            "abs_correlation": abs(corr) if not pd.isna(corr) else 0,
        })
    except Exception:
        pass

corr_df = pd.DataFrame(corr_rows)

log("\nTOP POSITIVE ASSOCIATIONS")
log(
    corr_df
    .sort_values("correlation", ascending=False)
    .head(25)
    .to_string(index=False)
)

log("\nTOP NEGATIVE ASSOCIATIONS")
log(
    corr_df
    .sort_values("correlation", ascending=True)
    .head(25)
    .to_string(index=False)
)


# =============================================================================
# 11. SUSPICIOUS FEATURE NAMES
# =============================================================================

section("11. FEATURE SEMANTIC AUDIT")

suspicious_terms = [
    "flood",
    "event",
    "affected",
    "fatal",
    "injured",
    "displaced",
    "severity",
    "duration",
]

suspicious = []

for col in feature_cols:
    lower = col.lower()

    hits = [
        term for term in suspicious_terms
        if term in lower
    ]

    if hits:
        suspicious.append({
            "feature": col,
            "matched_terms": ",".join(hits)
        })

if suspicious:
    suspicious_df = pd.DataFrame(suspicious)
    log(suspicious_df.to_string(index=False))
else:
    log("No suspicious flood/event-derived feature names detected.")


# =============================================================================
# 12. CONSTANT / NEAR CONSTANT
# =============================================================================

section("12. LOW-VARIANCE FEATURES")

low_variance = []

for col in feature_cols:
    nunique = train[col].nunique(dropna=True)

    if nunique <= 2:
        low_variance.append({
            "feature": col,
            "unique_values": nunique
        })

if low_variance:
    log(pd.DataFrame(low_variance).to_string(index=False))
else:
    log("No binary/near-constant numerical features requiring removal.")


# =============================================================================
# 13. DUPLICATE ROWS
# =============================================================================

section("13. DUPLICATE AUDIT")

for name, df in [
    ("TRAIN", train),
    ("VALIDATION", val),
    ("TEST", test),
]:
    duplicate_count = df.duplicated(
        subset=feature_cols + [TARGET]
    ).sum()

    log(f"{name} duplicate rows: {duplicate_count}")


# =============================================================================
# 14. TRAIN/VALIDATION OVERLAP
# =============================================================================

section("14. TRAIN / VALIDATION FEATURE OVERLAP")

train_keys = set(
    train[feature_cols]
    .fillna(-999999)
    .astype(str)
    .agg("|".join, axis=1)
)

val_keys = set(
    val[feature_cols]
    .fillna(-999999)
    .astype(str)
    .agg("|".join, axis=1)
)

overlap = len(train_keys.intersection(val_keys))

log(f"Exact feature-vector overlap: {overlap}")


# =============================================================================
# 15. LOCATION INFORMATION
# =============================================================================

section("15. LOCATION FEATURE AUDIT")

location_candidates = [
    c for c in feature_cols
    if any(
        term in c.lower()
        for term in [
            "lat",
            "lon",
            "latitude",
            "longitude",
            "elevation",
            "slope",
            "river",
            "basin",
            "distance"
        ]
    )
]

log("\nLocation / spatial related features:")
log("\n".join(location_candidates))


# =============================================================================
# 16. TRAIN / VALIDATION / TEST SUMMARY
# =============================================================================

section("16. FINAL READINESS SUMMARY")

for name, df in [
    ("TRAIN", train),
    ("VALIDATION", val),
    ("TEST", test),
]:
    positives = int(df[TARGET].sum())
    rows_count = len(df)

    log(
        f"{name:12s} rows={rows_count:4d} "
        f"positive={positives:4d} "
        f"rate={positives / rows_count:.2%}"
    )

log("\nCURRENT BASELINE:")
log("Logistic Regression")
log("Validation ROC-AUC : 0.7624")
log("Validation PR-AUC  : 0.6036")
log("Validation F1      : 0.6351")

log("\nPHASE 17 STATUS:")
log("AUDIT COMPLETE")
log(f"Report: {REPORT}")

REPORT.write_text(
    "\n".join(report),
    encoding="utf-8"
)

shift.to_csv(
    OUT / "feature_distribution_shift.csv",
    index=False
)

missing.to_csv(
    OUT / "feature_missingness_shift.csv",
    index=False
)

basin_table.to_csv(
    OUT / "basin_flood_rates.csv"
)

year_table.to_csv(
    OUT / "year_flood_rates.csv"
)

month_table.to_csv(
    OUT / "month_flood_rates.csv"
)

print("\n" + "=" * 110)
print("PHASE 17A COMPLETE")
print("=" * 110)
print(f"Report : {REPORT}")
print(f"Output : {OUT}")
print("=" * 110)