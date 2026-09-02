from pathlib import Path
import json
import shutil
import warnings

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

warnings.filterwarnings("ignore")


ROOT = Path("data/processed/master")
PHASE12_DIR = ROOT / "phase12"
PHASE13_DIR = ROOT / "phase13"

MODEL_DIR = PHASE13_DIR / "models"
PRED_DIR = PHASE13_DIR / "predictions"
METRIC_DIR = PHASE13_DIR / "metrics"
IMPORTANCE_DIR = PHASE13_DIR / "feature_importance"

X_TRAIN = PHASE12_DIR / "X_train.csv"
X_VAL = PHASE12_DIR / "X_validation.csv"
X_TEST = PHASE12_DIR / "X_test.csv"

Y_TRAIN = PHASE12_DIR / "y_train.csv"
Y_VAL = PHASE12_DIR / "y_validation.csv"
Y_TEST = PHASE12_DIR / "y_test.csv"

MODEL_FILE = MODEL_DIR / "chetakai_v1_flood_classifier_baseline.joblib"
FEATURE_FILE = MODEL_DIR / "chetakai_v1_flood_classifier_features.json"
MANIFEST_FILE = MODEL_DIR / "chetakai_v1_flood_classifier_manifest.json"

VAL_PRED_FILE = PRED_DIR / "flood_classifier_validation_predictions.csv"
TEST_PRED_FILE = PRED_DIR / "flood_classifier_test_predictions.csv"

METRICS_FILE = METRIC_DIR / "flood_classifier_baseline_metrics.csv"
IMPORTANCE_FILE = IMPORTANCE_DIR / "flood_classifier_feature_importance.csv"


print("=" * 110)
print("CHETAKAI V1 — PHASE 13A FLOOD CLASSIFIER BASELINE")
print("=" * 110)


for directory in [
    PHASE13_DIR,
    MODEL_DIR,
    PRED_DIR,
    METRIC_DIR,
    IMPORTANCE_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)


required_files = [
    X_TRAIN,
    X_VAL,
    X_TEST,
    Y_TRAIN,
    Y_VAL,
    Y_TEST,
]

for file in required_files:
    if not file.exists():
        raise FileNotFoundError(f"Required Phase 12 file not found:\n{file}")


print("\nLOADING FROZEN PHASE 12 DATA")
print("-" * 110)

X_train = pd.read_csv(X_TRAIN)
X_val = pd.read_csv(X_VAL)
X_test = pd.read_csv(X_TEST)

y_train_df = pd.read_csv(Y_TRAIN)
y_val_df = pd.read_csv(Y_VAL)
y_test_df = pd.read_csv(Y_TEST)

target = "target_flood"

if target not in y_train_df.columns:
    raise ValueError("target_flood missing from y_train.")

if target not in y_val_df.columns:
    raise ValueError("target_flood missing from y_validation.")

if target not in y_test_df.columns:
    raise ValueError("target_flood missing from y_test.")


y_train = y_train_df[target].astype(int)
y_val = y_val_df[target].astype(int)
y_test = y_test_df[target].astype(int)


print("X_train shape :", X_train.shape)
print("X_val shape   :", X_val.shape)
print("X_test shape  :", X_test.shape)

print("Train floods  :", int(y_train.sum()))
print("Val floods    :", int(y_val.sum()))
print("Test floods   :", int(y_test.sum()))


print("\nFEATURE ALIGNMENT")
print("-" * 110)

if list(X_train.columns) != list(X_val.columns):
    raise ValueError("X_train and X_validation feature columns do not match.")

if list(X_train.columns) != list(X_test.columns):
    raise ValueError("X_train and X_test feature columns do not match.")

feature_names = list(X_train.columns)

print("Features      :", len(feature_names))
print("Alignment     : PASS")


print("\nDATA SAFETY")
print("-" * 110)

if X_train.isna().any().any():
    raise ValueError("NaNs found in X_train.")

if X_val.isna().any().any():
    raise ValueError("NaNs found in X_validation.")

if X_test.isna().any().any():
    raise ValueError("NaNs found in X_test.")

if target in X_train.columns:
    raise ValueError("TARGET LEAKAGE: target_flood found in X_train.")

if target in X_val.columns:
    raise ValueError("TARGET LEAKAGE: target_flood found in X_validation.")

if target in X_test.columns:
    raise ValueError("TARGET LEAKAGE: target_flood found in X_test.")

if not set(y_train.unique()).issubset({0, 1}):
    raise ValueError("Invalid training target values.")

print("NaN safety       : PASS")
print("Target leakage   : PASS")


print("\nMODEL CONFIGURATION")
print("-" * 110)

