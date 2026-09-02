from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

API_PATH = ROOT / "scripts" / "phase21_production_risk_api.py"
BACKUP_PATH = ROOT / "scripts" / "phase21_production_risk_api.pre_terrain_runtime_fix.py"

TERRAIN_DIR = (
    ROOT
    / "data"
    / "processed"
    / "features"
    / "terrain"
)

RAW_DEM_DIR = (
    ROOT
    / "data"
    / "raw"
    / "dem"
)

INFERENCE_PATH = (
    ROOT
    / "data"
    / "processed"
    / "training"
    / "phase15_1"
    / "unlabeled_inference.csv"
)

MODEL_PATH = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase19"
    / "best_phase19_flood_model.joblib"
)

CONTRACT_PATH = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase19"
    / "phase19_feature_contract.json"
)


TERRAIN_FEATURES = (
    "mean_slope_deg",
    "elevation_range_ratio",
    "min_elevation_m",
)


def normalize_basin_id(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    text = str(value).strip().upper()

    if not text:
        return None

    if text.startswith("CWC_BASIN_"):
        suffix = text.replace("CWC_BASIN_", "", 1)
        if suffix.isdigit():
            return f"CWC_BASIN_{int(suffix):03d}"
        return text

    if text.startswith("CWC_"):
        suffix = text.replace("CWC_", "", 1)
        if suffix.isdigit():
            return f"CWC_BASIN_{int(suffix):03d}"

    if text.isdigit():
        return f"CWC_BASIN_{int(text):03d}"

    return text


def finite(value):
    try:
        value = float(value)
        return math.isfinite(value)
    except Exception:
        return False


def safe_float(value):
    try:
        value = float(value)
        if not math.isfinite(value):
            return None
        return value
    except Exception:
        return None


def discover_basin_column(df):
    candidates = [
        "canonical_basin_id",
        "basin_id",
        "BASIN_ID",
        "basin",
        "cwc_basin_id",
        "cwc_id",
        "id",
    ]

    lower = {
        str(c).strip().lower(): c
        for c in df.columns
    }

    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]

    return None


def discover_timestamp_column(df):
    candidates = [
        "timestamp",
        "datetime",
        "date",
        "time",
        "valid_time",
    ]

    lower = {
        str(c).strip().lower(): c
        for c in df.columns
    }

    for candidate in candidates:
        if candidate in lower:
            return lower[candidate]

    return None


def load_training_medians(features):
    candidates = [
        ROOT / "data" / "processed" / "models" / "phase19" / "train_selected.csv",
        ROOT / "data" / "processed" / "models" / "phase19" / "phase19_training_matrix.csv",
        ROOT / "data" / "processed" / "models" / "phase19" / "train.csv",
        ROOT / "data" / "processed" / "models" / "phase18" / "train_physical.csv",
        INFERENCE_PATH,
    ]

    for path in candidates:
        if not path.exists():
            continue

        try:
            df = pd.read_csv(path)

            available = [
                feature
                for feature in features
                if feature in df.columns
            ]

            if len(available) < len(features) * 0.8:
                continue

            values = (
                df[features]
                .apply(pd.to_numeric, errors="coerce")
                .median()
            )

            return {
                feature: safe_float(values.get(feature))
                for feature in features
                if safe_float(values.get(feature)) is not None
            }

        except Exception:
            continue

    return {}


def extract_model_medians(features):
    try:
        artifact = joblib.load(MODEL_PATH)
    except Exception:
        return {}

    result = {}

    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():

                key_text = str(key).lower()

                if isinstance(value, dict) and "median" in key_text:
                    for feature, median in value.items():
                        numeric = safe_float(median)
                        if numeric is not None:
                            result[str(feature)] = numeric

                walk(value)

        elif isinstance(obj, (list, tuple)):
            for value in obj:
                walk(value)

    walk(artifact)

    return {
        feature: result[feature]
        for feature in features
        if feature in result
    }


def find_terrain_files():
    files = []

    if TERRAIN_DIR.exists():
        for path in TERRAIN_DIR.rglob("*"):
            if (
                path.is_file()
                and path.suffix.lower()
                in {".csv", ".parquet", ".json", ".geojson", ".tif", ".tiff", ".vrt"}
            ):
                files.append(path)

    return sorted(files)


