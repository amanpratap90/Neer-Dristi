from pathlib import Path
import pandas as pd

ROOT = Path("data/processed")

DATASETS = {
    "hydrography": "hydrography/hydrography_basin_features.csv",
    "lulc": "lulc/lulc_basin_features.csv",
    "population": "population/population_basin_features.csv",
    "satellite": "satellite/satellite_basin_features.csv",
    "soil": "soil/soil_basin_features.csv",
    "rainfall": "rainfall/chirps_monthly_basin_features.csv",
}

print("=" * 110)
print("CHETAKAI — PHASE 4.1: IDENTIFY EXACT MISSING BASINS")
print("=" * 110)

for name, relative_path in DATASETS.items():

    path = ROOT / relative_path
    df = pd.read_csv(path)

    print("\n" + "-" * 110)
    print(name.upper())
    print("-" * 110)

    if "canonical_basin_id" not in df.columns:
        print("ERROR: canonical_basin_id missing")
        continue

    # Find rows containing NaN values
    missing_rows = df[df.isna().any(axis=1)]

    print("Total rows:", len(df))
    print("Rows containing NaN:", len(missing_rows))

    if len(missing_rows) == 0:
        print("✓ No missing rows")
        continue

    # Basin IDs affected
    ids = missing_rows["canonical_basin_id"].dropna().unique()

    print("\nAffected canonical basin IDs:")
    for basin_id in ids:
        print(" ", basin_id)

    # Show affected rows
    print("\nAffected rows:")

    display_cols = ["canonical_basin_id"]

    if "basin_name" in df.columns:
        display_cols.append("basin_name")

    # For rainfall, include date
    if "date" in df.columns:
        display_cols.append("date")

    print(
        missing_rows[display_cols]
        .drop_duplicates()
        .to_string(index=False)
    )

    # Missing columns
    print("\nMissing columns:")

    for col in df.columns:
        count = df[col].isna().sum()

        if count > 0:
            print(
                f"  {col:40} "
                f"{count:6} missing"
            )

print("\n" + "=" * 110)
print("PHASE 4.1 COMPLETE")
print("=" * 110)