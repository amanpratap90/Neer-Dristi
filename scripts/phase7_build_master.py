from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("data/processed")
OUT = ROOT / "master" / "chetakai_v1_master_phase7.csv"


print("=" * 110)
print("CHETAKAI V1 — PHASE 7 STATIC + TEMPORAL MASTER BUILD")
print("=" * 110)


FILES = {
    "rainfall": ROOT / "rainfall" / "chirps_monthly_basin_features.csv",
    "administrative": ROOT / "administrative" / "administrative_basin_features.csv",
    "dem": ROOT / "dem" / "dem_basin_features.csv",
    "hydrography": ROOT / "hydrography" / "hydrography_basin_features.csv",
    "infrastructure": ROOT / "infrastructure" / "infrastructure_basin_features.csv",
    "lulc": ROOT / "lulc" / "lulc_basin_features.csv",
    "population": ROOT / "population" / "population_basin_features.csv",
    "reservoirs": ROOT / "reservoirs" / "reservoir_basin_features.csv",
    "soil": ROOT / "soil" / "soil_basin_features.csv",
    "satellite": ROOT / "satellite" / "satellite_basin_features.csv",
}


# ------------------------------------------------------------------
# LOAD DATASETS
# ------------------------------------------------------------------

print("\nLoading datasets...")

data = {}

for name, path in FILES.items():

    if not path.exists():
        print(f"WARNING: missing {name}: {path}")
        continue

    df = pd.read_csv(path)

    if "canonical_basin_id" not in df.columns:
        raise ValueError(
            f"{name} does not contain canonical_basin_id"
        )

    print(
        f"{name:18} "
        f"rows={len(df):6} "
        f"cols={len(df.columns):3} "
        f"basins={df['canonical_basin_id'].nunique():2}"
    )

    data[name] = df


# ------------------------------------------------------------------
# RAINFALL = TEMPORAL BASE
# ------------------------------------------------------------------

if "rainfall" not in data:
    raise RuntimeError("Rainfall dataset is required.")

rainfall = data["rainfall"].copy()

if "timestamp" in rainfall.columns:

    rainfall["timestamp"] = pd.to_datetime(
        rainfall["timestamp"],
        errors="coerce"
    )

elif "date" in rainfall.columns:

    rainfall["timestamp"] = pd.to_datetime(
        rainfall["date"],
        errors="coerce"
    )

else:

    raise ValueError(
        "Rainfall dataset must contain either 'timestamp' or 'date'."
    )


if "canonical_basin_id" not in rainfall.columns:

    raise ValueError(
        "Rainfall dataset must contain canonical_basin_id."
    )


master = rainfall.copy()

master = master.dropna(
    subset=[
        "canonical_basin_id",
        "timestamp"
    ]
)


print("\nTEMPORAL BASE")
print("-" * 110)

print("Rows:", len(master))
print(
    "Basins:",
    master["canonical_basin_id"].nunique()
)

print(
    "Date:",
    master["timestamp"].min(),
    "→",
    master["timestamp"].max()
)


# ------------------------------------------------------------------
# REMOVE DUPLICATE TEMPORAL KEYS
# ------------------------------------------------------------------

key = [
    "canonical_basin_id",
    "timestamp"
]

duplicates = master.duplicated(
    subset=key,
    keep=False
).sum()

print(
    "Duplicate basin/timestamp rows:",
    duplicates
)

if duplicates:

    master = (
        master
        .sort_values(key)
        .drop_duplicates(
            subset=key,
            keep="first"
        )
    )


# ------------------------------------------------------------------
# STATIC DATASETS
# ------------------------------------------------------------------

static_names = [
    "administrative",
    "dem",
    "hydrography",
    "infrastructure",
    "lulc",
    "population",
    "reservoirs",
    "soil",
]


