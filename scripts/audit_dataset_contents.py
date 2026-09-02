from pathlib import Path
import json
import pandas as pd
import rasterio

RAW = Path("data/raw")

print("=" * 70)
print("CHETAKAI DATA ENGINEERING - DATASET CONTENT AUDIT")
print("=" * 70)

for group in sorted(RAW.iterdir()):
    if not group.is_dir():
        continue

    files = [x for x in group.rglob("*") if x.is_file()]

    print()
    print("=" * 70)
    print(f"GROUP: {group.name}")
    print(f"FILES: {len(files)}")
    print("=" * 70)

    for path in files:
        size = path.stat().st_size / 1024 / 1024
        ext = path.suffix.lower()

        print()
        print(f"FILE: {path.relative_to(RAW)}")
        print(f"SIZE: {size:.2f} MB")

        try:
            if ext in [".tif", ".tiff", ".jp2"]:
                with rasterio.open(path) as src:
                    print("TYPE: RASTER")
                    print("CRS:", src.crs)
                    print("SIZE:", src.width, "x", src.height)
                    print("BANDS:", src.count)
                    print("DTYPE:", src.dtypes[0])
                    print("RESOLUTION:", src.res)
                    print("NODATA:", src.nodata)
                    print(
                        "BOUNDS:",
                        tuple(round(x, 4) for x in src.bounds)
                    )

            elif ext == ".csv":
                try:
                    df = pd.read_csv(path, nrows=5)
                    print("TYPE: CSV")
                    print("COLUMNS:", list(df.columns))
                    print("SAMPLE ROWS:", len(df))
                except Exception as e:
                    print("CSV ERROR:", e)

            elif ext in [".geojson", ".json"]:
                try:
                    with open(path, encoding="utf-8") as f:
                        d = json.load(f)

                    print("TYPE: JSON/GEOJSON")
                    print("TOP LEVEL:", list(d.keys()))

                    if "features" in d:
                        print("FEATURES:", len(d["features"]))

                        if d["features"]:
                            properties = d["features"][0].get(
                                "properties", {}
                            )
                            print(
                                "PROPERTY FIELDS:",
                                list(properties.keys())
                            )

                except Exception as e:
                    print("JSON ERROR:", e)

            elif ext == ".gz":
                print("TYPE: GZIP")

            elif ext == ".kml":
                print("TYPE: KML")

            elif ext == ".pbf":
                print("TYPE: OSM PBF")

            elif ext == ".zip":
                print("TYPE: ZIP")

            else:
                print("TYPE: OTHER")

        except Exception as e:
            print("AUDIT ERROR:", e)

print()
print("=" * 70)
print("DATASET CONTENT AUDIT COMPLETE")
print("=" * 70)
