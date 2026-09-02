import os
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds

PROPERTIES = [
    "sand",
    "silt",
    "clay",
    "bdod",
    "soc",
    "phh2o",
    "cec",
    "cfvo",
    "wv0010",
    "wv0033",
    "wv1500",
]

DEPTHS = [
    "0-5cm",
    "5-15cm",
    "15-30cm",
    "30-60cm",
    "60-100cm",
    "100-200cm",
]

AOI_WEST = 73.38327110615607
AOI_SOUTH = 10.123562362103087
AOI_EAST = 97.41289624088454
AOI_NORTH = 31.46207936959709

BASE = "https://files.isric.org/soilgrids/latest/data"

ROOT = "data/raw/soil/soilgrids"

os.makedirs(ROOT, exist_ok=True)

print("=" * 70)
print("CHETAKAI — COMPLETE SOILGRIDS COLLECTION")
print("=" * 70)

print()
print("PROPERTIES:", len(PROPERTIES))
print("DEPTHS:", len(DEPTHS))
print("TOTAL RASTERS:", len(PROPERTIES) * len(DEPTHS))
print()

completed = 0
skipped = 0
failed = 0

for prop in PROPERTIES:

    for depth in DEPTHS:

        print()
        print("=" * 70)
        print(f"PROPERTY: {prop}")
        print(f"DEPTH   : {depth}")
        print("=" * 70)

        vrt_url = (
            f"/vsicurl/"
            f"{BASE}/{prop}/"
            f"{prop}_{depth}_mean.vrt"
        )

        output_dir = os.path.join(
            ROOT,
            prop,
            depth
        )

        os.makedirs(output_dir, exist_ok=True)

        output = os.path.join(
            output_dir,
            f"{prop}_{depth}_mean_aoi.tif"
        )

        if (
            os.path.exists(output)
            and os.path.getsize(output) > 100000
        ):
            print("ALREADY EXISTS")
            print(output)
            skipped += 1
            continue

        try:

            print("OPENING:", vrt_url)

            with rasterio.Env(
                GDAL_HTTP_MAX_RETRY=5,
                GDAL_HTTP_RETRY_DELAY=2,
                CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.vrt,.ovr",
            ):

                with rasterio.open(vrt_url) as src:

                    west, south, east, north = transform_bounds(
                        "EPSG:4326",
                        src.crs,
                        AOI_WEST,
                        AOI_SOUTH,
                        AOI_EAST,
                        AOI_NORTH,
                        densify_pts=21,
                    )

                    window = from_bounds(
                        west,
                        south,
                        east,
                        north,
                        transform=src.transform,
                    )

                    window = (
                        window
                        .round_offsets()
                        .round_lengths()
                    )

                    print(
                        "READING:",
                        window
                    )

                    data = src.read(
                        1,
                        window=window
                    )

                    transform = src.window_transform(
                        window
                    )

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

                    print(
                        "PIXELS:",
                        data.shape
                    )

                    with rasterio.open(
                        output,
                        "w",
                        **profile
                    ) as dst:

                        dst.write(
                            data,
                            1
                        )

            size = os.path.getsize(output) / 1024 / 1024

            print(
                f"SUCCESS: {size:.2f} MB"
            )

            completed += 1

        except Exception as e:

            print()
            print("FAILED:", prop, depth)
            print("ERROR:", str(e))

            failed += 1

print()
print("=" * 70)
print("SOILGRIDS COLLECTION COMPLETE")
print("=" * 70)

print("SUCCESS :", completed)
print("SKIPPED :", skipped)
print("FAILED  :", failed)
print("TOTAL   :", len(PROPERTIES) * len(DEPTHS))