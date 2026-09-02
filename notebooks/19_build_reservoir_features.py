from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import zipfile
import tempfile
import shutil
import warnings

warnings.filterwarnings("ignore")

print("=" * 70)
print("CHETAKAI V1 RESERVOIR FEATURE ENGINEERING")
print("=" * 70)

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw" / "reservoirs"
BASIN_DIR = ROOT / "data" / "raw" / "basin_boundaries"
OUT_DIR = ROOT / "data" / "processed" / "reservoirs"

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = OUT_DIR / "reservoir_basin_features.csv"

print("PROJECT ROOT :", ROOT)
print("RESERVOIR DIR:", RAW_DIR)
print("BASIN DIR    :", BASIN_DIR)
print("OUTPUT       :", OUTPUT)
print()


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def find_vector_files(folder):
    extensions = [
        "*.geojson",
        "*.gpkg",
        "*.shp",
        "*.json",
        "*.kml",
        "*.KML"
    ]

    files = []

    for ext in extensions:
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


def choose_basin_name_column(gdf):

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

    if gdf.empty:
        return gdf

    gdf = gdf[gdf.geometry.notna()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    return gdf


def calculate_area_km2(gdf):

    if gdf.empty:
        return 0.0

    try:
        projected = gdf.to_crs(6933)
        return float(projected.area.sum() / 1_000_000.0)
    except Exception:
        return 0.0


def load_kml(path):

    print("Loading KML...")
    print("PATH:", path)

    try:
        gdf = gpd.read_file(path, driver="KML")
        return gdf

    except Exception as e:

        print("Standard KML loading failed:")
        print(" ", e)

        print()
        print("Trying pyogrio engine...")

        try:
            gdf = gpd.read_file(
                path,
                driver="KML",
                engine="pyogrio"
            )
            return gdf

        except Exception as e2:

            print("Pyogrio KML loading failed:")
            print(" ", e2)

            raise RuntimeError(
                "Unable to read reservoir.kml. "
                "Your GDAL/Fiona installation may not support KML."
            )


def extract_hydrolakes(zip_path):

    temp_dir = Path(
        tempfile.mkdtemp(prefix="chetakai_hydrolakes_")
    )

    print("Extracting HydroLAKES ZIP...")
    print("ZIP:", zip_path)
    print("TEMP:", temp_dir)

    try:

        with zipfile.ZipFile(zip_path, "r") as z:

            members = z.namelist()

            shapefiles = [
                m for m in members
                if m.lower().endswith(".shp")
            ]

            if not shapefiles:
                raise RuntimeError(
                    "No shapefile found inside HydroLAKES ZIP."
                )

            z.extractall(temp_dir)

        shp = temp_dir / shapefiles[0]

        return shp, temp_dir

    except Exception:

        shutil.rmtree(temp_dir, ignore_errors=True)

        raise


# ---------------------------------------------------------------------
# FIND BASINS
# ---------------------------------------------------------------------

print("Searching for basin boundaries...")

basin_files = find_vector_files(BASIN_DIR)

if not basin_files:
    raise RuntimeError(
        "No basin boundary files found."
    )

print("BASIN FILES FOUND:")

for f in basin_files:
    print(" -", f)

basin_file = choose_basin_file(basin_files)

print()
print("Using basin file:")
print(" ", basin_file)
print()

basins = gpd.read_file(basin_file)

if basins.empty:
    raise RuntimeError(
        "Basin boundary file contains no features."
    )

if basins.crs is None:
    raise RuntimeError(
        "Basin layer has no CRS."
    )

name_col = choose_basin_name_column(basins)

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

    replacement = [
        f"BASIN_{i + 1}"
        for i in basins.index[bad]
    ]

    basins.loc[bad, "basin_name"] = replacement

basins = clean_geometry(basins)

print("BASIN CRS         :", basins.crs)
print("BASIN NAME COLUMN :", name_col)
print("BASINS FOUND      :", len(basins))
print()

print("BASINS:")

for name in sorted(
    basins["basin_name"].astype(str).unique()
):
    print(" -", name)

print()


# ---------------------------------------------------------------------
# FIND RESERVOIR SOURCES
# ---------------------------------------------------------------------

print("Searching reservoir datasets...")
print()

cwc_kml = RAW_DIR / "cwc" / "reservoir.kml"
hydrolakes_zip = RAW_DIR / "HydroLAKES_points_v10_shp.zip"

print("AVAILABLE RESERVOIR SOURCES:")
print()

if cwc_kml.exists():
    print("CWC KML       :", cwc_kml)

if hydrolakes_zip.exists():
    print("HydroLAKES ZIP:", hydrolakes_zip)

if not cwc_kml.exists() and not hydrolakes_zip.exists():
    raise RuntimeError(
        "No usable reservoir source found."
    )

print()


# ---------------------------------------------------------------------
# LOAD PRIMARY SOURCE: CWC
# ---------------------------------------------------------------------

reservoirs = None
reservoir_source = None
temp_hydrolakes = None

if cwc_kml.exists():

    print("=" * 70)
    print("PRIMARY RESERVOIR SOURCE: CWC")
    print("=" * 70)

    try:

        cwc = load_kml(cwc_kml)

        print()
        print("CWC CRS      :", cwc.crs)
        print("CWC FEATURES :", len(cwc))

        if not cwc.empty:

            cwc = clean_geometry(cwc)

            print(
                "GEOMETRY TYPES:",
                cwc.geometry.geom_type.value_counts().to_dict()
            )

            if cwc.crs is None:
                raise RuntimeError(
                    "CWC KML has no CRS."
                )

            cwc = cwc.to_crs(basins.crs)

            reservoirs = cwc
            reservoir_source = "CWC"

            print()
            print("CWC reservoir dataset accepted.")

        else:

            print("CWC dataset is empty.")

    except Exception as e:

        print()
        print("CWC loading failed:")
        print(e)

        reservoirs = None


# ---------------------------------------------------------------------
# FALLBACK: HYDROLAKES
# ---------------------------------------------------------------------

if reservoirs is None and hydrolakes_zip.exists():

    print()
    print("=" * 70)
    print("FALLBACK RESERVOIR SOURCE: HYDROLAKES")
    print("=" * 70)

    try:

        shp, temp_hydrolakes = extract_hydrolakes(
            hydrolakes_zip
        )

        lakes = gpd.read_file(shp)

        print()
        print("HYDROLAKES CRS      :", lakes.crs)
        print("HYDROLAKES FEATURES :", len(lakes))

        if lakes.empty:
            raise RuntimeError(
                "HydroLAKES dataset is empty."
            )

        lakes = clean_geometry(lakes)

        if lakes.crs is None:
            raise RuntimeError(
                "HydroLAKES has no CRS."
            )

        lakes = lakes.to_crs(basins.crs)

        reservoirs = lakes
        reservoir_source = "HydroLAKES"

        print()
        print("HydroLAKES fallback accepted.")

    except Exception as e:

        if temp_hydrolakes:
            shutil.rmtree(
                temp_hydrolakes,
                ignore_errors=True
            )

        raise RuntimeError(
            f"HydroLAKES loading failed: {e}"
        )


if reservoirs is None:

    raise RuntimeError(
        "No usable reservoir dataset could be loaded."
    )


# ---------------------------------------------------------------------
# GEOMETRY CLASSIFICATION
# ---------------------------------------------------------------------

print()
print("=" * 70)
print("RESERVOIR GEOMETRY ANALYSIS")
print("=" * 70)

reservoirs["_geometry_type"] = (
    reservoirs.geometry.geom_type.astype(str)
)

point_mask = reservoirs["_geometry_type"].isin([
    "Point",
    "MultiPoint"
])

line_mask = reservoirs["_geometry_type"].isin([
    "LineString",
    "MultiLineString"
])

polygon_mask = reservoirs["_geometry_type"].isin([
    "Polygon",
    "MultiPolygon"
])

print(
    "POINT FEATURES  :",
    int(point_mask.sum())
)

print(
    "LINE FEATURES   :",
    int(line_mask.sum())
)

print(
    "POLYGON FEATURES:",
    int(polygon_mask.sum())
)

print()


# ---------------------------------------------------------------------
# RESERVOIR ATTRIBUTE INSPECTION
# ---------------------------------------------------------------------

print("ATTRIBUTE COLUMNS:")

for col in reservoirs.columns:

    if col not in ["geometry", "_geometry_type"]:

        print(" -", col)

print()


# ---------------------------------------------------------------------
# BASIN FEATURE ENGINEERING
# ---------------------------------------------------------------------

print("=" * 70)
print("CALCULATING BASIN-LEVEL RESERVOIR FEATURES")
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

    basin_gdf = gpd.GeoDataFrame(
        {
            "basin_name": [basin_name]
        },
        geometry=[basin.geometry],
        crs=basins.crs
    )

    basin_area_km2 = calculate_area_km2(
        basin_gdf
    )

    reservoir_count = 0
    reservoir_area_km2 = 0.0

    point_count = 0
    polygon_count = 0

    # ---------------------------------------------------------------
    # SPATIAL JOIN
    # ---------------------------------------------------------------

    try:

        joined = gpd.sjoin(
            reservoirs,
            basin_gdf,
            predicate="intersects",
            how="inner"
        )

    except Exception as e:

        print(
            "  Spatial join failed:",
            e
        )

        joined = gpd.GeoDataFrame()

    if not joined.empty:

        unique_indices = joined.index.unique()

        selected = reservoirs.loc[
            unique_indices
        ].copy()

        reservoir_count = len(selected)

        selected_types = (
            selected.geometry.geom_type
        )

        point_count = int(
            selected_types.isin([
                "Point",
                "MultiPoint"
            ]).sum()
        )

        polygon_count = int(
            selected_types.isin([
                "Polygon",
                "MultiPolygon"
            ]).sum()
        )

        # -----------------------------------------------------------
        # POLYGON AREA
        # -----------------------------------------------------------

        polygon_selected = selected[
            selected.geometry.geom_type.isin([
                "Polygon",
                "MultiPolygon"
            ])
        ].copy()

        if not polygon_selected.empty:

            try:

                clipped = gpd.clip(
                    polygon_selected,
                    basin_gdf
                )

                reservoir_area_km2 = (
                    calculate_area_km2(
                        clipped
                    )
                )

            except Exception:

                reservoir_area_km2 = (
                    calculate_area_km2(
                        polygon_selected
                    )
                )

    # ---------------------------------------------------------------
    # DENSITY
    # ---------------------------------------------------------------

    if basin_area_km2 > 0:

        reservoir_density = (
            reservoir_count
            / basin_area_km2
            * 1000.0
        )

        reservoir_area_fraction = (
            reservoir_area_km2
            / basin_area_km2
            * 100.0
        )

    else:

        reservoir_density = 0.0
        reservoir_area_fraction = 0.0

    results.append({

        "basin_name": basin_name,

        "basin_area_km2":
            basin_area_km2,

        "reservoir_count":
            reservoir_count,

        "reservoir_point_count":
            point_count,

        "reservoir_polygon_count":
            polygon_count,

        "reservoir_area_km2":
            reservoir_area_km2,

        "reservoir_area_fraction_pct":
            reservoir_area_fraction,

        "reservoir_density_per_1000km2":
            reservoir_density,

        "reservoir_source":
            reservoir_source,

        "reservoir_geometry_type":
            (
                "polygon"
                if polygon_count > 0
                else
                "point"
                if point_count > 0
                else
                "other"
            )
    })


# ---------------------------------------------------------------------
# CREATE DATAFRAME
# ---------------------------------------------------------------------

df = pd.DataFrame(results)

numeric_columns = [
    "basin_area_km2",
    "reservoir_count",
    "reservoir_point_count",
    "reservoir_polygon_count",
    "reservoir_area_km2",
    "reservoir_area_fraction_pct",
    "reservoir_density_per_1000km2"
]

for col in numeric_columns:

    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )

