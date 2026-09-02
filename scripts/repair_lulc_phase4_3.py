# -*- coding: utf-8 -*-

import os
import glob
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.enums import Resampling
from shapely.geometry import box

BASIN_FILE = r"data/raw/basin_boundaries/cwc_basins.geojson"
TILE_DIR = r"data/raw/land_use_land_cover/worldcover_tiles"
CSV_FILE = r"data/processed/lulc/lulc_basin_features.csv"

print("=" * 80)
print("CHETAKAI - PHASE 4.3 FAST LULC REPAIR")
print("=" * 80)

# ---------------------------------------------------------------------
# BASINS
# ---------------------------------------------------------------------

g = gpd.read_file(BASIN_FILE)

if g.crs is None:
    raise RuntimeError("Basin CRS missing.")

g = g.to_crs(4326)

targets = g[
    g["ba_name"].astype(str).str.contains(
        "Kutch|Saurashtra|Inland drainage in Rajasthan",
        case=False,
        na=False
    )
].copy()

if len(targets) != 2:
    raise RuntimeError(
        f"Expected 2 target basins, found {len(targets)}"
    )

print()
print("TARGET BASINS:")
print(targets[["ba_code", "ba_name"]].to_string(index=False))

# ---------------------------------------------------------------------
# CANONICAL IDS
# ---------------------------------------------------------------------

target_map = {}

for _, row in targets.iterrows():

    name = str(row["ba_name"])

    if "Kutch" in name or "Saurashtra" in name:
        target_map[row["ba_code"]] = "CWC_BASIN_018"

    elif "Inland drainage" in name:
        target_map[row["ba_code"]] = "CWC_BASIN_019"

# ---------------------------------------------------------------------
# WORLDCOVER TILES
# ---------------------------------------------------------------------

tile_files = sorted(
    glob.glob(
        os.path.join(
            TILE_DIR,
            "ESA_WorldCover_10m_2021_v200_*_Map.tif"
        )
    )
)

print()
print("WorldCover tiles available:", len(tile_files))

if not tile_files:
    raise RuntimeError("No WorldCover tiles found.")

# ---------------------------------------------------------------------
# WORLD COVER CLASSES
# ---------------------------------------------------------------------

classes = {
    10: "tree_cover_pct",
    20: "shrubland_pct",
    30: "grassland_pct",
    40: "cropland_pct",
    50: "built_up_pct",
    60: "bare_sparse_pct",
    70: "snow_ice_pct",
    80: "water_pct",
    90: "herbaceous_wetland_pct",
    95: "mangroves_pct",
    100: "moss_lichen_pct",
}

# ---------------------------------------------------------------------
# PROCESS BASIN
# ---------------------------------------------------------------------

