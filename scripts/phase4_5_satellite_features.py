from pathlib import Path
import re
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from shapely.geometry import box
from shapely.ops import transform as shapely_transform
from pyproj import Transformer


# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

BASIN_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "basin_boundaries"
    / "cwc_subbasins.geojson"
)

SATELLITE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "satellite"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "satellite"
)

OUTPUT_FILE = OUTPUT_DIR / "satellite_basin_features.csv"


# Sentinel-2 bands required for NDVI / NDWI
REQUIRED_BANDS = {"B03", "B04", "B08"}


# NDVI / NDWI thresholds for MVP classification
VEGETATION_THRESHOLD = 0.30
WATER_THRESHOLD = 0.30


# Maximum number of pixels retained per scene for pooled statistics.
# This prevents memory explosions on large 10 m rasters.
MAX_SAMPLES_PER_SCENE = 50000


# Minimum valid reflectance.
# Sentinel-2 L2A reflectance is generally stored as scaled uint16.
MIN_REFLECTANCE = 0


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def print_header(title):
    print("=" * 80)
    print(title)
    print("=" * 80)


def normalize_scene_id(scene_id):
    """
    Normalizes:
        T44RKN -> 44RKN
        44RKN  -> 44RKN

    This allows both naming conventions to work.
    """
    scene_id = str(scene_id).upper().strip()

    if scene_id.startswith("T"):
        scene_id = scene_id[1:]

    return scene_id


def discover_satellite_files():
    """
    Discover all raster files under satellite directory.

    Supports:
        .tif
        .tiff
        .jp2

    Ignores:
        .part
    """

    files = []

    if not SATELLITE_DIR.exists():
        raise FileNotFoundError(
            f"Satellite directory does not exist:\n{SATELLITE_DIR}"
        )

    for p in SATELLITE_DIR.rglob("*"):

        if not p.is_file():
            continue

        suffix = p.suffix.lower()

        if suffix not in {".tif", ".tiff", ".jp2"}:
            continue

        # Ignore incomplete downloads
        if ".part" in p.name.lower():
            continue

        files.append(p)

    return sorted(files)


def parse_satellite_filename(path):
    """
    Parse filenames such as:

        43QFA_20240104_B03.tif
        45RTK_20240229_B04.tif
        T44RKN_20251231T052231_B03_10m.jp2

    Returns:
        scene_id
        acquisition
        band
    """

    name = path.name.upper()

    # ------------------------------------------------------------
    # Standard MVP TIFF naming
    # ------------------------------------------------------------

    m = re.match(
        r"^(T?\d{2}[A-Z]{3})_(.+?)_(B0[2348])(?:_10M)?\.(TIF|TIFF|JP2)$",
        name,
        flags=re.IGNORECASE,
    )

    if m:
        scene_id = normalize_scene_id(m.group(1))
        acquisition = m.group(2)
        band = m.group(3).upper()

        return scene_id, acquisition, band


    # ------------------------------------------------------------
    # More permissive fallback
    # ------------------------------------------------------------

    m = re.search(
        r"(T?\d{2}[A-Z]{3}).*_(B0[2348])(?:_10M)?\.(TIF|TIFF|JP2)$",
        name,
        flags=re.IGNORECASE,
    )

    if m:
        scene_id = normalize_scene_id(m.group(1))
        band = m.group(2).upper()

        # Everything between scene id and band
        scene_start = m.start(1)
        band_start = m.start(2)

        middle = name[scene_start + len(m.group(1)):band_start]

        acquisition = middle.strip("_")

        return scene_id, acquisition, band

    return None


