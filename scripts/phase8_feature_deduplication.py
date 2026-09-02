from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("data/processed")

MASTER = ROOT / "master" / "chetakai_v1_master_phase7.csv"
OUT = ROOT / "master" / "chetakai_v1_master_phase8.csv"

REPORT = ROOT / "master" / "phase8_deduplication_report.csv"
CORR_REPORT = ROOT / "master" / "phase8_high_correlation_report.csv"

BACKUP = ROOT / "master" / "chetakai_v1_master_phase7_backup.csv"


print("=" * 110)
print("CHETAKAI V1 — PHASE 8 FEATURE DEDUPLICATION")
print("=" * 110)


# ------------------------------------------------------------------
# LOAD MASTER
# ------------------------------------------------------------------

if not MASTER.exists():
    raise FileNotFoundError(
        f"Phase 7 master dataset not found:\n{MASTER}"
    )

df = pd.read_csv(MASTER)

print("\nINPUT DATASET")
print("-" * 110)
print("Rows:", len(df))
print("Columns:", len(df.columns))


# ------------------------------------------------------------------
# REQUIRED KEY VALIDATION
# ------------------------------------------------------------------

required_keys = [
    "canonical_basin_id",
    "timestamp",
]

missing_keys = [
    c for c in required_keys
    if c not in df.columns
]

if missing_keys:
    raise ValueError(
        f"Missing required columns: {missing_keys}"
    )


df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)

if df["timestamp"].isna().any():
    raise ValueError(
        "Invalid timestamp values detected."
    )


# ------------------------------------------------------------------
# BACKUP
# ------------------------------------------------------------------

if not BACKUP.exists():
    df.to_csv(
        BACKUP,
        index=False
    )

    print("\nPhase 7 backup created:")
    print(BACKUP.resolve())

else:
    print("\nPhase 7 backup already exists:")
    print(BACKUP.resolve())


# ------------------------------------------------------------------
# BASIC DATASET INFORMATION
# ------------------------------------------------------------------

print("\nDATASET STRUCTURE")
print("-" * 110)

print(
    "Basins:",
    df["canonical_basin_id"].nunique()
)

print(
    "Date range:",
    df["timestamp"].min(),
    "→",
    df["timestamp"].max()
)


duplicate_keys = df.duplicated(
    subset=required_keys
).sum()

print(
    "Duplicate basin/timestamp keys:",
    duplicate_keys
)

if duplicate_keys:
    raise ValueError(
        "Duplicate basin/timestamp keys detected."
    )


# ------------------------------------------------------------------
# PROTECTED COLUMNS
# ------------------------------------------------------------------

protected = {
    "canonical_basin_id",
    "timestamp",
}


feature_columns = [
    c for c in df.columns
    if c not in protected
]


# ------------------------------------------------------------------
# 1. EXACT DUPLICATE COLUMNS
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("1. EXACT DUPLICATE COLUMN DETECTION")
print("=" * 110)

duplicate_columns = []

columns = list(df.columns)

for i in range(len(columns)):

    col_a = columns[i]

    if col_a in protected:
        continue

    for j in range(i + 1, len(columns)):

        col_b = columns[j]

        if col_b in protected:
            continue

        if df[col_a].equals(df[col_b]):

            duplicate_columns.append(
                (col_a, col_b)
            )


if duplicate_columns:

    print(
        "Exact duplicate column pairs:",
        len(duplicate_columns)
    )

    for a, b in duplicate_columns:

        print(
            f"  {a} == {b}"
        )

else:

    print(
        "No exact duplicate columns found."
    )


# ------------------------------------------------------------------
# 2. CONSTANT FEATURES
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("2. CONSTANT FEATURE DETECTION")
print("=" * 110)

constant_columns = []

for col in feature_columns:

    nunique = df[col].nunique(
        dropna=False
    )

    if nunique <= 1:

        constant_columns.append(col)

        print(
            f"  CONSTANT: {col}"
        )


print(
    "Constant columns:",
    len(constant_columns)
)


# ------------------------------------------------------------------
# 3. NEAR-CONSTANT FEATURES
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("3. NEAR-CONSTANT FEATURE DETECTION")
print("=" * 110)

near_constant_columns = []

for col in feature_columns:

    counts = (
        df[col]
        .value_counts(
            dropna=False,
            normalize=True
        )
    )

    if len(counts) == 0:
        continue

    dominant_fraction = counts.iloc[0]

    if dominant_fraction >= 0.995:

        near_constant_columns.append(
            (
                col,
                float(dominant_fraction)
            )
        )

        print(
            f"  {col}: "
            f"{dominant_fraction:.4%} "
            f"dominant value"
        )


print(
    "Near-constant columns:",
    len(near_constant_columns)
)


# ------------------------------------------------------------------
# 4. NUMERIC CORRELATION ANALYSIS
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("4. HIGH-CORRELATION FEATURE ANALYSIS")
print("=" * 110)

numeric_columns = (
    df[feature_columns]
    .select_dtypes(include=[np.number])
    .columns
    .tolist()
)

print(
    "Numeric features:",
    len(numeric_columns)
)


high_corr_pairs = []

if len(numeric_columns) >= 2:

    corr = df[
        numeric_columns
    ].corr(
        method="pearson"
    )

    threshold = 0.995

    for i in range(len(numeric_columns)):

        for j in range(
            i + 1,
            len(numeric_columns)
        ):

            a = numeric_columns[i]
            b = numeric_columns[j]

            value = corr.loc[a, b]

            if (
                pd.notna(value)
                and abs(value) >= threshold
            ):

                high_corr_pairs.append(
                    (
                        a,
                        b,
                        float(value)
                    )
                )

                print(
                    f"  {a} <-> {b} "
                    f"| correlation={value:.6f}"
                )


