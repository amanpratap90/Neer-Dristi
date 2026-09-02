from pathlib import Path
from collections import defaultdict
import re
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]

SATELLITE_DIR = ROOT / "data" / "raw" / "satellite"
BASIN_FILE = ROOT / "data" / "raw" / "basin_boundaries" / "cwc_basins.geojson"
OUTPUT_DIR = ROOT / "data" / "processed" / "satellite"
OUTPUT_FILE = OUTPUT_DIR / "satellite_basin_features.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def discover_scenes():
    scenes = defaultdict(dict)

    pattern = re.compile(
        r"^(?:T)?([0-9]{2}[A-Z]{3})_(\d{8})(?:T\d+)?_B(02|03|04|08)",
        re.IGNORECASE
    )

    for f in SATELLITE_DIR.rglob("*"):
        if not f.is_file():
            continue

        if f.suffix.lower() not in {".tif", ".jp2"}:
            continue

        m = pattern.search(f.name)

        if not m:
            continue

        tile = m.group(1).upper()
        date = m.group(2)
        band = m.group(3)

        scenes[(tile, date)][band] = f

    complete = {}

    for key, bands in scenes.items():
        if {"03", "04", "08"}.issubset(bands):
            complete[key] = bands

    return complete


def safe_stats(arr):
    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return {
            "mean": np.nan,
            "median": np.nan,
            "std": np.nan,
            "p10": np.nan,
            "p90": np.nan,
        }

    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr)),
        "p10": float(np.percentile(arr, 10)),
        "p90": float(np.percentile(arr, 90)),
    }


def process_scene(tile, date, bands, basins):
    print(f"\nPROCESSING {tile} | {date}")

    try:
        with rasterio.open(bands["04"]) as red_src:
            red_crs = red_src.crs

        basins_local = basins.to_crs(red_crs)

        scene_bounds = None

        with rasterio.open(bands["04"]) as src:
            scene_bounds = src.bounds

        rows = []

        for _, basin in basins_local.iterrows():

            basin_id = (
                basin.get("ba_code")
                if pd.notna(basin.get("ba_code"))
                else basin.get("bacode")
            )

            basin_name = basin.get("ba_name", "")

            geom = [basin.geometry]

            try:
                with rasterio.open(bands["04"]) as red_src:
                    red, transform = mask(
                        red_src,
                        geom,
                        crop=True,
                        filled=True,
                        nodata=0
                    )
                    red = red[0].astype("float32")

                with rasterio.open(bands["03"]) as green_src:
                    green, _ = mask(
                        green_src,
                        geom,
                        crop=True,
                        filled=True,
                        nodata=0
                    )
                    green = green[0].astype("float32")

                with rasterio.open(bands["08"]) as nir_src:
                    nir, _ = mask(
                        nir_src,
                        geom,
                        crop=True,
                        filled=True,
                        nodata=0
                    )
                    nir = nir[0].astype("float32")

            except ValueError:
                continue

            if red.size == 0:
                continue

            valid = (
                np.isfinite(red)
                & np.isfinite(green)
                & np.isfinite(nir)
                & (red > 0)
                & (green > 0)
                & (nir > 0)
            )

            valid_count = int(valid.sum())

            if valid_count < 100:
                continue

            red = red[valid]
            green = green[valid]
            nir = nir[valid]

            ndvi_den = nir + red
            ndwi_den = green + nir

            ndvi = np.full_like(nir, np.nan, dtype="float32")
            ndwi = np.full_like(nir, np.nan, dtype="float32")

            ndvi_valid = np.abs(ndvi_den) > 1e-6
            ndwi_valid = np.abs(ndwi_den) > 1e-6

            ndvi[ndvi_valid] = (
                (nir[ndvi_valid] - red[ndvi_valid])
                / ndvi_den[ndvi_valid]
            )

            ndwi[ndwi_valid] = (
                (green[ndwi_valid] - nir[ndwi_valid])
                / ndwi_den[ndwi_valid]
            )

            ndvi = ndvi[np.isfinite(ndvi)]
            ndwi = ndwi[np.isfinite(ndwi)]

            if ndvi.size == 0 or ndwi.size == 0:
                continue

            ndvi = np.clip(ndvi, -1, 1)
            ndwi = np.clip(ndwi, -1, 1)

            vegetation_fraction = float(np.mean(ndvi > 0.30))
            water_fraction = float(np.mean(ndwi > 0.20))

            ndvi_stats = safe_stats(ndvi)
            ndwi_stats = safe_stats(ndwi)

            rows.append({
                "canonical_basin_id": str(basin_id),
                "basin_name": str(basin_name),
                "tile": tile,
                "observation_date": pd.to_datetime(date, format="%Y%m%d"),

                "ndvi_mean": ndvi_stats["mean"],
                "ndvi_median": ndvi_stats["median"],
                "ndvi_std": ndvi_stats["std"],
                "ndvi_p10": ndvi_stats["p10"],
                "ndvi_p90": ndvi_stats["p90"],

                "ndwi_mean": ndwi_stats["mean"],
                "ndwi_median": ndwi_stats["median"],
                "ndwi_std": ndwi_stats["std"],
                "ndwi_p10": ndwi_stats["p10"],
                "ndwi_p90": ndwi_stats["p90"],

                "vegetation_fraction": vegetation_fraction,
                "water_fraction": water_fraction,

                "valid_pixel_count": valid_count
            })

        print(f"  Basin records: {len(rows)}")

        return rows

    except Exception as e:
        print(f"  ERROR: {e}")
        return []


def main():

    print("=" * 80)
    print("CHETAKAI SATELLITE FEATURE ENGINEERING")
    print("=" * 80)

    print("\nLoading basin boundaries...")

    basins = gpd.read_file(BASIN_FILE)

    print(f"Basins loaded: {len(basins)}")
    print(f"Basin CRS: {basins.crs}")

    print("\nDiscovering complete Sentinel-2 scenes...")

    scenes = discover_scenes()

    print(f"Complete scenes found: {len(scenes)}")

    for (tile, date), bands in sorted(scenes.items()):
        print(
            f"  {tile} | {date} | "
            f"B03={bands['03'].name} | "
            f"B04={bands['04'].name} | "
            f"B08={bands['08'].name}"
        )

    all_rows = []

    for (tile, date), bands in sorted(scenes.items()):

        rows = process_scene(
            tile,
            date,
            bands,
            basins
        )

        all_rows.extend(rows)

    if not all_rows:
        raise RuntimeError(
            "No satellite features were generated. "
            "Check Sentinel-2 files and basin overlap."
        )

    df = pd.DataFrame(all_rows)

    df["observation_date"] = pd.to_datetime(
        df["observation_date"]
    )

    df = df.sort_values(
        ["canonical_basin_id", "observation_date", "tile"]
    )

    df = df.drop_duplicates(
        subset=[
            "canonical_basin_id",
            "observation_date",
            "tile"
        ],
        keep="first"
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\n" + "=" * 80)
    print("SATELLITE PROCESSING COMPLETE")
    print("=" * 80)

    print(f"Output: {OUTPUT_FILE}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")
    print(
        f"Basins represented: "
        f"{df['canonical_basin_id'].nunique()}"
    )

    print("\nDate range:")
    print(df["observation_date"].min())
    print(df["observation_date"].max())

    print("\nFeatures:")
    print(
        df[
            [
                "ndvi_mean",
                "ndwi_mean",
                "vegetation_fraction",
                "water_fraction"
            ]
        ].describe()
    )

    print("\nSample:")
    print(df.head(10).to_string(index=False))

    print("\nDONE.")


if __name__ == "__main__":
    main()