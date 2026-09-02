from pathlib import Path
import pandas as pd

ROOT = Path("data/processed")

FILES = {
    "MASTER": ROOT / "master" / "chetakai_v1_master_ml_dataset.csv",
    "RAINFALL": ROOT / "rainfall" / "chirps_monthly_basin_features.csv",
    "DEM": ROOT / "dem" / "dem_basin_features.csv",
    "DEM_TILE": ROOT / "dem" / "dem_tile_basin_features.csv",
    "HYDROGRAPHY": ROOT / "hydrography" / "hydrography_basin_features.csv",
    "RESERVOIR": ROOT / "reservoirs" / "reservoir_basin_features.csv",
    "SOIL": ROOT / "soil" / "soil_basin_features.csv",
    "LULC": ROOT / "lulc" / "lulc_basin_features.csv",
    "POPULATION": ROOT / "population" / "population_basin_features.csv",
    "ADMINISTRATIVE": ROOT / "administrative" / "administrative_basin_features.csv",
    "INFRASTRUCTURE": ROOT / "infrastructure" / "infrastructure_basin_features.csv",
    "SATELLITE": ROOT / "satellite" / "satellite_basin_features.csv",
    "FLOOD": ROOT / "flood_events" / "flood_events_model_ready.csv",
}


def inspect(name, path):
    print("\n" + "=" * 100)
    print(f"{name}")
    print("=" * 100)
    print(f"FILE: {path}")

    if not path.exists():
        print("STATUS: NOT FOUND")
        return

    df = pd.read_csv(path)

    print(f"ROWS: {len(df)}")
    print(f"COLS: {len(df.columns)}")
    print()

    print("COLUMNS:")
    for i, col in enumerate(df.columns, 1):
        dtype = str(df[col].dtype)
        non_null = int(df[col].notna().sum())
        missing = int(df[col].isna().sum())
        unique = int(df[col].nunique(dropna=True))

        print(
            f"{i:>3}. "
            f"{col:<40} "
            f"dtype={dtype:<12} "
            f"non_null={non_null:<7} "
            f"missing={missing:<7} "
            f"unique={unique}"
        )

    print("\nSAMPLE:")
    print(df.head(3).to_string(index=False))


def main():
    print("=" * 100)
    print("CHETAKAI ML SCHEMA INSPECTION")
    print("=" * 100)

    for name, path in FILES.items():
        inspect(name, path)

    print("\n" + "=" * 100)
    print("INSPECTION COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()