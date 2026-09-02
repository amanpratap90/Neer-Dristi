from pathlib import Path
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]

src = ROOT / "data" / "raw" / "basins" / "kosi_basin.geojson"
out = ROOT / "data" / "interim" / "aoi"

out.mkdir(parents=True, exist_ok=True)

gdf = gpd.read_file(src)

if gdf.crs is None:
    raise ValueError("AOI has no CRS")

gdf = gdf.to_crs("EPSG:4326")

gdf = gdf[gdf.geometry.notna()]
gdf = gdf[~gdf.geometry.is_empty]
gdf["geometry"] = gdf.geometry.buffer(0)

gdf = gdf.dissolve()

gdf.to_file(
    out / "kosi_aoi.geojson",
    driver="GeoJSON"
)

print("AOI prepared")
print("CRS:", gdf.crs)
print("Features:", len(gdf))
print("Bounds:", gdf.total_bounds)