import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";
import { generateFloodIntelligence } from "../../services/chetakai.service.js";
import { chatWithCopilot } from "../../services/llm.service.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export async function analyze(req, res, next) {
  try {
    const {
      latitude,
      longitude,
      strict = false,
      lang = "en",
      language = "en",
      demoScenario = null
    } = req.body;

    if (latitude === undefined || longitude === undefined) {
      return res.status(400).json({
        detail: "latitude and longitude are required.",
      });
    }

    const lat = Number(latitude);
    const lon = Number(longitude);

    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      return res.status(400).json({
        detail: "latitude and longitude must be valid numbers.",
      });
    }

    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      return res.status(400).json({
        detail: "Coordinates are outside valid geographic bounds.",
      });
    }

    const selectedLanguage = language || lang || "en";

    const result = await generateFloodIntelligence({
      latitude: lat,
      longitude: lon,
      language: selectedLanguage,
      demoScenario
    });

    res.json(result);
  } catch (error) {
    next(error);
  }
}

export async function debugAnalyze(req, res, next) {
  try {
    const { lat, lon, language = "en", demoScenario = null } = req.query;

    if (lat === undefined || lon === undefined) {
      return res.status(400).json({ detail: "lat and lon query params required." });
    }

    const latitude = Number(lat);
    const longitude = Number(lon);

    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      return res.status(400).json({ detail: "lat and lon must be valid numbers." });
    }

    if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
      return res.status(400).json({ detail: "Coordinates are outside valid geographic bounds." });
    }

    const result = await generateFloodIntelligence({
      latitude,
      longitude,
      language,
      demoScenario
    });

    res.json(result);
  } catch (error) {
    next(error);
  }
}


export async function chat(req, res, next) {
  try {
    const {
      message,
      telemetry,
      language = "en",
      history = []
    } = req.body;

    if (!message || typeof message !== "string") {
      return res.status(400).json({
        detail: "A message string is required."
      });
    }

    const response = await chatWithCopilot({
      message,
      telemetry: telemetry || {},
      language,
      history
    });

    res.json(response);
  } catch (error) {
    next(error);
  }
}

export async function getGlossary(req, res, next) {
  try {
    const glossaryPath = path.join(__dirname, "..", "..", "data", "glossary.json");
    const data = await fs.readFile(glossaryPath, "utf-8");
    res.json(JSON.parse(data));
  } catch (error) {
    next(error);
  }
}