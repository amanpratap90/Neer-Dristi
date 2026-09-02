from pathlib import Path
import pandas as pd


ROOT = Path("data/processed")

REGISTRY_FILE = ROOT / "basin_registry.csv"


DATASETS = {
    "administrative":
        "administrative/administrative_basin_features.csv",

    "dem":
        "dem/dem_basin_features.csv",

    "dem_tile":
        "dem/dem_tile_basin_features.csv",

    "hydrography":
        "hydrography/hydrography_basin_features.csv",

    "infrastructure":
        "infrastructure/infrastructure_basin_features.csv",

    "lulc":
        "lulc/lulc_basin_features.csv",

    "population":
        "population/population_basin_features.csv",

    "reservoirs":
        "reservoirs/reservoir_basin_features.csv",

    "satellite":
        "satellite/satellite_basin_features.csv",

    "soil":
        "soil/soil_basin_features.csv",

    "rainfall":
        "rainfall/chirps_monthly_basin_features.csv",

    "master":
        "master/chetakai_v1_master_ml_dataset.csv",
}


print("=" * 110)
print("CHETAKAI — PHASE 3.3: CROSS-DATASET STRUCTURAL CONTRACT")
print("=" * 110)


# ================================================================
# 1. LOAD REGISTRY
# ================================================================

print("\n[1/5] Loading canonical registry...")

registry = pd.read_csv(REGISTRY_FILE)

registry_ids = set(
    registry["canonical_basin_id"]
    .dropna()
    .astype(str)
)

print(f"Registry rows         : {len(registry)}")
print(f"Canonical basin IDs   : {len(registry_ids)}")

if len(registry_ids) != 25:
    raise RuntimeError(
        "Registry does not contain exactly 25 canonical basin IDs."
    )

print("✓ Registry contract PASS")


# ================================================================
# 2. DATASET VALIDATION
# ================================================================

print("\n[2/5] Validating all processed datasets...")

results = []


for name, relative_path in DATASETS.items():

    path = ROOT / relative_path

    print("\n" + "-" * 110)
    print(name.upper())
    print("-" * 110)

    if not path.exists():

        print("✗ FILE NOT FOUND")

        results.append({
            "dataset": name,
            "rows": 0,
            "unique_ids": 0,
            "missing_ids": 25,
            "invalid_ids": 0,
            "duplicate_ids": 0,
            "status": "FILE_MISSING"
        })

        continue


    df = pd.read_csv(path)

    # ------------------------------------------------------------
    # Find canonical ID
    # ------------------------------------------------------------

    if "canonical_basin_id" not in df.columns:

        print("✗ canonical_basin_id column missing")

        results.append({
            "dataset": name,
            "rows": len(df),
            "unique_ids": 0,
            "missing_ids": 25,
            "invalid_ids": 0,
            "duplicate_ids": 0,
            "status": "NO_CANONICAL_ID"
        })

        continue


    ids = df["canonical_basin_id"].dropna().astype(str)

    unique_ids = set(ids)

    invalid_ids = unique_ids - registry_ids

    missing_ids = registry_ids - unique_ids

    duplicate_ids = int(
        df["canonical_basin_id"].duplicated().sum()
    )


    print(f"Rows                  : {len(df)}")
    print(f"Unique canonical IDs  : {len(unique_ids)}")
    print(f"Invalid IDs           : {len(invalid_ids)}")
    print(f"Duplicate rows        : {duplicate_ids}")
    print(f"Missing basin IDs     : {len(missing_ids)}")


    # ------------------------------------------------------------
    # Classify dataset
    # ------------------------------------------------------------

    if invalid_ids:

        status = "FAIL_INVALID_IDS"

    elif duplicate_ids > 0:

        # dem_tile and rainfall/master are intentionally multi-row
        # datasets.

        if name in {"dem_tile", "rainfall", "master"}:
            status = "PASS_MULTIROW"

        else:
            status = "FAIL_DUPLICATES"

    else:

        if missing_ids:

            status = "PASS_COVERAGE_GAP"

        else:

            status = "PASS"


    print(f"STATUS                : {status}")


    results.append({
        "dataset": name,
        "rows": len(df),
        "unique_ids": len(unique_ids),
        "missing_ids": len(missing_ids),
        "invalid_ids": len(invalid_ids),
        "duplicate_ids": duplicate_ids,
        "status": status
    })


# ================================================================
# 3. WRITE REPORT
# ================================================================

print("\n[3/5] Writing structural contract report...")

report = pd.DataFrame(results)

report_path = ROOT / "cross_dataset_contract_report.csv"

report.to_csv(report_path, index=False)

print(f"Report written: {report_path}")


# ================================================================
# 4. SUMMARY
# ================================================================

print("\n[4/5] CROSS-DATASET CONTRACT SUMMARY")
print("=" * 110)

print(
    report[
        [
            "dataset",
            "rows",
            "unique_ids",
            "missing_ids",
            "invalid_ids",
            "duplicate_ids",
            "status"
        ]
    ].to_string(index=False)
)


# ================================================================
# 5. FINAL GATE
# ================================================================

print("\n[5/5] Final structural gate...")

hard_failures = report[
    report["status"].isin([
        "FILE_MISSING",
        "NO_CANONICAL_ID",
        "FAIL_INVALID_IDS",
        "FAIL_DUPLICATES"
    ])
]


if len(hard_failures) > 0:

    print("\n✗ CROSS-DATASET CONTRACT: FAIL")

    print("\nHard failures:")
    print(
        hard_failures[
            ["dataset", "status"]
        ].to_string(index=False)
    )

    raise SystemExit(1)


print("\n✓ CROSS-DATASET CONTRACT: PASS")
print("✓ All datasets use the canonical basin namespace")
print("✓ No invalid canonical IDs")
print("✓ No unexpected duplicate one-row-per-basin datasets")
print("✓ Coverage gaps are explicitly recorded")
print("\n" + "=" * 110)
print("PHASE 3.3 COMPLETE")
print("=" * 110)