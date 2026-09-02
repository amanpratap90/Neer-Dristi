from pathlib import Path
import warnings
import math

import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.warp import transform_bounds

warnings.filterwarnings("ignore")

print("=" * 80)
print("CHETAKAI V1 DEM FEATURE ENGINEERING")
print("=" * 80)

ROOT = Path(__file__).resolve().parents[1]

DEM_DIR = ROOT / "data" / "raw" / "dem" / "copernicus_glo30"
INVENTORY = ROOT / "data" / "raw" / "dem" / "priority_dem_inventory.csv"
BASIN_DIR = ROOT / "data" / "raw" / "basin_boundaries"
OUT_DIR = ROOT / "data" / "processed" / "dem"

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = OUT_DIR / "dem_basin_features.csv"

print("DEM DIR     :", DEM_DIR)
print("INVENTORY   :", INVENTORY)
print("BASIN DIR   :", BASIN_DIR)
print("OUTPUT      :", OUTPUT)

# ---------------------------------------------------------------------
# DEM FILES
# ---------------------------------------------------------------------

dem_files = sorted(
    list(DEM_DIR.glob("*.tif")) +
    list(DEM_DIR.glob("*.tiff"))
)

if not dem_files:
    raise RuntimeError("No Copernicus DEM files found.")

print("\nDEM FILES FOUND:", len(dem_files))

# ---------------------------------------------------------------------
# INVENTORY
# ---------------------------------------------------------------------

required_tiles = set()

if INVENTORY.exists():
    inv = pd.read_csv(INVENTORY)

    if "dem_tile" in inv.columns:
        required_tiles = set(
            inv["dem_tile"]
            .astype(str)
            .str.replace(".tif", "", regex=False)
            .str.strip()
        )

available_tiles = {
    f.stem for f in dem_files
}

if required_tiles:
    missing_tiles = sorted(required_tiles - available_tiles)

    print("REQUIRED DEM TILES :", len(required_tiles))
    print("AVAILABLE REQUIRED :", len(required_tiles & available_tiles))
    print("MISSING REQUIRED   :", len(missing_tiles))

    if missing_tiles:
        print("MISSING TILES:")
        for tile in missing_tiles:
            print("  -", tile)

# ---------------------------------------------------------------------
# BASIN FILE
# ---------------------------------------------------------------------

basin_files = sorted(
    list(BASIN_DIR.glob("*.geojson")) +
    list(BASIN_DIR.glob("*.shp"))
)

if not basin_files:
    raise RuntimeError("No basin boundary file found.")

preferred = [
    f for f in basin_files
    if "basin" in f.name.lower()
    and "subbasin" not in f.name.lower()
]

basin_file = preferred[0] if preferred else basin_files[0]

print("\nBASIN FILE:", basin_file)

basins = gpd.read_file(basin_file)

if basins.empty:
    raise RuntimeError("Basin file is empty.")

# ---------------------------------------------------------------------
# BASIN NAME
# ---------------------------------------------------------------------

candidates = [
    "basin_name",
    "BASIN_NAME",
    "basin",
    "BASIN",
    "name",
    "NAME",
    "river_basin",
    "River_Basin",
    "id",
    "ID"
]

basin_column = None

for col in candidates:
    if col in basins.columns and basins[col].notna().any():
        basin_column = col
        break

if basin_column is None:
    non_geom = [
        c for c in basins.columns
        if c != basins.geometry.name
    ]

    if not non_geom:
        raise RuntimeError("No basin identifier column found.")

    basin_column = non_geom[0]

basins["basin_name"] = (
    basins[basin_column]
    .astype(str)
    .str.strip()
)

basins = basins[
    ~basins["basin_name"].isin(
        ["", "nan", "None", "NULL", "null"]
    )
].copy()

basins = basins[
    ~basins["basin_name"].duplicated()
].copy()

if basins.crs is None:
    basins = basins.set_crs("EPSG:4326")

print("BASIN CRS:", basins.crs)
print("BASINS   :", len(basins))
print("NAME COL :", basin_column)

# ---------------------------------------------------------------------
# PREPARE BASIN GEOMETRIES IN WGS84
# ---------------------------------------------------------------------

basins_wgs84 = basins.to_crs("EPSG:4326")

# ---------------------------------------------------------------------
# HELPER: APPROXIMATE METERS PER DEGREE
# ---------------------------------------------------------------------

def meters_per_degree(latitude):
    lat = math.radians(latitude)

    meters_lat = (
        111132.92
        - 559.82 * math.cos(2 * lat)
        + 1.175 * math.cos(4 * lat)
        - 0.0023 * math.cos(6 * lat)
    )

    meters_lon = (
        111412.84 * math.cos(lat)
        - 93.5 * math.cos(3 * lat)
        + 0.118 * math.cos(5 * lat)
    )

    return meters_lon, meters_lat


