import pandas as pd
import geopandas as gpd
from pathlib import Path

BASE = Path("data")

flood_file = BASE / "raw/flood_events/india_flood_inventory/India_Flood_Inventory_v3.csv"
district_file = BASE / "raw/administrative/district_boundaries.shp"
output_dir = BASE / "processed/flood_events"

output_dir.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("CHETAKAI FLOOD EVENT PROCESSING")
print("=" * 70)

df = pd.read_csv(flood_file)

df["start_date"] = pd.to_datetime(df["Start Date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["End Date"], errors="coerce")

df["year"] = df["start_date"].dt.year
df["month"] = df["start_date"].dt.month

df = df[df["start_date"].notna()].copy()

districts = gpd.read_file(district_file)

print("FLOOD EVENTS:", len(df))
print("DISTRICTS:", len(districts))
print("DISTRICT CRS:", districts.crs)

if districts.crs is None:
    districts = districts.set_crs("EPSG:4326")

districts = districts.to_crs("EPSG:4326")

print("DISTRICT COLUMNS:")
print(list(districts.columns))

# Find likely district-name column
possible = [
    "DISTRICT",
    "District",
    "district",
    "DIST_NAME",
    "District_Name",
    "NAME",
    "name"
]

district_col = None

for c in possible:
    if c in districts.columns:
        district_col = c
        break

if district_col is None:
    print("WARNING: No obvious district-name column found.")
    print(districts.columns.tolist())
    raise SystemExit

print("USING DISTRICT COLUMN:", district_col)

districts["district_clean"] = (
    districts[district_col]
    .astype(str)
    .str.upper()
    .str.strip()
)

# Explode flood-event district lists
rows = []

for _, r in df.iterrows():

    district_text = r.get("Districts")

    if pd.isna(district_text):
        continue

    for district in str(district_text).split(","):

        district = district.strip()

        if not district:
            continue

        x = r.copy()
        x["district_event"] = district
        x["district_clean"] = district.upper().strip()

        rows.append(x)

events = pd.DataFrame(rows)

print("DISTRICT-EVENT ROWS:", len(events))

# Match district names
events_geo = events.merge(
    districts,
    on="district_clean",
    how="left",
    suffixes=("_event", "_district")
)

matched = events_geo["geometry"].notna().sum()

print("MATCHED DISTRICT EVENTS:", matched)
print("UNMATCHED DISTRICT EVENTS:", len(events_geo) - matched)

events_geo = gpd.GeoDataFrame(
    events_geo,
    geometry="geometry",
    crs="EPSG:4326"
)

# Use representative point instead of polygon centroid
events_geo["event_point"] = events_geo.geometry.representative_point()

events_geo["longitude"] = events_geo.event_point.x
events_geo["latitude"] = events_geo.event_point.y

# Select clean model-ready fields
keep = [
    "UEI",
    "start_date",
    "end_date",
    "year",
    "month",
    "Duration(Days)",
    "Main Cause",
    "State",
    "district_event",
    "Severity",
    "Area Affected",
    "Human fatality",
    "Human injured",
    "Human Displaced",
    "Animal Fatality",
    "longitude",
    "latitude",
    "geometry"
]

keep = [c for c in keep if c in events_geo.columns]

final = events_geo[keep].copy()

final = final[final.geometry.notna()].copy()

output_geojson = output_dir / "flood_events_district.geojson"
output_csv = output_dir / "flood_events_model_ready.csv"

final.to_file(output_geojson, driver="GeoJSON")

csv_final = final.drop(columns="geometry")
csv_final.to_csv(output_csv, index=False)

print()
print("=" * 70)
print("PROCESSING COMPLETE")
print("=" * 70)
print("FINAL EVENTS:", len(final))
print("YEARS:", final.year.min(), "->", final.year.max())
print("OUTPUT:", output_geojson)
print("OUTPUT:", output_csv)
print("=" * 70)