from pathlib import Path
import rasterio
import geopandas as gpd
from rasterio.mask import mask

ROOT = Path(__file__).resolve().parents[1]

AOI = ROOT / "data" / "interim" / "aoi" / "kosi_aoi.geojson"
SRC = ROOT / "data" / "interim"
OUT = ROOT / "data" / "processed" / "rasters"

OUT.mkdir(parents=True, exist_ok=True)

aoi = gpd.read_file(AOI)

raster_files = sorted(SRC.rglob("*.tif"))

success = 0
failed = 0

for path in raster_files:

    try:
        with rasterio.open(path) as src:

            geom = aoi.to_crs(src.crs)

            shapes = [
                feature.__geo_interface__
                for feature in geom.geometry
            ]

            data, transform = mask(
                src,
                shapes,
                crop=True,
                filled=True
            )

            profile = src.profile.copy()

            profile.update(
                height=data.shape[1],
                width=data.shape[2],
                transform=transform,
                compress="deflate",
                tiled=True
            )

            relative = path.relative_to(SRC)
            destination = OUT / relative
            destination.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            with rasterio.open(destination, "w", **profile) as dst:
                dst.write(data)

        success += 1

    except Exception as e:
        failed += 1
        print(f"FAILED: {path}")
        print(e)

print("=" * 80)
print("RASTER AOI PROCESSING")
print("=" * 80)
print("Found :", len(raster_files))
print("Done  :", success)
print("Failed:", failed)