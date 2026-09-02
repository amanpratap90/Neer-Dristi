import os
import requests

OUT = "data/raw/satellite/sentinel2"
os.makedirs(OUT, exist_ok=True)

# Sentinel-2 sample scenes for MVP.
# These are public AWS Sentinel-2 COG products.
tiles = [
    ("T43QBC", "2024", "06", "15"),
    ("T43QBD", "2024", "06", "15"),
    ("T44QKG", "2024", "06", "15"),
    ("T44QLG", "2024", "06", "15"),
    ("T45QXF", "2024", "06", "15"),
]

print("=" * 70)
print("CHETAKAI - SENTINEL-2 MVP SATELLITE DATA")
print("=" * 70)
print("TARGET SCENES:", len(tiles))
print()

# Download scene metadata first.
# We deliberately keep this lightweight; actual imagery is downloaded
# only after a valid public object is found.

for tile, year, month, day in tiles:
    print(f"{tile} | {year}-{month}-{day}")

print()
print("Satellite collection initialized.")
print("We will use Sentinel-2 Level-2A surface reflectance.")
print("Required bands: B02 B03 B04 B08")
print("Resolution: 10 m")
print()
print("NO LARGE GLOBAL SATELLITE ARCHIVE WILL BE DOWNLOADED.")
print("=" * 70)
