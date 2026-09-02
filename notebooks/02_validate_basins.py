import geopandas as gpd
from pathlib import Path

path = Path("data/raw/basin_boundaries/cwc_basins.geojson")

print("=" * 70)
print("CHETAKAI - BASIN DATA VALIDATION")
print("=" * 70)

print("\nReading:", path)
print("Exists:", path.exists())

basins = gpd.read_file(path)

print("\n--- BASIC INFORMATION ---")
print("Rows:", len(basins))
print("Columns:", len(basins.columns))
print("CRS:", basins.crs)

print("\n--- COLUMNS ---")
for i, column in enumerate(basins.columns, 1):
    print(f"{i:02d}. {column}")

print("\n--- DATA TYPES ---")
print(basins.dtypes)

print("\n--- MISSING VALUES ---")
missing = basins.isnull().sum()

for column, count in missing.items():
    if count > 0:
        print(f"{column}: {count}")

print("\n--- GEOMETRY ---")
print("Geometry types:")
print(basins.geometry.geom_type.value_counts())

print("\nInvalid geometries:", (~basins.geometry.is_valid).sum())
print("Empty geometries:", basins.geometry.is_empty.sum())

print("\n--- BASIN NAMES ---")

if "ba_name" in basins.columns:
    print(basins[["id", "ba_name"]].to_string(index=False))

print("\n--- AREA ---")

if "area_sqkm" in basins.columns:
    print(
        basins["area_sqkm"].describe()
    )

print("\n--- STATE INFORMATION ---")

if "state" in basins.columns:
    print(basins["state"].value_counts())

print("\n--- SOURCE INFORMATION ---")

for column in ["src_agency", "ds_name"]:
    if column in basins.columns:
        print(f"\n{column}:")
        print(basins[column].value_counts())

print("\n--- SAMPLE RECORD ---")
print(basins.iloc[0].to_string())

print("\n" + "=" * 70)
print("VALIDATION COMPLETE")
print("=" * 70)