def discover_scenes():

    files = discover_satellite_files()

    print(f"RAW SATELLITE FILES: {len(files)}")

    scenes = {}

    for path in files:

        parsed = parse_satellite_filename(path)

        if parsed is None:
            continue

        scene_id, acquisition, band = parsed

        key = (
            normalize_scene_id(scene_id),
            acquisition,
        )

        if key not in scenes:
            scenes[key] = {
                "scene_id": normalize_scene_id(scene_id),
                "acquisition": acquisition,
                "bands": {},
            }

        scenes[key]["bands"][band] = path

    print(f"SCENES DISCOVERED: {len(scenes)}")

    complete = []

    for key in sorted(scenes.keys()):

        scene = scenes[key]

        bands = scene["bands"]

        has_required = REQUIRED_BANDS.issubset(set(bands.keys()))

        if has_required:
            complete.append(scene)

    print(
        f"COMPLETE B03/B04/B08 SCENES: {len(complete)}"
    )

    for scene in complete:

        scene_id = scene["scene_id"]
        acquisition = scene["acquisition"]

        print(
            f"  {scene_id} | {acquisition} | "
            f"B03=Y B04=Y B08=Y"
        )

    return complete


# =============================================================================
# BASIN LOADING
# =============================================================================

def load_basins():

    if not BASIN_FILE.exists():
        raise FileNotFoundError(
            f"Basin boundary file not found:\n{BASIN_FILE}"
        )

    basins = gpd.read_file(BASIN_FILE)

    print()
    print(f"BASIN FILE: {BASIN_FILE}")
    print(f"BASIN ROWS: {len(basins)}")
    print(f"BASIN CRS: {basins.crs}")

    if basins.empty:
        raise ValueError("Basin boundary file contains zero rows.")

    if basins.crs is None:
        print(
            "WARNING: Basin CRS missing. "
            "Assuming EPSG:4326."
        )

        basins = basins.set_crs("EPSG:4326")

    else:
        basins = basins.to_crs("EPSG:4326")

    # ------------------------------------------------------------
    # FIX THE EXACT ERROR YOU ARE GETTING
    # ------------------------------------------------------------

    if "canonical_basin_id" not in basins.columns:

        print()
        print(
            "canonical_basin_id missing from source basin file."
        )

        # Your CWC subbasin file has objectid values corresponding
        # to the CWC basin numbering used by the project.

        if "objectid" in basins.columns:

            basins["canonical_basin_id"] = (
                "CWC_BASIN_"
                + basins["objectid"].astype(str)
            )

            print(
                "Created canonical_basin_id from objectid."
            )

        elif "bacode" in basins.columns:

            basins["canonical_basin_id"] = (
                "CWC_BASIN_"
                + basins["bacode"].astype(str)
            )

            print(
                "Created canonical_basin_id from bacode."
            )

        else:

            # Absolute fallback.
            basins["canonical_basin_id"] = [
                f"CWC_BASIN_{i + 1}"
                for i in range(len(basins))
            ]

            print(
                "Created canonical_basin_id from row numbering."
            )

    # ------------------------------------------------------------
    # Basin name
    # ------------------------------------------------------------

    if "basin_name" not in basins.columns:

        if "ba_name" in basins.columns:

            basins["basin_name"] = (
                basins["ba_name"]
                .fillna("Unknown Basin")
                .astype(str)
            )

        elif "sub_basin" in basins.columns:

            basins["basin_name"] = (
                basins["sub_basin"]
                .fillna("Unknown Basin")
                .astype(str)
            )

        else:

            basins["basin_name"] = "Unknown Basin"

    print()
    print("BASINS:")
    print(f"Rows: {len(basins)}")
    print(f"Columns: {list(basins.columns)}")

    return basins


# =============================================================================
# RASTER FOOTPRINT
# =============================================================================

def raster_footprint_wgs84(path):

    try:

        with rasterio.open(path) as src:

            bounds = src.bounds
            raster_crs = src.crs

            if raster_crs is None:
                return None

            # Convert raster bounds to WGS84.
            left, bottom, right, top = rasterio.warp.transform_bounds(
                raster_crs,
                "EPSG:4326",
                bounds.left,
                bounds.bottom,
                bounds.right,
                bounds.top,
                densify_pts=21,
            )

            return box(
                left,
                bottom,
                right,
                top,
            )

    except Exception as exc:

        print(
            f"WARNING: could not inspect raster "
            f"{path.name}: {exc}"
        )

        return None


# =============================================================================
# SCENE FOOTPRINTS
# =============================================================================

