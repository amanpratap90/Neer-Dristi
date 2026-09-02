import geopandas as gpd
import pandas as pd
import math
from pathlib import Path


BASIN_FILE = Path("data/raw/basin_boundaries/cwc_basins.geojson")
SUBBASIN_FILE = Path("data/raw/basin_boundaries/cwc_subbasins.geojson")

OUTPUT_DIR = Path("data/raw/dem")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "priority_dem_inventory.csv"


TARGET_BASINS = {
    "Godavari": "Godavari",
    "Mahanadi": "Mahanadi",
    "Subarnarekha": "Subernarekha",
    "Brahmaputra": "Brahamaputra",
}


TARGET_SUBBASINS = {
    "Kosi": "Kosi",
}


TARGET_CRS = "EPSG:4326"


def dem_tiles_from_bounds(bounds):
    minx, miny, maxx, maxy = bounds

    min_lon = math.floor(minx)
    max_lon = math.floor(maxx)

    min_lat = math.floor(miny)
    max_lat = math.floor(maxy)

    tiles = []

    for lat in range(min_lat, max_lat + 1):
        for lon in range(min_lon, max_lon + 1):

            if lat >= 0:
                lat_part = f"N{lat:02d}"
            else:
                lat_part = f"S{abs(lat):02d}"

            if lon >= 0:
                lon_part = f"E{lon:03d}"
            else:
                lon_part = f"W{abs(lon):03d}"

            tiles.append(f"{lat_part}{lon_part}")

    return sorted(set(tiles))


def validate_geographic_bounds(bounds, name):
    minx, miny, maxx, maxy = bounds

    if not (
        -180 <= minx <= 180
        and -180 <= maxx <= 180
        and -90 <= miny <= 90
        and -90 <= maxy <= 90
    ):
        raise RuntimeError(
            f"\n{name} GEOMETRY FAILED CRS SANITY CHECK.\n"
            f"Bounds are not geographic coordinates:\n"
            f"  West : {minx}\n"
            f"  South: {miny}\n"
            f"  East : {maxx}\n"
            f"  North: {maxy}\n"
            f"\nExpected EPSG:4326 longitude/latitude coordinates."
        )


def print_bounds(name, bounds):
    minx, miny, maxx, maxy = bounds

    print(f"\n{name} bounds:")
    print(f"  West : {minx:.6f}")
    print(f"  South: {miny:.6f}")
    print(f"  East : {maxx:.6f}")
    print(f"  North: {maxy:.6f}")


print("=" * 70)
print("CHETAKAI V1 PRIORITY DEM INVENTORY")
print("=" * 70)


if not BASIN_FILE.exists():
    raise FileNotFoundError(
        f"Major basin boundary file not found: {BASIN_FILE}"
    )

if not SUBBASIN_FILE.exists():
    raise FileNotFoundError(
        f"Sub-basin boundary file not found: {SUBBASIN_FILE}"
    )


print("\nLoading CWC basin boundaries...")

basins = gpd.read_file(BASIN_FILE)

if basins.empty:
    raise RuntimeError("CWC basin layer is empty.")

if basins.crs is None:
    raise RuntimeError(
        "CWC major basin layer has no CRS. "
        "Cannot safely calculate DEM tiles."
    )

print(f"Loaded major basins: {len(basins)}")
print(f"Original basin CRS: {basins.crs}")


print("\nConverting major basins to EPSG:4326...")

basins = basins.to_crs(TARGET_CRS)

print(f"Working basin CRS: {basins.crs}")


print("\nLoading CWC sub-basins...")

subbasins = gpd.read_file(SUBBASIN_FILE)

if subbasins.empty:
    raise RuntimeError("CWC sub-basin layer is empty.")

if subbasins.crs is None:
    raise RuntimeError(
        "CWC sub-basin layer has no CRS. "
        "Cannot safely calculate DEM tiles."
    )

print(f"Loaded sub-basins: {len(subbasins)}")
print(f"Original sub-basin CRS: {subbasins.crs}")


print("\nConverting sub-basins to EPSG:4326...")

subbasins = subbasins.to_crs(TARGET_CRS)

print(f"Working sub-basin CRS: {subbasins.crs}")


selected = []


print("\n" + "=" * 70)
print("PRIORITY MAJOR BASINS")
print("=" * 70)


