from typing import Any, Dict, List, Optional
from app.utils.geo import round_safe


BASIN_REGIONS: List[Dict[str, Any]] = [
    {
        "id": "CWC_BASIN_KOSI",
        "name": "Kosi Basin (North Bihar)",
        "bounds": {"minLat": 25.3, "maxLat": 27.5, "minLon": 85.5, "maxLon": 88.2},
        "slopeMean": 1.8,
        "reliefM": 28,
        "drainageDensity": 1.85,
        "soilGroup": "D",
        "soil": {"clay_fraction_pct": 36.5, "silt_fraction_pct": 42.0, "sand_fraction_pct": 21.5, "texture": "Silty Clay Loam", "cec_mean": 235, "phh2o_mean": 7.2},
        "landCover": {"cropland_pct": 68.4, "built_up_pct": 4.8, "tree_cover_pct": 12.2, "water_pct": 6.8, "wetland_pct": 4.2, "natural_vegetation_pct": 3.6},
        "baseCurveNumber": 84
    },
    {
        "id": "CWC_BASIN_BRAHMAPUTRA",
        "name": "Brahmaputra Valley (Assam)",
        "bounds": {"minLat": 25.0, "maxLat": 28.5, "minLon": 89.5, "maxLon": 96.0},
        "slopeMean": 2.2,
        "reliefM": 35,
        "drainageDensity": 2.10,
        "soilGroup": "D",
        "soil": {"clay_fraction_pct": 38.0, "silt_fraction_pct": 40.5, "sand_fraction_pct": 21.5, "texture": "Clay Loam", "cec_mean": 240, "phh2o_mean": 6.5},
        "landCover": {"cropland_pct": 54.2, "built_up_pct": 3.8, "tree_cover_pct": 24.5, "water_pct": 8.5, "wetland_pct": 5.8, "natural_vegetation_pct": 3.2},
        "baseCurveNumber": 86
    },
    {
        "id": "CWC_BASIN_GANGA_MIDDLE",
        "name": "Middle Ganga Basin (UP / South Bihar)",
        "bounds": {"minLat": 24.5, "maxLat": 27.5, "minLon": 80.0, "maxLon": 85.5},
        "slopeMean": 2.5,
        "reliefM": 42,
        "drainageDensity": 1.45,
        "soilGroup": "C",
        "soil": {"clay_fraction_pct": 29.5, "silt_fraction_pct": 38.2, "sand_fraction_pct": 32.3, "texture": "Loam", "cec_mean": 210, "phh2o_mean": 7.4},
        "landCover": {"cropland_pct": 72.5, "built_up_pct": 6.2, "tree_cover_pct": 10.4, "water_pct": 3.2, "wetland_pct": 1.8, "natural_vegetation_pct": 5.9},
        "baseCurveNumber": 80
    },
    {
        "id": "CWC_BASIN_MAHANADI",
        "name": "Mahanadi Basin (Odisha / Chhattisgarh)",
        "bounds": {"minLat": 19.5, "maxLat": 23.5, "minLon": 80.5, "maxLon": 87.0},
        "slopeMean": 4.8,
        "reliefM": 78,
        "drainageDensity": 1.62,
        "soilGroup": "C",
        "soil": {"clay_fraction_pct": 31.2, "silt_fraction_pct": 32.5, "sand_fraction_pct": 36.3, "texture": "Sandy Clay Loam", "cec_mean": 195, "phh2o_mean": 6.8},
        "landCover": {"cropland_pct": 52.0, "built_up_pct": 4.1, "tree_cover_pct": 28.5, "water_pct": 4.2, "wetland_pct": 2.1, "natural_vegetation_pct": 9.1},
        "baseCurveNumber": 78
    },
    {
        "id": "CWC_BASIN_GODAVARI",
        "name": "Godavari Basin (Maharashtra / Telangana / AP)",
        "bounds": {"minLat": 16.5, "maxLat": 21.0, "minLon": 73.5, "maxLon": 82.5},
        "slopeMean": 5.2,
        "reliefM": 95,
        "drainageDensity": 1.38,
        "soilGroup": "D",
        "soil": {"clay_fraction_pct": 46.0, "silt_fraction_pct": 28.0, "sand_fraction_pct": 26.0, "texture": "Heavy Clay", "cec_mean": 310, "phh2o_mean": 7.8},
        "landCover": {"cropland_pct": 64.0, "built_up_pct": 5.2, "tree_cover_pct": 16.8, "water_pct": 2.8, "wetland_pct": 1.1, "natural_vegetation_pct": 10.1},
        "baseCurveNumber": 85
    }
]

DEFAULT_BASIN: Dict[str, Any] = {
    "id": "CWC_BASIN_IN_REGIONAL",
    "name": "National Catchment Unit",
    "slopeMean": 4.2,
    "reliefM": 55,
    "drainageDensity": 1.5,
    "soilGroup": "C",
    "soil": {"clay_fraction_pct": 28.5, "silt_fraction_pct": 33.5, "sand_fraction_pct": 38.0, "texture": "Loam", "cec_mean": 200, "phh2o_mean": 7.0},
    "landCover": {"cropland_pct": 55.0, "built_up_pct": 4.8, "tree_cover_pct": 18.5, "water_pct": 2.8, "wetland_pct": 1.2, "natural_vegetation_pct": 17.7},
    "baseCurveNumber": 78
}


def get_catchment_profile(latitude: float, longitude: float, elevation: float = 50.0) -> Dict[str, Any]:
    """Identify the hydrographic basin profile for a given latitude/longitude."""
    matched = None
    for b in BASIN_REGIONS:
        bounds = b["bounds"]
        if bounds["minLat"] <= latitude <= bounds["maxLat"] and bounds["minLon"] <= longitude <= bounds["maxLon"]:
            matched = b
            break

    if not matched:
        matched = DEFAULT_BASIN

    adjusted_slope = (
        min(matched["slopeMean"], 1.6) if elevation < 25.0
        else max(matched["slopeMean"], 9.5) if elevation > 400.0
        else matched["slopeMean"]
    )

    cn = matched["baseCurveNumber"]
    potential_s = round(25400.0 / cn - 254.0, 1)

    return {
        "basin_id": matched["id"],
        "basin_name": matched["name"],
        "slope_deg": adjusted_slope,
        "relief_m": max(8.0, round(elevation * 0.45 + adjusted_slope * 5.0, 0)),
        "drainage_density_km_km2": matched["drainageDensity"],
        "hydrologic_soil_group": matched["soilGroup"],
        "soil": dict(matched["soil"]),
        "land_cover": dict(matched["landCover"]),
        "curve_number": cn,
        "potential_retention_s_mm": potential_s,
        "drainage_capacity": "RAPID" if adjusted_slope > 6.0 else "MODERATE" if adjusted_slope > 2.5 else "POOR_WATERLOGGING_PRONE"
    }