def find_terrain_table_for_basin(basin_id):
    target = normalize_basin_id(basin_id)

    if target is None:
        return None, None

    for path in find_terrain_files():

        if path.suffix.lower() not in {
            ".csv",
            ".parquet",
            ".json",
            ".geojson",
        }:
            continue

        try:

            if path.suffix.lower() == ".csv":
                df = pd.read_csv(path)

            elif path.suffix.lower() == ".parquet":
                df = pd.read_parquet(path)

            elif path.suffix.lower() in {".json", ".geojson"}:
                df = pd.read_json(path)

            else:
                continue

            if df.empty:
                continue

            basin_col = discover_basin_column(df)

            if basin_col is None:
                continue

            normalized = df[basin_col].apply(normalize_basin_id)

            matches = df[normalized == target]

            if matches.empty:
                continue

            row = matches.iloc[-1]

            values = {}

            for feature in TERRAIN_FEATURES:
                if feature in row.index:
                    numeric = safe_float(row[feature])

                    if numeric is not None:
                        values[feature] = numeric

            if values:
                return values, path

        except Exception:
            continue

    return None, None


def terrain_raster_candidates():
    files = []

    for base in (TERRAIN_DIR, RAW_DEM_DIR):

        if not base.exists():
            continue

        for path in base.rglob("*"):

            if not path.is_file():
                continue

            if path.suffix.lower() not in {
                ".tif",
                ".tiff",
                ".vrt",
            }:
                continue

            files.append(path)

    return sorted(files)


def read_raster_stats(path):
    try:
        import rasterio

        with rasterio.open(path) as src:

            data = src.read(
                1,
                masked=True,
            )

            values = np.asarray(
                data.compressed(),
                dtype=float,
            )

            if values.size == 0:
                return None

            values = values[np.isfinite(values)]

            if values.size == 0:
                return None

            return {
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "mean": float(np.mean(values)),
            }

    except Exception:
        return None


def derive_terrain_from_raster_fallback():
    """
    Last-resort deterministic DEM derivation.

    This is deliberately conservative:
    it does not invent geographic values.

    If a processed raster explicitly represents one of the
    requested terrain products, use it directly.

    Otherwise a DEM can provide minimum elevation, while
    slope/range are only derived when an explicit terrain
    raster is identifiable.
    """

    candidates = terrain_raster_candidates()

    if not candidates:
        return {}, []

    derived = {}
    used = []

    for path in candidates:

        name = path.stem.lower()

        if (
            "slope" in name
            and "mean_slope_deg" not in derived
        ):
            stats = read_raster_stats(path)

            if stats:
                derived["mean_slope_deg"] = stats["mean"]
                used.append(str(path))

        elif (
            (
                "elevation_range_ratio" in name
                or "elev_range_ratio" in name
                or "range_ratio" in name
            )
            and "elevation_range_ratio" not in derived
        ):
            stats = read_raster_stats(path)

            if stats:
                derived["elevation_range_ratio"] = stats["mean"]
                used.append(str(path))

        elif (
            (
                "min_elevation" in name
                or "elevation_min" in name
                or name.startswith("min_elev")
            )
            and "min_elevation_m" not in derived
        ):
            stats = read_raster_stats(path)

            if stats:
                derived["min_elevation_m"] = stats["min"]
                used.append(str(path))

    return derived, used


