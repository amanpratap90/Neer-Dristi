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
      language = "en"
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
      language: selectedLanguage
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