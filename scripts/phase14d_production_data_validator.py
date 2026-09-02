from pathlib import Path
import json
import math
import pandas as pd


ROOT = Path("data")
PROCESSED = ROOT / "processed"
MASTER = PROCESSED / "master"
PHASE13 = MASTER / "phase13"
PRODUCTION_DIR = PHASE13 / "production"

MASTER_PHASE12 = MASTER / "phase12" / "chetakai_v1_master_phase12.csv"
CONTRACT_JSON = PRODUCTION_DIR / "production_feature_contract.json"
AVAILABILITY_CSV = PRODUCTION_DIR / "production_feature_availability.csv"

OUTPUT_DIR = PROCESSED / "phase14d"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_TXT = OUTPUT_DIR / "phase14d_validation_report.txt"
FEATURE_AUDIT_CSV = OUTPUT_DIR / "phase14d_feature_audit.csv"
ROW_QUALITY_CSV = OUTPUT_DIR / "phase14d_row_quality.csv"
MANIFEST_JSON = OUTPUT_DIR / "phase14d_final_manifest.json"


def is_numeric(series):
    return pd.api.types.is_numeric_dtype(series)


def safe_float(value):
    try:
        value = float(value)

        if math.isfinite(value):
            return value

    except Exception:
        pass

    return None


def flatten_contract(obj):
    features = []

    if isinstance(obj, dict):
        for key, value in obj.items():

            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        features.append((key, item))

            elif isinstance(value, dict):
                nested = flatten_contract(value)
                features.extend(nested)

    return features


