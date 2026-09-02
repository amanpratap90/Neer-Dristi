import geopandas as gpd
import pandas as pd
import math
from pathlib import Path

BASIN_FILE = Path("data/raw/basin_boundaries/cwc_basins.geojson")
OUTPUT_DIR = Path("data/raw/dem")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

basins = gpd.read_file(BASIN_FILE)

print("=" * 70)
print("CHETAKAI - DEM TILE INVENTORY")
print("=" * 70)

print("\nOriginal CRS:")
print(basins.crs)

basins_wgs84 = basins.to_crs("EPSG:4326")

minx, miny, maxx, maxy = basins_wgs84.total_bounds

print("\nCWC BASIN EXTENT")
print("-" * 70)
print(f"West : {minx:.6f}")
print(f"South: {miny:.6f}")
print(f"East : {maxx:.6f}")
print(f"North: {maxy:.6f}")

tiles = []

for _, row in basins_wgs84.iterrows():

    basin_id = row["id"]
    basin_name = row["ba_name"] if "ba_name" in row else ""

    bminx, bminy, bmaxx, bmaxy = row.geometry.bounds

    west = math.floor(bminx)
    east = math.floor(bmaxx)

    south = math.floor(bminy)
    north = math.floor(bmaxy)

    for lat in range(south, north + 1):
        for lon in range(west, east + 1):

            if lat >= 0:
                lat_name = f"N{lat:02d}"
            else:
                lat_name = f"S{abs(lat):02d}"

            if lon >= 0:
                lon_name = f"E{lon:03d}"
            else:
                lon_name = f"W{abs(lon):03d}"

            tile = f"{lat_name}{lon_name}"

            tiles.append({
                "tile": tile,
                "basin_id": basin_id,
                "basin_name": basin_name
            })

inventory = pd.DataFrame(tiles)

inventory = inventory.drop_duplicates(
    subset=["tile"]
).sort_values("tile")

inventory["source"] = "USGS SRTM 1 Arc-Second Global"
inventory["resolution"] = "~30 m"
inventory["tile_size"] = "1 degree x 1 degree"
inventory["status"] = "REQUIRED"
inventory["local_path"] = inventory["tile"].apply(
    lambda x: f"data/raw/dem/srtm30/{x}"
)

output = OUTPUT_DIR / "dem_tile_inventory.csv"

inventory.to_csv(output, index=False)

print("\nDEM TILE INVENTORY")
print("-" * 70)

print("Unique DEM tiles required:", len(inventory))

print("\nFirst 30 tiles:")
print(inventory.head(30).to_string(index=False))

print("\nInventory saved to:")
print(output)

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)