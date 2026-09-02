from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parents[1]

BASIN_FILE = (
    BASE_DIR
    / "data"
    / "raw"
    / "basin_boundaries"
    / "cwc_basins.geojson"
)

OSM_DIR = BASE_DIR / "data" / "raw" / "infrastructure"

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "processed"
    / "infrastructure"
)

OUTPUT_FILE = OUTPUT_DIR / "infrastructure_basin_features.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_BASINS = [
    "Brahamaputra",
    "Mahanadi",
    "Godavari",
    "Subernarekha",
]


def find_osm_files():
    files = sorted(OSM_DIR.glob("*.osm.pbf"))

    if not files:
        raise SystemExit(
            f"No OSM PBF files found in {OSM_DIR}"
        )

    return files


def get_layers(pbf):
    try:
        return [
            row[0]
            for row in pyogrio.list_layers(pbf)
        ]
    except Exception:
        return []


def safe_read(pbf, layer, bbox):
    try:
        return pyogrio.read_dataframe(
            pbf,
            layer=layer,
            bbox=bbox,
            use_arrow=True
        )
    except Exception:
        try:
            return pyogrio.read_dataframe(
                pbf,
                layer=layer,
                bbox=bbox
            )
        except Exception:
            return gpd.GeoDataFrame()


def valid_geometries(gdf):
    if gdf is None or len(gdf) == 0:
        return gpd.GeoDataFrame()

    if "geometry" not in gdf.columns:
        return gpd.GeoDataFrame()

    gdf = gdf[gdf.geometry.notna()].copy()

    if len(gdf) == 0:
        return gdf

    try:
        gdf = gdf[
            ~gdf.geometry.is_empty
        ].copy()
    except Exception:
        pass

    return gdf


def calculate_features(gdf):

    result = {
        "road_feature_count": 0,
        "road_length_km": 0.0,
        "railway_feature_count": 0,
        "railway_length_km": 0.0,
        "bridge_count": 0,
        "building_count": 0,
    }

    if gdf is None or len(gdf) == 0:
        return result

    gdf = valid_geometries(gdf)

    if len(gdf) == 0:
        return result

    # ---------------------------------------------------------
    # ROADS
    # ---------------------------------------------------------

    if "highway" in gdf.columns:

        road_mask = (
            gdf["highway"].notna()
            & (
                gdf["highway"]
                .astype(str)
                .str.strip()
                != ""
            )
        )

        roads = gdf.loc[road_mask]

        if len(roads) > 0:

            result["road_feature_count"] = len(roads)

            try:
                result["road_length_km"] = (
                    roads.geometry.length.sum()
                    / 1000.0
                )
            except Exception:
                pass

    # ---------------------------------------------------------
    # RAILWAYS
    # ---------------------------------------------------------

    if "railway" in gdf.columns:

        railway_mask = (
            gdf["railway"].notna()
            & (
                gdf["railway"]
                .astype(str)
                .str.strip()
                != ""
            )
        )

        railways = gdf.loc[railway_mask]

        if len(railways) > 0:

            result["railway_feature_count"] = len(
                railways
            )

            try:
                result["railway_length_km"] = (
                    railways.geometry.length.sum()
                    / 1000.0
                )
            except Exception:
                pass

    # ---------------------------------------------------------
    # BRIDGES
    # ---------------------------------------------------------

    if "bridge" in gdf.columns:

        bridge_mask = (
            gdf["bridge"].notna()
            & (
                gdf["bridge"]
                .astype(str)
                .str.strip()
                != ""
            )
            & (
                gdf["bridge"]
                .astype(str)
                .str.lower()
                != "no"
            )
        )

        result["bridge_count"] = int(
            bridge_mask.sum()
        )

    return result


def calculate_building_count(gdf):

    if gdf is None or len(gdf) == 0:
        return 0

    if "building" not in gdf.columns:
        return 0

    mask = (
        gdf["building"].notna()
        & (
            gdf["building"]
            .astype(str)
            .str.strip()
            != ""
        )
        & (
            gdf["building"]
            .astype(str)
            .str.lower()
            != "no"
        )
    )

    return int(mask.sum())


