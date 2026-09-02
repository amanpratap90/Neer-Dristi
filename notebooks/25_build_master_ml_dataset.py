from pathlib import Path
import pandas as pd
import numpy as np
import re
import warnings

warnings.filterwarnings("ignore")

print("=" * 80)
print("CHETAKAI V1 MASTER ML DATASET BUILDER")
print("=" * 80)

ROOT = Path(__file__).resolve().parents[1]

PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

OUT_DIR = PROCESSED / "master"

OUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT = (
    OUT_DIR /
    "chetakai_v1_master_ml_dataset.csv"
)


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def find_csv(folder, keywords):

    if not folder.exists():
        return None

    candidates = list(
        folder.rglob("*.csv")
    )

    for f in candidates:

        name = f.name.lower()

        if all(
            key.lower() in name
            for key in keywords
        ):
            return f

    return None


def load_csv(folder, keywords):

    f = find_csv(
        folder,
        keywords
    )

    if f is None:

        print(
            "NOT FOUND:",
            keywords
        )

        return None

    try:

        df = pd.read_csv(f)

        print(
            "LOADED:",
            f
        )

        print(
            "  SHAPE:",
            df.shape
        )

        return df

    except Exception as e:

        print(
            "FAILED:",
            f,
            e
        )

        return None


def find_basin_column(df):

    if df is None:
        return None

    candidates = [
        "basin_name",
        "Basin_Name",
        "BASIN_NAME",
        "basin",
        "BASIN",
        "name",
        "Name",
        "NAME",
        "id"
    ]

    for c in candidates:

        if c in df.columns:
            return c

    return None


