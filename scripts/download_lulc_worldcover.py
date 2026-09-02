import os
import math
import requests

WEST = 73.38327110615607
SOUTH = 10.123562362103087
EAST = 97.41289624088454
NORTH = 31.46207936959709

BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
OUT = "data/raw/land_use_land_cover/worldcover_2021"

os.makedirs(OUT, exist_ok=True)

tiles = set()

for lat in range(math.floor(SOUTH / 3) * 3, math.ceil(NORTH / 3) * 3, 3):
    for lon in range(math.floor(WEST / 3) * 3, math.ceil(EAST / 3) * 3, 3):

        ns = "N" if lat >= 0 else "S"
        ew = "E" if lon >= 0 else "W"

        tiles.add(
            f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}"
        )

tiles = sorted(tiles)

print("=" * 70)
print("CHETAKAI - ESA WORLDCOVER 2021")
print("=" * 70)
print("TILES REQUIRED:", len(tiles))
print()
print("\n".join(tiles))
print()

for i, tile in enumerate(tiles, 1):

    filename = f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
    url = f"{BASE}/{filename}"
    output = os.path.join(OUT, filename)

    print(f"[{i}/{len(tiles)}] {tile}")

    if os.path.exists(output) and os.path.getsize(output) > 1_000_000:
        print("  SKIP - already downloaded")
        continue

    try:
        with requests.get(url, stream=True, timeout=300) as r:

            print("  STATUS:", r.status_code)
            r.raise_for_status()

            total = 0

            with open(output, "wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
                        print(
                            f"\r  {total / 1024 / 1024:.1f} MB",
                            end="",
                            flush=True
                        )

        print("\n  DONE")

    except Exception as e:
        print("\n  FAILED:", e)
        if os.path.exists(output):
            os.remove(output)

print()
print("=" * 70)
print("DOWNLOAD COMPLETE")
print("=" * 70)

