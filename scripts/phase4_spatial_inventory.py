from pathlib import Path
import geopandas as gpd
import rasterio


ROOT = Path("data")

print("=" * 110)
print("CHETAKAI — PHASE 4.1: SPATIAL DATA INVENTORY")
print("=" * 110)


# ================================================================
# VECTOR DATA
# ================================================================

VECTOR_FILES = [
    "raw/basin_boundaries/cwc_basins.geojson",
    "raw/basin_boundaries/cwc_subbasins.geojson",
    "processed/flood_events/flood_events_district.geojson",
]


print("\n[1/3] VECTOR DATA")
print("-" * 110)

for relative in VECTOR_FILES:

    path = ROOT / relative

    print(f"\nFILE: {relative}")

    if not path.exists():
        print("✗ NOT FOUND")
        continue

    try:
        gdf = gpd.read_file(path)

        print(f"Rows       : {len(gdf)}")
        print(f"CRS        : {gdf.crs}")
        print(f"Geometry   : {gdf.geometry.geom_type.value_counts().to_dict()}")
        print(f"Valid geom : {gdf.geometry.is_valid.sum()}/{len(gdf)}")

        if gdf.crs:
            bounds = gdf.to_crs(4326).total_bounds
            print(
                "WGS84 bounds:",
                f"W={bounds[0]:.4f}",
                f"S={bounds[1]:.4f}",
                f"E={bounds[2]:.4f}",
                f"N={bounds[3]:.4f}"
            )

    except Exception as e:

        print("✗ ERROR:", e)


# ================================================================
# RASTER DATA
# ================================================================

RASTER_FILES = [
    "processed/features/terrain/dem_mosaic_slope.tif",
    "processed/features/terrain/N25E085_elevation.tif",
    "processed/features/terrain/N25E085_slope.tif",
    "processed/features/terrain/N25E086_elevation.tif",
    "processed/features/terrain/N25E086_slope.tif",
    "processed/features/terrain/N25E086_slope.tif",
]


print("\n\n[2/3] RASTER DATA")
print("-" * 110)

for relative in RASTER_FILES:

    path = ROOT / relative

    print(f"\nFILE: {relative}")

    if not path.exists():
        print("✗ NOT FOUND")
        continue

    try:

        with rasterio.open(path) as src:

            print(f"CRS        : {src.crs}")
            print(f"Size       : {src.width} x {src.height}")
            print(f"Resolution : {src.res}")
            print(f"Bands      : {src.count}")
            print(f"Dtype      : {src.dtypes}")
            print(f"NoData     : {src.nodata}")
            print(f"Bounds     : {src.bounds}")

    except Exception as e:

        print("✗ ERROR:", e)


# ================================================================
# PROCESSED TERRAIN INVENTORY
# ================================================================

print("\n\n[3/3] TERRAIN RASTER INVENTORY")
print("-" * 110)

terrain_dir = ROOT / "processed/features/terrain"

if terrain_dir.exists():

    rasters = list(terrain_dir.glob("*.tif"))

    print(f"Terrain rasters found: {len(rasters)}")

    for r in sorted(rasters):
        print(" ", r.name)

else:

    print("✗ Terrain directory missing")


print("\n" + "=" * 110)
print("PHASE 4.1 INVENTORY COMPLETE")
print("=" * 110)