from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

out = Path("data/raw/hydrography/HydroRIVERS")
out.mkdir(parents=True, exist_ok=True)

page = "https://www.hydrosheds.org/products/hydrorivers"

print("Reading official HydroSHEDS download page...")
html = requests.get(page, timeout=60).text
soup = BeautifulSoup(html, "html.parser")

url = None

for a in soup.find_all("a", href=True):
    href = urljoin(page, a["href"])
    text = a.get_text(" ", strip=True).lower()

    if "asia" in text and ("shapefile" in text or "download" in text):
        url = href
        break

if url is None:
    for a in soup.find_all("a", href=True):
        href = urljoin(page, a["href"])
        if "HydroRIVERS" in href and "_as" in href:
            url = href
            break

if url is None:
    raise RuntimeError("Could not locate current Asia HydroRIVERS endpoint")

print("FOUND:")
print(url)
print()
print("DOWNLOADING...")

r = requests.get(url, timeout=600)
r.raise_for_status()

file = out / "HydroRIVERS_Asia.zip"
file.write_bytes(r.content)

print(f"DONE: {file.stat().st_size / 1024 / 1024:.1f} MB")
print(file)
