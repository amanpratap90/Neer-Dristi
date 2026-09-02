import {
  searchLocations,
} from "../../services/geocoding.service.js";

export async function search(req, res, next) {
  try {
    const query =
      String(req.query.q || req.query.query || "").trim();

    if (query.length < 2) {
      return res.json({
        status: "success",
        query,
        results: [],
      });
    }

    const results =
      await searchLocations(query);

    res.json({
      status: "success",
      query,
      results,
    });
  } catch (error) {
    next(error);
  }
}