from pathlib import Path
import json
import csv
import zipfile
import gzip
import rasterio
import geopandas as gpd

RAW = Path("data/raw")
OUT = Path("data/interim/raw_audit.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

records = []

for path in RAW.rglob("*"):
    if not path.is_file():
        continue

    rel = path.relative_to(RAW)
    ext = path.suffix.lower()

    record = {
        "file": str(rel),
        "extension": ext,
        "size_mb": round(path.stat().st_size / 1024 / 1024, 3)
    }

    try:
        if ext in [".tif", ".tiff"]:
            with rasterio.open(path) as src:
                record.update({
                    "type": "raster",
                    "crs": str(src.crs),
                    "width": src.width,
                    "height": src.height,
                    "bands": src.count,
                    "dtype": str(src.dtypes[0]),
                    "resolution": list(src.res),
                    "bounds": list(src.bounds),
                    "nodata": src.nodata
                })

        elif ext in [".geojson", ".json", ".gpkg", ".shp"]:
            try:
                gdf = gpd.read_file(path, rows=1)
                record.update({
                    "type": "vector",
                    "crs": str(gdf.crs),
                    "geometry": str(gdf.geometry.name) if hasattr(gdf, "geometry") else None,
                    "columns": [str(c) for c in gdf.columns]
                })
            except Exception as e:
                record["vector_error"] = str(e)

        elif ext == ".csv":
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.reader(f)
                header = next(reader, [])
                record.update({
                    "type": "csv",
                    "columns": header
                })

        elif ext == ".zip":
            with zipfile.ZipFile(path) as z:
                record.update({
                    "type": "archive",
                    "members": len(z.namelist()),
                    "sample_members": z.namelist()[:20]
                })

        elif ext == ".gz":
            record["type"] = "gzip"

        elif ext == ".kml":
            record["type"] = "kml"

        elif ext == ".pbf":
            record["type"] = "osm_pbf"

        elif ext == ".jp2":
            with rasterio.open(path) as src:
                record.update({
                    "type": "raster",
                    "crs": str(src.crs),
                    "width": src.width,
                    "height": src.height,
                    "bands": src.count,
                    "dtype": str(src.dtypes[0]),
                    "resolution": list(src.res),
                    "bounds": list(src.bounds),
                    "nodata": src.nodata
                })

        else:
            record["type"] = "other"

    except Exception as e:
        record["error"] = str(e)

    records.append(record)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(records, f, indent=2)

print("======================================")
print("CHETAKAI RAW DATA AUDIT COMPLETE")
print("======================================")
print("FILES AUDITED:", len(records))
print("AUDIT FILE:", OUT)
print()

types = {}
for r in records:
    t = r.get("type", "unknown")
    types[t] = types.get(t, 0) + 1

print("FILE TYPES:")
for k, v in sorted(types.items()):
    print(f"  {k}: {v}")
