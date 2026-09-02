import os
import shutil
import pandas as pd
import geopandas as gpd

# ============================================================
# CHETAKAI — PHASE 4.2
# HYDROGRAPHY MISSING-DATA REPAIR
# ============================================================

BASE = r"C:\Users\vinee\OneDrive\Desktop\ChetakAI"

BASIN_FILE = os.path.join(
    BASE, "data", "raw", "basin_boundaries", "cwc_basins.geojson"
)

RIVER_FILE = os.path.join(
    BASE, "data", "raw", "hydrography", "rivers", "river_network.kml"
)

OUTPUT_FILE = os.path.join(
    BASE, "data", "processed", "hydrography",
    "hydrography_basin_features.csv"
)

BACKUP_FILE = os.path.join(
    BASE, "data", "processed", "hydrography",
    "hydrography_basin_features.pre_phase4_2_backup.csv"
)

print("=" * 100)
print("CHETAKAI — PHASE 4.2: HYDROGRAPHY MISSING-DATA REPAIR")
print("=" * 100)

# ------------------------------------------------------------
# 1. CHECK FILES
# ------------------------------------------------------------

print("\n[1/7] Checking input files...")

for p in [BASIN_FILE, RIVER_FILE, OUTPUT_FILE]:
    if not os.path.exists(p):
        raise FileNotFoundError(f"Missing file: {p}")
    print("✓", p)

# ------------------------------------------------------------
# 2. LOAD EXISTING HYDROGRAPHY DATA
# ------------------------------------------------------------

print("\n[2/7] Loading existing hydrography dataset...")

df = pd.read_csv(OUTPUT_FILE)

print("Rows             :", len(df))
print("Columns          :", len(df.columns))
print("Unique basin IDs :", df["canonical_basin_id"].nunique())

# ------------------------------------------------------------
# 3. BACKUP
# ------------------------------------------------------------

print("\n[3/7] Creating backup...")

if not os.path.exists(BACKUP_FILE):
    shutil.copy2(OUTPUT_FILE, BACKUP_FILE)
    print("✓ Backup created")
else:
    print("✓ Backup already exists")

# ------------------------------------------------------------
# 4. LOAD BASINS
# ------------------------------------------------------------

print("\n[4/7] Loading CWC basin boundaries...")

basins = gpd.read_file(BASIN_FILE)

print("Basin rows :", len(basins))
print("Basin CRS  :", basins.crs)

if "bacode" not in basins.columns:
    raise ValueError("Expected 'bacode' column not found")

# ------------------------------------------------------------
# ACTUAL CWC CODE → CANONICAL ID
# ------------------------------------------------------------

code_to_id = {
    "05": "CWC_BASIN_001",
    "17": "CWC_BASIN_002",
    "09": "CWC_BASIN_003",
    "03": "CWC_BASIN_004",
    "08": "CWC_BASIN_005",
    "06": "CWC_BASIN_006",
    "07": "CWC_BASIN_007",
    "20": "CWC_BASIN_008",
    "11": "CWC_BASIN_009",
    "2C": "CWC_BASIN_010",
    "2B": "CWC_BASIN_011",
    "2A": "CWC_BASIN_012",
    "18": "CWC_BASIN_013",
    "12": "CWC_BASIN_014",
    "15": "CWC_BASIN_015",
    "19": "CWC_BASIN_016",
    "04": "CWC_BASIN_017",
    "21": "CWC_BASIN_018",
    "22": "CWC_BASIN_019",
    "23": "CWC_BASIN_020",
    "16": "CWC_BASIN_021",
    "10": "CWC_BASIN_022",
    "13": "CWC_BASIN_023",
    "14": "CWC_BASIN_024",
    "01": "CWC_BASIN_025",
}

basins["bacode"] = basins["bacode"].astype(str).str.strip().str.upper()

basins["canonical_basin_id"] = basins["bacode"].map(code_to_id)

missing_mapping = basins["canonical_basin_id"].isna().sum()

if missing_mapping:
    print("\nWARNING: Unmapped basin codes:")
    print(
        basins.loc[
            basins["canonical_basin_id"].isna(),
            ["bacode", "ba_name"]
        ].to_string(index=False)
    )
    raise ValueError("Some CWC basin codes could not be mapped")

