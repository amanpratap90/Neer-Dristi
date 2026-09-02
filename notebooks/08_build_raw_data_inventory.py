from pathlib import Path
import json
import csv
import rasterio
import geopandas as gpd
from rasterio.errors import RasterioIOError

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "inventory"

OUT.mkdir(parents=True, exist_ok=True)

RASTER_EXTENSIONS = {".tif", ".tiff", ".img", ".vrt"}
VECTOR_EXTENSIONS = {".shp", ".geojson", ".gpkg", ".json"}

rows = []
errors = []

def raster_inventory(path):
    try:
        with rasterio.open(path) as src:
            data = {
                "file": str(path.relative_to(ROOT)),
                "type": "raster",
                "format": path.suffix.lower(),
                "crs": str(src.crs),
                "width": src.width,
                "height": src.height,
                "bands": src.count,
                "resolution_x": src.res[0],
                "resolution_y": src.res[1],
                "bounds_left": src.bounds.left,
                "bounds_bottom": src.bounds.bottom,
                "bounds_right": src.bounds.right,
                "bounds_top": src.bounds.top,
                "nodata": src.nodata,
                "dtype": str(src.dtypes[0]),
                "valid": True,
                "error": ""
            }

            try:
                sample = src.read(1, masked=True)
                data["nodata_percent_sample"] = round(
                    float(sample.mask.mean() * 100), 4
                )
            except Exception:
                data["nodata_percent_sample"] = None

            rows.append(data)

    except Exception as e:
        errors.append({
            "file": str(path.relative_to(ROOT)),
            "type": "raster",
            "error": str(e)
        })

def vector_inventory(path):
    try:
        gdf = gpd.read_file(path)

        bounds = gdf.total_bounds

        rows.append({
            "file": str(path.relative_to(ROOT)),
            "type": "vector",
            "format": path.suffix.lower(),
            "crs": str(gdf.crs),
            "width": "",
            "height": "",
            "bands": "",
            "resolution_x": "",
            "resolution_y": "",
            "bounds_left": bounds[0],
            "bounds_bottom": bounds[1],
            "bounds_right": bounds[2],
            "bounds_top": bounds[3],
            "nodata": "",
            "dtype": "",
            "valid": True,
            "error": "",
            "feature_count": len(gdf),
            "geometry_types": ",".join(
                sorted(gdf.geometry.geom_type.dropna().unique())
            )
        })

    except Exception as e:
        errors.append({
            "file": str(path.relative_to(ROOT)),
            "type": "vector",
            "error": str(e)
        })

print("=" * 80)
print("CHETAKAI V1 RAW DATA INVENTORY & VALIDATION")
print("=" * 80)
print(f"RAW DIRECTORY: {RAW}")
print()

if not RAW.exists():
    raise FileNotFoundError(f"Raw directory does not exist: {RAW}")

all_files = [
    p for p in RAW.rglob("*")
    if p.is_file()
]

print(f"Files discovered: {len(all_files)}")
print()

for path in all_files:
    suffix = path.suffix.lower()

    if suffix in RASTER_EXTENSIONS:
        print(f"[RASTER] {path.relative_to(ROOT)}")
        raster_inventory(path)

    elif suffix in VECTOR_EXTENSIONS:
        print(f"[VECTOR] {path.relative_to(ROOT)}")
        vector_inventory(path)

print()
print("-" * 80)
print("WRITING INVENTORY")
print("-" * 80)

csv_path = OUT / "raw_data_inventory.csv"

if rows:
    fieldnames = sorted({
        key
        for row in rows
        for key in row.keys()
    })

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

json_path = OUT / "validation_report.json"

report = {
    "root": str(ROOT),
    "raw_directory": str(RAW),
    "total_files_discovered": len(all_files),
    "validated_files": len(rows),
    "failed_files": len(errors),
    "errors": errors,
    "inventory": rows
}

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, default=str)

print(f"Inventory CSV : {csv_path}")
print(f"Validation JSON: {json_path}")
print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Discovered : {len(all_files)}")
print(f"Validated  : {len(rows)}")
print(f"Failed     : {len(errors)}")
print()

if errors:
    print("FAILED FILES:")
    for error in errors:
        print(f"  ❌ {error['file']}")
        print(f"     {error['error']}")
else:
    print("✅ No files failed validation.")

print()
print("Inventory complete.")