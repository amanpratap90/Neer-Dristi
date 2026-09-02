from pathlib import Path
import re
import geopandas as gpd
import pandas as pd


# ============================================================
# CHETAKAI — PHASE 1
# CANONICAL BASIN REGISTRY BUILDER
# ============================================================

RAW_PATH = Path("data/raw/basin_boundaries/cwc_basins.geojson")
OUTPUT_DIR = Path("data/processed")
OUTPUT_PATH = OUTPUT_DIR / "basin_registry.csv"


# ------------------------------------------------------------
# 1. LOAD MASTER CWC BASINS
# ------------------------------------------------------------

print("=" * 90)
print("CHETAKAI — PHASE 1: CANONICAL BASIN REGISTRY")
print("=" * 90)

print("\n[1/6] Loading master CWC basin boundaries...")

if not RAW_PATH.exists():
    raise FileNotFoundError(f"Master basin file not found: {RAW_PATH}")

gdf = gpd.read_file(RAW_PATH)

print(f"Rows loaded : {len(gdf)}")


# ------------------------------------------------------------
# 2. BASIC VALIDATION
# ------------------------------------------------------------

print("\n[2/6] Validating master basin IDs...")

if "id" not in gdf.columns:
    raise ValueError("Required column 'id' is missing.")

if gdf["id"].isna().any():
    raise ValueError("Master basin IDs contain NULL values.")

ids = pd.to_numeric(gdf["id"], errors="coerce")

if ids.isna().any():
    raise ValueError("Master basin IDs contain non-numeric values.")

ids = ids.astype(int)

if ids.duplicated().any():
    duplicates = ids[ids.duplicated()].tolist()
    raise ValueError(f"Duplicate basin IDs found: {duplicates}")

expected_ids = set(range(1, 26))
actual_ids = set(ids.tolist())

if actual_ids != expected_ids:
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)

    raise ValueError(
        f"Master basin ID set is invalid.\n"
        f"Missing: {missing}\n"
        f"Extra: {extra}"
    )

print("✓ Exactly 25 CWC basin IDs found")
print("✓ IDs are unique")
print("✓ IDs 1–25 are complete")


# ------------------------------------------------------------
# 3. CANONICAL ID
# ------------------------------------------------------------

print("\n[3/6] Creating canonical basin IDs...")

gdf["cwc_id"] = ids

gdf["canonical_basin_id"] = gdf["cwc_id"].apply(
    lambda x: f"CWC_BASIN_{x:03d}"
)

print("✓ Canonical IDs generated")


# ------------------------------------------------------------
# 4. NORMALIZE BASIN NAMES
# ------------------------------------------------------------

print("\n[4/6] Creating normalized basin names...")


def normalize_text(value):
    if pd.isna(value):
        return None

    value = str(value)

    # Remove accidental repeated basin-name concatenation
    # Example:
    # SubernarekhaSubernarekha
    # BrahamaputraBrahamaputra
    half = len(value) // 2

    if len(value) > 3 and value[:half] == value[half:]:
        value = value[:half]

    # Normalize whitespace
    value = re.sub(r"\s+", " ", value).strip()

    # Fix common missing spaces
    replacements = {
        "MadhyaPradesh": "Madhya Pradesh",
        "Chhattisgarh": "Chhattisgarh",
        "Brahmaniand Baitarni": "Brahmani and Baitarni",
        "Drainage area of Andaman & Nicobar Islands":
            "Drainage area of Andaman & Nicobar Islands",
        "Drainage area of Lakshadweep Islands":
            "Drainage area of Lakshadweep Islands",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return value


gdf["basin_name"] = gdf["ba_name"].apply(normalize_text)

print("✓ Basin names normalized")


# ------------------------------------------------------------
# 5. BUILD FINAL REGISTRY
# ------------------------------------------------------------

print("\n[5/6] Building registry...")

registry_columns = [
    "canonical_basin_id",
    "cwc_id",
    "basin_name",
    "ba_name",
    "ba_code",
    "area_sqkm",
    "state",
]

registry = gdf[registry_columns].copy()

# Ensure deterministic ordering
registry = registry.sort_values("cwc_id").reset_index(drop=True)


# ------------------------------------------------------------
# 6. SAVE + FINAL VALIDATION
# ------------------------------------------------------------

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

registry.to_csv(OUTPUT_PATH, index=False)

print(f"\n[6/6] Registry written to:")
print(f"      {OUTPUT_PATH}")

print("\n" + "=" * 90)
print("PHASE 1 VALIDATION")
print("=" * 90)

print(f"Registry rows          : {len(registry)}")
print(f"Unique canonical IDs   : {registry['canonical_basin_id'].nunique()}")
print(f"Unique CWC IDs         : {registry['cwc_id'].nunique()}")

expected_canonical = {
    f"CWC_BASIN_{i:03d}" for i in range(1, 26)
}

actual_canonical = set(registry["canonical_basin_id"])

print(
    "Canonical ID coverage  :",
    "PASS" if actual_canonical == expected_canonical else "FAIL"
)

if actual_canonical != expected_canonical:
    print("Missing canonical IDs:")
    print(sorted(expected_canonical - actual_canonical))

    print("Extra canonical IDs:")
    print(sorted(actual_canonical - expected_canonical))

# Check duplicate canonical IDs
duplicate_ids = registry[
    registry["canonical_basin_id"].duplicated(keep=False)
]

print(
    "Duplicate canonical IDs:",
    "PASS" if duplicate_ids.empty else "FAIL"
)

if not duplicate_ids.empty:
    print(duplicate_ids.to_string(index=False))


print("\nCANONICAL BASIN REGISTRY")
print("-" * 90)

print(
    registry[
        ["canonical_basin_id", "cwc_id", "basin_name"]
    ].to_string(index=False)
)

print("\n" + "=" * 90)
print("PHASE 1 COMPLETE")
print("=" * 90)