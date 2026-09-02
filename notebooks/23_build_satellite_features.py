from pathlib import Path
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from shapely.geometry import box

warnings.filterwarnings("ignore")

print("=" * 70)
print("CHETAKAI V1 SATELLITE FEATURE ENGINEERING - MVP")
print("=" * 70)

ROOT = Path(__file__).resolve().parents[1]

SAT_DIR = ROOT / "data" / "raw" / "satellite" / "sentinel2" / "bands"
BASIN_DIR = ROOT / "data" / "raw" / "basin_boundaries"
OUT_DIR = ROOT / "data" / "processed" / "satellite"

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = OUT_DIR / "satellite_basin_features.csv"

MAX_SIZE = 1200


def get_basin_file():
    preferred = BASIN_DIR / "cwc_basins.geojson"

    if preferred.exists():
        return preferred

    candidates = list(BASIN_DIR.glob("*.geojson"))

    if not candidates:
        raise RuntimeError("No basin boundary GeoJSON found.")

    return candidates[0]


def get_name_col(gdf):
    candidates = [
        "basin_name",
        "Basin_Name",
        "BASIN_NAME",
        "basin",
        "BASIN",
        "ba_name",
        "name",
        "Name",
        "NAME",
        "id",
    ]

    for col in candidates:
        if col in gdf.columns:
            return col

    return None


def discover_products():
    files = list(SAT_DIR.rglob("*.jp2"))

    products = {}

    for file in files:
        name = file.name.upper()

        band = None

        for candidate in ["B02", "B03", "B04", "B08"]:
            if f"_{candidate}_" in name:
                band = candidate
                break

        if band is None:
            continue

        tile_id = name.split("_B")[0]

        if tile_id not in products:
            products[tile_id] = {}

        products[tile_id][band] = file

    return products


def read_band(path, geometry, basin_crs):
    with rasterio.open(path) as src:

        basin = gpd.GeoSeries(
            [geometry],
            crs=basin_crs
        ).to_crs(src.crs).iloc[0]

        tile_box = box(
            src.bounds.left,
            src.bounds.bottom,
            src.bounds.right,
            src.bounds.top
        )

        if not basin.intersects(tile_box):
            return None

        intersection = basin.intersection(tile_box)

        if intersection.is_empty:
            return None

        bounds = intersection.bounds

        window = from_bounds(
            bounds[0],
            bounds[1],
            bounds[2],
            bounds[3],
            transform=src.transform
        )

        window = window.round_offsets().round_lengths()

        width = int(window.width)
        height = int(window.height)

        if width <= 0 or height <= 0:
            return None

        scale = max(
            width / MAX_SIZE,
            height / MAX_SIZE,
            1
        )

        out_width = max(
            1,
            int(width / scale)
        )

        out_height = max(
            1,
            int(height / scale)
        )

        data = src.read(
            1,
            window=window,
            out_shape=(out_height, out_width),
            resampling=Resampling.average
        ).astype(np.float32)

        if src.nodata is not None:
            data[data == src.nodata] = np.nan

        return data


def clean_band(data):
    data = data.astype(np.float32)

    data[~np.isfinite(data)] = np.nan

    finite = np.isfinite(data)

    if np.any(finite):

        maximum = np.nanmax(data)

        if maximum > 2:
            data = data / 10000.0

    data[
        (data < 0) |
        (data > 1.5)
    ] = np.nan

    return data


def calculate_stats(values):

    values = values[np.isfinite(values)]

    if values.size == 0:
        return {
            "mean": np.nan,
            "median": np.nan,
            "std": np.nan,
            "min": np.nan,
            "max": np.nan
        }

    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values))
    }


print()
print("LOADING BASINS...")

basin_file = get_basin_file()

basins = gpd.read_file(basin_file)

if basins.crs is None:
    raise RuntimeError("Basin CRS is missing.")

print("Basins    :", len(basins))
print("Basin CRS :", basins.crs)

name_col = get_name_col(basins)

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


print()
print("SEARCHING SENTINEL-2 BANDS...")

products = discover_products()

print("Sentinel-2 tiles:", len(products))

for tile, bands in products.items():

    print(
        " ",
        tile,
        "->",
        ", ".join(sorted(bands.keys()))
    )


required_bands = {
    "B03",
    "B04",
    "B08"
}

valid_products = {
    tile: bands
    for tile, bands in products.items()
    if required_bands.issubset(bands.keys())
}


print()
print("VALID FEATURE PRODUCTS:", len(valid_products))

if not valid_products:
    raise RuntimeError(
        "No Sentinel-2 products containing B03, B04 and B08 were found."
    )


print()
print("=" * 70)
print("PROCESSING BASINS")
print("=" * 70)


results = []

basin_crs = basins.crs


