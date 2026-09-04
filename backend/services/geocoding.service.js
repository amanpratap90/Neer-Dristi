const NOMINATIM_URL = "https://nominatim.openstreetmap.org";

const headers = {
  "User-Agent": "ChetakAI-Flood-Intelligence/1.0 (contact: admin@chetakai.ai)"
};

const geocodeCache = new Map();

async function request(url, timeoutMs = 4000) {
  const cacheKey = url.toString();
  if (geocodeCache.has(cacheKey)) {
    return geocodeCache.get(cacheKey);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      headers,
      signal: controller.signal
    });

    if (!response.ok) {
      throw new Error(`Geocoding service returned ${response.status}`);
    }

    const data = await response.json();
    geocodeCache.set(cacheKey, data);
    return data;
  } finally {
    clearTimeout(timer);
  }
}

export async function searchLocations(query) {
  try {
    const geoUrl = new URL("https://geocoding-api.open-meteo.com/v1/search");
    geoUrl.searchParams.set("name", query);
    geoUrl.searchParams.set("count", "6");
    geoUrl.searchParams.set("language", "en");
    geoUrl.searchParams.set("countryCode", "IN");
    const geo = await request(geoUrl);
    if (Array.isArray(geo.results) && geo.results.length > 0) {
      return geo.results.map((item) => ({
        placeId: item.id,
        name: [item.name, item.admin1, item.country].filter(Boolean).join(", "),
        latitude: Number(item.latitude),
        longitude: Number(item.longitude),
        type: item.feature_code,
        address: {
          city: item.name || null,
          district: item.admin2 || item.admin1 || null,
          state: item.admin1 || null,
          country: item.country || null
        }
      }));
    }
  } catch {
    // Fall through to Nominatim.
  }

  const url = new URL(`${NOMINATIM_URL}/search`);

  url.searchParams.set("q", query);
  url.searchParams.set("format", "jsonv2");
  url.searchParams.set("addressdetails", "1");
  url.searchParams.set("limit", "6");
  url.searchParams.set("countrycodes", "in");

  const data = await request(url);

  return data.map((item) => ({
    placeId: item.place_id,
    name: item.display_name,
    latitude: Number(item.lat),
    longitude: Number(item.lon),
    type: item.type,
    address: {
      city:
        item.address?.city ||
        item.address?.town ||
        item.address?.village ||
        null,
      district:
        item.address?.county ||
        item.address?.state_district ||
        null,
      state: item.address?.state || null,
      country: item.address?.country || null
    }
  }));
}

export async function reverseGeocode(latitude, longitude) {
  const url = new URL(`${NOMINATIM_URL}/reverse`);

  url.searchParams.set("lat", latitude);
  url.searchParams.set("lon", longitude);
  url.searchParams.set("format", "jsonv2");
  url.searchParams.set("addressdetails", "1");

  const data = await request(url);

  return {
    displayName: data.display_name || null,
    reverseGeocode: {
      city:
        data.address?.city ||
        data.address?.town ||
        data.address?.village ||
        data.address?.municipality ||
        null,
      district:
        data.address?.county ||
        data.address?.state_district ||
        data.address?.district ||
        null,
      sub_district:
        data.address?.suburb ||
        data.address?.county ||
        data.address?.city_district ||
        null,
      block:
        data.address?.suburb ||
        data.address?.village ||
        data.address?.town ||
        null,
      state: data.address?.state || null,
      country: data.address?.country || null,
      postcode: data.address?.postcode || null
    }
  };
}