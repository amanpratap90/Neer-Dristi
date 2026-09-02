from pathlib import Path
import gc
import warnings

import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds

warnings.filterwarnings("ignore")

print("=" * 70)
print("CHETAKAI V1 LULC FEATURE ENGINEERING - MVP LOW DISK")
print("=" * 70)

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw" / "land_use_land_cover"
BASIN_DIR = ROOT / "data" / "raw" / "basin_boundaries"
OUT_DIR = ROOT / "data" / "processed" / "lulc"

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = OUT_DIR / "lulc_basin_features.csv"

CLASS_MAP = {
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse",
    70: "snow_ice",
    80: "water",
    90: "herbaceous_wetland",
    95: "mangroves",
    100: "moss_lichen",
}

BLOCK_SIZE = 512
SAMPLE_STEP = 3


def find_rasters():

    rasters = []

    for pattern in ("*.tif", "*.tiff"):

        rasters.extend(
            RAW_DIR.rglob(pattern)
        )

    return sorted(set(rasters))


def find_basin_file():

    preferred = (
        BASIN_DIR /
        "cwc_basins.geojson"
    )

    if preferred.exists():
        return preferred

    candidates = list(
        BASIN_DIR.glob("*.geojson")
    )

    if candidates:
        return candidates[0]

    raise RuntimeError(
        "No basin GeoJSON found."
    )


def find_name_column(gdf):

    candidates = [
        "basin_name",
        "Basin_Name",
        "BASIN_NAME",
        "basin",
        "BASIN",
        "name",
        "Name",
        "NAME",
        "id",
    ]

    for col in candidates:

        if col in gdf.columns:
            return col

    return None


def calculate_area_km2(
    geometry,
    crs
):

    temp = gpd.GeoDataFrame(
        {"geometry": [geometry]},
        crs=crs
    )

    if temp.crs.is_geographic:

        temp = temp.to_crs(
            "EPSG:6933"
        )

    return float(
        temp.geometry.area.iloc[0]
        / 1_000_000
    )


def bounds_intersect(
    a,
    b
):

    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    return not (
        ax2 <= bx1
        or ax1 >= bx2
        or ay2 <= by1
        or ay1 >= by2
    )


print()

basin_file = find_basin_file()

print(
    "BASIN FILE:",
    basin_file
)

basins = gpd.read_file(
    basin_file
)

if basins.empty:

    raise RuntimeError(
        "Basin file contains no features."
    )

if basins.crs is None:

    raise RuntimeError(
        "Basin CRS is missing."
    )

name_col = find_name_column(
    basins
)

if name_col:

    basins["basin_name"] = (
        basins[name_col]
        .fillna("")
        .astype(str)
    )

else:

    basins["basin_name"] = [
        f"BASIN_{i + 1}"
        for i in range(len(basins))
    ]

basins = basins[
    basins.geometry.notna()
    & ~basins.geometry.is_empty
].copy()

print(
    "BASINS:",
    len(basins)
)

print(
    "BASIN CRS:",
    basins.crs
)


# ------------------------------------------------------------
# Convert all basin geometries to WGS84 ONCE
# ------------------------------------------------------------

print()
print(
    "Preparing basin geometries..."
)

basins_wgs84 = basins.to_crs(
    "EPSG:4326"
)

print(
    "Basin transformation complete."
)


# ------------------------------------------------------------
# Raster metadata
# ------------------------------------------------------------

rasters = find_rasters()

print()
print(
    "LULC RASTERS:",
    len(rasters)
)

if not rasters:

    raise RuntimeError(
        "No LULC raster files found."
    )


raster_meta = []

print()
print(
    "Preparing raster metadata..."
)

for path in rasters:

    try:

        with rasterio.open(path) as src:

            if src.crs is None:
                continue

            bounds = src.bounds

            raster_meta.append(
                {
                    "path": path,
                    "crs": src.crs,
                    "bounds": (
                        bounds.left,
                        bounds.bottom,
                        bounds.right,
                        bounds.top,
                    ),
                }
            )

    except Exception:

        continue


print(
    "Usable rasters:",
    len(raster_meta)
)


# ------------------------------------------------------------
# IMPORTANT
# ------------------------------------------------------------

print()
print(
    "PROCESSING SETTINGS:"
)

print(
    "  Source resolution : 10 m"
)

print(
    "  Effective resolution: ~30 m"
)

print(
    "  Sample step       : every 3rd pixel"
)

print(
    "  Block size        : 512 rows"
)

print(
    "  Temporary files   : NONE"
)