def process_basin(row, canonical_id):

    geometry = row.geometry
    basin_name = str(row["ba_name"])

    print()
    print("=" * 80)
    print("PROCESSING:", canonical_id)
    print("BASIN:", basin_name)
    print("=" * 80)

    intersecting = []

    # -------------------------------------------------------------
    # FIND ACTUAL INTERSECTING TILES
    # -------------------------------------------------------------

    for tif in tile_files:

        try:

            with rasterio.open(tif) as src:

                basin_geom = gpd.GeoSeries(
                    [geometry],
                    crs="EPSG:4326"
                ).to_crs(src.crs).iloc[0]

                if basin_geom.intersects(box(*src.bounds)):
                    intersecting.append(tif)

        except Exception as e:

            print(
                "WARNING:",
                os.path.basename(tif),
                e
            )

    print()
    print("Intersecting tiles:", len(intersecting))

    if not intersecting:
        raise RuntimeError(
            f"No WorldCover tiles found for {canonical_id}"
        )

    # -------------------------------------------------------------
    # COUNTS
    # -------------------------------------------------------------

    counts = {
        cls: 0
        for cls in classes
    }

    total_valid = 0

    # -------------------------------------------------------------
    # READ AT 100 m EFFECTIVE RESOLUTION
    # -------------------------------------------------------------

    for n, tif in enumerate(intersecting, 1):

        name = os.path.basename(tif)

        print(
            f"[{n}/{len(intersecting)}] {name}",
            flush=True
        )

        with rasterio.open(tif) as src:

            basin_geom = gpd.GeoSeries(
                [geometry],
                crs="EPSG:4326"
            ).to_crs(src.crs).iloc[0]

            # -----------------------------------------------------
            # MASK FIRST AT 10 m
            # -----------------------------------------------------

            data, transform = mask(
                src,
                [basin_geom],
                crop=True,
                filled=False
            )

            arr = data[0]

            if arr.size == 0:
                continue

            # -----------------------------------------------------
            # DOWNSAMPLE 10 m -> ~100 m
            #
            # This is the major speed improvement.
            # -----------------------------------------------------

            h, w = arr.shape

            new_h = max(1, h // 10)
            new_w = max(1, w // 10)

            # Convert masked array to ordinary array.
            filled = arr.filled(0)

            # Use rasterio's efficient categorical resampling.
            from rasterio.warp import reproject

            destination = np.zeros(
                (new_h, new_w),
                dtype=filled.dtype
            )

            new_transform = transform * transform.scale(
                w / new_w,
                h / new_h
            )

            reproject(
                source=filled,
                destination=destination,
                src_transform=transform,
                src_crs=src.crs,
                dst_transform=new_transform,
                dst_crs=src.crs,
                resampling=Resampling.nearest
            )

            # -----------------------------------------------------
            # VALID PIXELS
            # -----------------------------------------------------

            valid = destination[
                destination != 0
            ]

            if valid.size == 0:
                continue

            total_valid += valid.size

            # -----------------------------------------------------
            # CLASS COUNTS
            # -----------------------------------------------------

            for cls in classes:

                counts[cls] += int(
                    np.count_nonzero(
                        valid == cls
                    )
                )

    if total_valid == 0:
        raise RuntimeError(
            f"No valid LULC pixels for {canonical_id}"
        )

    # -----------------------------------------------------------------
    # PERCENTAGES
    # -----------------------------------------------------------------

    result = {}

    for cls, column in classes.items():

        result[column] = (
            counts[cls] /
            total_valid
        ) * 100.0

    result["lulc_class_pct_sum"] = sum(
        result[x]
        for x in classes.values()
    )

    result["built_up_water_pct"] = (
        result["built_up_pct"] +
        result["water_pct"]
    )

    result["natural_vegetation_pct"] = (
        result["tree_cover_pct"] +
        result["shrubland_pct"] +
        result["grassland_pct"]
    )

    result["wetland_pct"] = (
        result["herbaceous_wetland_pct"] +
        result["mangroves_pct"] +
        result["moss_lichen_pct"]
    )

    result["lulc_coverage_pct"] = 100.0

    result["lulc_rasters_used"] = len(intersecting)

    result["lulc_valid_pixels"] = total_valid

    result["canonical_basin_id"] = canonical_id

    print()
    print("VALID 100m PIXELS:", total_valid)
    print("RASTERS USED:", len(intersecting))
    print("CLASS SUM:", round(
        result["lulc_class_pct_sum"], 6
    ))

    return result


# ---------------------------------------------------------------------
# PROCESS BOTH
# ---------------------------------------------------------------------

results = []

for _, row in targets.iterrows():

    canonical_id = target_map[row["ba_code"]]

    result = process_basin(
        row,
        canonical_id
    )

    results.append(result)


# ---------------------------------------------------------------------
# UPDATE CSV
# ---------------------------------------------------------------------

print()
print("=" * 80)
print("UPDATING LULC FEATURE CSV")
print("=" * 80)

df = pd.read_csv(CSV_FILE)

print("Existing rows:", len(df))

update_columns = [
    "lulc_rasters_used",
    "lulc_valid_pixels",
    "tree_cover_pct",
    "shrubland_pct",
    "grassland_pct",
    "cropland_pct",
    "built_up_pct",
    "bare_sparse_pct",
    "snow_ice_pct",
    "water_pct",
    "herbaceous_wetland_pct",
    "mangroves_pct",
    "moss_lichen_pct",
    "lulc_class_pct_sum",
    "built_up_water_pct",
    "natural_vegetation_pct",
    "wetland_pct",
    "lulc_coverage_pct",
]

for result in results:

    cid = result["canonical_basin_id"]

    idx = df.index[
        df["canonical_basin_id"].astype(str) == cid
    ]

    if len(idx) != 1:
        raise RuntimeError(
            f"Expected one CSV row for {cid}, "
            f"found {len(idx)}"
        )

    i = idx[0]

    for col in update_columns:
        df.loc[i, col] = result[col]


# ---------------------------------------------------------------------
# BACKUP
# ---------------------------------------------------------------------

backup = CSV_FILE.replace(
    ".csv",
    "_backup_before_fast_repair.csv"
)

df.to_csv(backup, index=False)

df.to_csv(CSV_FILE, index=False)

# ---------------------------------------------------------------------
# FINAL
# ---------------------------------------------------------------------

print()
print("=" * 80)
print("PHASE 4.3 FAST REPAIR COMPLETE")
print("=" * 80)

print()
print(
    df[
        df["canonical_basin_id"].isin(
            [
                "CWC_BASIN_018",
                "CWC_BASIN_019"
            ]
        )
    ].to_string(index=False)
)

print()
print("FINAL ROW COUNT:", len(df))
print("BACKUP:", backup)
print("UPDATED:", CSV_FILE)

print()
print("=" * 80)
