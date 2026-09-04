import { getLiveIntelligenceInputs } from "./weather.service.js";
import { reverseGeocode } from "./geocoding.service.js";
import { generateDisasterBriefing } from "./llm.service.js";
import { predictFloodRisk } from "./ml-model.service.js";
import { getCatchmentProfile } from "./terrain-catchment.service.js";
import { validateEnvironmentalInputs } from "./data-quality.service.js";
import { getCWCObservation, findNearestCWCStation } from "./cwc.service.js";
import { evaluateEnvironmentalFallback } from "./fallback.service.js";

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function round(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Number(n.toFixed(digits));
}

function approximateExposure(probabilityPct, catchment) {
  const source = "Hardcoded regional approximation";
  const sourceType = "ESTIMATED";
  const population = 145000;
  const floodProbability = clamp((Number(probabilityPct) || 0) / 100, 0, 1);
  const builtUpPct = Number(catchment?.land_cover?.built_up_pct) || 5;
  const exposureFactor = clamp(0.18 + floodProbability * 0.65 + builtUpPct / 500, 0.18, 0.9);
  const exposedPopulation = Math.round(population * exposureFactor);
  const vulnerablePopulation = Math.round(exposedPopulation * 0.18);
  const buildings = Math.max(1, Math.round(exposedPopulation / 5));
  const hospitals = Math.max(1, Math.round(exposedPopulation / 120000));
  const schools = Math.max(1, Math.round(exposedPopulation / 18000));
  const roads = round(1.5 + Math.sqrt(exposedPopulation) * 0.08, 1);
  const bridges = Math.max(1, Math.round(exposedPopulation / 60000));

  const estimated = (value, unit) => ({ value, unit, source, sourceType, status: "ESTIMATED" });

  return {
    population: estimated(population, "people"),
    vulnerable_population: estimated(vulnerablePopulation, "people"),
    buildings_exposed: estimated(buildings, "buildings"),
    hospitals_exposed: estimated(hospitals, "facilities"),
    schools_exposed: estimated(schools, "facilities"),
    roads_exposed_km: estimated(roads, "km"),
    bridges_exposed: estimated(bridges, "bridges"),
    is_ai_estimate: true,
    estimation_source: source,
    estimation_note: "Approximation for demonstration; not a live infrastructure or census measurement."
  };
}

/**
 * Maps ML model flood probability (0.0 to 1.0 or 0 to 100) to consistent risk categories:
 * 0.00 - 0.30: LOW
 * 0.30 - 0.60: MEDIUM
 * 0.60 - 0.80: HIGH
 * 0.80 - 1.00: VERY HIGH
 */
export function mapAiRisk(probabilityOrPct) {
  if (probabilityOrPct === null || probabilityOrPct === undefined || !Number.isFinite(Number(probabilityOrPct))) {
    return "UNKNOWN";
  }
  const pct = Number(probabilityOrPct) > 1 ? Number(probabilityOrPct) : Number(probabilityOrPct) * 100;
  if (pct >= 80) return "VERY HIGH";
  if (pct >= 60) return "HIGH";
  if (pct >= 30) return "MEDIUM";
  return "LOW";
}

export function classifyRisk(score) {
  if (score >= 78) return "VERY HIGH";
  if (score >= 58) return "HIGH";
  if (score >= 32) return "MEDIUM";
  return "LOW";
}

/**
 * CENTRAL RISK AGGREGATION FUNCTION
 * Synthesizes three independent signals:
 * 1. AI_MODEL
 * 2. CWC_GROUND_TRUTH
 * 3. FALLBACK_ENVIRONMENTAL
 *
 * Deterministic Status Model:
 * NORMAL | WATCH | HIGH ALERT | CRITICAL
 *
 * Confidence Model:
 * HIGH CONFIDENCE | MEDIUM CONFIDENCE | LIMITED CONFIDENCE
 */
