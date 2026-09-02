from pathlib import Path
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

INVENTORY = Path("data/raw/dem/priority_dem_inventory.csv")
OUTPUT_DIR = Path("data/raw/dem/copernicus_glo30")

BASE_URL = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"
WORKERS = 6


def tile_url(tile):
    lat = int(tile[1:3])
    lon = int(tile[4:7])

    lat_part = f"N{lat:02d}"
    lon_part = f"E{lon:03d}"

    product = (
        f"Copernicus_DSM_COG_10_"
        f"{lat_part}_00_"
        f"{lon_part}_00_DEM"
    )

    return (
        f"{BASE_URL}/"
        f"{product}/"
        f"{product}.tif"
    )


def download_tile(tile):
    output_path = OUTPUT_DIR / f"{tile}.tif"

    if output_path.exists() and output_path.stat().st_size > 0:
        return tile, "EXISTS", output_path.stat().st_size

    url = tile_url(tile)

    try:
        response = requests.get(url, stream=True, timeout=120)

        if response.status_code != 200:
            return tile, f"HTTP {response.status_code}", 0

        temp_path = output_path.with_suffix(".tmp")

        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

        if not temp_path.exists() or temp_path.stat().st_size == 0:
            return tile, "EMPTY", 0

        temp_path.replace(output_path)

        return tile, "DOWNLOADED", output_path.stat().st_size

    except Exception as e:
        return tile, f"ERROR: {e}", 0


print("=" * 70)
print("CHETAKAI V1 COPERNICUS GLO-30 DOWNLOADER")
print("=" * 70)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print()
print("Loading priority DEM inventory...")

inventory = pd.read_csv(INVENTORY)

if "dem_tile" not in inventory.columns:
    raise RuntimeError(
        "priority_dem_inventory.csv must contain a 'dem_tile' column."
    )

tiles = (
    inventory["dem_tile"]
    .dropna()
    .astype(str)
    .str.strip()
    .str.upper()
)

tiles = sorted(set(tiles))

print(f"Unique required tiles: {len(tiles)}")
print(f"Workers: {WORKERS}")
print()

print("=" * 70)
print("DOWNLOAD STATUS")
print("=" * 70)

results = []

with ThreadPoolExecutor(max_workers=WORKERS) as executor:

    futures = {
        executor.submit(download_tile, tile): tile
        for tile in tiles
    }

    for future in as_completed(futures):

        tile, status, size = future.result()

        results.append((tile, status, size))

        if status == "EXISTS":
            print(f"EXISTS     {tile}")

        elif status == "DOWNLOADED":
            size_mb = size / (1024 * 1024)
            print(f"DOWNLOADED {tile} ({size_mb:.1f} MB)")

        else:
            print(f"FAILED     {tile} -> {status}")


print()
print("=" * 70)
print("FINAL VALIDATION")
print("=" * 70)

found = set()

for path in OUTPUT_DIR.glob("*.tif"):
    found.add(path.stem.upper())

required = set(tiles)

missing = sorted(required - found)
extra = sorted(found - required)

print(f"Required unique tiles : {len(required)}")
print(f"Found TIFF tiles      : {len(found)}")
print(f"Missing tiles         : {len(missing)}")
print(f"Extra tiles           : {len(extra)}")

if missing:
    print()
    print("MISSING:")
    for tile in missing:
        print(f"  {tile}")

if extra:
    print()
    print("EXTRA:")
    for tile in extra:
        print(f"  {tile}")

print()

if not missing:
    print("OK ALL REQUIRED COPERNICUS GLO-30 TILES ARE PRESENT.")
else:
    print("WARNING: DEM RAW DATA COLLECTION IS NOT COMPLETE.")

print()
print("=" * 70)
print("DONE")
print("=" * 70)