def build_scene_footprints(scenes):

    print()
    print("VALID SCENE FOOTPRINTS:", len(scenes))

    for scene in scenes:

        # B03 is enough to determine footprint.
        path = scene["bands"]["B03"]

        footprint = raster_footprint_wgs84(path)

        scene["footprint"] = footprint

    valid = [
        scene
        for scene in scenes
        if scene.get("footprint") is not None
    ]

    print(
        f"VALID SCENE FOOTPRINTS: {len(valid)}"
    )

    return valid


# =============================================================================
# BASIN / SCENE MATCHING
# =============================================================================

def match_scenes_to_basins(basins, scenes):

    print()
    print("MATCHING SATELLITE SCENES TO BASINS...")

    matches = {}

    intersection_count = 0

    for idx, basin in basins.iterrows():

        basin_id = basin["canonical_basin_id"]

        geometry = basin.geometry

        if geometry is None or geometry.is_empty:
            matches[basin_id] = []
            continue

        basin_matches = []

        for scene in scenes:

            footprint = scene.get("footprint")

            if footprint is None:
                continue

            try:

                if geometry.intersects(footprint):

                    basin_matches.append(scene)
                    intersection_count += 1

            except Exception:

                continue

        matches[basin_id] = basin_matches

    print(
        f"BASIN-SCENE INTERSECTIONS: "
        f"{intersection_count}"
    )

    print()
    print("BASINS WITH SATELLITE COVERAGE:")

    coverage_count = 0

    for basin_id, basin_scenes in matches.items():

        if len(basin_scenes) == 0:
            continue

        coverage_count += 1

        row = basins[
            basins["canonical_basin_id"] == basin_id
        ].iloc[0]

        basin_name = row["basin_name"]

        print(
            f"  {basin_id} | "
            f"{basin_name} | "
            f"scenes={len(basin_scenes)}"
        )

    print()
    print(
        f"BASINS WITH COVERAGE: "
        f"{coverage_count}/{len(basins)}"
    )

    return matches


# =============================================================================
# GEOMETRY TRANSFORMATION
# =============================================================================

def transform_geometry_to_crs(geometry, source_crs, target_crs):

    if geometry is None or geometry.is_empty:
        return None

    if str(source_crs) == str(target_crs):
        return geometry

    transformer = Transformer.from_crs(
        source_crs,
        target_crs,
        always_xy=True,
    )

    return shapely_transform(
        transformer.transform,
        geometry,
    )


# =============================================================================
# SAFE RASTER READ
# =============================================================================

def read_masked_band(path, basin_geometry):

    try:

        with rasterio.open(path) as src:

            raster_crs = src.crs

            if raster_crs is None:
                return None

            transformed_geometry = (
                transform_geometry_to_crs(
                    basin_geometry,
                    "EPSG:4326",
                    raster_crs,
                )
            )

            if (
                transformed_geometry is None
                or transformed_geometry.is_empty
            ):
                return None

            try:

                data, _ = mask(
                    src,
                    [transformed_geometry],
                    crop=True,
                    filled=False,
                )

            except ValueError:

                # Geometry does not overlap raster.
                return None

            if data.size == 0:
                return None

            arr = data[0]

            if np.ma.isMaskedArray(arr):

                arr = arr.compressed()

            else:

                arr = arr.reshape(-1)

            if arr.size == 0:
                return None

            arr = arr.astype(np.float32)

            # Sentinel-2 L2A reflectance scaling.
            # Values such as 5000 -> 0.5
            if np.nanmax(arr) > 2:

                arr = arr / 10000.0

            arr = arr[
                np.isfinite(arr)
            ]

            arr = arr[
                arr >= MIN_REFLECTANCE
            ]

            return arr

    except Exception as exc:

        print(
            f"      WARNING: failed raster "
            f"{path.name}: {exc}"
        )

        return None


# =============================================================================
# SCENE FEATURE EXTRACTION
# =============================================================================