model = RandomForestClassifier(
    n_estimators=500,
    max_depth=None,
    min_samples_split=4,
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)

print("Algorithm        : RandomForestClassifier")
print("Estimators       : 500")
print("Class weighting  : balanced")
print("Random state     : 42")
print("Training split   : 2015–2022")
print("Validation split : 2023–2024")
print("Test split       : 2025")


print("\nTRAINING")
print("-" * 110)

model.fit(X_train, y_train)

print("Training complete.")


print("\nVALIDATION PREDICTIONS")
print("-" * 110)

val_probability = model.predict_proba(X_val)[:, 1]
val_prediction = (val_probability >= 0.50).astype(int)

val_auc = roc_auc_score(y_val, val_probability)
val_pr_auc = average_precision_score(y_val, val_probability)
val_accuracy = accuracy_score(y_val, val_prediction)
val_precision = precision_score(y_val, val_prediction, zero_division=0)
val_recall = recall_score(y_val, val_prediction, zero_division=0)
val_f1 = f1_score(y_val, val_prediction, zero_division=0)

val_cm = confusion_matrix(y_val, val_prediction)

print(f"ROC-AUC       : {val_auc:.4f}")
print(f"PR-AUC        : {val_pr_auc:.4f}")
print(f"Accuracy      : {val_accuracy:.4f}")
print(f"Precision     : {val_precision:.4f}")
print(f"Recall        : {val_recall:.4f}")
print(f"F1            : {val_f1:.4f}")

print("\nConfusion Matrix")
print(val_cm)


print("\nTEST HOLDOUT")
print("-" * 110)

test_probability = model.predict_proba(X_test)[:, 1]
test_prediction = (test_probability >= 0.50).astype(int)

if y_test.sum() == 0:
    print("WARNING: 2025 test contains ZERO positive flood labels.")
    print("ROC-AUC / PR-AUC / recall / F1 are not meaningful for this test set.")

    test_auc = np.nan
    test_pr_auc = np.nan
    test_precision = np.nan
    test_recall = np.nan
    test_f1 = np.nan
else:
    test_auc = roc_auc_score(y_test, test_probability)
    test_pr_auc = average_precision_score(y_test, test_probability)
    test_precision = precision_score(
        y_test,
        test_prediction,
        zero_division=0,
    )
    test_recall = recall_score(
        y_test,
        test_prediction,
        zero_division=0,
    )
    test_f1 = f1_score(
        y_test,
        test_prediction,
        zero_division=0,
    )

test_accuracy = accuracy_score(y_test, test_prediction)

print(f"Accuracy      : {test_accuracy:.4f}")

if not np.isnan(test_auc):
    print(f"ROC-AUC       : {test_auc:.4f}")
    print(f"PR-AUC        : {test_pr_auc:.4f}")
    print(f"Precision     : {test_precision:.4f}")
    print(f"Recall        : {test_recall:.4f}")
    print(f"F1            : {test_f1:.4f}")


print("\nTHRESHOLD ANALYSIS")
print("-" * 110)

threshold_rows = []

for threshold in np.arange(0.10, 0.91, 0.05):

    prediction = (val_probability >= threshold).astype(int)

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

    threshold_rows.append(
        {
            "threshold": round(float(threshold), 2),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
        }
    )

threshold_df = pd.DataFrame(threshold_rows)

best_row = threshold_df.loc[
    threshold_df["f1"].idxmax()
]

best_threshold = float(best_row["threshold"])

print(
    f"Best validation F1 threshold : "
    f"{best_threshold:.2f}"
)

print(
    f"Best validation F1            : "
    f"{best_row['f1']:.4f}"
)

print(
    f"Recall at best threshold      : "
    f"{best_row['recall']:.4f}"
)

print(
    f"Precision at best threshold   : "
    f"{best_row['precision']:.4f}"
)


print("\nFEATURE IMPORTANCE")
print("-" * 110)

importance = pd.DataFrame(
    {
        "feature": feature_names,
        "importance": model.feature_importances_,
    }
)

importance = importance.sort_values(
    "importance",
    ascending=False,
)

importance.to_csv(
    IMPORTANCE_FILE,
    index=False,
)

print("Saved feature importance.")
print("\nTop 20 features:")

for _, row in importance.head(20).iterrows():
    print(
        f"{row['feature']:<55} "
        f"{row['importance']:.6f}"
    )


print("\nSAVING MODEL")
print("-" * 110)

joblib.dump(
    model,
    MODEL_FILE,
)

with open(
    FEATURE_FILE,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        feature_names,
        f,
        indent=2,
    )