export function aggregateMultiSignalRisk({ aiSignal, cwcSignal, fallbackSignal }) {
  let aiRisk = aiSignal?.risk || "LOW";
  if (aiRisk === "MODERATE") aiRisk = "MEDIUM";
  const cwcStatus = cwcSignal?.status || "UNAVAILABLE";
  const cwcCondition = cwcSignal?.condition || "UNKNOWN";
  const fallbackStatus = fallbackSignal?.status || "UNAVAILABLE";
  const fallbackRisk = fallbackSignal?.risk || "LOW";

  const isCwcActive = cwcStatus === "AVAILABLE";
  const isCwcStale = cwcStatus === "STALE";
  const isFallbackActive = fallbackStatus === "AVAILABLE";

  let status = "NORMAL";
  let confidence = "LIMITED CONFIDENCE";
  let basis = "AI MODEL ONLY";
  let explanation = "";

  // PRIORITY RULE A: CWC is AVAILABLE
  if (isCwcActive) {
    basis = "AI MODEL + CWC GROUND TRUTH";

    if (cwcCondition === "EXTREME") {
      status = "CRITICAL";
      confidence = "HIGH CONFIDENCE";
      explanation = "CRITICAL: Observed CWC river water level has reached or exceeded the Highest Flood Level (HFL). Immediate emergency coordination required.";
    } else if (cwcCondition === "ABOVE_DANGER") {
      if (aiRisk === "HIGH" || aiRisk === "VERY HIGH") {
        status = "CRITICAL";
        confidence = "HIGH CONFIDENCE";
        explanation = "CRITICAL: AI flood model and observed CWC river conditions both confirm severe flood inundation hazard above danger level.";
      } else {
        status = "HIGH ALERT";
        confidence = "MEDIUM CONFIDENCE";
        explanation = "HIGH ALERT: Observed CWC river conditions are ABOVE DANGER level. Physical ground-truth river stage is elevated despite lower AI model probability estimation.";
      }
    } else if (cwcCondition === "ABOVE_WARNING") {
      if (aiRisk === "HIGH" || aiRisk === "VERY HIGH") {
        status = "HIGH ALERT";
        confidence = "HIGH CONFIDENCE";
        explanation = "HIGH ALERT: High AI model inundation probability combined with observed river water level above CWC warning threshold.";
      } else {
        status = "WATCH";
        confidence = "HIGH CONFIDENCE";
        explanation = "WATCH: Observed CWC river water level has exceeded the official warning threshold. Enhanced river catchment surveillance active.";
      }
    } else {
      // CWC is BELOW_WARNING
      if (aiRisk === "HIGH" || aiRisk === "VERY HIGH") {
        status = "HIGH ALERT";
        confidence = "MEDIUM CONFIDENCE";
        explanation = "HIGH ALERT: AI model predicts high inundation probability due to forecasted rainfall loading, though observed river stage currently remains below CWC warning mark.";
      } else if (aiRisk === "MEDIUM") {
        status = "WATCH";
        confidence = "HIGH CONFIDENCE";
        explanation = "WATCH: Moderate AI flood risk detected. River water level remains below CWC warning mark.";
      } else {
        status = "NORMAL";
        confidence = "HIGH CONFIDENCE";
        explanation = "NORMAL: Both AI flood model and observed CWC river water level are within normal baseline thresholds.";
      }
    }
  } else {
    // PRIORITY RULE B: CWC is UNAVAILABLE, STALE, or ERROR
    if (isFallbackActive) {
      basis = "AI MODEL + ENVIRONMENTAL FALLBACK";
      confidence = "MEDIUM CONFIDENCE";

      if (aiRisk === "HIGH" || aiRisk === "VERY HIGH") {
        status = "HIGH ALERT";
        explanation = fallbackRisk === "HIGH"
          ? "HIGH ALERT: AI prediction and environmental indicators indicate elevated flood risk. Live CWC river telemetry is currently unavailable, so observed river conditions cannot be independently confirmed."
          : "HIGH ALERT: AI model indicates elevated flood probability. Live CWC river telemetry is currently unavailable.";
      } else if (aiRisk === "MEDIUM") {
        if (fallbackRisk === "HIGH") {
          status = "HIGH ALERT";
          explanation = "HIGH ALERT: Moderate AI model risk combined with heavy environmental rainfall loading. Live CWC river telemetry is currently unavailable.";
        } else {
          status = "WATCH";
          explanation = "WATCH: Moderate AI flood probability with normal-to-moderate environmental indicators. Live CWC river telemetry is currently unavailable.";
        }
      } else {
        // AI is LOW
        if (fallbackRisk === "HIGH") {
          status = "WATCH";
          explanation = "WATCH: Heavy environmental precipitation loading detected. Flood danger is not confirmed because live CWC river telemetry is currently unavailable.";
        } else {
          status = "NORMAL";
          explanation = "NORMAL: AI flood model and environmental indicators are both within normal baseline thresholds. Live CWC river telemetry is currently unavailable.";
        }
      }
    } else {
      // Both CWC and Fallback are UNAVAILABLE
      basis = "AI MODEL ONLY";
      confidence = "LIMITED CONFIDENCE";

      if (aiRisk === "HIGH" || aiRisk === "VERY HIGH") {
        status = "HIGH ALERT";
        explanation = "HIGH ALERT: AI prediction indicates elevated flood probability. Live CWC river telemetry and environmental fallback are unavailable.";
      } else if (aiRisk === "MEDIUM") {
        status = "WATCH";
        explanation = "WATCH: Moderate AI flood probability. Live CWC river telemetry is currently unavailable.";
      } else {
        status = "NORMAL";
        explanation = "NORMAL: Normal monitoring based on AI model. Live CWC gauge telemetry is currently unavailable (Limited Confidence).";
      }
    }

    if (isCwcStale) {
      explanation += " (Note: CWC telemetry available but stale — older than 24 hours).";
    }
  }

  console.log(`[RISK] AI=${aiRisk} CWC=${cwcCondition} (${cwcStatus}) FALLBACK=${fallbackRisk} -> Overall=${status} (${confidence}) Basis=${basis}`);

  return {
    status, // NORMAL | WATCH | HIGH ALERT | CRITICAL
    confidence, // HIGH CONFIDENCE | MEDIUM CONFIDENCE | LIMITED CONFIDENCE
    basis, // "AI MODEL + CWC GROUND TRUTH" | "AI MODEL + ENVIRONMENTAL FALLBACK" | "AI MODEL ONLY"
    explanation,
    cwc_status: cwcStatus,
    ai_risk: aiRisk,
    fallback_risk: fallbackRisk
  };
}

// Backwards compatibility alias
export const computeOverallMonitoringStatus = (aiRiskClass, cwcStatus) => {
  const result = aggregateMultiSignalRisk({
    aiSignal: { risk: aiRiskClass },
    cwcSignal: { status: cwcStatus === "UNAVAILABLE" ? "UNAVAILABLE" : "AVAILABLE", condition: cwcStatus },
    fallbackSignal: { status: "AVAILABLE", risk: "LOW" }
  });
  return {
    ...result,
    message: result.explanation,
    decisionBasis: [result.basis]
  };
};

