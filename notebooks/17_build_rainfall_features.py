from pathlib import Path
import re
import gzip
import shutil
import tempfile

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask


print("=" * 70)
print("CHETAKAI V1 RAINFALL FEATURE ENGINEERING")
print("=" * 70)


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAIN_DIR = PROJECT_ROOT / "data" / "raw" / "rainfall"
BASIN_DIR = PROJECT_ROOT / "data" / "raw" / "basin_boundaries"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "rainfall"

OUTPUT_CSV = OUTPUT_DIR / "chirps_monthly_basin_features.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


START_YEAR = 2015
END_YEAR = 2025

MIN_VALID_PIXELS = 10

# CHIRPS NoData / invalid-value protection
NODATA_VALUES = {
    -9999.0,
    -999.0,
    -99999.0,
}

# Rainfall cannot physically be negative.
# Small floating point noise around zero is allowed and clipped.
MIN_RAINFALL_MM = 0.0


print(f"PROJECT ROOT : {PROJECT_ROOT}")
print(f"RAINFALL DIR : {RAIN_DIR}")
print(f"BASIN DIR    : {BASIN_DIR}")
print(f"OUTPUT       : {OUTPUT_CSV}")
print()


# ============================================================
# FIND CHIRPS FILES
# ============================================================

print("Searching for CHIRPS files...")

rainfall_files = sorted(
    list(RAIN_DIR.rglob("*.tif.gz")) +
    list(RAIN_DIR.rglob("*.tif"))
)

if not rainfall_files:
    raise RuntimeError(
        f"No CHIRPS rainfall files found inside:\n{RAIN_DIR}"
    )

print(f"CHIRPS FILES FOUND : {len(rainfall_files)}")
print()


# ============================================================
# DATE EXTRACTION
# ============================================================

def extract_date(filename):

    name = Path(filename).name

    match = re.search(
        r"chirps-v2\.0\.(\d{4})\.(\d{2})",
        name,
        re.IGNORECASE
    )

    if not match:
        return None

    year = int(match.group(1))
    month = int(match.group(2))

    if not START_YEAR <= year <= END_YEAR:
        return None

    if not 1 <= month <= 12:
        return None

    return pd.Timestamp(
        year=year,
        month=month,
        day=1
    )


# ============================================================
# LOAD BASIN BOUNDARIES
# ============================================================

print("Searching for basin boundaries...")

basin_file = BASIN_DIR / "cwc_basins.geojson"

if not basin_file.exists():

    candidates = list(
        BASIN_DIR.glob("*.geojson")
    )

    if not candidates:
        raise RuntimeError(
            "No basin GeoJSON found."
        )

    basin_file = candidates[0]


print(f"USING BASIN FILE : {basin_file}")
print()


# ============================================================
# READ BASINS
# ============================================================

basins = gpd.read_file(basin_file)

if basins.empty:
    raise RuntimeError(
        "Basin boundary file is empty."
    )

if basins.crs is None:
    raise RuntimeError(
        "Basin boundary CRS is missing."
    )


print("BASIN FILE COLUMNS:")

for column in basins.columns:
    print(
        f"  - {column} "
        f"({basins[column].dtype})"
    )

print()


# ============================================================
# SHOW SAMPLE ATTRIBUTES
# ============================================================

print("BASIN ATTRIBUTE SAMPLE:")

attribute_columns = [
    column
    for column in basins.columns
    if column != "geometry"
]

if attribute_columns:

    print(
        basins[
            attribute_columns
        ].head(5).to_string(index=False)
    )

else:

    print("No attribute columns found.")


print()


# ============================================================
# FIND BEST BASIN NAME FIELD
# ============================================================

preferred_columns = [
    "Basin_Name",
    "BASIN_NAME",
    "basin_name",

    "Basin",
    "BASIN",
    "basin",

    "River_Basin",
    "RIVER_BASIN",
    "river_basin",

    "Name",
    "NAME",
    "name",

    "Major_Basin",
    "major_basin"
]


basin_name_column = None


for column in preferred_columns:

    if column in basins.columns:

        values = (
            basins[column]
            .dropna()
            .astype(str)
            .str.strip()
        )

        if len(values) > 0:
            basin_name_column = column
            break


# ============================================================
# IF NO NAME FIELD EXISTS
# ============================================================

if basin_name_column is None:

    print(
        "WARNING: No obvious basin-name field found."
    )

    print(
        "Using stable polygon identifier instead."
    )

    basins["basin_name"] = [
        f"CWC_BASIN_{i + 1:03d}"
        for i in range(len(basins))
    ]

else:

    print(
        f"BASIN NAME FIELD : {basin_name_column}"
    )

    basins["basin_name"] = (
        basins[basin_name_column]
        .astype(str)
        .str.strip()
    )


# ============================================================
# CLEAN BASIN NAMES
# ============================================================

