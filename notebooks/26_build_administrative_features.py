from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings("ignore")

print("=" * 70)
print("CHETAKAI V1 ADMINISTRATIVE FEATURE ENGINEERING")
print("=" * 70)

ROOT = Path(__file__).resolve().parents[1]

BASIN_FILE = (
    ROOT
    / "data"
    / "raw"
    / "basin_boundaries"
    / "cwc_basins.geojson"
)

ADM1_FILE = (
    ROOT
    / "data"
    / "raw"
    / "administrative"
    / "IND_ADM1.geojson"
)

ADM2_FILE = (
    ROOT
    / "data"
    / "raw"
    / "administrative"
    / "ADM2"
    / "IND_ADM2.geojson"
)

OUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "administrative"
)

OUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT = (
    OUT_DIR
    / "administrative_basin_features.csv"
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


def clean_geometry(gdf):

    gdf = gdf[
        gdf.geometry.notna()
        & ~gdf.geometry.is_empty
    ].copy()

    return gdf


print()
print("CHECKING INPUTS...")

for file in [
    BASIN_FILE,
    ADM1_FILE,
    ADM2_FILE
]:

    if not file.exists():

        raise RuntimeError(
            f"Required file not found: {file}"
        )

    print("FOUND:", file)


print()
print("LOADING BASINS...")

basins = gpd.read_file(
    BASIN_FILE
)

if basins.empty:
    raise RuntimeError(
        "Basin file is empty."
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

basins = clean_geometry(
    basins
)

print("Basins    :", len(basins))
print("Basin CRS :", basins.crs)


print()
print("LOADING ADM1...")

adm1 = gpd.read_file(
    ADM1_FILE
)

if adm1.empty:

    raise RuntimeError(
        "ADM1 file is empty."
    )

if adm1.crs is None:

    raise RuntimeError(
        "ADM1 CRS is missing."
    )

adm1 = clean_geometry(
    adm1
)

print(
    "ADM1 features:",
    len(adm1)
)

print(
    "ADM1 CRS:",
    adm1.crs
)


print()
print("LOADING ADM2...")

adm2 = gpd.read_file(
    ADM2_FILE
)

if adm2.empty:

    raise RuntimeError(
        "ADM2 file is empty."
    )

if adm2.crs is None:

    raise RuntimeError(
        "ADM2 CRS is missing."
    )

adm2 = clean_geometry(
    adm2
)

print(
    "ADM2 features:",
    len(adm2)
)

print(
    "ADM2 CRS:",
    adm2.crs
)


print()
print("STANDARDIZING CRS...")

target_crs = basins.crs

adm1 = adm1.to_crs(
    target_crs
)

adm2 = adm2.to_crs(
    target_crs
)

print(
    "Target CRS:",
    target_crs
)


print()
print("BUILDING SPATIAL INDEXES...")

adm1_sindex = adm1.sindex
adm2_sindex = adm2.sindex

print("Spatial indexes ready.")


print()
print("=" * 70)
print("PROCESSING BASINS")
print("=" * 70)

results = []

for i, basin in basins.iterrows():

    basin_name = str(
        basin["basin_name"]
    )

    geometry = basin.geometry

    print()
    print(
        f"[{i + 1:03d}/{len(basins):03d}] "
        f"{basin_name}"
    )

    adm1_count = 0
    adm2_count = 0

    adm1_area_km2 = 0.0
    adm2_area_km2 = 0.0

    try:

        candidate_ids = list(
            adm1_sindex.intersection(
                geometry.bounds
            )
        )

        candidates = adm1.iloc[
            candidate_ids
        ]

        intersects = candidates[
            candidates.geometry.intersects(
                geometry
            )
        ]

        adm1_count = len(
            intersects
        )

        if adm1_count > 0:

            clipped = gpd.clip(
                intersects,
                gpd.GeoDataFrame(
                    geometry=[geometry],
                    crs=target_crs
                )
            )

            if not clipped.empty:

                clipped_area = (
                    clipped
                    .to_crs(6933)
                    .geometry
                    .area
                    .sum()
                )

                adm1_area_km2 = (
                    float(clipped_area)
                    / 1_000_000
                )

    except Exception as e:

        print(
            "  ADM1 failed:",
            str(e).splitlines()[0]
        )


    try:

        candidate_ids = list(
            adm2_sindex.intersection(
                geometry.bounds
            )
        )

        candidates = adm2.iloc[
            candidate_ids
        ]

        intersects = candidates[
            candidates.geometry.intersects(
                geometry
            )
        ]

        adm2_count = len(
            intersects
        )

        if adm2_count > 0:

            clipped = gpd.clip(
                intersects,
                gpd.GeoDataFrame(
                    geometry=[geometry],
                    crs=target_crs
                )
            )

            if not clipped.empty:

                clipped_area = (
                    clipped
                    .to_crs(6933)
                    .geometry
                    .area
                    .sum()
                )

                adm2_area_km2 = (
                    float(clipped_area)
                    / 1_000_000
                )

    except Exception as e:

        print(
            "  ADM2 failed:",
            str(e).splitlines()[0]
        )


    results.append({

        "basin_name":
            basin_name,

        "adm1_feature_count":
            adm1_count,

        "adm2_feature_count":
            adm2_count,

        "adm1_intersected_area_km2":
            adm1_area_km2,

        "adm2_intersected_area_km2":
            adm2_area_km2,

        "administrative_feature_count":
            adm1_count + adm2_count,

        "administrative_data_available":
            int(
                adm1_count > 0
                or adm2_count > 0
            ),

        "adm1_source":
            "IND_ADM1",

        "adm2_source":
            "IND_ADM2"

    })


    print(
        "  ADM1 features :",
        adm1_count
    )

    print(
        "  ADM2 features :",
        adm2_count
    )

    print(
        "  Total features:",
        adm1_count + adm2_count
    )


df = pd.DataFrame(
    results
)


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
print("ADMINISTRATIVE STATISTICS")

print(
    "ADM1 min :",
    df["adm1_feature_count"].min()
)

print(
    "ADM1 max :",
    df["adm1_feature_count"].max()
)

print(
    "ADM2 min :",
    df["adm2_feature_count"].min()
)

print(
    "ADM2 max :",
    df["adm2_feature_count"].max()
)

print(
    "Basins with ADM1:",
    (
        df["adm1_feature_count"] > 0
    ).sum()
)

print(
    "Basins with ADM2:",
    (
        df["adm2_feature_count"] > 0
    ).sum()
)


print()
print("SAVING OUTPUT...")

df.to_csv(
    OUTPUT,
    index=False
)

print(
    "OUTPUT:",
    OUTPUT
)

print(
    "SHAPE :",
    df.shape
)

print()
print("=" * 70)
print("ADMINISTRATIVE FEATURE ENGINEERING COMPLETE")
print("=" * 70)