from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd

from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
)

warnings.filterwarnings("ignore")

ROOT = Path("data/processed/training/phase15_1")
OUT = Path("data/processed/models/phase16")

OUT.mkdir(parents=True, exist_ok=True)

TRAIN = ROOT / "train.csv"
VALIDATION = ROOT / "validation.csv"
TEST = ROOT / "test.csv"

print("=" * 110)
print("CHETAKAI V1 — PHASE 16 BASELINE FLOOD MODELS")
print("=" * 110)

print("\nLOADING DATA")
print("-" * 110)

train = pd.read_csv(TRAIN)
validation = pd.read_csv(VALIDATION)
test = pd.read_csv(TEST)

print("Train      :", train.shape)
print("Validation :", validation.shape)
print("Test       :", test.shape)

TARGET = "target_flood"

META_COLUMNS = [
    "canonical_basin_id",
    "timestamp",
]

feature_columns = [
    c for c in train.columns
    if c not in META_COLUMNS + [TARGET]
]

print("\nFEATURE CONTRACT")
print("-" * 110)
print("Model features:", len(feature_columns))
print("Target:", TARGET)

if len(feature_columns) != 153:
    raise RuntimeError(
        f"Expected 153 model features, found {len(feature_columns)}"
    )

X_train = train[feature_columns].copy()
y_train = train[TARGET].astype(int)

X_val = validation[feature_columns].copy()
y_val = validation[TARGET].astype(int)

X_test = test[feature_columns].copy()
y_test = test[TARGET].astype(int)

print("\nTARGET DISTRIBUTION")
print("-" * 110)

for name, y in [
    ("TRAIN", y_train),
    ("VALIDATION", y_val),
    ("TEST", y_test),
]:
    print(
        f"{name:<12} "
        f"rows={len(y):4} "
        f"positive={int(y.sum()):4} "
        f"rate={y.mean() * 100:.2f}%"
    )

print("\nMISSING VALUES")
print("-" * 110)

print(
    "Train missing:",
    int(X_train.isna().sum().sum())
)

print(
    "Validation missing:",
    int(X_val.isna().sum().sum())
)

print(
    "Test missing:",
    int(X_test.isna().sum().sum())
)

# ------------------------------------------------------------------
# MODELS
# ------------------------------------------------------------------

models = {

    "logistic_regression": Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median")
        ),
        (
            "scaler",
            StandardScaler()
        ),
        (
            "model",
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                random_state=42,
                solver="liblinear"
            )
        )
    ]),

    "random_forest": Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median")
        ),
        (
            "model",
            RandomForestClassifier(
                n_estimators=500,
                max_depth=None,
                min_samples_leaf=3,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1
            )
        )
    ]),

    "hist_gradient_boosting": Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median")
        ),
        (
            "model",
            HistGradientBoostingClassifier(
                max_iter=300,
                learning_rate=0.05,
                max_leaf_nodes=31,
                min_samples_leaf=15,
                l2_regularization=1.0,
                random_state=42
            )
        )
    ]),
}

# ------------------------------------------------------------------
# METRICS
# ------------------------------------------------------------------

def evaluate(model, X, y):

    probability = model.predict_proba(X)[:, 1]

    prediction = (
        probability >= 0.5
    ).astype(int)

    tn, fp, fn, tp = confusion_matrix(
        y,
        prediction,
        labels=[0, 1]
    ).ravel()

    metrics = {
        "roc_auc": roc_auc_score(y, probability),
        "pr_auc": average_precision_score(y, probability),
        "accuracy": accuracy_score(y, prediction),
        "precision": precision_score(
            y,
            prediction,
            zero_division=0
        ),
        "recall": recall_score(
            y,
            prediction,
            zero_division=0
        ),
        "f1": f1_score(
            y,
            prediction,
            zero_division=0
        ),
        "brier_score": brier_score_loss(
            y,
            probability
        ),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }

    return metrics, probability


results = []
trained_models = {}

