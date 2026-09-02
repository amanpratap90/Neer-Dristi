from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings("ignore")

print("=" * 70)
print("CHETAKAI V1 HYDROGRAPHY FEATURE ENGINEERING")
print("=" * 70)

ROOT = Path(__file__).resolve().parents[1]

HYDRO_DIR = ROOT / "data" / "raw" / "hydrography"
BASIN_DIR = ROOT / "data" / "raw" / "basin_boundaries"
OUTPUT_DIR = ROOT / "data" / "processed" / "hydrography"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = OUTPUT_DIR / "hydrography_basin_features.csv"

print("PROJECT ROOT :", ROOT)
print("HYDRO DIR    :", HYDRO_DIR)
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
        "river_basi",
        "River_Basin",
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
        return np.nan


def calculate_length_km(gdf):
    if gdf.empty:
        return 0.0

    try:
        projected = gdf.to_crs(6933)
        return float(projected.length.sum() / 1000.0)

    except Exception:
        return np.nan


# ---------------------------------------------------------------------
# FIND BASINS
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
    raise RuntimeError("Basin file contains no features.")

if basins.crs is None:
    raise RuntimeError("Basin layer has no CRS.")

name_col = choose_name_column(basins)

if name_col is None:

    basins["basin_name"] = [
        f"BASIN_{i + 1}"
        for i in range(len(basins))
    ]

