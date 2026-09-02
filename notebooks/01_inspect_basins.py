from pathlib import Path
import geopandas as gpd

PROJECT_ROOT = Path(__file__).resolve().parent.parent

path = PROJECT_ROOT / "data" / "raw" / "basin_boundaries" / "cwc_basins.geojson"

print("Reading:", path)
print("Exists:", path.exists())

basins = gpd.read_file(path)

print(basins)
print()
print("Columns:")
print(basins.columns)

print()
print("CRS:")
print(basins.crs)

print()
print("Number of basins:")
print(len(basins))