from pathlib import Path
import requests

OUT = Path("data/raw/hydrography/HydroBASINS")
OUT.mkdir(parents=True, exist_ok=True)

URL = "https://data.hydrosheds.org/file/hydrobasins/standard/hybas_as_lev01-12_v1c.zip"

FILE = OUT / "hybas_as_lev01-12_v1c.zip"

print("DOWNLOADING HYDROBASINS ASIA")
print(URL)

with requests.get(URL, stream=True, timeout=900) as r:
    r.raise_for_status()

    total = 0

    with open(FILE, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)
                print(f"\rDOWNLOADED: {total / 1024 / 1024:.1f} MB", end="")

print()
print("======================================")
print("HYDROBASINS ASIA COMPLETE")
print("======================================")
print(FILE)
print(f"SIZE: {FILE.stat().st_size / 1024 / 1024:.1f} MB")
