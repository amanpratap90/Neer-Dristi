from pathlib import Path
import json
import warnings

import joblib
import numpy as np
import pandas as pd

from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, mutual_info_classif
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import (
    RandomForestClassifier,
    HistGradientBoostingClassifier,
    ExtraTreesClassifier,
    RandomForestRegressor,
)
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    brier_score_loss,
    confusion_matrix,
)
from sklearn.inspection import permutation_importance

warnings.filterwarnings("ignore")


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_DIR = BASE_DIR / "data" / "processed" / "models" / "phase18"
OUTPUT_DIR = BASE_DIR / "data" / "processed" / "models" / "phase19"

TRAIN_FILE = INPUT_DIR / "train_physical.csv"
VAL_FILE = INPUT_DIR / "validation_physical.csv"
TEST_FILE = INPUT_DIR / "test_physical.csv"
CONTRACT_FILE = INPUT_DIR / "physical_feature_contract.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "target_flood"

METADATA_COLUMNS = {
    "canonical_basin_id",
    "timestamp",
    TARGET,
}


# ============================================================
# PRINT HELPERS
# ============================================================

def banner(text):
    print()
    print("=" * 110)
    print(text)
    print("=" * 110)


def section(text):
    print()
    print("-" * 110)
    print(text)
    print("-" * 110)


# ============================================================
# LOAD
# ============================================================

def load_data():
    train = pd.read_csv(TRAIN_FILE)
    val = pd.read_csv(VAL_FILE)
    test = pd.read_csv(TEST_FILE)

    return train, val, test


