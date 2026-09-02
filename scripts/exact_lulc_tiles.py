import geopandas as gpd
import math
import os
import glob
from shapely.geometry import box

BASIN_FILE = r"data/raw/basin_boundaries/cwc_basins.geojson"
TILE_DIR = r"data/raw/land_use_land_cover/worldcover_tiles"

g = gpd.read_file(BASIN_FILE).to_crs(4326)

targets = g[
    g["ba_name"].astype(str).str.contains(
        "Kutch|Saurashtra|Inland drainage in Rajasthan",
        case=False,
        na=False
    )
].copy()

print("TARGET BASINS:")
print(targets[["ba_code", "ba_name"]].to_string(index=False))

existing_files = glob.glob(os.path.join(TILE_DIR, "*_Map.tif"))

existing = set()

for f in existing_files:
    name = os.path.basename(f)

    # Extract NxxExxx / SxxExxx / NxxWxxx etc.
    for part in name.split("_"):
        if (
            len(part) == 7
            and part[0] in "NS"
            and part[3] in "EW"
        ):
            existing.add(part)

required = set()

# Only inspect the bounding grid, then test actual geometry intersection.
for _, row in targets.iterrows():

    minx, miny, maxx, maxy = row.geometry.bounds

    for lat in range(math.floor(miny), math.floor(maxy) + 1):
        for lon in range(math.floor(minx), math.floor(maxx) + 1):

            tile_geom = box(lon, lat, lon + 1, lat + 1)

            if row.geometry.intersects(tile_geom):

                lat_prefix = "N" if lat >= 0 else "S"
                lon_prefix = "E" if lon >= 0 else "W"

                tile = (
                    f"{lat_prefix}{abs(lat):02d}"
                    f"{lon_prefix}{abs(lon):03d}"
                )

                required.add(tile)

missing = sorted(required - existing)

print("\n========================================")
print("ACTUAL WORLD COVER TILE REQUIREMENT")
print("========================================")

print("Required tiles :", len(required))
print("Already present:", len(required & existing))
print("Missing tiles  :", len(missing))

print("\nREQUIRED TILES:")
for tile in sorted(required):
    status = "PRESENT" if tile in existing else "MISSING"
    print(f"{tile:10s} {status}")

print("\n========================================")
print("MISSING ONLY")
print("========================================")

for tile in missing:
    print(tile)