basins["basin_name"] = (
    basins["basin_name"]
    .replace(
        {
            "nan": np.nan,
            "None": np.nan,
            "": np.nan
        }
    )
)


# ============================================================
# REMOVE INVALID GEOMETRIES
# ============================================================

basins = basins[
    basins.geometry.notna()
].copy()

basins = basins[
    ~basins.geometry.is_empty
].copy()


# ============================================================
# CRS
# ============================================================

basins = basins.to_crs("EPSG:4326")


# ============================================================
# FIX MISSING BASIN NAMES
# ============================================================

missing_name_mask = (
    basins["basin_name"].isna()
)

missing_indices = basins.index[missing_name_mask]

for i, idx in enumerate(missing_indices, start=1):

    basins.loc[idx, "basin_name"] = (
        f"CWC_BASIN_MISSING_{i:03d}"
    )


basins["basin_name"] = (
    basins["basin_name"]
    .astype(str)
    .str.strip()
)


# ============================================================
# REMOVE DUPLICATES
# ============================================================

basins = basins.drop_duplicates(
    subset=["basin_name"]
).reset_index(drop=True)


# ============================================================
# BASIN SUMMARY
# ============================================================

print()
print("=" * 70)
print("BASINS READY")
print("=" * 70)

print(
    f"TOTAL BASIN POLYGONS : {len(basins)}"
)

print()

for basin_name in sorted(
    basins["basin_name"].unique()
):

    print(
        f"  - {basin_name}"
    )

print()


# ============================================================
# TEMPORARY GZIP HANDLING
# ============================================================

def prepare_raster(raster_path):

    raster_path = Path(raster_path)

    if raster_path.suffix.lower() == ".gz":

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".tif",
            delete=False
        )

        temp_path = Path(
            temp_file.name
        )

        temp_file.close()

        with gzip.open(
            raster_path,
            "rb"
        ) as src:

            with open(
                temp_path,
                "wb"
            ) as dst:

                shutil.copyfileobj(
                    src,
                    dst
                )

        return temp_path, True

    return raster_path, False


# ============================================================
# RASTER STATISTICS
# ============================================================

def calculate_basin_statistics(
    raster_path,
    basin_geometry
):

    temp_path = None
    temporary = False

    try:

        temp_path, temporary = prepare_raster(
            raster_path
        )

        with rasterio.open(
            temp_path
        ) as src:

            if src.crs is None:
                raise RuntimeError(
                    "Raster CRS missing."
                )

            basin = basin_geometry.to_crs(
                src.crs
            )

            geometries = [
                geometry.__geo_interface__
                for geometry in basin.geometry
                if geometry is not None
                and not geometry.is_empty
            ]

            if not geometries:
                return None


            # ------------------------------------------------
            # MASK RASTER
            # ------------------------------------------------

            data, _ = mask(
                src,
                geometries,
                crop=True,
                filled=False
            )

            values = data[0]


            # ------------------------------------------------
            # EXTRACT VALID PIXELS
            # ------------------------------------------------

            if np.ma.isMaskedArray(values):
                values = values.compressed()
            else:
                values = values.flatten()


            values = values.astype(
                "float64"
            )


            # ------------------------------------------------
            # FINITE VALUES ONLY
            # ------------------------------------------------

            values = values[
                np.isfinite(values)
            ]


            # ------------------------------------------------
            # REMOVE RASTER NODATA
            # ------------------------------------------------

            if src.nodata is not None:

                values = values[
                    values != float(src.nodata)
                ]


            # ------------------------------------------------
            # EXPLICIT CHIRPS NODATA PROTECTION
            # ------------------------------------------------

            for nodata_value in NODATA_VALUES:

                values = values[
                    values != nodata_value
                ]


            # ------------------------------------------------
            # REMOVE NEGATIVE RAINFALL
            # ------------------------------------------------
            # Real rainfall cannot be negative.
            # This also catches malformed/invalid pixels.

            values = values[
                values >= MIN_RAINFALL_MM
            ]


            # ------------------------------------------------
            # VALID PIXEL CHECK
            # ------------------------------------------------

            if len(values) < MIN_VALID_PIXELS:

                return None


            # ------------------------------------------------
            # CLIP TINY FLOATING POINT NEGATIVES
            # ------------------------------------------------

            values = np.maximum(
                values,
                0.0
            )


            # ------------------------------------------------
            # STATISTICS
            # ------------------------------------------------

            return {

                "rainfall_mean_mm":
                    float(np.mean(values)),

                "rainfall_sum_mm":
                    float(np.sum(values)),

                "rainfall_min_mm":
                    float(np.min(values)),

                "rainfall_max_mm":
                    float(np.max(values)),

                "rainfall_std_mm":
                    float(np.std(values)),

                "rainfall_p90_mm":
                    float(
                        np.percentile(
                            values,
                            90
                        )
                    ),

                "rainfall_p95_mm":
                    float(
                        np.percentile(
                            values,
                            95
                        )
                    ),

                "rainfall_p99_mm":
                    float(
                        np.percentile(
                            values,
                            99
                        )
                    ),

                "valid_pixels":
                    int(len(values))
            }


    finally:

        if temporary and temp_path is not None:

            try:
                temp_path.unlink()
            except Exception:
                pass


