import os
import math
import requests
import geopandas as gpd
import rasterio
from rasterio.merge import merge
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
from shapely.geometry import box

BASINS = "data/raw/soil/chetakai_soil_aoi.geojson"
OUT = "data/raw/land_use_land_cover"

os.makedirs(OUT, exist_ok=True)

print("=" * 70)
print("CHETAKAI - ESA WORLDCOVER MVP")
print("=" * 70)

g = gpd.read_file(BASINS).to_crs(4326)

# Actual basin geometry, NOT the huge rectangular AOI
geom = g.geometry.union_all()

minx, miny, maxx, maxy = geom.bounds

print("ACTUAL BASIN EXTENT:")
print("WEST :", minx)
print("SOUTH:", miny)
print("EAST :", maxx)
print("NORTH:", maxy)

# WorldCover tiles are 3 x 3 degrees
tiles = []

lat0 = math.floor(miny / 3) * 3
lon0 = math.floor(minx / 3) * 3

while lat0 < maxy:
    lon = lon0

    while lon < maxx:

        tile_box = box(
            lon,
            lat0,
            lon + 3,
            lat0 + 3
        )

        if tile_box.intersects(geom):

            ns = "N" if lat0 >= 0 else "S"
            ew = "E" if lon >= 0 else "W"

            tile = f"{ns}{abs(lat0):02d}{ew}{abs(lon):03d}"

            tiles.append(tile)

        lon += 3

    lat0 += 3

tiles = sorted(set(tiles))

print()
print("ACTUAL INTERSECTING TILES:", len(tiles))
print()
print(" ".join(tiles))
print()

# We will download only intersecting tiles.
# Then crop and resample them to 100 m.

raw_dir = os.path.join(OUT, "worldcover_tiles")
os.makedirs(raw_dir, exist_ok=True)

BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"

downloaded = []

for i, tile in enumerate(tiles, 1):

    filename = f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"

    url = f"{BASE}/{filename}"

    output = os.path.join(raw_dir, filename)

    print(f"[{i}/{len(tiles)}] {tile}")

    if os.path.exists(output) and os.path.getsize(output) > 1_000_000:

        print("  EXISTS")
        downloaded.append(output)
        continue

    try:

        with requests.get(
            url,
            stream=True,
            timeout=300
        ) as r:

            print("  STATUS:", r.status_code)

            r.raise_for_status()

            total = 0

            with open(output, "wb") as f:

                for chunk in r.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if chunk:

                        f.write(chunk)
                        total += len(chunk)

                        print(
                            f"\r  {total / 1024 / 1024:.1f} MB",
                            end="",
                            flush=True
                        )

        print()
        print("  DONE")

        downloaded.append(output)

    except Exception as e:

        print()
        print("  FAILED:", e)

        if os.path.exists(output):
            os.remove(output)


if not downloaded:

    raise RuntimeError("No WorldCover tiles downloaded.")


print()
print("=" * 70)
print("CREATING 100m MVP LULC")
print("=" * 70)

srcs = [
    rasterio.open(x)
    for x in downloaded
]

mosaic, transform = merge(srcs)

profile = srcs[0].profile.copy()

for src in srcs:
    src.close()

profile.update(
    height=mosaic.shape[1],
    width=mosaic.shape[2],
    transform=transform,
    compress="LZW",
    tiled=True,
    BIGTIFF="IF_SAFER"
)

temporary = os.path.join(
    OUT,
    "worldcover_10m_basin_mosaic.tif"
)

with rasterio.open(
    temporary,
    "w",
    **profile
) as dst:

    dst.write(mosaic)


# Resample to approximately 100 m.
# WorldCover is categorical, so use nearest neighbour.

with rasterio.open(temporary) as src:

    scale = 10

    new_width = max(1, src.width // scale)
    new_height = max(1, src.height // scale)

    new_transform = src.transform * src.transform.scale(
        src.width / new_width,
        src.height / new_height
    )

    profile = src.profile.copy()

    profile.update(
        width=new_width,
        height=new_height,
        transform=new_transform,
        compress="LZW",
        tiled=True,
        BIGTIFF="IF_SAFER"
    )

    output = os.path.join(
        OUT,
        "worldcover_2021_100m_mvp.tif"
    )

    with rasterio.open(
        output,
        "w",
        **profile
    ) as dst:

        reproject(
            source=rasterio.band(src, 1),
            destination=rasterio.band(dst, 1),
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=new_transform,
            dst_crs=src.crs,
            resampling=Resampling.nearest
        )


print()
print("=" * 70)
print("SUCCESS")
print("=" * 70)

print("RAW TILES :", len(downloaded))
print("MVP FILE  :", output)
print(
    "SIZE      :",
    round(os.path.getsize(output) / 1024 / 1024, 2),
    "MB"
)

print()
print("ESA WorldCover 2021 -> 100m MVP LULC READY")
