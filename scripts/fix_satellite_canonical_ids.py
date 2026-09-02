from pathlib import Path
import pandas as pd

ROOT = Path("data/processed")
SAT_FILE = ROOT / "satellite" / "satellite_basin_features.csv"
REG_FILE = ROOT / "basin_registry.csv"
BACKUP = ROOT / "satellite" / "satellite_basin_features_before_canonical_fix.csv"

print("=" * 110)
print("CHETAKAI — SATELLITE CANONICAL BASIN ID REPAIR")
print("=" * 110)

sat = pd.read_csv(SAT_FILE)
registry = pd.read_csv(REG_FILE)

print("\nOriginal satellite basins:")
print(sorted(sat["canonical_basin_id"].dropna().unique()))

mapping = {
    "Godavari": "CWC_BASIN_004",
    "Mahanadi": "CWC_BASIN_005",
    "Subernarekha": "CWC_BASIN_006",
    "Brahmani and Baitarni": "CWC_BASIN_007",
    "Barak and Others": "CWC_BASIN_010",
    "Brahamaputra": "CWC_BASIN_011",
    "Ganga": "CWC_BASIN_012",
    "Narmada": "CWC_BASIN_014",
    "East flowing rivers between Mahanadi and Pennar": "CWC_BASIN_021",
    "Tapi": "CWC_BASIN_023",
}

if "basin_name" not in sat.columns:
    raise ValueError("Satellite dataset must contain basin_name.")

sat["canonical_basin_id_original"] = sat["canonical_basin_id"]

sat["canonical_basin_id"] = (
    sat["basin_name"]
    .astype(str)
    .str.strip()
    .map(mapping)
)

unmapped = sat.loc[
    sat["canonical_basin_id"].isna(),
    "basin_name"
].dropna().unique()

if len(unmapped):
    raise ValueError(
        "UNMAPPED SATELLITE BASINS:\n"
        + "\n".join(map(str, unmapped))
    )

print("\nCanonical mapping:")
print(
    sat[
        ["basin_name", "canonical_basin_id"]
    ]
    .drop_duplicates()
    .sort_values("canonical_basin_id")
    .to_string(index=False)
)

print("\nSatellite canonical basins:")
print(
    sorted(
        sat["canonical_basin_id"]
        .dropna()
        .unique()
    )
)

# Validate against registry
valid_ids = set(
    registry["canonical_basin_id"]
    .dropna()
    .astype(str)
)

invalid_ids = set(
    sat["canonical_basin_id"]
    .dropna()
) - valid_ids

if invalid_ids:
    raise ValueError(
        f"Invalid canonical basin IDs: {sorted(invalid_ids)}"
    )

# Backup
if not BACKUP.exists():
    sat_original = pd.read_csv(SAT_FILE)
    sat_original.to_csv(BACKUP, index=False)
    print("\nBackup created:")
    print(BACKUP.resolve())
else:
    print("\nBackup already exists:")
    print(BACKUP.resolve())

# Remove temporary original mapping column
sat = sat.drop(
    columns=["canonical_basin_id_original"]
)

sat.to_csv(
    SAT_FILE,
    index=False
)

print("\n" + "=" * 110)
print("SATELLITE CANONICAL ID REPAIR COMPLETE")
print("=" * 110)
print("Rows:", len(sat))
print(
    "Canonical basins:",
    sat["canonical_basin_id"].nunique()
)
print(
    "Unique satellite basin IDs:",
    sorted(sat["canonical_basin_id"].unique())
)

print("\nOutput:")
print(SAT_FILE.resolve())

print("=" * 110)
print("DONE")
print("=" * 110)