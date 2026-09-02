import json
from pathlib import Path

src = Path("data/raw/basin_boundaries/cwc_subbasins.geojson")
out = Path("data/raw/basins/kosi_basin.geojson")
out.parent.mkdir(parents=True, exist_ok=True)

with open(src, encoding="utf-8") as f:
    data = json.load(f)

features = [
    x for x in data["features"]
    if "kosi" in str(x["properties"]).lower()
]

if not features:
    raise RuntimeError("Kosi feature not found")

result = {
    "type": "FeatureCollection",
    "features": features
}

with open(out, "w", encoding="utf-8") as f:
    json.dump(result, f)

print("KOSI FEATURES:", len(features))
print("CREATED:", out)

for x in features:
    print(x["properties"])
