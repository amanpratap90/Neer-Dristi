from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import geopandas as gpd
import planetary_computer
import pystac_client

print("=" * 70)
print("CHETAKAI V1 - CONTROLLED PARALLEL SENTINEL-2 ACQUISITION")
print("=" * 70)

ROOT = Path(__file__).resolve().parents[1]

BASIN_FILE = (
    ROOT
    / "data"
    / "raw"
    / "basin_boundaries"
    / "cwc_basins.geojson"
)

OUT_DIR = (
    ROOT
    / "data"
    / "raw"
    / "satellite"
    / "sentinel2"
    / "bands"
)

OUT_DIR.mkdir(parents=True, exist_ok=True)

CATALOG_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"

START_DATE = "2024-01-01"
END_DATE = "2026-08-28"

MAX_CLOUD = 40
SCENES_PER_BASIN = 4
MAX_WORKERS = 3

PRIORITY = [
    "GODAVARI",
    "MAHANADI",
    "SUBERNAREKHA",
    "BRAHAMAPUTRA",
]

BANDS = [
    "B03",
    "B04",
    "B08",
]


def normalize_name(value):
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .upper()
        .replace("_", " ")
    )


def find_name_column(gdf):
    candidates = [
        "ba_code",
        "ba_name",
        "basin_name",
        "Basin_Name",
        "BASIN_NAME",
        "name",
        "Name",
        "NAME",
    ]

    for col in candidates:
        if col in gdf.columns:
            return col

    raise RuntimeError(
        "Could not find basin name column."
    )


def find_basin(gdf, name_col, target):
    target = normalize_name(target)

    for _, row in gdf.iterrows():

        values = [
            normalize_name(row.get("ba_code")),
            normalize_name(row.get("ba_name")),
            normalize_name(row.get(name_col)),
        ]

        if target in values:
            return row

    aliases = {
        "BRAHAMAPUTRA": [
            "BRAHMAPUTRA",
            "BRAHAMAPUTRA",
            "BRAHMAPUTRA BASIN",
        ],
        "SUBERNAREKHA": [
            "SUBERNAREKHA",
            "SUBARNAREKHA",
        ],
    }

    for alias in aliases.get(target, []):
        alias = normalize_name(alias)

        for _, row in gdf.iterrows():

            values = [
                normalize_name(row.get("ba_code")),
                normalize_name(row.get("ba_name")),
                normalize_name(row.get(name_col)),
            ]

            if alias in values:
                return row

    return None


def load_targets():

    print()
    print("LOADING BASINS...")

    basins = gpd.read_file(BASIN_FILE)

    if basins.crs is None:
        raise RuntimeError(
            "Basin CRS is missing."
        )

    print("Total basins:", len(basins))
    print("Basin CRS:", basins.crs)

    name_col = find_name_column(basins)

    basins = basins.to_crs(4326)

    targets = []

    for name in PRIORITY:

        row = find_basin(
            basins,
            name_col,
            name
        )

        if row is None:

            print(
                "WARNING: basin not found:",
                name
            )

            continue

        bounds = list(
            row.geometry.bounds
        )

        targets.append(
            {
                "name": name.title(),
                "bounds": bounds,
            }
        )

    return targets


def search_scenes(catalog, bounds):

    print()
    print("SEARCHING SENTINEL-2...")
    print(
        f"TIME: {START_DATE} -> {END_DATE}"
    )

    search = catalog.search(
        collections=[COLLECTION],
        bbox=bounds,
        datetime=(
            f"{START_DATE}T00:00:00Z/"
            f"{END_DATE}T23:59:59Z"
        ),
    )

    items = list(
        search.item_collection()
    )

    print(
        "RAW SCENES FOUND:",
        len(items)
    )

    filtered = []

    for item in items:

        cloud = item.properties.get(
            "eo:cloud_cover"
        )

        if cloud is None:
            filtered.append(item)
            continue

        try:
            cloud = float(cloud)
        except Exception:
            continue

        if cloud <= MAX_CLOUD:
            filtered.append(item)

    print(
        f"SCENES <= {MAX_CLOUD}% CLOUD:",
        len(filtered)
    )

    filtered.sort(
        key=lambda item: (
            float(
                item.properties.get(
                    "eo:cloud_cover",
                    100
                )
            ),
            item.datetime
            or datetime.max.replace(
                tzinfo=timezone.utc
            ),
        )
    )

    return filtered


def choose_scenes(items):

    if not items:
        return []

    selected = []
    used_tiles = set()

    for item in items:

        tile = item.properties.get(
            "s2:mgrs_tile"
        )

        if not tile:
            continue

        if tile in used_tiles:
            continue

        selected.append(item)
        used_tiles.add(tile)

        if len(selected) >= SCENES_PER_BASIN:
            break

    return selected


