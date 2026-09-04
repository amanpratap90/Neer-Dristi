/**
 * Central Water Commission (CWC) River Water Level Telemetry Adapter
 * Connects to official National Water Informatics Centre (NWIC) / National Water Data Portal (NWDP)
 * CWC River Water Level (Telemetry - Hourly) API.
 *
 * OFFICIAL DATASET:
 * - Title: "River Water Level (Telemetry - Hourly), Central Water Commission (CWC)"
 * - Package ID: 68600163-c5a0-4327-aa1a-fa7157b86cce
 * - Portal: https://nwdp.nwic.gov.in
 *
 * ARCHITECTURAL CONSTRAINTS:
 * 1. Do NOT use Open-Meteo Flood API as CWC data.
 * 2. GloFAS modelled discharge must remain separate and never converted to river stage.
 * 3. Never fabricate or hardcode live river stage values.
 * 4. Support CWC statuses: AVAILABLE, UNAVAILABLE, STALE, ERROR.
 * 5. If telemetry API is unreachable, status = "UNAVAILABLE" while station matching still works.
 */

export const CWC_STATIONS = [
  {
    id: "CWC_007-MGD4PTN",
    name: "Khagaria",
    river: "Burhi Gandak",
    state: "Bihar",
    latitude: 25.501111,
    longitude: 86.480556,
    warning_level: 35.58,
    danger_level: 36.58,
    extreme_level: 39.22,
    warningLevel: 35.58,
    dangerLevel: 36.58,
    highestFloodLevel: 39.22
  },
  {
    id: "CWC_027-MGD5PTN",
    name: "Maner",
    river: "Sone River",
    state: "Bihar",
    latitude: 25.650000,
    longitude: 84.828611,
    warning_level: 51.00,
    danger_level: 52.00,
    extreme_level: 53.79,
    warningLevel: 51.00,
    dangerLevel: 52.00,
    highestFloodLevel: 53.79
  },
  {
    id: "CWC_006-MGD3VNS",
    name: "Varanasi",
    river: "Ganga",
    state: "Uttar Pradesh",
    latitude: 25.323611,
    longitude: 83.037500,
    warning_level: 70.262,
    danger_level: 71.262,
    extreme_level: 73.901,
    warningLevel: 70.262,
    dangerLevel: 71.262,
    highestFloodLevel: 73.901
  },
  {
    id: "025-MDGBGP",
    name: "Guwahati D.C. Court",
    river: "Brahmaputra",
    state: "Assam",
    latitude: 26.194722,
    longitude: 91.743056,
    warning_level: 48.68,
    danger_level: 49.68,
    extreme_level: 51.46,
    warningLevel: 48.68,
    dangerLevel: 49.68,
    highestFloodLevel: 51.46
  }
];

export const OFFICIAL_NWIC_DATASET = "River Water Level (Telemetry - Hourly), Central Water Commission (CWC)";
export const OFFICIAL_NWIC_DATA_SOURCE = "NWIC / CWC River Water Level (Telemetry - Hourly)";

// Telemetry older than 24 hours is treated as STALE
const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000;

/**
 * Calculates geographical distance between two points in km (Haversine formula).
 */
