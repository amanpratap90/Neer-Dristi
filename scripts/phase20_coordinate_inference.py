from __future__ import annotations

import argparse
import json
import re
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings(
    "ignore",
    message="GeoSeries.notna\\(\\) previously returned False",
    category=UserWarning,
)

try:
    import geopandas as gpd
    from shapely.geometry import Point
except Exception:
    gpd = None
    Point = None


BASE_DIR = Path(__file__).resolve().parents[1]

MODEL_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "models"
    / "phase19"
    / "best_phase19_flood_model.joblib"
)

CONTRACT_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "models"
    / "phase19"
    / "phase19_feature_contract.json"
)

INFERENCE_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "training"
    / "phase15_1"
    / "unlabeled_inference.csv"
)

BASIN_DIR = BASE_DIR / "data" / "raw" / "basin_boundaries"


def banner(title: str) -> None:
    print()
    print("=" * 110)
    print(title)
    print("=" * 110)


def section(title: str) -> None:
    print()
    print("-" * 110)
    print(title)
    print("-" * 110)


def normalize_basin_id(value: Any) -> Optional[str]:
    if value is None:
        return None

    if pd.isna(value):
        return None

    s = str(value).strip()

    if not s:
        return None

    s = s.upper()

    match = re.fullmatch(r"CWC[_\- ]?BASIN[_\- ]?0*(\d+)", s)

    if match:
        number = int(match.group(1))
        return f"CWC_BASIN_{number:03d}"

    if s.isdigit():
        return f"CWC_BASIN_{int(s):03d}"

    return s


def extract_feature_list(contract: Dict[str, Any]) -> List[str]:
    candidates = []

    def recursive_find(obj: Any, path: str = "root") -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_lower = str(key).lower()

                if isinstance(value, list) and all(
                    isinstance(x, str) for x in value
                ):
                    if any(
                        token in key_lower
                        for token in [
                            "feature",
                            "model_features",
                            "physical_features",
                            "selected_features",
                        ]
                    ):
                        candidates.append((path + "." + str(key), value))

                recursive_find(value, path + "." + str(key))

        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                recursive_find(value, path + f"[{i}]")

    recursive_find(contract)

    if not candidates:
        raise ValueError(
            "Could not find feature list in phase19_feature_contract.json"
        )

    priority = [
        "model_features",
        "production_features",
        "selected_features",
        "physical_features",
        "features",
    ]

    for priority_name in priority:
        for path, values in candidates:
            if path.lower().endswith(priority_name):
                return list(values)

    return list(candidates[0][1])


def load_contract() -> Tuple[List[str], Dict[str, Any]]:
    with open(CONTRACT_PATH, "r", encoding="utf-8") as f:
        contract = json.load(f)

    features = extract_feature_list(contract)

    if len(features) != 60:
        print(
            f"WARNING: Phase 19 contract contains {len(features)} features, "
            f"expected 60."
        )

    return features, contract


def load_model() -> Any:
    model = joblib.load(MODEL_PATH)

    if isinstance(model, dict):
        estimator_keys = [
            "model",
            "estimator",
            "pipeline",
            "best_model",
            "classifier",
        ]

        extracted = None

        for key in estimator_keys:
            if key in model:
                candidate = model[key]

                if hasattr(candidate, "predict_proba"):
                    extracted = candidate
                    break

        if extracted is None:
            for value in model.values():
                if hasattr(value, "predict_proba"):
                    extracted = value
                    break

        if extracted is None:
            raise TypeError(
                "Phase 19 artifact is a dictionary, but no estimator "
                "with predict_proba() was found."
            )

        model = extracted

    if not hasattr(model, "predict_proba"):
        raise TypeError(
            f"Loaded Phase 19 model does not support predict_proba(): "
            f"{type(model).__name__}"
        )

    return model


def find_boundary_files() -> List[Path]:
    if not BASIN_DIR.exists():
        return []

    extensions = {".shp", ".gpkg", ".geojson", ".json"}

    files = [
        p
        for p in BASIN_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in extensions
    ]

    return sorted(files)


def discover_basin_column(columns: List[str]) -> Optional[str]:
    preferred = [
        "canonical_basin_id",
        "basin_id",
        "BASIN_ID",
        "basin",
        "Basin_ID",
        "BASIN",
        "id",
        "ID",
        "name",
        "NAME",
    ]

    for col in preferred:
        if col in columns:
            return col

    lower_map = {str(c).lower(): c for c in columns}

    for key in [
        "canonical_basin_id",
        "basin_id",
        "basin",
        "basin_no",
        "basin_number",
        "id",
    ]:
        if key in lower_map:
            return lower_map[key]

    return None


