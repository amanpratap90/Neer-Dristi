from pathlib import Path
from pystac_client import Client
import planetary_computer

OUT = Path("data/raw/satellite/sentinel1")
OUT.mkdir(parents=True, exist_ok=True)

BBOX = [85.0579402, 25.3548235, 87.2866913, 26.8738829]

catalog = Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1"
)

search = catalog.search(
    collections=["sentinel-1-grd"],
    bbox=BBOX,
    datetime="2020-01-01/2025-12-31",
    query={
        "sar:instrument_mode": {"eq": "IW"}
    },
    max_items=200
)

items = list(search.items())

print("TOTAL KOSI SENTINEL-1 ITEMS:", len(items))

# Keep only approximately one useful scene per month.
selected = {}

for item in items:
    dt = item.datetime
    key = f"{dt.year}-{dt.month:02d}"

    if key not in selected:
        selected[key] = item

print("SELECTED MONTHLY SCENES:", len(selected))
print()

for key, item in sorted(selected.items()):
    print(
        key,
        "|",
        item.id,
        "|",
        item.properties.get("sat:orbit_state")
    )

print()
print("======================================")
print("KOSI SENTINEL-1 MVP INVENTORY COMPLETE")
print("======================================")
