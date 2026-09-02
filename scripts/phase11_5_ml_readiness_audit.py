from pathlib import Path
import numpy as np
import pandas as pd


ROOT = Path("data/processed/master/phase11")

INPUT = ROOT / "chetakai_v1_master_phase11.csv"

REPORT = ROOT / "phase11_5_feature_governance_report.csv"
CORR_REPORT = ROOT / "phase11_5_high_correlation_report.csv"
MISSING_REPORT = ROOT / "phase11_5_missingness_report.csv"
ML_FEATURES = ROOT / "phase11_5_ml_feature_inventory.csv"


print("=" * 110)
print("CHETAKAI V1 — PHASE 11.5 FEATURE REALITY & ML READINESS AUDIT")
print("=" * 110)


# ------------------------------------------------------------------
# LOAD
# ------------------------------------------------------------------

if not INPUT.exists():
    raise FileNotFoundError(
        f"Phase 11 dataset not found:\n{INPUT}"
    )

df = pd.read_csv(INPUT)

print("\nINPUT DATASET")
print("-" * 110)
print(f"Rows    : {len(df)}")
print(f"Columns : {len(df.columns)}")


# ------------------------------------------------------------------
# BASIC VALIDATION
# ------------------------------------------------------------------

required = [
    "canonical_basin_id",
    "timestamp",
    "target_flood",
]

missing_required = [
    c for c in required
    if c not in df.columns
]

if missing_required:
    raise ValueError(
        f"Required columns missing: {missing_required}"
    )

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)

if df["timestamp"].isna().any():
    raise ValueError(
        "Invalid timestamps found."
    )


print("\nDATASET STRUCTURE")
print("-" * 110)

print(
    f"Basins      : {df['canonical_basin_id'].nunique()}"
)

print(
    f"Date range  : {df['timestamp'].min()} → {df['timestamp'].max()}"
)

duplicate_keys = df.duplicated(
    subset=["canonical_basin_id", "timestamp"]
).sum()

print(
    f"Duplicate keys : {duplicate_keys}"
)


# ------------------------------------------------------------------
# TARGET
# ------------------------------------------------------------------

print("\nTARGET")
print("-" * 110)

print(
    df["target_flood"].value_counts(dropna=False).to_dict()
)

positive = int((df["target_flood"] == 1).sum())

print(
    f"Flood positive : {positive}"
)

print(
    f"Flood rate     : {positive / len(df) * 100:.2f}%"
)


# ------------------------------------------------------------------
# FEATURE CLASSIFICATION
# ------------------------------------------------------------------

metadata = {
    "canonical_basin_id",
    "timestamp",
    "basin",
    "date",
}

label_features = {
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
}

proxy_keywords = [
    "proxy",
    "radar_",
    "nwp_",
    "obs_",
]

static_keywords = [
    "basin_area",
    "elevation",
    "slope",
    "relief",
    "river_",
    "lulc_",
    "tree_cover",
    "shrubland",
    "grassland",
    "cropland",
    "built_up",
    "bare_sparse",
    "snow_ice",
    "water_pct",
    "wetland",
    "mangroves",
    "population",
    "reservoir",
    "sand_",
    "clay_",
    "silt_",
    "soc_",
    "bdod_",
    "phh2o_",
    "cec_",
    "cfvo_",
    "soil_",
    "ndvi_",
    "ndwi_",
    "vegetation_fraction",
    "water_fraction",
]

rows = []

for col in df.columns:

    dtype = str(df[col].dtype)

    unique = df[col].nunique(dropna=False)

    missing_pct = df[col].isna().mean() * 100

    constant = unique <= 1

    if col in metadata:
        category = "METADATA"

    elif col in label_features:
        category = "LABEL_DERIVED"

    elif any(k in col.lower() for k in proxy_keywords):
        category = "PROXY"

    elif any(k in col.lower() for k in static_keywords):
        category = "ENVIRONMENTAL"

    elif col in {"year", "month", "month_sin", "month_cos"}:
        category = "TEMPORAL"

    else:
        category = "WEATHER_ENGINEERED"

    if category in {"METADATA", "LABEL_DERIVED"}:
        ml_use = "EXCLUDE"

    elif constant:
        ml_use = "EXCLUDE_CONSTANT"

    elif missing_pct > 70:
        ml_use = "REVIEW_HIGH_MISSINGNESS"

    elif missing_pct > 50:
        ml_use = "REVIEW_MISSINGNESS"

    else:
        ml_use = "CANDIDATE"

    rows.append({
        "feature": col,
        "dtype": dtype,
        "category": category,
        "unique_values": unique,
        "missing_count": int(df[col].isna().sum()),
        "missing_pct": round(missing_pct, 4),
        "constant": constant,
        "ml_use": ml_use,
    })


governance = pd.DataFrame(rows)


# ------------------------------------------------------------------
# PRINT CATEGORY SUMMARY
# ------------------------------------------------------------------

print("\nFEATURE CATEGORY SUMMARY")
print("-" * 110)

print(
    governance["category"]
    .value_counts()
    .to_string()
)


print("\nML USAGE SUMMARY")
print("-" * 110)

print(
    governance["ml_use"]
    .value_counts()
    .to_string()
)


# ------------------------------------------------------------------
# PROXY AUDIT
# ------------------------------------------------------------------

print("\nPROXY FEATURES")
print("-" * 110)

proxy_df = governance[
    governance["category"] == "PROXY"
]

print(
    f"Proxy features : {len(proxy_df)}"
)

for col in proxy_df["feature"]:
    print(f"  PROXY : {col}")


# ------------------------------------------------------------------
# LABEL LEAKAGE
# ------------------------------------------------------------------