def resolve_basin(
    lat: float,
    lon: float,
) -> Tuple[Optional[str], Optional[Any]]:
    if gpd is None or Point is None:
        return None, None

    files = find_boundary_files()

    if not files:
        return None, None

    point = gpd.GeoDataFrame(
        {"_id": [1]},
        geometry=[Point(lon, lat)],
        crs="EPSG:4326",
    )

    for path in files:
        try:
            gdf = gpd.read_file(path)

            if gdf.empty or gdf.geometry is None:
                continue

            basin_col = discover_basin_column(list(gdf.columns))

            if basin_col is None:
                continue

            if gdf.crs is None:
                continue

            point_local = point.to_crs(gdf.crs)

            valid = gdf[
                gdf.geometry.notna() & ~gdf.geometry.is_empty
            ].copy()

            if valid.empty:
                continue

            matches = valid[valid.geometry.contains(point_local.geometry.iloc[0])]

            if matches.empty:
                matches = valid[
                    valid.geometry.intersects(point_local.geometry.iloc[0])
                ]

            if matches.empty:
                continue

            row = matches.iloc[0]

            basin_id = normalize_basin_id(row[basin_col])

            if basin_id:
                return basin_id, row

        except Exception:
            continue

    return None, None


def discover_basin_column_in_data(
    df: pd.DataFrame,
) -> Optional[str]:
    return discover_basin_column(list(df.columns))


def discover_timestamp_column(
    df: pd.DataFrame,
) -> Optional[str]:
    candidates = [
        "timestamp",
        "datetime",
        "date",
        "time",
        "valid_time",
    ]

    lower_map = {str(c).lower(): c for c in df.columns}

    for candidate in candidates:
        if candidate in lower_map:
            return lower_map[candidate]

    return None


def prepare_inference_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:
    result = df.copy()

    basin_col = discover_basin_column_in_data(result)

    if basin_col:
        result["_normalized_basin_id"] = result[basin_col].apply(
            normalize_basin_id
        )
    else:
        result["_normalized_basin_id"] = None

    timestamp_col = discover_timestamp_column(result)

    if timestamp_col:
        result["_parsed_timestamp"] = pd.to_datetime(
            result[timestamp_col],
            errors="coerce",
        )
    else:
        result["_parsed_timestamp"] = pd.NaT

    return result


def select_basin_state(
    df: pd.DataFrame,
    basin_id: Optional[str],
) -> Tuple[pd.Series, str]:
    if basin_id is None:
        raise ValueError(
            "Cannot select a coordinate-specific feature state because "
            "the basin ID could not be resolved."
        )

    basin_rows = df[
        df["_normalized_basin_id"] == basin_id
    ].copy()

    if basin_rows.empty:
        raise ValueError(
            f"No inference feature state exists for basin {basin_id}."
        )

    timestamp_col = discover_timestamp_column(basin_rows)

    if timestamp_col:
        basin_rows = basin_rows.sort_values(
            "_parsed_timestamp",
            ascending=True,
            na_position="first",
        )

        selected = basin_rows.iloc[-1]

        timestamp_value = selected["_parsed_timestamp"]

        if pd.notna(timestamp_value):
            state_time = str(timestamp_value)
        else:
            state_time = str(selected[timestamp_col])
    else:
        selected = basin_rows.iloc[-1]
        state_time = "latest available row"

    return selected, state_time