else:

    basins["basin_name"] = (
        basins[name_col]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    bad = (
        basins["basin_name"].eq("")
        |
        basins["basin_name"].str.lower().isin(
            ["nan", "none", "null"]
        )
    )

    basins.loc[bad, "basin_name"] = [
        f"BASIN_{i + 1}"
        for i in basins.index[bad]
    ]

basins["basin_name"] = basins["basin_name"].astype(str)

basins = basins[
    basins.geometry.notna()
].copy()

basins = basins[
    ~basins.geometry.is_empty
].copy()

print("BASIN CRS         :", basins.crs)
print("BASIN NAME COLUMN :", name_col)
print("BASINS FOUND      :", len(basins))
print()

print("BASINS:")

for name in sorted(
    basins["basin_name"].unique(),
    key=lambda x: str(x)
):
    print("  -", name)

print()


# ---------------------------------------------------------------------
# FIND HYDROGRAPHY
# ---------------------------------------------------------------------

print("Searching for hydrography files...")

hydro_files = find_vector_files(HYDRO_DIR)

if not hydro_files:

    print("WARNING: No hydrography vector files found.")
    print("Creating empty feature table.")

    rows = []

    for name in basins["basin_name"].unique():

        rows.append({
            "basin_name": name,
            "basin_area_km2": 0.0,
            "river_feature_count": 0,
            "river_length_km": np.nan,
            "river_area_km2": 0.0,
            "river_area_fraction_pct": 0.0,
            "river_density_km_per_km2": np.nan,
            "waterbody_count": 0,
            "waterbody_area_km2": 0.0,
            "waterbody_fraction_pct": 0.0,
            "river_geometry_type": "missing"
        })

    pd.DataFrame(rows).to_csv(
        OUTPUT,
        index=False
    )

    print("OUTPUT:", OUTPUT)

    raise SystemExit(0)


print()
print("ALL HYDROGRAPHY FILES FOUND:")

for f in hydro_files:
    print("  -", f)

print()


# ---------------------------------------------------------------------
# LOAD HYDROGRAPHY
# ---------------------------------------------------------------------

print("=" * 70)
print("LOADING HYDROGRAPHY")
print("=" * 70)

layers = []

for file in hydro_files:

    print()
    print("Reading:", file)

    try:

        gdf = gpd.read_file(file)

        if gdf.empty:
            print("  EMPTY")
            continue

        if gdf.crs is None:
            print("  SKIPPED: CRS missing")
            continue

        gdf = gdf[
            gdf.geometry.notna()
        ].copy()

        gdf = gdf[
            ~gdf.geometry.is_empty
        ].copy()

        if gdf.empty:
            print("  EMPTY AFTER GEOMETRY CLEANING")
            continue

        print("  CRS      :", gdf.crs)
        print("  FEATURES :", len(gdf))

        geometry_types = (
            gdf.geometry.geom_type
            .value_counts()
            .to_dict()
        )

        print("  GEOMETRY TYPES:", geometry_types)

        gdf = gdf.to_crs(basins.crs)

        gdf["_source_file"] = file.name

        layers.append(gdf)

    except Exception as e:

        print("  FAILED:", e)


if not layers:

    raise RuntimeError(
        "No usable hydrography layers found."
    )


# ---------------------------------------------------------------------
# COMBINE
# ---------------------------------------------------------------------

print()
print("Combining hydrography layers...")

hydro = gpd.GeoDataFrame(
    pd.concat(
        layers,
        ignore_index=True
    ),
    crs=basins.crs
)

print("TOTAL HYDRO FEATURES:", len(hydro))
print()


# ---------------------------------------------------------------------
# GEOMETRY CLASSIFICATION
# ---------------------------------------------------------------------

hydro["_geometry_type"] = (
    hydro.geometry
    .geom_type
    .astype(str)
)

line_features = hydro[
    hydro["_geometry_type"].isin([
        "LineString",
        "MultiLineString"
    ])
].copy()

polygon_features = hydro[
    hydro["_geometry_type"].isin([
        "Polygon",
        "MultiPolygon"
    ])
].copy()

point_features = hydro[
    hydro["_geometry_type"].isin([
        "Point",
        "MultiPoint"
    ])
].copy()

print("GEOMETRY SUMMARY")
print("-" * 70)
print("LINE FEATURES   :", len(line_features))
print("POLYGON FEATURES:", len(polygon_features))
print("POINT FEATURES  :", len(point_features))
print()


# ---------------------------------------------------------------------
# INTERPRET AVAILABLE DATA
# ---------------------------------------------------------------------

if len(line_features) > 0:

    river_source_type = "line"

    river_features = line_features

    print("RIVER REPRESENTATION: LINE")

elif len(polygon_features) > 0:

    river_source_type = "polygon"

    river_features = polygon_features

    print("RIVER REPRESENTATION: POLYGON")

    print(
        "NOTE: River centerlines are unavailable."
    )

    print(
        "River length will remain unavailable."
    )

    print(
        "River polygon area will be used as a spatial proxy."
    )

else:

    river_source_type = "missing"

    river_features = polygon_features

    print(
        "WARNING: No river line/polygon features available."
    )


# ---------------------------------------------------------------------
# WATERBODY DATASET
# ---------------------------------------------------------------------

waterbody_features = gpd.GeoDataFrame(
    columns=hydro.columns,
    geometry=[],
    crs=basins.crs
)

print()
print("WATERBODY DATASET:")
print("  No independent waterbody layer detected.")

print()


# ---------------------------------------------------------------------
# BASIN-LEVEL FEATURES
# ---------------------------------------------------------------------

print("=" * 70)
print("CALCULATING BASIN-LEVEL HYDROGRAPHY FEATURES")
print("=" * 70)

results = []

for idx, basin in basins.iterrows():

    basin_name = str(
        basin["basin_name"]
    )

    print(
        f"[{idx + 1:03d}/{len(basins):03d}] "
        f"{basin_name}"
    )

    basin_geometry = basin.geometry

    basin_gdf = gpd.GeoDataFrame(
        {
            "basin_name": [basin_name]
        },
        geometry=[basin_geometry],
        crs=basins.crs
    )

    basin_area_km2 = calculate_area_km2(
        basin_gdf
    )

    # ---------------------------------------------------------------
    # RIVER FEATURES
    # ---------------------------------------------------------------

    river_count = 0
    river_length_km = np.nan
    river_area_km2 = 0.0

    try:

        if not river_features.empty:

            intersects = (
                river_features
                .geometry
                .intersects(basin_geometry)
            )

            selected = river_features[
                intersects
            ].copy()

            if not selected.empty:

                river_count = len(selected)

                if river_source_type == "line":

                    river_length_km = (
                        calculate_length_km(
                            selected
                        )
                    )

                elif river_source_type == "polygon":

                    river_area_km2 = (
                        calculate_area_km2(
                            selected
                        )
                    )

    except Exception as e:

        print(
            "  River processing failed:",
            e
        )

    # ---------------------------------------------------------------
    # WATERBODY FEATURES
    # ---------------------------------------------------------------

    waterbody_count = 0
    waterbody_area_km2 = 0.0

    try:

        if not waterbody_features.empty:

            intersects = (
                waterbody_features
                .geometry
                .intersects(basin_geometry)
            )

            selected_water = (
                waterbody_features[
                    intersects
                ].copy()
            )

            if not selected_water.empty:

                waterbody_count = len(
                    selected_water
                )

                waterbody_area_km2 = (
                    calculate_area_km2(
                        selected_water
                    )
                )

    except Exception as e:

        print(
            "  Waterbody processing failed:",
            e
        )

    # ---------------------------------------------------------------
    # RIVER AREA FRACTION
    # ---------------------------------------------------------------

    if (
        basin_area_km2 is not None
        and np.isfinite(basin_area_km2)
        and basin_area_km2 > 0
    ):

        river_area_fraction_pct = (
            river_area_km2
            / basin_area_km2
            * 100.0
        )

        waterbody_fraction_pct = (
            waterbody_area_km2
            / basin_area_km2
            * 100.0
        )

    else:

        river_area_fraction_pct = 0.0
        waterbody_fraction_pct = 0.0

    # ---------------------------------------------------------------
    # RIVER DENSITY
    # ---------------------------------------------------------------

    if (
        river_source_type == "line"
        and river_length_km is not None
        and np.isfinite(river_length_km)
        and basin_area_km2 > 0
    ):

        river_density = (
            river_length_km
            / basin_area_km2
        )

    else:

        river_density = np.nan

    results.append({

        "basin_name":
            basin_name,

        "basin_area_km2":
            basin_area_km2,

        "river_feature_count":
            river_count,

        "river_length_km":
            river_length_km,

        "river_area_km2":
            river_area_km2,

        "river_area_fraction_pct":
            river_area_fraction_pct,

        "river_density_km_per_km2":
            river_density,

        "waterbody_count":
            waterbody_count,

        "waterbody_area_km2":
            waterbody_area_km2,

        "waterbody_fraction_pct":
            waterbody_fraction_pct,

        "river_geometry_type":
            river_source_type
    })


# ---------------------------------------------------------------------
# DATAFRAME
# ---------------------------------------------------------------------

df = pd.DataFrame(results)

numeric_columns = [
    "basin_area_km2",
    "river_feature_count",
    "river_length_km",
    "river_area_km2",
    "river_area_fraction_pct",
    "river_density_km_per_km2",
    "waterbody_count",
    "waterbody_area_km2",
    "waterbody_fraction_pct"
]

for col in numeric_columns:

    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )


