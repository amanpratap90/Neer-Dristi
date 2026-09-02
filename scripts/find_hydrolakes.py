from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

OUT = Path("data/raw/reservoirs")
PAGE = "https://www.hydrosheds.org/products/hydrolakes"

print("READING OFFICIAL HYDROSHEDS HYDROLAKES PAGE...")

r = requests.get(PAGE, timeout=60)
r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")

found = []

for a in soup.find_all("a", href=True):
    href = urljoin(PAGE, a["href"])
    text = a.get_text(" ", strip=True).lower()

    if "download" in text or "hydrolakes" in href.lower():
        if href not in found:
            found.append(href)

for x in found:
    print(x)
