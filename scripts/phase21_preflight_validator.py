from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

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

DEM_RAW_DIR = (
    ROOT
    / "data"
    / "raw"
    / "dem"
)

TERRAIN_DIR = (
    ROOT
    / "data"
    / "processed"
    / "features"
    / "terrain"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase21"
)

AUDIT_PATH = (
    OUTPUT_DIR
    / "phase21_preflight_audit.json"
)

EXPECTED_FEATURES = 60
EXPECTED_THRESHOLD = 0.34

TERRAIN_FEATURES = [
    "mean_slope_deg",
    "elevation_range_ratio",
    "min_elevation_m",
]


class PreflightFailure(Exception):
    pass


def section(title: str) -> None:
    print()
    print("=" * 110)
    print(title)
    print("=" * 110)


def item(label: str, value: Any) -> None:
    print(f"{label:<38}: {value}")


def ok(label: str, value: Any = "PASS") -> None:
    print(f"[PASS] {label:<30} {value}")


def warn(label: str, value: Any) -> None:
    print(f"[WARN] {label:<30} {value}")


def fail(label: str, value: Any) -> None:
    print(f"[FAIL] {label:<30} {value}")


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def normalize_basin_id(value: Any) -> Optional[str]:

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
        suffix = text[len("CWC_BASIN_"):]

        if suffix.isdigit():
            return f"CWC_BASIN_{int(suffix):03d}"

        return text

    if text.startswith("CWC_"):
        suffix = text[len("CWC_"):]

        if suffix.isdigit():
            return f"CWC_BASIN_{int(suffix):03d}"

    if text.isdigit():
        return f"CWC_BASIN_{int(text):03d}"

    return text


def find_column(
    df: pd.DataFrame,
    candidates: List[str],
) -> Optional[str]:

    lower = {
        str(c).strip().lower(): c
        for c in df.columns
    }

    for candidate in candidates:

        key = candidate.strip().lower()

        if key in lower:
            return lower[key]

    return None


def resolve_estimator(
    artifact: Any,
    path: str = "root",
) -> Tuple[Any, str]:

    if (
        hasattr(artifact, "predict")
        and hasattr(artifact, "predict_proba")
    ):
        return artifact, path

    if isinstance(artifact, dict):

        preferred = [
            "model",
            "estimator",
            "pipeline",
            "classifier",
            "best_model",
            "best_estimator",
            "fitted_model",
            "fitted_estimator",
        ]

        for key in preferred:

            if key not in artifact:
                continue

            try:
                return resolve_estimator(
                    artifact[key],
                    f"{path}.{key}",
                )
            except PreflightFailure:
                pass

        for key, value in artifact.items():

            if key in preferred:
                continue

            try:
                return resolve_estimator(
                    value,
                    f"{path}.{key}",
                )
            except PreflightFailure:
                pass

    if isinstance(
        artifact,
        (list, tuple),
    ):

        for index, value in enumerate(artifact):

            try:
                return resolve_estimator(
                    value,
                    f"{path}[{index}]",
                )
            except PreflightFailure:
                pass

    raise PreflightFailure(
        "Could not locate sklearn estimator with "
        "predict() and predict_proba()."
    )


def extract_features(
    contract: Dict[str, Any],
) -> List[str]:

    candidates = [
        contract.get("features"),
        contract.get("production_features"),
        contract.get("model_features"),
        contract.get("selected_features"),
    ]

    for candidate in candidates:

        if (
            isinstance(candidate, list)
            and candidate
        ):
            return [
                str(x).strip()
                for x in candidate
            ]

    raise PreflightFailure(
        "No production feature list found."
    )


def extract_threshold(
    contract: Dict[str, Any],
) -> float:

    candidates = [
        "decision_threshold",
        "threshold",
        "optimal_threshold",
        "validation_threshold",
    ]

    for key in candidates:

        value = contract.get(key)

        if finite(value):
            value = float(value)

            if not 0 < value < 1:
                raise PreflightFailure(
                    f"Invalid threshold {value}."
                )

            return value

    raise PreflightFailure(
        "Phase 19 contract has no decision threshold. "
        "Run phase21_repair_phase19_contract.py."
    )


