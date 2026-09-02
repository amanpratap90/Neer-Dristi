from pathlib import Path
import glob
import rasterio

files = sorted(glob.glob(r"data/raw/land_use_land_cover/**/*.tif", recursive=True))

print("=" * 70)
print("CHETAKAI V1 WORLDCOVER TILE INTEGRITY CHECK")
print("=" * 70)
print("TOTAL TILES:", len(files))
print()

good = []
bad = []

for i, f in enumerate(files, 1):
    name = Path(f).name
    try:
        with rasterio.open(f) as src:
            width = src.width
            height = src.height

            # Read several windows across the tile.
            windows = [
                (0, 0),
                (width // 2, 0),
                (0, height // 2),
                (width // 2, height // 2),
                (max(0, width - 512), max(0, height - 512)),
            ]

            for x, y in windows:
                w = min(512, width - x)
                h = min(512, height - y)
                src.read(1, window=rasterio.windows.Window(x, y, w, h))

        good.append(f)
        print(f"[{i:02d}/{len(files):02d}] OK   {name}")

    except Exception as e:
        bad.append(f)
        print(f"[{i:02d}/{len(files):02d}] BAD  {name}")
        print("       ", str(e).splitlines()[0])

print()
print("=" * 70)
print("INTEGRITY SUMMARY")
print("=" * 70)
print("GOOD:", len(good))
print("BAD :", len(bad))

if bad:
    print()
    print("CORRUPTED TILES:")
    for f in bad:
        print(" -", f)
