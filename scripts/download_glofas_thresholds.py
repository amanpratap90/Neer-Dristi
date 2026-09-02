from pathlib import Path
import requests

OUT = Path("data/raw/flood_events/glofas_thresholds")
OUT.mkdir(parents=True, exist_ok=True)

BASE = "https://ewds.climate.copernicus.eu/api"

FILES = [
    "flood_threshold_glofas_v4_rl_1.5.nc",
    "flood_threshold_glofas_v4_rl_2.0.nc",
    "flood_threshold_glofas_v4_rl_5.0.nc",
    "flood_threshold_glofas_v4_rl_10.0.nc",
]

print("GLOFAS FLOOD THRESHOLDS")
print("Official Copernicus CEMS / ECMWF")
print()

for name in FILES:
    url = f"{BASE}/{name}"
    out = OUT / name

    if out.exists() and out.stat().st_size > 10000:
        print(f"EXISTS: {name}")
        continue

    print(f"DOWNLOADING: {name}")

    try:
        r = requests.get(url, stream=True, timeout=180)
        print("STATUS:", r.status_code)
        r.raise_for_status()

        with open(out, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)

        print(f"DONE: {out.stat().st_size / 1024 / 1024:.1f} MB")

    except Exception as e:
        if out.exists():
            out.unlink()
        print("FAILED:", e)

print()
print("FLOOD THRESHOLD DOWNLOAD FINISHED")
