from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.warp import transform_geom
from shapely.geometry import mapping
import warnings

warnings.filterwarnings("ignore")

print("=" * 70)
print("CHETAKAI V1 POPULATION FEATURE ENGINEERING")
print("=" * 70)

ROOT = Path(__file__).resolve().parents[1]

BASIN_FILE = (
    ROOT
    / "data"
    / "raw"
    / "basin_boundaries"
    / "cwc_basins.geojson"
)

POP_RASTER = (
    ROOT
    / "data"
    / "raw"
    / "population"
    / "worldpop_india_2020_1km.tif"
)

OUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "population"
)

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = (
    OUT_DIR
    / "population_basin_features.csv"
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
        "id"
    ]

    for col in candidates:
        if col in gdf.columns:
            return col

    return None


print()
print("CHECKING INPUTS...")

if not BASIN_FILE.exists():
    raise RuntimeError(
        f"Basin file not found: {BASIN_FILE}"
    )

if not POP_RASTER.exists():
    raise RuntimeError(
        f"Population raster not found: {POP_RASTER}"
    )

print("Basin file :", BASIN_FILE)
print("Population :", POP_RASTER)


print()
print("LOADING BASINS...")

basins = gpd.read_file(BASIN_FILE)

if basins.empty:
    raise RuntimeError(
        "Basin file contains no features."
    )

if basins.crs is None:
    raise RuntimeError(
        "Basin CRS is missing."
    )

name_col = find_name_column(basins)

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

print("Basins    :", len(basins))
print("Basin CRS :", basins.crs)


print()
print("PREPARING BASIN AREAS...")

area_gdf = basins[
    ["basin_name", "geometry"]
].copy()

area_gdf = area_gdf.to_crs(6933)

basin_area_map = dict(
    zip(
        area_gdf["basin_name"],
        area_gdf.geometry.area / 1_000_000
    )
)

print("Area calculation complete.")


print()
print("OPENING POPULATION RASTER...")

with rasterio.open(POP_RASTER) as src:

    print("Raster CRS     :", src.crs)
    print("Raster size    :", src.width, "x", src.height)
    print("Resolution     :", src.res)
    print("Band count     :", src.count)
    print("NoData         :", src.nodata)
    print("Data type      :", src.dtypes[0])
    print("Bounds         :", src.bounds)

    raster_crs = src.crs

    print()
    print("=" * 70)
    print("PROCESSING BASINS")
    print("=" * 70)

    results = []

    for i, basin in basins.iterrows():

        basin_name = str(
            basin["basin_name"]
        )

        print()
        print(
            f"[{len(results) + 1:03d}/{len(basins):03d}] "
            f"{basin_name}"
        )

        basin_area_km2 = float(
            basin_area_map.get(
                basin_name,
                np.nan
            )
        )

        population_total = np.nan
        valid_pixels = 0
        population_mean = np.nan
        population_min = np.nan
        population_max = np.nan

        try:

            raster_geometry = transform_geom(
                basins.crs,
                raster_crs,
                mapping(basin.geometry)
            )

            data, _ = mask(
                src,
                [raster_geometry],
                crop=True,
                filled=False
            )

            arr = data[0]

            if np.ma.isMaskedArray(arr):
                values = arr.compressed()
            else:

                values = arr.reshape(-1)

                if src.nodata is not None:
                    values = values[
                        values != src.nodata
                    ]

            values = values.astype(
                np.float64
            )

            values = values[
                np.isfinite(values)
            ]

            values = values[
                values >= 0
            ]

            if len(values) > 0:

                valid_pixels = len(values)

                population_total = float(
                    values.sum()
                )

                population_mean = float(
                    values.mean()
                )

                population_min = float(
                    values.min()
                )

                population_max = float(
                    values.max()
                )

        except Exception as e:

            print(
                "  Population failed:",
                str(e).splitlines()[0]
            )

        population_density = np.nan

        if (
            np.isfinite(population_total)
            and np.isfinite(basin_area_km2)
            and basin_area_km2 > 0
        ):

            population_density = (
                population_total
                / basin_area_km2
            )

        results.append({

            "basin_name":
                basin_name,

            "basin_area_km2":
                basin_area_km2,

            "population_total":
                population_total,

            "population_density_per_km2":
                population_density,

            "population_valid_pixels":
                valid_pixels,

            "population_mean_pixel_value":
                population_mean,

            "population_min_pixel_value":
                population_min,

            "population_max_pixel_value":
                population_max,

            "population_source":
                "WorldPop 2020 1km",

            "population_year":
                2020

        })

        print(
            "  Population total :",
            (
                f"{population_total:,.2f}"
                if np.isfinite(population_total)
                else "NaN"
            )
        )

        print(
            "  Density / km2    :",
            (
                f"{population_density:,.2f}"
                if np.isfinite(population_density)
                else "NaN"
            )
        )

        print(
            "  Valid pixels     :",
            f"{valid_pixels:,}"
        )


df = pd.DataFrame(results)

print()
print("=" * 70)
print("VALIDATION")
print("=" * 70)

print()
print("Rows    :", len(df))
print("Columns :", len(df.columns))

print()
print("NULL COUNTS")

nulls = df.isna().sum()

for column, count in nulls.items():

    if count > 0:

        print(
            f"  {column}: {count}"
        )


print()
print("POPULATION STATISTICS")

valid_pop = df[
    "population_total"
].dropna()

if len(valid_pop) > 0:

    print(
        "Min population :",
        f"{valid_pop.min():,.2f}"
    )

    print(
        "Max population :",
        f"{valid_pop.max():,.2f}"
    )

    print(
        "Mean population:",
        f"{valid_pop.mean():,.2f}"
    )


print()
print("SAVING OUTPUT...")

df.to_csv(
    OUTPUT,
    index=False
)

print("OUTPUT:", OUTPUT)
print("SHAPE :", df.shape)

print()
print("=" * 70)
print("POPULATION FEATURE ENGINEERING COMPLETE")
print("=" * 70)