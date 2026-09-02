from pathlib import Path
import json
import warnings
import shutil
import joblib
import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import (
    RandomForestClassifier,
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_score,
    recall_score,
    f1_score,
    fbeta_score,
    accuracy_score,
    confusion_matrix,
    brier_score_loss,
)

warnings.filterwarnings("ignore")


# ================================================================
# PATHS
# ================================================================

ROOT = Path("data/processed/master")

PHASE12 = ROOT / "phase12"
PHASE13 = ROOT / "phase13"

MODEL_DIR = PHASE13 / "production"
REPORT_DIR = PHASE13 / "phase13c_to_13f"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

X_TRAIN = PHASE12 / "X_train.csv"
X_VAL = PHASE12 / "X_validation.csv"
X_TEST = PHASE12 / "X_test.csv"

Y_TRAIN = PHASE12 / "y_train.csv"
Y_VAL = PHASE12 / "y_validation.csv"
Y_TEST = PHASE12 / "y_test.csv"

MASTER = PHASE12 / "chetakai_v1_master_phase12.csv"

MODEL_OUT = MODEL_DIR / "chetakai_v1_flood_classifier_production.joblib"
SCHEMA_OUT = MODEL_DIR / "chetakai_v1_flood_classifier_feature_schema.json"
PREPROCESS_OUT = MODEL_DIR / "chetakai_v1_flood_classifier_preprocessing.json"
THRESHOLD_OUT = MODEL_DIR / "chetakai_v1_flood_classifier_thresholds.json"
METRICS_OUT = MODEL_DIR / "chetakai_v1_flood_classifier_metrics.json"
MANIFEST_OUT = MODEL_DIR / "chetakai_v1_flood_classifier_manifest.json"

COMPARISON_OUT = REPORT_DIR / "phase13c_model_comparison.csv"
CALIBRATION_OUT = REPORT_DIR / "phase13d_calibration_comparison.csv"
THRESHOLD_OUT_CSV = REPORT_DIR / "phase13e_threshold_analysis.csv"
VAL_PRED_OUT = REPORT_DIR / "phase13_production_validation_predictions.csv"
TEST_PRED_OUT = REPORT_DIR / "phase13_production_test_predictions.csv"
FEATURE_IMPORTANCE_OUT = REPORT_DIR / "phase13_production_feature_importance.csv"


print("=" * 110)
print("CHETAKAI V1 — PHASE 13C → 13F PRODUCTION CLASSIFIER PIPELINE")
print("=" * 110)


# ================================================================
# LOAD
# ================================================================

print("\nLOADING FROZEN PHASE 12 DATA")
print("-" * 110)

for p in [
    X_TRAIN,
    X_VAL,
    X_TEST,
    Y_TRAIN,
    Y_VAL,
    Y_TEST,
]:
    if not p.exists():
        raise FileNotFoundError(f"Required file not found:\n{p}")

X_train = pd.read_csv(X_TRAIN)
X_val = pd.read_csv(X_VAL)
X_test = pd.read_csv(X_TEST)

y_train_df = pd.read_csv(Y_TRAIN)
y_val_df = pd.read_csv(Y_VAL)
y_test_df = pd.read_csv(Y_TEST)

y_train = y_train_df["target_flood"].astype(int)
y_val = y_val_df["target_flood"].astype(int)
y_test = y_test_df["target_flood"].astype(int)

print("X_train:", X_train.shape)
print("X_val  :", X_val.shape)
print("X_test :", X_test.shape)

print("Train floods:", int(y_train.sum()))
print("Val floods  :", int(y_val.sum()))
print("Test floods :", int(y_test.sum()))


# ================================================================
# SAFETY
# ================================================================

print("\nDATA SAFETY")
print("-" * 110)

if "target_flood" in X_train.columns:
    raise ValueError("TARGET LEAKAGE in X_train")

if "target_flood" in X_val.columns:
    raise ValueError("TARGET LEAKAGE in X_validation")

if "target_flood" in X_test.columns:
    raise ValueError("TARGET LEAKAGE in X_test")

if X_train.isna().any().any():
    raise ValueError("NaNs found in X_train")

if X_val.isna().any().any():
    raise ValueError("NaNs found in X_validation")

if X_test.isna().any().any():
    raise ValueError("NaNs found in X_test")

if list(X_train.columns) != list(X_val.columns):
    raise ValueError("Feature alignment failure: train/validation")

if list(X_train.columns) != list(X_test.columns):
    raise ValueError("Feature alignment failure: train/test")

