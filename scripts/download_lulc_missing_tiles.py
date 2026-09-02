import requests
from pathlib import Path

OUT_DIR = Path(r"data/raw/land_use_land_cover/worldcover_tiles")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TILES = [
    "N18E069",
    "N21E066",
    "N24E066",
    "N24E069",
    "N27E069",
]

BASE_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"

success = 0
skipped = 0
failed = 0

print("=" * 80)
print("CHETAKAI - PHASE 4.3 - WORLD COVER 3x3 MISSING TILE DOWNLOAD")
print("=" * 80)

print("Tiles to process:", len(TILES))
print()

for i, tile in enumerate(TILES, 1):

    filename = f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
    output = OUT_DIR / filename

    print(f"[{i}/{len(TILES)}] {tile}")

    if output.exists() and output.stat().st_size > 100000:
        print("  OK - Already exists")
        skipped += 1
        continue

    url = f"{BASE_URL}/{filename}"
    temp = output.with_suffix(".download")

    try:
        with requests.get(
            url,
            stream=True,
            timeout=(20, 180)
        ) as r:

            if r.status_code != 200:
                print(f"  FAILED - HTTP {r.status_code}")
                failed += 1
                continue

            with open(temp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        if not temp.exists() or temp.stat().st_size < 100000:
            print("  FAILED - File suspiciously small")
            temp.unlink(missing_ok=True)
            failed += 1
            continue

        temp.replace(output)

        size_mb = output.stat().st_size / (1024 * 1024)

        print(f"  OK - Downloaded {size_mb:.2f} MB")
        success += 1

    except KeyboardInterrupt:
        print("\nStopped by user.")
        temp.unlink(missing_ok=True)
        raise

    except Exception as e:
        print(f"  FAILED - {e}")
        temp.unlink(missing_ok=True)
        failed += 1

print()
print("=" * 80)
print("DOWNLOAD COMPLETE")
print("=" * 80)
print("SUCCESS :", success)
print("SKIPPED :", skipped)
print("FAILED  :", failed)
print("TOTAL   :", len(TILES))
print("=" * 80)