print("\n✓ All 25 CWC basins mapped successfully")

# ------------------------------------------------------------
# 5. LOAD RIVERS
# ------------------------------------------------------------

print("\n[5/7] Loading river network...")
print("River network contains ~30,000 features; processing may take a few minutes.")

rivers = gpd.read_file(
    RIVER_FILE,
    driver="KML"
)

print("River features :", len(rivers))
print("River CRS      :", rivers.crs)

# Remove invalid/empty geometries
rivers = rivers[
    rivers.geometry.notna() &
    ~rivers.geometry.is_empty
].copy()

print("Valid rivers   :", len(rivers))

# ------------------------------------------------------------
# PROJECT TO METRIC CRS
# ------------------------------------------------------------

print("\nProjecting to EPSG:6933 for length calculation...")

basins_metric = basins.to_crs("EPSG:6933")
rivers_metric = rivers.to_crs("EPSG:6933")

# ------------------------------------------------------------
# SPATIAL JOIN
# ------------------------------------------------------------

print("\nFinding rivers intersecting each basin...")

joined = gpd.sjoin(
    rivers_metric[["geometry"]],
    basins_metric[
        ["canonical_basin_id", "geometry"]
    ],
    how="inner",
    predicate="intersects"
)

print("Intersecting records :", len(joined))

# ------------------------------------------------------------
# CLIP RIVERS TO BASIN
# ------------------------------------------------------------

print("\nClipping river geometries to basin boundaries...")

basin_geom = basins_metric.set_index(
    "canonical_basin_id"
)["geometry"]

joined["basin_geometry"] = joined[
    "canonical_basin_id"
].map(basin_geom)

joined["clipped_geometry"] = joined.geometry.intersection(
    joined["basin_geometry"]
)

joined = joined[
    joined["clipped_geometry"].notna() &
    ~joined["clipped_geometry"].is_empty
].copy()

# ------------------------------------------------------------
# CALCULATE LENGTH
# ------------------------------------------------------------

joined["river_length_km"] = (
    joined["clipped_geometry"].length / 1000.0
)

river_stats = (
    joined.groupby("canonical_basin_id")["river_length_km"]
    .sum()
    .reset_index()
)

# ------------------------------------------------------------
# BASIN AREA
# ------------------------------------------------------------

basins_metric["area_sqkm_calc"] = (
    basins_metric.geometry.area / 1_000_000
)

area_lookup = basins_metric[
    ["canonical_basin_id", "area_sqkm_calc"]
]

river_stats = river_stats.merge(
    area_lookup,
    on="canonical_basin_id",
    how="left"
)

river_stats["river_density_km_per_km2"] = (
    river_stats["river_length_km"] /
    river_stats["area_sqkm_calc"]
)

# ------------------------------------------------------------
# UPDATE DATASET
# ------------------------------------------------------------

print("\n[6/7] Updating hydrography dataset...")

df = df.drop(
    columns=[
        "river_length_km",
        "river_density_km_per_km2"
    ],
    errors="ignore"
)

df = df.merge(
    river_stats[
        [
            "canonical_basin_id",
            "river_length_km",
            "river_density_km_per_km2"
        ]
    ],
    on="canonical_basin_id",
    how="left"
)

# ------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------

print("\n[7/7] Validation...")

missing_length = df["river_length_km"].isna().sum()
missing_density = df["river_density_km_per_km2"].isna().sum()

print("Total basins            :", len(df))
print("Missing river length    :", missing_length)
print("Missing river density   :", missing_density)

print("\nFinal hydrography values:")

print(
    df[
        [
            "canonical_basin_id",
            "river_length_km",
            "river_density_km_per_km2"
        ]
    ]
    .sort_values("canonical_basin_id")
    .to_string(index=False)
)

# ------------------------------------------------------------
# SAVE
# ------------------------------------------------------------

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\n✓ Saved:")
print(OUTPUT_FILE)

print("\n" + "=" * 100)
print("PHASE 4.2 COMPLETE")
print("=" * 100)