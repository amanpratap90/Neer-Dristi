import geopandas as gpd
import math
import os
import glob

p = r"data/raw/basin_boundaries/cwc_basins.geojson"

g = gpd.read_file(p).to_crs(4326)

x = g[
    g["ba_name"].astype(str).str.contains(
        "Kutch|Saurashtra|Inland drainage in Rajasthan",
        case=False,
        na=False
    )
]

b = x.total_bounds

print("TARGET BASINS:")
print(x[["ba_code", "ba_name"]].to_string(index=False))

print("\nTOTAL BOUNDS:")
print("WEST :", b[0])
print("SOUTH:", b[1])
print("EAST :", b[2])
print("NORTH:", b[3])

existing_files = glob.glob(
    r"data/raw/land_use_land_cover/worldcover_tiles/*_Map.tif"
)

existing = set()

for f in existing_files:
    name = os.path.basename(f)
    parts = name.split("_Map")[0]
    existing.add(parts)

required = []

for lat in range(math.floor(b[1]), math.floor(b[3]) + 1):
    for lon in range(math.floor(b[0]), math.floor(b[2]) + 1):

        lat_prefix = "N" if lat >= 0 else "S"
        lon_prefix = "E" if lon >= 0 else "W"

        tile = (
            f"{lat_prefix}{abs(lat):02d}"
            f"{lon_prefix}{abs(lon):03d}"
        )

        required.append(tile)

missing = [
    tile for tile in required
    if not any(tile in e for e in existing)
]

print("\nTOTAL 1-DEGREE GRID TILES:", len(required))
print("ALREADY PRESENT:", len(required) - len(missing))
print("MISSING:", len(missing))

print("\nMISSING TILE NAMES:")
for tile in missing:
    print(tile)