def inject_runtime_resolver():
    text = API_PATH.read_text(
        encoding="utf-8"
    )

    if "PHASE21_TERRAIN_RUNTIME_FIX_V1" in text:
        print("Runtime terrain resolver already installed.")
        return

    backup = API_PATH.with_name(
        "phase21_production_risk_api.pre_terrain_runtime_fix.py"
    )

    shutil.copy2(
        API_PATH,
        backup,
    )

    marker = "# =============================================================================\n# FEATURE VECTOR\n# ============================================================================="

    if marker not in text:
        raise RuntimeError(
            "Could not find Phase 21 FEATURE VECTOR marker."
        )

    runtime_block = r'''

# =============================================================================
# PHASE21_TERRAIN_RUNTIME_FIX_V1
# =============================================================================

def _phase21_normalize_basin(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    text = str(value).strip().upper()

    if not text:
        return None

    if text.startswith("CWC_BASIN_"):
        suffix = text.replace("CWC_BASIN_", "", 1)
        if suffix.isdigit():
            return f"CWC_BASIN_{int(suffix):03d}"
        return text

    if text.startswith("CWC_"):
        suffix = text.replace("CWC_", "", 1)
        if suffix.isdigit():
            return f"CWC_BASIN_{int(suffix):03d}"

    if text.isdigit():
        return f"CWC_BASIN_{int(text):03d}"

    return text


def _phase21_numeric(value):
    try:
        value = float(value)
        if not math.isfinite(value):
            return None
        return value
    except Exception:
        return None


def _phase21_find_terrain_tables():
    paths = []

    if TERRAIN_DIR.exists():
        for path in TERRAIN_DIR.rglob("*"):
            if (
                path.is_file()
                and path.suffix.lower()
                in {".csv", ".parquet", ".json"}
            ):
                paths.append(path)

    return sorted(paths)


def _phase21_terrain_from_tables(basin_id):
    target = _phase21_normalize_basin(basin_id)

    if target is None:
        return {}, []

    for path in _phase21_find_terrain_tables():

        try:

            suffix = path.suffix.lower()

            if suffix == ".csv":
                df = pd.read_csv(path)

            elif suffix == ".parquet":
                df = pd.read_parquet(path)

            elif suffix == ".json":
                df = pd.read_json(path)

            else:
                continue

            if df.empty:
                continue

            basin_col = None

            for candidate in [
                "canonical_basin_id",
                "basin_id",
                "BASIN_ID",
                "basin",
                "cwc_basin_id",
                "cwc_id",
                "id",
            ]:
                if candidate in df.columns:
                    basin_col = candidate
                    break

            if basin_col is None:
                continue

            normalized = df[basin_col].apply(
                _phase21_normalize_basin
            )

            matches = df[
                normalized == target
            ]

            if matches.empty:
                continue

            values = {}

            for feature in [
                "mean_slope_deg",
                "elevation_range_ratio",
                "min_elevation_m",
            ]:

                if feature not in matches.columns:
                    continue

                series = pd.to_numeric(
                    matches[feature],
                    errors="coerce",
                ).dropna()

                if not series.empty:
                    values[feature] = float(
                        series.iloc[-1]
                    )

            if values:
                return values, [str(path)]

        except Exception:
            continue

    return {}, []


def _phase21_terrain_from_state_history(
    inference_df,
    basin_id,
):
    target = _phase21_normalize_basin(
        basin_id
    )

    if target is None:
        return {}, []

    basin_col = None

    for candidate in [
        "canonical_basin_id",
        "basin_id",
        "BASIN_ID",
        "basin",
        "cwc_basin_id",
        "cwc_id",
    ]:
        if candidate in inference_df.columns:
            basin_col = candidate
            break

    if basin_col is None:
        return {}, []

    normalized = inference_df[
        basin_col
    ].apply(_phase21_normalize_basin)

    rows = inference_df[
        normalized == target
    ].copy()

    if rows.empty:
        return {}, []

    values = {}

    for feature in [
        "mean_slope_deg",
        "elevation_range_ratio",
        "min_elevation_m",
    ]:

        if feature not in rows.columns:
            continue

        series = pd.to_numeric(
            rows[feature],
            errors="coerce",
        ).dropna()

        if not series.empty:
            values[feature] = float(
                series.iloc[-1]
            )

    if values:
        return values, ["inference_state_history"]

    return {}, []


def _phase21_terrain_from_rasters(
    basin_id=None,
):
    """
    Explicitly searches processed terrain products.

    We only use a raster when its filename identifies
    the requested physical terrain feature.

    Raw DEMs are not silently converted into an arbitrary
    terrain feature because that could change the Phase 19
    feature semantics.
    """

    if not TERRAIN_DIR.exists():
        return {}, []

    derived = {}
    used = []

    for path in TERRAIN_DIR.rglob("*"):

        if not path.is_file():
            continue

        if path.suffix.lower() not in {
            ".tif",
            ".tiff",
            ".vrt",
        }:
            continue

        name = path.stem.lower()

        if (
            "slope" in name
            and "mean_slope_deg" not in derived
        ):
            try:
                import rasterio

                with rasterio.open(path) as src:
                    data = src.read(
                        1,
                        masked=True,
                    )

                    values = np.asarray(
                        data.compressed(),
                        dtype=float,
                    )

                    values = values[
                        np.isfinite(values)
                    ]

                    if values.size:
                        derived[
                            "mean_slope_deg"
                        ] = float(
                            values.mean()
                        )
                        used.append(
                            str(path)
                        )
            except Exception:
                pass

        elif (
            (
                "elevation_range_ratio" in name
                or "elev_range_ratio" in name
                or "range_ratio" in name
            )
            and "elevation_range_ratio" not in derived
        ):
            try:
                import rasterio

                with rasterio.open(path) as src:
                    data = src.read(
                        1,
                        masked=True,
                    )

                    values = np.asarray(
                        data.compressed(),
                        dtype=float,
                    )

                    values = values[
                        np.isfinite(values)
                    ]

                    if values.size:
                        derived[
                            "elevation_range_ratio"
                        ] = float(
                            values.mean()
                        )
                        used.append(
                            str(path)
                        )
            except Exception:
                pass

        elif (
            (
                "min_elevation" in name
                or "elevation_min" in name
                or name.startswith("min_elev")
            )
            and "min_elevation_m" not in derived
        ):
            try:
                import rasterio

                with rasterio.open(path) as src:
                    data = src.read(
                        1,
                        masked=True,
                    )

                    values = np.asarray(
                        data.compressed(),
                        dtype=float,
                    )

                    values = values[
                        np.isfinite(values)
                    ]

                    if values.size:
                        derived[
                            "min_elevation_m"
                        ] = float(
                            values.min()
                        )
                        used.append(
                            str(path)
                        )
            except Exception:
                pass

    return derived, used


def derive_terrain_runtime(
    state,
    inference_df=None,
    basin_id=None,
):
    """
    Production terrain resolver.

    Priority:

    1. Valid terrain values already in the selected state row.
    2. Basin-specific processed terrain tables.
    3. Other rows for the same basin.
    4. Explicit processed terrain rasters.

    No training median is used here.
    """

    desired = [
        "mean_slope_deg",
        "elevation_range_ratio",
        "min_elevation_m",
    ]

    result = {}
    sources = []

    row = state.get(
        "row"
    )

    if row is not None:

        for feature in desired:

            if feature not in row.index:
                continue

            value = _phase21_numeric(
                row[feature]
            )

            if value is not None:
                result[feature] = value
                sources.append(
                    "state_row"
                )

    if len(result) < len(desired):

        table_values, table_sources = (
            _phase21_terrain_from_tables(
                basin_id
            )
        )

        for feature, value in table_values.items():

            if feature not in result:
                result[feature] = value
                sources.extend(
                    table_sources
                )

    if (
        len(result) < len(desired)
        and inference_df is not None
    ):

        history_values, history_sources = (
            _phase21_terrain_from_state_history(
                inference_df,
                basin_id,
            )
        )

        for feature, value in history_values.items():

            if feature not in result:
                result[feature] = value
                sources.extend(
                    history_sources
                )

    if len(result) < len(desired):

        raster_values, raster_sources = (
            _phase21_terrain_from_rasters(
                basin_id
            )
        )

        for feature, value in raster_values.items():

            if feature not in result:
                result[feature] = value
                sources.extend(
                    raster_sources
                )

    return {
        feature: result[feature]
        for feature in desired
        if feature in result
    }, sorted(set(sources))


'''

    text = text.replace(
        marker,
        runtime_block + "\n" + marker,
        1,
    )

    old_call = '''    terrain = derive_terrain_from_existing_state(
        state
    )
'''

    new_call = '''    terrain, terrain_sources = derive_terrain_runtime(
        state,
        inference_df=inference_df,
        basin_id=basin_id,
    )
'''

    if old_call not in text:
        raise RuntimeError(
            "Could not find the existing terrain call."
        )

    text = text.replace(
        old_call,
        new_call,
        1,
    )

    old_result = '''        "terrain": {
            "derived": sorted(
                terrain.keys()
            ),
            "dem_files_used": [],
            "dem_feature_derivation": (
                "state_feature_available"
                if terrain
                else "unavailable"
            ),
        },
'''

    new_result = '''        "terrain": {
            "derived": sorted(
                terrain.keys()
            ),
            "dem_files_used": terrain_sources,
            "dem_feature_derivation": (
                "runtime_terrain_resolver"
                if terrain
                else "unavailable"
            ),
        },
'''

    if old_result not in text:
        raise RuntimeError(
            "Could not find terrain result block."
        )

    text = text.replace(
        old_result,
        new_result,
        1,
    )

    API_PATH.write_text(
        text,
        encoding="utf-8",
    )

    print()
    print("=" * 110)
    print("CHETAKAI V1 — PHASE 21 TERRAIN RUNTIME REPAIR")
    print("=" * 110)
    print()
    print(f"API backup : {backup}")
    print(f"API updated: {API_PATH}")
    print()
    print("Runtime terrain resolver installed.")
    print()
    print("Priority:")
    print("  1. Selected basin state")
    print("  2. Basin terrain table")
    print("  3. Basin state history")
    print("  4. Explicit processed terrain rasters")
    print()
    print("Median imputation remains disabled in strict mode.")
    print()
    print("REPAIR: PASS")
    print("=" * 110)


def main():
    if not API_PATH.exists():
        raise FileNotFoundError(
            API_PATH
        )

    inject_runtime_resolver()

    print()
    print("Next validation commands:")
    print()
    print(
        r"python scripts\phase21_preflight_validator.py --strict"
    )
    print()
    print(
        r"python scripts\phase21_production_risk_api.py --lat 25.1234 --lon 86.5678 --strict"
    )


if __name__ == "__main__":
    main()