print("\nLABEL LEAKAGE AUDIT")
print("-" * 110)

for col in label_features:

    if col in df.columns:
        print(
            f"  EXCLUDE : {col}"
        )


# ------------------------------------------------------------------
# MISSINGNESS
# ------------------------------------------------------------------

missing_df = governance[
    governance["missing_count"] > 0
].sort_values(
    "missing_pct",
    ascending=False
)

print("\nMISSINGNESS AUDIT")
print("-" * 110)

if len(missing_df) == 0:
    print("No missing values.")
else:
    for _, r in missing_df.iterrows():
        print(
            f"  {r['feature']} : "
            f"{r['missing_count']} "
            f"({r['missing_pct']:.2f}%)"
        )


# ------------------------------------------------------------------
# CONSTANT FEATURES
# ------------------------------------------------------------------

constant_df = governance[
    governance["constant"]
]

print("\nCONSTANT FEATURES")
print("-" * 110)

if len(constant_df) == 0:
    print("None")
else:
    for col in constant_df["feature"]:
        print(
            f"  CONSTANT : {col}"
        )


# ------------------------------------------------------------------
# HIGH CORRELATION
# ------------------------------------------------------------------

print("\nHIGH CORRELATION ANALYSIS")
print("-" * 110)

numeric_cols = df.select_dtypes(
    include=np.number
).columns.tolist()

numeric_cols = [
    c for c in numeric_cols
    if c not in label_features
]

corr = df[numeric_cols].corr()

pairs = []

for i in range(len(corr.columns)):

    for j in range(i + 1, len(corr.columns)):

        a = corr.columns[i]
        b = corr.columns[j]

        value = corr.iloc[i, j]

        if pd.notna(value) and abs(value) >= 0.995:

            pairs.append({
                "feature_a": a,
                "feature_b": b,
                "correlation": round(float(value), 6),
            })


corr_df = pd.DataFrame(pairs)

if len(corr_df):

    corr_df = corr_df.sort_values(
        "correlation",
        key=lambda x: x.abs(),
        ascending=False
    )

    print(
        f"High-correlation pairs : {len(corr_df)}"
    )

    for _, r in corr_df.head(50).iterrows():
        print(
            f"  {r['feature_a']} <-> "
            f"{r['feature_b']} | "
            f"{r['correlation']:.6f}"
        )

else:
    print(
        "No correlation >= 0.995"
    )


# ------------------------------------------------------------------
# FUTURE INFORMATION / TEMPORAL SAFETY
# ------------------------------------------------------------------

print("\nTEMPORAL SAFETY AUDIT")
print("-" * 110)

future_risk = []

for col in df.columns:

    name = col.lower()

    risk = False

    if "future" in name:
        risk = True

    if "lead" in name:
        risk = True

    if "next_month" in name:
        risk = True

    if "next_" in name:
        risk = True

    if "forecast_actual" in name:
        risk = True

    if risk:
        future_risk.append(col)

if future_risk:

    print("Potential future-information features:")

    for col in future_risk:
        print(
            f"  REVIEW : {col}"
        )

else:

    print(
        "No obvious future-information feature names detected."
    )


# ------------------------------------------------------------------
# TEMPORAL FEATURES
# ------------------------------------------------------------------

print("\nTEMPORAL FEATURES")
print("-" * 110)

for col in [
    "year",
    "month",
    "month_sin",
    "month_cos",
]:
    if col in df.columns:
        print(
            f"  RETAIN : {col}"
        )


# ------------------------------------------------------------------
# ML FEATURE INVENTORY
# ------------------------------------------------------------------

print("\nML FEATURE INVENTORY")
print("-" * 110)

candidate_df = governance[
    governance["ml_use"] == "CANDIDATE"
].copy()

print(
    f"Candidate ML features : {len(candidate_df)}"
)

print(
    f"Numeric candidates     : "
    f"{df[candidate_df['feature']].select_dtypes(include=np.number).shape[1]}"
)


# ------------------------------------------------------------------
# SAVE REPORTS
# ------------------------------------------------------------------

governance.to_csv(
    REPORT,
    index=False
)

corr_df.to_csv(
    CORR_REPORT,
    index=False
)

missing_df.to_csv(
    MISSING_REPORT,
    index=False
)

candidate_df.to_csv(
    ML_FEATURES,
    index=False
)


# ------------------------------------------------------------------
# FINAL VALIDATION
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("PHASE 11.5 FINAL VALIDATION")
print("=" * 110)

print(
    f"Input rows             : {len(df)}"
)

print(
    f"Input columns          : {len(df.columns)}"
)

print(
    f"Governance rows        : {len(governance)}"
)

print(
    f"Candidate ML features  : {len(candidate_df)}"
)

print(
    f"Proxy features         : {len(proxy_df)}"
)

print(
    f"Label-derived features : "
    f"{len([c for c in label_features if c in df.columns])}"
)

print(
    f"High correlation pairs : {len(corr_df)}"
)

print(
    f"Missing-value features : {len(missing_df)}"
)

print(
    f"Constant features      : {len(constant_df)}"
)

print(
    f"Duplicate keys         : {duplicate_keys}"
)


if duplicate_keys != 0:
    raise ValueError(
        "Duplicate basin/timestamp keys detected."
    )

if len(df) != 3168:
    raise ValueError(
        "Unexpected row count. Phase 11 dataset appears changed."
    )

print("\nREPORTS")
print("-" * 110)

print(REPORT)
print(CORR_REPORT)
print(MISSING_REPORT)
print(ML_FEATURES)

print("\n" + "=" * 110)
print("🔥 PHASE 11.5 PASS — FEATURE GOVERNANCE AUDIT COMPLETE")
print("=" * 110)