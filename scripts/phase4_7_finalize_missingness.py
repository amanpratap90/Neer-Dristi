from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

HYDRO = ROOT / "data/processed/hydrography/hydrography_basin_features.csv"
SOIL = ROOT / "data/processed/soil/soil_basin_features.csv"

print("=" * 100)
print("CHETAKAI — PHASE 4.7 MISSING DATA FINALIZATION")
print("=" * 100)


# ============================================================
# 1. HYDROGRAPHY
# ============================================================

print("\n[1/3] HYDROGRAPHY")

hydro = pd.read_csv(HYDRO)

hydro_cols = [
    "river_length_km",
    "river_density_km_per_km2",
]

for col in hydro_cols:
    missing = hydro[col].isna().sum()

    if missing > 0:
        median = hydro[col].median()

        print(f"  {col}: {missing} missing")
        print(f"  Imputation value: {median}")

        hydro[col] = hydro[col].fillna(median)

hydro.to_csv(HYDRO, index=False)

print("  ✓ Hydrography missing values resolved")


# ============================================================
# 2. SOIL
# ============================================================

print("\n[2/3] SOIL")

soil = pd.read_csv(SOIL)

soil_numeric = soil.select_dtypes(include=[np.number]).columns.tolist()

# Don't impute IDs
exclude = {
    "canonical_basin_id",
}

soil_features = [
    c for c in soil_numeric
    if c not in exclude
]

total_before = soil[soil_features].isna().sum().sum()

print(f"  Missing soil cells before: {total_before}")

for col in soil_features:
    if soil[col].isna().any():
        median = soil[col].median()

        if pd.notna(median):
            soil[col] = soil[col].fillna(median)

total_after = soil[soil_features].isna().sum().sum()

soil.to_csv(SOIL, index=False)

print(f"  Missing soil cells after: {total_after}")

if total_after == 0:
    print("  ✓ Soil missing values resolved")
else:
    print("  ⚠ Soil still contains missing values")


# ============================================================
# 3. FINAL SOURCE CHECK
# ============================================================

print("\n[3/3] FINAL SOURCE DATA CHECK")

datasets = {
    "hydrography": HYDRO,
    "soil": SOIL,
}

all_pass = True

for name, path in datasets.items():

    df = pd.read_csv(path)

    missing = int(df.isna().sum().sum())

    print(f"\n{name.upper()}")
    print(f"  Rows: {len(df)}")
    print(f"  Missing cells: {missing}")

    if missing == 0:
        print("  STATUS: PASS")
    else:
        print("  STATUS: REVIEW")
        all_pass = False


print("\n" + "=" * 100)

if all_pass:
    print("PHASE 4.7 FEATURE MISSINGNESS: PASS")
else:
    print("PHASE 4.7 FEATURE MISSINGNESS: REVIEW")

print("=" * 100)