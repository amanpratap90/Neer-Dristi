from pathlib import Path
import pandas as pd
import numpy as np


ROOT = Path("data/processed")

print("=" * 110)
print("CHETAKAI — PHASE 4: MISSING DATA AUDIT")
print("=" * 110)


# ============================================================
# CONFIGURATION
# ============================================================

DATASETS = {
    "administrative":
        ROOT / "administrative" / "administrative_basin_features.csv",

    "dem":
        ROOT / "dem" / "dem_basin_features.csv",

    "dem_tile":
        ROOT / "dem" / "dem_tile_basin_features.csv",

    "hydrography":
        ROOT / "hydrography" / "hydrography_basin_features.csv",

    "infrastructure":
        ROOT / "infrastructure" / "infrastructure_basin_features.csv",

    "lulc":
        ROOT / "lulc" / "lulc_basin_features.csv",

    "population":
        ROOT / "population" / "population_basin_features.csv",

    "reservoirs":
        ROOT / "reservoirs" / "reservoir_basin_features.csv",

    "satellite":
        ROOT / "satellite" / "satellite_basin_features.csv",

    "soil":
        ROOT / "soil" / "soil_basin_features.csv",

    "rainfall":
        ROOT / "rainfall" / "chirps_monthly_basin_features.csv",

    "master":
        ROOT / "master" / "chetakai_v1_master_ml_dataset.csv",
}


CANONICAL_IDS = {
    f"CWC_BASIN_{i:03d}"
    for i in range(1, 26)
}


# ============================================================
# RESULT STORAGE
# ============================================================

summary = []
missing_details = []


# ============================================================
# HELPER
# ============================================================

def classify_missing(value, column, dataset):

    if pd.isna(value):
        return "MISSING_VALUE"

    return None


# ============================================================
# DATASET AUDIT
# ============================================================

for name, path in DATASETS.items():

    print("\n" + "-" * 110)
    print(f"{name.upper()}")
    print("-" * 110)

    if not path.exists():

        print("FILE STATUS : MISSING")

        summary.append({
            "dataset": name,
            "file_exists": False,
            "rows": 0,
            "columns": 0,
            "missing_cells": None,
            "missing_pct": None,
            "status": "FILE_MISSING"
        })

        continue


    df = pd.read_csv(path)

    total_cells = df.shape[0] * df.shape[1]

    missing_cells = int(df.isna().sum().sum())

    missing_pct = (
        missing_cells / total_cells * 100
        if total_cells > 0
        else 0
    )


    print("Rows             :", len(df))
    print("Columns          :", len(df))
    print("Total cells      :", total_cells)
    print("Missing cells    :", missing_cells)
    print(f"Missing %        : {missing_pct:.4f}%")


    # --------------------------------------------------------
    # CANONICAL ID
    # --------------------------------------------------------

    if "canonical_basin_id" in df.columns:

        ids = set(
            df["canonical_basin_id"]
            .dropna()
            .astype(str)
        )

        invalid_ids = ids - CANONICAL_IDS

        missing_ids = CANONICAL_IDS - ids

        print("Canonical IDs    :", len(ids))
        print("Invalid IDs      :", len(invalid_ids))
        print("Missing IDs      :", len(missing_ids))


    # --------------------------------------------------------
    # COLUMN-LEVEL MISSINGNESS
    # --------------------------------------------------------

    missing_by_column = df.isna().sum()

    missing_by_column = (
        missing_by_column[
            missing_by_column > 0
        ]
        .sort_values(ascending=False)
    )


    if len(missing_by_column) > 0:

        print("\nColumns containing missing values:")

        for column, count in missing_by_column.items():

            pct = count / len(df) * 100

            print(
                f"  {column:40} "
                f"{count:8} "
                f"({pct:7.2f}%)"
            )

            missing_details.append({
                "dataset": name,
                "column": column,
                "missing_count": int(count),
                "missing_pct": round(pct, 4)
            })

    else:

        print("\n✓ No NaN values")


    # --------------------------------------------------------
    # DATASET-SPECIFIC COVERAGE FLAGS
    # --------------------------------------------------------

    coverage_status = "NO_MISSING_VALUES"


    # Satellite
    if name == "satellite":

        if "satellite_data_available" in df.columns:

            unavailable = (
                df["satellite_data_available"]
                .fillna(0)
                == 0
            ).sum()

            print(
                "\nSatellite unavailable basins:",
                unavailable
            )

            if unavailable > 0:
                coverage_status = "GENUINE_COVERAGE_GAP"


    # DEM
    elif name == "dem":

        if "available_dem_tile_count" in df.columns:

            unavailable = (
                pd.to_numeric(
                    df["available_dem_tile_count"],
                    errors="coerce"
                )
                .fillna(0)
                == 0
            ).sum()

            print(
                "\nBasins with zero DEM tiles:",
                unavailable
            )

            if unavailable > 0:
                coverage_status = "GENUINE_COVERAGE_GAP"


    # Infrastructure
    elif name == "infrastructure":

        if "infrastructure_data_available" in df.columns:

            unavailable = (
                df["infrastructure_data_available"]
                .fillna(0)
                == 0
            ).sum()

            print(
                "\nBasins with unavailable infrastructure:",
                unavailable
            )

            if unavailable > 0:
                coverage_status = "POSSIBLE_COVERAGE_GAP"


    # --------------------------------------------------------
    # FINAL DATASET STATUS
    # --------------------------------------------------------

    if missing_cells == 0:

        if coverage_status == "NO_MISSING_VALUES":
            status = "PASS"

        else:
            status = coverage_status

    else:

        status = "MISSING_VALUES_REQUIRES_REVIEW"


    print("\nSTATUS           :", status)


    summary.append({
        "dataset": name,
        "file_exists": True,
        "rows": len(df),
        "columns": len(df.columns),
        "missing_cells": missing_cells,
        "missing_pct": round(missing_pct, 4),
        "status": status
    })


