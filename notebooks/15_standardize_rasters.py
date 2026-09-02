from pathlib import Path
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

ROOT = Path(__file__).resolve().parents[1]

SRC = ROOT / "data" / "processed" / "rasters"
OUT = ROOT / "data" / "processed" / "aligned"

TARGET_CRS = "EPSG:32645"
TARGET_RES = 30

OUT.mkdir(parents=True, exist_ok=True)

for path in sorted(SRC.rglob("*.tif")):

    relative = path.relative_to(SRC)
    destination = OUT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:

        with rasterio.open(path) as src:

            transform, width, height = calculate_default_transform(
                src.crs,
                TARGET_CRS,
                src.width,
                src.height,
                *src.bounds,
                resolution=TARGET_RES
            )

            profile = src.profile.copy()

            profile.update(
                crs=TARGET_CRS,
                transform=transform,
                width=width,
                height=height,
                compress="deflate",
                tiled=True
            )

            with rasterio.open(destination, "w", **profile) as dst:

                for band in range(1, src.count + 1):

                    reproject(
                        source=rasterio.band(src, band),
                        destination=rasterio.band(dst, band),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=TARGET_CRS,
                        resampling=Resampling.bilinear
                    )

        print("OK:", relative)

    except Exception as e:
        print("FAILED:", relative, e)