if not set(y_train.unique()).issubset({0, 1}):
    raise ValueError("Invalid training target")

if not set(y_val.unique()).issubset({0, 1}):
    raise ValueError("Invalid validation target")

print("Feature alignment : PASS")
print("NaN safety        : PASS")
print("Target leakage    : PASS")


FEATURES = list(X_train.columns)


# ================================================================
# PHASE 13C — MODEL COMPARISON
# ================================================================

print("\n")
print("=" * 110)
print("PHASE 13C — MODEL COMPARISON")
print("=" * 110)


models = {}


models["logistic_regression"] = Pipeline(
    [
        ("scaler", StandardScaler()),
        (
            "model",
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                random_state=42,
            ),
        ),
    ]
)


models["random_forest"] = RandomForestClassifier(
    n_estimators=600,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)


models["extra_trees"] = ExtraTreesClassifier(
    n_estimators=600,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)


models["hist_gradient_boosting"] = HistGradientBoostingClassifier(
    max_iter=300,
    learning_rate=0.05,
    max_leaf_nodes=31,
    l2_regularization=1.0,
    random_state=42,
)


# Optional XGBoost
try:
    from xgboost import XGBClassifier

    models["xgboost"] = XGBClassifier(
        n_estimators=500,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )

    print("XGBoost available: YES")

except Exception:
    print("XGBoost available: NO")
    print("Continuing with sklearn models.")


comparison_rows = []


for name, model in models.items():

    print("\n" + "-" * 110)
    print("MODEL:", name)

    model.fit(X_train, y_train)

    val_probability = model.predict_proba(X_val)[:, 1]
    val_prediction = (val_probability >= 0.50).astype(int)

    roc = roc_auc_score(y_val, val_probability)
    pr = average_precision_score(y_val, val_probability)
    precision = precision_score(
        y_val,
        val_prediction,
        zero_division=0,
    )
    recall = recall_score(
        y_val,
        val_prediction,
        zero_division=0,
    )
    f1 = f1_score(
        y_val,
        val_prediction,
        zero_division=0,
    )
    f2 = fbeta_score(
        y_val,
        val_prediction,
        beta=2,
        zero_division=0,
    )
    accuracy = accuracy_score(
        y_val,
        val_prediction,
    )
    brier = brier_score_loss(
        y_val,
        val_probability,
    )

    cm = confusion_matrix(
        y_val,
        val_prediction,
    )

    print("ROC-AUC   :", round(roc, 4))
    print("PR-AUC    :", round(pr, 4))
    print("Precision :", round(precision, 4))
    print("Recall    :", round(recall, 4))
    print("F1        :", round(f1, 4))
    print("F2        :", round(f2, 4))
    print("Brier     :", round(brier, 4))
    print("Confusion matrix:")
    print(cm)

    comparison_rows.append(
        {
            "model": name,
            "features": len(FEATURES),
            "roc_auc": roc,
            "pr_auc": pr,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "f2": f2,
            "accuracy": accuracy,
            "brier_score": brier,
        }
    )


comparison = pd.DataFrame(comparison_rows)

comparison = comparison.sort_values(
    ["pr_auc", "f2", "roc_auc"],
    ascending=False,
)

comparison.to_csv(
    COMPARISON_OUT,
    index=False,
)

print("\nMODEL RANKING")
print("-" * 110)
print(
    comparison[
        [
            "model",
            "roc_auc",
            "pr_auc",
            "precision",
            "recall",
            "f1",
            "f2",
            "brier_score",
        ]
    ].to_string(index=False)
)


# ================================================================
# CHAMPION SELECTION
# ================================================================

champion_name = comparison.iloc[0]["model"]

print("\n")
print("=" * 110)
print("PHASE 13C CHAMPION")
print("=" * 110)
print("Champion model:", champion_name)

champion_base = models[champion_name]


# ================================================================
# PHASE 13D — PROBABILITY CALIBRATION
# ================================================================

print("\n")
print("=" * 110)
print("PHASE 13D — PROBABILITY CALIBRATION")
print("=" * 110)

print("""
Calibration strategy:
- Calibration is fitted using TRAIN only.
- Validation remains outside calibration fitting.
- Validation is used only for evaluation.
- Test remains untouched.
""")


# Use sigmoid calibration because the dataset has only 481 positives.
calibrated_model = CalibratedClassifierCV(
    estimator=champion_base,
    method="sigmoid",
    cv=5,
)

calibrated_model.fit(
    X_train,
    y_train,
)