manifest = {
    "project": "ChetakAI V1",
    "phase": "13A",
    "model": "flood_classifier_baseline",
    "algorithm": "RandomForestClassifier",
    "purpose": "Flood probability classification",
    "training_period": "2015-2022",
    "validation_period": "2023-2024",
    "test_period": "2025",
    "features": len(feature_names),
    "train_rows": len(X_train),
    "validation_rows": len(X_val),
    "test_rows": len(X_test),
    "train_positive": int(y_train.sum()),
    "validation_positive": int(y_val.sum()),
    "test_positive": int(y_test.sum()),
    "validation_roc_auc": float(val_auc),
    "validation_pr_auc": float(val_pr_auc),
    "validation_precision": float(val_precision),
    "validation_recall": float(val_recall),
    "validation_f1": float(val_f1),
    "best_validation_threshold": best_threshold,
    "test_positive_available": bool(y_test.sum() > 0),
    "phase12_data_modified": False,
    "model_persistent": True,
    "proxy_features_present": True,
    "proxy_features_are_real_observations": False,
}

with open(
    MANIFEST_FILE,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        manifest,
        f,
        indent=2,
    )


print("Model saved:")
print(MODEL_FILE)

print("\nFeature schema saved:")
print(FEATURE_FILE)

print("\nManifest saved:")
print(MANIFEST_FILE)


print("\nSAVING PREDICTIONS")
print("-" * 110)

val_predictions = val_df = y_val_df[
    [
        "canonical_basin_id",
        "timestamp",
        "target_flood",
    ]
].copy()

val_predictions["flood_probability"] = val_probability
val_predictions["flood_prediction_050"] = val_prediction
val_predictions["flood_prediction_best_threshold"] = (
    val_probability >= best_threshold
).astype(int)

val_predictions.to_csv(
    VAL_PRED_FILE,
    index=False,
)

test_predictions = y_test_df[
    [
        "canonical_basin_id",
        "timestamp",
        "target_flood",
    ]
].copy()

test_predictions["flood_probability"] = test_probability
test_predictions["flood_prediction_050"] = test_prediction

test_predictions.to_csv(
    TEST_PRED_FILE,
    index=False,
)


metrics = pd.DataFrame(
    [
        {
            "dataset": "validation",
            "period": "2023-2024",
            "roc_auc": val_auc,
            "pr_auc": val_pr_auc,
            "accuracy": val_accuracy,
            "precision": val_precision,
            "recall": val_recall,
            "f1": val_f1,
            "threshold": 0.50,
            "positive_labels": int(y_val.sum()),
        },
        {
            "dataset": "test",
            "period": "2025",
            "roc_auc": test_auc,
            "pr_auc": test_pr_auc,
            "accuracy": test_accuracy,
            "precision": test_precision,
            "recall": test_recall,
            "f1": test_f1,
            "threshold": 0.50,
            "positive_labels": int(y_test.sum()),
        },
    ]
)

metrics.to_csv(
    METRICS_FILE,
    index=False,
)


print("\n")
print("=" * 110)
print("PHASE 13A FINAL VALIDATION")
print("=" * 110)

print("\nMODEL")
print("-" * 110)
print("Algorithm                 : Random Forest")
print("Training rows             :", len(X_train))
print("Validation rows           :", len(X_val))
print("Test rows                 :", len(X_test))
print("Features                  :", len(feature_names))

print("\nVALIDATION")
print("-" * 110)
print(f"ROC-AUC                   : {val_auc:.4f}")
print(f"PR-AUC                    : {val_pr_auc:.4f}")
print(f"Precision                 : {val_precision:.4f}")
print(f"Recall                    : {val_recall:.4f}")
print(f"F1                        : {val_f1:.4f}")
print(f"Best threshold            : {best_threshold:.2f}")

print("\nMODEL PERSISTENCE")
print("-" * 110)
print("Saved model               : PASS")
print("Reusable without training: YES")
print("Phase 12 modified        : NO")

print("\nOUTPUTS")
print("-" * 110)
print("Model:")
print(MODEL_FILE)

print("\nFeature schema:")
print(FEATURE_FILE)

print("\nManifest:")
print(MANIFEST_FILE)

print("\nValidation predictions:")
print(VAL_PRED_FILE)

print("\nTest predictions:")
print(TEST_PRED_FILE)

print("\nMetrics:")
print(METRICS_FILE)

print("\nFeature importance:")
print(IMPORTANCE_FILE)

print("\n")
print("=" * 110)
print("🔥 PHASE 13A PASS — FLOOD CLASSIFIER TRAINED & PERSISTED")
print("=" * 110)