for index, basin in basins.iterrows():

    basin_name = str(basin["basin_name"])

    print()
    print(
        f"[{index + 1:03d}/{len(basins):03d}] "
        f"BASIN {basin_name}"
    )

    geometry = basin.geometry

    ndvi_values_all = []
    ndwi_values_all = []

    products_used = 0
    valid_pixels = 0

    for tile, bands in valid_products.items():

        try:

            red = read_band(
                bands["B04"],
                geometry,
                basin_crs
            )

            green = read_band(
                bands["B03"],
                geometry,
                basin_crs
            )

            nir = read_band(
                bands["B08"],
                geometry,
                basin_crs
            )

            if (
                red is None or
                green is None or
                nir is None
            ):

                print(
                    f"  {tile}: no intersection"
                )

                continue

            red = clean_band(red)
            green = clean_band(green)
            nir = clean_band(nir)

            h = min(
                red.shape[0],
                green.shape[0],
                nir.shape[0]
            )

            w = min(
                red.shape[1],
                green.shape[1],
                nir.shape[1]
            )

            red = red[:h, :w]
            green = green[:h, :w]
            nir = nir[:h, :w]

            valid = (
                np.isfinite(red) &
                np.isfinite(green) &
                np.isfinite(nir)
            )

            if not np.any(valid):

                print(
                    f"  {tile}: no valid pixels"
                )

                continue

            ndvi_den = nir + red
            ndwi_den = nir + green

            ndvi = np.full(
                red.shape,
                np.nan,
                dtype=np.float32
            )

            ndwi = np.full(
                red.shape,
                np.nan,
                dtype=np.float32
            )

            valid_ndvi = (
                valid &
                (np.abs(ndvi_den) > 1e-6)
            )

            valid_ndwi = (
                valid &
                (np.abs(ndwi_den) > 1e-6)
            )

            ndvi[valid_ndvi] = (
                (
                    nir[valid_ndvi] -
                    red[valid_ndvi]
                )
                /
                ndvi_den[valid_ndvi]
            )

            ndwi[valid_ndwi] = (
                (
                    green[valid_ndwi] -
                    nir[valid_ndwi]
                )
                /
                ndwi_den[valid_ndwi]
            )

            ndvi_vals = ndvi[
                np.isfinite(ndvi)
            ]

            ndwi_vals = ndwi[
                np.isfinite(ndwi)
            ]

            if ndvi_vals.size:

                ndvi_values_all.extend(
                    ndvi_vals.tolist()
                )

                valid_pixels += ndvi_vals.size

            if ndwi_vals.size:

                ndwi_values_all.extend(
                    ndwi_vals.tolist()
                )

            products_used += 1

            print(
                f"  {tile}: "
                f"{ndvi_vals.size:,} valid pixels"
            )

        except Exception as e:

            print(
                f"  {tile}: ERROR - "
                f"{type(e).__name__}: {e}"
            )

            continue


    ndvi_arr = np.asarray(
        ndvi_values_all,
        dtype=np.float32
    )

    ndwi_arr = np.asarray(
        ndwi_values_all,
        dtype=np.float32
    )


    ndvi_stats = calculate_stats(
        ndvi_arr
    )

    ndwi_stats = calculate_stats(
        ndwi_arr
    )


    if ndvi_arr.size:

        vegetation_pct = float(
            np.mean(ndvi_arr > 0.30) * 100
        )

    else:

        vegetation_pct = np.nan


    if ndwi_arr.size:

        water_pct = float(
            np.mean(ndwi_arr > 0.20) * 100
        )

    else:

        water_pct = np.nan


    available = 1 if products_used > 0 else 0


    print()
    print(
        "  RESULT:",
        (
            "Satellite available"
            if available
            else
            "Satellite unavailable"
        )
    )


    results.append({

        "basin_name":
            basin_name,

        "satellite_products_used":
            products_used,

        "satellite_valid_pixels":
            valid_pixels,

        "ndvi_mean":
            ndvi_stats["mean"],

        "ndvi_median":
            ndvi_stats["median"],

        "ndvi_std":
            ndvi_stats["std"],

        "ndvi_min":
            ndvi_stats["min"],

        "ndvi_max":
            ndvi_stats["max"],

        "ndwi_mean":
            ndwi_stats["mean"],

        "ndwi_median":
            ndwi_stats["median"],

        "ndwi_std":
            ndwi_stats["std"],

        "ndwi_min":
            ndwi_stats["min"],

        "ndwi_max":
            ndwi_stats["max"],

        "vegetation_pct":
            vegetation_pct,

        "water_pct":
            water_pct,

        "satellite_data_available":
            available
    })


df = pd.DataFrame(results)

df.to_csv(
    OUTPUT,
    index=False
)


print()
print("=" * 70)
print("SATELLITE FEATURE VALIDATION")
print("=" * 70)

print()
print("ROWS   :", len(df))
print("COLUMNS:", len(df.columns))

print()
print("SATELLITE AVAILABILITY:")

print(
    df[
        [
            "basin_name",
            "satellite_products_used",
            "satellite_valid_pixels",
            "ndvi_mean",
            "ndwi_mean",
            "vegetation_pct",
            "water_pct",
            "satellite_data_available"
        ]
    ].to_string(index=False)
)


print()
print("NULL COUNTS:")

for col in [
    "ndvi_mean",
    "ndvi_median",
    "ndvi_std",
    "ndvi_min",
    "ndvi_max",
    "ndwi_mean",
    "ndwi_median",
    "ndwi_std",
    "ndwi_min",
    "ndwi_max",
    "vegetation_pct",
    "water_pct"
]:

    print(
        f"  {col}: "
        f"{df[col].isna().sum()}"
    )


print()
print("=" * 70)
print("SATELLITE FEATURE ENGINEERING COMPLETE")
print("=" * 70)

print()
print("OUTPUT:", OUTPUT)
print("SHAPE :", df.shape)