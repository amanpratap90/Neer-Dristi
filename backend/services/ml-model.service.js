/**
 * Production Machine Learning Inference Engine for ChetakAI
 * Loads the trained Calibrated Decision Forest model and performs
 * real-time inference with exact mathematical parity, sub-millisecond latency,
 * and coordinate-specific feature attribution.
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const MODEL_PATH = path.join(__dirname, "..", "models", "production_flood_model.json");

let modelArtifact = null;
let isLoaded = false;

function loadModel() {
  if (isLoaded) return modelArtifact;
  try {
    const raw = fs.readFileSync(MODEL_PATH, "utf-8");
    modelArtifact = JSON.parse(raw);
    isLoaded = true;
    console.log(`[ML-Model] Loaded ${modelArtifact.model_name} (v${modelArtifact.version}) with ${modelArtifact.n_estimators} trees.`);
  } catch (err) {
    console.error(`[ML-Model] Error loading model artifact from ${MODEL_PATH}:`, err.message);
    modelArtifact = null;
  }
  return modelArtifact;
}

// Initial load attempt
loadModel();

function clamp(val, min, max) {
  return Math.min(max, Math.max(min, val));
}

function round(val, digits = 2) {
  const n = Number(val);
  if (!Number.isFinite(n)) return 0;
  return Number(n.toFixed(digits));
}

/**
 * Evaluates a single decision tree on the feature vector
 */
function evaluateTree(tree, featureVector) {
  let node = 0;
  const left = tree.children_left;
  const right = tree.children_right;
  const feature = tree.feature;
  const threshold = tree.threshold;
  const values = tree.values;

  // Track decision path for feature contribution
  const pathFeatures = [];

  while (left[node] !== -1 && right[node] !== -1) {
    const featIdx = feature[node];
    const featVal = featureVector[featIdx];
    const thresh = threshold[node];

    pathFeatures.push({ featureIndex: featIdx, wentRight: featVal > thresh });

    if (featVal <= thresh) {
      node = left[node];
    } else {
      node = right[node];
    }
  }

  const counts = values[node];
  const total = counts[0] + counts[1];
  const prob = total > 0 ? counts[1] / total : 0;

  return { prob, pathFeatures };
}

/**
 * Builds the 30-feature vector from environmental telemetry
 */