print(
    "  Disk growth       : negligible"
)

print()


results = []

total_basins = len(
    basins_wgs84
)


# ------------------------------------------------------------
# BASIN LOOP
# ------------------------------------------------------------

for basin_number, (
    original_index,
    basin
) in enumerate(
    basins_wgs84.iterrows(),
    start=1
):

    basin_name = str(
        basin["basin_name"]
    )

    geometry = basin.geometry

    basin_bounds = geometry.bounds

    print("=" * 70)

    print(
        f"[{basin_number:03d}/{total_basins:03d}] "
        f"{basin_name}"
    )

    print("=" * 70)

    print(
        "Basin bbox:",
        tuple(
            round(x, 4)
            for x in basin_bounds
        )
    )

    totals = {
        feature: 0
        for feature in CLASS_MAP.values()
    }

    effective_pixels = 0
    rasters_used = 0

    basin_area = calculate_area_km2(
        basins.geometry.loc[
            original_index
        ],
        basins.crs
    )

    # --------------------------------------------------------
    # Find candidate tiles
    # --------------------------------------------------------

    candidate_tiles = []

    for meta in raster_meta:

        if bounds_intersect(
            basin_bounds,
            meta["bounds"]
        ):

            candidate_tiles.append(
                meta
            )

    print(
        "Intersecting tiles:",
        len(candidate_tiles)
    )

    # --------------------------------------------------------
    # Tile processing
    # --------------------------------------------------------

    for tile_number, meta in enumerate(
        candidate_tiles,
        start=1
    ):

        path = meta["path"]

        print(
            f"  Tile {tile_number}/"
            f"{len(candidate_tiles)}: "
            f"{path.name}"
        )

        try:

            with rasterio.open(path) as src:

                # WorldCover is normally EPSG:4326.
                # Avoid expensive reprojection.
                if (
                    src.crs.to_epsg()
                    != 4326
                ):

                    print(
                        "    Skipped: "
                        "non-WGS84 raster"
                    )

                    continue

                window = from_bounds(
                    basin_bounds[0],
                    basin_bounds[1],
                    basin_bounds[2],
                    basin_bounds[3],
                    src.transform
                )

                window = (
                    window
                    .round_offsets()
                    .round_lengths()
                )

                col_start = max(
                    0,
                    int(window.col_off)
                )

                row_start = max(
                    0,
                    int(window.row_off)
                )

                col_end = min(
                    src.width,
                    col_start
                    + int(window.width)
                )

                row_end = min(
                    src.height,
                    row_start
                    + int(window.height)
                )

                if (
                    col_end <= col_start
                    or row_end <= row_start
                ):

                    continue

                tile_pixels = 0

                # ------------------------------------------------
                # Read small blocks
                # ------------------------------------------------

                for row in range(
                    row_start,
                    row_end,
                    BLOCK_SIZE
                ):

                    rows = min(
                        BLOCK_SIZE,
                        row_end - row
                    )

                    block_window = (
                        rasterio.windows.Window(
                            col_start,
                            row,
                            col_end - col_start,
                            rows
                        )
                    )

                    arr = src.read(
                        1,
                        window=block_window
                    )

                    if arr.size == 0:
                        continue

                    # ------------------------------------------------
                    # Sample every 3rd pixel
                    #
                    # This gives an effective ~30 m representation
                    # without generating a 30 m raster.
                    # ------------------------------------------------

                    sampled = arr[
                        ::SAMPLE_STEP,
                        ::SAMPLE_STEP
                    ]

                    # ------------------------------------------------
                    # Create corresponding transform
                    # ------------------------------------------------

                    sampled_transform = (
                        src.window_transform(
                            block_window
                        )
                    )

                    # ------------------------------------------------
                    # Actual basin polygon mask
                    # ------------------------------------------------

                    mask_array = geometry_mask(
                        [geometry.__geo_interface__],
                        out_shape=arr.shape,
                        transform=sampled_transform,
                        invert=True
                    )

                    sampled_mask = mask_array[
                        ::SAMPLE_STEP,
                        ::SAMPLE_STEP
                    ]

                    if src.nodata is not None:

                        sampled_mask &= (
                            sampled
                            != src.nodata
                        )

                    valid = sampled[
                        sampled_mask
                    ]

                    if valid.size == 0:

                        del arr
                        del sampled
                        del mask_array
                        del sampled_mask
                        del valid

                        continue

                    tile_pixels += valid.size

                    unique, counts = np.unique(
                        valid,
                        return_counts=True
                    )

                    for cls, count in zip(
                        unique,
                        counts
                    ):

                        cls = int(cls)

                        if cls in CLASS_MAP:

                            totals[
                                CLASS_MAP[cls]
                            ] += int(count)

                    effective_pixels += (
                        valid.size
                    )

                    del arr
                    del sampled
                    del mask_array
                    del sampled_mask
                    del valid

                if tile_pixels > 0:

                    rasters_used += 1

                    print(
                        "    Effective valid:",
                        f"{tile_pixels:,}"
                    )

        except Exception as e:

            print(
                "    Tile failed:",
                path.name,
                "|",
                str(e).splitlines()[0]
            )

        gc.collect()

    # --------------------------------------------------------
    # Build result
    # --------------------------------------------------------

    if effective_pixels > 0:

        row = {
            "basin_name": basin_name,
            "basin_area_km2": basin_area,
            "lulc_rasters_used": rasters_used,
            "lulc_valid_pixels": effective_pixels,
        }

        for feature in CLASS_MAP.values():

            row[
                f"{feature}_pct"
            ] = (
                totals[feature]
                / effective_pixels
                * 100.0
            )

        row[
            "lulc_class_pct_sum"
        ] = sum(
            row[
                f"{feature}_pct"
            ]
            for feature in CLASS_MAP.values()
        )

        row[
            "built_up_water_pct"
        ] = (
            row["built_up_pct"]
            + row["water_pct"]
        )

        row[
            "natural_vegetation_pct"
        ] = (
            row["tree_cover_pct"]
            + row["shrubland_pct"]
            + row["grassland_pct"]
        )

        row[
            "wetland_pct"
        ] = (
            row["herbaceous_wetland_pct"]
            + row["mangroves_pct"]
        )

        row[
            "lulc_coverage_pct"
        ] = 100.0

    else:

        row = {
            "basin_name": basin_name,
            "basin_area_km2": basin_area,
            "lulc_rasters_used": 0,
            "lulc_valid_pixels": 0,
        }

        for feature in CLASS_MAP.values():

            row[
                f"{feature}_pct"
            ] = np.nan

        row[
            "lulc_class_pct_sum"
        ] = np.nan

        row[
            "built_up_water_pct"
        ] = np.nan

        row[
            "natural_vegetation_pct"
        ] = np.nan

        row[
            "wetland_pct"
        ] = np.nan

        row[
            "lulc_coverage_pct"
        ] = np.nan

    results.append(row)

    print()
    print(
        "  Rasters used :",
        rasters_used
    )

    print(
        "  Effective pixels:",
        f"{effective_pixels:,}"
    )

    if effective_pixels > 0:

        print(
            "  Class sum    :",
            f"{row['lulc_class_pct_sum']:.2f}%"
        )

    else:

        print(
            "  Class sum    : NaN"
        )

    print()

    gc.collect()


