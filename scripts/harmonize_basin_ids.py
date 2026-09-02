from pathlib import Path
import pandas as pd
import re
import shutil


# ============================================================
# CHETAKAI — PHASE 2.2
# CANONICAL BASIN ID HARMONIZATION
# ============================================================

ROOT = Path("data")
PROCESSED = ROOT / "processed"
REGISTRY_PATH = PROCESSED / "basin_registry.csv"

BACKUP_DIR = PROCESSED / "_phase2_backup"

print("=" * 100)
print("CHETAKAI — PHASE 2.2: CANONICAL BASIN ID HARMONIZATION")
print("=" * 100)


# ============================================================
# 1. LOAD REGISTRY
# ============================================================

print("\n[1/7] Loading canonical basin registry...")

registry = pd.read_csv(REGISTRY_PATH)

required_registry_cols = [
    "canonical_basin_id",
    "cwc_id",
    "basin_name",
]

missing = [
    c for c in required_registry_cols
    if c not in registry.columns
]

if missing:
    raise RuntimeError(
        f"Registry missing required columns: {missing}"
    )

print(f"Registry rows : {len(registry)}")

if len(registry) != 25:
    raise RuntimeError(
        f"Expected 25 registry rows, found {len(registry)}"
    )


# ============================================================
# 2. BUILD MAPPING TABLES
# ============================================================

print("\n[2/7] Building canonical mapping tables...")


def clean_text(value):
    """
    Normalize names only for matching.
    Original values are never overwritten.
    """
    if pd.isna(value):
        return ""

    value = str(value).strip().upper()

    # Normalize ampersands
    value = value.replace("&", " AND ")

    # Remove punctuation
    value = re.sub(r"[^A-Z0-9]+", " ", value)

    # Collapse whitespace
    value = re.sub(r"\s+", " ", value).strip()

    return value


# ------------------------------------------------------------
# Numeric ID -> canonical ID
# ------------------------------------------------------------

numeric_to_canonical = {}

for _, row in registry.iterrows():

    cwc_id = int(row["cwc_id"])

    canonical = str(row["canonical_basin_id"])

    numeric_to_canonical[str(cwc_id)] = canonical
    numeric_to_canonical[str(cwc_id).zfill(2)] = canonical
    numeric_to_canonical[str(cwc_id).zfill(3)] = canonical


# ------------------------------------------------------------
# Canonical ID -> canonical ID
# ------------------------------------------------------------

canonical_to_canonical = {
    str(row["canonical_basin_id"]).upper().strip():
        str(row["canonical_basin_id"])
    for _, row in registry.iterrows()
}


# ------------------------------------------------------------
# Basin name -> canonical ID
# ------------------------------------------------------------

name_to_canonical = {}

for _, row in registry.iterrows():

    canonical = str(row["canonical_basin_id"])

    possible_names = [
        row.get("basin_name"),
        row.get("ba_name"),
        row.get("ba_code"),
    ]

    for name in possible_names:

        cleaned = clean_text(name)

        if cleaned:
            name_to_canonical[cleaned] = canonical


# ------------------------------------------------------------
# Known spelling aliases
# ------------------------------------------------------------

ALIASES = {
    "BRAHAMAPUTRA": "CWC_BASIN_011",
    "BRAHMAPUTRA": "CWC_BASIN_011",

    "SUBERNAREKHA": "CWC_BASIN_006",
    "SUBARNA REKHA": "CWC_BASIN_006",

    "BARAK AND OTHERS": "CWC_BASIN_010",
    "BARAK AND OTHER": "CWC_BASIN_010",

    "BRAHMANI AND BAITARNI": "CWC_BASIN_007",

    "CAUVERY": "CWC_BASIN_001",
    "PENNAR": "CWC_BASIN_003",
    "GODAVARI": "CWC_BASIN_004",
    "MAHANADI": "CWC_BASIN_005",
    "SABARMATI": "CWC_BASIN_009",
    "GANGA": "CWC_BASIN_012",
    "NARMADA": "CWC_BASIN_014",
    "KRISHNA": "CWC_BASIN_017",
    "MAHI": "CWC_BASIN_022",
    "TAPI": "CWC_BASIN_023",

    "EAST FLOWING RIVERS BETWEEN MAHANADI AND PENNAR":
        "CWC_BASIN_021",

    "EAST FLOWING RIVERS BETWEEN PENNAR AND KANYAKUMARI":
        "CWC_BASIN_002",

    "WEST FLOWING RIVERS FROM TAPI TO TADRI":
        "CWC_BASIN_024",

    "WEST FLOWING RIVERS FROM TADRI TO KANYAKUMARI":
        "CWC_BASIN_015",

    "WEST FLOWING RIVERS OF KUTCH AND SAURASHTRA INCLUDING LUNI":
        "CWC_BASIN_013",

    "AREA OF INLAND DRAINAGE IN RAJASTHAN":
        "CWC_BASIN_016",

    "MINOR RIVERS DRAINING INTO MYANMAR AND BANGLADESH":
        "CWC_BASIN_008",

    "INDUS UP TO BORDER":
        "CWC_BASIN_025",

    "DRAINAGE AREA OF ANDAMAN NICOBAR ISLANDS":
        "CWC_BASIN_019",

    "DRAINAGE AREA OF LAKSHADWEEP ISLANDS":
        "CWC_BASIN_020",

    "AREA OF NORTH LADAKH NOT DRAINING INTO INDUS BASIN":
        "CWC_BASIN_018",
}

