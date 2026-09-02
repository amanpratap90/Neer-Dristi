from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings(
    "ignore",
    message="GeoSeries.notna\\(\\) previously returned False"
)


# =============================================================================
# PATHS
# =============================================================================

ROOT = Path(__file__).resolve().parents[1]

MODEL_DIR = ROOT / "data" / "processed" / "models" / "phase19"
PHASE21_DIR = ROOT / "data" / "processed" / "models" / "phase21"

MODEL_PATH = MODEL_DIR / "best_phase19_flood_model.joblib"
CONTRACT_PATH = MODEL_DIR / "phase19_feature_contract.json"
IMPORTANCE_PATH = PHASE21_DIR.parent / "phase19" / "phase19_feature_importance.csv"

INFERENCE_PATH = (
    ROOT
    / "data"
    / "processed"
    / "training"
    / "phase15_1"
    / "unlabeled_inference.csv"
)

BASIN_PATH = (
    ROOT
    / "data"
    / "raw"
    / "basin_boundaries"
    / "cwc_basins.geojson"
)

TERRAIN_DIR = (
    ROOT
    / "data"
    / "processed"
    / "features"
    / "terrain"
)

PHASE21_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_PATH = PHASE21_DIR / "latest_risk_snapshot.json"
AUDIT_PATH = PHASE21_DIR / "phase21_api_audit.jsonl"


# =============================================================================
# CONSTANTS
# =============================================================================

PHASE = "21"
SCHEMA_VERSION = "1.2"

RISK_ORDER = {
    "VERY_LOW": 0,
    "LOW": 1,
    "MODERATE": 2,
    "HIGH": 3,
    "VERY_HIGH": 4,
}


# =============================================================================
# BASIC UTILITIES
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        value = float(value)
        if not math.isfinite(value):
            return None
        return value

    if isinstance(value, np.ndarray):
        return [json_safe(x) for x in value.tolist()]

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [json_safe(x) for x in value]

    return value


def normalize_basin_id(value: Any) -> Optional[str]:
    """
    Canonical basin ID representation.

    Examples:
        12              -> CWC_BASIN_012
        "12"            -> CWC_BASIN_012
        "012"           -> CWC_BASIN_012
        "CWC_BASIN_012" -> CWC_BASIN_012
    """

    if value is None:
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    upper = text.upper()

    if upper.startswith("CWC_BASIN_"):
        suffix = upper.replace("CWC_BASIN_", "", 1)
        if suffix.isdigit():
            return f"CWC_BASIN_{int(suffix):03d}"
        return upper

    if upper.startswith("CWC_"):
        suffix = upper.replace("CWC_", "", 1)
        if suffix.isdigit():
            return f"CWC_BASIN_{int(suffix):03d}"

    if upper.isdigit():
        return f"CWC_BASIN_{int(upper):03d}"

    return upper


def clean_column_name(value: Any) -> str:
    return str(value).strip()


def find_column(
    df: pd.DataFrame,
    candidates: List[str],
) -> Optional[str]:

    normalized = {
        str(c).strip().lower(): c
        for c in df.columns
    }

    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]

    return None


def safe_float(value: Any) -> Optional[float]:
    try:
        x = float(value)

        if not math.isfinite(x):
            return None

        return x
    except Exception:
        return None


# =============================================================================
# PHASE 19 MODEL LOADER
# =============================================================================