for name in static_names:

    if name not in data:
        continue

    df = data[name].copy()

    # Keep exactly one record per basin
    df = df.drop_duplicates(
        subset=["canonical_basin_id"],
        keep="first"
    )

    # Remove columns that could conflict with temporal data
    protected = {
        "canonical_basin_id",
        "timestamp"
    }

    rename = {}

    for col in df.columns:

        if col in protected:
            continue

        if col in master.columns:

            rename[col] = f"{name}__{col}"

    if rename:
        df = df.rename(columns=rename)

    print(
        f"\nMERGING {name.upper()}"
    )

    print(
        "  static basins:",
        df["canonical_basin_id"].nunique()
    )

    before = len(master)

    master = master.merge(
        df,
        on="canonical_basin_id",
        how="left",
        validate="many_to_one"
    )

    after = len(master)

    if before != after:

        raise RuntimeError(
            f"ROW COUNT CHANGED while merging {name}: "
            f"{before} → {after}"
        )

    print(
        "  rows after merge:",
        after
    )


# ------------------------------------------------------------------
# SATELLITE
# ------------------------------------------------------------------

if "satellite" in data:

    sat = data["satellite"].copy()

    if "observation_date" in sat.columns:

        sat["observation_date"] = pd.to_datetime(
            sat["observation_date"],
            errors="coerce"
        )

    # Satellite is auxiliary/static information.
    # Aggregate multiple observations to one basin-level record.

    sat_numeric = sat.select_dtypes(
        include=[np.number]
    ).columns.tolist()

    sat_numeric = [
        c
        for c in sat_numeric
        if c not in [
            "valid_pixel_count",
            "satellite_available"
        ]
    ]

    if sat_numeric:

        sat_agg = (
            sat
            .groupby("canonical_basin_id")[sat_numeric]
            .median()
            .reset_index()
        )

    else:

        sat_agg = (
            sat[
                ["canonical_basin_id"]
            ]
            .drop_duplicates()
        )


    sat_agg["satellite_available"] = 1


    rename = {}

    for col in sat_agg.columns:

        if col == "canonical_basin_id":
            continue

        if col in master.columns:

            rename[col] = f"satellite__{col}"

    sat_agg = sat_agg.rename(
        columns=rename
    )


    print("\nMERGING SATELLITE")

    print(
        "  satellite basins:",
        sat_agg["canonical_basin_id"].nunique()
    )

    before = len(master)

    master = master.merge(
        sat_agg,
        on="canonical_basin_id",
        how="left",
        validate="many_to_one"
    )

    if len(master) != before:

        raise RuntimeError(
            "Satellite merge changed row count."
        )


    # Satellite coverage flag
    if "satellite_available" in master.columns:

        master["satellite_available"] = (
            master["satellite_available"]
            .fillna(0)
            .astype("int8")
        )


# ------------------------------------------------------------------
# NUMERIC CLEANUP
# ------------------------------------------------------------------

print("\nCLEANING")

master = master.replace(
    [np.inf, -np.inf],
    np.nan
)


# ------------------------------------------------------------------
# SORT
# ------------------------------------------------------------------

master = (
    master
    .sort_values(
        [
            "canonical_basin_id",
            "timestamp"
        ]
    )
    .reset_index(drop=True)
)


# ------------------------------------------------------------------
# FINAL REPORT
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("PHASE 7 MASTER DATASET COMPLETE")
print("=" * 110)

print(
    "Rows:",
    len(master)
)

print(
    "Columns:",
    len(master.columns)
)

print(
    "Basins:",
    master["canonical_basin_id"].nunique()
)

print(
    "Date range:",
    master["timestamp"].min(),
    "→",
    master["timestamp"].max()
)

print(
    "Duplicate keys:",
    master.duplicated(
        subset=[
            "canonical_basin_id",
            "timestamp"
        ]
    ).sum()
)


print("\nNULL SUMMARY")

nulls = (
    master
    .isna()
    .sum()
)

nulls = (
    nulls[
        nulls > 0
    ]
    .sort_values(
        ascending=False
    )
)

if len(nulls):

    print(
        nulls.to_string()
    )

else:

    print(
        "NO NULLS"
    )


print("\nSATELLITE COVERAGE")

if "satellite_available" in master.columns:

    print(
        master[
            "satellite_available"
        ].value_counts()
    )


# ------------------------------------------------------------------
# SAVE
# ------------------------------------------------------------------

OUT.parent.mkdir(
    parents=True,
    exist_ok=True
)

master.to_csv(
    OUT,
    index=False
)


print("\nSaved:")
print(
    OUT.resolve()
)

print("=" * 110)
print("DONE")
print("=" * 110)