# ------------------------------------------------------------
# SAVE
# ------------------------------------------------------------

df = pd.DataFrame(
    results
)

df.to_csv(
    OUTPUT,
    index=False
)


# ------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------

print("=" * 70)
print("LULC FEATURE VALIDATION")
print("=" * 70)

print()

print(
    "ROWS   :",
    len(df)
)

print(
    "COLUMNS:",
    len(df.columns)
)

print()

print("NULL COUNTS:")

null_counts = df.isna().sum()

for col, count in null_counts.items():

    if count > 0:

        print(
            f"  {col}: {count}"
        )

print()

print(
    "CLASS PERCENTAGE CHECK:"
)

valid_sum = df[
    "lulc_class_pct_sum"
].dropna()

if len(valid_sum) > 0:

    print(
        "MIN CLASS SUM:",
        round(
            valid_sum.min(),
            4
        )
    )

    print(
        "MAX CLASS SUM:",
        round(
            valid_sum.max(),
            4
        )
    )

    print(
        "MEAN CLASS SUM:",
        round(
            valid_sum.mean(),
            4
        )
    )

print()

print("LULC COVERAGE:")

print(
    df[
        [
            "basin_name",
            "basin_area_km2",
            "lulc_rasters_used",
            "lulc_valid_pixels",
            "lulc_coverage_pct",
            "lulc_class_pct_sum",
        ]
    ].to_string(
        index=False
    )
)

print()

print("=" * 70)
print("OUTPUT")
print("=" * 70)

print()

print(
    "OUTPUT:",
    OUTPUT
)

print(
    "SHAPE :",
    df.shape
)

print()

print(
    "LULC FEATURE ENGINEERING COMPLETE"
)

print("=" * 70)