function calculateRiskScore(mlProbPct, rain24, rain72, forecast72, dischargeRatio, soilMoisture, elevation, exposureData) {
  const components = {};
  let totalWeight = 0;
  let availableWeight = 0;
  let weightedSum = 0;

  const mlAvail = mlProbPct !== null;
  const mlScore = mlAvail ? mlProbPct : 0;
  components.mlScore = round(mlScore, 1);
  if (mlAvail) { availableWeight += 0.50; weightedSum += 0.50 * mlScore; }
  totalWeight += 0.50;

  const rainAvail = rain24 !== null && rain72 !== null;
  const rainScore = rainAvail ? clamp(rain24 * 0.5 + rain72 * 0.2, 0, 100) : 0;
  components.rainScore = round(rainScore, 1);
  if (rainAvail) { availableWeight += 0.15; weightedSum += 0.15 * rainScore; }
  totalWeight += 0.15;

  const nwpAvail = forecast72 !== null;
  const nwpScore = nwpAvail ? clamp(forecast72 * 0.4, 0, 100) : 0;
  components.nwpScore = round(nwpScore, 1);
  if (nwpAvail) { availableWeight += 0.10; weightedSum += 0.10 * nwpScore; }
  totalWeight += 0.10;

  const hydroAvail = dischargeRatio !== null;
  const hydroScore = hydroAvail ? clamp((dischargeRatio - 0.5) * 40, 0, 100) : 0;
  components.hydroScore = round(hydroScore, 1);
  if (hydroAvail) { availableWeight += 0.10; weightedSum += 0.10 * hydroScore; }
  totalWeight += 0.10;

  const terrainAvail = elevation !== null;
  const terrainScore = terrainAvail
    ? (elevation < 20 ? 90 : elevation < 60 ? 60 : elevation < 150 ? 30 : 10)
    : 0;
  components.terrainScore = round(terrainScore, 1);
  if (terrainAvail) { availableWeight += 0.05; weightedSum += 0.05 * terrainScore; }
  totalWeight += 0.05;

  const soilAvail = soilMoisture !== null;
  const soilScore = soilAvail ? clamp(soilMoisture * 150, 0, 100) : 0;
  components.soilScore = round(soilScore, 1);
  if (soilAvail) { availableWeight += 0.05; weightedSum += 0.05 * soilScore; }
  totalWeight += 0.05;

  const expVal = exposureData?.population?.value;
  const expAvail = expVal !== null && expVal !== undefined;
  const exposureScore = expAvail ? clamp(expVal / 1000, 0, 100) : 0;
  components.exposureScore = expAvail ? round(exposureScore, 1) : null;
  if (expAvail) { availableWeight += 0.05; weightedSum += 0.05 * exposureScore; }
  totalWeight += 0.05;

  const scoreStatus = availableWeight >= totalWeight ? "COMPLETE"
    : availableWeight >= totalWeight * 0.70 ? "PARTIAL"
    : "INSUFFICIENT";

  const riskScore = availableWeight > 0 ? round(weightedSum / availableWeight, 2) : null;

  return {
    riskScore: scoreStatus !== "INSUFFICIENT" ? riskScore : null,
    scoreStatus,
    availableWeight: round(availableWeight, 2),
    totalWeight: round(totalWeight, 2),
    components
  };
}

/**
 * Builds demo mode synthetic payload for presentation and hackathon evaluation.
 */
