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
}


def find_column(df):
    candidates = [
        "basin_name",
        "basin",
        "basin_id",
        "BASIN",
        "BASIN_NAME",
    ]

    for col in candidates:
        if col in df.columns:
            return col

    return None


def normalize(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    # Numeric basin IDs such as 1, 2, 10
    try:
        number = float(value)

        if number.is_integer():
            return str(int(number))
    except Exception:
        pass

    return value.upper()


def main():

    print("=" * 100)
    print("CHETAKAI BASIN JOIN COMPATIBILITY AUDIT")
    print("=" * 100)

    datasets = {}

    for name, path in FILES.items():

        if not path.exists():
            print(f"\n{name}: FILE NOT FOUND")
            continue

        df = pd.read_csv(path)

        col = find_column(df)

        if col is None:
            print(f"\n{name}: NO BASIN COLUMN FOUND")
            continue

        values = (
            df[col]
            .dropna()
            .map(normalize)
            .drop_duplicates()
            .tolist()
        )

        datasets[name] = set(values)

        print("\n" + "-" * 100)
        print(name)
        print("-" * 100)
        print(f"Column : {col}")
        print(f"Unique : {len(values)}")

        print("Values:")
        print(values)

    # ------------------------------------------------------------------
    # Compare everything against rainfall/master canonical basin set
    # ------------------------------------------------------------------

    canonical_name = "MASTER"

    if canonical_name not in datasets:
        print("\nMASTER DATASET NOT FOUND")
        return

    canonical = datasets[canonical_name]

    print("\n" + "=" * 100)
    print("REFERENCE BASIN SET")
    print("=" * 100)
    print(f"Canonical dataset : {canonical_name}")
    print(f"Canonical basins  : {len(canonical)}")

    for name, values in datasets.items():

        if name == canonical_name:
            continue

        missing = canonical - values
        extra = values - canonical
        overlap = canonical & values

        print("\n" + "-" * 100)
        print(f"{name}")
        print("-" * 100)

        print(f"Overlap with master : {len(overlap)}")
        print(f"Missing from source : {len(missing)}")
        print(f"Extra in source     : {len(extra)}")

        if missing:
            print("\nMISSING:")
            print(sorted(missing))

        if extra:
            print("\nEXTRA:")
            print(sorted(extra))

    # ------------------------------------------------------------------
    # Generate compatibility report
    # ------------------------------------------------------------------

    report = []

    for name, values in datasets.items():

        if name == canonical_name:
            continue

        missing = canonical - values
        extra = values - canonical
        overlap = canonical & values

        report.append({
            "dataset": name,
            "canonical_basins": len(canonical),
            "source_basins": len(values),
            "overlap": len(overlap),
            "missing": len(missing),
            "extra": len(extra),
        })

    report_df = pd.DataFrame(report)

    output = Path("data/ml")
    output.mkdir(parents=True, exist_ok=True)

    report_df.to_csv(
        output / "basin_join_compatibility.csv",
        index=False
    )

    print("\n" + "=" * 100)
    print("JOIN AUDIT COMPLETE")
    print("=" * 100)
    print(f"Report: {output / 'basin_join_compatibility.csv'}")


if __name__ == "__main__":
    main()