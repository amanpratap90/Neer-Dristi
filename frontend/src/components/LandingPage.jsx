import React, { useEffect, useRef, useState } from "react";
import { analyzeLocation, searchLocation } from "../api";

export default function LandingPage({ onResult }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [locating, setLocating] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  const searchTimer = useRef(null);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    clearTimeout(searchTimer.current);

    searchTimer.current = setTimeout(async () => {
      try {
        setSearching(true);
        const data = await searchLocation(query);
        setResults(data.results || []);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 450);

    return () => clearTimeout(searchTimer.current);
  }, [query]);

  async function analyze(latitude, longitude) {
    try {
      setError("");
      setAnalyzing(true);

      const result = await analyzeLocation(
        Number(latitude),
        Number(longitude)
      );

      onResult(result);
    } catch (err) {
      setError(
        err?.message ||
        "Unable to generate flood intelligence."
      );
    } finally {
      setAnalyzing(false);
    }
  }

  function useCurrentLocation() {
    setError("");

    if (!navigator.geolocation) {
      setError(
        "Your browser does not support location services."
      );
      return;
    }

    setLocating(true);

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          await analyze(
            position.coords.latitude,
            position.coords.longitude
          );
        } finally {
          setLocating(false);
        }
      },
      (err) => {
        setLocating(false);

        if (err.code === 1) {
          setError(
            "Location access was denied. You can allow it in browser settings or enter a location manually."
          );
        } else if (err.code === 2) {
          setError(
            "Your location could not be determined."
          );
        } else if (err.code === 3) {
          setError(
            "Location request timed out. Please try again."
          );
        } else {
          setError(
            "Unable to determine your current location."
          );
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 30000,
      }
    );
  }

  async function selectLocation(place) {
    setSelected(place);
    setQuery(place.name || place.display_name || place.displayName || "");
    setResults([]);

    await analyze(place.latitude, place.longitude);
  }

  return (
    <div className="landing-page">
      <header className="site-header">
        <div className="brand">
          <div className="brand-symbol">C</div>

          <div className="brand-copy">
            <strong>ChetakAI</strong>
            <span>Flood Intelligence</span>
          </div>
        </div>

        <div className="header-status">
          <span className="status-dot" />
          LIVE SYSTEM
        </div>
      </header>

      <main className="landing-content">
        <section className="hero-grid">

          <div className="hero-content">

            <div className="eyebrow">
              LOCAL FLOOD INTELLIGENCE
            </div>

            <h1>
              Know the flood risk
              <br />
              <em>before it reaches you.</em>
            </h1>

            <p className="hero-lead">
              ChetakAI combines hydrological data,
              satellite-informed moisture, terrain slope,
              forecast rainfall and physical basin intelligence
              to evaluate flood exposure for your exact
              location.
            </p>

            <div className="location-card">

              <div className="location-card-header">
                <strong>Where are you checking?</strong>
                <span>
                  Search a town, city, district or village
                  in India.
                </span>
              </div>

              <div className="search-field">

                <span className="search-symbol">⌕</span>

                <input
                  type="text"
                  placeholder="Search city, district, village..."
                  value={query}
                  onChange={(e) =>
                    setQuery(e.target.value)
                  }
                  disabled={analyzing}
                />

                {searching && (
                  <div className="search-spinner" />
                )}

                {results.length > 0 && (
                  <div className="search-results">

                    {searching && (
                      <div className="search-loading">
                        Searching locations...
                      </div>
                    )}

                    {results.map((place) => (
                      <button
                        key={place.placeId || place.id || place.name}
                        className="search-result"
                        onClick={() =>
                          selectLocation(place)
                        }
                      >
                        <span className="result-pin">
                          ◉
                        </span>

                        <span>
                          <strong>
                            {place.address?.city ||
                              place.name?.split(",")[0] ||
                              place.name}
                          </strong>

                          <small>
                            {place.name ||
                              place.display_name ||
                              place.displayName}
                          </small>
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="location-divider">
                <span>OR</span>
              </div>

              <button
                className="current-location-button"
                onClick={useCurrentLocation}
                disabled={locating || analyzing}
              >
                <span className="current-location-icon">
                  ⌖
                </span>

                <span>
                  {locating
                    ? "Finding your location..."
                    : analyzing
                    ? "Analyzing flood risk..."
                    : "Use my current location"}
                </span>

                {!locating && !analyzing && (
                  <span className="button-arrow">
                    →
                  </span>
                )}
              </button>

              {selected && !analyzing && (
                <div className="selected-location">
                  <span>✓</span>
                  {selected.display_name}
                </div>
              )}

              {error && (
                <div className="location-error">
                  {error}
                </div>
              )}

              <p className="privacy-text">
                Your location is used only to generate
                your local flood assessment.
              </p>

            </div>
          </div>

          <div className="hero-visual">

            <div className="visual-card">

              <div className="visual-top">
                <span>CHETAKAI INTELLIGENCE</span>

                <span className="visual-live">
                  ● LIVE
                </span>
              </div>

              <div className="abstract-map">

                <div className="map-grid" />

                <svg
                  viewBox="0 0 600 520"
                  preserveAspectRatio="none"
                >
                  <path
                    d="M20 150 C120 70 180 210 250 150 S380 80 470 150 S550 180 610 100"
                  />

                  <path
                    d="M-20 330 C90 250 130 390 240 320 S390 260 470 350 S550 400 620 320"
                  />

                  <path
                    d="M330 -20 C260 80 390 130 330 230 S260 350 340 540"
                  />

                  <path
                    d="M80 500 C150 400 230 450 300 390 S430 390 520 470"
                  />
                </svg>

                <div className="map-ring ring-one" />
                <div className="map-ring ring-two" />

                <div className="map-center">
                  <div className="map-center-dot" />
                </div>

                <div className="map-label-card">
                  <span>SELECTED AREA</span>
                  <strong>
                    Flood intelligence
                  </strong>
                  <small>
                    Weather · Terrain · Water · Exposure
                  </small>
                </div>

              </div>

              <div className="visual-footer">

                <div>
                  <span>DATA LAYERS</span>
                  <strong>08</strong>
                </div>

                <div>
                  <span>LOCATION</span>
                  <strong>READY</strong>
                </div>

                <div>
                  <span>ENGINE</span>
                  <strong>AI</strong>
                </div>

              </div>

            </div>
          </div>

        </section>

        <section className="capability-section">

          <div className="capability-intro">
            <span>WHY CHETAKAI</span>
            <h2>
              One location.
              <br />
              Multiple flood signals.
            </h2>
          </div>

          <div className="capability-grid">

            <Capability
              number="01"
              title="Weather"
              text="Current rainfall and atmospheric conditions."
            />

            <Capability
              number="02"
              title="Terrain"
              text="Elevation, slope, drainage and river proximity."
            />

            <Capability
              number="03"
              title="Hydrology"
              text="Water levels, trends and hydrological loading."
            />

            <Capability
              number="04"
              title="Exposure"
              text="Population, infrastructure and surface vulnerability."
            />

          </div>
        </section>

      </main>

      <footer className="site-footer">
        <span>CHETAKAI</span>
        <span>
          Grounded flood intelligence for local communities
        </span>
        <span>V1 · INDIA</span>
      </footer>
    </div>
  );
}

function Capability({ number, title, text }) {
  return (
    <div className="capability-card">
      <span>{number}</span>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}