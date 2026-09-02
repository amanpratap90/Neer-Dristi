from pathlib import Path
import json
import warnings

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

warnings.filterwarnings("ignore")


ROOT = Path("data/processed/master")
PHASE12_DIR = ROOT / "phase12"
PHASE13_DIR = ROOT / "phase13"
PHASE13B_DIR = PHASE13_DIR / "phase13b"

MODEL_DIR = PHASE13B_DIR / "models"
REPORT_DIR = PHASE13B_DIR / "reports"
PRED_DIR = PHASE13B_DIR / "predictions"

X_TRAIN = PHASE12_DIR / "X_train.csv"
X_VAL = PHASE12_DIR / "X_validation.csv"
X_TEST = PHASE12_DIR / "X_test.csv"

Y_TRAIN = PHASE12_DIR / "y_train.csv"
Y_VAL = PHASE12_DIR / "y_validation.csv"
Y_TEST = PHASE12_DIR / "y_test.csv"

RESULTS_FILE = REPORT_DIR / "phase13b_ablation_results.csv"
FEATURE_GROUP_FILE = REPORT_DIR / "phase13b_feature_groups.csv"
YEAR_ANALYSIS_FILE = REPORT_DIR / "phase13b_year_analysis.csv"
BEST_MANIFEST_FILE = MODEL_DIR / "phase13b_best_model_manifest.json"
BEST_FEATURE_FILE = MODEL_DIR / "phase13b_best_model_features.json"
BEST_MODEL_FILE = MODEL_DIR / "chetakai_v1_flood_classifier_phase13b_best.joblib"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
PRED_DIR.mkdir(parents=True, exist_ok=True)


print("=" * 110)
print("CHETAKAI V1 — PHASE 13B CLASSIFIER ABLATION & ROBUSTNESS")
print("=" * 110)


# ------------------------------------------------------------------
# LOAD
# ------------------------------------------------------------------

print("\nLOADING FROZEN PHASE 12 DATA")
print("-" * 110)

X_train = pd.read_csv(X_TRAIN)
X_val = pd.read_csv(X_VAL)
X_test = pd.read_csv(X_TEST)

y_train = pd.read_csv(Y_TRAIN)["target_flood"].astype(int)
y_val = pd.read_csv(Y_VAL)["target_flood"].astype(int)
y_test = pd.read_csv(Y_TEST)["target_flood"].astype(int)

print("X_train:", X_train.shape)
print("X_val  :", X_val.shape)
print("X_test :", X_test.shape)


# ------------------------------------------------------------------
# SAFETY
# ------------------------------------------------------------------

if list(X_train.columns) != list(X_val.columns):
    raise ValueError("TRAIN/VALIDATION feature mismatch.")

if list(X_train.columns) != list(X_test.columns):
    raise ValueError("TRAIN/TEST feature mismatch.")

if "target_flood" in X_train.columns:
    raise ValueError("Target leakage detected.")

if X_train.isna().any().any():
    raise ValueError("NaNs found in X_train.")

if X_val.isna().any().any():
    raise ValueError("NaNs found in X_validation.")

if X_test.isna().any().any():
    raise ValueError("NaNs found in X_test.")

print("Feature alignment : PASS")
print("NaN safety        : PASS")
print("Target leakage    : PASS")


# ------------------------------------------------------------------
# FEATURE GROUPING
# ------------------------------------------------------------------

