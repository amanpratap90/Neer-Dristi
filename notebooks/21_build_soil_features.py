from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from rasterio.mask import mask
import warnings

warnings.filterwarnings("ignore")

print("=" * 70)
print("CHETAKAI V1 SOIL FEATURE ENGINEERING")
print("=" * 70)

ROOT = Path(__file__).resolve().parents[1]

SOIL_DIR = ROOT / "data" / "raw" / "soil"
BASIN_DIR = ROOT / "data" / "raw" / "basin_boundaries"
OUTPUT_DIR = ROOT / "data" / "processed" / "soil"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = OUTPUT_DIR / "soil_basin_features.csv"

print("PROJECT ROOT :", ROOT)
print("SOIL DIR     :", SOIL_DIR)
print("BASIN DIR    :", BASIN_DIR)
print("OUTPUT       :", OUTPUT)
print()


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def find_vector_files(folder):
    files = []

    for ext in ["*.geojson", "*.gpkg", "*.shp", "*.json"]:
        files.extend(folder.rglob(ext))

    return sorted(set(files))


def choose_basin_file(files):

    priority = [
        "cwc_basins.geojson",
        "basins.geojson",
        "basin_boundaries.geojson"
    ]

    for name in priority:
        for f in files:
            if f.name.lower() == name.lower():
                return f

    return files[0] if files else None


def choose_name_column(gdf):

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
            values = gdf[col].dropna()

            if len(values) > 0:
                return col

    return None


def calculate_area_km2(gdf):

    if gdf.empty:
        return 0.0

    try:
        projected = gdf.to_crs(6933)
        return float(projected.area.sum() / 1_000_000.0)

    except Exception:
        return 0.0


def find_soil_rasters():

    rasters = []

    for ext in ["*.tif", "*.tiff", "*.vrt"]:

        rasters.extend(SOIL_DIR.rglob(ext))

    return sorted(set(rasters))


def identify_soil_property(path):

    name = path.name.lower()

    properties = [
        "sand",
        "clay",
        "silt",
        "soc",
        "bdod",
        "phh2o",
        "cec",
        "nitrogen",
        "cfvo"
    ]

    for prop in properties:

        if prop in name:
            return prop

    return None


def normalize_property_name(path):

    name = path.name.lower()

    property_map = {
        "sand": "sand",
        "clay": "clay",
        "silt": "silt",
        "soc": "soc",
        "bdod": "bdod",
        "phh2o": "phh2o",
        "cec": "cec",
        "nitrogen": "nitrogen",
        "cfvo": "cfvo"
    }

    for key, value in property_map.items():

        if key in name:
            return value

    return None


def zonal_mean(raster_path, geometry):

    try:

        with rasterio.open(raster_path) as src:

            geom = geometry

            if src.crs != basin_crs:
                temp = gpd.GeoDataFrame(
                    {"id": [1]},
                    geometry=[geometry],
                    crs=basin_crs
                )

                temp = temp.to_crs(src.crs)

                geom = temp.geometry.iloc[0]

            out_image, out_transform = mask(
                src,
                [geom],
                crop=True,
                filled=False
            )

            data = out_image[0]

            if np.ma.isMaskedArray(data):
                values = data.compressed()
            else:
                values = data.flatten()

            values = values[np.isfinite(values)]

            if len(values) == 0:
                return np.nan, np.nan, 0

            mean_value = float(np.mean(values))
            median_value = float(np.median(values))

            return mean_value, median_value, len(values)

    except Exception as e:

        return np.nan, np.nan, 0


# ---------------------------------------------------------------------
# BASINS
# ---------------------------------------------------------------------

print("Searching for basin boundaries...")

basin_files = find_vector_files(BASIN_DIR)

if not basin_files:
    raise RuntimeError("No basin boundary files found.")

print("BASIN FILES FOUND:")

for f in basin_files:
    print("  -", f)

basin_file = choose_basin_file(basin_files)

print()
print("Using basin file:")
print(" ", basin_file)
print()

basins = gpd.read_file(basin_file)

if basins.empty:
    raise RuntimeError("Basin file is empty.")

if basins.crs is None:
    raise RuntimeError("Basin CRS is missing.")

basin_crs = basins.crs

name_col = choose_name_column(basins)

if name_col:

    basins["basin_name"] = (
        basins[name_col]
        .fillna("")
        .astype(str)
        .str.strip()
    )

else:

    basins["basin_name"] = [
        f"BASIN_{i + 1}"
        for i in range(len(basins))
    ]

bad = (
    basins["basin_name"].eq("") |
    basins["basin_name"].str.lower().isin(
        ["nan", "none", "null"]
    )
)

basins.loc[bad, "basin_name"] = [
    f"BASIN_{i + 1}"
    for i in basins.index[bad]
]

basins = basins[
    basins.geometry.notna()
].copy()

basins = basins[
    ~basins.geometry.is_empty
].copy()