# ---------------------------------------------------------------------
# PROCESS DEM TILES
# ---------------------------------------------------------------------

records = []

print("\nPROCESSING DEM TILES...")
print("-" * 80)

for idx, dem_file in enumerate(dem_files, start=1):

    print(
        f"[{idx:03d}/{len(dem_files):03d}] "
        f"{dem_file.stem}"
    )

    try:

        with rasterio.open(dem_file) as src:

            if src.crs is None:
                print("  SKIPPED: missing CRS")
                continue

            # ---------------------------------------------------------
            # Transform raster bounds to WGS84
            # ---------------------------------------------------------

            raster_bounds = transform_bounds(
                src.crs,
                "EPSG:4326",
                *src.bounds
            )

            raster_box = (
                raster_bounds[0],
                raster_bounds[1],
                raster_bounds[2],
                raster_bounds[3]
            )

            tile_minx, tile_miny, tile_maxx, tile_maxy = raster_box

            # ---------------------------------------------------------
            # ONLY PROCESS BASINS THAT INTERSECT TILE
            # ---------------------------------------------------------

            candidate_basins = basins_wgs84[
                (basins_wgs84.geometry.bounds["maxx"] >= tile_minx) &
                (basins_wgs84.geometry.bounds["minx"] <= tile_maxx) &
                (basins_wgs84.geometry.bounds["maxy"] >= tile_miny) &
                (basins_wgs84.geometry.bounds["miny"] <= tile_maxy)
            ]

            if candidate_basins.empty:
                continue

            basin_projected = candidate_basins.to_crs(src.crs)

            tile_records = 0

            for _, basin in basin_projected.iterrows():

                basin_name = str(basin["basin_name"])
                geometry = basin.geometry

                if geometry is None or geometry.is_empty:
                    continue

                try:

                    # -------------------------------------------------
                    # MASK ONLY INTERSECTING AREA
                    # -------------------------------------------------

                    data, transform = mask(
                        src,
                        [geometry],
                        crop=True,
                        filled=False
                    )

                    elevation = data[0].astype("float64")

                    if np.ma.isMaskedArray(elevation):
                        elevation = elevation.filled(np.nan)

                    nodata = src.nodata

                    if nodata is not None:
                        elevation[
                            np.isclose(
                                elevation,
                                nodata,
                                equal_nan=False
                            )
                        ] = np.nan

                    valid = elevation[
                        np.isfinite(elevation)
                    ]

                    if valid.size == 0:
                        continue

                    # -------------------------------------------------
                    # ELEVATION FEATURES
                    # -------------------------------------------------

                    mean_elev = float(np.mean(valid))
                    min_elev = float(np.min(valid))
                    max_elev = float(np.max(valid))
                    median_elev = float(np.median(valid))
                    std_elev = float(np.std(valid))

                    relief = max_elev - min_elev

                    # -------------------------------------------------
                    # SLOPE
                    # -------------------------------------------------

                    try:

                        center_lat = float(
                            geometry.centroid.y
                        )

                        meters_lon, meters_lat = (
                            meters_per_degree(center_lat)
                        )

                        pixel_x_deg = abs(transform.a)
                        pixel_y_deg = abs(transform.e)

                        pixel_x_m = (
                            pixel_x_deg *
                            meters_lon
                        )

                        pixel_y_m = (
                            pixel_y_deg *
                            meters_lat
                        )

                        if (
                            pixel_x_m <= 0 or
                            pixel_y_m <= 0
                        ):
                            raise ValueError(
                                "Invalid pixel dimensions."
                            )

                        filled_elevation = elevation.copy()

                        valid_mask = np.isfinite(
                            filled_elevation
                        )

                        if not valid_mask.any():
                            raise ValueError(
                                "No valid elevation."
                            )

                        # Fill small NoData gaps only for gradient
                        # calculation. Original elevation statistics
                        # remain based only on valid pixels.
                        median_value = float(
                            np.nanmedian(
                                filled_elevation
                            )
                        )

                        gradient_input = np.where(
                            valid_mask,
                            filled_elevation,
                            median_value
                        )

                        gy, gx = np.gradient(
                            gradient_input,
                            pixel_y_m,
                            pixel_x_m
                        )

                        slope_deg = np.degrees(
                            np.arctan(
                                np.sqrt(
                                    gx ** 2 +
                                    gy ** 2
                                )
                            )
                        )

                        slope_valid = slope_deg[
                            valid_mask &
                            np.isfinite(slope_deg)
                        ]

                        mean_slope = (
                            float(
                                np.mean(slope_valid)
                            )
                            if slope_valid.size
                            else np.nan
                        )

                        max_slope = (
                            float(
                                np.max(slope_valid)
                            )
                            if slope_valid.size
                            else np.nan
                        )

                    except Exception:

                        mean_slope = np.nan
                        max_slope = np.nan

                    records.append(
                        {
                            "basin_name": basin_name,
                            "dem_tile": dem_file.stem,
                            "mean_elevation_m": mean_elev,
                            "min_elevation_m": min_elev,
                            "max_elevation_m": max_elev,
                            "median_elevation_m": median_elev,
                            "elevation_std_m": std_elev,
                            "relief_m": relief,
                            "mean_slope_deg": mean_slope,
                            "max_slope_deg": max_slope
                        }
                    )

                    tile_records += 1

                except ValueError as e:

                    if "do not overlap" not in str(e):
                        print(
                            f"  Basin failed: "
                            f"{basin_name} -> {e}"
                        )

                except Exception as e:

                    print(
                        f"  Basin failed: "
                        f"{basin_name} -> {e}"
                    )

            if tile_records:
                print(
                    f"  INTERSECTING BASINS: "
                    f"{tile_records}"
                )

    except Exception as e:

        print(
            f"  DEM FAILED: {dem_file.name} -> {e}"
        )

