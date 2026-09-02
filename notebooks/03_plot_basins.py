import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path

path = Path("data/raw/basin_boundaries/cwc_basins.geojson")

basins = gpd.read_file(path)

fig, ax = plt.subplots(figsize=(12, 12))

basins.boundary.plot(ax=ax)

if "ba_name" in basins.columns:
    for _, row in basins.iterrows():
        point = row.geometry.representative_point()
        ax.annotate(
            str(row["ba_name"]),
            xy=(point.x, point.y),
            fontsize=7
        )

ax.set_title("ChetakAI - India Basin Boundaries")
ax.set_axis_off()

plt.tight_layout()

output = Path("data/processed/basin_boundaries_preview.png")
output.parent.mkdir(parents=True, exist_ok=True)

plt.savefig(output, dpi=200)
plt.show()

print("Saved:", output)