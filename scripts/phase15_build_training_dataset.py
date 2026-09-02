from pathlib import Path
import json
import math
import pandas as pd


ROOT = Path("data")
PROCESSED = ROOT / "processed"
MASTER = PROCESSED / "master"

MASTER_PHASE12 = (
    MASTER
    / "phase12"
    / "chetakai_v1_master_phase12.csv"
)

OUTPUT_DIR = PROCESSED / "training" / "phase15"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRAINING_MASTER_CSV = OUTPUT_DIR / "chetakai_v1_training_master.csv"
TRAIN_CSV = OUTPUT_DIR / "train.csv"
VALIDATION_CSV = OUTPUT_DIR / "validation.csv"
TEST_CSV = OUTPUT_DIR / "test.csv"
FEATURE_MANIFEST_JSON = OUTPUT_DIR / "feature_manifest.json"
REPORT_TXT = OUTPUT_DIR / "phase15_training_report.txt"


TARGET = "target_flood"

IDENTITY_COLUMNS = [
    "canonical_basin_id",
    "basin",
    "basin_name",
    "timestamp",
    "date",
]

LEAKAGE_COLUMNS = [
    "target_flood",
    "flood_event_flag",
    "flood_event_count",
    "flood_severity_score",
    "flood_area_affected",
    "flood_fatalities",
    "flood_injured",
    "flood_displaced",
    "flood_animal_fatalities",
    "flood_duration_days",
]

NON_FEATURE_COLUMNS = set(
    IDENTITY_COLUMNS
    + LEAKAGE_COLUMNS
)


def safe_float(value):
    try:
        value = float(value)
        if math.isfinite(value):
            return value
    except Exception:
        pass
    return None