name_to_canonical.update(ALIASES)


print(f"Numeric mappings : {len(numeric_to_canonical)}")
print(f"Name mappings    : {len(name_to_canonical)}")


# ============================================================
# 3. SAFE RESOLVER
# ============================================================

print("\n[3/7] Initializing basin resolver...")


def resolve_basin(value):

    if pd.isna(value):
        return None

    raw = str(value).strip()

    if not raw:
        return None

    # ----------------------------------------
    # Already canonical
    # ----------------------------------------

    canonical_key = raw.upper()

    if canonical_key in canonical_to_canonical:
        return canonical_to_canonical[canonical_key]

    # ----------------------------------------
    # Numeric ID
    # ----------------------------------------

    numeric_match = re.fullmatch(r"\d+(\.0+)?", raw)

    if numeric_match:

        numeric = str(int(float(raw)))

        if numeric in numeric_to_canonical:
            return numeric_to_canonical[numeric]

    # ----------------------------------------
    # Name
    # ----------------------------------------

    cleaned = clean_text(raw)

    if cleaned in name_to_canonical:
        return name_to_canonical[cleaned]

    return None


# ============================================================
# 4. DATASET CONFIGURATION
# ============================================================

print("\n[4/7] Preparing dataset configuration...")


datasets = {

    "administrative/administrative_basin_features.csv":
        "basin_name",

    "dem/dem_basin_features.csv":
        "basin_name",

    "dem/dem_tile_basin_features.csv":
        "basin_name",

    "hydrography/hydrography_basin_features.csv":
        "basin_name",

    "infrastructure/infrastructure_basin_features.csv":
        "basin_name",

    "lulc/lulc_basin_features.csv":
        "basin_name",

    "population/population_basin_features.csv":
        "basin_name",

    "reservoirs/reservoir_basin_features.csv":
        "basin_name",

    "satellite/satellite_basin_features.csv":
        "basin_name",

    "soil/soil_basin_features.csv":
        "basin_name",

    "master/chetakai_v1_master_ml_dataset.csv":
        "basin_name",

    "rainfall/chirps_monthly_basin_features.csv":
        "basin",
}


# ============================================================
# 5. BACKUP
# ============================================================

print("\n[5/7] Creating Phase 2 backup...")

BACKUP_DIR.mkdir(parents=True, exist_ok=True)

for relative_path in datasets:

    source = PROCESSED / relative_path

    if not source.exists():
        print(f"WARNING: missing file: {source}")
        continue

    destination = BACKUP_DIR / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source, destination)

print(f"Backup directory: {BACKUP_DIR}")


# ============================================================
# 6. HARMONIZE
# ============================================================

print("\n[6/7] Harmonizing datasets...")

results = []

for relative_path, basin_column in datasets.items():

    path = PROCESSED / relative_path

    if not path.exists():

        print(f"\nSKIP — file not found: {relative_path}")

        results.append({
            "dataset": relative_path,
            "rows": 0,
            "mapped": 0,
            "unmapped": 0,
            "status": "MISSING_FILE"
        })

        continue

    df = pd.read_csv(path)

    if basin_column not in df.columns:

        print(
            f"\nFAIL — {relative_path}: "
            f"missing column '{basin_column}'"
        )

        results.append({
            "dataset": relative_path,
            "rows": len(df),
            "mapped": 0,
            "unmapped": len(df),
            "status": "MISSING_BASIN_COLUMN"
        })

        continue

    # ----------------------------------------
    # Resolve IDs
    # ----------------------------------------

    resolved = df[basin_column].apply(resolve_basin)

    # ----------------------------------------
    # Add canonical ID
    # ----------------------------------------

    df["canonical_basin_id"] = resolved

    mapped = int(resolved.notna().sum())
    unmapped = int(resolved.isna().sum())

    # ----------------------------------------
    # Validate mapped IDs
    # ----------------------------------------

    invalid = sorted(
        set(resolved.dropna())
        - set(registry["canonical_basin_id"])
    )

    if invalid:

        raise RuntimeError(
            f"{relative_path} produced invalid "
            f"canonical IDs: {invalid}"
        )

    # ----------------------------------------
    # Save
    # ----------------------------------------

    df.to_csv(path, index=False)

    status = "PASS" if unmapped == 0 else "PARTIAL"

    print(
        f"\n{relative_path}"
        f"\n  Rows       : {len(df)}"
        f"\n  Mapped     : {mapped}"
        f"\n  Unmapped   : {unmapped}"
        f"\n  Status     : {status}"
    )

    results.append({
        "dataset": relative_path,
        "rows": len(df),
        "mapped": mapped,
        "unmapped": unmapped,
        "status": status
    })


# ============================================================
# 7. FINAL REPORT
# ============================================================

print("\n[7/7] Writing Phase 2.2 report...")

report = pd.DataFrame(results)

report_path = PROCESSED / "basin_harmonization_report.csv"

report.to_csv(report_path, index=False)

print("\n" + "=" * 100)
print("PHASE 2.2 RESULT")
print("=" * 100)

print(report.to_string(index=False))

print("\nReport:")
print(f"  {report_path}")

print("\nBackup:")
print(f"  {BACKUP_DIR}")

print("\n" + "=" * 100)
print("PHASE 2.2 COMPLETE")
print("=" * 100)