import requests
import json
import os

URL = "https://stac.dataspace.copernicus.eu/v1/search"

payload = {
    "collections": ["sentinel-2-l2a"],
    "bbox": [73.38327110615607, 10.123562362103087, 97.41289624088454, 31.46207936959709],
    "datetime": "2024-01-01T00:00:00Z/2025-12-31T23:59:59Z",
    "query": {
        "eo:cloud_cover": {
            "lte": 10
        }
    },
    "limit": 20,
    "sortby": [
        {
            "field": "properties.eo:cloud_cover",
            "direction": "asc"
        }
    ]
}

print("=" * 70)
print("CHETAKAI - SENTINEL-2 L2A SEARCH")
print("=" * 70)
print("AOI: INDIA BASIN REGION")
print("CLOUD COVER: <= 10%")
print("PERIOD: 2024-2025")
print()

r = requests.post(URL, json=payload, timeout=300)

print("STATUS:", r.status_code)

if r.status_code != 200:
    print(r.text[:2000])
    raise SystemExit

data = r.json()
items = data.get("features", [])

print("SCENES FOUND:", len(items))
print()

os.makedirs("data/raw/satellite", exist_ok=True)

with open(
    "data/raw/satellite/sentinel2_catalog.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(data, f, indent=2)

for i, item in enumerate(items, 1):
    p = item.get("properties", {})
    print(
        f"[{i}] {item.get('id')}"
        f" | {p.get('datetime')}"
        f" | CLOUD {p.get('eo:cloud_cover')}%"
    )

print()
print("CATALOG SAVED")
print("data/raw/satellite/sentinel2_catalog.json")
print("=" * 70)