def process_basin(
    basin_name,
    basin_geom,
    osm_files
):

    print()
    print("=" * 70)
    print(f"PROCESSING: {basin_name}")
    print("=" * 70)

    basin = gpd.GeoDataFrame(
        {"name": [basin_name]},
        geometry=[basin_geom],
        crs="EPSG:4326"
    )

    basin_metric = basin.to_crs("EPSG:6933")

    basin_metric_geom = (
        basin_metric.geometry.iloc[0]
    )

    basin_area_km2 = (
        basin_metric_geom.area
        / 1_000_000.0
    )

    minx, miny, maxx, maxy = basin_geom.bounds

    bbox = (
        minx,
        miny,
        maxx,
        maxy
    )

    totals = {
        "basin_name": basin_name,
        "basin_area_km2": basin_area_km2,

        "road_feature_count": 0,
        "road_length_km": 0.0,

        "railway_feature_count": 0,
        "railway_length_km": 0.0,

        "bridge_count": 0,

        "building_count": 0,

        "osm_files_used": 0,
    }

    for index, pbf in enumerate(
        osm_files,
        start=1
    ):

        print(
            f"[{index}/{len(osm_files)}] "
            f"{pbf.name}"
        )

        layers = get_layers(pbf)

        if not layers:
            print("  No readable layers")
            continue

        used = False

        # =====================================================
        # LINES
        # =====================================================

        if "lines" in layers:

            lines = safe_read(
                pbf,
                "lines",
                bbox
            )

            if len(lines) > 0:

                try:

                    lines = valid_geometries(lines)

                    if len(lines) > 0:

                        lines = lines.to_crs(
                            "EPSG:6933"
                        )

                        features = calculate_features(
                            lines
                        )

                        for key, value in features.items():
                            totals[key] += value

                        used = True

                        print(
                            f"  Lines loaded: "
                            f"{len(lines):,}"
                        )

                except Exception as e:

                    print(
                        f"  Line error: {e}"
                    )

                del lines

        # =====================================================
        # BUILDINGS
        # =====================================================

        if "multipolygons" in layers:

            polygons = safe_read(
                pbf,
                "multipolygons",
                bbox
            )

            if len(polygons) > 0:

                try:

                    polygons = valid_geometries(
                        polygons
                    )

                    if len(polygons) > 0:

                        count = calculate_building_count(
                            polygons
                        )

                        totals[
                            "building_count"
                        ] += count

                        used = True

                        print(
                            f"  Building features: "
                            f"{count:,}"
                        )

                except Exception as e:

                    print(
                        f"  Building error: {e}"
                    )

                del polygons

        if used:

            totals[
                "osm_files_used"
            ] += 1

        print(
            f"  TOTAL SO FAR | "
            f"roads={totals['road_feature_count']:,} "
            f"| railways={totals['railway_feature_count']:,} "
            f"| bridges={totals['bridge_count']:,} "
            f"| buildings={totals['building_count']:,}"
        )

    # =========================================================
    # DERIVED FEATURES
    # =========================================================

    area = max(
        totals["basin_area_km2"],
        0.000001
    )

    totals[
        "road_density_km_per_km2"
    ] = (
        totals["road_length_km"]
        / area
    )

    totals[
        "railway_density_km_per_km2"
    ] = (
        totals["railway_length_km"]
        / area
    )

    totals[
        "building_density_per_km2"
    ] = (
        totals["building_count"]
        / area
    )

    totals[
        "infrastructure_data_available"
    ] = int(
        (
            totals["road_feature_count"]
            + totals["railway_feature_count"]
            + totals["bridge_count"]
            + totals["building_count"]
        ) > 0
    )

    print()
    print("RESULT")
    print(
        f"Roads       : "
        f"{totals['road_feature_count']:,}"
    )

    print(
        f"Road length : "
        f"{totals['road_length_km']:.2f} km"
    )

    print(
        f"Railways    : "
        f"{totals['railway_feature_count']:,}"
    )

    print(
        f"Rail length : "
        f"{totals['railway_length_km']:.2f} km"
    )

    print(
        f"Bridges     : "
        f"{totals['bridge_count']:,}"
    )

    print(
        f"Buildings   : "
        f"{totals['building_count']:,}"
    )

    print(
        f"Data status : "
        f"{'AVAILABLE' if totals['infrastructure_data_available'] else 'NO DATA'}"
    )

    return totals


