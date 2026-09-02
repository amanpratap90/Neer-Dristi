import os
import json
import boto3
from botocore.config import Config

CATALOG = "data/raw/satellite/sentinel2/sentinel2_catalog.json"
OUT = "data/raw/satellite/sentinel2/bands"

os.makedirs(OUT, exist_ok=True)

print("=" * 70)
print("CHETAKAI - SENTINEL-2 MVP DOWNLOAD")
print("=" * 70)

print()
print("IMPORTANT:")
print("This requires Copernicus Data Space S3 credentials.")
print()

ACCESS_KEY = os.getenv("CDSE_ACCESS_KEY")
SECRET_KEY = os.getenv("CDSE_SECRET_KEY")

if not ACCESS_KEY or not SECRET_KEY:
    print("CDSE_ACCESS_KEY / CDSE_SECRET_KEY not configured.")
    print()
    print("STOPPING SAFELY.")
    print()
    print("You need to generate S3 credentials in Copernicus Data Space.")
    print("Do NOT put credentials inside this script.")
    raise SystemExit(1)

with open(CATALOG, "r", encoding="utf-8") as f:
    catalog = json.load(f)

items = catalog.get("features", [])

if not items:
    raise RuntimeError("No Sentinel-2 scenes found in catalog.")

# Only 2 representative scenes for MVP.
items = items[:2]

bands = [
    "B02_10m",
    "B03_10m",
    "B04_10m",
    "B08_10m",
]

s3 = boto3.client(
    "s3",
    endpoint_url="https://eodata.dataspace.copernicus.eu",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name="default",
    config=Config(signature_version="s3v4"),
)

success = 0
failed = 0
skipped = 0

for item in items:

    scene_id = item["id"]

    print()
    print("SCENE:", scene_id)

    assets = item.get("assets", {})

    for band in bands:

        asset = assets.get(band)

        if not asset:
            print("  MISSING:", band)
            failed += 1
            continue

        href = asset["href"]

        if not href.startswith("s3://"):
            print("  INVALID S3 URL:", band)
            failed += 1
            continue

        s3_path = href[5:]
        bucket, key = s3_path.split("/", 1)

        filename = os.path.basename(key)

        scene_dir = os.path.join(
            OUT,
            scene_id
        )

        os.makedirs(scene_dir, exist_ok=True)

        output = os.path.join(
            scene_dir,
            filename
        )

        if os.path.exists(output) and os.path.getsize(output) > 100000:
            print("  SKIP:", band)
            skipped += 1
            continue

        print("  DOWNLOADING:", band)

        try:
            s3.download_file(
                bucket,
                key,
                output
            )

            size = os.path.getsize(output) / 1024 / 1024

            print(
                f"    DONE: {size:.1f} MB"
            )

            success += 1

        except Exception as e:

            print(
                "    FAILED:",
                str(e)
            )

            if os.path.exists(output):
                os.remove(output)

            failed += 1

print()
print("=" * 70)
print("SENTINEL-2 DOWNLOAD FINISHED")
print("=" * 70)
print("SUCCESS:", success)
print("SKIPPED:", skipped)
print("FAILED :", failed)
print("=" * 70)