def get_asset(item, band):

    possible = [
        band,
        f"{band}-10m",
        band.lower(),
    ]

    for key in possible:

        if key in item.assets:
            return item.assets[key]

    return None


def download_asset(asset, output):

    if output.exists() and output.stat().st_size > 0:

        return "EXISTS"

    partial = output.with_suffix(
        output.suffix + ".part"
    )

    if partial.exists():
        partial.unlink()

    signed = planetary_computer.sign(
        asset
    )

    response = requests.get(
        signed.href,
        stream=True,
        timeout=(30, 300)
    )

    response.raise_for_status()

    with open(partial, "wb") as f:

        for chunk in response.iter_content(
            chunk_size=4 * 1024 * 1024
        ):

            if chunk:
                f.write(chunk)

    partial.replace(output)

    return "DOWNLOADED"


def download_one(task):

    item = task["item"]
    band = task["band"]
    output = task["output"]

    tile = task["tile"]
    date = task["date"]

    asset = get_asset(
        item,
        band
    )

    if asset is None:

        return (
            tile,
            date,
            band,
            "MISSING_ASSET"
        )

    try:

        result = download_asset(
            asset,
            output
        )

        return (
            tile,
            date,
            band,
            result
        )

    except Exception as e:

        return (
            tile,
            date,
            band,
            f"ERROR: {type(e).__name__}: {e}"
        )


def process_target(catalog, target):

    name = target["name"]
    bounds = target["bounds"]

    print()
    print("=" * 70)
    print("TARGET:", name)
    print("=" * 70)
    print("BOUNDS:", *bounds)

    items = search_scenes(
        catalog,
        bounds
    )

    if not items:

        print("NO SENTINEL-2 SCENES FOUND")
        return 0

    selected = choose_scenes(
        items
    )

    print()
    print(
        "SELECTED SCENES:",
        len(selected)
    )

    tasks = []

    for item in selected:

        tile = item.properties.get(
            "s2:mgrs_tile",
            "UNKNOWN"
        )

        date = item.datetime

        date_string = (
            date.strftime("%Y%m%d")
            if date
            else "UNKNOWN"
        )

        cloud = item.properties.get(
            "eo:cloud_cover",
            100
        )

        print()
        print("ITEM:", item.id)
        print("DATE:", date)
        print("TILE:", tile)
        print("CLOUD:", cloud)

        for band in BANDS:

            filename = (
                f"{tile}_"
                f"{date_string}_"
                f"{band}.tif"
            )

            output = OUT_DIR / filename

            tasks.append(
                {
                    "item": item,
                    "band": band,
                    "output": output,
                    "tile": tile,
                    "date": date_string,
                }
            )

    print()
    print(
        "DOWNLOAD TASKS:",
        len(tasks)
    )

    completed = 0

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [
            executor.submit(
                download_one,
                task
            )
            for task in tasks
        ]

        for future in as_completed(futures):

            tile, date, band, status = (
                future.result()
            )

            print(
                f"  {tile}_{date}_{band}: "
                f"{status}"
            )

            if status in [
                "DOWNLOADED",
                "EXISTS",
            ]:
                completed += 1

    return completed


print()
print(
    "CONNECTING TO PLANETARY COMPUTER..."
)

catalog = pystac_client.Client.open(
    CATALOG_URL
)

print("CONNECTED")

targets = load_targets()

print()
print("=" * 70)
print("SATELLITE TARGETS")
print("=" * 70)

for target in targets:

    print(
        f"{target['name']} -> "
        f"{target['bounds']}"
    )

print()
print("=" * 70)
print("STARTING CONTROLLED ACQUISITION")
print("=" * 70)

total_completed = 0

for target in targets:

    total_completed += process_target(
        catalog,
        target
    )

print()
print("=" * 70)
print("SATELLITE DOWNLOAD VALIDATION")
print("=" * 70)

files = list(
    OUT_DIR.glob("*.tif")
)

print()
print(
    "TOTAL TIFF FILES:",
    len(files)
)

for band in BANDS:

    count = sum(
        1
        for f in files
        if f"_{band}.tif" in f.name
    )

    print(
        f"{band}:",
        count
    )

print()
print(
    "NEW/EXISTING TASKS COMPLETED:",
    total_completed
)

print()
print("OUTPUT DIRECTORY:")
print(OUT_DIR)

print()
print("=" * 70)
print(
    "CONTROLLED PARALLEL SATELLITE "
    "ACQUISITION COMPLETE"
)
print("=" * 70)