def find_coordinate_state(
    df: pd.DataFrame,
    basin_id: str,
    lat: float,
    lon: float,
) -> Tuple[pd.Series, str]:
    """
    Prefer exact coordinate rows when latitude/longitude are available.
    Otherwise use the latest state belonging to the resolved basin.

    This prevents the old unsafe behavior of selecting a random/global
    basin state such as CWC_BASIN_025 for a coordinate located in
    CWC_BASIN_012.
    """

    latitude_candidates = [
        "lat",
        "latitude",
        "LAT",
        "Latitude",
    ]

    longitude_candidates = [
        "lon",
        "longitude",
        "LON",
        "Longitude",
    ]

    lat_col = next(
        (c for c in latitude_candidates if c in df.columns),
        None,
    )

    lon_col = next(
        (c for c in longitude_candidates if c in df.columns),
        None,
    )

    basin_rows = df[
        df["_normalized_basin_id"] == basin_id
    ].copy()

    if basin_rows.empty:
        raise ValueError(
            f"No inference rows found for resolved basin {basin_id}."
        )

    if lat_col and lon_col:
        lat_values = pd.to_numeric(
            basin_rows[lat_col],
            errors="coerce",
        )

        lon_values = pd.to_numeric(
            basin_rows[lon_col],
            errors="coerce",
        )

        valid = (
            lat_values.notna()
            & lon_values.notna()
        )

        coordinate_rows = basin_rows[valid].copy()

        if not coordinate_rows.empty:
            coordinate_rows["_distance"] = (
                (lat_values[valid] - lat) ** 2
                + (lon_values[valid] - lon) ** 2
            )

            coordinate_rows = coordinate_rows.sort_values(
                "_distance"
            )

            nearest = coordinate_rows.iloc[0]

            timestamp_value = nearest["_parsed_timestamp"]

            if pd.notna(timestamp_value):
                state_time = str(timestamp_value)
            else:
                state_time = "nearest coordinate state"

            return nearest, state_time

    return select_basin_state(df, basin_id)


def numeric_value(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        value = float(value)
    except Exception:
        return None

    if not np.isfinite(value):
        return None

    return value


def build_feature_vector(
    state: pd.Series,
    features: List[str],
) -> Tuple[pd.DataFrame, List[str]]:
    values: Dict[str, float] = {}
    missing: List[str] = []

    for feature in features:
        if feature not in state.index:
            values[feature] = np.nan
            missing.append(feature)
            continue

        value = numeric_value(state[feature])

        if value is None:
            values[feature] = np.nan
            missing.append(feature)
        else:
            values[feature] = value

    X = pd.DataFrame(
        [[values[f] for f in features]],
        columns=features,
    )

    return X, missing


def load_training_medians(
    features: List[str],
) -> pd.Series:
    candidates = [
        BASE_DIR
        / "data"
        / "processed"
        / "models"
        / "phase19"
        / "train_selected.csv",

        BASE_DIR
        / "data"
        / "processed"
        / "models"
        / "phase19"
        / "phase19_training_matrix.csv",

        BASE_DIR
        / "data"
        / "processed"
        / "models"
        / "phase19"
        / "train.csv",

        BASE_DIR
        / "data"
        / "processed"
        / "models"
        / "phase18"
        / "train_physical.csv",
    ]

    for path in candidates:
        if not path.exists():
            continue

        try:
            df = pd.read_csv(path)

            available = [
                f
                for f in features
                if f in df.columns
            ]

            if len(available) >= len(features) * 0.8:
                medians = (
                    df[features]
                    .apply(pd.to_numeric, errors="coerce")
                    .median()
                )

                return medians
        except Exception:
            continue

    # Final deterministic fallback:
    # compute medians from inference data.
    if INFERENCE_PATH.exists():
        df = pd.read_csv(INFERENCE_PATH)

        medians = (
            df[features]
            .apply(pd.to_numeric, errors="coerce")
            .median()
        )

        return medians

    return pd.Series(
        0.0,
        index=features,
        dtype=float,
    )


def audit_and_impute(
    X: pd.DataFrame,
    features: List[str],
    medians: pd.Series,
    strict: bool,
    missing: List[str],
) -> Tuple[pd.DataFrame, List[str]]:
    if strict and missing:
        raise ValueError(
            "Strict mode enabled: coordinate/basin feature state is missing "
            f"{len(missing)} required model features: {missing}"
        )

    X = X[features].copy()

    imputed: List[str] = []

    for feature in features:
        value = X.at[0, feature]

        if pd.isna(value) or not np.isfinite(float(value)):
            median = medians.get(feature, np.nan)

            if pd.isna(median) or not np.isfinite(float(median)):
                raise ValueError(
                    f"No valid imputation value available for feature "
                    f"'{feature}'."
                )

            X.at[0, feature] = float(median)

            if feature not in imputed:
                imputed.append(feature)

    X = X.astype(float)

    return X, imputed


def probability_from_model(
    model: Any,
    X: pd.DataFrame,
) -> float:
    probabilities = model.predict_proba(X)

    if probabilities.ndim != 2:
        raise ValueError(
            f"Unexpected predict_proba output shape: "
            f"{probabilities.shape}"
        )

    if probabilities.shape[1] < 2:
        raise ValueError(
            "Model does not expose binary class probabilities."
        )

    return float(probabilities[0, 1])


def classify_risk(
    probability: float,
    threshold: float,
) -> Tuple[int, str]:
    prediction = int(probability >= threshold)

    if probability >= 0.70:
        risk_class = "VERY_HIGH"
    elif probability >= 0.50:
        risk_class = "HIGH"
    elif probability >= threshold:
        risk_class = "MODERATE"
    elif probability >= 0.20:
        risk_class = "LOW"
    else:
        risk_class = "VERY_LOW"

    return prediction, risk_class


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CHETAKAI V1 Phase 20 Coordinate Flood Inference"
    )

    parser.add_argument(
        "--lat",
        type=float,
        required=True,
    )

    parser.add_argument(
        "--lon",
        type=float,
        required=True,
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
    )

    parser.add_argument(
        "--strict",
        action="store_true",
    )

    return parser.parse_args()


