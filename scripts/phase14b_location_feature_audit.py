from pathlib import Path
import pandas as pd

ROOT = Path("data")

print("=" * 110)
print("CHETAKAI V1 — PHASE 14B LOCATION FEATURE BUILDER AUDIT")
print("=" * 110)

keywords = [
    "basin",
    "admin",
    "dem",
    "elevation",
    "slope",
    "flow",
    "river",
    "lulc",
    "land",
    "soil",
    "population",
    "infrastructure",
    "rainfall",
    "radar",
    "satellite",
    "nwp",
    "weather",
]

files = []

for ext in ["*.csv", "*.geojson", "*.gpkg", "*.shp", "*.tif", "*.vrt"]:
    files.extend(ROOT.rglob(ext))

print()
print("TOTAL DATA FILES :", len(files))
print("-" * 110)

for path in sorted(files):
    name = path.name.lower()

    matched = [
        k for k in keywords
        if k in name
    ]

    if not matched:
        continue

    print()
    print("FILE :", path)
    print("TYPE :", path.suffix)
    print("MATCH :", ", ".join(matched))

    if path.suffix.lower() == ".csv":
        try:
            df = pd.read_csv(path, nrows=3)

            print("COLUMNS :", len(df.columns))
            print("FIELDS  :")

            for c in df.columns:
                print("   ", c)

        except Exception as e:
            print("CSV READ ERROR :", e)

print()
print("=" * 110)
print("PHASE 14B AUDIT COMPLETE")
print("=" * 110)

print("""
NEXT STEP

We will use the audit to construct:

LAT/LON
  ↓
Basin resolver
  ↓
Administrative resolver
  ↓
Raster/vector spatial feature extraction
  ↓
Dynamic data resolver
  ↓
Production feature schema
  ↓
Persisted Phase-13 classifier
""")