def inspect_model() -> Dict[str, Any]:

    section("1. PHASE 19 MODEL")

    if not MODEL_PATH.exists():
        raise PreflightFailure(
            f"Model not found:\n{MODEL_PATH}"
        )

    artifact = joblib.load(MODEL_PATH)

    estimator, estimator_path = resolve_estimator(
        artifact
    )

    item(
        "Loaded artifact type",
        type(artifact).__name__,
    )

    item(
        "Estimator path",
        estimator_path,
    )

    item(
        "Estimator type",
        type(estimator).__name__,
    )

    if not hasattr(
        estimator,
        "predict_proba",
    ):
        raise PreflightFailure(
            "Estimator does not expose predict_proba()."
        )

    if not hasattr(
        estimator,
        "predict",
    ):
        raise PreflightFailure(
            "Estimator does not expose predict()."
        )

    ok(
        "predict_proba()",
        "AVAILABLE",
    )

    ok(
        "predict()",
        "AVAILABLE",
    )

    return {
        "artifact": artifact,
        "estimator": estimator,
        "estimator_path": estimator_path,
    }


def inspect_contract() -> Dict[str, Any]:

    section("2. PHASE 19 FEATURE CONTRACT")

    if not CONTRACT_PATH.exists():
        raise PreflightFailure(
            f"Contract not found:\n{CONTRACT_PATH}"
        )

    with open(
        CONTRACT_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        contract = json.load(f)

    features = extract_features(
        contract
    )

    threshold = extract_threshold(
        contract
    )

    item(
        "Production feature count",
        len(features),
    )

    item(
        "Decision threshold",
        threshold,
    )

    if len(features) != EXPECTED_FEATURES:
        raise PreflightFailure(
            f"Expected {EXPECTED_FEATURES} features, "
            f"found {len(features)}."
        )

    if abs(
        threshold - EXPECTED_THRESHOLD
    ) > 1e-12:
        raise PreflightFailure(
            "Phase 21 threshold mismatch. "
            f"Expected {EXPECTED_THRESHOLD}, "
            f"found {threshold}."
        )

    ok(
        "Feature count",
        "60 / 60",
    )

    ok(
        "Decision threshold",
        f"{threshold:.6f}",
    )

    return {
        "contract": contract,
        "features": features,
        "threshold": threshold,
    }


def inspect_inference(
    features: List[str],
) -> Dict[str, Any]:

    section("3. INFERENCE DATA")

    if not INFERENCE_PATH.exists():
        raise PreflightFailure(
            f"Inference dataset not found:\n{INFERENCE_PATH}"
        )

    df = pd.read_csv(
        INFERENCE_PATH
    )

    if df.empty:
        raise PreflightFailure(
            "Inference dataset is empty."
        )

    missing = [
        f
        for f in features
        if f not in df.columns
    ]

    basin_col = find_column(
        df,
        [
            "canonical_basin_id",
            "basin_id",
            "basin",
            "cwc_basin",
            "id",
        ],
    )

    timestamp_col = find_column(
        df,
        [
            "timestamp",
            "datetime",
            "date",
            "time",
            "valid_time",
            "state_timestamp",
        ],
    )

    item(
        "Rows",
        len(df),
    )

    item(
        "Columns",
        len(df.columns),
    )

    item(
        "Basin column",
        basin_col,
    )

    item(
        "Timestamp column",
        timestamp_col,
    )

    item(
        "Missing production features",
        len(missing),
    )

    if basin_col is None:
        raise PreflightFailure(
            "Inference dataset has no basin identifier column."
        )

    if missing:
        for feature in missing:
            print(
                f"  [WARN] {feature}"
            )

    return {
        "df": df,
        "missing": missing,
        "basin_column": basin_col,
        "timestamp_column": timestamp_col,
    }


def inspect_boundary() -> Dict[str, Any]:

    section("4. BASIN BOUNDARY")

    if not BASIN_PATH.exists():
        raise PreflightFailure(
            f"Basin boundary not found:\n{BASIN_PATH}"
        )

    try:
        import geopandas as gpd

        gdf = gpd.read_file(
            BASIN_PATH
        )

        if gdf.empty:
            raise PreflightFailure(
                "Basin boundary is empty."
            )

        basin_col = find_column(
            pd.DataFrame(
                columns=gdf.columns
            ),
            [
                "canonical_basin_id",
                "basin_id",
                "cwc_id",
                "cwc_basin",
                "id",
            ],
        )

        if basin_col is None:
            raise PreflightFailure(
                "No usable basin ID column found "
                "in boundary file."
            )

        item(
            "Rows",
            len(gdf),
        )

        item(
            "CRS",
            gdf.crs,
        )

        item(
            "Basin ID column",
            basin_col,
        )

        ok(
            "Boundary geometry",
            "AVAILABLE",
        )

        return {
            "rows": len(gdf),
            "crs": str(gdf.crs),
            "basin_column": basin_col,
        }

    except ImportError as exc:
        raise PreflightFailure(
            "GeoPandas is required for Phase 21 "
            "coordinate validation."
        ) from exc


def inspect_terrain(
    features: List[str],
) -> Dict[str, Any]:

    section("5. TERRAIN")

    required = [
        feature
        for feature in TERRAIN_FEATURES
        if feature in features
    ]

    item(
        "Required terrain features",
        len(required),
    )

    if len(required) != 3:
        raise PreflightFailure(
            "Phase 19 contract does not contain "
            "all required terrain features."
        )

    processed = []

    if TERRAIN_DIR.exists():

        for path in TERRAIN_DIR.rglob("*"):

            if (
                path.is_file()
                and path.suffix.lower()
                in {
                    ".tif",
                    ".tiff",
                    ".vrt",
                }
            ):
                processed.append(path)

    raw = []

    if DEM_RAW_DIR.exists():

        for path in DEM_RAW_DIR.rglob("*"):

            if (
                path.is_file()
                and path.suffix.lower()
                in {
                    ".tif",
                    ".tiff",
                    ".vrt",
                }
            ):
                raw.append(path)

    item(
        "Processed terrain rasters",
        len(processed),
    )

    item(
        "Raw DEM rasters",
        len(raw),
    )

    if not processed and not raw:
        raise PreflightFailure(
            "No DEM/terrain rasters found."
        )

    ok(
        "Terrain source",
        "AVAILABLE",
    )

    return {
        "processed_files": [
            str(x)
            for x in processed
        ],
        "raw_files": [
            str(x)
            for x in raw
        ],
        "available": True,
    }


def inspect_model_contract(
    estimator: Any,
    features: List[str],
) -> None:

    section("6. MODEL ↔ CONTRACT")

    expected = getattr(
        estimator,
        "n_features_in_",
        None,
    )

    item(
        "Contract features",
        len(features),
    )

    item(
        "Estimator n_features_in_",
        expected,
    )

    if expected is not None:

        if int(expected) != len(features):

            raise PreflightFailure(
                "Model and feature contract disagree: "
                f"{expected} vs {len(features)}."
            )

    ok(
        "Model / contract compatibility",
        "PASS",
    )


def make_synthetic_matrix(
    features: List[str],
) -> pd.DataFrame:

    return pd.DataFrame(
        np.zeros(
            (1, len(features)),
            dtype=float,
        ),
        columns=features,
    )


def synthetic_prediction(
    estimator: Any,
    features: List[str],
    threshold: float,
) -> Dict[str, Any]:

    section("7. SYNTHETIC MODEL TEST")

    X = make_synthetic_matrix(
        features
    )

    try:
        probabilities = estimator.predict_proba(
            X
        )

        prediction = estimator.predict(
            X
        )

    except Exception as exc:

        raise PreflightFailure(
            "Phase 19 estimator rejected the "
            "60-feature production matrix."
        ) from exc

    probabilities = np.asarray(
        probabilities
    )

    prediction = np.asarray(
        prediction
    )

    if (
        probabilities.ndim != 2
        or probabilities.shape[0] != 1
        or probabilities.shape[1] < 2
    ):
        raise PreflightFailure(
            f"Unexpected predict_proba shape: "
            f"{probabilities.shape}"
        )

    probability = float(
        probabilities[0, -1]
    )

    if not 0 <= probability <= 1:
        raise PreflightFailure(
            f"Invalid model probability: "
            f"{probability}"
        )

    predicted_class = int(
        prediction.reshape(-1)[0]
    )

    threshold_class = int(
        probability >= threshold
    )

    item(
        "Probability",
        f"{probability:.6f}",
    )

    item(
        "Threshold",
        f"{threshold:.6f}",
    )

    item(
        "predict()",
        predicted_class,
    )

    item(
        "Threshold prediction",
        threshold_class,
    )

    ok(
        "Synthetic prediction",
        "PASS",
    )

    return {
        "probability": probability,
        "prediction": predicted_class,
        "threshold_prediction": threshold_class,
    }


def build_state_diagnostics(
    inference: Dict[str, Any],
) -> Dict[str, Any]:

    df = inference["df"]
    basin_col = inference["basin_column"]

    normalized = (
        df[basin_col]
        .map(normalize_basin_id)
    )

    counts = (
        normalized
        .value_counts(dropna=False)
        .head(10)
        .to_dict()
    )

    section("8. BASIN STATE COVERAGE")

    item(
        "Unique normalized basins",
        normalized.nunique(
            dropna=True
        ),
    )

    item(
        "Null basin rows",
        int(
            normalized.isna().sum()
        ),
    )

    print()

    for basin, count in counts.items():
        print(
            f"  {basin}: {count}"
        )

    target = "CWC_BASIN_012"

    target_count = int(
        (normalized == target).sum()
    )

    item(
        "CWC_BASIN_012 rows",
        target_count,
    )

    if target_count == 0:
        warn(
            "Coordinate test basin",
            "CWC_BASIN_012 not represented"
        )
    else:
        ok(
            "Coordinate test basin",
            "STATE AVAILABLE",
        )

    return {
        "unique_basins": int(
            normalized.nunique(
                dropna=True
            )
        ),
        "target_rows": target_count,
    }


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--strict",
        action="store_true",
    )

    args = parser.parse_args()

    section(
        "CHETAKAI V1 — PHASE 21 PREFLIGHT VALIDATOR"
    )

    print(
        "This validator validates the complete Phase 21 "
        "production contract."
    )

    results: Dict[str, Any] = {}

    try:

        model = inspect_model()

        contract = inspect_contract()

        inference = inspect_inference(
            contract["features"]
        )

        boundary = inspect_boundary()

        terrain = inspect_terrain(
            contract["features"]
        )

        inspect_model_contract(
            model["estimator"],
            contract["features"],
        )

        prediction = synthetic_prediction(
            model["estimator"],
            contract["features"],
            contract["threshold"],
        )

        state = build_state_diagnostics(
            inference
        )

        failures = []

        if args.strict:

            if inference["missing"]:
                failures.append(
                    "Inference dataset is missing "
                    "production features."
                )

            if state["target_rows"] == 0:
                failures.append(
                    "Coordinate test basin "
                    "CWC_BASIN_012 has no state rows."
                )

        results = {
            "phase": "21",
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "model": {
                "path": str(MODEL_PATH),
                "estimator_type": type(
                    model["estimator"]
                ).__name__,
                "estimator_path": model[
                    "estimator_path"
                ],
            },
            "contract": {
                "feature_count": len(
                    contract["features"]
                ),
                "threshold": contract[
                    "threshold"
                ],
            },
            "inference": {
                "rows": len(
                    inference["df"]
                ),
                "columns": len(
                    inference["df"].columns
                ),
                "missing": inference[
                    "missing"
                ],
            },
            "boundary": boundary,
            "terrain": terrain,
            "synthetic_prediction": prediction,
            "state": state,
            "strict": args.strict,
            "failures": failures,
            "status": (
                "PASS"
                if not failures
                else "FAIL"
            ),
        }

        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            AUDIT_PATH,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                results,
                f,
                indent=2,
                ensure_ascii=False,
            )

        section(
            "PHASE 21 PREFLIGHT RESULT"
        )

        item(
            "Status",
            results["status"],
        )

        item(
            "Feature count",
            f"{len(contract['features'])} / 60",
        )

        item(
            "Threshold",
            contract["threshold"],
        )

        item(
            "Inference rows",
            len(inference["df"]),
        )

        item(
            "Terrain",
            "AVAILABLE",
        )

        item(
            "CWC_BASIN_012 state rows",
            state["target_rows"],
        )

        item(
            "Synthetic probability",
            f"{prediction['probability']:.6f}",
        )

        item(
            "Audit",
            AUDIT_PATH,
        )

        if failures:

            print()
            print(
                "BLOCKING FAILURES:"
            )

            for failure in failures:
                print(
                    f"  [FAIL] {failure}"
                )

            print()
            print(
                "PHASE 21 PREFLIGHT: BLOCKED"
            )

            return 2

        print()
        print(
            "PHASE 21 PREFLIGHT: PASS"
        )

        return 0

    except Exception as exc:

        print()
        print("=" * 110)
        print(
            "PHASE 21 PREFLIGHT: CRASHED"
        )
        print("=" * 110)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        traceback.print_exc()

        return 1


if __name__ == "__main__":
    sys.exit(main())