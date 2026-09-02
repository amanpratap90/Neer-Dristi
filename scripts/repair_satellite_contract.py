from pathlib import Path
import pandas as pd


ROOT = Path("data/processed")

SATELLITE = ROOT / "satellite/satellite_basin_features.csv"
REGISTRY = ROOT / "basin_registry.csv"

print("=" * 100)
print("CHETAKAI — PHASE 3.2: SATELLITE CONTRACT REPAIR")
print("=" * 100)

# ---------------------------------------------------------------------
# 1. Load
# ---------------------------------------------------------------------

print("\n[1/6] Loading registry and satellite dataset...")

registry = pd.read_csv(REGISTRY)
satellite = pd.read_csv(SATELLITE)

print(f"Registry rows  : {len(registry)}")
print(f"Satellite rows : {len(satellite)}")


# ---------------------------------------------------------------------
# 2. Preserve original satellite data
# ---------------------------------------------------------------------

backup = SATELLITE.with_suffix(".pre_phase3_2_backup.csv")

if not backup.exists():
    satellite.to_csv(backup, index=False)
    print(f"Backup created : {backup}")


# ---------------------------------------------------------------------
# 3. Remove rows that cannot resolve to a canonical basin
# ---------------------------------------------------------------------

print("\n[2/6] Removing unresolved satellite rows...")

before = len(satellite)

satellite = satellite[
    satellite["canonical_basin_id"].notna()
].copy()

removed = before - len(satellite)

print(f"Rows removed because canonical ID is missing: {removed}")


# ---------------------------------------------------------------------
# 4. Remove duplicate canonical IDs
# ---------------------------------------------------------------------

print("\n[3/6] Checking duplicate canonical IDs...")

duplicates = satellite[
    satellite["canonical_basin_id"].duplicated(keep=False)
]

if len(duplicates) > 0:
    print("Duplicate rows found:")
    print(
        duplicates[
            ["canonical_basin_id", "basin_name"]
        ].to_string(index=False)
    )

    # Keep first valid record for each basin.
    satellite = satellite.drop_duplicates(
        subset=["canonical_basin_id"],
        keep="first"
    )

    print("✓ Duplicate records collapsed")
else:
    print("✓ No duplicates")


# ---------------------------------------------------------------------
# 5. Reindex against complete canonical registry
# ---------------------------------------------------------------------

print("\n[4/6] Aligning against complete canonical registry...")

canonical_ids = registry["canonical_basin_id"].tolist()

satellite = (
    satellite
    .set_index("canonical_basin_id")
    .reindex(canonical_ids)
    .reset_index()
)

# Recover basin metadata from registry
registry_lookup = registry.set_index("canonical_basin_id")

satellite["basin_name"] = satellite["basin_name"].fillna(
    satellite["canonical_basin_id"].map(
        registry_lookup["basin_name"]
    )
)


# ---------------------------------------------------------------------
# 6. Explicitly mark missing satellite coverage
# ---------------------------------------------------------------------

print("\n[5/6] Applying explicit missing-coverage contract...")

coverage_columns = [
    "satellite_products_used",
    "satellite_valid_pixels",
    "ndvi_mean",
    "ndvi_median",
    "ndvi_std",
    "ndvi_min",
    "ndvi_max",
    "ndwi_mean",
    "ndwi_median",
    "ndwi_std",
    "ndwi_min",
    "ndwi_max",
    "vegetation_pct",
    "water_pct",
    "satellite_data_available",
]

missing_mask = satellite["satellite_products_used"].isna()

satellite.loc[missing_mask, "satellite_products_used"] = 0
satellite.loc[missing_mask, "satellite_valid_pixels"] = 0
satellite.loc[missing_mask, "satellite_data_available"] = 0

# Numerical satellite measurements intentionally remain NaN.
print(
    "Missing satellite coverage:",
    int(missing_mask.sum())
)


# ---------------------------------------------------------------------
# Final column order
# ---------------------------------------------------------------------

metadata_columns = [
    "basin_name",
    "satellite_products_used",
    "satellite_valid_pixels",
    "ndvi_mean",
    "ndvi_median",
    "ndvi_std",
    "ndvi_min",
    "ndvi_max",
    "ndwi_mean",
    "ndwi_median",
    "ndwi_std",
    "ndwi_min",
    "ndwi_max",
    "vegetation_pct",
    "water_pct",
    "satellite_data_available",
    "canonical_basin_id",
]

satellite = satellite[
    metadata_columns
]


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------

print("\n[6/6] Final validation...")

expected_ids = set(canonical_ids)
actual_ids = set(satellite["canonical_basin_id"])

invalid = actual_ids - expected_ids
missing = expected_ids - actual_ids
duplicates = satellite["canonical_basin_id"].duplicated().sum()

print(f"Final rows             : {len(satellite)}")
print(f"Unique canonical IDs   : {satellite['canonical_basin_id'].nunique()}")
print(f"Invalid IDs            : {len(invalid)}")
print(f"Duplicate IDs          : {duplicates}")
print(f"Missing IDs             : {len(missing)}")

if invalid:
    print("INVALID:", sorted(invalid))

if missing:
    print("MISSING:", sorted(missing))


if (
    len(satellite) == 25
    and satellite["canonical_basin_id"].nunique() == 25
    and not invalid
    and not missing
    and duplicates == 0
):
    satellite.to_csv(SATELLITE, index=False)

    print("\n✓ SATELLITE CONTRACT: PASS")
    print(f"✓ Written: {SATELLITE}")

else:
    raise RuntimeError(
        "Satellite contract failed. Output was NOT written."
    )


print("\n" + "=" * 100)
print("PHASE 3.2 COMPLETE")
print("=" * 100)