df[numeric_columns] = (
    df[numeric_columns]
    .fillna(0)
)


# ---------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------

print()
print("=" * 70)
print("RESERVOIR VALIDATION")
print("=" * 70)

print(
    "SOURCE              :",
    reservoir_source
)

print(
    "BASIN ROWS          :",
    len(df)
)

print(
    "TOTAL RESERVOIRS    :",
    int(df["reservoir_count"].sum())
)

print(
    "TOTAL POINT FEATURES:",
    int(df["reservoir_point_count"].sum())
)

print(
    "TOTAL POLYGONS      :",
    int(df["reservoir_polygon_count"].sum())
)

print(
    "TOTAL AREA KM2      :",
    round(
        float(df["reservoir_area_km2"].sum()),
        3
    )
)

print()

print("NULL COUNTS:")

for col in df.columns:

    print(
        f"  {col}:",
        int(df[col].isna().sum())
    )


# ---------------------------------------------------------------------
# HARD FAILURE CHECK
# ---------------------------------------------------------------------

if int(df["reservoir_count"].sum()) == 0:

    raise RuntimeError(
        "RESERVOIR PROCESSING FAILED: "
        "zero reservoirs were assigned to all basins. "
        "Do NOT use this output."
    )


# ---------------------------------------------------------------------
# SORT
# ---------------------------------------------------------------------

df = df.sort_values(
    "basin_name",
    key=lambda s: s.astype(str)
).reset_index(drop=True)


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
print("RESERVOIR FEATURE ENGINEERING COMPLETE")
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

    print(" -", col)

print()
print("FINAL TABLE:")
print(
    df.to_string(index=False)
)

print()
print("=" * 70)
print("SUCCESS")
print("=" * 70)


# ---------------------------------------------------------------------
# CLEAN TEMPORARY HYDROLAKES DATA
# ---------------------------------------------------------------------

if temp_hydrolakes:

    shutil.rmtree(
        temp_hydrolakes,
        ignore_errors=True
    )