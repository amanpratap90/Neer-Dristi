from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

files = [p for p in RAW.rglob("*") if p.is_file()]

print("=" * 80)
print("CHETAKAI RAW DATASET SUMMARY")
print("=" * 80)

print(f"\nTotal files: {len(files)}")

print("\nDATASET FOLDERS")
print("-" * 80)

groups = defaultdict(list)

for p in files:
    rel = p.relative_to(RAW)
    dataset = rel.parts[0] if len(rel.parts) > 0 else "[ROOT]"
    groups[dataset].append(p)

for dataset, items in sorted(groups.items()):
    extensions = Counter(
        p.suffix.lower() if p.suffix else "[NO EXT]"
        for p in items
    )

    ext_text = ", ".join(
        f"{ext}={count}"
        for ext, count in extensions.items()
    )

    print(f"{dataset:30} files={len(items):4}   {ext_text}")

print("\nALL EXTENSIONS")
print("-" * 80)

extensions = Counter(
    p.suffix.lower() if p.suffix else "[NO EXT]"
    for p in files
)

for ext, count in extensions.most_common():
    print(f"{ext:15} {count}")

print("\nUNRECOGNIZED EXTENSIONS")
print("-" * 80)

known = {
    ".tif",
    ".tiff",
    ".img",
    ".vrt",
    ".shp",
    ".geojson",
    ".gpkg",
    ".json"
}

unknown = [
    p for p in files
    if p.suffix.lower() not in known
]

unknown_groups = defaultdict(list)

for p in unknown:
    rel = p.relative_to(RAW)
    dataset = rel.parts[0] if rel.parts else "[ROOT]"
    unknown_groups[dataset].append(p)

for dataset, items in sorted(unknown_groups.items()):
    print(f"\n{dataset}: {len(items)} files")

    shown = 0

    for p in items:
        print(f"  {p.relative_to(RAW)}")
        shown += 1

        if shown >= 10:
            if len(items) > 10:
                print(f"  ... and {len(items) - 10} more")
            break

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)