def extract_scene_indices(scene, basin_geometry):

    scene_id = scene["scene_id"]
    acquisition = scene["acquisition"]

    print(
        f"  Processing {scene_id} "
        f"{acquisition}..."
    )

    b03 = read_masked_band(
        scene["bands"]["B03"],
        basin_geometry,
    )

    b04 = read_masked_band(
        scene["bands"]["B04"],
        basin_geometry,
    )

    b08 = read_masked_band(
        scene["bands"]["B08"],
        basin_geometry,
    )

    if b03 is None or b04 is None or b08 is None:

        print(
            "    -> Could not extract all required bands"
        )

        return None

    # All arrays should normally have equal lengths
    # because they come from identical Sentinel-2 grids.
    n = min(
        len(b03),
        len(b04),
        len(b08),
    )

    if n == 0:
        return None

    b03 = b03[:n]
    b04 = b04[:n]
    b08 = b08[:n]

    # ------------------------------------------------------------
    # NDVI
    # ------------------------------------------------------------

    ndvi_denominator = b08 + b04

    valid_ndvi = (
        np.isfinite(ndvi_denominator)
        & (np.abs(ndvi_denominator) > 1e-8)
    )

    ndvi = (
        (b08 - b04)
        / np.where(
            valid_ndvi,
            ndvi_denominator,
            np.nan,
        )
    )

    # ------------------------------------------------------------
    # NDWI
    # Green vs NIR
    # ------------------------------------------------------------

    ndwi_denominator = b03 + b08

    valid_ndwi = (
        np.isfinite(ndwi_denominator)
        & (np.abs(ndwi_denominator) > 1e-8)
    )

    ndwi = (
        (b03 - b08)
        / np.where(
            valid_ndwi,
            ndwi_denominator,
            np.nan,
        )
    )

    # ------------------------------------------------------------
    # Remove impossible index values
    # ------------------------------------------------------------

    ndvi = ndvi[
        np.isfinite(ndvi)
        & (ndvi >= -1)
        & (ndvi <= 1)
    ]

    ndwi = ndwi[
        np.isfinite(ndwi)
        & (ndwi >= -1)
        & (ndwi <= 1)
    ]

    if len(ndvi) == 0 or len(ndwi) == 0:

        print(
            "    -> No valid NDVI/NDWI pixels"
        )

        return None

    # ------------------------------------------------------------
    # Downsample for memory safety
    # ------------------------------------------------------------

    if len(ndvi) > MAX_SAMPLES_PER_SCENE:

        rng = np.random.default_rng(
            seed=42
        )

        indices = rng.choice(
            len(ndvi),
            size=MAX_SAMPLES_PER_SCENE,
            replace=False,
        )

        ndvi = ndvi[indices]

    if len(ndwi) > MAX_SAMPLES_PER_SCENE:

        rng = np.random.default_rng(
            seed=43
        )

        indices = rng.choice(
            len(ndwi),
            size=MAX_SAMPLES_PER_SCENE,
            replace=False,
        )

        ndwi = ndwi[indices]

    print(
        f"    Valid pixels: "
        f"NDVI={len(ndvi):,} "
        f"NDWI={len(ndwi):,}"
    )

    return {
        "scene_id": scene_id,
        "acquisition": acquisition,
        "ndvi": ndvi,
        "ndwi": ndwi,
    }


# =============================================================================
# STATISTICS
# =============================================================================

def calculate_statistics(values):

    if values is None or len(values) == 0:

        return {
            "mean": np.nan,
            "median": np.nan,
            "std": np.nan,
            "min": np.nan,
            "max": np.nan,
        }

    values = np.asarray(values)

    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


# =============================================================================
# BASIN FEATURE EXTRACTION
# =============================================================================

