from pathlib import Path
from urllib.request import urlopen

tile = "N24E082"

lat = tile[:3]
lon = tile[3:]

product = f"Copernicus_DSM_COG_10_{lat}_00_{lon}_00_DEM"

url = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    f"{product}/{product}.tif"
)

output_dir = Path("data/raw/dem/copernicus_glo30")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / f"{tile}.tif"

print("=" * 70)
print("COPERNICUS GLO-30 TEST")
print("=" * 70)

print("Tile:")
print(tile)

print("\nURL:")
print(url)

print("\nDownloading...")

try:
    with urlopen(url, timeout=120) as response:
        data = response.read()

    output_file.write_bytes(data)

    print("\nSUCCESS")
    print("File:", output_file)
    print(
        "Size:",
        round(output_file.stat().st_size / (1024 * 1024), 2),
        "MB"
    )

except Exception as e:
    print("\nDOWNLOAD FAILED")
    print(type(e).__name__)
    print(e)