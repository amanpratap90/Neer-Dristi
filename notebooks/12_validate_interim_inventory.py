from pathlib import Path
import json
import hashlib
import rasterio
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
MANIFEST = ROOT / "data" / "manifests"

OUT = MANIFEST / "interim_inventory.json"

results = {
    "rasters": [],
    "vectors": [],
    "other": [],
    "errors": []
}


def checksum(path, block_size=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(block_size):
            h.update(block)
    return h.hexdigest()


for path in sorted(INTERIM.rglob("*")):
    if not path.is_file():
        continue

    suffix = path.suffix.lower()

    try:
        if suffix in [".tif", ".tiff"]:

            with rasterio.open(path) as src:
                item = {
                    "path": str(path.relative_to(ROOT)),
                    "type": "raster",
                    "crs": str(src.crs),
                    "width": src.width,
                    "height": src.height,
                    "count": src.count,
                    "dtype": str(src.dtypes[0]),
                    "nodata": src.nodata,
                    "resolution_x": src.res[0],
                    "resolution_y": src.res[1],
                    "bounds": list(src.bounds),
                    "transform": list(src.transform),
                    "sha256": checksum(path)
                }

            results["rasters"].append(item)

        elif suffix in [".geojson", ".json", ".gpkg", ".shp"]:

            try:
                gdf = gpd.read_file(path)

                item = {
                    "path": str(path.relative_to(ROOT)),
                    "type": "vector",
                    "features": len(gdf),
                    "crs": str(gdf.crs),
                    "geometry_types": sorted(
                        gdf.geometry.geom_type.dropna().unique().tolist()
                    ),
                    "empty_geometries": int(gdf.geometry.is_empty.sum()),
                    "invalid_geometries": int(
                        (~gdf.geometry.is_valid.fillna(False)).sum()
                    ),
                    "sha256": checksum(path)
                }

                results["vectors"].append(item)

            except Exception as e:
                results["errors"].append({
                    "path": str(path.relative_to(ROOT)),
                    "error": str(e)
                })

        else:
            results["other"].append({
                "path": str(path.relative_to(ROOT)),
                "extension": suffix,
                "size_bytes": path.stat().st_size,
                "sha256": checksum(path)
            })

    except Exception as e:
        results["errors"].append({
            "path": str(path.relative_to(ROOT)),
            "error": str(e)
        })


MANIFEST.mkdir(parents=True, exist_ok=True)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("=" * 80)
print("CHETAKAI V1 INTERIM INVENTORY VALIDATION")
print("=" * 80)
print(f"Rasters : {len(results['rasters'])}")
print(f"Vectors : {len(results['vectors'])}")
print(f"Other   : {len(results['other'])}")
print(f"Errors  : {len(results['errors'])}")
print(f"Output  : {OUT}")
print("=" * 80)