def extract_basin_features(
    basin,
    basin_scenes,
):

    basin_id = basin["canonical_basin_id"]
    basin_name = basin["basin_name"]
    geometry = basin.geometry

    ndvi_samples = []
    ndwi_samples = []

    products = []

    print()
    print(
        f"Processing basin: "
        f"{basin_id} | {basin_name}"
    )

    if not basin_scenes:

        print(
            "  -> NO SATELLITE DATA"
        )

        return {
            "canonical_basin_id": basin_id,
            "basin_name": basin_name,

            "ndvi_mean": np.nan,
            "ndvi_median": np.nan,
            "ndvi_std": np.nan,
            "ndvi_min": np.nan,
            "ndvi_max": np.nan,

            "ndwi_mean": np.nan,
            "ndwi_median": np.nan,
            "ndwi_std": np.nan,
            "ndwi_min": np.nan,
            "ndwi_max": np.nan,

            "vegetation_pct": np.nan,
            "water_pct": np.nan,

            "satellite_products_used": 0,
            "satellite_valid_pixels": 0,
            "satellite_data_available": 0,
        }

    for scene in basin_scenes:

        result = extract_scene_indices(
            scene,
            geometry,
        )

        if result is None:
            continue

        ndvi_samples.append(
            result["ndvi"]
        )

        ndwi_samples.append(
            result["ndwi"]
        )

        products.append(
            f"{result['scene_id']}_{result['acquisition']}"
        )

    if not ndvi_samples or not ndwi_samples:

        print(
            "  -> NO VALID SATELLITE DATA"
        )

        return {
            "canonical_basin_id": basin_id,
            "basin_name": basin_name,

            "ndvi_mean": np.nan,
            "ndvi_median": np.nan,
            "ndvi_std": np.nan,
            "ndvi_min": np.nan,
            "ndvi_max": np.nan,

            "ndwi_mean": np.nan,
            "ndwi_median": np.nan,
            "ndwi_std": np.nan,
            "ndwi_min": np.nan,
            "ndwi_max": np.nan,

            "vegetation_pct": np.nan,
            "water_pct": np.nan,

            "satellite_products_used": 0,
            "satellite_valid_pixels": 0,
            "satellite_data_available": 0,
        }

    # ------------------------------------------------------------
    # Combine scene samples
    # ------------------------------------------------------------

    ndvi_all = np.concatenate(
        ndvi_samples
    )

    ndwi_all = np.concatenate(
        ndwi_samples
    )

    ndvi_stats = calculate_statistics(
        ndvi_all
    )

    ndwi_stats = calculate_statistics(
        ndwi_all
    )

    # ------------------------------------------------------------
    # Vegetation percentage
    # ------------------------------------------------------------

    vegetation_pct = float(
        np.mean(
            ndvi_all >= VEGETATION_THRESHOLD
        )
        * 100.0
    )

    # ------------------------------------------------------------
    # Water percentage
    # ------------------------------------------------------------

    water_pct = float(
        np.mean(
            ndwi_all >= WATER_THRESHOLD
        )
        * 100.0
    )

    valid_pixels = int(
        min(
            len(ndvi_all),
            len(ndwi_all),
        )
    )

    print(
        f"  -> SATELLITE DATA AVAILABLE"
    )

    print(
        f"  -> Scenes used: "
        f"{len(products)}"
    )

    print(
        f"  -> Valid pixels: "
        f"{valid_pixels:,}"
    )

    print(
        f"  -> NDVI mean: "
        f"{ndvi_stats['mean']:.4f}"
    )

    print(
        f"  -> NDWI mean: "
        f"{ndwi_stats['mean']:.4f}"
    )

    return {
        "canonical_basin_id": basin_id,
        "basin_name": basin_name,

        "ndvi_mean": ndvi_stats["mean"],
        "ndvi_median": ndvi_stats["median"],
        "ndvi_std": ndvi_stats["std"],
        "ndvi_min": ndvi_stats["min"],
        "ndvi_max": ndvi_stats["max"],

        "ndwi_mean": ndwi_stats["mean"],
        "ndwi_median": ndwi_stats["median"],
        "ndwi_std": ndwi_stats["std"],
        "ndwi_min": ndwi_stats["min"],
        "ndwi_max": ndwi_stats["max"],

        "vegetation_pct": vegetation_pct,
        "water_pct": water_pct,

        "satellite_products_used": len(products),
        "satellite_valid_pixels": valid_pixels,
        "satellite_data_available": 1,
    }


# =============================================================================
# VALIDATION
# =============================================================================