def main():

    print("=" * 70)
    print(
        "CHETAKAI V1 FAST INFRASTRUCTURE "
        "FEATURE ENGINEERING"
    )
    print("=" * 70)

    if not BASIN_FILE.exists():

        raise SystemExit(
            f"Basin file not found:\n"
            f"{BASIN_FILE}"
        )

    osm_files = find_osm_files()

    print()
    print(
        f"OSM files found: "
        f"{len(osm_files)}"
    )

    for pbf in osm_files:

        size_mb = (
            pbf.stat().st_size
            / (1024 * 1024)
        )

        print(
            f"  {pbf.name} | "
            f"{size_mb:.1f} MB"
        )

    print()
    print("Loading basin boundaries...")

    basins = (
        gpd.read_file(BASIN_FILE)
        .to_crs("EPSG:4326")
    )

    print(
        f"Total CWC basins: "
        f"{len(basins)}"
    )

    if "ba_name" not in basins.columns:

        raise SystemExit(
            "ERROR: ba_name column missing."
        )

    available_names = (
        basins["ba_name"]
        .dropna()
        .astype(str)
        .tolist()
    )

    print()
    print(
        "TARGET BASIN MATCHING"
    )
    print("-" * 70)

    selected = []

    for target in TARGET_BASINS:

        matches = [
            name
            for name in available_names
            if name.lower()
            == target.lower()
        ]

        if matches:

            print(
                f"FOUND : {target}"
            )

            selected.append(
                matches[0]
            )

        else:

            print(
                f"NOT FOUND : {target}"
            )

    if not selected:

        raise SystemExit(
            "No target basins matched."
        )

    results = []

    for basin_name in selected:

        rows = basins[
            basins["ba_name"]
            .astype(str)
            .str.lower()
            == basin_name.lower()
        ]

        if len(rows) == 0:
            continue

        basin_geom = (
            rows.geometry.iloc[0]
        )

        try:

            result = process_basin(
                basin_name,
                basin_geom,
                osm_files
            )

            results.append(result)

        except KeyboardInterrupt:

            print()
            print(
                "PROCESS INTERRUPTED."
            )

            raise SystemExit(0)

        except Exception as e:

            print()
            print(
                f"ERROR: {basin_name}"
            )
            print(e)

    if not results:

        raise SystemExit(
            "No infrastructure features generated."
        )

    df = pd.DataFrame(results)

    numeric_columns = [
        "basin_area_km2",
        "road_feature_count",
        "road_length_km",
        "railway_feature_count",
        "railway_length_km",
        "bridge_count",
        "building_count",
        "osm_files_used",
        "road_density_km_per_km2",
        "railway_density_km_per_km2",
        "building_density_per_km2",
        "infrastructure_data_available",
    ]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            ).fillna(0)

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print()
    print("=" * 70)
    print(
        "INFRASTRUCTURE DATASET COMPLETE"
    )
    print("=" * 70)

    print(
        f"Output : {OUTPUT_FILE}"
    )

    print(
        f"Rows   : {len(df)}"
    )

    print(
        f"Columns: {len(df.columns)}"
    )

    print()

    print(
        df[
            [
                "basin_name",
                "road_feature_count",
                "road_length_km",
                "railway_feature_count",
                "bridge_count",
                "building_count",
                "road_density_km_per_km2",
                "building_density_per_km2",
                "infrastructure_data_available",
            ]
        ].to_string(index=False)
    )

    print()
    print("DONE")


if __name__ == "__main__":
    main()