# ---------------------------------------------------------------------
# SANITY CLEANING
# ---------------------------------------------------------------------

for col in [
    "basin_area_km2",
    "river_feature_count",
    "river_area_km2",
    "river_area_fraction_pct",
    "waterbody_count",
    "waterbody_area_km2",
    "waterbody_fraction_pct"
]:

    df[col] = df[col].fillna(0)


df = df.replace(
    [np.inf, -np.inf],
    np.nan
)


# ---------------------------------------------------------------------
# SORT
# ---------------------------------------------------------------------

df = df.sort_values(
    "basin_name",
    key=lambda s: s.astype(str)
).reset_index(drop=True)


# ---------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------

print()
print("=" * 70)
print("HYDROGRAPHY VALIDATION")
print("=" * 70)

print("ROWS :", len(df))
print("COLUMNS :", len(df.columns))

print()
print("RIVER FEATURES :", int(
    df["river_feature_count"].sum()
))

print(
    "RIVER AREA KM2 :",
    round(
        df["river_area_km2"].sum(),
        3
    )
)

if df["river_length_km"].notna().any():

    print(
        "RIVER LENGTH KM:",
        round(
            df["river_length_km"].sum(),
            3
        )
    )

else:

    print(
        "RIVER LENGTH KM: UNAVAILABLE "
        "(polygon source)"
    )

print(
    "WATERBODIES :",
    int(
        df["waterbody_count"].sum()
    )
)

print(
    "WATER AREA KM2:",
    round(
        df["waterbody_area_km2"].sum(),
        3
    )
)

print()
print("NULL COUNTS:")

for col in df.columns:

    print(
        f"  {col}: "
        f"{df[col].isna().sum()}"
    )


# ---------------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------------

df.to_csv(
    OUTPUT,
    index=False
)


# ---------------------------------------------------------------------
# FINAL OUTPUT
# ---------------------------------------------------------------------

print()
print("=" * 70)
print("HYDROGRAPHY FEATURE ENGINEERING COMPLETE")
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
print("FINAL TABLE:")
print(
    df.to_string(index=False)
)

print()
print("=" * 70)
print("SUCCESS")
print("=" * 70)