export function calculateDistanceKm(lat1, lon1, lat2, lon2) {
  const R = 6371; // Earth's radius in km
  const dLat = (lat2 - lat1) * (Math.PI / 180);
  const dLon = (lon2 - lon1) * (Math.PI / 180);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * (Math.PI / 180)) *
      Math.cos(lat2 * (Math.PI / 180)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Finds the nearest CWC gauge station within a configurable matching radius.
 */
export function findNearestCWCStation(lat, lon, maxDistanceKm = 50) {
  let nearest = null;
  let minDistance = Infinity;

  for (const station of CWC_STATIONS) {
    const dist = calculateDistanceKm(Number(lat), Number(lon), station.latitude, station.longitude);
    if (dist < minDistance) {
      minDistance = dist;
      nearest = station;
    }
  }

  if (nearest && minDistance <= maxDistanceKm) {
    const distRounded = Number(minDistance.toFixed(1));
    return {
      ...nearest,
      distance_km: distRounded,
      distanceKm: distRounded
    };
  }

  return null;
}

export const findNearestCWCGauge = findNearestCWCStation;

/**
 * Deterministically classifies river condition against official thresholds.
 *
 * @param {number|null} stage - Observed river water level in metres
 * @param {object} thresholds - { warning_level, danger_level, extreme_level }
 * @returns {string} EXTREME | ABOVE_DANGER | ABOVE_WARNING | BELOW_WARNING | UNKNOWN
 */
export function classifyCWCStatus(stage, thresholds) {
  if (stage === null || stage === undefined || !Number.isFinite(Number(stage))) {
    return "UNAVAILABLE";
  }
  if (!thresholds) return "UNAVAILABLE";

  const val = Number(stage);
  const extreme = thresholds.extreme_level ?? thresholds.highestFloodLevel;
  const danger = thresholds.danger_level ?? thresholds.dangerLevel;
  const warning = thresholds.warning_level ?? thresholds.warningLevel;

  if (extreme !== undefined && val >= extreme) return "EXTREME";
  if (danger !== undefined && val >= danger) return "ABOVE_DANGER";
  if (warning !== undefined && val >= warning) return "ABOVE_WARNING";
  return "BELOW_WARNING";
}

/**
 * Fetches water level telemetry for a station using official NWIC / NWDP APIs.
 * Supports statuses: AVAILABLE, UNAVAILABLE, STALE, ERROR.
 *
 * @param {string} stationId - CWC Station ID
 * @param {string} [stationName] - Station name
 * @returns {Promise<object>}
 */
export async function fetchCWCWaterLevel(stationId, stationName = "") {
  console.log(`[CWC] Request started for station ${stationName || stationId}`);

  const apiUrl = process.env.CWC_API_URL || "https://nwdp.nwic.gov.in/api/3/action/datastore_search";
  const apiKey = process.env.CWC_API_KEY || "";

  // Strategy 1: Official NWIC CKAN datastore API
  if (apiUrl) {
    try {
      const url = new URL(apiUrl);
      if (stationName) {
        url.searchParams.set("q", stationName);
      } else {
        url.searchParams.set("q", stationId);
      }
      url.searchParams.set("limit", "5");

      const headers = {
        "User-Agent": "ChetakAI-FloodIntelligence/2.2",
        "Accept": "application/json"
      };
      if (apiKey) {
        headers["Authorization"] = apiKey;
        headers["api-key"] = apiKey;
      }

      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 4500);

      const response = await fetch(url.toString(), {
        signal: controller.signal,
        headers
      });

      clearTimeout(timer);

      if (response.ok) {
        const json = await response.json();
        const records = json?.result?.records || [];

        const match = records.find(r => {
          const st = (r.Station || r.station || "").toLowerCase();
          const q = (stationName || stationId).toLowerCase();
          return st.includes(q) || q.includes(st);
        });

        if (match) {
          const rawStage = match["River Water Level Telemetry Hourly (meter)"] ?? match.water_level ?? match.stage;
          const stageNum = rawStage !== null && rawStage !== undefined ? parseFloat(rawStage) : null;
          const rawTime = match["Data Acquisition Time"] ?? match.timestamp ?? match.observed_at;

          if (stageNum !== null && Number.isFinite(stageNum) && stageNum > 0) {
            const observedDate = rawTime ? new Date(rawTime) : new Date();
            const isStale = (Date.now() - observedDate.getTime()) > STALE_THRESHOLD_MS;
            const status = isStale ? "STALE" : "AVAILABLE";

            console.log(`[CWC] Telemetry received: station=${stationName} stage=${stageNum}m status=${status}`);

            return {
              status,
              water_level_m: stageNum,
              updated_at: observedDate.toISOString(),
              reason: isStale ? "CWC telemetry available but stale (>24h old)" : null,
              data_source: OFFICIAL_NWIC_DATA_SOURCE
            };
          }
        }
      } else {
        console.warn(`[CWC] NWIC endpoint returned HTTP ${response.status}`);
      }
    } catch (err) {
      if (err.name === "AbortError") {
        console.warn(`[CWC] API timeout for station ${stationName || stationId}`);
      } else {
        console.warn(`[CWC] API error: ${err.message}`);
      }
    }
  }

  // Strategy 2: Official CWC Flood Forecast System (FFS) endpoint
  try {
    const ffsUrl = `https://ffs.india-water.gov.in/api/station/${encodeURIComponent(stationId)}/latest`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 3500);

    const response = await fetch(ffsUrl, {
      signal: controller.signal,
      headers: {
        "User-Agent": "ChetakAI-FloodIntelligence/2.2",
        "Accept": "application/json"
      }
    });

    clearTimeout(timer);

    if (response.ok) {
      const data = await response.json();
      const rawStage = data?.current_level ?? data?.water_level ?? data?.stage;
      const stageNum = rawStage !== null && rawStage !== undefined ? parseFloat(rawStage) : null;
      const rawTime = data?.observed_at ?? data?.timestamp;

      if (stageNum !== null && Number.isFinite(stageNum) && stageNum > 0) {
        const observedDate = rawTime ? new Date(rawTime) : new Date();
        const isStale = (Date.now() - observedDate.getTime()) > STALE_THRESHOLD_MS;
        const status = isStale ? "STALE" : "AVAILABLE";

        console.log(`[CWC] FFS telemetry received: station=${stationName} stage=${stageNum}m status=${status}`);

        return {
          status,
          water_level_m: stageNum,
          updated_at: observedDate.toISOString(),
          reason: isStale ? "CWC telemetry available but stale (>24h old)" : null,
          data_source: OFFICIAL_NWIC_DATA_SOURCE
        };
      }
    }
  } catch (err) {
    // Both endpoints failed
  }

  console.log(`[CWC] Telemetry unavailable for station ${stationName || stationId}`);

  // Strict Data Honesty: Never fabricate live telemetry
  return {
    status: "UNAVAILABLE",
    water_level_m: null,
    updated_at: null,
    reason: "Live CWC telemetry is currently unavailable.",
    data_source: OFFICIAL_NWIC_DATA_SOURCE
  };
}