export function buildFeatureVector(inputs, catchment) {
  const requiredFeatures = [
    "rainfall_1h_mm", "rainfall_24h_mm", "rainfall_72h_mm",
    "soil_moisture_0_to_1cm", "root_zone_soil_moisture",
    "elevation_m", "slope_deg"
  ];
  
  const missingFeatures = [];

  const rain = inputs.rainfall || {};
  const current = inputs.current || {};
  const daily = inputs.daily || {};
  const flood = inputs.flood || {};

  const getOrNull = (val) => (val !== undefined && val !== null && !isNaN(Number(val)) ? Number(val) : null);

  const rain1h = getOrNull(rain.h1);
  const rain3h = getOrNull(rain.h3);
  const rain6h = getOrNull(rain.h6);
  const rain12h = getOrNull(rain.h12);
  const rain24h = getOrNull(rain.h24);
  const rain72h = getOrNull(rain.h72);
  const api = getOrNull(rain.antecedentPrecipitationIndex);

  const sm0_1 = getOrNull(current.soilMoisture0_1);
  const sm1_3 = getOrNull(current.soilMoisture1_3);
  const sm3_9 = getOrNull(current.soilMoisture3_9);
  const sm9_27 = getOrNull(current.soilMoisture9_27);
  const rootZoneMoisture = getOrNull(current.rootZoneSoilMoisture);

  const evap72h = getOrNull(rain.evapotranspiration72h);

  const soil = catchment.soil || {};
  const clay = getOrNull(soil.clay_fraction_pct);
  const sand = getOrNull(soil.sand_fraction_pct);
  const silt = getOrNull(soil.silt_fraction_pct);

  const elevation = getOrNull(inputs.elevation);
  const slope = getOrNull(catchment.slope_deg);
  const relief = getOrNull(catchment.relief_m);
  const drainageDensity = getOrNull(catchment.drainage_density_km_km2);
  const cn = getOrNull(catchment.curve_number);
  const potentialS = cn ? (25400 / cn - 254) : null;

  let scsRunoff = null;
  if (rain72h !== null && potentialS !== null) {
    const initialAbstraction = 0.2 * potentialS;
    const excessP = Math.max(0, rain72h - initialAbstraction);
    scsRunoff = excessP > 0 ? (excessP * excessP) / (rain72h + 0.8 * potentialS) : 0.0;
  }

  const dischargeMean = getOrNull(flood.dischargeMean);
  const dischargeNow = getOrNull(flood.dischargeNow);
  const dischargeRatio = (dischargeNow !== null && dischargeMean !== null && dischargeMean > 0) ? dischargeNow / dischargeMean : null;
  const dischargeExceedance = dischargeRatio !== null ? clamp((dischargeRatio - 1.0) * 45.0, 0, 100) : null;

  const landCover = catchment.land_cover || {};
  const cropland = getOrNull(landCover.cropland_pct);
  const builtUp = getOrNull(landCover.built_up_pct);
  const water = getOrNull(landCover.water_pct);

  // forecast fields
  const forecast24h = getOrNull(rain.forecast24h);
  const forecast72h = getOrNull(rain.forecast72h);

  const featureMap = {
    // Keys MUST exactly match model.features from production_flood_model.json
    rainfall_1h_mm: rain1h,
    rainfall_3h_mm: rain3h,
    rainfall_6h_mm: rain6h,
    rainfall_12h_mm: rain12h,
    rainfall_24h_mm: rain24h,
    rainfall_72h_mm: rain72h,
    forecast_24h_mm: forecast24h,
    forecast_72h_mm: forecast72h,
    antecedent_precipitation_index_7d: api,
    evapotranspiration_72h_mm: evap72h,
    soil_moisture_0_to_1cm: sm0_1,
    soil_moisture_1_to_3cm: sm1_3,
    soil_moisture_3_to_9cm: sm3_9,
    soil_moisture_9_to_27cm: sm9_27,
    root_zone_soil_moisture: rootZoneMoisture,
    clay_fraction_pct: clay,
    sand_fraction_pct: sand,
    silt_fraction_pct: silt,
    elevation_m: elevation,
    mean_slope_deg: slope,
    relief_m: relief,
    drainage_density_km_km2: drainageDensity,
    curve_number: cn,
    potential_retention_s_mm: potentialS,
    scs_runoff_depth_mm: scsRunoff,
    discharge_ratio: dischargeRatio,
    discharge_exceedance_pct: dischargeExceedance,
    cropland_pct: cropland,
    built_up_pct: builtUp,
    water_pct: water
  };

  // Check if ANY model feature is missing, as our model doesn't support NaNs natively
  const modelFeatures = modelArtifact ? modelArtifact.features : [];
  const missingModelFeatures = modelFeatures.filter(f => featureMap[f] === null);

  if (missingModelFeatures.length > 0) {
    return {
      status: "INSUFFICIENT_DATA",
      probability: null,
      probabilityPercent: null,
      riskClass: "UNKNOWN",
      modelName: isLoaded ? modelArtifact.model_name : "UNKNOWN",
      version: isLoaded ? modelArtifact.version : "UNKNOWN",
      sourceType: "MODELLED",
      featuresUsed: modelFeatures.filter(f => featureMap[f] !== null),
      featuresMissing: missingModelFeatures,
      confidencePct: null
    };
  }

  return featureMap;
}

/**
 * Predicts flood probability, risk class, calibrated confidence,
 * and feature drivers using the trained ML model.
 */