# ---------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------

print("\n" + "=" * 80)
print("DEM PROCESSING COMPLETE")
print("=" * 80)

print("RAW TILE/BASIN RECORDS:", len(records))

if not records:
    raise RuntimeError(
        "No DEM feature records generated."
    )

df = pd.DataFrame(records)

numeric_cols = [
    "mean_elevation_m",
    "min_elevation_m",
    "max_elevation_m",
    "median_elevation_m",
    "elevation_std_m",
    "relief_m",
    "mean_slope_deg",
    "max_slope_deg"
]

for col in numeric_cols:
    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )

# ---------------------------------------------------------------------
# BASIN LEVEL AGGREGATION
# ---------------------------------------------------------------------

basin_df = (
    df.groupby(
        "basin_name",
        as_index=False
    )
    .agg(
        mean_elevation_m=(
            "mean_elevation_m",
            "mean"
        ),
        min_elevation_m=(
            "min_elevation_m",
            "min"
        ),
        max_elevation_m=(
            "max_elevation_m",
            "max"
        ),
        median_elevation_m=(
            "median_elevation_m",
            "mean"
        ),
        elevation_std_m=(
            "elevation_std_m",
            "mean"
        ),
        relief_m=(
            "relief_m",
            "max"
        ),
        mean_slope_deg=(
            "mean_slope_deg",
            "mean"
        ),
        max_slope_deg=(
            "max_slope_deg",
            "max"
        ),
        dem_tile_count=(
            "dem_tile",
            "nunique"
        )
    )
)

# ---------------------------------------------------------------------
# TERRAIN INDICATORS
# ---------------------------------------------------------------------

relief_median = basin_df["relief_m"].median()
slope_median = basin_df["mean_slope_deg"].median()

basin_df["high_relief_flag"] = (
    basin_df["relief_m"] >= relief_median
).astype(int)

basin_df["steep_terrain_flag"] = (
    basin_df["mean_slope_deg"] >= slope_median
).astype(int)

basin_df["elevation_range_ratio"] = np.where(
    basin_df["mean_elevation_m"].abs() > 0,
    basin_df["relief_m"] /
    basin_df["mean_elevation_m"].abs(),
    np.nan
)

# ---------------------------------------------------------------------
# COVERAGE INFORMATION
# ---------------------------------------------------------------------

available_counts = (
    df.groupby("basin_name")["dem_tile"]
    .nunique()
    .reset_index(
        name="available_dem_tile_count"
    )
)

basin_df = basin_df.merge(
    available_counts,
    on="basin_name",
    how="left"
)

basin_df = basin_df.replace(
    [np.inf, -np.inf],
    np.nan
)

basin_df = basin_df.sort_values(
    "basin_name"
).reset_index(drop=True)

# ---------------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------------

basin_df.to_csv(
    OUTPUT,
    index=False
)

# Save tile-level diagnostics too.
tile_output = OUT_DIR / "dem_tile_basin_features.csv"

df.to_csv(
    tile_output,
    index=False
)

print("\nOUTPUTS SAVED:")
print("BASIN FEATURES:", OUTPUT)
print("TILE FEATURES  :", tile_output)

print("\nFINAL BASIN SHAPE:")
print(basin_df.shape)

print("\nFINAL BASINS:")
for name in basin_df["basin_name"]:
    print(
        f"  {name} | "
        f"tiles={int(basin_df.loc[basin_df['basin_name'] == name, 'dem_tile_count'].iloc[0])}"
    )

print("\nCOLUMNS:")
for col in basin_df.columns:
    print("  -", col)

print("\n" + "=" * 80)
print("DEM FEATURE ENGINEERING SUCCESS")
print("=" * 80)