def load_contract():
    with open(CONTRACT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# ROBUST CONTRACT FEATURE EXTRACTION
# ============================================================

def recursively_find_feature_lists(obj, candidates, path="root"):
    """
    Recursively inspect JSON and collect lists that look like
    feature-name lists.

    This avoids assuming a particular JSON key such as
    'physical_features'.
    """

    if isinstance(obj, dict):
        for key, value in obj.items():
            child_path = f"{path}.{key}"

            if isinstance(value, list):
                string_items = [
                    str(x) for x in value
                    if isinstance(x, str)
                ]

                if len(string_items) >= 5:
                    candidates.append(
                        (
                            child_path,
                            string_items,
                            key.lower(),
                        )
                    )

            elif isinstance(value, dict):
                recursively_find_feature_lists(
                    value,
                    candidates,
                    child_path,
                )

            elif isinstance(value, list):
                recursively_find_feature_lists(
                    value,
                    candidates,
                    child_path,
                )

    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            recursively_find_feature_lists(
                value,
                candidates,
                f"{path}[{i}]",
            )


def validate_contract(train, val, test, contract):
    """
    Find the physical feature list without relying on one exact
    JSON schema.
    """

    all_train_numeric = set(
        train.select_dtypes(include="number").columns
    )

    all_train_features = all_train_numeric - {TARGET}

    candidates = []

    recursively_find_feature_lists(
        contract,
        candidates,
    )

    if not candidates:
        raise ValueError(
            "No feature list containing strings was found in "
            "physical_feature_contract.json"
        )

    scored = []

    for path, features, key_name in candidates:

        feature_set = set(features)

        overlap = feature_set.intersection(
            all_train_features
        )

        metadata_overlap = feature_set.intersection(
            METADATA_COLUMNS
        )

        score = len(overlap)

        key_bonus = 0

        important_terms = [
            "physical",
            "feature",
            "model",
            "hazard",
            "contract",
        ]

        for term in important_terms:
            if term in key_name:
                key_bonus += 100

        score += key_bonus

        scored.append(
            (
                score,
                len(overlap),
                path,
                features,
                metadata_overlap,
            )
        )

    scored.sort(
        key=lambda x: (x[0], x[1]),
        reverse=True,
    )

    best = scored[0]

    _, overlap_count, selected_path, selected_features, metadata_overlap = best

    selected_features = [
        f for f in selected_features
        if f in all_train_features
        and f not in METADATA_COLUMNS
    ]

    if len(selected_features) == 0:
        raise ValueError(
            "Could not match any contract features to the "
            "numeric columns in train_physical.csv"
        )

    train_set = set(train.columns)
    val_set = set(val.columns)
    test_set = set(test.columns)

    missing_train = [
        f for f in selected_features
        if f not in train_set
    ]

    missing_val = [
        f for f in selected_features
        if f not in val_set
    ]

    missing_test = [
        f for f in selected_features
        if f not in test_set
    ]

    if missing_train:
        raise ValueError(
            f"Contract features missing from train: {missing_train}"
        )

    if missing_val:
        raise ValueError(
            f"Contract features missing from validation: {missing_val}"
        )

    if missing_test:
        raise ValueError(
            f"Contract features missing from test: {missing_test}"
        )

    print(f"Contract feature list found at : {selected_path}")
    print(f"Contract features matched      : {len(selected_features)}")

    if metadata_overlap:
        print(
            f"Metadata excluded from contract: "
            f"{sorted(metadata_overlap)}"
        )

    return selected_features


# ============================================================
# DATA PREPARATION
# ============================================================

def prepare_xy(df, features):
    X = df[features].copy()
    y = df[TARGET].astype(int)

    X = X.replace([np.inf, -np.inf], np.nan)

    return X, y


# ============================================================
# MISSING VALUE SUMMARY
# ============================================================

def missing_summary(X):
    result = pd.DataFrame({
        "feature": X.columns,
        "missing_count": X.isna().sum().values,
        "missing_rate": X.isna().mean().values,
    })

    return result.sort_values(
        "missing_rate",
        ascending=False,
    )


# ============================================================
# FEATURE CLEANING
# ============================================================

def remove_bad_features(train_X, val_X, test_X):

    keep = []

    removed = []

    for feature in train_X.columns:

        values = train_X[feature]

        if values.isna().all():
            removed.append(
                (feature, "all_missing")
            )
            continue

        non_missing = values.dropna()

        if non_missing.nunique() <= 1:
            removed.append(
                (feature, "constant")
            )
            continue

        keep.append(feature)

    train_X = train_X[keep].copy()
    val_X = val_X[keep].copy()
    test_X = test_X[keep].copy()

    return train_X, val_X, test_X, removed


# ============================================================
# FEATURE SELECTION
# ============================================================

def mutual_information_selection(
    X_train,
    y_train,
    X_val,
    X_test,
    max_features=60,
):
    """
    Select features using mutual information calculated only
    on training data.
    """

    n_features = X_train.shape[1]

    if n_features <= max_features:
        return (
            list(X_train.columns),
            pd.DataFrame({
                "feature": X_train.columns,
                "mutual_information": np.nan,
            }),
        )

    imputer = SimpleImputer(
        strategy="median"
    )

    X_imp = imputer.fit_transform(X_train)

    scores = mutual_info_classif(
        X_imp,
        y_train,
        random_state=42,
    )

    score_df = pd.DataFrame({
        "feature": X_train.columns,
        "mutual_information": scores,
    })

    score_df = score_df.sort_values(
        "mutual_information",
        ascending=False,
    )

    selected = score_df.head(
        max_features
    )["feature"].tolist()

    return selected, score_df


# ============================================================
# MODEL PIPELINES
# ============================================================

def build_models():

    models = {}

    models["logistic_regression"] = Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median"),
        ),
        (
            "scaler",
            StandardScaler(),
        ),
        (
            "model",
            LogisticRegression(
                max_iter=5000,
                class_weight="balanced",
                C=0.5,
                random_state=42,
            ),
        ),
    ])

    models["random_forest"] = Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median"),
        ),
        (
            "model",
            RandomForestClassifier(
                n_estimators=500,
                max_depth=8,
                min_samples_leaf=5,
                max_features="sqrt",
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ])

    models["extra_trees"] = Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median"),
        ),
        (
            "model",
            ExtraTreesClassifier(
                n_estimators=500,
                max_depth=10,
                min_samples_leaf=5,
                max_features="sqrt",
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ])

    models["hist_gradient_boosting"] = Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median"),
        ),
        (
            "model",
            HistGradientBoostingClassifier(
                max_iter=300,
                learning_rate=0.04,
                max_leaf_nodes=15,
                min_samples_leaf=15,
                l2_regularization=2.0,
                random_state=42,
            ),
        ),
    ])

    return models


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(y_true, probabilities, threshold=0.5):

    predictions = (
        probabilities >= threshold
    ).astype(int)

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        predictions,
        labels=[0, 1],
    ).ravel()

    return {
        "roc_auc": float(
            roc_auc_score(
                y_true,
                probabilities,
            )
        ),
        "pr_auc": float(
            average_precision_score(
                y_true,
                probabilities,
            )
        ),
        "accuracy": float(
            accuracy_score(
                y_true,
                predictions,
            )
        ),
        "precision": float(
            precision_score(
                y_true,
                predictions,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y_true,
                predictions,
                zero_division=0,
            )
        ),
        "f1": float(
            f1_score(
                y_true,
                predictions,
                zero_division=0,
            )
        ),
        "brier_score": float(
            brier_score_loss(
                y_true,
                probabilities,
            )
        ),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }


