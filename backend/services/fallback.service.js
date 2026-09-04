/**
 * Environmental & Hydrological Fallback Signal Evaluator
 *
 * Evaluates supplementary physical evidence when live CWC telemetry is unavailable:
 * - Current 24h & 72h precipitation (Open-Meteo)
 * - 72h NWP ensemble rainfall forecast
 * - Soil saturation & catchment runoff proxy (NRCS CN)
 * - GloFAS hydrologic discharge ratio (discharge / mean)
 * - River proximity & topographic elevation
 *
 * CRITICAL RULE:
 * This signal MUST NOT be labeled as CWC.
 * It is strictly labeled as "FALLBACK_ENVIRONMENTAL".
 */

/**
 * Evaluates environmental fallback risk.
 *
 * @param {object} params
 * @param {object} params.live - Live weather & environmental inputs
 * @param {object} params.catchment - Catchment profile data
 * @param {number|null} params.nearestStationDistanceKm - Distance to nearest river gauge in km
 * @returns {object} Standardized fallback environmental signal
 */
export function evaluateEnvironmentalFallback({ live, catchment = {}, nearestStationDistanceKm = null }) {
  if (!live) {
    console.log("[FALLBACK] Environmental data unavailable (null live input)");
    return {
      source: "FALLBACK_ENVIRONMENTAL",
      status: "UNAVAILABLE",
      risk: "LOW",
      rainfall_mm: null,
      forecast_rainfall_mm: null,
      river_proximity: "UNKNOWN",
      summary: "Environmental telemetry unavailable."
    };
  }

  const rain24h = live.rainfall?.h24 ?? null;
  const rain72h = live.rainfall?.h72 ?? null;
  const forecast72h = live.rainfall?.forecast72h ?? null;
  const soilMoisture = live.current?.soilMoisture ?? null;
  const curveNumber = catchment?.curve_number ?? null;
  const elevation = live.elevation ?? null;

  const dischargeNow = live.flood?.dischargeNow ?? null;
  const dischargeMean = live.flood?.dischargeMean ?? null;
  const dischargeRatio = (dischargeNow !== null && dischargeMean !== null && dischargeMean > 0)
    ? dischargeNow / dischargeMean
    : null;

  // Check data availability
  const hasWeather = rain24h !== null || forecast72h !== null;
  if (!hasWeather && dischargeNow === null) {
    console.log("[FALLBACK] Environmental data unavailable (no weather or discharge data)");
    return {
      source: "FALLBACK_ENVIRONMENTAL",
      status: "UNAVAILABLE",
      risk: "LOW",
      rainfall_mm: null,
      forecast_rainfall_mm: null,
      river_proximity: "UNKNOWN",
      summary: "Environmental telemetry unavailable."
    };
  }

  // Determine river proximity
  let riverProximity = "FAR";
  if (nearestStationDistanceKm !== null && Number.isFinite(nearestStationDistanceKm)) {
    if (nearestStationDistanceKm <= 6 || (elevation !== null && elevation < 25)) {
      riverProximity = "NEAR";
    } else if (nearestStationDistanceKm <= 25 || (elevation !== null && elevation < 70)) {
      riverProximity = "MODERATE";
    }
  } else if (elevation !== null && elevation < 30) {
    riverProximity = "NEAR";
  }

  // Rainfall intensity scoring
  const r24 = rain24h || 0;
  const r72 = rain72h || 0;
  const f72 = forecast72h || 0;

  const isHeavyRain = r24 >= 60 || r72 >= 110 || f72 >= 90;
  const isModerateRain = r24 >= 25 || r72 >= 50 || f72 >= 40;

  // Catchment saturation & hydrologic surge
  const isHighDischarge = dischargeRatio !== null && dischargeRatio >= 1.5;
  const isSaturatedSoil = (soilMoisture !== null && soilMoisture >= 0.40) || (curveNumber !== null && curveNumber >= 78);

  // Deterministic fallback risk assignment
  let risk = "LOW";
  let summary = "Normal baseline environmental and meteorological conditions.";

  if (isHeavyRain && (riverProximity === "NEAR" || isHighDischarge || isSaturatedSoil)) {
    risk = "HIGH";
    summary = "High environmental flood hazard: heavy precipitation loading combined with elevated hydrologic runoff.";
  } else if (isHeavyRain || (isModerateRain && (riverProximity === "NEAR" || isHighDischarge))) {
    risk = "HIGH";
    summary = "Elevated environmental risk: significant cumulative rainfall and river proximity.";
  } else if (isModerateRain || isHighDischarge || (isSaturatedSoil && riverProximity === "NEAR")) {
    risk = "MEDIUM";
    summary = "Moderate environmental indications: sustained rainfall or elevated river discharge ratio.";
  }

  console.log(`[FALLBACK] Environmental data evaluated: risk=${risk} rain24h=${r24}mm f72h=${f72}mm proximity=${riverProximity}`);

  return {
    source: "FALLBACK_ENVIRONMENTAL",
    status: "AVAILABLE",
    risk, // "LOW" | "MEDIUM" | "HIGH"
    rainfall_mm: rain24h !== null ? Number(rain24h.toFixed(1)) : 0,
    forecast_rainfall_mm: forecast72h !== null ? Number(forecast72h.toFixed(1)) : 0,
    river_proximity: riverProximity, // "NEAR" | "MODERATE" | "FAR"
    soil_moisture: soilMoisture !== null ? Number(soilMoisture.toFixed(2)) : null,
    discharge_ratio: dischargeRatio !== null ? Number(dischargeRatio.toFixed(2)) : null,
    summary
  };
}