# ============================================================
# PROCESS CHIRPS
# ============================================================

records = []

total_files = len(
    rainfall_files
)

successful = 0
failed = 0
skipped = 0


print("=" * 70)
print("PROCESSING CHIRPS")
print("=" * 70)
print()


for index, rainfall_file in enumerate(
    rainfall_files,
    start=1
):

    print(
        f"[{index:03d}/{total_files:03d}] "
        f"{rainfall_file.name}"
    )


    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    date = extract_date(
        rainfall_file
    )


    if date is None:

        print(
            "  SKIPPED: invalid CHIRPS date"
        )

        skipped += 1
        continue


    print(
        f"  DATE: "
        f"{date.strftime('%Y-%m')}"
    )


    file_success = False


    # --------------------------------------------------------
    # BASINS
    # --------------------------------------------------------

    for basin_name, basin_group in basins.groupby(
        "basin_name"
    ):

        try:

            stats = calculate_basin_statistics(
                rainfall_file,
                basin_group
            )


            if stats is None:

                print(
                    f"  {basin_name}: "
                    f"insufficient valid pixels"
                )

                continue


            record = {

                "basin":
                    str(basin_name),

                "date":
                    date,

                "year":
                    int(date.year),

                "month":
                    int(date.month),

                **stats
            }


            records.append(
                record
            )

            file_success = True


            print(
                f"  {basin_name}: "
                f"mean="
                f"{stats['rainfall_mean_mm']:.2f} mm "
                f"valid_pixels="
                f"{stats['valid_pixels']}"
            )


        except Exception as e:

            print(
                f"  {basin_name}: "
                f"FAILED -> {e}"
            )


    if file_success:

        successful += 1

    else:

        failed += 1

        print(
            "  FAILED: "
            "no basin statistics generated"
        )


# ============================================================
# PROCESSING SUMMARY
# ============================================================

print()

print("=" * 70)
print("PROCESSING COMPLETE")
print("=" * 70)

print(
    f"TOTAL FILES : {total_files}"
)

print(
    f"SUCCESS     : {successful}"
)

print(
    f"FAILED      : {failed}"
)

print(
    f"SKIPPED     : {skipped}"
)

print(
    f"RECORDS     : {len(records)}"
)

print()


if not records:

    raise RuntimeError(
        "No rainfall records generated."
    )


# ============================================================
# DATAFRAME
# ============================================================

df = pd.DataFrame(
    records
)


# ============================================================
# SORT
# ============================================================

df = df.sort_values(
    [
        "basin",
        "date"
    ]
).reset_index(
    drop=True
)


# ============================================================
# TEMPORAL FEATURES
# ============================================================

df["month_sin"] = np.sin(
    2 * np.pi * df["month"] / 12
)

df["month_cos"] = np.cos(
    2 * np.pi * df["month"] / 12
)


# ============================================================
# ROLLING FEATURES
# ============================================================

df["rainfall_3month_sum_mm"] = (
    df.groupby("basin")[
        "rainfall_mean_mm"
    ]
    .transform(
        lambda x:
        x.rolling(
            3,
            min_periods=1
        ).sum()
    )
)


df["rainfall_6month_sum_mm"] = (
    df.groupby("basin")[
        "rainfall_mean_mm"
    ]
    .transform(
        lambda x:
        x.rolling(
            6,
            min_periods=1
        ).sum()
    )
)


df["rainfall_12month_sum_mm"] = (
    df.groupby("basin")[
        "rainfall_mean_mm"
    ]
    .transform(
        lambda x:
        x.rolling(
            12,
            min_periods=1
        ).sum()
    )
)


# ============================================================
# MONTHLY CLIMATOLOGY
# ============================================================

monthly_climatology = (
    df.groupby(
        [
            "basin",
            "month"
        ]
    )[
        "rainfall_mean_mm"
    ]
    .transform("mean")
)


df["rainfall_climatology_mm"] = (
    monthly_climatology
)


# ============================================================
# ANOMALY
# ============================================================

df["rainfall_anomaly_mm"] = (
    df["rainfall_mean_mm"]
    -
    df["rainfall_climatology_mm"]
)


df["rainfall_anomaly_pct"] = np.where(

    df["rainfall_climatology_mm"] > 0,

    (
        df["rainfall_anomaly_mm"]
        /
        df["rainfall_climatology_mm"]
    ) * 100,

    np.nan
)


