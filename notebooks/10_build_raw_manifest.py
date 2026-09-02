from pathlib import Path
import csv
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "manifests" / "raw_manifest.csv"

rows = []

for path in sorted(RAW.rglob("*")):
    if not path.is_file():
        continue

    relative = path.relative_to(RAW)
    parts = relative.parts

    dataset = parts[0] if parts else "unknown"

    stat = path.stat()

    rows.append({
        "relative_path": str(relative),
        "dataset": dataset,
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 3),
        "modified_time": datetime.fromtimestamp(
            stat.st_mtime
        ).isoformat()
    })

OUT.parent.mkdir(parents=True, exist_ok=True)

with OUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "relative_path",
            "dataset",
            "extension",
            "size_bytes",
            "size_mb",
            "modified_time"
        ]
    )
    writer.writeheader()
    writer.writerows(rows)

print("=" * 80)
print("CHETAKAI V1 RAW MANIFEST")
print("=" * 80)
print(f"Raw directory : {RAW}")
print(f"Files indexed : {len(rows)}")
print(f"Manifest      : {OUT}")
print("=" * 80)