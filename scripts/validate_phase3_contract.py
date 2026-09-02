from pathlib import Path
import pandas as pd

ROOT = Path("data/processed")

EXPECTED_BASINS = {
    f"CWC_BASIN_{i:03d}"
    for i in range(1, 26)
}

DATASETS = {
    "administrative": "administrative/administrative_basin_features.csv",
    "dem": "dem/dem_basin_features.csv",
    "hydrography": "hydrography/hydrography_basin_features.csv",
    "infrastructure": "infrastructure/infrastructure_basin_features.csv",
    "lulc": "lulc/lulc_basin_features.csv",
    "population": "population/population_basin_features.csv",
    "reservoirs": "reservoirs/reservoir_basin_features.csv",
    "satellite": "satellite/satellite_basin_features.csv",
    "soil": "soil/soil_basin_features.csv",
}

print("=" * 100)
print("CHETAKAI — PHASE 3: DATASET CONTRACT VALIDATION")
print("=" * 100)

overall_pass = True

for name, relative_path in DATASETS.items():

    path = ROOT / relative_path

    print("\n" + "-" * 100)
    print(name.upper())
    print("-" * 100)

    if not path.exists():
        print(f"❌ FILE NOT FOUND: {path}")
        overall_pass = False
        continue

    df = pd.read_csv(path)

    if "canonical_basin_id" not in df.columns:
        print("❌ canonical_basin_id missing")
        overall_pass = False
        continue

    ids = set(df["canonical_basin_id"].dropna().astype(str))

    invalid = ids - EXPECTED_BASINS
    duplicates = df["canonical_basin_id"].duplicated().sum()

    print(f"Rows                  : {len(df)}")
    print(f"Unique canonical IDs  : {df['canonical_basin_id'].nunique()}")
    print(f"Invalid IDs           : {len(invalid)}")
    print(f"Duplicate IDs         : {duplicates}")

    if invalid:
        print(f"❌ INVALID IDs: {sorted(invalid)}")
        overall_pass = False
    else:
        print("✓ IDs belong to canonical registry")

    if duplicates:
        print("⚠ Duplicate basin IDs detected")
        print("   This may be valid only for multi-row datasets.")
    else:
        print("✓ No duplicate basin IDs")

    missing = EXPECTED_BASINS - ids

    print(f"Missing canonical IDs  : {len(missing)}")

    if missing:
        print("Missing:")
        print(sorted(missing))

        # Missing data is allowed at this stage.
        # We are checking identity consistency, not forcing coverage.
        print("ℹ Missing coverage recorded — no synthetic values created.")

print("\n" + "=" * 100)
print("PHASE 3 RESULT")
print("=" * 100)

if overall_pass:
    print("✓ CANONICAL ID CONTRACT: PASS")
else:
    print("❌ CANONICAL ID CONTRACT: FAIL")

print("=" * 100)