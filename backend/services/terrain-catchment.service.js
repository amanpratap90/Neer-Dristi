/**
 * Terrain & Catchment Profiling Service for ChetakAI
 * Provides physically grounded basin topography, soil texture,
 * SCS curve numbers, and drainage parameters across Indian catchments.
 */

function clamp(val, min, max) {
  return Math.min(max, Math.max(min, val));
}

function round(val, digits = 2) {
  const n = Number(val);
  if (!Number.isFinite(n)) return 0;
  return Number(n.toFixed(digits));
}

// Hydrographic Basin Catalog for India
const BASIN_REGIONS = [
  {
    id: "CWC_BASIN_KOSI",
    name: "Kosi Basin (North Bihar)",
    bounds: { minLat: 25.3, maxLat: 27.5, minLon: 85.5, maxLon: 88.2 },
    slopeMean: 1.8,
    reliefM: 28,
    drainageDensity: 1.85,
    soilGroup: "D", // High runoff potential
    soil: { clay_fraction_pct: 36.5, silt_fraction_pct: 42.0, sand_fraction_pct: 21.5, texture: "Silty Clay Loam", cec_mean: 235, phh2o_mean: 7.2 },
    landCover: { cropland_pct: 68.4, built_up_pct: 4.8, tree_cover_pct: 12.2, water_pct: 6.8, wetland_pct: 4.2, natural_vegetation_pct: 3.6 },
    baseCurveNumber: 84
  },
  {
    id: "CWC_BASIN_BRAHMAPUTRA",
    name: "Brahmaputra Valley (Assam)",
    bounds: { minLat: 25.0, maxLat: 28.5, minLon: 89.5, maxLon: 96.0 },
    slopeMean: 2.2,
    reliefM: 35,
    drainageDensity: 2.10,
    soilGroup: "D",
    soil: { clay_fraction_pct: 38.0, silt_fraction_pct: 40.5, sand_fraction_pct: 21.5, texture: "Clay Loam", cec_mean: 240, phh2o_mean: 6.5 },
    landCover: { cropland_pct: 54.2, built_up_pct: 3.8, tree_cover_pct: 24.5, water_pct: 8.5, wetland_pct: 5.8, natural_vegetation_pct: 3.2 },
    baseCurveNumber: 86
  },
  {
    id: "CWC_BASIN_GANGA_MIDDLE",
    name: "Middle Ganga Basin (UP / South Bihar)",
    bounds: { minLat: 24.5, maxLat: 27.5, minLon: 80.0, maxLon: 85.5 },
    slopeMean: 2.5,
    reliefM: 42,
    drainageDensity: 1.45,
    soilGroup: "C",
    soil: { clay_fraction_pct: 29.5, silt_fraction_pct: 38.2, sand_fraction_pct: 32.3, texture: "Loam", cec_mean: 210, phh2o_mean: 7.4 },
    landCover: { cropland_pct: 72.5, built_up_pct: 6.2, tree_cover_pct: 10.4, water_pct: 3.2, wetland_pct: 1.8, natural_vegetation_pct: 5.9 },
    baseCurveNumber: 80
  },
  {
    id: "CWC_BASIN_MAHANADI",
    name: "Mahanadi Basin (Odisha / Chhattisgarh)",
    bounds: { minLat: 19.5, maxLat: 23.5, minLon: 80.5, maxLon: 87.0 },
    slopeMean: 4.8,
    reliefM: 78,
    drainageDensity: 1.62,
    soilGroup: "C",
    soil: { clay_fraction_pct: 31.2, silt_fraction_pct: 32.5, sand_fraction_pct: 36.3, texture: "Sandy Clay Loam", cec_mean: 195, phh2o_mean: 6.8 },
    landCover: { cropland_pct: 52.0, built_up_pct: 4.1, tree_cover_pct: 28.5, water_pct: 4.2, wetland_pct: 2.1, natural_vegetation_pct: 9.1 },
    baseCurveNumber: 78
  },
  {
    id: "CWC_BASIN_GODAVARI",
    name: "Godavari Basin (Maharashtra / Telangana / AP)",
    bounds: { minLat: 16.5, maxLat: 21.0, minLon: 73.5, maxLon: 82.5 },
    slopeMean: 5.2,
    reliefM: 95,
    drainageDensity: 1.38,
    soilGroup: "D", // Black cotton clay soils
    soil: { clay_fraction_pct: 46.0, silt_fraction_pct: 28.0, sand_fraction_pct: 26.0, texture: "Heavy Clay", cec_mean: 310, phh2o_mean: 7.8 },
    landCover: { cropland_pct: 64.0, built_up_pct: 5.2, tree_cover_pct: 16.8, water_pct: 2.8, wetland_pct: 1.1, natural_vegetation_pct: 10.1 },
    baseCurveNumber: 85
  },
  {
    id: "CWC_BASIN_KRISHNA",
    name: "Krishna Basin (Karnataka / Telangana / AP)",
    bounds: { minLat: 13.0, maxLat: 17.5, minLon: 73.5, maxLon: 81.5 },
    slopeMean: 4.9,
    reliefM: 82,
    drainageDensity: 1.25,
    soilGroup: "C",
    soil: { clay_fraction_pct: 34.0, silt_fraction_pct: 30.0, sand_fraction_pct: 36.0, texture: "Clay Loam", cec_mean: 220, phh2o_mean: 7.6 },
    landCover: { cropland_pct: 66.5, built_up_pct: 5.8, tree_cover_pct: 12.0, water_pct: 2.2, wetland_pct: 0.9, natural_vegetation_pct: 12.6 },
    baseCurveNumber: 79
  },
  {
    id: "CWC_BASIN_WESTERN_GHATS",
    name: "Western Ghats High Relief Catchment",
    bounds: { minLat: 8.5, maxLat: 19.0, minLon: 72.8, maxLon: 76.5 },
    slopeMean: 14.5,
    reliefM: 420,
    drainageDensity: 2.45,
    soilGroup: "B", // Well-drained laterite soils
    soil: { clay_fraction_pct: 24.0, silt_fraction_pct: 22.0, sand_fraction_pct: 54.0, texture: "Gravelly Loam", cec_mean: 140, phh2o_mean: 5.8 },
    landCover: { cropland_pct: 28.0, built_up_pct: 4.5, tree_cover_pct: 52.0, water_pct: 3.5, wetland_pct: 1.2, natural_vegetation_pct: 10.8 },
    baseCurveNumber: 72
  },
  {
    id: "CWC_BASIN_COASTAL_EAST",
    name: "East Coast Deltaic Plain",
    bounds: { minLat: 11.0, maxLat: 22.0, minLon: 79.5, maxLon: 87.5 },
    slopeMean: 1.2,
    reliefM: 14,
    drainageDensity: 1.95,
    soilGroup: "D",
    soil: { clay_fraction_pct: 39.0, silt_fraction_pct: 34.0, sand_fraction_pct: 27.0, texture: "Coastal Alluvium", cec_mean: 260, phh2o_mean: 7.5 },
    landCover: { cropland_pct: 60.0, built_up_pct: 9.5, tree_cover_pct: 11.5, water_pct: 7.2, wetland_pct: 6.5, natural_vegetation_pct: 5.3 },
    baseCurveNumber: 88
  }
];

