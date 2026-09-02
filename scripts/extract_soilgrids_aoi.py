import os
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds

VRT = "https://files.isric.org/soilgrids/latest/data/sand/sand_0-5cm_mean.vrt"

AOI_WEST = 73.38327110615607
AOI_SOUTH = 10.123562362103087
AOI_EAST = 97.41289624088454
AOI_NORTH = 31.46207936959709

OUT = "data/raw/soil/soilgrids/sand_0-5cm_mean_aoi.tif"

os.makedirs(os.path.dirname(OUT), exist_ok=True)

print("=" * 70)
print("CHETAKAI SOILGRIDS AOI EXTRACTION")
print("=" * 70)
print("SOURCE:", VRT)
print()

with rasterio.Env(
    GDAL_HTTP_MAX_RETRY=5,
    GDAL_HTTP_RETRY_DELAY=2,
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.vrt,.ovr",
):
    print("OPENING SOILGRIDS VRT...")

    with rasterio.open(VRT) as src:

        print("CRS:", src.crs)
        print("RESOLUTION:", src.res)
        print("WIDTH:", src.width)
        print("HEIGHT:", src.height)

        west, south, east, north = transform_bounds(
            "EPSG:4326",
            src.crs,
            AOI_WEST,
            AOI_SOUTH,
            AOI_EAST,
            AOI_NORTH,
            densify_pts=21,
        )

        print()
        print("AOI TRANSFORMED TO SOILGRIDS CRS:")
        print("WEST :", west)
        print("SOUTH:", south)
        print("EAST :", east)
        print("NORTH:", north)

        window = from_bounds(
            west,
            south,
            east,
            north,
            transform=src.transform,
        )

        window = window.round_offsets().round_lengths()

        print()
        print("READING AOI...")
        print("WINDOW:", window)

        data = src.read(
            1,
            window=window,
        )

        transform = src.window_transform(window)

        profile = src.profile.copy()

        profile.update(
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            transform=transform,
            compress="LZW",
            tiled=True,
            BIGTIFF="IF_SAFER",
        )

        print()
        print("PIXELS:", data.shape)
        print("WRITING:", OUT)

        with rasterio.open(OUT, "w", **profile) as dst:
            dst.write(data, 1)

print()
print("=" * 70)
print("SUCCESS")
print("=" * 70)

size = os.path.getsize(OUT) / 1024 / 1024

print("FILE:", OUT)
print(f"SIZE: {size:.2f} MB")