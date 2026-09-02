from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd

warnings.filterwarnings("ignore")

BASE = Path("data")
RAW = BASE / "raw"
PROCESSED = BASE / "processed"
OUTPUT = BASE / "ml"

OUTPUT.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("CHETAKAI V1 — FINAL ML MASTER DATASET BUILDER")
print("=" * 80)

# ============================================================
# CONFIG
# ============================================================

START_DATE = "2015-01-01"
END_DATE = "2025-12-31"

# ============================================================
# HELPERS
# ============================================================

def find_files(root, patterns):
    files = []
    for pattern in patterns:
        files.extend(root.rglob(pattern))
    return sorted(set(files))


def clean_name(x):
    return (
        str(x)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
    )


def numeric_columns(df):
    return [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c])
    ]


def aggregate_numeric(df, keys, prefix):
    nums = numeric_columns(df)

    nums = [
        c for c in nums
        if c not in keys
        and c not in ["latitude", "longitude"]
    ]

    if not nums:
        return None

    out = df.groupby(keys)[nums].mean().reset_index()

    rename = {
        c: f"{prefix}_{clean_name(c)}"
        for c in nums
    }

    return out.rename(columns=rename)


# ============================================================
# 1. BASIN BOUNDARIES
# ============================================================

print("\n[1/8] Loading basin boundaries...")

basin_file = RAW / "basin_boundaries" / "cwc_basins.geojson"

if not basin_file.exists():
    basin_file = RAW / "basin_boundaries" / "cwc_subbasins.geojson"

basins = gpd.read_file(basin_file)

if basins.crs is None:
    basins = basins.set_crs("EPSG:4326")

basins = basins.to_crs("EPSG:4326")

print("Basins:", len(basins))
print("Columns:", list(basins.columns))


# ============================================================
# 2. CREATE DAILY TIME INDEX
# ============================================================

print("\n[2/8] Creating daily modeling index...")

dates = pd.date_range(
    START_DATE,
    END_DATE,
    freq="D"
)

basin_names = []

for i, row in basins.iterrows():

    name = None

    for col in [
        "BASIN_NAME",
        "Basin_Name",
        "Basin",
        "NAME",
        "name",
        " basin"
    ]:
        if col in basins.columns:
            name = row[col]
            break

    if pd.isna(name) or name is None:
        name = f"basin_{i}"

    basin_names.append(str(name).strip())

basins["basin"] = basin_names

calendar = pd.MultiIndex.from_product(
    [basins["basin"].unique(), dates],
    names=["basin", "date"]
).to_frame(index=False)

print("Basins:", calendar["basin"].nunique())
print("Dates:", calendar["date"].nunique())
print("Base rows:", len(calendar))


# ============================================================
# 3. RAINFALL
# ============================================================

print("\n[3/8] Integrating rainfall...")

rain_files = find_files(
    RAW / "rainfall",
    ["*.csv", "*.parquet"]
)

print("Rainfall files:", len(rain_files))

rain_parts = []

for f in rain_files:

    try:

        if f.suffix.lower() == ".csv":
            d = pd.read_csv(f)
        else:
            d = pd.read_parquet(f)

        if len(d) == 0:
            continue

        d.columns = [clean_name(c) for c in d.columns]

        date_col = None

        for c in ["date", "time", "datetime", "month"]:
            if c in d.columns:
                date_col = c
                break

        if date_col is None:
            continue

        d["date"] = pd.to_datetime(
            d[date_col],
            errors="coerce"
        ).dt.normalize()

        d = d.dropna(subset=["date"])

        # Existing basin column
        basin_col = None

        for c in ["basin", "basin_name"]:
            if c in d.columns:
                basin_col = c
                break

        if basin_col:
            d["basin"] = d[basin_col].astype(str).str.strip()
            rain_parts.append(d)

    except Exception:
        continue

