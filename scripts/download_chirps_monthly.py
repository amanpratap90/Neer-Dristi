from pathlib import Path
import requests

ROOT = Path("data/raw/rainfall/chirps_monthly")
ROOT.mkdir(parents=True, exist_ok=True)

BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs"

for year in range(2015, 2026):
    outdir = ROOT / str(year)
    outdir.mkdir(parents=True, exist_ok=True)

    for month in range(1, 13):
        name = f"chirps-v2.0.{year}.{month:02d}.tif.gz"
        out = outdir / name
        url = f"{BASE}/{name}"

        if out.exists() and out.stat().st_size > 100000:
            print(f"[{year}-{month:02d}] EXISTS")
            continue

        print(f"[{year}-{month:02d}] DOWNLOADING")

        try:
            r = requests.get(url, timeout=180)
            r.raise_for_status()
            out.write_bytes(r.content)
            print(f"          DONE {out.stat().st_size / 1024 / 1024:.1f} MB")
        except Exception as e:
            if out.exists():
                out.unlink()
            print(f"          FAILED: {e}")

print("======================================")
print("CHIRPS MONTHLY DOWNLOAD COMPLETE")
print("======================================")