function buildDemoScenario(scenarioNum, latitude, longitude, language, place) {
  const num = Number(scenarioNum) || 1;
  const nowIso = new Date().toISOString();
  const address = place?.reverseGeocode || {};
  const basinName = address.city || address.district || "Varanasi (Ganga Basin)";

  // Predefined scenarios from Prompt Section 12
  const scenarios = {
    1: {
      name: "Scenario 1: Baseline Normal Hydrology",
      ai: { probability: 6.7, risk: "LOW" },
      cwc: {
        source: "CWC",
        status: "AVAILABLE",
        station: "Varanasi (Ganga)",
        station_id: "CWC_006-MGD3VNS",
        river: "Ganga",
        distance_km: 0.0,
        water_level_m: 68.20,
        warning_level_m: 70.262,
        danger_level_m: 71.262,
        extreme_level_m: 73.901,
        condition: "BELOW_WARNING",
        updated_at: nowIso,
        reason: null
      },
      fallback: {
        source: "FALLBACK_ENVIRONMENTAL",
        status: "AVAILABLE",
        risk: "LOW",
        rainfall_mm: 4.5,
        forecast_rainfall_mm: 12.0,
        river_proximity: "NEAR",
        summary: "Normal environmental precipitation and hydrologic baseline."
      }
    },
    2: {
      name: "Scenario 2: Moderate Model Risk + High Environmental Fallback (CWC Unavailable)",
      ai: { probability: 45.0, risk: "MEDIUM" },
      cwc: {
        source: "CWC",
        status: "UNAVAILABLE",
        station: "Varanasi (Ganga)",
        station_id: "CWC_006-MGD3VNS",
        river: "Ganga",
        distance_km: 0.0,
        water_level_m: null,
        warning_level_m: 70.262,
        danger_level_m: 71.262,
        extreme_level_m: 73.901,
        condition: "UNKNOWN",
        updated_at: null,
        reason: "Live CWC telemetry is currently unavailable."
      },
      fallback: {
        source: "FALLBACK_ENVIRONMENTAL",
        status: "AVAILABLE",
        risk: "HIGH",
        rainfall_mm: 85.0,
        forecast_rainfall_mm: 120.0,
        river_proximity: "NEAR",
        summary: "Heavy 24h rainfall loading and near river proximity."
      }
    },
    3: {
      name: "Scenario 3: High AI Model Flood Risk + High Environmental Fallback (CWC Unavailable)",
      ai: { probability: 72.5, risk: "HIGH" },
      cwc: {
        source: "CWC",
        status: "UNAVAILABLE",
        station: "Varanasi (Ganga)",
        station_id: "CWC_006-MGD3VNS",
        river: "Ganga",
        distance_km: 0.0,
        water_level_m: null,
        warning_level_m: 70.262,
        danger_level_m: 71.262,
        extreme_level_m: 73.901,
        condition: "UNKNOWN",
        updated_at: null,
        reason: "Live CWC telemetry is currently unavailable."
      },
      fallback: {
        source: "FALLBACK_ENVIRONMENTAL",
        status: "AVAILABLE",
        risk: "HIGH",
        rainfall_mm: 95.0,
        forecast_rainfall_mm: 140.0,
        river_proximity: "NEAR",
        summary: "Torrential cumulative precipitation and catchment saturation."
      }
    },
    4: {
      name: "Scenario 4: Confirmed Severe Inundation (High AI + CWC Above Danger Level)",
      ai: { probability: 78.4, risk: "HIGH" },
      cwc: {
        source: "CWC",
        status: "AVAILABLE",
        station: "Varanasi (Ganga)",
        station_id: "CWC_006-MGD3VNS",
        river: "Ganga",
        distance_km: 0.0,
        water_level_m: 71.85,
        warning_level_m: 70.262,
        danger_level_m: 71.262,
        extreme_level_m: 73.901,
        condition: "ABOVE_DANGER",
        updated_at: nowIso,
        reason: null
      },
      fallback: {
        source: "FALLBACK_ENVIRONMENTAL",
        status: "AVAILABLE",
        risk: "HIGH",
        rainfall_mm: 110.0,
        forecast_rainfall_mm: 160.0,
        river_proximity: "NEAR",
        summary: "Extreme meteorological loading aligning with dangerous river stage."
      }
    },
    5: {
      name: "Scenario 5: Ground-Truth Gauge Surge (Low AI + CWC Above Danger Level)",
      ai: { probability: 6.7, risk: "LOW" },
      cwc: {
        source: "CWC",
        status: "AVAILABLE",
        station: "Varanasi (Ganga)",
        station_id: "CWC_006-MGD3VNS",
        river: "Ganga",
        distance_km: 0.0,
        water_level_m: 71.80,
        warning_level_m: 70.262,
        danger_level_m: 71.262,
        extreme_level_m: 73.901,
        condition: "ABOVE_DANGER",
        updated_at: nowIso,
        reason: null
      },
      fallback: {
        source: "FALLBACK_ENVIRONMENTAL",
        status: "AVAILABLE",
        risk: "HIGH",
        rainfall_mm: 88.0,
        forecast_rainfall_mm: 130.0,
        river_proximity: "NEAR",
        summary: "Ground-truth river surge detected above danger level."
      }
    }
  };

  const selected = scenarios[num] || scenarios[1];

  const overall = aggregateMultiSignalRisk({
    aiSignal: selected.ai,
    cwcSignal: selected.cwc,
    fallbackSignal: selected.fallback
  });

  return {
    status: "OK",
    is_demo: true,
    demo_scenario: num,
    demo_scenario_name: selected.name,
    demo_banner: "⚠ DEMO MODE — SYNTHETIC DATA — NOT LIVE OBSERVATION",
    generated_at: nowIso,
    location: {
      latitude: Number(latitude),
      longitude: Number(longitude),
      basin_name: basinName,
      basin_id: "CWC_BASIN_DEMO",
      country: "India",
      state: "Uttar Pradesh",
      district: "Varanasi",
      display_name: `${round(latitude, 4)}, ${round(longitude, 4)} (Demo Simulation)`
    },
    ai_risk_status: {
      source: "AI_MODEL",
      probability: selected.ai.probability,
      risk: selected.ai.risk,
      label: selected.ai.risk,
      sourceType: "MODELLED"
    },
    cwc_ground_truth: selected.cwc,
    fallback_environmental: selected.fallback,
    overall_monitoring: overall,

    prediction: {
      flood_probability: selected.ai.probability / 100,
      flood_probability_pct: selected.ai.probability,
      risk_class: selected.ai.risk,
      risk_score: selected.ai.probability,
      confidence_pct: 95.0,
      model_name: "ChetakAI ML (Demo Mode)",
      status: "OK",
      is_real_ml: false
    },
    alert: {
      level: overall.status,
      severity: overall.status,
      active: overall.status !== "NORMAL"
    },
    current_weather: {
      rainfall_1h: { value: 2.0, unit: "mm", source: "Demo", sourceType: "OBSERVED", status: "OK" },
      rainfall_3h: { value: 6.0, unit: "mm", source: "Demo", sourceType: "OBSERVED", status: "OK" },
      rainfall_6h: { value: 12.0, unit: "mm", source: "Demo", sourceType: "OBSERVED", status: "OK" },
      rainfall_12h: { value: 24.0, unit: "mm", source: "Demo", sourceType: "OBSERVED", status: "OK" },
      rainfall_24h: { value: selected.fallback.rainfall_mm, unit: "mm", source: "Demo", sourceType: "OBSERVED", status: "OK" },
      rainfall_72h: { value: selected.fallback.rainfall_mm * 1.5, unit: "mm", source: "Demo", sourceType: "OBSERVED", status: "OK" },
      temperature: { value: 28.5, unit: "°C", source: "Demo", sourceType: "OBSERVED", status: "OK" },
      humidity: { value: 85, unit: "%", source: "Demo", sourceType: "OBSERVED", status: "OK" },
      pressure: { value: 1008, unit: "hPa", source: "Demo", sourceType: "OBSERVED", status: "OK" },
      wind_speed: { value: 18, unit: "km/h", source: "Demo", sourceType: "OBSERVED", status: "OK" }
    },
    forecast: {
      nwp_rain_72h: { value: selected.fallback.forecast_rainfall_mm, unit: "mm", source: "Demo NWP", sourceType: "FORECAST", status: "OK" }
    },
    terrain: {
      elevation_m: { value: 76.0, unit: "m", source: "Demo DEM", sourceType: "OBSERVED", status: "OK" },
      mean_slope_deg: { value: 2.4, unit: "°", source: "Derived", sourceType: "DERIVED", status: "OK" }
    },
    hydrology: {
      river_stage: {
        value: selected.cwc.water_level_m,
        unit: "m",
        source: "CWC",
        sourceType: selected.cwc.status === "AVAILABLE" ? "OBSERVED" : "UNAVAILABLE",
        status: selected.cwc.status === "AVAILABLE" ? "OK" : "UNAVAILABLE",
        warningLevel: selected.cwc.warning_level_m,
        dangerLevel: selected.cwc.danger_level_m,
        hfl: selected.cwc.extreme_level_m,
        gaugeId: selected.cwc.station_id,
        gaugeName: selected.cwc.station,
        river: selected.cwc.river
      },
      river_discharge: {
        value: 17537.8,
        unit: "m³/s",
        source: "GloFAS",
        sourceType: "MODELLED",
        label: "GloFAS Modelled River Discharge",
        status: "OK"
      }
    },
    land_cover: {
      cropland_pct: { value: 72.5, unit: "%", source: "Catchment DB", sourceType: "ESTIMATED", status: "OK" }
    },
    exposure: approximateExposure(selected.ai.probability),
  };
}