def classify_feature(name):

    n = name.lower()

    if n in {
        "year",
        "month",
        "month_sin",
        "month_cos",
    }:
        return "TEMPORAL"

    if n.startswith("radar_"):
        return "RADAR_PROXY"

    if n.startswith("nwp_"):
        return "NWP_PROXY"

    if n.startswith("obs_"):
        return "OBSERVATIONAL_PROXY"

    if n.startswith("satellite_"):
        return "SATELLITE_PROXY"

    if n.startswith("rainfall_"):
        return "RAINFALL"

    if n in {
        "rainfall_sum_mm",
        "annual_rainfall_mm",
        "rainfall_mean_mm",
        "rainfall_std_mm",
        "rainfall_max_mm",
        "rainfall_min_mm",
        "rainfall_p90_mm",
        "rainfall_p95_mm",
        "rainfall_p99_mm",
        "rainfall_anomaly_mm",
        "rainfall_anomaly_pct",
        "rainfall_lag_1_month_mm",
        "rainfall_lag_2_month_mm",
        "rainfall_lag_3_month_mm",
        "rainfall_3month_sum_mm",
        "rainfall_6month_sum_mm",
        "rainfall_12month_sum_mm",
    }:
        return "RAINFALL"

    if any(
        token in n
        for token in [
            "elevation",
            "slope",
            "relief",
            "flow_accumulation",
            "distance_to_river",
            "river_area",
            "river_length",
            "river_density",
            "basin_area",
            "terrain",
            "drainage",
        ]
    ):
        return "TERRAIN_HYDROLOGY"

    if any(
        token in n
        for token in [
            "river_",
            "reservoir",
            "runoff",
            "hydrological",
            "wetness",
        ]
    ):
        return "TERRAIN_HYDROLOGY"

    if any(
        token in n
        for token in [
            "sand",
            "clay",
            "silt",
            "soil",
            "soc_",
            "bdod",
            "phh2o",
            "cec_",
            "cfvo",
        ]
    ):
        return "SOIL"

    if any(
        token in n
        for token in [
            "population",
            "building",
            "road",
            "rail",
            "bridge",
            "school",
            "hospital",
            "infrastructure",
            "adm1",
            "adm2",
        ]
    ):
        return "EXPOSURE"

    if any(
        token in n
        for token in [
            "tree_",
            "shrub",
            "grass",
            "crop",
            "built_up",
            "water_pct",
            "wetland",
            "natural_vegetation",
            "lulc",
            "land_cover",
        ]
    ):
        return "LULC"

    return "ENVIRONMENTAL"


feature_groups = {}

for feature in X_train.columns:
    feature_groups[feature] = classify_feature(feature)

feature_group_df = pd.DataFrame(
    [
        {
            "feature": feature,
            "group": group,
        }
        for feature, group in feature_groups.items()
    ]
)

feature_group_df.to_csv(
    FEATURE_GROUP_FILE,
    index=False,
)

print("\nFEATURE GROUPS")
print("-" * 110)

for group, subset in feature_group_df.groupby("group"):
    print(f"{group:<25}: {len(subset)}")


# ------------------------------------------------------------------
# EXPERIMENT DEFINITIONS
# ------------------------------------------------------------------

groups = {
    group: [
        feature
        for feature, assigned_group in feature_groups.items()
        if assigned_group == group
    ]
    for group in set(feature_groups.values())
}


def combine(*group_names):

    features = []

    for group_name in group_names:
        features.extend(groups.get(group_name, []))

    return list(dict.fromkeys(features))


experiments = {
    "01_rainfall_only": combine(
        "RAINFALL",
    ),

    "02_rainfall_terrain": combine(
        "RAINFALL",
        "TERRAIN_HYDROLOGY",
    ),

    "03_rainfall_terrain_soil": combine(
        "RAINFALL",
        "TERRAIN_HYDROLOGY",
        "SOIL",
    ),

    "04_plus_lulc": combine(
        "RAINFALL",
        "TERRAIN_HYDROLOGY",
        "SOIL",
        "LULC",
    ),

    "05_plus_exposure": combine(
        "RAINFALL",
        "TERRAIN_HYDROLOGY",
        "SOIL",
        "LULC",
        "EXPOSURE",
    ),

    "06_plus_observation_proxy": combine(
        "RAINFALL",
        "TERRAIN_HYDROLOGY",
        "SOIL",
        "LULC",
        "EXPOSURE",
        "OBSERVATIONAL_PROXY",
    ),

    "07_plus_nwp_proxy": combine(
        "RAINFALL",
        "TERRAIN_HYDROLOGY",
        "SOIL",
        "LULC",
        "EXPOSURE",
        "OBSERVATIONAL_PROXY",
        "NWP_PROXY",
    ),

    "08_plus_radar_proxy": combine(
        "RAINFALL",
        "TERRAIN_HYDROLOGY",
        "SOIL",
        "LULC",
        "EXPOSURE",
        "OBSERVATIONAL_PROXY",
        "NWP_PROXY",
        "RADAR_PROXY",
    ),

    "09_full_without_temporal": combine(
        "RAINFALL",
        "TERRAIN_HYDROLOGY",
        "SOIL",
        "LULC",
        "EXPOSURE",
        "OBSERVATIONAL_PROXY",
        "NWP_PROXY",
        "RADAR_PROXY",
        "SATELLITE_PROXY",
        "ENVIRONMENTAL",
    ),

    "10_full_with_temporal": combine(
        "RAINFALL",
        "TERRAIN_HYDROLOGY",
        "SOIL",
        "LULC",
        "EXPOSURE",
        "OBSERVATIONAL_PROXY",
        "NWP_PROXY",
        "RADAR_PROXY",
        "SATELLITE_PROXY",
        "ENVIRONMENTAL",
        "TEMPORAL",
    ),
}


