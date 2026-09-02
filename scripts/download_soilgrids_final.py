import os
import requests
import xml.etree.ElementTree as ET
import geopandas as gpd
from pyproj import CRS, Transformer

VRT = "data/raw/soil/soilgrids/sand_0-5cm_mean.vrt"
AOI = "data/raw/soil/chetakai_soil_aoi.geojson"

BASE = "https://files.isric.org/soilgrids/latest/data/"

OUT = "data/raw/soil/soilgrids/sand/0-5cm/mean"
os.makedirs(OUT, exist_ok=True)

print("=" * 70)
print("CHETAKAI — SOILGRIDS 250m RAW DATA")
print("=" * 70)

# ------------------------------------------------------------
# Read AOI
# ------------------------------------------------------------

g = gpd.read_file(AOI).to_crs(4326)

minx, miny, maxx, maxy = g.total_bounds

print()
print("AOI:")
print(f"  WEST : {minx}")
print(f"  SOUTH: {miny}")
print(f"  EAST : {maxx}")
print(f"  NORTH: {maxy}")

# ------------------------------------------------------------
# Read VRT
# ------------------------------------------------------------

print()
print("READING SOILGRIDS VRT...")

tree = ET.parse(VRT)
root = tree.getroot()

srs_text = root.findtext("SRS")

if srs_text is None:
    raise RuntimeError("VRT has no SRS")

vrt_crs = CRS.from_wkt(srs_text)

print("VRT CRS:", vrt_crs.to_string())

# ------------------------------------------------------------
# VRT geotransform
# ------------------------------------------------------------

gt_text = root.findtext("GeoTransform")

if gt_text is None:
    raise RuntimeError("VRT has no GeoTransform")

gt = [
    float(x.strip())
    for x in gt_text.split(",")
]

origin_x = gt[0]
pixel_x = gt[1]
rotation_x = gt[2]
origin_y = gt[3]
rotation_y = gt[4]
pixel_y = gt[5]

print("VRT GeoTransform:", gt)

# ------------------------------------------------------------
# Transform AOI to VRT CRS
# ------------------------------------------------------------

transformer = Transformer.from_crs(
    "EPSG:4326",
    vrt_crs,
    always_xy=True
)

corners = [
    transformer.transform(minx, miny),
    transformer.transform(minx, maxy),
    transformer.transform(maxx, miny),
    transformer.transform(maxx, maxy),
]

vx = [p[0] for p in corners]
vy = [p[1] for p in corners]

aoi_vrt_minx = min(vx)
aoi_vrt_maxx = max(vx)
aoi_vrt_miny = min(vy)
aoi_vrt_maxy = max(vy)

print()
print("AOI IN VRT CRS:")
print(
    aoi_vrt_minx,
    aoi_vrt_miny,
    aoi_vrt_maxx,
    aoi_vrt_maxy
)

# ------------------------------------------------------------
# Convert geographic VRT coordinates to pixel coordinates
# ------------------------------------------------------------

def world_to_pixel(x, y):

    px = (
        (x - origin_x) / pixel_x
        if pixel_x != 0
        else 0
    )

    py = (
        (y - origin_y) / pixel_y
        if pixel_y != 0
        else 0
    )

    return px, py


corners_pixel = [
    world_to_pixel(aoi_vrt_minx, aoi_vrt_miny),
    world_to_pixel(aoi_vrt_minx, aoi_vrt_maxy),
    world_to_pixel(aoi_vrt_maxx, aoi_vrt_miny),
    world_to_pixel(aoi_vrt_maxx, aoi_vrt_maxy),
]

pxs = [p[0] for p in corners_pixel]
pys = [p[1] for p in corners_pixel]

aoi_px_minx = min(pxs)
aoi_px_maxx = max(pxs)
aoi_px_miny = min(pys)
aoi_px_maxy = max(pys)

print()
print("AOI PIXEL WINDOW:")
print(
    aoi_px_minx,
    aoi_px_miny,
    aoi_px_maxx,
    aoi_px_maxy
)

# ------------------------------------------------------------
# Find actual TIFF source pieces intersecting AOI
# ------------------------------------------------------------

print()
print("SCANNING VRT SOURCE TILES...")

sources = root.findall(".//SimpleSource")

selected = []

for source in sources:

    filename = source.findtext("SourceFilename")

    if not filename:
        continue

    dst = source.find("DstRect")

    if dst is None:
        continue

    xoff = float(dst.attrib["xOff"])
    yoff = float(dst.attrib["yOff"])
    xsize = float(dst.attrib["xSize"])
    ysize = float(dst.attrib["ySize"])

    tile_minx = xoff
    tile_maxx = xoff + xsize

    tile_miny = yoff
    tile_maxy = yoff + ysize

    intersects = not (
        tile_maxx < aoi_px_minx
        or tile_minx > aoi_px_maxx
        or tile_maxy < aoi_px_miny
        or tile_miny > aoi_px_maxy
    )

    if intersects:
        selected.append(filename)

selected = sorted(set(selected))

print()
print("=" * 70)
print("RESULT")
print("=" * 70)

print("TOTAL VRT SOURCES :", len(sources))
print("AOI SOURCES       :", len(selected))

if not selected:
    raise RuntimeError(
        "ZERO SOURCE TILES FOUND. "
        "VRT coordinate interpretation needs investigation."
    )

print()
print("FIRST 10 SELECTED:")
for x in selected[:10]:
    print(" ", x)

print()
print("=" * 70)
print("STARTING ACTUAL DOWNLOAD")
print("=" * 70)

session = requests.Session()

downloaded = 0
skipped = 0
failed = 0

for i, relative in enumerate(selected, 1):

    relative = relative.replace("\\", "/")

    if relative.startswith("./"):
        relative = relative[2:]

    url = BASE + relative

    filename = os.path.basename(relative)

    output = os.path.join(OUT, filename)

    if (
        os.path.exists(output)
        and os.path.getsize(output) > 100000
    ):
        skipped += 1
        print(
            f"[{i}/{len(selected)}] EXISTS {filename}"
        )
        continue

    print(
        f"[{i}/{len(selected)}] DOWNLOADING {filename}"
    )

    try:

        with session.get(
            url,
            stream=True,
            timeout=600
        ) as response:

            response.raise_for_status()

            with open(output, "wb") as f:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if chunk:
                        f.write(chunk)

        size = os.path.getsize(output)

        if size < 100000:
            print(
                "  WARNING: suspiciously small file:",
                size
            )
            failed += 1
        else:
            downloaded += 1

            print(
                f"  OK: {size / 1024 / 1024:.2f} MB"
            )

    except Exception as e:

        failed += 1

        print(
            "  FAILED:",
            str(e)
        )

print()
print("=" * 70)
print("DOWNLOAD FINISHED")
print("=" * 70)

print("SELECTED :", len(selected))
print("DOWNLOADED:", downloaded)
print("SKIPPED   :", skipped)
print("FAILED    :", failed)
print()
print("OUTPUT:")
print(OUT)