# ------------------------------------------------------------------
# TRAIN
# ------------------------------------------------------------------

for name, model in models.items():

    print("\n" + "=" * 110)
    print(f"TRAINING: {name}")
    print("=" * 110)

    model.fit(
        X_train,
        y_train
    )

    trained_models[name] = model

    train_metrics, _ = evaluate(
        model,
        X_train,
        y_train
    )

    val_metrics, _ = evaluate(
        model,
        X_val,
        y_val
    )

    test_metrics, _ = evaluate(
        model,
        X_test,
        y_test
    )

    print("\nTRAIN")
    print(train_metrics)

    print("\nVALIDATION")
    print(val_metrics)

    print("\nTEST")
    print(test_metrics)

    for split_name, metrics in [
        ("train", train_metrics),
        ("validation", val_metrics),
        ("test", test_metrics),
    ]:

        row = {
            "model": name,
            "split": split_name,
        }

        row.update(metrics)

        results.append(row)

# ------------------------------------------------------------------
# SAVE METRICS
# ------------------------------------------------------------------

results_df = pd.DataFrame(results)

metrics_path = OUT / "baseline_metrics.csv"

results_df.to_csv(
    metrics_path,
    index=False
)

# ------------------------------------------------------------------
# SELECT BEST MODEL
# ------------------------------------------------------------------

validation_results = results_df[
    results_df["split"] == "validation"
].copy()

validation_results = validation_results.sort_values(
    "pr_auc",
    ascending=False
)

best_model_name = validation_results.iloc[0]["model"]

print("\n" + "=" * 110)
print("MODEL COMPARISON")
print("=" * 110)

print(
    validation_results[
        [
            "model",
            "roc_auc",
            "pr_auc",
            "precision",
            "recall",
            "f1",
            "brier_score",
        ]
    ].to_string(index=False)
)

print("\nBEST BASELINE MODEL")
print("-" * 110)
print(best_model_name)

# ------------------------------------------------------------------
# SAVE BEST MODEL
# ------------------------------------------------------------------

import joblib

best_model = trained_models[best_model_name]

model_path = OUT / "best_baseline_model.joblib"

joblib.dump(
    best_model,
    model_path
)

# ------------------------------------------------------------------
# SAVE FEATURE CONTRACT
# ------------------------------------------------------------------

feature_contract = {
    "phase": "16",
    "model_type": best_model_name,
    "target": TARGET,
    "feature_count": len(feature_columns),
    "features": feature_columns,
    "metadata_columns": META_COLUMNS,
    "train_rows": len(train),
    "validation_rows": len(validation),
    "test_rows": len(test),
}

with open(
    OUT / "feature_contract.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        feature_contract,
        f,
        indent=2
    )

# ------------------------------------------------------------------
# FINAL REPORT
# ------------------------------------------------------------------

report = []

report.append(
    "CHETAKAI V1 — PHASE 16 BASELINE MODEL REPORT"
)

report.append("=" * 80)

report.append(
    f"Model features : {len(feature_columns)}"
)

report.append(
    f"Target         : {TARGET}"
)

report.append(
    f"Best model     : {best_model_name}"
)

report.append("")

for _, r in validation_results.iterrows():

    report.append(
        f"{r['model']}: "
        f"PR-AUC={r['pr_auc']:.4f}, "
        f"ROC-AUC={r['roc_auc']:.4f}, "
        f"F1={r['f1']:.4f}, "
        f"Recall={r['recall']:.4f}, "
        f"Precision={r['precision']:.4f}"
    )

with open(
    OUT / "phase16_report.txt",
    "w",
    encoding="utf-8"
) as f:
    f.write("\n".join(report))

print("\n" + "=" * 110)
print("PHASE 16 COMPLETE")
print("=" * 110)

print("Metrics :", metrics_path)
print("Model   :", model_path)
print("Contract:", OUT / "feature_contract.json")
print("Report  :", OUT / "phase16_report.txt")

print("=" * 110)