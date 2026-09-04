const FORECAST_URL = "https://api.open-meteo.com/v1/forecast";
const ELEVATION_URL = "https://api.open-meteo.com/v1/elevation";
const FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood";

const weatherCache = new Map();
const CACHE_TTL_MS = 90 * 1000; // 90 seconds cache

async function fetchJson(url, timeoutMs = 8000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`Upstream API returned ${response.status}`);
    }
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

function sumWindow(hourly = {}, field, hoursBack, hoursAhead = 0) {
  const times = hourly.time || [];
  const values = hourly[field] || hourly.precipitation || [];
  if (!times.length) return 0;

  const now = Date.now();
  const start = now - hoursBack * 3600 * 1000;
  const end = now + hoursAhead * 3600 * 1000;
  let sum = 0;

  for (let i = 0; i < times.length; i += 1) {
    const t = Date.parse(times[i]);
    if (!Number.isFinite(t)) continue;
    if (t >= start && t <= end) {
      sum += Number(values[i] || 0);
    }
  }

  return Number(sum.toFixed(2));
}

export async function getLiveIntelligenceInputs(latitude, longitude) {
  const cacheKey = `${Number(latitude).toFixed(4)}_${Number(longitude).toFixed(4)}`;
  const cached = weatherCache.get(cacheKey);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
    return cached.data;
  }

  const forecastUrl = new URL(FORECAST_URL);
  forecastUrl.searchParams.set("latitude", String(latitude));
  forecastUrl.searchParams.set("longitude", String(longitude));
  forecastUrl.searchParams.set(
    "current",
    [
      "temperature_2m",
      "relative_humidity_2m",
      "surface_pressure",
      "wind_speed_10m",
      "precipitation",
      "rain",
      "soil_moisture_0_to_1cm",
      "soil_moisture_1_to_3cm",
      "soil_moisture_3_to_9cm",
      "soil_moisture_9_to_27cm"
    ].join(",")
  );
  forecastUrl.searchParams.set(
    "hourly",
    ["precipitation", "rain", "temperature_2m", "relative_humidity_2m"].join(",")
  );
  forecastUrl.searchParams.set(
    "daily",
    [
      "precipitation_sum",
      "rain_sum",
      "temperature_2m_max",
      "temperature_2m_min",
      "et0_fao_evapotranspiration"
    ].join(",")
  );
  forecastUrl.searchParams.set("past_days", "7");
  forecastUrl.searchParams.set("forecast_days", "3");
  forecastUrl.searchParams.set("timezone", "auto");

  const elevationUrl = new URL(ELEVATION_URL);
  elevationUrl.searchParams.set("latitude", String(latitude));
  elevationUrl.searchParams.set("longitude", String(longitude));

  const floodUrl = new URL(FLOOD_URL);
  floodUrl.searchParams.set("latitude", String(latitude));
  floodUrl.searchParams.set("longitude", String(longitude));
  floodUrl.searchParams.set(
    "daily",
    "river_discharge,river_discharge_mean,river_discharge_median,river_discharge_max"
  );
  floodUrl.searchParams.set("forecast_days", "3");

  const [forecastResult, elevationResult, floodResult] = await Promise.allSettled([
    fetchJson(forecastUrl),
    fetchJson(elevationUrl),
    fetchJson(floodUrl)
  ]);

  if (forecastResult.status !== "fulfilled") {
    throw new Error(
      `Weather API failed: ${forecastResult.reason?.message || "unreachable"}`
    );
  }

  const forecast = forecastResult.value || {};
  const current = forecast.current || {};
  const hourly = forecast.hourly || {};
  const daily = forecast.daily || {};

  const rainfall1h = Number(current.precipitation ?? current.rain ?? 0);
  const rainfall3h = sumWindow(hourly, "precipitation", 3);
  const rainfall6h = sumWindow(hourly, "precipitation", 6);
  const rainfall12h = sumWindow(hourly, "precipitation", 12);
  const rainfall24h = sumWindow(hourly, "precipitation", 24);
  const rainfall72h = sumWindow(hourly, "precipitation", 72);
  const forecast1h = sumWindow(hourly, "precipitation", 0, 1);
  const forecast3h = sumWindow(hourly, "precipitation", 0, 3);
  const forecast6h = sumWindow(hourly, "precipitation", 0, 6);
  const forecast12h = sumWindow(hourly, "precipitation", 0, 12);
  const forecast24h = sumWindow(hourly, "precipitation", 0, 24);
  const forecast72h = sumWindow(hourly, "precipitation", 0, 72);

  const dailySums = Array.isArray(daily.precipitation_sum)
    ? daily.precipitation_sum.map((v) => Number(v || 0))
    : [];

  // Calculate 7-day Antecedent Precipitation Index (API = sum(0.85^t * Rain_t))
  // The first 7 entries in dailySums correspond to the past 7 days
  let antecedentPrecipitationIndex = null;
  if (dailySums.length >= 7) {
    antecedentPrecipitationIndex = 0;
    for (let i = 0; i < 7; i += 1) {
      const dayRain = dailySums[6 - i] || 0; // index 6 is yesterday, index 5 is 2 days ago
      antecedentPrecipitationIndex += dayRain * Math.pow(0.85, i + 1);
    }
    antecedentPrecipitationIndex = Number(antecedentPrecipitationIndex.toFixed(2));
  } else if (rainfall24h !== null && rainfall72h !== null) {
    antecedentPrecipitationIndex = Number(((rainfall24h * 0.85) + ((rainfall72h - rainfall24h) * 0.72)).toFixed(2));
  }

  // Multi-depth soil moisture
  const sm0_1 = current.soil_moisture_0_to_1cm !== undefined ? Number(current.soil_moisture_0_to_1cm) : null;
  const sm1_3 = current.soil_moisture_1_to_3cm !== undefined ? Number(current.soil_moisture_1_to_3cm) : null;
  const sm3_9 = current.soil_moisture_3_to_9cm !== undefined ? Number(current.soil_moisture_3_to_9cm) : null;
  const sm9_27 = current.soil_moisture_9_to_27cm !== undefined ? Number(current.soil_moisture_9_to_27cm) : null;
  const rootZoneMoisture = (sm0_1 !== null && sm1_3 !== null && sm3_9 !== null && sm9_27 !== null) 
    ? Number((sm0_1 * 0.15 + sm1_3 * 0.25 + sm3_9 * 0.35 + sm9_27 * 0.25).toFixed(3)) 
    : null;

  const evapotranspiration72h = Array.isArray(daily.et0_fao_evapotranspiration)
    ? Number(daily.et0_fao_evapotranspiration.slice(-3).reduce((a, b) => a + Number(b || 0), 0).toFixed(2))
    : null;

  const elevation =
    elevationResult.status === "fulfilled" && Array.isArray(elevationResult.value?.elevation)
      ? Number(elevationResult.value.elevation[0])
      : null;

  const floodDaily =
    floodResult.status === "fulfilled" ? floodResult.value?.daily || {} : {};
  const dischargeNow = floodDaily.river_discharge?.[0] !== undefined ? Number(floodDaily.river_discharge[0]) : null;
  const dischargeMean = floodDaily.river_discharge_mean?.[0] !== undefined ? Number(floodDaily.river_discharge_mean[0]) : null;
  const dischargeMax = floodDaily.river_discharge_max?.[0] !== undefined ? Number(floodDaily.river_discharge_max[0]) : null;

  const result = {
    current: {
      rainfall: rainfall1h,
      temperature: current.temperature_2m !== undefined ? Number(current.temperature_2m) : null,
      humidity: current.relative_humidity_2m !== undefined ? Number(current.relative_humidity_2m) : null,
      pressure: current.surface_pressure !== undefined ? Number(current.surface_pressure) : null,
      wind: current.wind_speed_10m !== undefined ? Number(current.wind_speed_10m) : null,
      soilMoisture: sm0_1,
      soilMoisture0_1: sm0_1,
      soilMoisture1_3: sm1_3,
      soilMoisture3_9: sm3_9,
      soilMoisture9_27: sm9_27,
      rootZoneSoilMoisture: rootZoneMoisture
    },
    rainfall: {
      h1: rainfall1h,
      h3: rainfall3h,
      h6: rainfall6h,
      h12: rainfall12h,
      h24: rainfall24h,
      h72: rainfall72h,
      forecast1h,
      forecast3h,
      forecast6h,
      forecast12h,
      forecast24h,
      forecast72h,
      dailySums,
      antecedentPrecipitationIndex,
      evapotranspiration72h
    },
    elevation,
    flood: {
      dischargeNow,
      dischargeMean,
      dischargeMax,
      available: floodResult.status === "fulfilled"
    },
    raw: {
      forecast,
      elevation: elevationResult.status === "fulfilled" ? elevationResult.value : null,
      flood: floodResult.status === "fulfilled" ? floodResult.value : null
    }
  };

  weatherCache.set(cacheKey, { timestamp: Date.now(), data: result });
  return result;
}

export async function getWeather(latitude, longitude) {
  const live = await getLiveIntelligenceInputs(latitude, longitude);
  return {
    current: {
      rainfall: live.current.rainfall,
      temperature: live.current.temperature,
      humidity: live.current.humidity,
      pressure: live.current.pressure,
      wind: live.current.wind
    },
    forecast: {
      rainfall: live.rainfall.forecast72h,
      dailyRainfall: live.rainfall.dailySums,
      confidence: null,
      nwpSpread: null
    },
    raw: live.raw.forecast
  };
}