print(
    "High-correlation pairs:",
    len(high_corr_pairs)
)


# ------------------------------------------------------------------
# 5. MISSINGNESS ANALYSIS
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("5. FEATURE MISSINGNESS")
print("=" * 110)

missingness = []

for col in feature_columns:

    null_count = int(
        df[col].isna().sum()
    )

    if null_count > 0:

        percentage = (
            null_count / len(df)
        ) * 100

        missingness.append(
            (
                col,
                null_count,
                percentage
            )
        )

        print(
            f"  {col}: "
            f"{null_count} nulls "
            f"({percentage:.2f}%)"
        )


print(
    "Features containing NULLs:",
    len(missingness)
)


# ------------------------------------------------------------------
# 6. SAFE AUTOMATIC REMOVAL
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("6. SAFE AUTOMATIC DEDUPLICATION")
print("=" * 110)

drop_columns = set()


# Exact duplicate columns
for a, b in duplicate_columns:

    if b not in protected:

        drop_columns.add(b)


# Constant columns
for col in constant_columns:

    if col not in protected:

        drop_columns.add(col)


print(
    "Columns selected for automatic removal:",
    len(drop_columns)
)


if drop_columns:

    for col in sorted(drop_columns):

        print(
            f"  DROP: {col}"
        )

else:

    print(
        "No columns require automatic removal."
    )


# ------------------------------------------------------------------
# 7. CREATE PHASE 8 DATASET
# ------------------------------------------------------------------

phase8 = df.drop(
    columns=sorted(drop_columns)
).copy()


# ------------------------------------------------------------------
# 8. FINAL SANITY CHECK
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("7. PHASE 8 DATASET VALIDATION")
print("=" * 110)

print(
    "Original columns:",
    len(df.columns)
)

print(
    "Phase 8 columns:",
    len(phase8.columns)
)

print(
    "Columns removed:",
    len(df.columns) - len(phase8.columns)
)

print(
    "Rows:",
    len(phase8)
)

print(
    "Basins:",
    phase8[
        "canonical_basin_id"
    ].nunique()
)

print(
    "Date range:",
    phase8["timestamp"].min(),
    "→",
    phase8["timestamp"].max()
)


remaining_duplicate_keys = phase8.duplicated(
    subset=required_keys
).sum()

print(
    "Duplicate basin/timestamp keys:",
    remaining_duplicate_keys
)

if remaining_duplicate_keys:

    raise RuntimeError(
        "Duplicate basin/timestamp keys appeared."
    )


# ------------------------------------------------------------------
# 9. SAVE DEDUPLICATION REPORT
# ------------------------------------------------------------------

report_rows = []

for col in sorted(drop_columns):

    reason = (
        "exact_duplicate"
        if any(
            b == col
            for _, b in duplicate_columns
        )
        else "constant"
    )

    report_rows.append(
        {
            "feature": col,
            "action": "removed",
            "reason": reason,
        }
    )


for col, fraction in near_constant_columns:

    if col not in drop_columns:

        report_rows.append(
            {
                "feature": col,
                "action": "review",
                "reason": (
                    f"near_constant_{fraction:.6f}"
                ),
            }
        )


if report_rows:

    report_df = pd.DataFrame(
        report_rows
    )

else:

    report_df = pd.DataFrame(
        columns=[
            "feature",
            "action",
            "reason",
        ]
    )


REPORT.parent.mkdir(
    parents=True,
    exist_ok=True
)

report_df.to_csv(
    REPORT,
    index=False
)


# ------------------------------------------------------------------
# 10. SAVE HIGH-CORRELATION REPORT
# ------------------------------------------------------------------

corr_rows = []

for a, b, value in high_corr_pairs:

    corr_rows.append(
        {
            "feature_a": a,
            "feature_b": b,
            "correlation": value,
            "absolute_correlation": abs(value),
            "action": "review_only",
        }
    )


if corr_rows:

    corr_df = pd.DataFrame(
        corr_rows
    )

else:

    corr_df = pd.DataFrame(
        columns=[
            "feature_a",
            "feature_b",
            "correlation",
            "absolute_correlation",
            "action",
        ]
    )


corr_df.to_csv(
    CORR_REPORT,
    index=False
)


# ------------------------------------------------------------------
# 11. SAVE PHASE 8 MASTER
# ------------------------------------------------------------------

OUT.parent.mkdir(
    parents=True,
    exist_ok=True
)

phase8.to_csv(
    OUT,
    index=False
)


# ------------------------------------------------------------------
# FINAL REPORT
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("🔥 PHASE 8 FEATURE DEDUPLICATION COMPLETE")
print("=" * 110)

print(
    "Input rows:",
    len(df)
)

print(
    "Input columns:",
    len(df.columns)
)

print(
    "Output rows:",
    len(phase8)
)

print(
    "Output columns:",
    len(phase8.columns)
)

print(
    "Removed columns:",
    len(drop_columns)
)

print(
    "Exact duplicate pairs:",
    len(duplicate_columns)
)

print(
    "Constant columns:",
    len(constant_columns)
)

print(
    "Near-constant columns:",
    len(near_constant_columns)
)

print(
    "High-correlation pairs:",
    len(high_corr_pairs)
)

print(
    "Duplicate keys:",
    phase8.duplicated(
        subset=required_keys
    ).sum()
)

print("\nOUTPUT:")
print(
    OUT.resolve()
)

print("\nREPORT:")
print(
    REPORT.resolve()
)

print("\nCORRELATION REPORT:")
print(
    CORR_REPORT.resolve()
)

print("\n" + "=" * 110)
print("🔥 PHASE 8 PASS")
print("=" * 110)