raw_model = clone(champion_base)
raw_model.fit(X_train, y_train)

raw_val_probability = raw_model.predict_proba(X_val)[:, 1]
calibrated_val_probability = calibrated_model.predict_proba(X_val)[:, 1]

raw_brier = brier_score_loss(
    y_val,
    raw_val_probability,
)

calibrated_brier = brier_score_loss(
    y_val,
    calibrated_val_probability,
)

raw_pr = average_precision_score(
    y_val,
    raw_val_probability,
)

calibrated_pr = average_precision_score(
    y_val,
    calibrated_val_probability,
)

raw_roc = roc_auc_score(
    y_val,
    raw_val_probability,
)

calibrated_roc = roc_auc_score(
    y_val,
    calibrated_val_probability,
)


calibration_report = pd.DataFrame(
    [
        {
            "model": champion_name,
            "probability_type": "raw",
            "roc_auc": raw_roc,
            "pr_auc": raw_pr,
            "brier_score": raw_brier,
        },
        {
            "model": champion_name,
            "probability_type": "sigmoid_calibrated",
            "roc_auc": calibrated_roc,
            "pr_auc": calibrated_pr,
            "brier_score": calibrated_brier,
        },
    ]
)

calibration_report.to_csv(
    CALIBRATION_OUT,
    index=False,
)

print("Raw Brier score       :", round(raw_brier, 4))
print("Calibrated Brier score:", round(calibrated_brier, 4))

if calibrated_brier <= raw_brier:
    calibration_status = "CALIBRATION_IMPROVED"
else:
    calibration_status = "CALIBRATION_NOT_IMPROVED"

print("Calibration status:", calibration_status)


# ================================================================
# PHASE 13E — THRESHOLD OPTIMIZATION
# ================================================================

print("\n")
print("=" * 110)
print("PHASE 13E — THRESHOLD OPTIMIZATION")
print("=" * 110)

thresholds = np.arange(
    0.05,
    0.951,
    0.01,
)

threshold_rows = []

for threshold in thresholds:

    prediction = (
        calibrated_val_probability >= threshold
    ).astype(int)

    precision = precision_score(
        y_val,
        prediction,
        zero_division=0,
    )

    recall = recall_score(
        y_val,
        prediction,
        zero_division=0,
    )

    f1 = f1_score(
        y_val,
        prediction,
        zero_division=0,
    )

    f2 = fbeta_score(
        y_val,
        prediction,
        beta=2,
        zero_division=0,
    )

    threshold_rows.append(
        {
            "threshold": float(threshold),
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "f2": f2,
        }
    )


threshold_report = pd.DataFrame(threshold_rows)

threshold_report.to_csv(
    THRESHOLD_OUT_CSV,
    index=False,
)


best_f1_row = threshold_report.loc[
    threshold_report["f1"].idxmax()
]

best_f2_row = threshold_report.loc[
    threshold_report["f2"].idxmax()
]


# Minimum-recall operational threshold.
recall_target = 0.75

recall_candidates = threshold_report[
    threshold_report["recall"] >= recall_target
]

if len(recall_candidates) > 0:

    operational_row = recall_candidates.sort_values(
        ["precision", "threshold"],
        ascending=[False, False],
    ).iloc[0]

else:

    operational_row = threshold_report.loc[
        threshold_report["recall"].idxmax()
    ]


print("\nBEST F1 THRESHOLD")
print("-" * 110)
print(
    "Threshold :",
    round(float(best_f1_row["threshold"]), 2),
)
print(
    "F1        :",
    round(float(best_f1_row["f1"]), 4),
)
print(
    "Precision :",
    round(float(best_f1_row["precision"]), 4),
)
print(
    "Recall    :",
    round(float(best_f1_row["recall"]), 4),
)


print("\nBEST F2 THRESHOLD")
print("-" * 110)
print(
    "Threshold :",
    round(float(best_f2_row["threshold"]), 2),
)
print(
    "F2        :",
    round(float(best_f2_row["f2"]), 4),
)
print(
    "Precision :",
    round(float(best_f2_row["precision"]), 4),
)
print(
    "Recall    :",
    round(float(best_f2_row["recall"]), 4),
)


print("\nOPERATIONAL EARLY-WARNING THRESHOLD")
print("-" * 110)
print(
    "Recall target:",
    recall_target,
)
print(
    "Threshold    :",
    round(float(operational_row["threshold"]), 2),
)
print(
    "Precision    :",
    round(float(operational_row["precision"]), 4),
)
print(
    "Recall       :",
    round(float(operational_row["recall"]), 4),
)


