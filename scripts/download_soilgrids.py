import os
import requests

URL = "https://files.isric.org/soilgrids/latest/data/sand/sand_0-5cm_mean.vrt"

OUT = "data/raw/soil/soilgrids/sand_0-5cm_mean.vrt"

os.makedirs(os.path.dirname(OUT), exist_ok=True)

print("=" * 70)
print("DOWNLOADING SOILGRIDS 250m SAND VRT")
print("=" * 70)
print()
print("SOURCE:", URL)
print()

with requests.get(URL, stream=True, timeout=300) as r:
    print("STATUS:", r.status_code)
    print("CONTENT TYPE:", r.headers.get("Content-Type"))
    print("SERVER SIZE:", r.headers.get("Content-Length"))
    print()

    r.raise_for_status()

    total = 0

    with open(OUT, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)

                print(
                    f"\rDOWNLOADED: {total / 1024 / 1024:.2f} MB",
                    end="",
                    flush=True
                )

print()
print()
print("=" * 70)
print("DOWNLOAD COMPLETE")
print("=" * 70)
print(f"FILE: {OUT}")
print(f"SIZE: {os.path.getsize(OUT) / 1024 / 1024:.2f} MB")