// Default catchment parameters for other regions across India
const DEFAULT_BASIN = {
  id: "CWC_BASIN_IN_REGIONAL",
  name: "National Catchment Unit",
  slopeMean: 4.2,
  reliefM: 55,
  drainageDensity: 1.5,
  soilGroup: "C",
  soil: { clay_fraction_pct: 28.5, silt_fraction_pct: 33.5, sand_fraction_pct: 38.0, texture: "Loam", cec_mean: 200, phh2o_mean: 7.0 },
  landCover: { cropland_pct: 55.0, built_up_pct: 4.8, tree_cover_pct: 18.5, water_pct: 2.8, wetland_pct: 1.2, natural_vegetation_pct: 17.7 },
  baseCurveNumber: 78
};

/**
 * Identify the hydrographic basin profile for a given lat/lon
 */
export function getCatchmentProfile(latitude, longitude, elevation = 50) {
  const lat = Number(latitude);
  const lon = Number(longitude);

  let matched = BASIN_REGIONS.find((b) =>
    lat >= b.bounds.minLat && lat <= b.bounds.maxLat &&
    lon >= b.bounds.minLon && lon <= b.bounds.maxLon
  );

  if (!matched) {
    matched = DEFAULT_BASIN;
  }

  // Adjust slope dynamically if Open-Meteo elevation is available
  // Flat alluvial plains (<30m) have very low slope; uplands have higher slope
  const adjustedSlope = elevation < 25
    ? Math.min(matched.slopeMean, 1.6)
    : elevation > 400
    ? Math.max(matched.slopeMean, 9.5)
    : matched.slopeMean;

  // Compute USDA-NRCS Curve Number & Potential Maximum Retention S (mm)
  const cn = matched.baseCurveNumber;
  const potentialRetentionS = round(25400 / cn - 254, 1);

  return {
    basin_id: matched.id,
    basin_name: matched.name,
    slope_deg: adjustedSlope,
    relief_m: Math.max(8, round(elevation * 0.45 + adjustedSlope * 5, 0)),
    drainage_density_km_km2: matched.drainageDensity,
    hydrologic_soil_group: matched.soilGroup,
    soil: { ...matched.soil },
    land_cover: { ...matched.landCover },
    curve_number: cn,
    potential_retention_s_mm: potentialRetentionS,
    drainage_capacity: adjustedSlope > 6 ? "RAPID" : adjustedSlope > 2.5 ? "MODERATE" : "POOR_WATERLOGGING_PRONE"
  };
}