def main():

    print("=" * 110)
    print("CHETAKAI V1 — PHASE 15 TRAINING DATASET BUILDER")
    print("=" * 110)

    print("\nLOADING PHASE 12 MASTER")
    print("-" * 110)

    if not MASTER_PHASE12.exists():
        raise FileNotFoundError(
            f"Phase 12 master not found: {MASTER_PHASE12}"
        )

    df = pd.read_csv(
        MASTER_PHASE12,
        low_memory=False
    )

    print(f"Input dataset : {MASTER_PHASE12}")
    print(f"Rows          : {len(df)}")
    print(f"Columns       : {len(df.columns)}")

    # ------------------------------------------------------------------
    # REQUIRED COLUMNS
    # ------------------------------------------------------------------

    required_columns = [
        TARGET,
        "timestamp",
        "canonical_basin_id",
    ]

    missing_required = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_required:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing_required)
        )

    # ------------------------------------------------------------------
    # TIMESTAMP
    # ------------------------------------------------------------------

    print("\nTIMESTAMP VALIDATION")
    print("-" * 110)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    invalid_timestamps = int(
        df["timestamp"].isna().sum()
    )

    if invalid_timestamps:
        raise ValueError(
            f"Invalid timestamps detected: {invalid_timestamps}"
        )

    df = df.sort_values(
        ["canonical_basin_id", "timestamp"]
    ).reset_index(drop=True)

    print(
        f"Date range : "
        f"{df['timestamp'].min().date()} -> "
        f"{df['timestamp'].max().date()}"
    )

    # ------------------------------------------------------------------
    # TARGET VALIDATION
    # ------------------------------------------------------------------

    print("\nTARGET VALIDATION")
    print("-" * 110)

    target_numeric = pd.to_numeric(
        df[TARGET],
        errors="coerce"
    )

    invalid_target = int(
        target_numeric.isna().sum()
    )

    if invalid_target:
        raise ValueError(
            f"Invalid target values detected: {invalid_target}"
        )

    df[TARGET] = target_numeric.astype(int)

    invalid_target_values = sorted(
        set(df[TARGET].unique()) - {0, 1}
    )

    if invalid_target_values:
        raise ValueError(
            "Target must be binary 0/1. "
            f"Found: {invalid_target_values}"
        )

    target_distribution = (
        df[TARGET]
        .value_counts()
        .sort_index()
        .to_dict()
    )

    print(
        f"Target 0 : "
        f"{target_distribution.get(0, 0)}"
    )

    print(
        f"Target 1 : "
        f"{target_distribution.get(1, 0)}"
    )

    positive_rate = (
        df[TARGET].mean() * 100
        if len(df)
        else 0
    )

    print(
        f"Flood rate: {positive_rate:.2f}%"
    )

    # ------------------------------------------------------------------
    # DUPLICATE IDENTITY CHECK
    # ------------------------------------------------------------------

    print("\nIDENTITY CHECK")
    print("-" * 110)

    identity_check_columns = [
        column
        for column in [
            "canonical_basin_id",
            "timestamp",
        ]
        if column in df.columns
    ]

    duplicate_identity_rows = int(
        df.duplicated(
            subset=identity_check_columns
        ).sum()
    )

    print(
        f"Duplicate basin/timestamp rows : "
        f"{duplicate_identity_rows}"
    )

    if duplicate_identity_rows:
        raise ValueError(
            "Duplicate basin/timestamp observations detected."
        )

    # ------------------------------------------------------------------
    # MONTHLY CONTINUITY
    # ------------------------------------------------------------------

    print("\nTEMPORAL CONTINUITY")
    print("-" * 110)

    continuity_problems = []

    for basin_id, basin_df in df.groupby(
        "canonical_basin_id"
    ):

        dates = (
            basin_df["timestamp"]
            .sort_values()
            .dt.to_period("M")
        )

        expected = pd.period_range(
            dates.min(),
            dates.max(),
            freq="M"
        )

        if len(dates) != len(expected) or not dates.equals(
            pd.Series(expected)
        ):
            continuity_problems.append(
                str(basin_id)
            )

    print(
        f"Basins checked : "
        f"{df['canonical_basin_id'].nunique()}"
    )

    print(
        f"Basins with continuity problems : "
        f"{len(continuity_problems)}"
    )

    if continuity_problems:
        print(
            "WARNING — continuity problems detected:"
        )
        for basin in continuity_problems:
            print(f"  - {basin}")

    # ------------------------------------------------------------------
    # LEAKAGE SCREEN
    # ------------------------------------------------------------------

    print("\nLEAKAGE SCREEN")
    print("-" * 110)

    leakage_present = [
        column
        for column in LEAKAGE_COLUMNS
        if column in df.columns
    ]

    print(
        f"Leakage/target-related columns found : "
        f"{len(leakage_present)}"
    )

    for column in leakage_present:
        print(f"  - {column}")

    # ------------------------------------------------------------------
    # BUILD FEATURE LIST
    # ------------------------------------------------------------------

    feature_columns = [
        column
        for column in df.columns
        if column not in NON_FEATURE_COLUMNS
    ]

    # Remove obviously non-modelable object fields except useful
    # categorical basin metadata retained separately.
    categorical_features = []
    numeric_features = []

    for column in feature_columns:

        if pd.api.types.is_numeric_dtype(
            df[column]
        ):
            numeric_features.append(column)

        else:
            categorical_features.append(column)

    print("\nFEATURE INVENTORY")
    print("-" * 110)

    print(
        f"Total candidate features : "
        f"{len(feature_columns)}"
    )

    print(
        f"Numeric features          : "
        f"{len(numeric_features)}"
    )

    print(
        f"Non-numeric features      : "
        f"{len(categorical_features)}"
    )

    if categorical_features:
        print("\nNon-numeric candidate features:")
        for column in categorical_features:
            print(f"  - {column}")

    # ------------------------------------------------------------------
    # REMOVE PURELY IDENTIFIER-LIKE / NON-PREDICTIVE COLUMNS
    # ------------------------------------------------------------------

    additional_exclusions = []

    for column in categorical_features:

        if column in [
            "basin_name",
            "basin",
        ]:
            additional_exclusions.append(column)

    feature_columns = [
        column
        for column in feature_columns
        if column not in additional_exclusions
    ]

    numeric_features = [
        column
        for column in numeric_features
        if column in feature_columns
    ]

    print(
        f"\nFinal numeric model features : "
        f"{len(numeric_features)}"
    )

    # ------------------------------------------------------------------
    # FEATURE QUALITY
    # ------------------------------------------------------------------

    print("\nFEATURE QUALITY")
    print("-" * 110)

    feature_quality = []

    for column in feature_columns:

        series = df[column]

        missing_count = int(
            series.isna().sum()
        )

        missing_pct = (
            missing_count / len(df) * 100
            if len(df)
            else 0
        )

        infinite_count = 0

        if pd.api.types.is_numeric_dtype(series):

            infinite_count = int(
                (~series.replace(
                    [float("inf"), float("-inf")],
                    pd.NA
                ).notna()).sum()
            )

            finite_series = series.replace(
                [float("inf"), float("-inf")],
                pd.NA
            ).dropna()

            minimum = (
                safe_float(finite_series.min())
                if len(finite_series)
                else None
            )

            maximum = (
                safe_float(finite_series.max())
                if len(finite_series)
                else None
            )

            mean = (
                safe_float(finite_series.mean())
                if len(finite_series)
                else None
            )

            std = (
                safe_float(finite_series.std())
                if len(finite_series)
                else None
            )

        else:

            minimum = None
            maximum = None
            mean = None
            std = None

        unique_count = int(
            series.nunique(dropna=True)
        )

        feature_quality.append({
            "feature": column,
            "dtype": str(series.dtype),
            "missing_count": missing_count,
            "missing_pct": round(
                missing_pct,
                4
            ),
            "infinite_count": infinite_count,
            "unique_count": unique_count,
            "constant": unique_count <= 1,
            "min": minimum,
            "max": maximum,
            "mean": mean,
            "std": std,
        })

    feature_quality_df = pd.DataFrame(
        feature_quality
    )

    constant_features = (
        feature_quality_df[
            feature_quality_df["constant"]
        ]["feature"]
        .tolist()
    )

    high_missing_features = (
        feature_quality_df[
            feature_quality_df["missing_pct"] >= 50
        ]["feature"]
        .tolist()
    )

    infinite_features = (
        feature_quality_df[
            feature_quality_df["infinite_count"] > 0
        ]["feature"]
        .tolist()
    )

    print(
        f"Constant features       : "
        f"{len(constant_features)}"
    )

    print(
        f"≥50% missing features   : "
        f"{len(high_missing_features)}"
    )

    print(
        f"Features with infinity  : "
        f"{len(infinite_features)}"
    )

    # ------------------------------------------------------------------
    # DROP CONSTANT FEATURES
    # ------------------------------------------------------------------

    dropped_constant_features = []

    if constant_features:

        dropped_constant_features = (
            constant_features.copy()
        )

        feature_columns = [
            column
            for column in feature_columns
            if column not in constant_features
        ]

        numeric_features = [
            column
            for column in numeric_features
            if column not in constant_features
        ]

    # ------------------------------------------------------------------
    # TEMPORAL SPLIT
    # ------------------------------------------------------------------

    print("\nTEMPORAL TRAIN / VALIDATION / TEST SPLIT")
    print("-" * 110)

    train_end = pd.Timestamp(
        "2021-12-01"
    )

    validation_end = pd.Timestamp(
        "2023-12-01"
    )

    train_df = df[
        df["timestamp"] <= train_end
    ].copy()

    validation_df = df[
        (df["timestamp"] > train_end)
        & (df["timestamp"] <= validation_end)
    ].copy()

    test_df = df[
        df["timestamp"] > validation_end
    ].copy()

    if train_df.empty:
        raise ValueError(
            "Training split is empty."
        )

    if validation_df.empty:
        raise ValueError(
            "Validation split is empty."
        )

    if test_df.empty:
        raise ValueError(
            "Test split is empty."
        )

    print(
        f"TRAIN      : "
        f"{train_df['timestamp'].min().date()} -> "
        f"{train_df['timestamp'].max().date()} "
        f"({len(train_df)} rows)"
    )

    print(
        f"VALIDATION : "
        f"{validation_df['timestamp'].min().date()} -> "
        f"{validation_df['timestamp'].max().date()} "
        f"({len(validation_df)} rows)"
    )

    print(
        f"TEST       : "
        f"{test_df['timestamp'].min().date()} -> "
        f"{test_df['timestamp'].max().date()} "
        f"({len(test_df)} rows)"
    )

    # ------------------------------------------------------------------
    # SPLIT TARGET DISTRIBUTION
    # ------------------------------------------------------------------

    print("\nSPLIT TARGET DISTRIBUTION")
    print("-" * 110)

    split_target_summary = {}

    for split_name, split_df in [
        ("train", train_df),
        ("validation", validation_df),
        ("test", test_df),
    ]:

        counts = (
            split_df[TARGET]
            .value_counts()
            .sort_index()
            .to_dict()
        )

        positives = int(
            split_df[TARGET].sum()
        )

        rate = (
            positives / len(split_df) * 100
            if len(split_df)
            else 0
        )

        split_target_summary[split_name] = {
            "rows": int(len(split_df)),
            "class_0": int(
                counts.get(0, 0)
            ),
            "class_1": int(
                counts.get(1, 0)
            ),
            "positive_rate_pct": round(
                rate,
                4
            ),
        }

        print(
            f"{split_name.upper():12} "
            f"rows={len(split_df):5d} "
            f"flood={positives:4d} "
            f"rate={rate:6.2f}%"
        )

    # ------------------------------------------------------------------
    # ENSURE NO TEMPORAL OVERLAP
    # ------------------------------------------------------------------

    if (
        train_df["timestamp"].max()
        >= validation_df["timestamp"].min()
    ):
        raise ValueError(
            "Temporal overlap between train and validation."
        )

    if (
        validation_df["timestamp"].max()
        >= test_df["timestamp"].min()
    ):
        raise ValueError(
            "Temporal overlap between validation and test."
        )

    # ------------------------------------------------------------------
    # SAVE TRAINING MASTER
    # ------------------------------------------------------------------

    training_master_columns = (
        [
            column
            for column in IDENTITY_COLUMNS
            if column in df.columns
        ]
        + feature_columns
        + [TARGET]
    )

    training_master = df[
        list(dict.fromkeys(
            training_master_columns
        ))
    ].copy()

    training_master.to_csv(
        TRAINING_MASTER_CSV,
        index=False
    )

    train_df[
        list(dict.fromkeys(
            training_master_columns
        ))
    ].to_csv(
        TRAIN_CSV,
        index=False
    )

    validation_df[
        list(dict.fromkeys(
            training_master_columns
        ))
    ].to_csv(
        VALIDATION_CSV,
        index=False
    )

    test_df[
        list(dict.fromkeys(
            training_master_columns
        ))
    ].to_csv(
        TEST_CSV,
        index=False
    )

    # ------------------------------------------------------------------
    # FEATURE MANIFEST
    # ------------------------------------------------------------------

    manifest = {
        "phase": "15",
        "purpose": (
            "Leakage-safe temporal training dataset "
            "construction for ChetakAI V1 flood classification."
        ),
        "source_dataset": str(
            MASTER_PHASE12
        ),
        "target": TARGET,
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
        "model_feature_count": int(
            len(feature_columns)
        ),
        "numeric_feature_count": int(
            len(numeric_features)
        ),
        "identity_columns": [
            column
            for column in IDENTITY_COLUMNS
            if column in df.columns
        ],
        "excluded_leakage_columns": leakage_present,
        "additional_exclusions": additional_exclusions,
        "dropped_constant_features": dropped_constant_features,
        "high_missing_features": high_missing_features,
        "infinite_features": infinite_features,
        "feature_columns": feature_columns,
        "numeric_features": numeric_features,
        "split_definition": {
            "train": "2015-01-01 through 2021-12-01",
            "validation": "2022-01-01 through 2023-12-01",
            "test": "2024-01-01 through 2025-12-01",
        },
        "split_summary": split_target_summary,
        "outputs": {
            "training_master": str(
                TRAINING_MASTER_CSV
            ),
            "train": str(
                TRAIN_CSV
            ),
            "validation": str(
                VALIDATION_CSV
            ),
            "test": str(
                TEST_CSV
            ),
            "feature_manifest": str(
                FEATURE_MANIFEST_JSON
            ),
            "report": str(
                REPORT_TXT
            ),
        },
    }

    with open(
        FEATURE_MANIFEST_JSON,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2,
            ensure_ascii=False
        )

    # ------------------------------------------------------------------
    # REPORT
    # ------------------------------------------------------------------

    report = []

    report.append("=" * 110)
    report.append(
        "CHETAKAI V1 — PHASE 15 TRAINING DATASET REPORT"
    )
    report.append("=" * 110)
    report.append("")

    report.append("SOURCE")
    report.append("-" * 110)
    report.append(
        f"Dataset : {MASTER_PHASE12}"
    )
    report.append(
        f"Rows    : {len(df)}"
    )
    report.append(
        f"Columns : {len(df.columns)}"
    )
    report.append("")

    report.append("TARGET")
    report.append("-" * 110)
    report.append(
        f"Target       : {TARGET}"
    )
    report.append(
        f"Class 0      : "
        f"{target_distribution.get(0, 0)}"
    )
    report.append(
        f"Class 1      : "
        f"{target_distribution.get(1, 0)}"
    )
    report.append(
        f"Flood rate   : "
        f"{positive_rate:.4f}%"
    )
    report.append("")

    report.append("FEATURES")
    report.append("-" * 110)
    report.append(
        f"Model features        : {len(feature_columns)}"
    )
    report.append(
        f"Numeric features      : {len(numeric_features)}"
    )
    report.append(
        f"Constant removed      : "
        f"{len(dropped_constant_features)}"
    )
    report.append(
        f"High missing features : "
        f"{len(high_missing_features)}"
    )
    report.append(
        f"Infinite features     : "
        f"{len(infinite_features)}"
    )
    report.append("")

    report.append("LEAKAGE EXCLUSIONS")
    report.append("-" * 110)

    for column in leakage_present:
        report.append(
            f"  - {column}"
        )

    report.append("")

    report.append("TEMPORAL SPLIT")
    report.append("-" * 110)

    report.append(
        "TRAIN      : 2015-01-01 -> 2021-12-01"
    )

    report.append(
        "VALIDATION : 2022-01-01 -> 2023-12-01"
    )

    report.append(
        "TEST       : 2024-01-01 -> 2025-12-01"
    )

    report.append("")

    for split_name, summary in split_target_summary.items():

        report.append(
            f"{split_name.upper():12} "
            f"rows={summary['rows']} "
            f"class0={summary['class_0']} "
            f"class1={summary['class_1']} "
            f"flood_rate={summary['positive_rate_pct']:.4f}%"
        )

    report.append("")

    report.append("IDENTITY")
    report.append("-" * 110)
    report.append(
        f"Unique basins : "
        f"{df['canonical_basin_id'].nunique()}"
    )
    report.append(
        f"Duplicate basin/timestamp rows : "
        f"{duplicate_identity_rows}"
    )
    report.append(
        f"Continuity problems : "
        f"{len(continuity_problems)}"
    )

    report.append("")

    report.append("OUTPUTS")
    report.append("-" * 110)
    report.append(
        f"Training master : {TRAINING_MASTER_CSV}"
    )
    report.append(
        f"Train           : {TRAIN_CSV}"
    )
    report.append(
        f"Validation      : {VALIDATION_CSV}"
    )
    report.append(
        f"Test            : {TEST_CSV}"
    )
    report.append(
        f"Manifest        : {FEATURE_MANIFEST_JSON}"
    )
    report.append(
        f"Report          : {REPORT_TXT}"
    )

    report.append("")
    report.append("FINAL STATUS")
    report.append("-" * 110)
    report.append(
        "PASS — Phase 15 training dataset successfully built."
    )

    REPORT_TXT.write_text(
        "\n".join(report),
        encoding="utf-8"
    )

    # ------------------------------------------------------------------
    # CONSOLE SUMMARY
    # ------------------------------------------------------------------

    print("\n" + "=" * 110)
    print("PHASE 15 COMPLETE")
    print("=" * 110)

    print(
        f"Training master : {TRAINING_MASTER_CSV}"
    )

    print(
        f"Train           : {TRAIN_CSV}"
    )

    print(
        f"Validation      : {VALIDATION_CSV}"
    )

    print(
        f"Test            : {TEST_CSV}"
    )

    print(
        f"Features        : {len(feature_columns)}"
    )

    print(
        f"Numeric         : {len(numeric_features)}"
    )

    print(
        f"Target          : {TARGET}"
    )

    print(
        f"Train rows      : {len(train_df)}"
    )

    print(
        f"Validation rows : {len(validation_df)}"
    )

    print(
        f"Test rows       : {len(test_df)}"
    )

    print("\nFINAL STATUS")
    print("-" * 110)
    print(
        "PASS — Phase 15 training dataset successfully built."
    )

    print("=" * 110)


if __name__ == "__main__":
    main()