# ============================================================
# EXTREME RAINFALL THRESHOLDS
# ============================================================

p90_threshold = (
    df.groupby("basin")[
        "rainfall_mean_mm"
    ]
    .transform(
        lambda x:
        x.quantile(0.90)
    )
)


p95_threshold = (
    df.groupby("basin")[
        "rainfall_mean_mm"
    ]
    .transform(
        lambda x:
        x.quantile(0.95)
    )
)


df["heavy_rain_flag"] = (
    df["rainfall_mean_mm"]
    >= p90_threshold
).astype(int)


df["extreme_rain_flag"] = (
    df["rainfall_mean_mm"]
    >= p95_threshold
).astype(int)


# ============================================================
# ANNUAL RAINFALL
# ============================================================

df["annual_rainfall_mm"] = (
    df.groupby(
        [
            "basin",
            "year"
        ]
    )[
        "rainfall_mean_mm"
    ]
    .transform("sum")
)


# ============================================================
# RAINFALL LAG FEATURES
# ============================================================

df["rainfall_lag_1_month_mm"] = (
    df.groupby("basin")[
        "rainfall_mean_mm"
    ]
    .shift(1)
)


df["rainfall_lag_2_month_mm"] = (
    df.groupby("basin")[
        "rainfall_mean_mm"
    ]
    .shift(2)
)


df["rainfall_lag_3_month_mm"] = (
    df.groupby("basin")[
        "rainfall_mean_mm"
    ]
    .shift(3)
)


# ============================================================
# CANONICAL BASIN IDS
# ============================================================

# Project uses the basin polygon order as the stable
# CWC canonical identifier.

basin_id_map = {
    basin_name: f"CWC_BASIN_{i + 1:03d}"
    for i, basin_name in enumerate(
        basins["basin_name"].tolist()
    )
}


df["canonical_basin_id"] = (
    df["basin"]
    .map(basin_id_map)
)


# ============================================================
# CLEAN NUMERIC VALUES
# ============================================================

numeric_columns = df.select_dtypes(
    include=[np.number]
).columns


df[numeric_columns] = (
    df[numeric_columns]
    .replace(
        [
            np.inf,
            -np.inf
        ],
        np.nan
    )
)


# ============================================================
# FINAL RAINFALL SANITY PROTECTION
# ============================================================

rainfall_columns = [
    "rainfall_mean_mm",
    "rainfall_sum_mm",
    "rainfall_min_mm",
    "rainfall_max_mm",
    "rainfall_std_mm",
    "rainfall_p90_mm",
    "rainfall_p95_mm",
    "rainfall_p99_mm",
    "rainfall_3month_sum_mm",
    "rainfall_6month_sum_mm",
    "rainfall_12month_sum_mm",
    "annual_rainfall_mm",
    "rainfall_lag_1_month_mm",
    "rainfall_lag_2_month_mm",
    "rainfall_lag_3_month_mm",
]


for column in rainfall_columns:

    if column in df.columns:

        df[column] = df[column].where(
            df[column].isna()
            |
            (df[column] >= 0)
        )


# ============================================================
# SAVE
# ============================================================

df.to_csv(
    OUTPUT_CSV,
    index=False
)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("=" * 70)
print("RAINFALL DATASET CREATED")
print("=" * 70)

print(
    f"OUTPUT FILE : {OUTPUT_CSV}"
)

print(
    f"ROWS        : {len(df)}"
)

print(
    f"COLUMNS     : {len(df.columns)}"
)

print()


print("DATE RANGE:")

print(
    f"  {df['date'].min().strftime('%Y-%m')}"
    f" -> "
    f"{df['date'].max().strftime('%Y-%m')}"
)

print()


print("CANONICAL BASIN IDS:")

print(
    df["canonical_basin_id"]
    .drop_duplicates()
    .sort_values()
    .to_string(index=False)
)

print()


print("RAINfall SANITY CHECK:")

for column in [
    "rainfall_mean_mm",
    "rainfall_sum_mm",
    "rainfall_min_mm",
    "rainfall_max_mm"
]:

    print(
        f"  {column}: "
        f"min={df[column].min():.4f}, "
        f"max={df[column].max():.4f}"
    )

print()


print("EXPECTED LAG NaNs:")

print(
    df[
        [
            "rainfall_lag_1_month_mm",
            "rainfall_lag_2_month_mm",
            "rainfall_lag_3_month_mm"
        ]
    ]
    .isna()
    .sum()
    .to_string()
)

print()


print("ANOMALY NaNs:")

print(
    df["rainfall_anomaly_pct"]
    .isna()
    .sum()
)

print()


print("FEATURE COLUMNS:")

for column in df.columns:

    print(
        f"  - {column}"
    )


print()
print("=" * 70)
print("DONE")
print("=" * 70)