def validate_output(
    output_df,
    expected_basins,
):

    print()
    print_header(
        "PHASE 4.5 SATELLITE VALIDATION"
    )

    print(
        f"OUTPUT: {OUTPUT_FILE}"
    )

    print(
        f"ROWS: {len(output_df)}"
    )

    print(
        f"EXPECTED BASINS: {expected_basins}"
    )

    print(
        f"UNIQUE BASINS: "
        f"{output_df['canonical_basin_id'].nunique()}"
    )

    available = int(
        output_df[
            "satellite_data_available"
        ].sum()
    )

    print()
    print(
        "SATELLITE DATA AVAILABLE:"
    )

    print(
        f"{available} / {expected_basins}"
    )

    print()
    print(
        "SATELLITE PRODUCTS USED:"
    )

    print(
        output_df[
            "satellite_products_used"
        ].describe()
    )

    print()
    print(
        "VALID PIXELS:"
    )

    print(
        output_df[
            "satellite_valid_pixels"
        ].describe()
    )

    print()
    print(
        "NULL COUNTS:"
    )

    feature_columns = [
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
        "water_pct",
    ]

    print(
        output_df[
            feature_columns
        ].isna().sum()
    )

    print()
    print(
        "NDVI SUMMARY:"
    )

    print(
        output_df[
            "ndvi_mean"
        ].describe()
    )

    print()
    print(
        "NDWI SUMMARY:"
    )

    print(
        output_df[
            "ndwi_mean"
        ].describe()
    )

    # ------------------------------------------------------------
    # Range checks
    # ------------------------------------------------------------

    print()
    print(
        "RANGE CHECKS:"
    )

    checks = {

        "NDVI mean [-1,1]":
            output_df["ndvi_mean"]
            .dropna()
            .between(-1, 1)
            .all(),

        "NDWI mean [-1,1]":
            output_df["ndwi_mean"]
            .dropna()
            .between(-1, 1)
            .all(),

        "vegetation_pct [0,100]":
            output_df["vegetation_pct"]
            .dropna()
            .between(0, 100)
            .all(),

        "water_pct [0,100]":
            output_df["water_pct"]
            .dropna()
            .between(0, 100)
            .all(),

        "basin count":
            len(output_df) == expected_basins,

        "unique basin count":
            output_df[
                "canonical_basin_id"
            ].nunique() == expected_basins,
    }

    for name, result in checks.items():

        print(
            f"  {name}: "
            f"{'PASS' if result else 'FAIL'}"
        )

    print()
    print(
        "SATELLITE COVERAGE:"
    )

    coverage_pct = (
        available
        / expected_basins
        * 100
    )

    print(
        f"{coverage_pct:.1f}% "
        f"({available}/{expected_basins})"
    )

    return checks


# =============================================================================
# MAIN
# =============================================================================