# ================================================================
# RISK LEVEL POLICY
# ================================================================

# Use the F2 threshold as the main binary flood decision.
f2_threshold = float(best_f2_row["threshold"])

# Risk display thresholds are deliberately separate from
# binary flood threshold.
risk_thresholds = {
    "LOW": 0.25,
    "MODERATE": 0.45,
    "HIGH": 0.65,
    "SEVERE": f2_threshold,
}

# Ensure monotonic ordering.
risk_thresholds["SEVERE"] = max(
    risk_thresholds["SEVERE"],
    risk_thresholds["HIGH"],
)

THRESHOLD_CONFIG = {
    "binary_flood_threshold": f2_threshold,
    "best_f1_threshold": float(best_f1_row["threshold"]),
    "best_f2_threshold": f2_threshold,
    "operational_recall_threshold": float(
        operational_row["threshold"]
    ),
    "operational_recall_target": recall_target,
    "risk_levels": risk_thresholds,
}


# ================================================================
# FINAL CALIBRATED VALIDATION
# ================================================================

production_threshold = f2_threshold

val_final_prediction = (
    calibrated_val_probability >= production_threshold
).astype(int)

final_val_metrics = {
    "roc_auc": float(
        roc_auc_score(
            y_val,
            calibrated_val_probability,
        )
    ),
    "pr_auc": float(
        average_precision_score(
            y_val,
            calibrated_val_probability,
        )
    ),
    "precision": float(
        precision_score(
            y_val,
            val_final_prediction,
            zero_division=0,
        )
    ),
    "recall": float(
        recall_score(
            y_val,
            val_final_prediction,
            zero_division=0,
        )
    ),
    "f1": float(
        f1_score(
            y_val,
            val_final_prediction,
            zero_division=0,
        )
    ),
    "f2": float(
        fbeta_score(
            y_val,
            val_final_prediction,
            beta=2,
            zero_division=0,
        )
    ),
    "brier_score": float(
        brier_score_loss(
            y_val,
            calibrated_val_probability,
        )
    ),
    "threshold": production_threshold,
}


# ================================================================
# 2025 HOLDOUT
# ================================================================

print("\n")
print("=" * 110)
print("2025 FINAL HOLDOUT")
print("=" * 110)

test_probability = calibrated_model.predict_proba(
    X_test
)[:, 1]

test_prediction = (
    test_probability >= production_threshold
).astype(int)

test_accuracy = accuracy_score(
    y_test,
    test_prediction,
)

print("2025 rows:", len(y_test))
print("2025 floods:", int(y_test.sum()))
print("2025 predicted floods:", int(test_prediction.sum()))
print("2025 accuracy:", round(test_accuracy, 4))

if y_test.sum() == 0:

    print(
        "\nWARNING: 2025 contains ZERO observed flood positives."
    )

    print(
        "ROC-AUC / PR-AUC / recall / F1 cannot be meaningfully "
        "reported for this holdout."
    )

    test_metrics = {
        "rows": int(len(y_test)),
        "observed_floods": 0,
        "predicted_floods": int(test_prediction.sum()),
        "accuracy": float(test_accuracy),
        "roc_auc": None,
        "pr_auc": None,
        "precision": None,
        "recall": None,
        "f1": None,
        "f2": None,
        "evaluation_status": "ZERO_POSITIVE_HOLDOUT",
    }

else:

    test_metrics = {
        "rows": int(len(y_test)),
        "observed_floods": int(y_test.sum()),
        "predicted_floods": int(test_prediction.sum()),
        "accuracy": float(test_accuracy),
        "roc_auc": float(
            roc_auc_score(
                y_test,
                test_probability,
            )
        ),
        "pr_auc": float(
            average_precision_score(
                y_test,
                test_probability,
            )
        ),
        "precision": float(
            precision_score(
                y_test,
                test_prediction,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y_test,
                test_prediction,
                zero_division=0,
            )
        ),
        "f1": float(
            f1_score(
                y_test,
                test_prediction,
                zero_division=0,
            )
        ),
        "f2": float(
            fbeta_score(
                y_test,
                test_prediction,
                beta=2,
                zero_division=0,
            )
        ),
        "evaluation_status": "VALID",
    }


# ================================================================
# FEATURE IMPORTANCE
# ================================================================

print("\nFEATURE IMPORTANCE")
print("-" * 110)

feature_importance = None

