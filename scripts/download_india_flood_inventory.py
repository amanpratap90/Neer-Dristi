from pathlib import Path
import requests

OUT = Path("data/raw/flood_events/india_flood_inventory")
OUT.mkdir(parents=True, exist_ok=True)

URL = "https://zenodo.org/records/11275211/files/India_Flood_Inventory_v3.csv?download=1"
FILE = OUT / "India_Flood_Inventory_v3.csv"

print("DOWNLOADING INDIA FLOOD INVENTORY v3...")
print("1967-2023")

r = requests.get(URL, stream=True, timeout=300)
r.raise_for_status()

with open(FILE, "wb") as f:
    for chunk in r.iter_content(chunk_size=1024 * 1024):
        if chunk:
            f.write(chunk)

print()
print("======================================")
print("FLOOD INVENTORY COMPLETE")
print("======================================")
print(FILE)
print(f"SIZE: {FILE.stat().st_size / 1024 / 1024:.2f} MB")
