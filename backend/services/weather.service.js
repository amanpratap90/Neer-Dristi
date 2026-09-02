const FORECAST_URL = "https://api.open-meteo.com/v1/forecast";
const ELEVATION_URL = "https://api.open-meteo.com/v1/elevation";
const FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood";

async function fetchJson(url, timeoutMs = 12000) {
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
      "soil_moisture_0_to_1cm"
    ].join(",")
  );
  forecastUrl.searchParams.set(
    "hourly",
    ["precipitation", "rain", "temperature_2m", "relative_humidity_2m"].join(",")
  );
  forecastUrl.searchParams.set(
    "daily",
    ["precipitation_sum", "rain_sum", "temperature_2m_max", "temperature_2m_min"].join(",")
  );
  forecastUrl.searchParams.set("past_days", "3");
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

  const elevation =
    elevationResult.status === "fulfilled"
      ? Number(elevationResult.value?.elevation?.[0] ?? 50)
      : 50;

  const floodDaily =
    floodResult.status === "fulfilled" ? floodResult.value?.daily || {} : {};
  const dischargeNow = Number(floodDaily.river_discharge?.[0] ?? 0);
  const dischargeMean = Number(floodDaily.river_discharge_mean?.[0] ?? dischargeNow);
  const dischargeMax = Number(floodDaily.river_discharge_max?.[0] ?? dischargeNow);

  return {
    current: {
      rainfall: rainfall1h,
      temperature: Number(current.temperature_2m ?? 28),
      humidity: Number(current.relative_humidity_2m ?? 70),
      pressure: Number(current.surface_pressure ?? 1010),
      wind: Number(current.wind_speed_10m ?? 8),
      soilMoisture: Number(current.soil_moisture_0_to_1cm ?? 0.3)
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
      dailySums
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
      confidence: 86,
      nwpSpread: null
    },
    raw: live.raw.forecast
  };
}