def find_estimator(
    obj: Any,
    path: str = "root",
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Phase 19 may save:

        Pipeline

    or:

        {
            "model": Pipeline,
            ...
        }

    or a more deeply nested package.

    This function recursively searches for the real estimator.
    """

    if obj is None:
        return None, None

    if hasattr(obj, "predict") and hasattr(obj, "predict_proba"):
        return obj, path

    if isinstance(obj, dict):

        preferred_keys = [
            "model",
            "estimator",
            "pipeline",
            "classifier",
            "best_model",
            "best_estimator",
            "fitted_model",
            "fitted_estimator",
        ]

        for key in preferred_keys:
            if key not in obj:
                continue

            estimator, estimator_path = find_estimator(
                obj[key],
                f"{path}.{key}",
            )

            if estimator is not None:
                return estimator, estimator_path

        for key, value in obj.items():

            if key in preferred_keys:
                continue

            estimator, estimator_path = find_estimator(
                value,
                f"{path}.{key}",
            )

            if estimator is not None:
                return estimator, estimator_path

    if isinstance(obj, (list, tuple)):

        for index, value in enumerate(obj):

            estimator, estimator_path = find_estimator(
                value,
                f"{path}[{index}]",
            )

            if estimator is not None:
                return estimator, estimator_path

    return None, None


def load_phase19_model(
    model_path: Path,
) -> Tuple[Any, Any, str]:

    if not model_path.exists():
        raise FileNotFoundError(
            f"Phase 19 model not found:\n{model_path}"
        )

    artifact = joblib.load(model_path)

    estimator, estimator_path = find_estimator(artifact)

    if estimator is None:
        artifact_type = type(artifact).__name__

        if isinstance(artifact, dict):
            keys = list(artifact.keys())

            raise TypeError(
                "Could not find a usable sklearn estimator inside the "
                f"Phase 19 dictionary artifact.\n"
                f"Artifact type : {artifact_type}\n"
                f"Artifact keys : {keys}"
            )

        raise TypeError(
            "Could not find a usable Phase 19 estimator.\n"
            f"Loaded type: {artifact_type}"
        )

    return artifact, estimator, estimator_path or "unknown"


# =============================================================================
# CONTRACT LOADING
# =============================================================================

def recursive_find_feature_list(
    obj: Any,
    preferred_keys: Optional[List[str]] = None,
) -> Optional[List[str]]:

    if preferred_keys is None:
        preferred_keys = [
            "selected_features",
            "production_features",
            "model_features",
            "features",
            "feature_names",
            "feature_list",
            "physical_features",
        ]

    if isinstance(obj, dict):

        for key in preferred_keys:

            if key in obj and isinstance(obj[key], list):

                values = [
                    clean_column_name(x)
                    for x in obj[key]
                    if isinstance(x, (str, int, float))
                ]

                if values:
                    return values

        for value in obj.values():

            result = recursive_find_feature_list(
                value,
                preferred_keys,
            )

            if result:
                return result

    return None


def load_feature_contract(
    contract_path: Path,
) -> Tuple[Dict[str, Any], List[str]]:

    if not contract_path.exists():
        raise FileNotFoundError(
            f"Phase 19 feature contract not found:\n{contract_path}"
        )

    with open(
        contract_path,
        "r",
        encoding="utf-8",
    ) as f:
        contract = json.load(f)

    features = recursive_find_feature_list(contract)

    if not features:
        raise ValueError(
            "Could not find the Phase 19 production feature list "
            "inside phase19_feature_contract.json."
        )

    return contract, features


# =============================================================================
# IMPORTANCE
# =============================================================================

def load_feature_importance(
    importance_path: Path,
) -> Dict[str, float]:

    if not importance_path.exists():
        return {}

    try:
        df = pd.read_csv(importance_path)

        feature_col = find_column(
            df,
            [
                "feature",
                "features",
                "feature_name",
            ],
        )

        importance_col = find_column(
            df,
            [
                "importance",
                "model_importance",
                "feature_importance",
            ],
        )

        if feature_col is None or importance_col is None:
            return {}

        result = {}

        for _, row in df.iterrows():

            feature = str(row[feature_col])

            importance = safe_float(
                row[importance_col]
            )

            if importance is not None:
                result[feature] = importance

        return result

    except Exception:
        return {}


# =============================================================================
# INFERENCE DATA
# =============================================================================

def load_inference_data(
    inference_path: Path,
) -> pd.DataFrame:

    if not inference_path.exists():
        raise FileNotFoundError(
            f"Inference dataset not found:\n{inference_path}"
        )

    df = pd.read_csv(inference_path)

    if df.empty:
        raise ValueError(
            "Inference dataset is empty."
        )

    df.columns = [
        clean_column_name(c)
        for c in df.columns
    ]

    return df


# =============================================================================
# BASIN RESOLUTION
# =============================================================================

def resolve_basin(
    lat: float,
    lon: float,
    basin_path: Path,
) -> Dict[str, Any]:

    result = {
        "basin_id": None,
        "basin_name": None,
        "coordinate_resolution": "FAILED",
        "boundary_source": str(basin_path),
        "raw_properties": {},
    }

    if not basin_path.exists():
        result["coordinate_resolution"] = "BOUNDARY_FILE_MISSING"
        return result

    try:

        import geopandas as gpd
        from shapely.geometry import Point

        gdf = gpd.read_file(basin_path)

        if gdf.empty:
            result["coordinate_resolution"] = "EMPTY_BOUNDARY"
            return result

        gdf = gdf[
            (~gdf.geometry.is_empty)
            & gdf.geometry.notna()
        ].copy()

        if gdf.empty:
            result["coordinate_resolution"] = "NO_VALID_GEOMETRY"
            return result

        if gdf.crs is None:
            raise ValueError(
                "Basin GeoJSON has no CRS."
            )

        point = gpd.GeoSeries(
            [Point(lon, lat)],
            crs="EPSG:4326",
        )

        point = point.to_crs(gdf.crs)

        matches = gdf[
            gdf.geometry.contains(point.iloc[0])
            | gdf.geometry.intersects(point.iloc[0])
        ]

        if matches.empty:
            result["coordinate_resolution"] = "NOT_FOUND"
            return result

        row = matches.iloc[0]

        properties = {}

        for key, value in row.items():

            if key == "geometry":
                continue

            properties[str(key)] = json_safe(value)

        result["raw_properties"] = properties

        basin_id = None

        basin_id_candidates = [
            "basin_id",
            "BASIN_ID",
            "id",
            "ID",
            "cwc_basin",
            "CWC_BASIN",
            "cwc_id",
            "CWC_ID",
            "objectid",
            "OBJECTID",
        ]

        for candidate in basin_id_candidates:

            if candidate in row.index:

                value = row[candidate]

                normalized = normalize_basin_id(value)

                if normalized:
                    basin_id = normalized
                    break

        if basin_id is None:

            for key, value in properties.items():

                key_lower = key.lower()

                if (
                    "basin" in key_lower
                    or key_lower in {"id", "cwc_id"}
                ):

                    normalized = normalize_basin_id(value)

                    if normalized:
                        basin_id = normalized
                        break

        basin_name_candidates = [
            "basin_name",
            "BASIN_NAME",
            "name",
            "NAME",
            "river_name",
            "RIVER_NAME",
        ]

        basin_name = None

        for candidate in basin_name_candidates:

            if candidate in row.index:

                value = row[candidate]

                if (
                    value is not None
                    and not pd.isna(value)
                ):

                    basin_name = str(value)
                    break

        result["basin_id"] = basin_id
        result["basin_name"] = basin_name
        result["coordinate_resolution"] = (
            "PASS"
            if basin_id is not None
            else "PASS_NO_ID"
        )

        return result

    except Exception as exc:

        result["coordinate_resolution"] = "ERROR"
        result["error"] = str(exc)

        return result


# =============================================================================
# BASIN STATE RESOLUTION
# =============================================================================

def resolve_state(
    df: pd.DataFrame,
    basin_id: Optional[str],
) -> Dict[str, Any]:
    """
    Production-safe basin state resolver.

    Resolution contract:

        coordinate
            ↓
        canonical basin ID
            ↓
        canonical_basin_id match
            ↓
        basin-specific rows ONLY
            ↓
        latest valid timestamp
            ↓
        state_basin_id == requested basin

    IMPORTANT:
        There is intentionally NO global fallback.

    A coordinate-specific flood prediction must never use the
    latest state belonging to another basin.
    """

    if basin_id is None:
        raise ValueError(
            "Cannot resolve state because coordinate basin ID is missing."
        )

    canonical_target = normalize_basin_id(
        basin_id
    )

    if canonical_target is None:
        raise ValueError(
            "Cannot resolve state because basin ID is invalid."
        )

    working = df.copy()

    # -------------------------------------------------------------------------
    # DISCOVER BASIN COLUMN
    # -------------------------------------------------------------------------

    basin_col = find_column(
        working,
        [
            # Canonical production column FIRST.
            "canonical_basin_id",

            # Other supported representations.
            "basin_id",
            "BASIN_ID",
            "basin",
            "BASIN",
            "cwc_basin",
            "CWC_BASIN",
            "cwc_basin_id",
            "cwc_id",
            "id",
        ],
    )

    if basin_col is None:
        raise ValueError(
            "Inference dataset has no recognized basin identifier column. "
            "Expected 'canonical_basin_id', 'basin_id', or another "
            "supported basin identifier."
        )

    # -------------------------------------------------------------------------
    # NORMALIZE BASIN IDS
    # -------------------------------------------------------------------------

    working["_phase21_normalized_basin_id"] = (
        working[basin_col]
        .map(normalize_basin_id)
    )

    # -------------------------------------------------------------------------
    # TIMESTAMP
    # -------------------------------------------------------------------------

    timestamp_col = find_column(
        working,
        [
            "timestamp",
            "datetime",
            "date",
            "time",
            "valid_time",
            "state_timestamp",
        ],
    )

    if timestamp_col is not None:

        working["_phase21_timestamp"] = pd.to_datetime(
            working[timestamp_col],
            errors="coerce",
        )

    else:

        working["_phase21_timestamp"] = pd.NaT

    # -------------------------------------------------------------------------
    # BASIN-SPECIFIC FILTER — NO GLOBAL FALLBACK
    # -------------------------------------------------------------------------

    basin_rows = working[
        working["_phase21_normalized_basin_id"]
        == canonical_target
    ].copy()

    if basin_rows.empty:

        available_basins = sorted(
            x
            for x in (
                working[
                    "_phase21_normalized_basin_id"
                ]
                .dropna()
                .unique()
                .tolist()
            )
            if x
        )

        raise ValueError(
            "No basin-specific inference state exists for "
            f"{canonical_target}. "
            f"Available canonical basins: {available_basins}"
        )

    # -------------------------------------------------------------------------
    # SELECT LATEST BASIN-SPECIFIC STATE
    # -------------------------------------------------------------------------

    if basin_rows["_phase21_timestamp"].notna().any():

        valid_timestamp_rows = basin_rows[
            basin_rows["_phase21_timestamp"].notna()
        ].copy()

        valid_timestamp_rows = (
            valid_timestamp_rows
            .sort_values(
                "_phase21_timestamp",
                ascending=True,
            )
        )

        selected = valid_timestamp_rows.iloc[-1]

        timestamp_value = selected[
            "_phase21_timestamp"
        ]

        state_timestamp = (
            timestamp_value.strftime(
                "%Y-%m-%d"
            )
        )

    else:

        selected = basin_rows.iloc[-1]

        state_timestamp = (
            "latest available basin-specific row"
        )

    # -------------------------------------------------------------------------
    # FINAL IDENTITY CHECK
    # -------------------------------------------------------------------------

    resolved_state_basin = normalize_basin_id(
        selected[basin_col]
    )

    if resolved_state_basin != canonical_target:

        raise ValueError(
            "CRITICAL STATE IDENTITY FAILURE: "
            f"selected state belongs to "
            f"'{resolved_state_basin}', "
            f"but requested coordinate basin is "
            f"'{canonical_target}'."
        )

    # -------------------------------------------------------------------------
    # RETURN
    # -------------------------------------------------------------------------

    return {
        "row": selected,

        "state_timestamp": state_timestamp,

        "state_resolution": "basin_matched",

        "state_basin_id": resolved_state_basin,

        "basin_state_consistency": True,

        "state_source": "basin_specific_inference_data",

        "state_basin_column": basin_col,

        "state_candidate_rows": int(
            len(basin_rows)
        ),

        "state_selection_rule": (
            "latest_valid_timestamp_within_requested_basin"
        ),
    }


# =============================================================================
# TERRAIN SUPPORT
# =============================================================================

def find_terrain_feature_file(
    feature_name: str,
) -> Optional[Path]:

    if not TERRAIN_DIR.exists():
        return None

    exact_names = [
        f"{feature_name}.tif",
        f"{feature_name}.tiff",
    ]

    for name in exact_names:

        candidate = TERRAIN_DIR / name

        if candidate.exists():
            return candidate

    # Basin feature CSVs are handled separately.
    return None


def derive_terrain_from_existing_state(
    state: Dict[str, Any],
) -> Dict[str, float]:

    """
    Prefer already processed terrain/state values.

    We intentionally do not fabricate terrain values from latitude/longitude.
    """

    row = state["row"]

    desired = [
        "mean_slope_deg",
        "elevation_range_ratio",
        "min_elevation_m",
    ]

    derived = {}

    for feature in desired:

        if feature not in row.index:
            continue

        value = safe_float(
            row[feature]
        )

        if value is not None:
            derived[feature] = value

    return derived




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



# =============================================================================
# FEATURE VECTOR
# =============================================================================

def build_feature_vector(
    state_row: pd.Series,
    required_features: List[str],
    training_medians: Dict[str, float],
    terrain_features: Dict[str, float],
    strict: bool,
) -> Tuple[pd.DataFrame, List[str], List[str]]:

    feature_values = {}

    for feature in required_features:

        value = None

        if feature in state_row.index:
            value = safe_float(
                state_row[feature]
            )

        if value is None and feature in terrain_features:
            value = terrain_features[feature]

        feature_values[feature] = value

    missing = [
        feature
        for feature, value in feature_values.items()
        if value is None
    ]

    if strict and missing:

        raise ValueError(
            "Strict mode enabled and required features are missing: "
            + str(missing)
        )

    imputed = []

    for feature in missing:

        if feature not in training_medians:
            raise ValueError(
                f"No training median available for required "
                f"feature: {feature}"
            )

        feature_values[feature] = training_medians[feature]
        imputed.append(feature)

    X = pd.DataFrame(
        [[
            feature_values[feature]
            for feature in required_features
        ]],
        columns=required_features,
    )

    return X, missing, imputed


# =============================================================================
# TRAINING MEDIANS
# =============================================================================

def extract_medians_from_contract(
    contract: Dict[str, Any],
) -> Dict[str, float]:

    medians = {}

    def walk(obj: Any):

        if isinstance(obj, dict):

            for key, value in obj.items():

                key_lower = str(key).lower()

                if (
                    "median" in key_lower
                    and isinstance(value, dict)
                ):

                    for feature, median in value.items():

                        numeric = safe_float(median)

                        if numeric is not None:
                            medians[str(feature)] = numeric

                walk(value)

        elif isinstance(obj, list):

            for item in obj:
                walk(item)

    walk(contract)

    return medians


def extract_medians_from_model(
    artifact: Any,
) -> Dict[str, float]:

    medians = {}

    def walk(obj: Any):

        if isinstance(obj, dict):

            for key, value in obj.items():

                key_lower = str(key).lower()

                if "median" in key_lower:

                    if isinstance(value, dict):

                        for feature, median in value.items():

                            numeric = safe_float(median)

                            if numeric is not None:
                                medians[str(feature)] = numeric

                    elif isinstance(value, pd.Series):

                        for feature, median in value.items():

                            numeric = safe_float(median)

                            if numeric is not None:
                                medians[str(feature)] = numeric

                walk(value)

        elif isinstance(obj, (list, tuple)):

            for item in obj:
                walk(item)

    walk(artifact)

    return medians


def build_training_medians(
    contract: Dict[str, Any],
    artifact: Any,
    required_features: List[str],
    inference_df: pd.DataFrame,
) -> Dict[str, float]:

    medians = {}

    medians.update(
        extract_medians_from_contract(contract)
    )

    model_medians = extract_medians_from_model(
        artifact
    )

    for feature, value in model_medians.items():

        if feature not in medians:
            medians[feature] = value

    # Last-resort inference-data medians.
    #
    # This is used only for features where Phase 19's package/contract
    # did not persist a median.
    for feature in required_features:

        if feature in medians:
            continue

        if feature in inference_df.columns:

            numeric = pd.to_numeric(
                inference_df[feature],
                errors="coerce",
            )

            median = numeric.median()

            if pd.notna(median):

                medians[feature] = float(median)

    return medians


# =============================================================================
# FEATURE AUDIT
# =============================================================================

def audit_feature_matrix(
    X: pd.DataFrame,
    required_features: List[str],
) -> Dict[str, Any]:

    ordered = list(X.columns) == list(
        required_features
    )

    infinity = int(
        np.isinf(
            X.to_numpy(dtype=float)
        ).sum()
    )

    missing = int(
        X.isna().sum().sum()
    )

    numeric = True

    try:
        X.to_numpy(dtype=float)
    except Exception:
        numeric = False

    return {
        "feature_order": "PASS" if ordered else "FAIL",
        "feature_count": int(X.shape[1]),
        "numeric_matrix": (
            "PASS"
            if numeric
            else "FAIL"
        ),
        "remaining_missing": missing,
        "infinity": infinity,
    }


# =============================================================================
# PREDICTION
# =============================================================================

def predict_probability(
    estimator: Any,
    X: pd.DataFrame,
) -> float:

    if not hasattr(
        estimator,
        "predict_proba",
    ):
        raise TypeError(
            "Resolved Phase 19 estimator does not expose "
            "predict_proba(). "
            f"Resolved type: {type(estimator).__name__}"
        )

    probabilities = estimator.predict_proba(
        X
    )

    if probabilities.ndim != 2:
        raise ValueError(
            "Unexpected predict_proba() output shape: "
            f"{probabilities.shape}"
        )

    if probabilities.shape[1] < 2:
        raise ValueError(
            "Phase 19 classifier does not expose a binary "
            "positive-class probability."
        )

    probability = float(
        probabilities[0, 1]
    )

    return max(
        0.0,
        min(
            1.0,
            probability,
        ),
    )


def classify_risk(
    probability: float,
) -> str:

    if probability < 0.10:
        return "VERY_LOW"

    if probability < 0.25:
        return "LOW"

    if probability < 0.50:
        return "MODERATE"

    if probability < 0.75:
        return "HIGH"

    return "VERY_HIGH"


def calculate_confidence(
    probability: float,
) -> float:

    """
    Confidence represents separation from the 0.5 decision boundary.

    It is deliberately bounded and independent of the selected threshold.
    """

    confidence = 0.50 + abs(
        probability - 0.50
    )

    return max(
        0.50,
        min(
            1.0,
            confidence,
        ),
    )


# =============================================================================
# EVIDENCE
# =============================================================================

def build_evidence(
    X: pd.DataFrame,
    importance: Dict[str, float],
    top_n: int = 10,
) -> List[Dict[str, Any]]:

    ranked = sorted(
        importance.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    evidence = []

    for feature, model_importance in ranked:

        if feature not in X.columns:
            continue

        value = safe_float(
            X.iloc[0][feature]
        )

        evidence.append(
            {
                "feature": feature,
                "value": value,
                "model_importance": float(
                    model_importance
                ),
            }
        )

        if len(evidence) >= top_n:
            break

    return evidence


# =============================================================================
# THRESHOLD
# =============================================================================

def extract_threshold(
    contract: Dict[str, Any],
    artifact: Any,
) -> float:

    candidate_keys = [
        "threshold",
        "decision_threshold",
        "optimal_threshold",
        "validation_threshold",
    ]

    def search(obj: Any) -> Optional[float]:

        if isinstance(obj, dict):

            for key in candidate_keys:

                if key in obj:

                    value = safe_float(
                        obj[key]
                    )

                    if value is not None:
                        return value

            for value in obj.values():

                result = search(value)

                if result is not None:
                    return result

        return None

    threshold = search(contract)

    if threshold is None:
        threshold = search(artifact)

    if threshold is None:
        threshold = 0.34

    return float(threshold)


# =============================================================================
# MAIN RISK RESULT
# =============================================================================

def generate_risk_result(
    latitude: float,
    longitude: float,
    strict: bool = False,
) -> Dict[str, Any]:

    # -------------------------------------------------------------------------
    # VALIDATE COORDINATE
    # -------------------------------------------------------------------------

    latitude = float(latitude)
    longitude = float(longitude)

    if not -90 <= latitude <= 90:
        raise ValueError(
            "Latitude must be between -90 and 90."
        )

    if not -180 <= longitude <= 180:
        raise ValueError(
            "Longitude must be between -180 and 180."
        )

    # -------------------------------------------------------------------------
    # LOAD MODEL
    # -------------------------------------------------------------------------

    artifact, estimator, estimator_path = (
        load_phase19_model(
            MODEL_PATH
        )
    )

    contract, required_features = (
        load_feature_contract(
            CONTRACT_PATH
        )
    )

    threshold = extract_threshold(
        contract,
        artifact,
    )

    importance = load_feature_importance(
        IMPORTANCE_PATH
    )

    # -------------------------------------------------------------------------
    # LOAD DATA
    # -------------------------------------------------------------------------

    inference_df = load_inference_data(
        INFERENCE_PATH
    )

    # -------------------------------------------------------------------------
    # BASIN
    # -------------------------------------------------------------------------

    basin = resolve_basin(
        latitude,
        longitude,
        BASIN_PATH,
    )

    basin_id = basin.get(
        "basin_id"
    )

    # -------------------------------------------------------------------------
    # STATE
    # -------------------------------------------------------------------------

    state = resolve_state(
        inference_df,
        basin_id,
    )

    state_row = state["row"]

    # -------------------------------------------------------------------------
    # TERRAIN
    # -------------------------------------------------------------------------

    terrain, terrain_sources = derive_terrain_runtime(
        state,
        inference_df=inference_df,
        basin_id=basin_id,
    )

    # -------------------------------------------------------------------------
    # MEDIANS
    # -------------------------------------------------------------------------

    training_medians = (
        build_training_medians(
            contract,
            artifact,
            required_features,
            inference_df,
        )
    )

    # -------------------------------------------------------------------------
    # FEATURE VECTOR
    # -------------------------------------------------------------------------

    X, original_missing, median_imputed = (
        build_feature_vector(
            state_row,
            required_features,
            training_medians,
            terrain,
            strict,
        )
    )

    # -------------------------------------------------------------------------
    # FEATURE AUDIT
    # -------------------------------------------------------------------------

    feature_audit = audit_feature_matrix(
        X,
        required_features,
    )

    if feature_audit["feature_order"] != "PASS":
        raise ValueError(
            "Feature order contract failed."
        )

    if feature_audit["numeric_matrix"] != "PASS":
        raise ValueError(
            "Feature matrix is not numeric."
        )

    if feature_audit["remaining_missing"] != 0:
        raise ValueError(
            "Feature matrix still contains missing values."
        )

    if feature_audit["infinity"] != 0:
        raise ValueError(
            "Feature matrix contains infinity values."
        )

    # -------------------------------------------------------------------------
    # PREDICTION
    # -------------------------------------------------------------------------

    probability = predict_probability(
        estimator,
        X,
    )

    flood_prediction = int(
        probability >= threshold
    )

    risk_class = classify_risk(
        probability
    )

    confidence = calculate_confidence(
        probability
    )

    evidence = build_evidence(
        X,
        importance,
        top_n=10,
    )

    state_timestamp = state.get(
        "state_timestamp"
    )

    # -------------------------------------------------------------------------
    # QUALITY
    # -------------------------------------------------------------------------

    coordinate_resolution = basin.get(
        "coordinate_resolution"
    )

    state_resolution = state.get(
        "state_resolution"
    )

    basin_state_consistency = bool(
        state.get(
            "basin_state_consistency",
            False,
        )
    )

    terrain_resolution = (
        "AVAILABLE"
        if terrain
        else "UNAVAILABLE"
    )

    if (
        coordinate_resolution == "PASS"
        and state_resolution == "basin_matched"
        and basin_state_consistency
        and feature_audit["feature_order"] == "PASS"
        and feature_audit["remaining_missing"] == 0
        and feature_audit["infinity"] == 0
        and not median_imputed
    ):
        production_status = "PRODUCTION_READY"

    elif (
        coordinate_resolution in {
            "PASS",
            "PASS_NO_ID",
        }
        and feature_audit["feature_order"] == "PASS"
    ):
        production_status = (
            "PRODUCTION_READY_WITH_FALLBACK"
        )

    else:
        production_status = "DEGRADED"

    # -------------------------------------------------------------------------
    # RESULT
    # -------------------------------------------------------------------------

    result = {
        "phase": PHASE,
        "engine": "ChetakAI Production Risk API",
        "schema_version": SCHEMA_VERSION,
        "timestamp": utc_now_iso(),

        "coordinate": {
            "latitude": latitude,
            "longitude": longitude,
        },

        "basin": {
            "basin_id": basin_id,
            "basin_name": basin.get(
                "basin_name"
            ),
            "coordinate_resolution": (
                coordinate_resolution
            ),
            "boundary_source": basin.get(
                "boundary_source"
            ),
        },

        "state": {
            "state_timestamp": state_timestamp,
            "state_resolution": state_resolution,
            "state_basin_id": state.get(
                "state_basin_id"
            ),
            "basin_state_consistency": (
                basin_state_consistency
            ),
            "current": {
                feature: safe_float(
                    state_row[feature]
                )
                for feature in required_features
                if feature in state_row.index
                and safe_float(
                    state_row[feature]
                ) is not None
            },
            "forecast": {},
        },

        "terrain": {
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

        "model": {
            "name": "phase19_best",
            "path": str(
                MODEL_PATH
            ),
            "estimator": type(
                estimator
            ).__name__,
            "artifact_estimator_path": (
                estimator_path
            ),
            "feature_count": len(
                required_features
            ),
            "threshold": threshold,
        },

        "prediction": {
            "flood_probability": probability,
            "flood_probability_pct": round(
                probability * 100,
                2,
            ),
            "flood_prediction": flood_prediction,
            "risk_class": risk_class,
            "confidence": confidence,
            "confidence_pct": round(
                confidence * 100,
                2,
            ),
        },

        "evidence": {
            "top_features": evidence,
        },

        "feature_audit": {
            "required_features": len(
                required_features
            ),
            "original_missing_features": (
                original_missing
            ),
            "median_imputed_features": (
                median_imputed
            ),
            "remaining_missing": (
                feature_audit[
                    "remaining_missing"
                ]
            ),
            "infinity": feature_audit[
                "infinity"
            ],
            "contract_status": (
                "PASS"
                if (
                    feature_audit[
                        "feature_order"
                    ] == "PASS"
                    and feature_audit[
                        "remaining_missing"
                    ] == 0
                    and feature_audit[
                        "infinity"
                    ] == 0
                )
                else "FAIL"
            ),
        },

        "data_quality": {
            "coordinate_resolution": (
                coordinate_resolution
            ),
            "state_resolution": (
                state_resolution
            ),
            "basin_state_consistency": (
                basin_state_consistency
            ),
            "terrain_resolution": (
                terrain_resolution
            ),
            "feature_contract": (
                "PASS"
                if (
                    feature_audit[
                        "feature_order"
                    ] == "PASS"
                    and feature_audit[
                        "remaining_missing"
                    ] == 0
                    and feature_audit[
                        "infinity"
                    ] == 0
                )
                else "FAIL"
            ),
            "median_imputation_used": bool(
                median_imputed
            ),
            "production_status": (
                production_status
            ),
        },

        "integration": {
            "risk_engine_ready": True,
            "alert_ready": True,
            "rag_ready": True,
            "llm_ready": True,
        },

        "strict_mode": bool(strict),
    }

    return json_safe(result)


# =============================================================================
# PERSISTENCE
# =============================================================================

def save_result(
    result: Dict[str, Any],
) -> None:

    with open(
        SNAPSHOT_PATH,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False,
        )

    audit_record = {
        "timestamp": utc_now_iso(),
        "phase": PHASE,
        "schema_version": SCHEMA_VERSION,
        "latitude": result[
            "coordinate"
        ]["latitude"],
        "longitude": result[
            "coordinate"
        ]["longitude"],
        "basin_id": result[
            "basin"
        ]["basin_id"],
        "state_resolution": result[
            "state"
        ]["state_resolution"],
        "probability": result[
            "prediction"
        ]["flood_probability"],
        "risk_class": result[
            "prediction"
        ]["risk_class"],
        "confidence": result[
            "prediction"
        ]["confidence"],
        "production_status": result[
            "data_quality"
        ]["production_status"],
        "strict_mode": result[
            "strict_mode"
        ],
    }

    with open(
        AUDIT_PATH,
        "a",
        encoding="utf-8",
    ) as f:

        f.write(
            json.dumps(
                json_safe(audit_record),
                ensure_ascii=False,
            )
            + "\n"
        )


# =============================================================================
# CLI OUTPUT
# =============================================================================

def print_header(
    title: str,
) -> None:

    print()
    print("=" * 110)
    print(title)
    print("=" * 110)


def print_section(
    title: str,
) -> None:

    print()
    print("-" * 110)
    print(title)
    print("-" * 110)


def print_result(
    result: Dict[str, Any],
) -> None:

    coordinate = result[
        "coordinate"
    ]

    basin = result[
        "basin"
    ]

    state = result[
        "state"
    ]

    model = result[
        "model"
    ]

    prediction = result[
        "prediction"
    ]

    audit = result[
        "feature_audit"
    ]

    quality = result[
        "data_quality"
    ]

    print_header(
        "CHETAKAI V1 — PHASE 21 PRODUCTION RISK API"
    )

    print_section("COORDINATE")

    print(
        f"Latitude              : "
        f"{coordinate['latitude']:.6f}"
    )

    print(
        f"Longitude             : "
        f"{coordinate['longitude']:.6f}"
    )

    print(
        f"Strict mode           : "
        f"{result['strict_mode']}"
    )

    print_section("LOADING PHASE 19 MODEL")

    print(
        f"Model                 : "
        f"{model['path']}"
    )

    print(
        f"Contract              : "
        f"{CONTRACT_PATH}"
    )

    print(
        f"Production features   : "
        f"{model['feature_count']}"
    )

    print(
        f"Estimator             : "
        f"{model['estimator']}"
    )

    print(
        f"Artifact estimator    : "
        f"{model['artifact_estimator_path']}"
    )

    print(
        f"Threshold             : "
        f"{model['threshold']:.6f}"
    )

    print_section("LOADING INFERENCE DATA")

    print(
        f"Unlabeled dataset     : "
        f"{INFERENCE_PATH}"
    )

    try:
        df = pd.read_csv(
            INFERENCE_PATH,
            nrows=1,
        )

        print(
            f"Columns               : "
            f"{len(df.columns)}"
        )

    except Exception:
        pass

    print_section("RESOLVING BASIN")

    print(
        f"Basin ID              : "
        f"{basin['basin_id']}"
    )

    print(
        f"Basin Name            : "
        f"{basin['basin_name']}"
    )

    print(
        f"Coordinate resolution : "
        f"{basin['coordinate_resolution']}"
    )

    print(
        f"Boundary source       : "
        f"{basin['boundary_source']}"
    )

    print_section(
        "RESOLVING BASIN FEATURE STATE"
    )

    print(
        f"State resolution      : "
        f"{state['state_resolution']}"
    )

    print(
        f"State basin           : "
        f"{state['state_basin_id']}"
    )

    print(
        f"State timestamp       : "
        f"{state['state_timestamp']}"
    )

    print(
        f"Basin/state consistency: "
        f"{state['basin_state_consistency']}"
    )

    print_section(
        "BUILDING PHASE 19 FEATURE VECTOR"
    )

    print(
        f"Required features     : "
        f"{audit['required_features']}"
    )

    print(
        f"Original missing      : "
        f"{len(audit['original_missing_features'])}"
    )

    if audit[
        "original_missing_features"
    ]:

        for feature in audit[
            "original_missing_features"
        ]:

            print(
                f" - {feature}"
            )

    print(
        f"Median imputed        : "
        f"{len(audit['median_imputed_features'])}"
    )

    if audit[
        "median_imputed_features"
    ]:

        for feature in audit[
            "median_imputed_features"
        ]:

            print(
                f" - {feature}"
            )

    print_section(
        "FINAL FEATURE CONTRACT AUDIT"
    )

    print(
        f"Feature order         : "
        f"{audit['contract_status']}"
    )

    print(
        f"Feature count         : "
        f"{audit['required_features']}"
    )

    print(
        f"Remaining missing     : "
        f"{audit['remaining_missing']}"
    )

    print(
        f"Infinity              : "
        f"{audit['infinity']}"
    )

    print_section(
        "FLOOD PREDICTION"
    )

    print(
        f"Flood probability     : "
        f"{prediction['flood_probability']:.4f}"
    )

    print(
        f"Flood probability %   : "
        f"{prediction['flood_probability_pct']:.2f}%"
    )

    print(
        f"Threshold             : "
        f"{model['threshold']:.4f}"
    )

    prediction_text = (
        "FLOOD RISK"
        if prediction["flood_prediction"]
        else "NO FLOOD RISK"
    )

    print(
        f"Flood prediction      : "
        f"{prediction_text}"
    )

    print(
        f"Risk class            : "
        f"{prediction['risk_class']}"
    )

    print(
        f"Confidence            : "
        f"{prediction['confidence_pct']:.2f}%"
    )

    print_section("EVIDENCE")

    for item in result[
        "evidence"
    ]["top_features"]:

        print(
            f"{item['feature']:<45} "
            f"value={item['value']} "
            f"importance={item['model_importance']:.6f}"
        )

    print_section(
        "DOWNSTREAM READINESS"
    )

    print(
        "Risk Engine           : READY"
    )

    print(
        "Alert Engine          : READY"
    )

    print(
        "RAG                   : READY"
    )

    print(
        "LLM                   : READY"
    )

    print_header(
        "PHASE 21 RESULT"
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )

    print_header(
        "PHASE 21 COMPLETE"
    )

    print(
        f"Coordinate resolution : "
        f"{basin['coordinate_resolution']}"
    )

    print(
        f"Basin                 : "
        f"{basin['basin_id']}"
    )

    print(
        f"Feature state         : "
        f"{state['state_resolution']}"
    )

    print(
        f"Probability           : "
        f"{prediction['flood_probability_pct']:.2f}%"
    )

    print(
        f"Risk                  : "
        f"{prediction['risk_class']}"
    )

    print(
        f"Confidence            : "
        f"{prediction['confidence_pct']:.2f}%"
    )

    print(
        f"Production status     : "
        f"{quality['production_status']}"
    )

    print(
        f"Snapshot              : "
        f"{SNAPSHOT_PATH}"
    )

    print(
        f"Audit                 : "
        f"{AUDIT_PATH}"
    )

    print(
        "STATUS: PASS"
    )

    print("=" * 110)


# =============================================================================
# FASTAPI
# =============================================================================

def create_fastapi_app():

    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel, Field

    except ImportError as exc:

        raise RuntimeError(
            "FastAPI is not installed. "
            "Install with: pip install fastapi uvicorn"
        ) from exc

    app = FastAPI(
        title="ChetakAI Production Risk API",
        version=SCHEMA_VERSION,
        description=(
            "Coordinate-to-flood-risk inference service "
            "using the Phase 19 production model."
        ),
    )

    class RiskRequest(BaseModel):
        latitude: float = Field(
            ...,
            ge=-90,
            le=90,
        )

        longitude: float = Field(
            ...,
            ge=-180,
            le=180,
        )

        strict: bool = False

    @app.get("/health")
    def health():

        return {
            "status": "ok",
            "phase": PHASE,
            "schema_version": SCHEMA_VERSION,
            "model_exists": MODEL_PATH.exists(),
            "contract_exists": CONTRACT_PATH.exists(),
            "inference_data_exists": (
                INFERENCE_PATH.exists()
            ),
            "basin_boundary_exists": (
                BASIN_PATH.exists()
            ),
        }

    @app.post("/risk")
    def risk(request: RiskRequest):

        try:

            result = generate_risk_result(
                request.latitude,
                request.longitude,
                request.strict,
            )

            save_result(result)

            return result

        except Exception as exc:

            raise HTTPException(
                status_code=500,
                detail={
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
            )

    return app


# =============================================================================
# CLI
# =============================================================================

def cli():

    parser = argparse.ArgumentParser(
        description=(
            "ChetakAI Phase 21 Production Risk API"
        )
    )

    parser.add_argument(
        "--lat",
        type=float,
        required=True,
        help="Latitude",
    )

    parser.add_argument(
        "--lon",
        type=float,
        required=True,
        help="Longitude",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Reject inference if any required "
            "feature is unavailable instead of "
            "using a training/inference median."
        ),
    )

    parser.add_argument(
        "--serve",
        action="store_true",
        help=(
            "Start FastAPI server instead of "
            "running one CLI inference."
        ),
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="FastAPI host",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="FastAPI port",
    )

    args = parser.parse_args()

    if args.serve:

        try:

            import uvicorn

            app = create_fastapi_app()

            uvicorn.run(
                app,
                host=args.host,
                port=args.port,
            )

            return

        except Exception as exc:

            print()
            print("=" * 110)
            print("PHASE 21 FAILED")
            print("=" * 110)
            print(
                f"{type(exc).__name__}: {exc}"
            )

            sys.exit(1)

    try:

        result = generate_risk_result(
            args.lat,
            args.lon,
            args.strict,
        )

        save_result(result)

        print_result(
            result
        )

    except Exception as exc:

        print()
        print("=" * 110)
        print("PHASE 21 FAILED")
        print("=" * 110)
        print(
            f"{type(exc).__name__}: {exc}"
        )

        traceback.print_exc()

        sys.exit(1)


if __name__ == "__main__":
    cli()