# Remove accidental empty experiments/features
experiments = {
    name: [
        f for f in features
        if f in X_train.columns
    ]
    for name, features in experiments.items()
}


# ------------------------------------------------------------------
# TRAIN FUNCTION
# ------------------------------------------------------------------

def train_model(features):

    model = RandomForestClassifier(
        n_estimators=500,
        max_depth=None,
        min_samples_split=4,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    model.fit(
        X_train[features],
        y_train,
    )

    probability = model.predict_proba(
        X_val[features]
    )[:, 1]

    prediction = (
        probability >= 0.50
    ).astype(int)

    metrics = {
        "features": len(features),
        "roc_auc": roc_auc_score(
            y_val,
            probability,
        ),
        "pr_auc": average_precision_score(
            y_val,
            probability,
        ),
        "accuracy": accuracy_score(
            y_val,
            prediction,
        ),
        "precision": precision_score(
            y_val,
            prediction,
            zero_division=0,
        ),
        "recall": recall_score(
            y_val,
            prediction,
            zero_division=0,
        ),
        "f1": f1_score(
            y_val,
            prediction,
            zero_division=0,
        ),
    }

    return model, probability, prediction, metrics


# ------------------------------------------------------------------
# ABLATION
# ------------------------------------------------------------------

print("\n")
print("=" * 110)
print("FEATURE ABLATION EXPERIMENTS")
print("=" * 110)

results = []
trained_models = {}

for experiment_name, features in experiments.items():

    print("\n" + "-" * 110)
    print(experiment_name)
    print("Features:", len(features))

    if not features:
        print("SKIPPED — no features")
        continue

    model, probability, prediction, metrics = train_model(
        features
    )

    trained_models[experiment_name] = (
        model,
        features,
        probability,
        prediction,
    )

    print(
        f"ROC-AUC={metrics['roc_auc']:.4f} | "
        f"PR-AUC={metrics['pr_auc']:.4f} | "
        f"Precision={metrics['precision']:.4f} | "
        f"Recall={metrics['recall']:.4f} | "
        f"F1={metrics['f1']:.4f}"
    )

    results.append(
        {
            "experiment": experiment_name,
            **metrics,
        }
    )


results_df = pd.DataFrame(results)

results_df = results_df.sort_values(
    "pr_auc",
    ascending=False,
)

results_df.to_csv(
    RESULTS_FILE,
    index=False,
)


# ------------------------------------------------------------------
# YEAR DEPENDENCE
# ------------------------------------------------------------------

print("\n")
print("=" * 110)
print("YEAR DEPENDENCE ANALYSIS")
print("=" * 110)

year_rows = []

for year in sorted(
    pd.read_csv(Y_TRAIN)["timestamp"]
    .pipe(pd.to_datetime)
    .dt.year
    .unique()
):

    mask = (
        pd.to_datetime(
            pd.read_csv(Y_TRAIN)["timestamp"]
        ).dt.year == year
    )

    year_rows.append(
        {
            "year": int(year),
            "rows": int(mask.sum()),
            "floods": int(y_train[mask].sum()),
            "flood_rate": float(y_train[mask].mean()),
        }
    )

year_analysis = pd.DataFrame(year_rows)

year_analysis.to_csv(
    YEAR_ANALYSIS_FILE,
    index=False,
)

print(year_analysis.to_string(index=False))


# ------------------------------------------------------------------
# BEST MODEL
# ------------------------------------------------------------------

if len(results_df) == 0:
    raise ValueError("No valid experiments completed.")

best_experiment = results_df.iloc[0]["experiment"]

best_model, best_features, best_probability, best_prediction = (
    trained_models[best_experiment]
)

best_row = results_df.iloc[0]

print("\n")
print("=" * 110)
print("BEST ABLATION MODEL")
print("=" * 110)

print("Experiment :", best_experiment)
print("Features   :", len(best_features))
print(f"ROC-AUC    : {best_row['roc_auc']:.4f}")
print(f"PR-AUC     : {best_row['pr_auc']:.4f}")
print(f"Precision  : {best_row['precision']:.4f}")
print(f"Recall     : {best_row['recall']:.4f}")
print(f"F1         : {best_row['f1']:.4f}")


# ------------------------------------------------------------------
# SAVE BEST MODEL
# ------------------------------------------------------------------

joblib.dump(
    best_model,
    BEST_MODEL_FILE,
)

with open(
    BEST_FEATURE_FILE,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        best_features,
        f,
        indent=2,
    )

manifest = {
    "project": "ChetakAI V1",
    "phase": "13B",
    "model_type": "Flood classifier",
    "algorithm": "RandomForestClassifier",
    "experiment": best_experiment,
    "features": len(best_features),
    "training_period": "2015-2022",
    "validation_period": "2023-2024",
    "test_period": "2025",
    "validation_roc_auc": float(best_row["roc_auc"]),
    "validation_pr_auc": float(best_row["pr_auc"]),
    "validation_precision": float(best_row["precision"]),
    "validation_recall": float(best_row["recall"]),
    "validation_f1": float(best_row["f1"]),
    "test_positive_labels": int(y_test.sum()),
    "persistent_model": True,
    "phase12_modified": False,
    "phase13a_modified": False,
    "proxy_features_present": True,
    "proxy_features_are_real_observations": False,
}

with open(
    BEST_MANIFEST_FILE,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        manifest,
        f,
        indent=2,
    )


# ------------------------------------------------------------------
# BEST VALIDATION PREDICTIONS
# ------------------------------------------------------------------

best_predictions = pd.read_csv(Y_VAL).copy()

best_predictions["flood_probability"] = (
    best_probability
)

best_predictions["flood_prediction"] = (
    best_prediction
)

best_predictions.to_csv(
    PRED_DIR / "phase13b_best_validation_predictions.csv",
    index=False,
)


# ------------------------------------------------------------------
# FINAL
# ------------------------------------------------------------------

print("\n")
print("=" * 110)
print("PHASE 13B FINAL VALIDATION")
print("=" * 110)

print("\nAblation experiments completed :", len(results_df))
print("Best experiment                :", best_experiment)
print("Best feature count             :", len(best_features))
print(f"Best validation ROC-AUC        : {best_row['roc_auc']:.4f}")
print(f"Best validation PR-AUC         : {best_row['pr_auc']:.4f}")
print(f"Best validation Precision      : {best_row['precision']:.4f}")
print(f"Best validation Recall         : {best_row['recall']:.4f}")
print(f"Best validation F1             : {best_row['f1']:.4f}")

print("\nMODEL PERSISTENCE")
print("-" * 110)
print("Best model saved               : PASS")
print("Reusable without retraining   : YES")
print("Phase 12 modified             : NO")
print("Phase 13A modified            : NO")

print("\nOUTPUTS")
print("-" * 110)

print("Ablation results:")
print(RESULTS_FILE)

print("\nFeature groups:")
print(FEATURE_GROUP_FILE)

print("\nYear analysis:")
print(YEAR_ANALYSIS_FILE)

print("\nBest model:")
print(BEST_MODEL_FILE)

print("\nBest model feature schema:")
print(BEST_FEATURE_FILE)

print("\nBest model manifest:")
print(BEST_MANIFEST_FILE)

print("\nBest validation predictions:")
print(
    PRED_DIR
    / "phase13b_best_validation_predictions.csv"
)

print("\n")
print("=" * 110)
print("🔥 PHASE 13B PASS — CLASSIFIER ABLATION COMPLETE")
print("=" * 110)