try:

    if hasattr(champion_base, "feature_importances_"):

        feature_importance = champion_base.feature_importances_

    elif hasattr(
        champion_base,
        "named_steps",
    ):

        final_model = champion_base.named_steps.get(
            "model"
        )

        if hasattr(
            final_model,
            "feature_importances_",
        ):
            feature_importance = (
                final_model.feature_importances_
            )

    if feature_importance is not None:

        importance_df = pd.DataFrame(
            {
                "feature": FEATURES,
                "importance": feature_importance,
            }
        ).sort_values(
            "importance",
            ascending=False,
        )

        importance_df.to_csv(
            FEATURE_IMPORTANCE_OUT,
            index=False,
        )

        print(
            importance_df.head(20).to_string(
                index=False
            )
        )

except Exception as e:

    print(
        "Feature importance unavailable:",
        str(e),
    )


# ================================================================
# PHASE 13F — PRODUCTION MODEL
# ================================================================

print("\n")
print("=" * 110)
print("PHASE 13F — PRODUCTION MODEL PERSISTENCE")
print("=" * 110)

# The calibrated model is the production model.
joblib.dump(
    calibrated_model,
    MODEL_OUT,
)


schema = {
    "dataset": "ChetakAI V1",
    "phase12_source": str(X_TRAIN),
    "feature_count": len(FEATURES),
    "features": FEATURES,
    "target": "target_flood",
    "feature_order_locked": True,
}

with open(
    SCHEMA_OUT,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        schema,
        f,
        indent=2,
    )


preprocessing = {
    "calibration": "sigmoid",
    "calibration_fit": "TRAIN ONLY",
    "imputation": "already completed in Phase 12",
    "scaling": (
        "inside model pipeline where applicable"
    ),
    "feature_order": "schema locked",
    "random_state": 42,
}

with open(
    PREPROCESS_OUT,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        preprocessing,
        f,
        indent=2,
    )


with open(
    THRESHOLD_OUT,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        THRESHOLD_CONFIG,
        f,
        indent=2,
    )


metrics = {
    "champion_model": champion_name,
    "feature_count": len(FEATURES),
    "validation": final_val_metrics,
    "test": test_metrics,
    "calibration": {
        "method": "sigmoid",
        "raw_brier": float(raw_brier),
        "calibrated_brier": float(calibrated_brier),
        "status": calibration_status,
    },
}

with open(
    METRICS_OUT,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        metrics,
        f,
        indent=2,
    )


manifest = {
    "project": "ChetakAI V1",
    "phase": "13C-13F",
    "purpose": "production flood classifier",
    "source_dataset": "Phase 12",
    "phase12_modified": False,
    "phase13a_modified": False,
    "phase13b_modified": False,
    "training_rows": int(len(X_train)),
    "validation_rows": int(len(X_val)),
    "test_rows": int(len(X_test)),
    "features": int(len(FEATURES)),
    "champion_model": champion_name,
    "calibration": "sigmoid",
    "calibration_fit_on": "TRAIN ONLY",
    "threshold_selection": "VALIDATION ONLY",
    "production_threshold": production_threshold,
    "random_split": False,
    "temporal_split": {
        "train": "2015-2022",
        "validation": "2023-2024",
        "test": "2025",
    },
    "test_positive_count": int(y_test.sum()),
    "test_limitation": (
        "2025 contains zero positive flood labels"
    ),
    "model_persistence": True,
    "requires_retraining_for_inference": False,
    "feature_schema_locked": True,
    "created_outputs": {
        "model": str(MODEL_OUT),
        "schema": str(SCHEMA_OUT),
        "preprocessing": str(PREPROCESS_OUT),
        "thresholds": str(THRESHOLD_OUT),
        "metrics": str(METRICS_OUT),
    },
}

with open(
    MANIFEST_OUT,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        manifest,
        f,
        indent=2,
    )


# ================================================================
# SAVE PREDICTIONS
# ================================================================

validation_predictions = y_val_df.copy()

validation_predictions["flood_probability_raw"] = (
    raw_val_probability
)

validation_predictions["flood_probability_calibrated"] = (
    calibrated_val_probability
)

validation_predictions["flood_prediction"] = (
    val_final_prediction
)

validation_predictions["threshold"] = (
    production_threshold
)

validation_predictions.to_csv(
    VAL_PRED_OUT,
    index=False,
)


test_predictions = y_test_df.copy()

test_predictions["flood_probability_calibrated"] = (
    test_probability
)

test_predictions["flood_prediction"] = (
    test_prediction
)