print("BASIN CRS         :", basin_crs)
print("BASIN NAME COLUMN :", name_col)
print("BASINS FOUND      :", len(basins))
print()

print("BASINS:")

for name in basins["basin_name"]:
    print("  -", name)

print()


# ---------------------------------------------------------------------
# FIND SOIL RASTERS
# ---------------------------------------------------------------------

print("Searching SoilGrids rasters...")

soil_files = find_soil_rasters()

if not soil_files:

    raise RuntimeError(
        "No SoilGrids raster/VRT files found in data/raw/soil"
    )

print()
print("SOIL FILES FOUND:", len(soil_files))

for f in soil_files:

    prop = identify_soil_property(f)

    print(
        "  -",
        f.name,
        "| PROPERTY:",
        prop
    )

print()


# ---------------------------------------------------------------------
# SELECT BEST RASTER PER PROPERTY
# ---------------------------------------------------------------------

soil_rasters = {}

for f in soil_files:

    prop = normalize_property_name(f)

    if prop is None:
        continue

    # Prefer 0-5cm mean layer where available
    name = f.name.lower()

    score = 0

    if "0-5cm" in name:
        score += 100

    if "mean" in name:
        score += 50

    current = soil_rasters.get(prop)

    if current is None:

        soil_rasters[prop] = (score, f)

    else:

        if score > current[0]:
            soil_rasters[prop] = (score, f)


soil_rasters = {
    prop: item[1]
    for prop, item in soil_rasters.items()
}

print("SELECTED SOIL RASTERS:")
print()

for prop, path in sorted(soil_rasters.items()):

    print(
        f"  {prop:10s} -> {path.name}"
    )

print()


# ---------------------------------------------------------------------
# CHECK REQUIRED PROPERTIES
# ---------------------------------------------------------------------

required_properties = [
    "sand",
    "clay",
    "silt",
    "soc",
    "bdod",
    "phh2o",
    "cec"
]

available_required = [
    p for p in required_properties
    if p in soil_rasters
]

missing_required = [
    p for p in required_properties
    if p not in soil_rasters
]

print("REQUIRED PROPERTIES :", len(required_properties))
print("AVAILABLE            :", len(available_required))

if missing_required:

    print()
    print("MISSING PROPERTIES:")

    for prop in missing_required:
        print("  -", prop)

else:

    print("ALL REQUIRED PROPERTIES AVAILABLE.")

print()


# ---------------------------------------------------------------------
# RASTER CRS / METADATA CHECK
# ---------------------------------------------------------------------

print("=" * 70)
print("SOIL RASTER VALIDATION")
print("=" * 70)

for prop, path in sorted(soil_rasters.items()):

    try:

        with rasterio.open(path) as src:

            print()
            print("PROPERTY :", prop)
            print("FILE     :", path.name)
            print("CRS      :", src.crs)
            print("WIDTH    :", src.width)
            print("HEIGHT   :", src.height)
            print("RES      :", src.res)
            print("NODATA   :", src.nodata)

    except Exception as e:

        print(
            "FAILED:",
            prop,
            e
        )

print()


# ---------------------------------------------------------------------
# BASIN-LEVEL SOIL FEATURES
# ---------------------------------------------------------------------

print("=" * 70)
print("CALCULATING BASIN-LEVEL SOIL FEATURES")
print("=" * 70)

results = []