def normalize_basin_column(df):

    if df is None:
        return None

    c = find_basin_column(df)

    if c is None:
        return df

    if c != "basin_name":

        df = df.rename(
            columns={
                c: "basin_name"
            }
        )

    df["basin_name"] = (
        df["basin_name"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    return df


def normalize_month(df):

    if df is None:
        return None

    candidates = [
        "date",
        "month",
        "datetime",
        "time",
        "timestamp",
        "year_month"
    ]

    date_col = None

    for c in candidates:

        if c in df.columns:

            date_col = c
            break

    if date_col is None:

        for c in df.columns:

            if "date" in c.lower():

                date_col = c
                break

    if date_col is None:

        print(
            "No date/month column found."
        )

        return df

    df["month"] = pd.to_datetime(
        df[date_col],
        errors="coerce",
        format="mixed"
    ).dt.to_period(
        "M"
    ).astype(str)

    return df


def numeric_clean(df):

    if df is None:
        return None

    for c in df.columns:

        if c in [
            "basin_name",
            "month"
        ]:
            continue

        if (
            df[c].dtype == "object"
        ):

            converted = pd.to_numeric(
                df[c],
                errors="coerce"
            )

            valid_ratio = (
                converted.notna().mean()
            )

            if valid_ratio > 0.7:

                df[c] = converted

    return df


def collapse_duplicate_columns(df):

    df = df.loc[
        :,
        ~df.columns.duplicated()
    ]

    return df


# ---------------------------------------------------------------------
# LOAD DATASETS
# ---------------------------------------------------------------------

print()
print("1. LOADING RAINFALL")

rainfall = load_csv(
    PROCESSED / "rainfall",
    ["rainfall", "features"]
)

if rainfall is None:

    candidates = list(
        (PROCESSED / "rainfall").glob(
            "*.csv"
        )
    )

    if candidates:

        rainfall = pd.read_csv(
            candidates[0]
        )


if rainfall is None:

    raise RuntimeError(
        "Rainfall feature dataset is required."
    )


rainfall = normalize_basin_column(
    rainfall
)

rainfall = normalize_month(
    rainfall
)

rainfall = numeric_clean(
    rainfall
)


# ---------------------------------------------------------------------
# LOAD STATIC FEATURES
# ---------------------------------------------------------------------

print()
print("2. LOADING STATIC FEATURES")


dem = load_csv(
    PROCESSED / "dem",
    ["dem", "features"]
)

hydro = load_csv(
    PROCESSED / "hydrography",
    ["hydrography", "features"]
)

reservoir = load_csv(
    PROCESSED / "reservoirs",
    ["reservoir", "features"]
)

lulc = load_csv(
    PROCESSED / "lulc",
    ["lulc", "features"]
)

soil = load_csv(
    PROCESSED / "soil",
    ["soil", "features"]
)

population = load_csv(
    PROCESSED / "population",
    ["population", "admin", "features"]
)

satellite = load_csv(
    PROCESSED / "satellite",
    ["satellite", "features"]
)

infrastructure = load_csv(
    PROCESSED / "infrastructure",
    ["infrastructure", "features"]
)


# ---------------------------------------------------------------------
# NORMALIZE
# ---------------------------------------------------------------------

datasets = {
    "dem": dem,
    "hydro": hydro,
    "reservoir": reservoir,
    "lulc": lulc,
    "soil": soil,
    "population": population,
    "satellite": satellite,
    "infrastructure": infrastructure
}


for key in datasets:

    datasets[key] = normalize_basin_column(
        datasets[key]
    )

    datasets[key] = numeric_clean(
        datasets[key]
    )


# ---------------------------------------------------------------------
# DROP UNUSABLE STATIC FILES
# ---------------------------------------------------------------------

static = []

for name, df in datasets.items():

    if df is None:
        continue

    if "basin_name" not in df.columns:
        print(
            "SKIPPING STATIC DATASET:",
            name,
            "because basin_name is missing."
        )

        continue

    df = df.copy()

    df["basin_name"] = (
        df["basin_name"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df[
        df["basin_name"] != ""
    ]

    if df.empty:
        continue

    # Remove duplicate basin rows.
    df = df.groupby(
        "basin_name",
        as_index=False
    ).mean(
        numeric_only=True
    )

    static.append(
        (
            name,
            df
        )
    )


# ---------------------------------------------------------------------
# BUILD STATIC MASTER
# ---------------------------------------------------------------------

print()
print("3. BUILDING STATIC FEATURE TABLE")

static_master = None

for name, df in static:

    print(
        "MERGING:",
        name
    )

    if static_master is None:

        static_master = df.copy()

    else:

        static_master = static_master.merge(
            df,
            on="basin_name",
            how="outer",
            suffixes=(
                "",
                f"_{name}"
            )
        )


if static_master is None:

    static_master = pd.DataFrame(
        columns=["basin_name"]
    )


static_master = collapse_duplicate_columns(
    static_master
)


# ---------------------------------------------------------------------
# RAINFALL BASIN CLEANING
# ---------------------------------------------------------------------

print()
print("4. CLEANING RAINFALL")

if "basin_name" not in rainfall.columns:

    raise RuntimeError(
        "Rainfall dataset has no basin_name."
    )

if "month" not in rainfall.columns:

    raise RuntimeError(
        "Rainfall dataset has no month/date column."
    )


rainfall["basin_name"] = (
    rainfall["basin_name"]
    .fillna("")
    .astype(str)
    .str.strip()
)

rainfall = rainfall[
    rainfall["basin_name"] != ""
]

rainfall = rainfall[
    rainfall["month"].notna()
]


rainfall = rainfall.sort_values(
    [
        "basin_name",
        "month"
    ]
)


# ---------------------------------------------------------------------
# RAINFALL TIME-SERIES FEATURES
# ---------------------------------------------------------------------

print()
print("5. BUILDING TEMPORAL RAINFALL FEATURES")


numeric_rainfall_columns = []

for c in rainfall.columns:

    if c in [
        "basin_name",
        "month"
    ]:
        continue

    if pd.api.types.is_numeric_dtype(
        rainfall[c]
    ):

        numeric_rainfall_columns.append(
            c
        )


# Identify main rainfall variable.

preferred = [
    "rainfall_mm",
    "precipitation_mm",
    "precip_mm",
    "rainfall",
    "precipitation",
    "mean_rainfall_mm",
    "mean_precipitation"
]

rainfall_column = None

for c in preferred:

    if c in rainfall.columns:

        rainfall_column = c
        break


if rainfall_column is None:

    rainfall_candidates = [
        c
        for c in numeric_rainfall_columns
        if (
            "rain" in c.lower()
            or "precip" in c.lower()
        )
    ]

    if rainfall_candidates:

        rainfall_column = (
            rainfall_candidates[0]
        )


if rainfall_column:

    rainfall[rainfall_column] = pd.to_numeric(
        rainfall[rainfall_column],
        errors="coerce"
    )

    rainfall["rainfall_lag_1"] = (
        rainfall
        .groupby("basin_name")[
            rainfall_column
        ]
        .shift(1)
    )

    rainfall["rainfall_lag_2"] = (
        rainfall
        .groupby("basin_name")[
            rainfall_column
        ]
        .shift(2)
    )

    rainfall["rainfall_lag_3"] = (
        rainfall
        .groupby("basin_name")[
            rainfall_column
        ]
        .shift(3)
    )

    rainfall["rainfall_roll_3"] = (
        rainfall
        .groupby("basin_name")[
            rainfall_column
        ]
        .transform(
            lambda x:
            x.rolling(
                3,
                min_periods=1
            ).sum()
        )
    )

    rainfall["rainfall_roll_6"] = (
        rainfall
        .groupby("basin_name")[
            rainfall_column
        ]
        .transform(
            lambda x:
            x.rolling(
                6,
                min_periods=1
            ).sum()
        )
    )

    rainfall["rainfall_roll_12"] = (
        rainfall
        .groupby("basin_name")[
            rainfall_column
        ]
        .transform(
            lambda x:
            x.rolling(
                12,
                min_periods=1
            ).sum()
        )
    )

    rainfall["rainfall_change"] = (
        rainfall[rainfall_column]
        -
        rainfall["rainfall_lag_1"]
    )

    rainfall["rainfall_anomaly"] = (
        rainfall[rainfall_column]
        -
        rainfall
        .groupby("basin_name")[
            rainfall_column
        ]
        .transform("mean")
    )

    rainfall["rainfall_zscore"] = (
        rainfall["rainfall_anomaly"]
        /
        rainfall
        .groupby("basin_name")[
            rainfall_column
        ]
        .transform("std")
        .replace(0, np.nan)
    )

else:

    print(
        "WARNING: Main rainfall variable "
        "could not be identified."
    )


# ---------------------------------------------------------------------
# MONTH FEATURES
# ---------------------------------------------------------------------

rainfall["month_number"] = pd.to_datetime(
    rainfall["month"],
    errors="coerce"
).dt.month

rainfall["year"] = pd.to_datetime(
    rainfall["month"],
    errors="coerce"
).dt.year

rainfall["monsoon"] = (
    rainfall["month_number"]
    .isin([6, 7, 8, 9])
    .astype(int)
)

rainfall["pre_monsoon"] = (
    rainfall["month_number"]
    .isin([3, 4, 5])
    .astype(int)
)

rainfall["post_monsoon"] = (
    rainfall["month_number"]
    .isin([10, 11])
    .astype(int)
)


# ---------------------------------------------------------------------
# MERGE STATIC FEATURES
# ---------------------------------------------------------------------

print()
print("6. MERGING STATIC FEATURES")

master = rainfall.merge(
    static_master,
    on="basin_name",
    how="left"
)

master = collapse_duplicate_columns(
    master
)


# ---------------------------------------------------------------------
# FLOOD TARGET
# ---------------------------------------------------------------------

print()
print("7. BUILDING FLOOD TARGET")

flood_files = list(
    (RAW / "flood_events").rglob(
        "*.csv"
    )
)

flood_target = None

for f in flood_files:

    try:

        tmp = pd.read_csv(f)

        tmp = normalize_basin_column(
            tmp
        )

        tmp = normalize_month(
            tmp
        )

        if (
            "basin_name" in tmp.columns
            and
            "month" in tmp.columns
        ):

            target_candidates = [
                c
                for c in tmp.columns
                if any(
                    x in c.lower()
                    for x in [
                        "flood",
                        "event",
                        "severity",
                        "target"
                    ]
                )
            ]

            if target_candidates:

                tc = target_candidates[0]

                flood_target = tmp[
                    [
                        "basin_name",
                        "month",
                        tc
                    ]
                ].copy()

                flood_target = (
                    flood_target
                    .rename(
                        columns={
                            tc:
                            "flood_target_raw"
                        }
                    )
                )

                print(
                    "Flood target source:",
                    f
                )

                break

    except Exception:
        continue


if flood_target is not None:

    flood_target[
        "flood_target_raw"
    ] = pd.to_numeric(
        flood_target[
            "flood_target_raw"
        ],
        errors="coerce"
    )

    flood_target[
        "flood_target"
    ] = (
        flood_target[
            "flood_target_raw"
        ]
        .fillna(0)
        > 0
    ).astype(int)

    flood_target = flood_target[
        [
            "basin_name",
            "month",
            "flood_target"
        ]
    ]

    flood_target = (
        flood_target
        .drop_duplicates(
            [
                "basin_name",
                "month"
            ]
        )
    )

    master = master.merge(
        flood_target,
        on=[
            "basin_name",
            "month"
        ],
        how="left"
    )

else:

    print(
        "No compatible flood-event target "
        "found."
    )

    master["flood_target"] = np.nan


# ---------------------------------------------------------------------
# SORT
# ---------------------------------------------------------------------

master = master.sort_values(
    [
        "basin_name",
        "month"
    ]
).reset_index(
    drop=True
)


# ---------------------------------------------------------------------
# REMOVE IMPOSSIBLE COLUMNS
# ---------------------------------------------------------------------

master = master.replace(
    [
        np.inf,
        -np.inf
    ],
    np.nan
)


# Remove columns with completely no information.

all_nan = [
    c
    for c in master.columns
    if master[c].isna().all()
]

if all_nan:

    print(
        "Dropping completely empty columns:",
        len(all_nan)
    )

    master = master.drop(
        columns=all_nan
    )


# ---------------------------------------------------------------------
# FEATURE MISSINGNESS
# ---------------------------------------------------------------------

print()
print("8. MISSINGNESS ANALYSIS")

missing = (
    master.isna()
    .mean()
    .sort_values(
        ascending=False
    )
)

for col, ratio in missing.items():

    if ratio > 0:

        print(
            f"{col:45s} "
            f"{ratio * 100:6.2f}% missing"
        )


# ---------------------------------------------------------------------
# SAFE NUMERIC IMPUTATION
# ---------------------------------------------------------------------

feature_columns = [
    c
    for c in master.columns
    if c not in [
        "basin_name",
        "month"
    ]
]


for c in feature_columns:

    if pd.api.types.is_numeric_dtype(
        master[c]
    ):

        master[c] = master[c].replace(
            [
                np.inf,
                -np.inf
            ],
            np.nan
        )


# Static features:

static_numeric = [
    c
    for c in feature_columns
    if c not in [
        "flood_target"
    ]
]


# Do NOT blindly fill rainfall target-related
# missingness with zero.

for c in static_numeric:

    if master[c].isna().any():

        if (
            "rainfall" not in c.lower()
            and
            "precip" not in c.lower()
        ):

            median = master[c].median()

            if pd.notna(median):

                master[c] = master[c].fillna(
                    median
                )


# Rainfall temporal features:
# initial missing lags are expected.

rain_cols = [
    c
    for c in master.columns
    if (
        "rainfall" in c.lower()
        or
        "precip" in c.lower()
    )
]

for c in rain_cols:

    if c == rainfall_column:
        continue

    master[c] = master[c].fillna(0)


# ---------------------------------------------------------------------
# DATA QUALITY COLUMNS
# ---------------------------------------------------------------------

master["feature_missing_count"] = (
    master[
        [
            c
            for c in feature_columns
            if c in master.columns
        ]
    ]
    .isna()
    .sum(axis=1)
)

master["feature_missing_ratio"] = (
    master["feature_missing_count"]
    /
    max(
        len(feature_columns),
        1
    )
)


# ---------------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------------

master.to_csv(
    OUTPUT,
    index=False
)

print()
print("=" * 80)
print("MASTER ML DATASET COMPLETE")
print("=" * 80)

print(
    "ROWS    :",
    len(master)
)

print(
    "COLUMNS :",
    len(master.columns)
)

print(
    "OUTPUT  :",
    OUTPUT
)

print()

print(
    "BASINS:",
    master["basin_name"]
    .nunique()
)

print(
    "MONTHS:",
    master["month"]
    .nunique()
)

if "flood_target" in master.columns:

    print(
        "FLOOD POSITIVE ROWS:",
        (
            master["flood_target"]
            == 1
        ).sum()
    )

print()

print("FINAL COLUMNS:")

for c in master.columns:
    print(
        "  -",
        c
    )

print()
print(
    master.head(10).to_string(
        index=False
    )
)

print()
print("=" * 80)