if rain_parts:

    rain = pd.concat(
        rain_parts,
        ignore_index=True
    )

    rain = rain[
        (rain["date"] >= START_DATE) &
        (rain["date"] <= END_DATE)
    ]

    rain_numeric = [
        c for c in numeric_columns(rain)
        if c not in ["latitude", "longitude"]
    ]

    if rain_numeric:

        rain_daily = (
            rain.groupby(["basin", "date"])[rain_numeric]
            .mean()
            .reset_index()
        )

        # Standard rainfall feature
        candidates = [
            c for c in rain_numeric
            if any(
                x in c
                for x in [
                    "rain",
                    "precip",
                    "chirps",
                    "ppt"
                ]
            )
        ]

        if candidates:

            rainfall_col = candidates[0]

            rain_daily["rainfall"] = rain_daily[rainfall_col]

            rain_daily = rain_daily[
                ["basin", "date", "rainfall"]
            ]

            rain_daily["rainfall_3d"] = (
                rain_daily
                .sort_values(["basin", "date"])
                .groupby("basin")["rainfall"]
                .transform(
                    lambda x: x.rolling(3, min_periods=1).sum()
                )
            )

            rain_daily["rainfall_7d"] = (
                rain_daily
                .sort_values(["basin", "date"])
                .groupby("basin")["rainfall"]
                .transform(
                    lambda x: x.rolling(7, min_periods=1).sum()
                )
            )

            rain_daily["rainfall_30d"] = (
                rain_daily
                .sort_values(["basin", "date"])
                .groupby("basin")["rainfall"]
                .transform(
                    lambda x: x.rolling(30, min_periods=1).sum()
                )
            )

            calendar = calendar.merge(
                rain_daily,
                on=["basin", "date"],
                how="left"
            )

            print("Rainfall integrated:", len(rain_daily))

else:
    print("WARNING: rainfall files not directly basin-indexed.")


# ============================================================
# 4. FLOOD EVENTS
# ============================================================

print("\n[4/8] Creating flood labels...")

flood_file = (
    PROCESSED
    / "flood_events"
    / "flood_events_model_ready.csv"
)

if flood_file.exists():

    flood = pd.read_csv(flood_file)

    flood["start_date"] = pd.to_datetime(
        flood["start_date"],
        errors="coerce"
    )

    flood["end_date"] = pd.to_datetime(
        flood["end_date"],
        errors="coerce"
    )

    flood["date"] = flood["start_date"].dt.normalize()

    flood = flood.dropna(subset=["date"])

    # Flood-event indicator
    flood_daily = (
        flood.groupby("date")
        .size()
        .reset_index(name="flood_event_count")
    )

    flood_daily["flood_event"] = (
        flood_daily["flood_event_count"] > 0
    ).astype(int)

    calendar = calendar.merge(
        flood_daily,
        on="date",
        how="left"
    )

    calendar["flood_event_count"] = (
        calendar["flood_event_count"]
        .fillna(0)
    )

    calendar["flood_event"] = (
        calendar["flood_event"]
        .fillna(0)
        .astype(int)
    )

    print("Flood records:", len(flood))
    print(
        "Flood-positive dates:",
        int(calendar["flood_event"].sum())
    )

else:
    print("WARNING: processed flood file not found.")


# ============================================================
# 5. GENERIC PROCESSED TABULAR FEATURES
# ============================================================

print("\n[5/8] Searching processed feature datasets...")

processed_files = find_files(
    PROCESSED,
    ["*.csv", "*.parquet"]
)

processed_files = [
    f for f in processed_files
    if "flood_events" not in str(f)
]

print("Processed files found:", len(processed_files))

for f in processed_files:

    try:

        if f.suffix.lower() == ".csv":
            d = pd.read_csv(f)
        else:
            d = pd.read_parquet(f)

        if len(d) == 0:
            continue

        d.columns = [clean_name(c) for c in d.columns]

        date_candidates = [
            c for c in d.columns
            if c in [
                "date",
                "datetime",
                "time",
                "timestamp"
            ]
        ]

        basin_candidates = [
            c for c in d.columns
            if c in [
                "basin",
                "basin_name"
            ]
        ]

        if not date_candidates or not basin_candidates:
            continue

        date_col = date_candidates[0]
        basin_col = basin_candidates[0]

        d["date"] = pd.to_datetime(
            d[date_col],
            errors="coerce"
        ).dt.normalize()

        d["basin"] = (
            d[basin_col]
            .astype(str)
            .str.strip()
        )

        d = d.dropna(subset=["date"])

        agg = aggregate_numeric(
            d,
            ["basin", "date"],
            f.stem
        )

        if agg is not None:

            calendar = calendar.merge(
                agg,
                on=["basin", "date"],
                how="left"
            )

            print(
                "Integrated:",
                f.name,
                "rows:",
                len(d)
            )

    except Exception as e:

        print(
            "Skipped:",
            f.name,
            "|",
            type(e).__name__
        )


# ============================================================
# 6. ADD STATIC BASIN FEATURES
# ============================================================

print("\n[6/8] Adding basin-level spatial features...")

spatial_candidates = find_files(
    PROCESSED,
    ["*.csv", "*.parquet"]
)

