import express from "express";
import cors from "cors";
import dotenv from "dotenv";

import locationRoutes from "./routes/location.routes.js";
import intelligenceRoutes from "./routes/intelligence.routes.js";

dotenv.config();

const app = express();

const PORT = Number(process.env.PORT || 8000);

const allowedOrigins = (
  process.env.FRONTEND_ORIGIN || ""
)
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

app.use(
  cors({
    origin(origin, callback) {
      if (!origin) {
        return callback(null, true);
      }

      if (
        allowedOrigins.length === 0 ||
        allowedOrigins.includes(origin)
      ) {
        return callback(null, true);
      }

      return callback(
        new Error("CORS origin not allowed.")
      );
    },
    credentials: false,
  })
);

app.use(express.json({ limit: "1mb" }));

app.get("/", (req, res) => {
  res.json({
    service: "ChetakAI Flood Intelligence API",
    status: "online",
    version: "1.0.0",
  });
});

app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "chetakai-backend",
    timestamp: new Date().toISOString(),
  });
});

app.use("/api/v1/location", locationRoutes);
app.use(
  "/api/v1/intelligence",
  intelligenceRoutes
);

app.use((req, res) => {
  res.status(404).json({
    detail: `Route not found: ${req.method} ${req.originalUrl}`,
  });
});

app.use((err, req, res, next) => {
  console.error("BACKEND ERROR:", err);

  res.status(err.statusCode || err.status || 500).json({
    detail:
      err.message || "Internal server error",
  });
});

app.listen(PORT, "0.0.0.0", () => {
  console.log("");
  console.log("==============================================");
  console.log("CHETAKAI BACKEND");
  console.log("==============================================");
  console.log(
    `Server: http://127.0.0.1:${PORT}`
  );
  console.log(
    `Health: http://127.0.0.1:${PORT}/health`
  );
  console.log(
    "Search:   GET  /api/v1/location/search?q=:query"
  );
  console.log(
    "Location: POST /api/v1/location"
  );
  console.log(
    "Analyze:  POST /api/v1/intelligence/analyze"
  );
  console.log("==============================================");
  console.log("");
});