# ============================================================
# THRESHOLD OPTIMIZATION
# ============================================================

def find_best_threshold(y_true, probabilities):

    thresholds = np.arange(
        0.10,
        0.91,
        0.01,
    )

    best_threshold = 0.50
    best_f1 = -1

    rows = []

    for threshold in thresholds:

        predictions = (
            probabilities >= threshold
        ).astype(int)

        f1 = f1_score(
            y_true,
            predictions,
            zero_division=0,
        )

        precision = precision_score(
            y_true,
            predictions,
            zero_division=0,
        )

        recall = recall_score(
            y_true,
            predictions,
            zero_division=0,
        )

        rows.append({
            "threshold": threshold,
            "f1": f1,
            "precision": precision,
            "recall": recall,
        })

        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold

    return (
        best_threshold,
        pd.DataFrame(rows),
    )


# ============================================================
# MODEL TRAINING
# ============================================================

def train_and_evaluate(
    name,
    model,
    X_train,
    y_train,
    X_val,
    y_val,
    X_test,
    y_test,
):

    print()
    print("=" * 110)
    print(f"TRAINING: {name}")
    print("=" * 110)

    model.fit(
        X_train,
        y_train,
    )

    train_prob = model.predict_proba(
        X_train
    )[:, 1]

    val_prob = model.predict_proba(
        X_val
    )[:, 1]

    test_prob = model.predict_proba(
        X_test
    )[:, 1]

    best_threshold, threshold_df = (
        find_best_threshold(
            y_val,
            val_prob,
        )
    )

    train_metrics = calculate_metrics(
        y_train,
        train_prob,
        best_threshold,
    )

    val_metrics = calculate_metrics(
        y_val,
        val_prob,
        best_threshold,
    )

    test_metrics = calculate_metrics(
        y_test,
        test_prob,
        best_threshold,
    )

    print()
    print("OPTIMAL VALIDATION THRESHOLD")
    print(
        f"{best_threshold:.2f}"
    )

    print()
    print("TRAIN")
    print(train_metrics)

    print()
    print("VALIDATION")
    print(val_metrics)

    print()
    print("TEST")
    print(test_metrics)

    return {
        "model": model,
        "threshold": best_threshold,
        "threshold_table": threshold_df,
        "train_metrics": train_metrics,
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "train_prob": train_prob,
        "validation_prob": val_prob,
        "test_prob": test_prob,
    }


# ============================================================
# FEATURE IMPORTANCE
# ============================================================

def extract_feature_importance(
    model,
    feature_names,
):

    estimator = model.named_steps["model"]

    if hasattr(estimator, "feature_importances_"):

        importance = estimator.feature_importances_

        return pd.DataFrame({
            "feature": feature_names,
            "importance": importance,
        }).sort_values(
            "importance",
            ascending=False,
        )

    if hasattr(estimator, "coef_"):

        importance = np.abs(
            estimator.coef_[0]
        )

        return pd.DataFrame({
            "feature": feature_names,
            "importance": importance,
        }).sort_values(
            "importance",
            ascending=False,
        )

    return pd.DataFrame(
        columns=[
            "feature",
            "importance",
        ]
    )


# ============================================================
# SAVE MODEL PACKAGE
# ============================================================

def save_model_package(
    result,
    selected_features,
    model_name,
):

    package = {
        "model": result["model"],
        "threshold": result["threshold"],
        "features": selected_features,
        "target": TARGET,
        "model_name": model_name,
        "version": "CHETAKAI_V1_PHASE19",
    }

    output_file = (
        OUTPUT_DIR /
        f"{model_name}_phase19.joblib"
    )

    joblib.dump(
        package,
        output_file,
    )

    return output_file


