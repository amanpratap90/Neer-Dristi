import React, { useEffect, useState } from "react";
import {
  IconSearch,
  IconLocation,
  IconGlobe,
  IconShield,
  IconAlertTriangle,
  IconCheck,
  IconLayers,
  IconCrosshair
} from "./components/Icons";
import Dashboard from "./components/Dashboard";
import VoiceAgent from "./components/VoiceAgent";
import MetricExplainerModal from "./components/MetricExplainerModal";
import { languages, translations, presetLocations } from "./i18n/translations";

const RAW_API_BASE = import.meta.env.VITE_API_BASE_URL || "";
const API_BASE = RAW_API_BASE
  .replace(/\/+$/, "")
  .replace(/\/api\/v1\/intelligence\/analyze$/, "")
  .replace(/\/api\/v1\/location$/, "");

export default function App() {
  const [language, setLanguage] = useState("en");
  const [query, setQuery] = useState("");
  const [latInput, setLatInput] = useState("");
  const [lonInput, setLonInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState("");
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [explainingMetric, setExplainingMetric] = useState(null);
  const [gpsLoading, setGpsLoading] = useState(false);
  const [showCoords, setShowCoords] = useState(true);
  const [locationHint, setLocationHint] = useState("");

  const t = translations[language] || translations.en;

  // Run analysis for a given coordinate
  const runAnalysis = async (lat, lon, currentLang = language) => {
    setLoading(true);
    setError(null);
    setLoadingStep("Fetching live weather, elevation and river discharge...");

    try {
      setTimeout(() => setLoadingStep("Scoring flood risk from live APIs..."), 500);
      setTimeout(() => setLoadingStep("Building dashboard briefing..."), 1200);

      const res = await fetch(`${API_BASE}/api/v1/intelligence/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          latitude: Number(lat),
          longitude: Number(lon),
          language: currentLang
        })
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned error ${res.status}`);
      }

      const result = await res.json();
      setData(result);
      setLatInput(String(lat));
      setLonInput(String(lon));
      setLocationHint("");
    } catch (err) {
      console.error("Analysis Error:", err);
      setError(err.message || "Failed to analyze flood risk for this coordinate.");
    } finally {
      setLoading(false);
      setLoadingStep("");
    }
  };

  // NO auto-load on mount - user must enter location first

  // When language changes, re-fetch briefing in selected language
  const handleLanguageChange = (newLang) => {
    setLanguage(newLang);
    if (data?.location?.latitude && data?.location?.longitude) {
      runAnalysis(data.location.latitude, data.location.longitude, newLang);
    }
  };

  // Search geocode handler
  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) {
      if (latInput && lonInput) {
        runAnalysis(latInput, lonInput, language);
      }
      return;
    }

    // Check if query is "lat, lon"
    const coordMatch = query.match(/^([-+]?\d*\.?\d+)[,\s]+([-+]?\d*\.?\d+)$/);
    if (coordMatch) {
      runAnalysis(Number(coordMatch[1]), Number(coordMatch[2]), language);
      return;
    }

    setLoading(true);
    setLoadingStep("Geocoding location...");
    try {
      const res = await fetch(`${API_BASE}/api/v1/location/search?q=${encodeURIComponent(query)}`);
      if (res.ok) {
        const results = await res.json();
        const list = Array.isArray(results) ? results : results?.results;
        if (Array.isArray(list) && list.length > 0) {
          const first = list[0];
          runAnalysis(first.latitude, first.longitude, language);
          return;
        }
      }
      // Fallback geocode via OpenStreetMap Nominatim
      const nominatim = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=1`);
      if (nominatim.ok) {
        const nomResults = await nominatim.json();
        if (nomResults && nomResults.length > 0) {
          runAnalysis(Number(nomResults[0].lat), Number(nomResults[0].lon), language);
          return;
        }
      }
      throw new Error(`Could not find "${query}". Try entering Lat & Lon directly.`);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  // GPS Location handler
  const handleGPS = () => {
    if (!navigator.geolocation) {
      setError("Geolocation is not supported by your browser.");
      return;
    }
    setGpsLoading(true);
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude.toFixed(4);
        const lon = pos.coords.longitude.toFixed(4);
        setLatInput(lat);
        setLonInput(lon);
        setQuery(`${lat}, ${lon}`);
        setShowCoords(true);
        setGpsLoading(false);
        setLocationHint(`Location fetched: ${lat}, ${lon}. Click Analyze to start.`);
      },
      (err) => {
        setGpsLoading(false);
        if (err.code === 1) setError("Location access denied. Please allow location or enter manually.");
        else if (err.code === 2) setError("Location unavailable. Enter coordinates manually.");
        else setError("Location request timed out. Try again.");
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 }
    );
  };

  return (
    <div className="app-shell">
      {/* TOP NAVIGATION BAR */}
      <header className="topbar">
        <div className="brand-group">
          <div className="brand-mark">
            <IconShield className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="brand-title">{t.appTitle}</h1>
            <p className="brand-subtitle">{t.appSubtitle}</p>
          </div>
        </div>

        <div className="topbar-controls">
          <div className="live-status-pill">
            <span className="pulse-dot"></span>
            <span className="status-label">{t.liveSystem}</span>
          </div>

          <div className="lang-select-wrap">
            <IconGlobe className="w-4 h-4 text-copper" />
            <select
              className="lang-select"
              value={language}
              onChange={(e) => handleLanguageChange(e.target.value)}
              aria-label="Select Language"
            >
              {languages.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.native} ({lang.name})
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {/* COMPACT SEARCH SECTION */}
      <section className="search-section-compact">
        <div className="search-section-inner">
          {/* Main search row */}
          <form className="search-row-compact" onSubmit={handleSearch}>
            <div className="search-input-group">
              <IconSearch className="w-4 h-4 text-muted" />
              <input
                type="text"
                className="search-input-compact"
                placeholder={t.searchPlaceholder || "Search city, village, district or enter lat, lon..."}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>

            <button
              type="button"
              className="btn-gps"
              onClick={handleGPS}
              disabled={gpsLoading || loading}
              title="Fetch my current GPS location"
            >
              {gpsLoading ? (
                <span className="mini-spinner"></span>
              ) : (
                <IconCrosshair className="w-4 h-4" />
              )}
              <span className="btn-gps-text">Fetch location</span>
            </button>

            <button
              type="button"
              className="btn-toggle-coords"
              onClick={() => setShowCoords(!showCoords)}
              title="Enter coordinates manually"
            >
              <IconLocation className="w-4 h-4" />
            </button>

            <button type="submit" className="btn-analyze" disabled={loading}>
              {loading ? t.analyzing || "Analyzing..." : t.analyzeBtn || "Analyze"}
            </button>
          </form>

          {showCoords && (
            <div className="coord-row-compact">
              <label className="coord-label-compact">Lat</label>
              <input
                type="number"
                step="0.0001"
                className="coord-input-compact"
                placeholder="25.1234"
                value={latInput}
                onChange={(e) => {
                  setLatInput(e.target.value);
                  setLocationHint("");
                }}
              />
              <label className="coord-label-compact">Lon</label>
              <input
                type="number"
                step="0.0001"
                className="coord-input-compact"
                placeholder="86.5678"
                value={lonInput}
                onChange={(e) => {
                  setLonInput(e.target.value);
                  setLocationHint("");
                }}
              />
            </div>
          )}

          {locationHint && <p className="location-hint">{locationHint}</p>}

          {/* Preset basins */}
          <div className="presets-row-compact">
            <span className="presets-label">{t.quickBasins || "Quick"}:</span>
            {presetLocations.map((basin, idx) => {
              const localizedName = basin[language === "hi" ? "hindi" : language === "bn" ? "bengali" : language === "mr" ? "marathi" : language === "te" ? "telugu" : language === "ta" ? "tamil" : "name"] || basin.name;
              const isActive = data?.location?.latitude === basin.lat && data?.location?.longitude === basin.lon;
              return (
                <button
                  key={idx}
                  className={`preset-chip-sm ${isActive ? "active" : ""}`}
                  onClick={() => runAnalysis(basin.lat, basin.lon, language)}
                  disabled={loading}
                >
                  {localizedName}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* MAIN CONTENT */}
      <main className="main-content-area">
        {error && (
          <div className="error-banner animate-fade-in">
            <IconAlertTriangle className="w-6 h-6 text-rose-600 flex-shrink-0" />
            <div>
              <h3 className="error-title">Analysis Error</h3>
              <p className="error-msg">{error}</p>
            </div>
          </div>
        )}

        {loading && (
          <div className="loading-state-card animate-pulse">
            <div className="spinner-wrap">
              <div className="spinner"></div>
            </div>
            <h3 className="loading-title">Analyzing flood intelligence</h3>
            <p className="loading-step-text">{loadingStep || "Calling weather and river APIs..."}</p>
          </div>
        )}

        {!loading && !data && !error && (
          <div className="welcome-card">
            <div className="welcome-icon">
              <IconShield className="w-12 h-12 text-copper" />
            </div>
            <h2 className="welcome-title">ChetakAI Flood Intelligence</h2>
            <p className="welcome-desc">
              Type a place, enter coordinates, or fetch GPS. Then click Analyze.
            </p>
            <div className="welcome-features">
              <div className="welcome-feat"><IconCheck className="w-4 h-4 text-teal" /> Live Weather & Rainfall</div>
              <div className="welcome-feat"><IconCheck className="w-4 h-4 text-teal" /> Terrain & Hydrology</div>
              <div className="welcome-feat"><IconCheck className="w-4 h-4 text-teal" /> Radar & Satellite Data</div>
              <div className="welcome-feat"><IconCheck className="w-4 h-4 text-teal" /> Population & Infrastructure</div>
              <div className="welcome-feat"><IconCheck className="w-4 h-4 text-teal" /> AI Risk Assessment</div>
              <div className="welcome-feat"><IconCheck className="w-4 h-4 text-teal" /> Voice Agent</div>
            </div>
          </div>
        )}

        {!loading && data && (
          <Dashboard
            data={data}
            language={language}
            apiBase={API_BASE}
            onExplain={(metric) => setExplainingMetric(metric)}
          />
        )}
      </main>

      {/* METRIC EXPLAINER MODAL */}
      {explainingMetric && (
        <MetricExplainerModal
          metric={explainingMetric}
          language={language}
          onClose={() => setExplainingMetric(null)}
        />
      )}

      {/* VOICE AGENT FAB */}
      <VoiceAgent
        apiBase={API_BASE}
        telemetry={data}
        language={language}
      />

      {/* FOOTER */}
      <footer className="app-footer">
        <div className="footer-content">
          <p>© 2026 ChetakAI Flood Intelligence • Live weather, elevation and river discharge APIs</p>
          <div className="footer-links">
            <span>Production Grade v2.1</span>
            <span>•</span>
            <span>Deterministic Grounding</span>
            <span>•</span>
            <span>Multilingual Copilot</span>
          </div>
        </div>
      </footer>
    </div>
  );
}