for idx, basin in basins.iterrows():

    basin_name = str(
        basin["basin_name"]
    )

    geometry = basin.geometry

    print(
        f"[{idx + 1:03d}/{len(basins):03d}] {basin_name}"
    )

    row = {
        "basin_name": basin_name
    }

    # ---------------------------------------------------------------
    # BASIN AREA
    # ---------------------------------------------------------------

    basin_gdf = gpd.GeoDataFrame(
        {"basin_name": [basin_name]},
        geometry=[geometry],
        crs=basin_crs
    )

    row["basin_area_km2"] = calculate_area_km2(
        basin_gdf
    )

    # ---------------------------------------------------------------
    # SOIL PROPERTIES
    # ---------------------------------------------------------------

    property_values = {}

    for prop in required_properties:

        if prop not in soil_rasters:

            row[f"{prop}_mean"] = np.nan
            row[f"{prop}_median"] = np.nan

            continue

        raster_path = soil_rasters[prop]

        mean_value, median_value, valid_pixels = (
            zonal_mean(
                raster_path,
                geometry
            )
        )

        row[f"{prop}_mean"] = mean_value
        row[f"{prop}_median"] = median_value

        property_values[prop] = mean_value

    # ---------------------------------------------------------------
    # OPTIONAL PROPERTIES
    # ---------------------------------------------------------------

    for prop in ["nitrogen", "cfvo"]:

        if prop in soil_rasters:

            mean_value, median_value, valid_pixels = (
                zonal_mean(
                    soil_rasters[prop],
                    geometry
                )
            )

            row[f"{prop}_mean"] = mean_value
            row[f"{prop}_median"] = median_value

    # ---------------------------------------------------------------
    # DATA AVAILABILITY
    # ---------------------------------------------------------------

    available_count = 0

    for prop in required_properties:

        value = row.get(
            f"{prop}_mean",
            np.nan
        )

        if pd.notna(value):
            available_count += 1

    row["soil_property_availability_pct"] = (
        available_count /
        len(required_properties)
        * 100.0
    )

    # ---------------------------------------------------------------
    # SOIL TEXTURE PROXY
    # ---------------------------------------------------------------

    sand = row.get("sand_mean", np.nan)
    clay = row.get("clay_mean", np.nan)
    silt = row.get("silt_mean", np.nan)

    if pd.notna(sand) and pd.notna(clay) and pd.notna(silt):

        total = sand + clay + silt

        if total > 0:

            sand_pct = sand / total * 100
            clay_pct = clay / total * 100
            silt_pct = silt / total * 100

            row["sand_fraction_pct"] = sand_pct
            row["clay_fraction_pct"] = clay_pct
            row["silt_fraction_pct"] = silt_pct

            if clay_pct >= 40:

                texture = "clay"

            elif clay_pct >= 27 and silt_pct >= 40:

                texture = "silty_clay"

            elif sand_pct >= 70:

                texture = "sandy"

            elif sand_pct >= 50:

                texture = "sandy_loam"

            elif silt_pct >= 50:

                texture = "silty"

            else:

                texture = "loam"

            row["soil_texture_proxy"] = texture

        else:

            row["sand_fraction_pct"] = np.nan
            row["clay_fraction_pct"] = np.nan
            row["silt_fraction_pct"] = np.nan
            row["soil_texture_proxy"] = "unknown"

    else:

        row["sand_fraction_pct"] = np.nan
        row["clay_fraction_pct"] = np.nan
        row["silt_fraction_pct"] = np.nan
        row["soil_texture_proxy"] = "unknown"

    # ---------------------------------------------------------------
    # WATER RETENTION / RUNOFF PROXY
    # ---------------------------------------------------------------

    if pd.notna(clay) and pd.notna(sand):

        row["soil_runoff_proxy"] = (
            (clay * 0.7) -
            (sand * 0.3)
        )

    else:

        row["soil_runoff_proxy"] = np.nan

    # ---------------------------------------------------------------
    # SOIL ORGANIC CARBON AVAILABILITY
    # ---------------------------------------------------------------

    soc = row.get(
        "soc_mean",
        np.nan
    )

    if pd.notna(soc):

        row["high_soc_proxy"] = (
            1 if soc > 20 else 0
        )

    else:

        row["high_soc_proxy"] = np.nan

    results.append(row)


# ---------------------------------------------------------------------
# DATAFRAME
# ---------------------------------------------------------------------

df = pd.DataFrame(results)


# ---------------------------------------------------------------------
# NUMERIC CLEANING
# ---------------------------------------------------------------------

numeric_columns = [

    "basin_area_km2",

    "sand_mean",
    "sand_median",

    "clay_mean",
    "clay_median",

    "silt_mean",
    "silt_median",

    "soc_mean",
    "soc_median",

    "bdod_mean",
    "bdod_median",

    "phh2o_mean",
    "phh2o_median",

    "cec_mean",
    "cec_median",

    "nitrogen_mean",
    "nitrogen_median",

    "cfvo_mean",
    "cfvo_median",

    "soil_property_availability_pct",

    "sand_fraction_pct",
    "clay_fraction_pct",
    "silt_fraction_pct",

    "soil_runoff_proxy",

    "high_soc_proxy"
]

for col in numeric_columns:

    if col in df.columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )


# ---------------------------------------------------------------------
# SORT
# ---------------------------------------------------------------------

df = df.sort_values(
    "basin_name",
    key=lambda s: s.astype(str)
)


# ---------------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------------

df.to_csv(
    OUTPUT,
    index=False
)


# ---------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------

print()

print("=" * 70)
print("SOIL FEATURE VALIDATION")
print("=" * 70)

print()

print("ROWS    :", len(df))
print("COLUMNS :", len(df.columns))

print()

print("NULL COUNTS:")

for col in df.columns:

    nulls = int(
        df[col].isna().sum()
    )

    print(
        f"  {col}: {nulls}"
    )

print()

print("SOIL PROPERTY AVAILABILITY:")

if "soil_property_availability_pct" in df.columns:

    print(
        df[
            [
                "basin_name",
                "soil_property_availability_pct"
            ]
        ].to_string(index=False)
    )

print()

print("FINAL TABLE:")

print(
    df.to_string(
        index=False
    )
)

print()

print("=" * 70)
print("SOIL FEATURE ENGINEERING COMPLETE")
print("=" * 70)

print()

print("OUTPUT:")
print(OUTPUT)

print()

print("FINAL SHAPE:")
print(df.shape)

print()

print("COLUMNS:")

for col in df.columns:

    print("  -", col)

print()

print("=" * 70)
print("SUCCESS")
print("=" * 70)