# ============================================================
# MAIN
# ============================================================

def main():

    banner(
        "CHETAKAI V1 — PHASE 19 FEATURE SELECTION + ROBUST MODEL TRAINING"
    )

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    section("LOADING DATA")

    train, val, test = load_data()

    print(
        f"Train      : {train.shape}"
    )
    print(
        f"Validation : {val.shape}"
    )
    print(
        f"Test       : {test.shape}"
    )

    # --------------------------------------------------------
    # TARGET
    # --------------------------------------------------------

    section("TARGET")

    for name, df in [
        ("TRAIN", train),
        ("VALIDATION", val),
        ("TEST", test),
    ]:

        positives = int(
            df[TARGET].sum()
        )

        rate = (
            positives /
            len(df)
        )

        print(
            f"{name:<12} "
            f"rows={len(df):4d} "
            f"floods={positives:4d} "
            f"rate={rate:.2%}"
        )

    # --------------------------------------------------------
    # CONTRACT
    # --------------------------------------------------------

    section("FEATURE CONTRACT")

    contract = load_contract()

    contract_features = validate_contract(
        train,
        val,
        test,
        contract,
    )

    print(
        f"Final contract features: "
        f"{len(contract_features)}"
    )

    # --------------------------------------------------------
    # PREPARE
    # --------------------------------------------------------

    section("PREPARING FEATURES")

    X_train, y_train = prepare_xy(
        train,
        contract_features,
    )

    X_val, y_val = prepare_xy(
        val,
        contract_features,
    )

    X_test, y_test = prepare_xy(
        test,
        contract_features,
    )

    print(
        f"Initial feature count: "
        f"{X_train.shape[1]}"
    )

    # --------------------------------------------------------
    # INFINITY
    # --------------------------------------------------------

    section("INFINITY AUDIT")

    for name, X in [
        ("TRAIN", X_train),
        ("VALIDATION", X_val),
        ("TEST", X_test),
    ]:

        count = np.isinf(
            X.select_dtypes(
                include=np.number
            )
        ).sum().sum()

        print(
            f"{name:<12} infinity={int(count)}"
        )

    X_train = X_train.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    X_val = X_val.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    X_test = X_test.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    # --------------------------------------------------------
    # BAD FEATURES
    # --------------------------------------------------------

    section("FEATURE QUALITY")

    (
        X_train,
        X_val,
        X_test,
        removed,
    ) = remove_bad_features(
        X_train,
        X_val,
        X_test,
    )

    print(
        f"Retained features : {X_train.shape[1]}"
    )

    print(
        f"Removed features  : {len(removed)}"
    )

    if removed:

        for feature, reason in removed:
            print(
                f" - {feature}: {reason}"
            )

    # --------------------------------------------------------
    # MISSINGNESS
    # --------------------------------------------------------

    section("MISSINGNESS")

    for name, X in [
        ("TRAIN", X_train),
        ("VALIDATION", X_val),
        ("TEST", X_test),
    ]:

        missing = int(
            X.isna().sum().sum()
        )

        total = (
            X.shape[0] *
            X.shape[1]
        )

        rate = (
            missing /
            total
            if total
            else 0
        )

        print(
            f"{name:<12} "
            f"missing={missing:6d} "
            f"rate={rate:.2%}"
        )

    # --------------------------------------------------------
    # MUTUAL INFORMATION
    # --------------------------------------------------------

    section(
        "MUTUAL INFORMATION FEATURE SELECTION"
    )

    MAX_FEATURES = min(
        60,
        X_train.shape[1],
    )

    (
        selected_features,
        mi_scores,
    ) = mutual_information_selection(
        X_train,
        y_train,
        X_val,
        X_test,
        max_features=MAX_FEATURES,
    )

    print(
        f"Original physical features : "
        f"{len(contract_features)}"
    )

    print(
        f"Usable features             : "
        f"{X_train.shape[1]}"
    )

    print(
        f"Selected features           : "
        f"{len(selected_features)}"
    )

    mi_scores.to_csv(
        OUTPUT_DIR /
        "mutual_information_scores.csv",
        index=False,
    )

    print()
    print("TOP SELECTED FEATURES")

    for i, feature in enumerate(
        selected_features[:30],
        1,
    ):
        print(
            f"{i:3d}. {feature}"
        )

    # --------------------------------------------------------
    # REDUCE DATA
    # --------------------------------------------------------

    X_train_selected = (
        X_train[selected_features]
        .copy()
    )

    X_val_selected = (
        X_val[selected_features]
        .copy()
    )

    X_test_selected = (
        X_test[selected_features]
        .copy()
    )

    # --------------------------------------------------------
    # SAVE SELECTED CONTRACT
    # --------------------------------------------------------

    selected_contract = {
        "version": "CHETAKAI_V1_PHASE19",
        "source_contract": str(
            CONTRACT_FILE.relative_to(
                BASE_DIR
            )
        ),
        "original_feature_count": len(
            contract_features
        ),
        "usable_feature_count": X_train.shape[1],
        "selected_feature_count": len(
            selected_features
        ),
        "target": TARGET,
        "features": selected_features,
    }

    with open(
        OUTPUT_DIR /
        "phase19_feature_contract.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            selected_contract,
            f,
            indent=2,
        )

    # --------------------------------------------------------
    # MODELS
    # --------------------------------------------------------

    section(
        "ROBUST MODEL TRAINING"
    )

    models = build_models()

    results = {}

    for name, model in models.items():

        results[name] = train_and_evaluate(
            name,
            model,
            X_train_selected,
            y_train,
            X_val_selected,
            y_val,
            X_test_selected,
            y_test,
        )

    # --------------------------------------------------------
    # COMPARISON
    # --------------------------------------------------------

    section(
        "MODEL COMPARISON"
    )

    comparison_rows = []

    for name, result in results.items():

        metrics = result[
            "validation_metrics"
        ]

        test_metrics = result[
            "test_metrics"
        ]

        comparison_rows.append({
            "model": name,
            "validation_roc_auc":
                metrics["roc_auc"],
            "validation_pr_auc":
                metrics["pr_auc"],
            "validation_precision":
                metrics["precision"],
            "validation_recall":
                metrics["recall"],
            "validation_f1":
                metrics["f1"],
            "validation_brier":
                metrics["brier_score"],
            "test_roc_auc":
                test_metrics["roc_auc"],
            "test_pr_auc":
                test_metrics["pr_auc"],
            "test_f1":
                test_metrics["f1"],
            "threshold":
                result["threshold"],
        })

    comparison = pd.DataFrame(
        comparison_rows
    )

    comparison = comparison.sort_values(
        [
            "validation_pr_auc",
            "validation_f1",
            "validation_roc_auc",
        ],
        ascending=False,
    )

    print(
        comparison.to_string(
            index=False
        )
    )

    comparison.to_csv(
        OUTPUT_DIR /
        "phase19_model_comparison.csv",
        index=False,
    )

    # --------------------------------------------------------
    # BEST MODEL
    # --------------------------------------------------------

    best_model_name = (
        comparison.iloc[0]["model"]
    )

    best_result = results[
        best_model_name
    ]

    section(
        "BEST PHASE 19 MODEL"
    )

    print(
        f"Model             : "
        f"{best_model_name}"
    )

    print(
        f"Selected features : "
        f"{len(selected_features)}"
    )

    print(
        f"Threshold          : "
        f"{best_result['threshold']:.2f}"
    )

    print()
    print("VALIDATION METRICS")

    print(
        best_result[
            "validation_metrics"
        ]
    )

    print()
    print("TEST METRICS")

    print(
        best_result[
            "test_metrics"
        ]
    )

    # --------------------------------------------------------
    # FEATURE IMPORTANCE
    # --------------------------------------------------------

    section(
        "BEST MODEL FEATURE IMPORTANCE"
    )

    importance = extract_feature_importance(
        best_result["model"],
        selected_features,
    )

    importance.to_csv(
        OUTPUT_DIR /
        "phase19_feature_importance.csv",
        index=False,
    )

    print(
        importance.head(30).to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # SAVE BEST MODEL
    # --------------------------------------------------------

    best_model_file = (
        OUTPUT_DIR /
        "best_phase19_flood_model.joblib"
    )

    package = {
        "model":
            best_result["model"],
        "model_name":
            best_model_name,
        "threshold":
            float(
                best_result["threshold"]
            ),
        "features":
            selected_features,
        "target":
            TARGET,
        "version":
            "CHETAKAI_V1_PHASE19",
        "validation_metrics":
            best_result[
                "validation_metrics"
            ],
        "test_metrics":
            best_result[
                "test_metrics"
            ],
    }

    joblib.dump(
        package,
        best_model_file,
    )

    # --------------------------------------------------------
    # SAVE ALL MODELS
    # --------------------------------------------------------

    section(
        "SAVING MODEL ARTIFACTS"
    )

    for name, result in results.items():

        output_file = save_model_package(
            result,
            selected_features,
            name,
        )

        print(
            f"{name:<30} -> "
            f"{output_file}"
        )

    # --------------------------------------------------------
    # PREDICTIONS
    # --------------------------------------------------------

    section(
        "GENERATING TEST PREDICTIONS"
    )

    test_predictions = test[
        [
            c for c in
            [
                "canonical_basin_id",
                "timestamp",
            ]
            if c in test.columns
        ]
    ].copy()

    test_predictions[
        "actual_flood"
    ] = y_test.values

    test_predictions[
        "flood_probability"
    ] = best_result[
        "test_prob"
    ]

    test_predictions[
        "flood_prediction"
    ] = (
        test_predictions[
            "flood_probability"
        ]
        >= best_result[
            "threshold"
        ]
    ).astype(int)

    test_predictions.to_csv(
        OUTPUT_DIR /
        "phase19_test_predictions.csv",
        index=False,
    )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    report_file = (
        OUTPUT_DIR /
        "phase19_training_report.txt"
    )

    with open(
        report_file,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            "CHETAKAI V1 — PHASE 19 "
            "FEATURE SELECTION + ROBUST MODEL TRAINING\n"
        )

        f.write("=" * 100 + "\n\n")

        f.write(
            f"Original physical features: "
            f"{len(contract_features)}\n"
        )

        f.write(
            f"Usable features: "
            f"{X_train.shape[1]}\n"
        )

        f.write(
            f"Selected features: "
            f"{len(selected_features)}\n"
        )

        f.write(
            f"Best model: "
            f"{best_model_name}\n"
        )

        f.write(
            f"Threshold: "
            f"{best_result['threshold']:.4f}\n\n"
        )

        f.write(
            "VALIDATION\n"
        )

        for key, value in (
            best_result[
                "validation_metrics"
            ].items()
        ):

            f.write(
                f"{key}: {value}\n"
            )

        f.write(
            "\nTEST\n"
        )

        for key, value in (
            best_result[
                "test_metrics"
            ].items()
        ):

            f.write(
                f"{key}: {value}\n"
            )

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    banner(
        "PHASE 19 COMPLETE"
    )

    print(
        f"Physical features      : "
        f"{len(contract_features)}"
    )

    print(
        f"Usable features        : "
        f"{X_train.shape[1]}"
    )

    print(
        f"Selected features      : "
        f"{len(selected_features)}"
    )

    print(
        f"Best model             : "
        f"{best_model_name}"
    )

    print(
        f"Validation ROC-AUC     : "
        f"{best_result['validation_metrics']['roc_auc']:.4f}"
    )

    print(
        f"Validation PR-AUC      : "
        f"{best_result['validation_metrics']['pr_auc']:.4f}"
    )

    print(
        f"Validation F1          : "
        f"{best_result['validation_metrics']['f1']:.4f}"
    )

    print(
        f"Test ROC-AUC           : "
        f"{best_result['test_metrics']['roc_auc']:.4f}"
    )

    print(
        f"Test PR-AUC            : "
        f"{best_result['test_metrics']['pr_auc']:.4f}"
    )

    print(
        f"Test F1                : "
        f"{best_result['test_metrics']['f1']:.4f}"
    )

    print()
    print(
        f"Best model : "
        f"{best_model_file}"
    )

    print(
        f"Contract   : "
        f"{OUTPUT_DIR / 'phase19_feature_contract.json'}"
    )

    print(
        f"Comparison : "
        f"{OUTPUT_DIR / 'phase19_model_comparison.csv'}"
    )

    print(
        f"Importance : "
        f"{OUTPUT_DIR / 'phase19_feature_importance.csv'}"
    )

    print(
        f"Report     : "
        f"{report_file}"
    )

    print()
    print(
        "STATUS: PASS"
    )

    print(
        "=" * 110
    )


if __name__ == "__main__":
    main()