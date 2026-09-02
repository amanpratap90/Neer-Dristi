import express from "express";
import { reverseGeocode, searchLocations } from "../services/geocoding.service.js";
import { getWeather } from "../services/weather.service.js";

const router = express.Router();

router.get("/search", async (req, res, next) => {
  try {
    const query = String(req.query.q || req.query.query || "").trim();

    if (query.length < 2) {
      return res.json({
        status: "success",
        query,
        results: []
      });
    }

    const results = await searchLocations(query);

    res.json({
      status: "success",
      query,
      results
    });
  } catch (error) {
    console.error("LOCATION SEARCH ERROR:", error);
    res.status(502).json({
      detail: error.message || "Location search failed."
    });
  }
});

router.get("/", async (req, res, next) => {
  if (req.query.q || req.query.query) {
    return router.handle(
      Object.assign(req, { url: `/search?${req.url.split("?")[1] || ""}` }),
      res,
      next
    );
  }

  res.json({
    service: "ChetakAI Location Service",
    status: "online"
  });
});

router.post("/", async (req, res) => {
  try {
    const latitude = Number(req.body?.latitude);
    const longitude = Number(req.body?.longitude);

    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      return res.status(400).json({
        detail: "Valid latitude and longitude are required."
      });
    }

    if (latitude < -90 || latitude > 90) {
      return res.status(400).json({
        detail: "Latitude must be between -90 and 90."
      });
    }

    if (longitude < -180 || longitude > 180) {
      return res.status(400).json({
        detail: "Longitude must be between -180 and 180."
      });
    }

    let location = null;
    let weather = null;

    try {
      location = await reverseGeocode(latitude, longitude);
    } catch (locErr) {
      console.warn("Reverse geocode warning:", locErr.message);
    }

    try {
      weather = await getWeather(latitude, longitude);
    } catch (wxErr) {
      console.warn("Weather fetch warning:", wxErr.message);
    }

    res.json({
      status: "success",
      generated_at: new Date().toISOString(),

      location: {
        latitude,
        longitude,
        basin: null,
        basin_id: null,
        basin_name: null,

        administrative_area:
          location?.reverseGeocode?.state || null,

        district:
          location?.reverseGeocode?.district || null,

        city:
          location?.reverseGeocode?.city || null,

        display_name:
          location?.displayName || null
      },

      current_weather:
        weather?.current || {},

      forecast: {
        rainfall:
          weather?.forecast?.rainfall ?? null,

        nwp_spread:
          weather?.forecast?.nwpSpread ?? null,

        confidence:
          weather?.forecast?.confidence ?? null,

        daily_rainfall:
          weather?.forecast?.dailyRainfall ?? null
      }
    });
  } catch (error) {
    console.error("LOCATION ERROR:", error);

    res.status(502).json({
      detail:
        error.message ||
        "Location analysis failed."
    });
  }
});

export default router;