def main():

    print("=" * 110)
    print("CHETAKAI V1 — PHASE 14D PRODUCTION DATA VALIDATOR")
    print("=" * 110)

    print("\nLOADING INPUTS")
    print("-" * 110)

    if not MASTER_PHASE12.exists():
        raise FileNotFoundError(
            f"Phase 12 master not found: {MASTER_PHASE12}"
        )

    if not CONTRACT_JSON.exists():
        raise FileNotFoundError(
            f"Production feature contract not found: {CONTRACT_JSON}"
        )

    df = pd.read_csv(
        MASTER_PHASE12,
        low_memory=False
    )

    with open(
        CONTRACT_JSON,
        "r",
        encoding="utf-8"
    ) as f:
        contract = json.load(f)

    print(f"Master dataset : {MASTER_PHASE12}")
    print(f"Rows           : {len(df)}")
    print(f"Columns        : {len(df.columns)}")
    print(f"Contract       : {CONTRACT_JSON}")

    # ------------------------------------------------------------------
    # CONTRACT
    # ------------------------------------------------------------------

    contract_features = flatten_contract(contract)

    feature_pairs = []
    seen = set()

    for group, feature in contract_features:

        if feature not in seen:
            feature_pairs.append((group, feature))
            seen.add(feature)

    contract_features_only = [
        x[1]
        for x in feature_pairs
    ]

    print("\nCONTRACT")
    print("-" * 110)
    print(f"Contract features : {len(contract_features_only)}")

    # ------------------------------------------------------------------
    # BASIC SCHEMA
    # ------------------------------------------------------------------

    duplicate_columns = (
        df.columns[
            df.columns.duplicated()
        ].tolist()
    )

    missing_contract = [
        feature
        for feature in contract_features_only
        if feature not in df.columns
    ]

    present_contract = [
        feature
        for feature in contract_features_only
        if feature in df.columns
    ]

    extra_columns = [
        column
        for column in df.columns
        if column not in contract_features_only
    ]

    # ------------------------------------------------------------------
    # FEATURE AUDIT
    # ------------------------------------------------------------------

    feature_rows = []

    for group, feature in feature_pairs:

        if feature not in df.columns:

            feature_rows.append({
                "feature": feature,
                "group": group,
                "present": False,
                "dtype": None,
                "numeric": False,
                "missing_count": None,
                "missing_pct": None,
                "infinite_count": None,
                "unique_count": None,
                "constant": None,
                "min": None,
                "max": None,
                "mean": None,
                "std": None,
            })

            continue

        series = df[feature]

        numeric = is_numeric(series)

        missing_count = int(
            series.isna().sum()
        )

        missing_pct = (
            missing_count / len(df) * 100
            if len(df) > 0
            else 0
        )

        infinite_count = 0

        if numeric:

            infinite_mask = (
                series == float("inf")
            ) | (
                series == float("-inf")
            )

            infinite_count = int(
                infinite_mask.sum()
            )

            finite_series = series[
                ~infinite_mask
            ].dropna()

            if len(finite_series):

                minimum = safe_float(
                    finite_series.min()
                )

                maximum = safe_float(
                    finite_series.max()
                )

                mean = safe_float(
                    finite_series.mean()
                )

                std = safe_float(
                    finite_series.std()
                )

            else:

                minimum = None
                maximum = None
                mean = None
                std = None

        else:

            minimum = None
            maximum = None
            mean = None
            std = None

        unique_count = int(
            series.nunique(
                dropna=True
            )
        )

        feature_rows.append({
            "feature": feature,
            "group": group,
            "present": True,
            "dtype": str(series.dtype),
            "numeric": numeric,
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

    feature_audit = pd.DataFrame(
        feature_rows
    )

    feature_audit.to_csv(
        FEATURE_AUDIT_CSV,
        index=False
    )

    # ------------------------------------------------------------------
    # ROW QUALITY
    # ------------------------------------------------------------------

    row_quality = pd.DataFrame({
        "row_index": df.index,
        "missing_values": df.isna().sum(axis=1),
        "missing_pct": df.isna().mean(axis=1) * 100,
    })

    numeric_columns = (
        df.select_dtypes(
            include="number"
        ).columns
    )

    if len(numeric_columns):

        numeric_values = df[
            numeric_columns
        ]

        infinite_mask = (
            numeric_values == float("inf")
        ) | (
            numeric_values == float("-inf")
        )

        row_quality[
            "infinite_values"
        ] = infinite_mask.sum(axis=1)

    else:

        row_quality[
            "infinite_values"
        ] = 0

    row_quality[
        "complete_row"
    ] = (
        row_quality[
            "missing_values"
        ] == 0
    )

    row_quality.to_csv(
        ROW_QUALITY_CSV,
        index=False
    )

    # ------------------------------------------------------------------
    # LOCATION / TIME
    # ------------------------------------------------------------------

    required_identity = [
        "basin_id",
        "timestamp",
        "latitude",
        "longitude",
    ]

    identity_results = {}

    for column in required_identity:

        if column not in df.columns:

            identity_results[column] = {
                "present": False,
                "missing": None,
                "invalid": None,
            }

            continue

        if column == "timestamp":

            parsed = pd.to_datetime(
                df[column],
                errors="coerce"
            )

            identity_results[column] = {
                "present": True,
                "missing": int(
                    df[column].isna().sum()
                ),
                "invalid": int(
                    parsed.isna().sum()
                ),
            }

        elif column in [
            "latitude",
            "longitude"
        ]:

            numeric = pd.to_numeric(
                df[column],
                errors="coerce"
            )

            if column == "latitude":

                invalid = (
                    numeric.isna()
                    |
                    ~numeric.between(
                        -90,
                        90
                    )
                    & df[column].notna()
                )

            else:

                invalid = (
                    numeric.isna()
                    |
                    ~numeric.between(
                        -180,
                        180
                    )
                    & df[column].notna()
                )

            identity_results[column] = {
                "present": True,
                "missing": int(
                    df[column].isna().sum()
                ),
                "invalid": int(
                    invalid.sum()
                ),
            }

        else:

            identity_results[column] = {
                "present": True,
                "missing": int(
                    df[column].isna().sum()
                ),
                "invalid": 0,
            }

    # ------------------------------------------------------------------
    # DUPLICATE ROWS
    # ------------------------------------------------------------------

    duplicate_rows = int(
        df.duplicated().sum()
    )

    identity_columns = [
        column
        for column in [
            "basin_id",
            "timestamp",
            "latitude",
            "longitude",
        ]
        if column in df.columns
    ]

    duplicate_identity_rows = 0

    if identity_columns:

        duplicate_identity_rows = int(
            df.duplicated(
                subset=identity_columns
            ).sum()
        )

    # ------------------------------------------------------------------
    # CONSTANT / HIGH-MISSING FEATURES
    # ------------------------------------------------------------------

    constant_features = (
        feature_audit[
            feature_audit["constant"] == True
        ]["feature"]
        .tolist()
    )

    high_missing_features = (
        feature_audit[
            feature_audit["missing_pct"] >= 50
        ]["feature"]
        .tolist()
    )

    infinite_features = (
        feature_audit[
            feature_audit[
                "infinite_count"
            ].fillna(0) > 0
        ]["feature"]
        .tolist()
    )

    non_numeric_features = (
        feature_audit[
            (feature_audit["present"] == True)
            &
            (feature_audit["numeric"] == False)
        ]["feature"]
        .tolist()
    )

    # ------------------------------------------------------------------
    # POTENTIAL LEAKAGE FLAGS
    # ------------------------------------------------------------------

    leakage_keywords = [
        "target",
        "label",
        "future",
        "flood_event",
        "flood_label",
        "observed_future",
        "lead_",
        "_lead",
    ]

    leakage_candidates = []

    for column in df.columns:

        name = column.lower()

        if any(
            keyword in name
            for keyword in leakage_keywords
        ):

            leakage_candidates.append(
                column
            )

    # ------------------------------------------------------------------
    # OVERALL STATUS
    # ------------------------------------------------------------------

    critical_failures = []

    if duplicate_columns:
        critical_failures.append(
            "duplicate_columns"
        )

    if missing_contract:
        critical_failures.append(
            "missing_contract_features"
        )

    timestamp_invalid = (
        identity_results
        .get("timestamp", {})
        .get("invalid")
        or 0
    )

    latitude_invalid = (
        identity_results
        .get("latitude", {})
        .get("invalid")
        or 0
    )

    longitude_invalid = (
        identity_results
        .get("longitude", {})
        .get("invalid")
        or 0
    )

    if timestamp_invalid > 0:

        critical_failures.append(
            "invalid_timestamps"
        )

    if latitude_invalid > 0:

        critical_failures.append(
            "invalid_latitudes"
        )

    if longitude_invalid > 0:

        critical_failures.append(
            "invalid_longitudes"
        )

    status = (
        "PASS"
        if not critical_failures
        else "FAIL"
    )

    # ------------------------------------------------------------------
    # REPORT
    # ------------------------------------------------------------------

    lines = []

    lines.append("=" * 110)

    lines.append(
        "CHETAKAI V1 — PHASE 14D "
        "PRODUCTION DATA VALIDATION REPORT"
    )

    lines.append("=" * 110)

    lines.append("")

    lines.append("DATASET")
    lines.append("-" * 110)

    lines.append(
        f"Rows                         : {len(df)}"
    )

    lines.append(
        f"Columns                      : {len(df.columns)}"
    )

    lines.append(
        f"Contract features            : {len(contract_features_only)}"
    )

    lines.append(
        f"Present contract features    : {len(present_contract)}"
    )

    lines.append(
        f"Missing contract features    : {len(missing_contract)}"
    )

    lines.append(
        f"Extra master columns         : {len(extra_columns)}"
    )

    lines.append("")

    lines.append("SCHEMA")
    lines.append("-" * 110)

    lines.append(
        f"Duplicate columns             : {len(duplicate_columns)}"
    )

    lines.append(
        f"Duplicate complete rows       : {duplicate_rows}"
    )

    lines.append(
        f"Duplicate identity rows       : {duplicate_identity_rows}"
    )

    lines.append("")

    lines.append("FEATURE QUALITY")
    lines.append("-" * 110)

    lines.append(
        f"Constant features             : {len(constant_features)}"
    )

    lines.append(
        f"≥50% missing features         : {len(high_missing_features)}"
    )

    lines.append(
        f"Features containing infinity  : {len(infinite_features)}"
    )

    lines.append(
        f"Non-numeric contract fields   : {len(non_numeric_features)}"
    )

    lines.append("")

    lines.append("IDENTITY / TIME")
    lines.append("-" * 110)

    for column, result in identity_results.items():

        lines.append(
            f"{column:28} "
            f"present={result['present']} "
            f"missing={result['missing']} "
            f"invalid={result['invalid']}"
        )

    lines.append("")

    lines.append("LEAKAGE SCREEN")
    lines.append("-" * 110)

    lines.append(
        f"Potential leakage candidates : "
        f"{len(leakage_candidates)}"
    )

    for column in leakage_candidates:

        lines.append(
            f"  - {column}"
        )

    lines.append("")

    lines.append("MISSING CONTRACT FEATURES")
    lines.append("-" * 110)

    if missing_contract:

        for feature in missing_contract:

            lines.append(
                f"  - {feature}"
            )

    else:

        lines.append(
            "  NONE"
        )

    lines.append("")

    lines.append("CONSTANT FEATURES")
    lines.append("-" * 110)

    if constant_features:

        for feature in constant_features:

            lines.append(
                f"  - {feature}"
            )

    else:

        lines.append(
            "  NONE"
        )

    lines.append("")

    lines.append("HIGH-MISSING FEATURES")
    lines.append("-" * 110)

    if high_missing_features:

        for feature in high_missing_features:

            lines.append(
                f"  - {feature}"
            )

    else:

        lines.append(
            "  NONE"
        )

    lines.append("")

    lines.append("FINAL VERDICT")
    lines.append("-" * 110)

    lines.append(
        f"STATUS : {status}"
    )

    if critical_failures:

        lines.append("")

        lines.append(
            "CRITICAL FAILURES:"
        )

        for failure in critical_failures:

            lines.append(
                f"  - {failure}"
            )

    else:

        lines.append("")

        lines.append(
            "No critical structural failures detected."
        )

    lines.append("")

    lines.append("OUTPUT FILES")
    lines.append("-" * 110)

    lines.append(
        f"Feature audit : {FEATURE_AUDIT_CSV}"
    )

    lines.append(
        f"Row quality   : {ROW_QUALITY_CSV}"
    )

    lines.append(
        f"Report        : {REPORT_TXT}"
    )

    lines.append(
        f"Manifest      : {MANIFEST_JSON}"
    )

    REPORT_TXT.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    # ------------------------------------------------------------------
    # MANIFEST
    # ------------------------------------------------------------------

    manifest = {

        "phase": "14D",

        "status": status,

        "master_dataset": str(
            MASTER_PHASE12
        ),

        "contract": str(
            CONTRACT_JSON
        ),

        "rows": int(
            len(df)
        ),

        "columns": int(
            len(df.columns)
        ),

        "contract_features": int(
            len(contract_features_only)
        ),

        "present_contract_features": int(
            len(present_contract)
        ),

        "missing_contract_features": int(
            len(missing_contract)
        ),

        "extra_columns": int(
            len(extra_columns)
        ),

        "duplicate_columns":
            duplicate_columns,

        "duplicate_rows":
            duplicate_rows,

        "duplicate_identity_rows":
            duplicate_identity_rows,

        "constant_features":
            constant_features,

        "high_missing_features":
            high_missing_features,

        "infinite_features":
            infinite_features,

        "non_numeric_features":
            non_numeric_features,

        "leakage_candidates":
            leakage_candidates,

        "identity_checks":
            identity_results,

        "critical_failures":
            critical_failures,

        "outputs": {

            "report":
                str(REPORT_TXT),

            "feature_audit":
                str(FEATURE_AUDIT_CSV),

            "row_quality":
                str(ROW_QUALITY_CSV),

            "manifest":
                str(MANIFEST_JSON),
        },
    }

    with open(
        MANIFEST_JSON,
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
    # CONSOLE SUMMARY
    # ------------------------------------------------------------------

    print("\nVALIDATION SUMMARY")
    print("-" * 110)

    print(
        f"Rows                         : {len(df)}"
    )

    print(
        f"Columns                      : {len(df.columns)}"
    )

    print(
        f"Contract features            : {len(contract_features_only)}"
    )

    print(
        f"Present contract features    : {len(present_contract)}"
    )

    print(
        f"Missing contract features    : {len(missing_contract)}"
    )

    print(
        f"Duplicate columns            : {len(duplicate_columns)}"
    )

    print(
        f"Duplicate rows               : {duplicate_rows}"
    )

    print(
        f"Constant features            : {len(constant_features)}"
    )

    print(
        f"≥50% missing features        : {len(high_missing_features)}"
    )

    print(
        f"Infinite features            : {len(infinite_features)}"
    )

    print(
        f"Leakage candidates           : {len(leakage_candidates)}"
    )

    print("\nFINAL STATUS")
    print("-" * 110)

    if status == "PASS":

        print(
            "PASS — Phase 14D structural validation passed."
        )

    else:

        print(
            "FAIL — Phase 14D found critical structural issues."
        )

        for failure in critical_failures:

            print(
                f"  - {failure}"
            )

    print("\nREPORTS")
    print("-" * 110)

    print(
        f"Report        : {REPORT_TXT}"
    )

    print(
        f"Feature audit : {FEATURE_AUDIT_CSV}"
    )

    print(
        f"Row quality   : {ROW_QUALITY_CSV}"
    )

    print(
        f"Manifest      : {MANIFEST_JSON}"
    )

    print("\n" + "=" * 110)


if __name__ == "__main__":
    main()