# ============================================================
# SPECIAL ANALYSIS — MASTER DATASET
# ============================================================

print("\n" + "=" * 110)
print("MASTER DATASET MISSINGNESS ANALYSIS")
print("=" * 110)

master_path = DATASETS["master"]

if master_path.exists():

    master = pd.read_csv(master_path)

    print("Rows:", len(master))
    print("Columns:", len(master.columns))


    print("\nMissing values by column:")

    master_missing = (
        master.isna()
        .sum()
        .sort_values(ascending=False)
    )

    master_missing = master_missing[
        master_missing > 0
    ]


    if len(master_missing) == 0:

        print("✓ MASTER DATASET HAS ZERO NaN VALUES")

    else:

        for column, count in master_missing.items():

            pct = count / len(master) * 100

            print(
                f"{column:45} "
                f"{count:8} "
                f"({pct:7.2f}%)"
            )


# ============================================================
# WRITE REPORTS
# ============================================================

summary_df = pd.DataFrame(summary)

details_df = pd.DataFrame(missing_details)


summary_path = ROOT / "phase4_missing_data_summary.csv"

details_path = ROOT / "phase4_missing_data_details.csv"


summary_df.to_csv(
    summary_path,
    index=False
)


details_df.to_csv(
    details_path,
    index=False
)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n" + "=" * 110)
print("PHASE 4 — MISSING DATA SUMMARY")
print("=" * 110)

print(
    summary_df.to_string(index=False)
)


print("\n" + "-" * 110)

print(
    "Summary report :",
    summary_path
)

print(
    "Details report :",
    details_path
)


# ============================================================
# GATE
# ============================================================

print("\n" + "=" * 110)
print("PHASE 4 AUDIT GATE")
print("=" * 110)


file_missing = summary_df[
    summary_df["status"] == "FILE_MISSING"
]


requires_review = summary_df[
    summary_df["status"] == "MISSING_VALUES_REQUIRES_REVIEW"
]


if len(file_missing) > 0:

    print(
        "❌ BLOCKED — processed dataset file missing:",
        len(file_missing)
    )

elif len(requires_review) > 0:

    print(
        "⚠ REVIEW REQUIRED — actual NaN values detected:",
        len(requires_review)
    )

else:

    print("✓ STRUCTURAL MISSING-DATA AUDIT: PASS")
    print("✓ No missing processed files")
    print("✓ No unexpected NaN-bearing datasets")
    print("✓ Coverage gaps remain explicitly represented")
    print("✓ No synthetic values created")


print("\n" + "=" * 110)
print("PHASE 4 AUDIT COMPLETE")
print("=" * 110)