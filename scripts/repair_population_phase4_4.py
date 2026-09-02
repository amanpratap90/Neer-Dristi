import os
import shutil
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask

BASIN_FILE = r"data/raw/basin_boundaries/cwc_basins.geojson"
WORLDPOP = r"data/raw/population/worldpop_india_2020_1km.tif"
CSV = r"data/processed/population/population_basin_features.csv"
BACKUP = r"data/processed/population/population_basin_features_backup_before_018_repair.csv"

print("=" * 80)
print("CHETAKAI - PHASE 4.4 POPULATION REPAIR")
print("=" * 80)

g = gpd.read_file(BASIN_FILE)

targets = g[
    g["ba_name"].astype(str).str.contains(
        "Kutch|Saurashtra|Inland drainage in Rajasthan",
        case=False,
        na=False
    )
].copy()

print("\nTARGET BASINS:")
print(targets[["ba_code", "ba_name"]].to_string(index=False))

if len(targets) != 2:
    raise RuntimeError(f"Expected 2 target basins, found {len(targets)}")

# Identify basin 018 by NAME, not numeric ba_code.
basin_018 = targets[
    targets["ba_name"].astype(str).str.contains(
        "Kutch|Saurashtra",
        case=False,
        na=False
    )
].copy()

if len(basin_018) != 1:
    raise RuntimeError(
        f"Could not uniquely identify CWC_BASIN_018. Found {len(basin_018)}"
    )

print("\nIDENTIFIED CWC_BASIN_018:")
print(basin_018[["ba_code", "ba_name"]].to_string(index=False))

with rasterio.open(WORLDPOP) as src:

    print("\nWORLDPOP:")
    print("CRS:", src.crs)
    print("RESOLUTION:", src.res)
    print("BOUNDS:", src.bounds)

    basin_018 = basin_018.to_crs(src.crs)

    geom = [basin_018.geometry.iloc[0]]

    print("\nPROCESSING: CWC_BASIN_018")

    out_image, out_transform = mask(
        src,
        geom,
        crop=True,
        filled=False
    )

    data = out_image[0]

    if np.ma.isMaskedArray(data):
        values = data.compressed()
    else:
        values = data[np.isfinite(data)]

    values = values[np.isfinite(values)]
    values = values[values >= 0]

    valid_pixels = len(values)

    print("VALID PIXELS:", valid_pixels)

    if valid_pixels == 0:
        raise RuntimeError(
            "WorldPop returned zero valid pixels for CWC_BASIN_018."
        )

    population_total = float(values.sum())
    population_mean = float(values.mean())
    population_min = float(values.min())
    population_max = float(values.max())

    # Geometry is in EPSG:4326, so use geodesic-ish area approximation
    # from the existing processed basin area instead of planar degrees.
    existing_df = pd.read_csv(CSV)

    existing_row = existing_df[
        existing_df["canonical_basin_id"].astype(str) == "CWC_BASIN_018"
    ]

    if len(existing_row) == 1 and pd.notna(
        existing_row.iloc[0]["basin_area_km2"]
    ):
        basin_area_km2 = float(
            existing_row.iloc[0]["basin_area_km2"]
        )
    else:
        # Fallback: project to equal-area CRS.
        basin_area_km2 = float(
            basin_018.to_crs("ESRI:6933").geometry.area.iloc[0]
            / 1_000_000
        )

    population_density = population_total / basin_area_km2

    print("\nRESULT:")
    print("Population total :", population_total)
    print("Population density:", population_density)
    print("Valid pixels     :", valid_pixels)
    print("Mean pixel       :", population_mean)
    print("Min pixel        :", population_min)
    print("Max pixel        :", population_max)
    print("Area km2         :", basin_area_km2)

# ---------------------------------------------------------
# Update CSV
# ---------------------------------------------------------

print("\n" + "=" * 80)
print("UPDATING PROCESSED POPULATION CSV")
print("=" * 80)

df = pd.read_csv(CSV)

if not os.path.exists(BACKUP):
    shutil.copy2(CSV, BACKUP)

idx = df.index[
    df["canonical_basin_id"].astype(str) == "CWC_BASIN_018"
]

if len(idx) != 1:
    raise RuntimeError(
        f"Expected exactly one CWC_BASIN_018 row, found {len(idx)}"
    )

i = idx[0]

df.loc[i, "population_total"] = population_total
df.loc[i, "population_density_per_km2"] = population_density
df.loc[i, "population_valid_pixels"] = valid_pixels
df.loc[i, "population_mean_pixel_value"] = population_mean
df.loc[i, "population_min_pixel_value"] = population_min
df.loc[i, "population_max_pixel_value"] = population_max
df.loc[i, "population_source"] = "WorldPop 2020 1km"
df.loc[i, "population_year"] = 2020

df.to_csv(CSV, index=False)

print("\nREPAIRED ROW:")
print(
    df[
        df["canonical_basin_id"].astype(str) == "CWC_BASIN_018"
    ].to_string(index=False)
)

print("\nFINAL ROW COUNT:", len(df))
print("\nBACKUP:", BACKUP)
print("UPDATED:", CSV)

print("\n" + "=" * 80)
print("PHASE 4.4 POPULATION REPAIR COMPLETE")
print("=" * 80)