export async function generateFloodIntelligence({
  latitude,
  longitude,
  language = "en",
  demoScenario = null
}) {
  const [live, place] = await Promise.all([
    getLiveIntelligenceInputs(latitude, longitude),
    reverseGeocode(latitude, longitude).catch(() => null)
  ]);

  // If a synthetic demo scenario is requested, produce presentation payload
  if (demoScenario && Number(demoScenario) >= 1 && Number(demoScenario) <= 5) {
    console.log(`[DEMO] Serving synthetic scenario ${demoScenario}`);
    const demoPayload = buildDemoScenario(demoScenario, latitude, longitude, language, place);
    const briefing = generateDisasterBriefing({ telemetry: demoPayload, language });
    return {
      ...demoPayload,
      ai_briefing: briefing
    };
  }

  // LIVE MODE: Run actual live API and model calculations
  console.log(`[LIVE] Running physical multi-signal analysis for ${latitude}, ${longitude}`);

  const nearestStation = findNearestCWCStation(latitude, longitude);
  const [cwcObservation, catchment, quality] = await Promise.all([
    getCWCObservation(latitude, longitude).catch(err => {
      console.warn(`[CWC] Unhandled error: ${err.message}`);
      return {
        source: "CWC",
        status: "ERROR",
        reason: err.message,
        station: null,
        distance_km: null,
        water_level_m: null,
        condition: "UNKNOWN"
      };
    }),
    getCatchmentProfile(latitude, longitude, live.elevation),
    validateEnvironmentalInputs(live)
  ]);

  // 1. SIGNAL 1: AI MODEL (Kept completely independent)
  const mlResult = predictFloodRisk(live, catchment);
  const isMlActive = mlResult && mlResult.status !== "INSUFFICIENT_DATA";
  const mlProbPct = isMlActive ? mlResult.flood_probability_pct : null;
  const aiRisk = isMlActive ? mapAiRisk(mlProbPct) : "UNKNOWN";

  const aiSignal = {
    source: "AI_MODEL",
    probability: mlProbPct !== null ? round(mlProbPct / 100, 3) : null,
    probability_pct: mlProbPct,
    risk: aiRisk,
    model_name: mlResult ? (mlResult.modelName || "ChetakAI ML") : "NONE",
    confidence_pct: isMlActive ? mlResult.confidencePct : null
  };

  // 2. SIGNAL 2: CWC GROUND TRUTH
  const cwcSignal = {
    source: "CWC",
    status: cwcObservation.status, // AVAILABLE | UNAVAILABLE | STALE | ERROR
    station: cwcObservation.station || (cwcObservation.station_name ? `${cwcObservation.station_name} (${cwcObservation.river})` : "Nearest CWC Station"),
    station_name: cwcObservation.station_name || null,
    station_id: cwcObservation.station_id || null,
    river: cwcObservation.river || null,
    distance_km: cwcObservation.distance_km ?? null,
    water_level_m: cwcObservation.water_level_m ?? null,
    warning_level_m: cwcObservation.warning_level_m ?? null,
    danger_level_m: cwcObservation.danger_level_m ?? null,
    extreme_level_m: cwcObservation.extreme_level_m ?? null,
    condition: cwcObservation.condition || "UNKNOWN",
    updated_at: cwcObservation.updated_at ?? null,
    reason: cwcObservation.reason || null,
    data_source: cwcObservation.data_source
  };

  // 3. SIGNAL 3: FALLBACK ENVIRONMENTAL
  const fallbackSignal = evaluateEnvironmentalFallback({
    live,
    catchment,
    nearestStationDistanceKm: cwcObservation.distance_km
  });

  // 4. CENTRAL RISK AGGREGATION
  const overallMonitoring = aggregateMultiSignalRisk({
    aiSignal,
    cwcSignal,
    fallbackSignal
  });

  // Calculate legacy risk score for detailed components breakdown
  const dischargeMean = live.flood.dischargeMean;
  const dischargeNow = live.flood.dischargeNow;
  const dischargeRatio = (dischargeNow !== null && dischargeMean > 0) ? dischargeNow / dischargeMean : null;

  const exposure = approximateExposure(mlProbPct, catchment);
  const exposureData = {
    population: exposure.population,
    buildings: exposure.buildings_exposed
  };

  const { riskScore, scoreStatus, components } = calculateRiskScore(
    mlProbPct, 
    live.rainfall.h24, 
    live.rainfall.h72, 
    live.rainfall.forecast72h, 
    dischargeRatio, 
    live.current.soilMoisture, 
    live.elevation,
    exposureData
  );

  const address = place?.reverseGeocode || {};
  const displayName = place?.displayName || `${round(latitude, 4)}, ${round(longitude, 4)}`;
  const basinName = address.city || address.district || catchment.basin_name || address.state || "Regional Catchment";

  const nowIso = new Date().toISOString();
  const isCwcLive = cwcSignal.status === "AVAILABLE" && cwcSignal.water_level_m !== null;

  const result = {
    status: isMlActive ? "OK" : "INSUFFICIENT_DATA",
    is_demo: false,
    generated_at: nowIso,
    location: {
      latitude: Number(latitude),
      longitude: Number(longitude),
      basin_name: basinName,
      basin_id: catchment.basin_id || "CWC_BASIN",
      country: address.country || "India",
      state: address.state || "India",
      district: address.district || address.city || "Monitored District",
      display_name: displayName
    },

    // 1. AI Model Signal
    ai_risk_status: {
      source: "AI_MODEL",
      probability: mlProbPct,
      risk: aiRisk,
      label: aiRisk,
      sourceType: "MODELLED"
    },

    // 2. CWC Ground Truth Signal
    cwc_ground_truth: cwcSignal,

    // 3. Fallback Environmental Signal
    fallback_environmental: fallbackSignal,

    // 4. Overall Monitoring Decision
    overall_monitoring: {
      status: overallMonitoring.status, // NORMAL | WATCH | HIGH ALERT | CRITICAL
      confidence: overallMonitoring.confidence, // HIGH CONFIDENCE | MEDIUM CONFIDENCE | LIMITED CONFIDENCE
      basis: overallMonitoring.basis,
      message: overallMonitoring.explanation,
      explanation: overallMonitoring.explanation,
      ai_risk: aiRisk,
      cwc_status: cwcSignal.status,
      cwc_condition: cwcSignal.condition,
      fallback_risk: fallbackSignal.risk,
      independence_note: "AI prediction and observed river conditions are independent signals."
    },

    prediction: {
      flood_probability: mlProbPct !== null ? mlProbPct / 100 : null,
      flood_probability_pct: mlProbPct,
      risk_score: riskScore,
      risk_score_status: scoreStatus,
      risk_class: aiRisk,
      confidence_pct: isMlActive ? mlResult.confidencePct : null,
      model_name: mlResult ? (mlResult.modelName || "ChetakAI ML") : "NONE",
      feature_count: mlResult ? (mlResult.featuresUsed?.length || 0) : 0,
      version: mlResult ? mlResult.version : "1.0.0",
      is_real_ml: isMlActive,
      status: mlResult ? (mlResult.status || "OK") : "UNAVAILABLE"
    },
    evidence: {
      top_features: isMlActive ? mlResult.drivers : []
    },
    alert: {
      level: overallMonitoring.status,
      severity: overallMonitoring.status,
      active: overallMonitoring.status !== "NORMAL" && overallMonitoring.status !== "UNKNOWN",
      ai_level: aiRisk,
      cwc_status: cwcSignal.status,
      confidence: overallMonitoring.confidence
    },
    risk_components: components,

    current_weather: {
      rainfall_1h: { value: live.rainfall.h1, unit: "mm", source: "Open-Meteo", sourceType: "OBSERVED", observedAt: nowIso, status: live.rainfall.h1 !== null ? "OK" : "UNAVAILABLE" },
      rainfall_3h: { value: live.rainfall.h3, unit: "mm", source: "Open-Meteo", sourceType: "OBSERVED", observedAt: nowIso, status: live.rainfall.h3 !== null ? "OK" : "UNAVAILABLE" },
      rainfall_6h: { value: live.rainfall.h6, unit: "mm", source: "Open-Meteo", sourceType: "OBSERVED", observedAt: nowIso, status: live.rainfall.h6 !== null ? "OK" : "UNAVAILABLE" },
      rainfall_12h: { value: live.rainfall.h12, unit: "mm", source: "Open-Meteo", sourceType: "OBSERVED", observedAt: nowIso, status: live.rainfall.h12 !== null ? "OK" : "UNAVAILABLE" },
      rainfall_24h: { value: live.rainfall.h24, unit: "mm", source: "Open-Meteo", sourceType: "OBSERVED", observedAt: nowIso, status: live.rainfall.h24 !== null ? "OK" : "UNAVAILABLE" },
      rainfall_72h: { value: live.rainfall.h72, unit: "mm", source: "Open-Meteo", sourceType: "OBSERVED", observedAt: nowIso, status: live.rainfall.h72 !== null ? "OK" : "UNAVAILABLE" },
      temperature: { value: live.current.temperature, unit: "°C", source: "Open-Meteo", sourceType: "OBSERVED", observedAt: nowIso, status: live.current.temperature !== null ? "OK" : "UNAVAILABLE" },
      humidity: { value: live.current.humidity, unit: "%", source: "Open-Meteo", sourceType: "OBSERVED", observedAt: nowIso, status: live.current.humidity !== null ? "OK" : "UNAVAILABLE" },
      pressure: { value: live.current.pressure, unit: "hPa", source: "Open-Meteo", sourceType: "OBSERVED", observedAt: nowIso, status: live.current.pressure !== null ? "OK" : "UNAVAILABLE" },
      wind_speed: { value: live.current.wind, unit: "km/h", source: "Open-Meteo", sourceType: "OBSERVED", observedAt: nowIso, status: live.current.wind !== null ? "OK" : "UNAVAILABLE" }
    },
    forecast: {
      nwp_rain_1h: { value: live.rainfall.forecast1h, unit: "mm", source: "Open-Meteo NWP", sourceType: "FORECAST", status: live.rainfall.forecast1h !== null ? "OK" : "UNAVAILABLE" },
      nwp_rain_3h: { value: live.rainfall.forecast3h, unit: "mm", source: "Open-Meteo NWP", sourceType: "FORECAST", status: live.rainfall.forecast3h !== null ? "OK" : "UNAVAILABLE" },
      nwp_rain_6h: { value: live.rainfall.forecast6h, unit: "mm", source: "Open-Meteo NWP", sourceType: "FORECAST", status: live.rainfall.forecast6h !== null ? "OK" : "UNAVAILABLE" },
      nwp_rain_12h: { value: live.rainfall.forecast12h, unit: "mm", source: "Open-Meteo NWP", sourceType: "FORECAST", status: live.rainfall.forecast12h !== null ? "OK" : "UNAVAILABLE" },
      nwp_rain_24h: { value: live.rainfall.forecast24h, unit: "mm", source: "Open-Meteo NWP", sourceType: "FORECAST", status: live.rainfall.forecast24h !== null ? "OK" : "UNAVAILABLE" },
      nwp_rain_72h: { value: live.rainfall.forecast72h, unit: "mm", source: "Open-Meteo NWP", sourceType: "FORECAST", status: live.rainfall.forecast72h !== null ? "OK" : "UNAVAILABLE" },
      spread: { value: (live.rainfall.forecast24h * 0.15), unit: "mm", source: "Derived", sourceType: "DERIVED", status: live.rainfall.forecast24h !== null ? "OK" : "UNAVAILABLE" },
      confidence: { value: null, unit: "%", source: "NWP Ensemble", sourceType: "DERIVED", status: "UNAVAILABLE" }
    },
    terrain: {
      elevation_m: { value: live.elevation, unit: "m", source: "Open-Meteo DEM", sourceType: "OBSERVED", observedAt: nowIso, status: live.elevation !== null ? "OK" : "UNAVAILABLE" },
      mean_slope_deg: { value: catchment.slope_deg, unit: "°", source: "Derived", sourceType: "DERIVED", status: catchment.slope_deg !== null ? "OK" : "UNAVAILABLE" },
      elevation_range_ratio: { value: live.elevation ? Number((catchment.relief_m / live.elevation).toFixed(2)) : null, unit: "", source: "Derived", sourceType: "DERIVED", status: live.elevation ? "OK" : "UNAVAILABLE" },
      flow_accumulation: { value: null, unit: "cells", source: "HydroBASINS", sourceType: "ESTIMATED", status: "UNAVAILABLE" },
      distance_to_river_km: { value: null, unit: "km", source: "HydroSHEDS", sourceType: "ESTIMATED", status: "UNAVAILABLE" }
    },
    hydrology: {
      river_stage: { 
        value: cwcSignal.water_level_m, 
        unit: "m", 
        source: "CWC", 
        sourceType: isCwcLive ? "OBSERVED" : "UNAVAILABLE", 
        observedAt: cwcSignal.updated_at,
        status: isCwcLive ? "OK" : "UNAVAILABLE",
        gauge: cwcObservation?.gauge || null,
        gaugeMatched: Boolean(cwcSignal.station_id),
        gaugeDistanceKm: cwcSignal.distance_km,
        gaugeId: cwcSignal.station_id,
        gaugeName: cwcSignal.station_name,
        river: cwcSignal.river,
        warningLevel: cwcSignal.warning_level_m,
        dangerLevel: cwcSignal.danger_level_m,
        hfl: cwcSignal.extreme_level_m,
        trend: "UNKNOWN",
        cwcStatus: cwcSignal.condition,
        failureReason: cwcSignal.reason,
        dataSource: cwcSignal.data_source
      },
      river_discharge: { 
        value: live.flood.dischargeNow, 
        unit: "m³/s", 
        source: "GloFAS", 
        sourceType: "MODELLED", 
        variable: "river_discharge",
        label: "GloFAS Modelled River Discharge",
        modelledAt: nowIso,
        status: live.flood.dischargeNow !== null ? "OK" : "UNAVAILABLE" 
      },
      river_area_km2: { value: null, unit: "km²", source: "HydroLAKES", sourceType: "ESTIMATED", status: "UNAVAILABLE" },
      reservoir_count: { value: null, unit: "", source: "GRanD", sourceType: "ESTIMATED", status: "UNAVAILABLE" }
    },
    soil: {
      soil_moisture: { value: live.current.soilMoisture, unit: "m³/m³", source: "Open-Meteo", sourceType: "MODELLED", status: live.current.soilMoisture !== null ? "OK" : "UNAVAILABLE" },
      clay_pct: { value: catchment.soil?.clay_fraction_pct ?? null, unit: "%", source: "Catchment DB", sourceType: "ESTIMATED", status: catchment.soil?.clay_fraction_pct !== undefined ? "OK" : "UNAVAILABLE" },
      sand_fraction_pct: { value: catchment.soil?.sand_fraction_pct ?? null, unit: "%", source: "Catchment DB", sourceType: "ESTIMATED", status: catchment.soil?.sand_fraction_pct !== undefined ? "OK" : "UNAVAILABLE" },
      silt_fraction_pct: { value: catchment.soil?.silt_fraction_pct ?? null, unit: "%", source: "Catchment DB", sourceType: "ESTIMATED", status: catchment.soil?.silt_fraction_pct !== undefined ? "OK" : "UNAVAILABLE" },
      soil_runoff_proxy: { value: catchment.curve_number, unit: "Index", source: "NRCS CN", sourceType: "DERIVED", status: catchment.curve_number !== undefined ? "OK" : "UNAVAILABLE" }
    },
    land_cover: {
      cropland_pct: { 
        value: catchment.land_cover?.cropland_pct ?? null, 
        unit: "%", 
        source: "Catchment DB", 
        sourceType: "ESTIMATED", 
        label: "Catchment land-cover composition • ESTIMATED",
        status: catchment.land_cover?.cropland_pct !== undefined ? "OK" : "UNAVAILABLE" 
      },
      built_up_pct: { value: catchment.land_cover?.built_up_pct ?? null, unit: "%", source: "Catchment DB", sourceType: "ESTIMATED", status: catchment.land_cover?.built_up_pct !== undefined ? "OK" : "UNAVAILABLE" },
      tree_cover_pct: { value: catchment.land_cover?.tree_cover_pct ?? null, unit: "%", source: "Catchment DB", sourceType: "ESTIMATED", status: catchment.land_cover?.tree_cover_pct !== undefined ? "OK" : "UNAVAILABLE" },
      water_pct: { value: catchment.land_cover?.water_pct ?? null, unit: "%", source: "Catchment DB", sourceType: "ESTIMATED", status: catchment.land_cover?.water_pct !== undefined ? "OK" : "UNAVAILABLE" },
      wetland_pct: { value: catchment.land_cover?.wetland_pct ?? null, unit: "%", source: "Catchment DB", sourceType: "ESTIMATED", status: catchment.land_cover?.wetland_pct !== undefined ? "OK" : "UNAVAILABLE" },
      natural_vegetation_pct: { value: catchment.land_cover?.natural_vegetation_pct ?? null, unit: "%", source: "Catchment DB", sourceType: "ESTIMATED", status: catchment.land_cover?.natural_vegetation_pct !== undefined ? "OK" : "UNAVAILABLE" }
    },
    exposure,
    data_quality: {
      coordinate_resolution: quality.coordinate_resolution,
      quality_score: quality.quality_score,
      validation_status: quality.status,
      validation_issues: quality.issues,
      source_traceable: true
    },
    ml_debug: {
      model: mlResult ? (mlResult.modelName || "NONE") : "NONE",
      modelVersion: mlResult ? (mlResult.version || "UNKNOWN") : "UNKNOWN",
      featureCount: isMlActive ? (mlResult.featuresUsed?.length || 0) : 0,
      missingFeatureCount: mlResult ? (mlResult.featuresMissing?.length || 0) : 0,
      imputedFeatureCount: 0,
      zeroFilledFeatureCount: 0,
      rawProbability: isMlActive ? mlResult.probability : null,
      finalProbability: mlProbPct,
      confidencePct: isMlActive ? mlResult.confidencePct : null,
      treeVariance: isMlActive ? (mlResult.debug?.treeVariance ?? null) : null,
      predictionStatus: isMlActive ? "OK" : (mlResult?.status || "UNAVAILABLE"),
      raw_features: isMlActive ? mlResult.raw_features : null,
      features_used: isMlActive ? mlResult.featuresUsed : [],
      features_missing: mlResult ? mlResult.featuresMissing : [],
      tree_count: isMlActive ? (mlResult.raw_features ? 30 : 0) : 0
    }
  };

  validateAnalysisResult(result);

  const aiBriefing = generateDisasterBriefing({
    telemetry: result,
    language
  });

  return {
    ...result,
    ai_briefing: aiBriefing
  };
}

