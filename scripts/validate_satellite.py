from pathlib import Path
import rasterio
from collections import Counter

ROOT = Path("data/raw/satellite")

files = [
    p for p in ROOT.rglob("*")
    if p.is_file() and p.suffix.lower() in {".tif", ".jp2"}
]

print("=" * 100)
print("SATELLITE VALIDATION")
print("=" * 100)

print(f"FILES: {len(files)}")
print()

crs_counter = Counter()
res_counter = Counter()
dtype_counter = Counter()

valid = []
bad = []

for path in sorted(files):

    try:
        with rasterio.open(path) as src:

            info = {
                "file": path.name,
                "width": src.width,
                "height": src.height,
                "bands": src.count,
                "crs": str(src.crs),
                "res": src.res,
                "dtype": src.dtypes[0],
                "nodata": src.nodata,
            }

            valid.append(info)

            crs_counter[str(src.crs)] += 1
            res_counter[str(src.res)] += 1
            dtype_counter[src.dtypes[0]] += 1

    except Exception as e:
        bad.append((path.name, str(e)))


print("CRS")
for k, v in crs_counter.items():
    print(f"  {k}: {v}")

print()

print("RESOLUTION")
for k, v in res_counter.items():
    print(f"  {k}: {v}")

print()

print("DTYPE")
for k, v in dtype_counter.items():
    print(f"  {k}: {v}")

print()

print("=" * 100)
print("VALID FILES")
print("=" * 100)

for x in valid:
    print(
        f"{x['file']} | "
        f"{x['width']}x{x['height']} | "
        f"bands={x['bands']} | "
        f"CRS={x['crs']} | "
        f"RES={x['res']} | "
        f"DTYPE={x['dtype']} | "
        f"NODATA={x['nodata']}"
    )

print()

print("=" * 100)
print("BAD / UNREADABLE FILES")
print("=" * 100)

if bad:
    for name, error in bad:
        print(name)
        print("  ERROR:", error)
else:
    print("None")

print()

print("=" * 100)
print("DONE")
print("=" * 100)