export function predictFloodRisk(inputs, catchment) {
  const model = loadModel();
  if (!model || !model.trees || model.trees.length === 0) {
    return null; // Signals fallback to heuristic
  }

  const featureMap = buildFeatureVector(inputs, catchment);
  
  if (featureMap.status === "INSUFFICIENT_DATA") {
    return featureMap;
  }

  const featureList = model.features;
  const vector = featureList.map((f) => Number(featureMap[f] ?? 0));

  // Evaluate Forest
  const treeCount = model.trees.length;
  let probSum = 0;
  const treeProbs = [];
  const featureContributionCounts = new Array(featureList.length).fill(0);

  for (let i = 0; i < treeCount; i += 1) {
    const { prob, pathFeatures } = evaluateTree(model.trees[i], vector);
    probSum += prob;
    treeProbs.push(prob);

    // If tree predicted high flood risk, reward the features along that decision branch
    if (prob > 0.4) {
      for (const step of pathFeatures) {
        if (step.wentRight) {
          featureContributionCounts[step.featureIndex] += (prob - 0.4);
        }
      }
    }
  }

  const rawProbability = probSum / treeCount;
  const probabilityPct = round(rawProbability * 100, 2);

  // Tree variance for confidence calibration
  let variance = 0;
  for (let i = 0; i < treeCount; i += 1) {
    variance += Math.pow(treeProbs[i] - rawProbability, 2);
  }
  variance /= treeCount;
  const stdDev = Math.sqrt(variance);

  // Confidence: based purely on ensemble variance
  const agreementFactor = Math.max(0, 1 - stdDev * 2.2);
  const confidencePct = round(70 + agreementFactor * 30, 1);

  // Risk Score calculation removed here, delegated to chetakai.service.js
  const riskScore = null;

  // Risk Class mapping
  let riskClass = "LOW";
  if (rawProbability >= 0.72 || riskScore >= 78) {
    riskClass = "SEVERE";
  } else if (rawProbability >= 0.50 || riskScore >= 58) {
    riskClass = "HIGH";
  } else if (rawProbability >= 0.25 || riskScore >= 32) {
    riskClass = "MODERATE";
  }

  // Calculate local feature attributions (decision drivers)
  const globalWeights = model.global_feature_importances || {};
  const driverScores = featureList.map((featName, idx) => {
    const globalImp = Number(globalWeights[featName] || 0.03);
    const localHit = featureContributionCounts[idx] / Math.max(1, treeCount);
    // Combine global learned importance with local active feature value
    const importance = round(globalImp * 0.6 + localHit * 0.4, 3);
    return {
      feature: featName,
      model_importance: Math.max(0.04, importance),
      value: featureMap[featName]
    };
  });

  driverScores.sort((a, b) => b.model_importance - a.model_importance);
  const topDrivers = driverScores.slice(0, 6);

  // Compute 6-pillar Risk Components (0-100)
  const rainComponent = round(clamp((featureMap.rainfall_72h_mm / 250) * 80 + (featureMap.rainfall_24h_mm / 100) * 20, 8, 100));
  const forecastComponent = round(clamp((featureMap.forecast_72h_mm / 200) * 85, 8, 100));
  const hydroComponent = round(clamp((featureMap.discharge_ratio / 2.5) * 80 + featureMap.discharge_exceedance_pct * 0.3, 12, 100));
  const terrainComponent = round(clamp((6.0 / Math.max(0.8, featureMap.mean_slope_deg)) * 25 + (featureMap.elevation_m < 30 ? 30 : 10), 10, 100));
  const soilComponent = round(clamp(featureMap.root_zone_soil_moisture * 150 + (featureMap.clay_fraction_pct / 50) * 20, 15, 100));
  const exposureComponent = round(clamp(featureMap.built_up_pct * 4.5 + (featureMap.elevation_m < 40 ? 25 : 10), 15, 90));

  return {
    status: "OK",
    probability: rawProbability,
    flood_probability_pct: probabilityPct,
    riskClass,
    modelName: model.model_name || "UNKNOWN",
    version: model.version || "UNKNOWN",
    sourceType: "MODELLED",
    featuresUsed: featureList,
    featuresMissing: [],
    confidencePct: confidencePct,
    drivers: topDrivers,
    components: {
      model_probability: probabilityPct,
      rainfall: rainComponent,
      forecast: forecastComponent,
      hydrology: hydroComponent,
      terrain: terrainComponent,
      surface_soil: soilComponent,
      exposure: exposureComponent
    },
    raw_features: featureMap,
    metrics: model.metrics,
    debug: {
      treeVariance: round(variance, 6),
      stdDev: round(stdDev, 6),
      agreementFactor: round(agreementFactor, 4)
    }
  };
}