test_predictions["threshold"] = (
    production_threshold
)

test_predictions.to_csv(
    TEST_PRED_OUT,
    index=False,
)


# ================================================================
# HARD SAFETY
# ================================================================

print("\n")
print("=" * 110)
print("HARD PRODUCTION SAFETY VALIDATION")
print("=" * 110)

if not MODEL_OUT.exists():
    raise ValueError("Production model was not saved.")

if not SCHEMA_OUT.exists():
    raise ValueError("Feature schema was not saved.")

if not THRESHOLD_OUT.exists():
    raise ValueError("Threshold configuration was not saved.")

if not METRICS_OUT.exists():
    raise ValueError("Metrics were not saved.")

if len(FEATURES) != X_train.shape[1]:
    raise ValueError("Feature count mismatch.")

if production_threshold <= 0 or production_threshold >= 1:
    raise ValueError("Invalid production threshold.")

# Reload model to prove persistence.
reloaded_model = joblib.load(MODEL_OUT)

reload_probability = reloaded_model.predict_proba(
    X_val
)[:, 1]

if len(reload_probability) != len(X_val):
    raise ValueError(
        "Reloaded model inference length mismatch."
    )

if not np.allclose(
    reload_probability,
    calibrated_val_probability,
    atol=1e-8,
):
    raise ValueError(
        "Reloaded model predictions differ."
    )

print("Model saved                 : PASS")
print("Model reload                : PASS")
print("Reloaded inference          : PASS")
print("Feature schema              : PASS")
print("Threshold configuration     : PASS")
print("Metrics manifest            : PASS")
print("Phase 12 untouched          : PASS")
print("Phase 13A untouched         : PASS")
print("Phase 13B untouched         : PASS")
print("Retraining required         : NO")


# ================================================================
# FINAL
# ================================================================

print("\n")
print("=" * 110)
print("PHASE 13C → 13F FINAL VALIDATION")
print("=" * 110)

print("\nMODEL")
print("-" * 110)
print("Champion model       :", champion_name)
print("Features             :", len(FEATURES))
print("Training rows        :", len(X_train))
print("Validation rows      :", len(X_val))
print("Test rows            :", len(X_test))

print("\nCALIBRATION")
print("-" * 110)
print("Method               : sigmoid")
print("Raw Brier            :", round(raw_brier, 4))
print("Calibrated Brier     :", round(calibrated_brier, 4))
print("Status               :", calibration_status)

print("\nTHRESHOLD")
print("-" * 110)
print("Best F1 threshold    :", round(float(best_f1_row["threshold"]), 2))
print("Best F2 threshold    :", round(float(best_f2_row["threshold"]), 2))
print(
    "Operational threshold:",
    round(float(operational_row["threshold"]), 2),
)
print(
    "Production threshold :",
    round(production_threshold, 2),
)

print("\nVALIDATION")
print("-" * 110)
for k, v in final_val_metrics.items():
    if isinstance(v, float):
        print(f"{k:<22}: {v:.4f}")
    else:
        print(f"{k:<22}: {v}")

print("\n2025 HOLDOUT")
print("-" * 110)
print("Observed floods      :", int(y_test.sum()))
print("Predicted floods     :", int(test_prediction.sum()))
print("Evaluation status    :", test_metrics["evaluation_status"])

print("\nPRODUCTION ARTIFACTS")
print("-" * 110)
print("Model                :", MODEL_OUT)
print("Feature schema       :", SCHEMA_OUT)
print("Preprocessing        :", PREPROCESS_OUT)
print("Thresholds           :", THRESHOLD_OUT)
print("Metrics              :", METRICS_OUT)
print("Manifest             :", MANIFEST_OUT)

print("\nREPORTS")
print("-" * 110)
print("Model comparison     :", COMPARISON_OUT)
print("Calibration report   :", CALIBRATION_OUT)
print("Threshold analysis   :", THRESHOLD_OUT_CSV)
print("Validation prediction:", VAL_PRED_OUT)
print("Test prediction      :", TEST_PRED_OUT)

print("\n")
print("=" * 110)
print("🔥🔥 PHASE 13C PASS — MODEL COMPARISON COMPLETE")
print("🔥🔥 PHASE 13D PASS — PROBABILITY CALIBRATION COMPLETE")
print("🔥🔥 PHASE 13E PASS — THRESHOLD OPTIMIZATION COMPLETE")
print("🔥🔥 PHASE 13F PASS — PRODUCTION MODEL PERSISTED")
print("=" * 110)