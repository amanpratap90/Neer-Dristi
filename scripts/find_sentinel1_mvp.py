from pathlib import Path
from pystac_client import Client

OUT = Path("data/raw/satellite/sentinel1")
OUT.mkdir(parents=True, exist_ok=True)

# Approximate India coverage
BBOX = [73.3, 10.0, 97.5, 31.6]

catalog = Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1"
)

search = catalog.search(
    collections=["sentinel-1-grd"],
    bbox=BBOX,
    datetime="2019-01-01/2025-12-31",
    max_items=50
)

items = list(search.items())

print("SENTINEL-1 ITEMS FOUND:", len(items))

for item in items[:50]:
    print(item.id, item.datetime)

print()
print("SATELLITE INVENTORY COMPLETE")
print("We will download only basin-intersecting scenes next.")