def main():

    warnings.filterwarnings(
        "ignore",
        category=UserWarning,
    )

    print_header(
        "CHETAKAI - PHASE 4.5 SATELLITE FEATURE EXTRACTION"
    )

    print()

    # ------------------------------------------------------------
    # 1. Load basins
    # ------------------------------------------------------------

    basins = load_basins()

    # ------------------------------------------------------------
    # 2. Discover Sentinel-2 scenes
    # ------------------------------------------------------------

    scenes = discover_scenes()

    if not scenes:

        raise RuntimeError(
            "No complete Sentinel-2 B03/B04/B08 scenes found."
        )

    # ------------------------------------------------------------
    # 3. Build scene footprints
    # ------------------------------------------------------------

    scenes = build_scene_footprints(
        scenes
    )

    if not scenes:

        raise RuntimeError(
            "No valid Sentinel-2 scene footprints could be created."
        )

    # ------------------------------------------------------------
    # 4. Match scenes to basins
    # ------------------------------------------------------------

    scene_matches = match_scenes_to_basins(
        basins,
        scenes,
    )

    # ------------------------------------------------------------
    # 5. Extract features
    # ------------------------------------------------------------

    print()
    print(
        "EXTRACTING NDVI / NDWI..."
    )

    records = []

    total = len(basins)

    for counter, (_, basin) in enumerate(
        basins.iterrows(),
        start=1,
    ):

        basin_id = basin[
            "canonical_basin_id"
        ]

        basin_name = basin[
            "basin_name"
        ]

        print()
        print(
            f"[{counter}/{total}] "
            f"{basin_name} | {basin_id}"
        )

        basin_scenes = scene_matches.get(
            basin_id,
            [],
        )

        record = extract_basin_features(
            basin,
            basin_scenes,
        )

        records.append(record)

    # ------------------------------------------------------------
    # 6. Create dataframe
    # ------------------------------------------------------------

    output_df = pd.DataFrame(
        records
    )

    # ------------------------------------------------------------
    # 7. Ensure exact basin coverage
    # ------------------------------------------------------------

    basin_ids = (
        basins[
            "canonical_basin_id"
        ]
        .astype(str)
        .tolist()
    )

    output_df = (
        output_df
        .drop_duplicates(
            subset=[
                "canonical_basin_id"
            ],
            keep="first",
        )
    )

    missing_ids = [
        basin_id
        for basin_id in basin_ids
        if basin_id not in set(
            output_df[
                "canonical_basin_id"
            ]
        )
    ]

    # Safety fallback
    if missing_ids:

        print()
        print(
            "WARNING: Missing basin rows detected."
        )

        for basin_id in missing_ids:

            row = basins[
                basins[
                    "canonical_basin_id"
                ] == basin_id
            ].iloc[0]

            output_df = pd.concat(
                [
                    output_df,
                    pd.DataFrame(
                        [{
                            "canonical_basin_id":
                                basin_id,

                            "basin_name":
                                row["basin_name"],

                            "ndvi_mean":
                                np.nan,

                            "ndvi_median":
                                np.nan,

                            "ndvi_std":
                                np.nan,

                            "ndvi_min":
                                np.nan,

                            "ndvi_max":
                                np.nan,

                            "ndwi_mean":
                                np.nan,

                            "ndwi_median":
                                np.nan,

                            "ndwi_std":
                                np.nan,

                            "ndwi_min":
                                np.nan,

                            "ndwi_max":
                                np.nan,

                            "vegetation_pct":
                                np.nan,

                            "water_pct":
                                np.nan,

                            "satellite_products_used":
                                0,

                            "satellite_valid_pixels":
                                0,

                            "satellite_data_available":
                                0,
                        }]
                    ),
                ],
                ignore_index=True,
            )

    # ------------------------------------------------------------
    # 8. Restore original basin ordering
    # ------------------------------------------------------------

    order_map = {
        basin_id: i
        for i, basin_id
        in enumerate(basin_ids)
    }

    output_df["_order"] = (
        output_df[
            "canonical_basin_id"
        ]
        .map(order_map)
    )

    output_df = (
        output_df
        .sort_values("_order")
        .drop(columns=["_order"])
        .reset_index(drop=True)
    )

    # ------------------------------------------------------------
    # 9. Save
    # ------------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    # ------------------------------------------------------------
    # 10. Validate
    # ------------------------------------------------------------

    checks = validate_output(
        output_df,
        len(basins),
    )

    # ------------------------------------------------------------
    # Final status
    # ------------------------------------------------------------

    print()
    print_header(
        "PHASE 4.5 COMPLETE"
    )

    print(
        "Satellite feature extraction finished."
    )

    print()
    print(
        f"Output file:"
    )

    print(
        OUTPUT_FILE
    )

    print()
    print(
        "Features:"
    )

    print(
        "  NDVI mean/median/std/min/max"
    )

    print(
        "  NDWI mean/median/std/min/max"
    )

    print(
        "  vegetation_pct"
    )

    print(
        "  water_pct"
    )

    print(
        "  satellite_products_used"
    )

    print(
        "  satellite_valid_pixels"
    )

    print(
        "  satellite_data_available"
    )

    print()

    if all(checks.values()):

        print(
            "STATUS: PASS"
        )

    else:

        print(
            "STATUS: COMPLETED WITH VALIDATION WARNINGS"
        )

    print()
    print(
        "Raw satellite files were NOT modified."
    )


if __name__ == "__main__":
    main()