for target, cwc_name in TARGET_BASINS.items():

    matches = basins[
        basins["ba_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        == cwc_name.lower()
    ]

    if len(matches) == 1:

        row = matches.iloc[0]

        geometry = row.geometry

        if geometry is None or geometry.is_empty:
            raise RuntimeError(
                f"{target} has empty geometry."
            )

        if not geometry.is_valid:
            print(
                f"WARNING: {target} geometry is invalid."
            )

        bounds = geometry.bounds

        validate_geographic_bounds(bounds, target)

        tiles = dem_tiles_from_bounds(bounds)

        selected.append({
            "inventory_name": target,
            "boundary_type": "CWC_MAJOR_BASIN",
            "basin_id": str(row["id"]),
            "basin_name": row["ba_name"],
            "sub_basin": None,
            "bacode": None,
            "west": bounds[0],
            "south": bounds[1],
            "east": bounds[2],
            "north": bounds[3],
            "dem_tile_count": len(tiles),
            "dem_tiles": ";".join(tiles),
        })

        print(
            f"OK {target:15} -> "
            f"CWC BASIN: {row['ba_name']}"
        )

    elif len(matches) == 0:

        print(
            f"WARNING {target:15} -> "
            f"CWC name NOT FOUND: {cwc_name}"
        )

    else:

        raise RuntimeError(
            f"{target} matched multiple CWC major basins: "
            f"{len(matches)}"
        )


print("\n" + "=" * 70)
print("KOSI SUB-BASIN")
print("=" * 70)


kosi = subbasins[
    subbasins["sub_basin"]
    .astype(str)
    .str.strip()
    .str.lower()
    == TARGET_SUBBASINS["Kosi"].lower()
]


if len(kosi) != 1:
    raise RuntimeError(
        f"Kosi sub-basin was not uniquely found. "
        f"Matches: {len(kosi)}"
    )


kosi_row = kosi.iloc[0]

print("OK Kosi -> CWC SUB-BASIN: Kosi")
print(f"  Parent basin -> {kosi_row['ba_name']}")
print(f"  Basin code   -> {kosi_row['bacode']}")


kosi_geom = kosi_row.geometry


if kosi_geom is None or kosi_geom.is_empty:
    raise RuntimeError(
        "Kosi geometry is empty."
    )


if not kosi_geom.is_valid:
    raise RuntimeError(
        "Kosi geometry is invalid."
    )


kosi_bounds = kosi_geom.bounds

validate_geographic_bounds(
    kosi_bounds,
    "Kosi"
)


print_bounds(
    "Kosi",
    kosi_bounds
)


kosi_tiles = dem_tiles_from_bounds(
    kosi_bounds
)


print("\nKosi DEM tiles:")

for tile in kosi_tiles:
    print(f"  {tile}")


print(f"\nKosi tile count: {len(kosi_tiles)}")


if len(kosi_tiles) != 6:
    raise RuntimeError(
        "\nKOSI TILE COUNT SANITY CHECK FAILED.\n"
        f"Expected 6 tiles but generated {len(kosi_tiles)}.\n"
        f"Generated: {kosi_tiles}"
    )


selected.append({
    "inventory_name": "Kosi",
    "boundary_type": "CWC_SUB_BASIN",
    "basin_id": None,
    "basin_name": kosi_row["ba_name"],
    "sub_basin": kosi_row["sub_basin"],
    "bacode": str(kosi_row["bacode"]),
    "west": kosi_bounds[0],
    "south": kosi_bounds[1],
    "east": kosi_bounds[2],
    "north": kosi_bounds[3],
    "dem_tile_count": len(kosi_tiles),
    "dem_tiles": ";".join(kosi_tiles),
})


print("\n" + "=" * 70)
print("GENERATING DEM TILE INVENTORY")
print("=" * 70)


inventory_rows = []


for item in selected:

    tiles = item["dem_tiles"].split(";")

    for tile in tiles:

        inventory_rows.append({
            "inventory_name": item["inventory_name"],
            "boundary_type": item["boundary_type"],
            "basin_id": item["basin_id"],
            "basin_name": item["basin_name"],
            "sub_basin": item["sub_basin"],
            "bacode": item["bacode"],
            "west": item["west"],
            "south": item["south"],
            "east": item["east"],
            "north": item["north"],
            "dem_tile": tile,
        })


inventory = pd.DataFrame(inventory_rows)


inventory = inventory.sort_values(
    ["inventory_name", "dem_tile"]
).reset_index(drop=True)


print(f"Spatial units: {len(selected)}")
print(f"Unique DEM tiles: {inventory['dem_tile'].nunique()}")


print("\nSpatial units:")

for item in selected:

    print(
        f"  OK {item['inventory_name']:15} "
        f"{item['boundary_type']}"
    )


print("\nTiles by spatial unit:")

tile_counts = (
    inventory
    .groupby("inventory_name")["dem_tile"]
    .nunique()
    .sort_index()
)


for name, count in tile_counts.items():

    print(
        f"  {name:15}: {count} tiles"
    )


print("\nKosi tiles:")

kosi_inventory = inventory[
    inventory["inventory_name"] == "Kosi"
]["dem_tile"].tolist()


for tile in kosi_inventory:
    print(f"  {tile}")


print("\n" + "=" * 70)
print("SAVING INVENTORY")
print("=" * 70)


inventory.to_csv(
    OUTPUT_FILE,
    index=False
)


print(f"Saved:")
print(f"  {OUTPUT_FILE}")


print("\n" + "=" * 70)
print("FINAL VALIDATION")
print("=" * 70)


expected_kosi_tiles = {
    "N25E085",
    "N25E086",
    "N25E087",
    "N26E085",
    "N26E086",
    "N26E087",
}


actual_kosi_tiles = set(kosi_inventory)


if actual_kosi_tiles != expected_kosi_tiles:

    print("ERROR: Kosi tile validation failed.")

    print(
        "Expected:",
        sorted(expected_kosi_tiles)
    )

    print(
        "Actual:",
        sorted(actual_kosi_tiles)
    )

    raise RuntimeError(
        "Kosi DEM inventory does not match expected tiles."
    )


print("OK Kosi tile validation passed.")
print("OK CRS validation passed.")
print("OK Geographic bounds validation passed.")
print("OK DEM inventory generated successfully.")


print("\n" + "=" * 70)
print("RAW DATA POLICY")
print("=" * 70)

print(
    "Keep original Copernicus GLO-30 tiles unchanged."
)

print(
    "Do NOT clip, resample, fill sinks, or preprocess here."
)

print(
    "Processing will happen after raw-data collection."
)

print("\nCHETAKAI V1 DEM INVENTORY COMPLETE.")