/**
 * Main CWC observation resolver.
 * Evaluates nearest station, fetches live telemetry, and classifies condition.
 *
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @param {number} [maxDistanceKm=50] - Matching radius
 * @returns {Promise<object>}
 */
export async function getCWCObservation(lat, lon, maxDistanceKm = 50) {
  const station = findNearestCWCStation(lat, lon, maxDistanceKm);

  if (!station) {
    console.log(`[CWC] No station found within ${maxDistanceKm}km of ${lat}, ${lon}`);
    return {
      source: "CWC",
      status: "UNAVAILABLE",
      reason: `No official CWC station within ${maxDistanceKm}km radius`,
      station: null,
      station_id: null,
      river: null,
      distance_km: null,
      water_level_m: null,
      warning_level_m: null,
      danger_level_m: null,
      extreme_level_m: null,
      condition: "UNKNOWN",
      updated_at: null,
      data_source: OFFICIAL_NWIC_DATA_SOURCE,

      // Compatibility fields
      gaugeMatched: false,
      observed_stage: null,
      telemetry_status: "UNAVAILABLE"
    };
  }

  console.log(`[CWC] Station found: ${station.name} (${station.id}) on ${station.river} at ${station.distance_km}km`);

  const telemetry = await fetchCWCWaterLevel(station.id, station.name);

  const condition = classifyCWCStatus(telemetry.water_level_m, {
    warning_level: station.warning_level,
    danger_level: station.danger_level,
    extreme_level: station.extreme_level
  });

  return {
    source: "CWC",
    status: telemetry.status, // AVAILABLE | UNAVAILABLE | STALE | ERROR
    station: `${station.name} (${station.river})`,
    station_name: station.name,
    station_id: station.id,
    river: station.river,
    distance_km: station.distance_km,
    water_level_m: telemetry.water_level_m,
    warning_level_m: station.warning_level,
    danger_level_m: station.danger_level,
    extreme_level_m: station.extreme_level,
    condition, // ABOVE_EXTREME | ABOVE_DANGER | ABOVE_WARNING | BELOW_WARNING | UNKNOWN
    updated_at: telemetry.updated_at,
    reason: telemetry.reason,
    data_source: telemetry.data_source,

    // Compatibility fields for legacy consumers
    gaugeMatched: true,
    gaugeDistanceKm: station.distance_km,
    gaugeId: station.id,
    gaugeName: station.name,
    observed_stage: telemetry.water_level_m,
    observed_at: telemetry.updated_at,
    warning_level: station.warning_level,
    danger_level: station.danger_level,
    extreme_level: station.extreme_level,
    telemetry_status: telemetry.status,
    failure_reason: telemetry.reason,
    cwcRiverStageM: telemetry.water_level_m,
    cwcWarningLevelM: station.warning_level,
    cwcDangerLevelM: station.danger_level,
    cwcHflM: station.extreme_level,
    cwcStatus: condition,
    cwcAvailability: telemetry.status,
    gauge: station
  };
}

export const getLiveCWCStage = getCWCObservation;