def validate_coordinates(
    lat: float,
    lon: float,
) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(
            f"Invalid latitude: {lat}"
        )

    if not -180 <= lon <= 180:
        raise ValueError(
            f"Invalid longitude: {lon}"
        )


def main() -> None:
    args = parse_args()

    validate_coordinates(
        args.lat,
        args.lon,
    )

    banner(
        "CHETAKAI V1 — PHASE 20 COORDINATE FLOOD INFERENCE ENGINE"
    )

    section("INPUT")

    print(f"Latitude                : {args.lat:.6f}")
    print(f"Longitude               : {args.lon:.6f}")
    print(f"Strict mode             : {args.strict}")

    section("LOADING PHASE 19 MODEL")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Phase 19 model not found:\n{MODEL_PATH}"
        )

    if not CONTRACT_PATH.exists():
        raise FileNotFoundError(
            f"Phase 19 contract not found:\n{CONTRACT_PATH}"
        )

    model = load_model()

    features, contract = load_contract()

    print(f"Model                   : {MODEL_PATH}")
    print(f"Contract                : {CONTRACT_PATH}")
    print(f"Production features     : {len(features)}")
    print(
        f"Estimator type          : "
        f"{type(model).__name__}"
    )

    threshold = args.threshold

    if threshold is None:
        threshold = contract.get("threshold")

    if threshold is None:
        threshold = contract.get(
            "optimal_threshold",
            0.34,
        )

    threshold = float(threshold)

    print(
        f"Threshold               : {threshold:.6f}"
    )

    section("LOADING INFERENCE DATA")

    if not INFERENCE_PATH.exists():
        raise FileNotFoundError(
            f"Inference dataset not found:\n{INFERENCE_PATH}"
        )

    inference = pd.read_csv(INFERENCE_PATH)

    print(f"Unlabeled dataset       : {INFERENCE_PATH}")
    print(f"Rows                    : {len(inference)}")
    print(f"Columns                 : {len(inference.columns)}")

    inference = prepare_inference_dataframe(
        inference
    )

    section("RESOLVING LOCATION")

    basin_id, basin_row = resolve_basin(
        args.lat,
        args.lon,
    )

    if basin_id is None:
        print("Basin boundary match    : NOT FOUND")

        if args.strict:
            raise ValueError(
                "Strict mode enabled: coordinate does not resolve to "
                "a known basin boundary."
            )

        raise ValueError(
            "Coordinate could not be resolved to a basin. "
            "Inference stopped to prevent unsafe global-state fallback."
        )

    print(
        f"Basin boundary match    : {basin_id}"
    )

    section("RESOLVING BASIN FEATURE STATE")

    try:
        state, state_timestamp = find_coordinate_state(
            inference,
            basin_id,
            args.lat,
            args.lon,
        )
    except Exception as exc:
        raise ValueError(
            f"Could not resolve feature state for basin {basin_id}: "
            f"{exc}"
        ) from exc

    state_basin = normalize_basin_id(
        state.get("_normalized_basin_id")
    )

    print(
        f"Resolved state basin    : {state_basin}"
    )

    print(
        f"State timestamp         : {state_timestamp}"
    )

    if state_basin != basin_id:
        raise ValueError(
            "CRITICAL SAFETY ERROR: resolved feature state basin "
            f"'{state_basin}' does not match coordinate basin "
            f"'{basin_id}'."
        )

    print(
        "Basin/state consistency : PASS"
    )

    section("BUILDING PHASE 19 FEATURE VECTOR")

    X, missing = build_feature_vector(
        state,
        features,
    )

    print(
        f"Required features       : {len(features)}"
    )

    available_count = len(features) - len(missing)

    print(
        f"Available features      : {available_count}"
    )

    print(
        f"Missing features        : {len(missing)}"
    )

    if missing:
        print()
        print("MISSING FEATURES:")

        for feature in missing:
            print(f" - {feature}")

    section("FEATURE IMPUTATION")

    medians = load_training_medians(
        features
    )

    print(
        f"Training medians available: "
        f"{len(medians.dropna())}"
    )

    if missing:
        print()
        print("FEATURES NOT PRESENT IN ORIGINAL STATE:")

        for feature in missing:
            print(f" - {feature}")

    X, imputed = audit_and_impute(
        X,
        features,
        medians,
        args.strict,
        missing,
    )

    if imputed:
        print()
        print("MEDIAN-IMPUTED FEATURES:")

        for feature in imputed:
            print(f" - {feature}")
    else:
        print(
            "No feature imputation required."
        )

    section("FINAL FEATURE CONTRACT AUDIT")

    order_pass = list(X.columns) == features

    numeric_pass = all(
        pd.api.types.is_numeric_dtype(
            X[col]
        )
        for col in X.columns
    )

    infinity_count = int(
        np.isinf(
            X.to_numpy(dtype=float)
        ).sum()
    )

    remaining_missing = int(
        X.isna().sum().sum()
    )

    print(
        f"Feature order           : "
        f"{'PASS' if order_pass else 'FAIL'}"
    )

    print(
        f"Feature count           : {X.shape[1]}"
    )

    print(
        f"Numeric matrix          : "
        f"{'PASS' if numeric_pass else 'FAIL'}"
    )

    print(
        f"Infinity                : {infinity_count}"
    )

    print(
        f"Remaining missing      : {remaining_missing}"
    )

    if not order_pass:
        raise ValueError(
            "Feature ordering does not match Phase 19 contract."
        )

    if not numeric_pass:
        raise ValueError(
            "Feature matrix contains non-numeric columns."
        )

    if infinity_count != 0:
        raise ValueError(
            "Feature matrix contains infinity values."
        )

    if remaining_missing != 0:
        raise ValueError(
            "Feature matrix still contains missing values."
        )

    section("FLOOD PREDICTION")

    probability = probability_from_model(
        model,
        X,
    )

    prediction, risk_class = classify_risk(
        probability,
        threshold,
    )

    print(
        f"Flood probability       : {probability:.4f}"
    )

    print(
        f"Flood probability %     : "
        f"{probability * 100:.2f}%"
    )

    print(
        f"Threshold               : {threshold:.4f}"
    )

    print(
        f"Flood prediction        : "
        f"{'FLOOD RISK' if prediction else 'NO FLOOD RISK'}"
    )

    print(
        f"Risk class              : {risk_class}"
    )

    result = {
        "latitude": args.lat,
        "longitude": args.lon,
        "basin_id": basin_id,
        "basin_name": (
            basin_row.get("basin_name")
            if basin_row is not None
            else None
        ),
        "timestamp": state_timestamp,
        "model": "phase19_best",
        "estimator": type(model).__name__,
        "feature_count": len(features),
        "threshold": threshold,
        "flood_probability": probability,
        "flood_prediction": prediction,
        "risk_class": risk_class,
        "state_resolution": "basin_matched",
        "state_basin_id": state_basin,
        "original_missing_features": missing,
        "median_imputed_features": imputed,
        "strict_mode": args.strict,
    }

    section("PHASE 20 RESULT")

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )

    banner("PHASE 20 COMPLETE")

    print(
        "Coordinate resolution    : PASS"
    )

    print(
        f"Basin                    : {basin_id}"
    )

    print(
        f"Feature state            : {state_basin}"
    )

    print(
        f"Probability              : "
        f"{probability * 100:.2f}%"
    )

    print(
        f"Risk                     : {risk_class}"
    )

    print(
        f"Prediction               : "
        f"{'FLOOD RISK' if prediction else 'NO FLOOD RISK'}"
    )


if __name__ == "__main__":
    main()