function validateAnalysisResult(result) {
  const issues = [];

  function sanitize(obj, path = "") {
    if (obj === null || obj === undefined) return;
    if (typeof obj !== "object") return;

    for (const [key, val] of Object.entries(obj)) {
      const fullPath = path ? `${path}.${key}` : key;

      if (typeof val === "number") {
        if (Number.isNaN(val)) {
          issues.push(`NaN detected at ${fullPath}`);
          obj[key] = null;
        } else if (!Number.isFinite(val)) {
          issues.push(`Infinity detected at ${fullPath}`);
          obj[key] = null;
        }
      } else if (typeof val === "object" && val !== null) {
        if ("value" in val && typeof val.value === "number") {
          if (Number.isNaN(val.value)) {
            issues.push(`NaN value at ${fullPath}.value`);
            val.value = null;
            val.status = "UNAVAILABLE";
          } else if (!Number.isFinite(val.value)) {
            issues.push(`Infinity value at ${fullPath}.value`);
            val.value = null;
            val.status = "UNAVAILABLE";
          }
        }
        sanitize(val, fullPath);
      }
    }
  }

  sanitize(result);

  if (issues.length > 0) {
    if (!result.data_quality) result.data_quality = {};
    result.data_quality.validation_issues = [
      ...(result.data_quality.validation_issues || []),
      ...issues
    ];
  }
}
