from pathlib import Path
import requests

OUT = Path("data/raw/reservoirs")
OUT.mkdir(parents=True, exist_ok=True)

URL = "https://data.hydrosheds.org/file/hydrolakes/HydroLAKES_points_v10_shp.zip"
FILE = OUT / "HydroLAKES_points_v10_shp.zip"

print("DOWNLOADING HydroLAKES POINTS...")
print(URL)

with requests.get(URL, stream=True, timeout=900) as r:
    r.raise_for_status()
    total = 0
    with open(FILE, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)
                print(f"\rDOWNLOADED: {total/1024/1024:.1f} MB", end="")

print()
print("======================================")
print("HYDROLAKES POINTS COMPLETE")
print("======================================")
print(FILE)
print(f"SIZE: {FILE.stat().st_size/1024/1024:.1f} MB")