for f in spatial_candidates:

    try:

        if "flood_events" in str(f):
            continue

        if f.suffix.lower() == ".csv":
            d = pd.read_csv(f)
        else:
            d = pd.read_parquet(f)

        if len(d) == 0:
            continue

        d.columns = [clean_name(c) for c in d.columns]

        basin_col = None

        for c in ["basin", "basin_name"]:
            if c in d.columns:
                basin_col = c
                break

        if basin_col is None:
            continue

        d["basin"] = (
            d[basin_col]
            .astype(str)
            .str.strip()
        )

        nums = numeric_columns(d)

        nums = [
            c for c in nums
            if c not in [
                "latitude",
                "longitude",
                "year",
                "month",
                "day"
            ]
        ]

        if not nums:
            continue

        static = (
            d.groupby("basin")[nums]
            .mean()
            .reset_index()
        )

        rename = {
            c: f"{f.stem}_{c}"
            for c in nums
        }

        static = static.rename(
            columns=rename
        )

        calendar = calendar.merge(
            static,
            on="basin",
            how="left"
        )

    except Exception:
        continue


# ============================================================
# 7. FEATURE ENGINEERING
# ============================================================

print("\n[7/8] Final feature engineering...")

calendar = calendar.sort_values(
    ["basin", "date"]
).reset_index(drop=True)

calendar["year"] = calendar["date"].dt.year
calendar["month"] = calendar["date"].dt.month
calendar["day_of_year"] = calendar["date"].dt.dayofyear

calendar["sin_month"] = np.sin(
    2 * np.pi * calendar["month"] / 12
)

calendar["cos_month"] = np.cos(
    2 * np.pi * calendar["month"] / 12
)

# Rainfall anomaly
if "rainfall" in calendar.columns:

    monthly_mean = (
        calendar.groupby(
            ["basin", "month"]
        )["rainfall"]
        .transform("mean")
    )

    calendar["rainfall_anomaly"] = (
        calendar["rainfall"] - monthly_mean
    )

# Fill only numeric missing values with basin median,
# then global median.
numeric_cols = calendar.select_dtypes(
    include=np.number
).columns

for c in numeric_cols:

    if c in [
        "flood_event",
        "year",
        "month",
        "day_of_year"
    ]:
        continue

    calendar[c] = (
        calendar.groupby("basin")[c]
        .transform(
            lambda x: x.fillna(x.median())
        )
    )

    calendar[c] = calendar[c].fillna(
        calendar[c].median()
    )

# Final binary label
calendar["flood_event"] = (
    calendar["flood_event"]
    .fillna(0)
    .astype(int)
)


# ============================================================
# 8. VALIDATION + OUTPUT
# ============================================================

print("\n[8/8] Validating master dataset...")

# Remove accidental unnamed columns
calendar = calendar[
    [
        c for c in calendar.columns
        if not c.lower().startswith("unnamed")
    ]
]

# Remove duplicate rows
calendar = calendar.drop_duplicates(
    subset=["basin", "date"]
)

# Sort
calendar = calendar.sort_values(
    ["basin", "date"]
).reset_index(drop=True)

# Save
parquet_file = (
    OUTPUT / "chetakai_master_dataset.parquet"
)

csv_file = (
    OUTPUT / "chetakai_master_dataset.csv"
)

summary_file = (
    OUTPUT / "dataset_summary.json"
)

calendar.to_parquet(
    parquet_file,
    index=False
)

calendar.to_csv(
    csv_file,
    index=False
)

summary = {
    "dataset": "ChetakAI V1 ML Master Dataset",
    "date_start": str(calendar["date"].min()),
    "date_end": str(calendar["date"].max()),
    "rows": int(len(calendar)),
    "columns": int(len(calendar.columns)),
    "basins": int(calendar["basin"].nunique()),
    "flood_positive_rows": int(
        calendar["flood_event"].sum()
    ),
    "flood_negative_rows": int(
        (calendar["flood_event"] == 0).sum()
    ),
    "missing_values": int(
        calendar.isna().sum().sum()
    ),
    "duplicate_basin_dates": int(
        calendar.duplicated(
            ["basin", "date"]
        ).sum()
    ),
    "feature_columns": [
        c for c in calendar.columns
        if c not in ["basin", "date", "flood_event"]
    ]
}

with open(
    summary_file,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        summary,
        f,
        indent=2
    )

print()
print("=" * 80)
print("MASTER DATASET COMPLETE")
print("=" * 80)

print("ROWS:", len(calendar))
print("COLUMNS:", len(calendar.columns))
print("BASINS:", calendar["basin"].nunique())
print("DATE RANGE:", calendar["date"].min(), "->", calendar["date"].max())
print("FLOOD POSITIVE:", calendar["flood_event"].sum())
print("MISSING VALUES:", calendar.isna().sum().sum())
print(
    "DUPLICATE BASIN-DATES:",
    calendar.duplicated(["basin", "date"]).sum()
)

print()
print("PARQUET:", parquet_file)
print("CSV:", csv_file)
print("SUMMARY:", summary_file)

print("=" * 80)