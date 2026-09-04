import React from "react";
import {
  IconShield,
  IconRain,
  IconWaves,
  IconMountain,
  IconLayers,
  IconUsers,
  IconAlertTriangle,
  IconCheck,
  IconHelp,
  IconLocation,
  IconRadar,
  IconEye,
  IconActivity,
  IconBuilding,
  IconDroplet,
  IconThermometer,
  IconWind
} from "./Icons";
import RiskGauge from "./RiskGauge";
import FeatureImportanceChart from "./FeatureImportanceChart";
import MetricCard from "./MetricCard";
import AICopilotChat from "./AICopilotChat";
import DetailedReport from "./DetailedReport";
import HomeOverview from "./HomeOverview";
import { translations } from "../i18n/translations";

export default function Dashboard({
  data,
  language = "en",
  apiBase,
  onExplain
}) {
  const t = translations[language] || translations.en;
  const briefing = data?.ai_briefing || {};
  const prediction = data?.prediction || {};
  const alert = data?.alert || {};
  const weather = data?.current_weather || {};
  const terrain = data?.terrain || {};
  const hydrology = data?.hydrology || {};
  const soil = data?.soil || {};
  const landCover = data?.land_cover || {};
  const exposure = data?.exposure || {};
  const location = data?.location || {};
  const evidence = data?.evidence?.top_features || [];
  const forecast = data?.forecast || {};
  const remote = data?.remote_sensing || {};
  const floodExp = data?.flood_exposure || {};

  const riskClass = prediction.risk_class || "HIGH";
  const probability = prediction.flood_probability_pct || 0;
  const approximationFactor = Math.min(0.9, Math.max(0.18, 0.18 + (Number(probability) / 100) * 0.65 + (Number(landCover.built_up_pct?.value) || 5) / 500));
  const approximationPopulation = Math.round(145000 * approximationFactor);
  const estimatedExposure = {
    population: { value: 145000, unit: "people", source: "Hardcoded probability approximation", sourceType: "ESTIMATED", status: "ESTIMATED" },
    vulnerable_population: { value: Math.round(approximationPopulation * 0.18), unit: "people", source: "Hardcoded probability approximation", sourceType: "ESTIMATED", status: "ESTIMATED" },
    buildings_exposed: { value: Math.max(1, Math.round(approximationPopulation / 5)), unit: "buildings", source: "Hardcoded probability approximation", sourceType: "ESTIMATED", status: "ESTIMATED" },
    hospitals_exposed: { value: Math.max(1, Math.round(approximationPopulation / 120000)), unit: "facilities", source: "Hardcoded probability approximation", sourceType: "ESTIMATED", status: "ESTIMATED" },
    schools_exposed: { value: Math.max(1, Math.round(approximationPopulation / 18000)), unit: "facilities", source: "Hardcoded probability approximation", sourceType: "ESTIMATED", status: "ESTIMATED" },
    roads_exposed_km: { value: Number((1.5 + Math.sqrt(approximationPopulation) * 0.08).toFixed(1)), unit: "km", source: "Hardcoded probability approximation", sourceType: "ESTIMATED", status: "ESTIMATED" },
    bridges_exposed: { value: Math.max(1, Math.round(approximationPopulation / 60000)), unit: "bridges", source: "Hardcoded probability approximation", sourceType: "ESTIMATED", status: "ESTIMATED" }
  };
  const exposureMetric = (key) => {
    const metric = exposure[key];
    return metric && metric.value !== null && metric.value !== undefined ? metric : estimatedExposure[key];
  };
  const probabilityMetric = (value, unit) => ({
    value,
    unit,
    source: "Hardcoded probability approximation",
    sourceType: "ESTIMATED",
    status: "ESTIMATED"
  });
  const estimatedSoilRunoff = probabilityMetric(Math.round(65 + Number(probability) * 0.2), "Index");
  const estimatedClay = probabilityMetric(28.5, "%");
  const estimatedSand = probabilityMetric(38, "%");
  const estimatedSilt = probabilityMetric(33.5, "%");
  const estimatedRiverStage = probabilityMetric(Number((0.8 + Number(probability) * 0.012).toFixed(2)), "m");
  const estimatedDrainage = probability >= 60 ? "HIGH" : probability >= 30 ? "MODERATE" : "LOW";
  const metricOrProbability = (metric, fallback) => metric && metric.value !== null && metric.value !== undefined ? metric : fallback;

  const aiRisk = data?.ai_risk_status || {};
  const cwcGroundTruth = data?.cwc_ground_truth || data?.observed_hydrology_status || {};
  const fallbackEnv = data?.fallback_environmental || {};
  const overallMonitoring = data?.overall_monitoring || {};
  const overallStatus = overallMonitoring.status || alert.level || "NORMAL";
  const overallConfidence = overallMonitoring.confidence || "MEDIUM CONFIDENCE";
  const overallBasis = overallMonitoring.basis || "AI MODEL";

  const isCwcAvailable = cwcGroundTruth.status === "AVAILABLE" && cwcGroundTruth.water_level_m !== null;
  const isCwcStale = cwcGroundTruth.status === "STALE";

  // Computed flood exposure values
  const estimatedDepth = floodExp.estimated_depth_m ?? (0.3 + (probability / 100) * 1.2).toFixed(2);
  const maxDepth = floodExp.max_expected_depth_m ?? (Number(estimatedDepth) * 1.5).toFixed(2);
  const inundatedArea = floodExp.inundated_area_km2 ?? ((exposure.estimated_exposed_population || 0) / 530).toFixed(1);
  const agriExposed = floodExp.agricultural_land_km2 ?? (Number(inundatedArea) * 0.58).toFixed(1);

  const riskEntries = Object.entries(data?.risk_components || {}).map(([key, value]) => [key, Number(value) || 0]);
  const riskTotal = riskEntries.reduce((sum, [, value]) => sum + value, 0) || 1;
  const riskColors = ["#b25d2b", "#d47d32", "#3b7468", "#5b9ed1", "#8b6f47", "#8d4f3d", "#9aa69f"];
  let riskOffset = 0;
  const riskGradient = riskEntries.map(([key, value], index) => {
    const start = (riskOffset / riskTotal) * 100;
    riskOffset += value;
    const end = (riskOffset / riskTotal) * 100;
    return `${riskColors[index % riskColors.length]} ${start}% ${end}%`;
  }).join(", ");

  const lat = location.latitude || 25.25;
  const lon = location.longitude || 87.04;
  const tileZoom = 11;
  const n = 2 ** tileZoom;
  const tileX = Math.floor(((lon + 180) / 360) * n);
  const latRad = (lat * Math.PI) / 180;
  const tileY = Math.floor((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * n);
  const demTile = `https://tile.opentopomap.org/${tileZoom}/${tileX}/${tileY}.png`;
  const satTile = `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${tileZoom}/${tileY}/${tileX}`;
  const bbox = `${lon - 0.18},${lat - 0.12},${lon + 0.18},${lat + 0.12}`;

  // Warning emoji
  const warningEmoji = overallStatus === "CRITICAL" ? "🔴" : overallStatus === "HIGH ALERT" ? "🟠" : overallStatus === "WATCH" ? "🟡" : "🟢";

  return (
    <div className="dashboard-root animate-fade-in">

      <HomeOverview data={data} language={language} onAnalyzeBasin={(basinLat, basinLon) => window.dispatchEvent(new CustomEvent("chetakai:analyze-basin", { detail: { lat: basinLat, lon: basinLon } }))} />

      {/* NEW UPPER UI - INTELLIGENCE DASHBOARD */}
      <section className="intel-wrapper">
        <div className="intel-grid">
          {/* COLUMN 1: AI FLOOD RISK */}
          <div className="intel-col theme-ai">
            <div className="intel-header">
              <span>🧠 . AI FLOOD RISK</span>
              <IconShield className="w-4 h-4" />
            </div>
            <div className="intel-body">
              <div className="intel-title">
                AI Model Prediction
              </div>
              <div className="intel-subtitle">Based on rainfall, soil, terrain & more</div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '8px' }}>
                <div>
                  <div className="intel-main-val">{aiRisk.probability !== null && aiRisk.probability !== undefined ? `${(Number(aiRisk.probability) > 1 ? Number(aiRisk.probability) : Number(aiRisk.probability) * 100).toFixed(1)}%` : `${probability.toFixed(1)}%`}</div>
                  <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '8px' }}>Flood Probability</div>
                  <span className="intel-badge outline-green">{aiRisk.risk || aiRisk.label || riskClass} RISK</span>
                </div>
                {/* A simulated circular arc icon */}
                <div style={{ width: '80px', height: '80px', borderRadius: '50%', border: '8px solid #f1f5f9', borderBottomColor: '#22c55e', borderLeftColor: '#22c55e', display: 'grid', placeItems: 'center', transform: 'rotate(-45deg)' }}>
                  <IconRain className="w-8 h-8 text-slate-400" style={{ transform: 'rotate(45deg)' }} />
                </div>
              </div>
              
              <div className="intel-box-light" style={{ marginTop: 'auto' }}>
                <IconCheck className="w-5 h-5 text-green-600 flex-shrink-0" />
                <span>Low chance of flood in this area based on our AI model.</span>
              </div>
            </div>
            <div className="intel-footer">
              Source: Neer Drishti Model
            </div>
          </div>

          {/* COLUMN 2: ENVIRONMENTAL CONDITIONS */}
          <div className="intel-col theme-cwc">
            <div className="intel-header">
              <span>2. ENVIRONMENTAL CONDITIONS</span>
              <IconWaves className="w-4 h-4" />
            </div>
            <div className="intel-body">
              <div className="intel-title">
                Rainfall & Soil Signals
              </div>
              <div className="intel-subtitle">Independent environmental inputs</div>

              <div className="station-levels" style={{ marginTop: '12px' }}>
                <div className="level-col">
                  <span>Rainfall 24h</span>
                  <strong style={{ color: '#f59e0b' }}>{weather.rainfall_24h?.value ?? "—"} mm</strong>
                </div>
                <div className="level-col">
                  <span>Rainfall 72h</span>
                  <strong style={{ color: '#f59e0b' }}>{weather.rainfall_72h?.value ?? "—"} mm</strong>
                </div>
                <div className="level-col">
                  <span>Soil Moisture</span>
                  <strong style={{ color: '#22c55e' }}>{soil.moisture_root_zone?.value ?? "—"} m³/m³</strong>
                </div>
              </div>

              <div className="intel-box-light" style={{ marginTop: '12px' }}>
                <IconCheck className="w-5 h-5 text-green-600 flex-shrink-0" />
                <span>Prediction is driven by rainfall, soil moisture, GloFAS, terrain, and satellite indicators rather than a single gauge level.</span>
              </div>
            </div>
            <div className="intel-footer">
              Source: Rainfall, soil, terrain, GloFAS, satellite
            </div>
          </div>

        </div>

        {/* BOTTOM EXPLAINER SECTION */}
        <div className="intel-explainer">
          <div>
            <div className="explainer-title" style={{ marginBottom: '12px' }}>
              <IconUsers className="w-4 h-4 text-emerald-600" /> WHAT DOES THIS MEAN?
            </div>
            <div className="explainer-cols">
              <div className="expl-item" style={{ borderRight: '1px solid #e2e8f0', paddingRight: '16px' }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                  <IconCheck className="w-6 h-6 text-emerald-600 flex-shrink-0" style={{ background: '#dcfce7', borderRadius: '50%', padding: '3px' }} />
                  <span>Low flood risk in this area (according to AI).</span>
                </div>
              </div>
              
              <div className="expl-item" style={{ borderRight: '1px solid #e2e8f0', paddingRight: '16px' }}>
                <IconAlertTriangle className="w-6 h-6 text-amber-500 flex-shrink-0" />
                <span>Independent environmental indicators are being monitored continuously.</span>
              </div>
              
              <div className="expl-item">
                <IconRain className="w-6 h-6 text-blue-500 flex-shrink-0" />
                <span>River discharge is low according to model.</span>
              </div>
            </div>
          </div>
          
          <div>
            <div className="explainer-title" style={{ color: '#16a34a' }}><IconShield className="w-4 h-4" /> WHAT SHOULD YOU DO?</div>
            <div className="action-items">
              <div className="action-item">
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: '#dcfce7', display: 'grid', placeItems: 'center', color: '#16a34a' }}>
                  <IconEye className="w-4 h-4" />
                </div>
                <strong>KEEP WATCH</strong>
                <span>Stay alert</span>
              </div>
              <div className="action-item">
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: '#fef3c7', display: 'grid', placeItems: 'center', color: '#d97706' }}>
                  <IconActivity className="w-4 h-4" />
                </div>
                <strong>STAY INFORMED</strong>
                <span>Check updates regularly</span>
              </div>
              <div className="action-item">
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: '#dbeafe', display: 'grid', placeItems: 'center', color: '#2563eb' }}>
                  <IconUsers className="w-4 h-4" />
                </div>
                <strong>FOLLOW ADVICE</strong>
                <span>Follow local instructions</span>
              </div>
              <div className="action-item">
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: '#ede9fe', display: 'grid', placeItems: 'center', color: '#7c3aed' }}>
                  <IconBuilding className="w-4 h-4" />
                </div>
                <strong>BE PREPARED</strong>
                <span>Keep essentials ready</span>
              </div>
            </div>
          </div>
        </div>

        {/* RISK LEVEL GUIDE (Inside Explainer) */}
        <div className="risk-guide-wrap">
          <div className="risk-level-guide">
            <div style={{ padding: '6px 10px', fontSize: '9px', fontWeight: 800, letterSpacing: '0.5px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>RISK LEVEL GUIDE</div>
            <div className="risk-guide-row">
              <div className="risk-guide-label" style={{ color: '#16a34a' }}>NORMAL</div>
              <div className="risk-guide-desc">No immediate risk</div>
            </div>
            <div className="risk-guide-row">
              <div className="risk-guide-label" style={{ color: '#d97706' }}>ELEVATED</div>
              <div className="risk-guide-desc">Be cautious</div>
            </div>
            <div className="risk-guide-row">
              <div className="risk-guide-label" style={{ color: '#ea580c' }}>HIGH</div>
              <div className="risk-guide-desc">Take action</div>
            </div>
            <div className="risk-guide-row">
              <div className="risk-guide-label" style={{ color: '#dc2626' }}>CRITICAL</div>
              <div className="risk-guide-desc">Danger! Act now</div>
            </div>
          </div>
        </div>

        {/* STATUS BAR */}
        <div className="intel-status-bar">
          <div className="status-bar-left">
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><IconLocation className="w-3.5 h-3.5" /> Location: <strong>{location.latitude?.toFixed(6) ?? lat.toFixed(6)}°N, {location.longitude?.toFixed(6) ?? lon.toFixed(6)}°E</strong></span>
            <div className="status-bar-divider"></div>
            <span>District: {location.district || "Unknown"}, {location.administrative_area || "Unknown"}</span>
          </div>
          <div className="status-bar-right">
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>📅 Last Updated: {data.generated_at ? new Date(data.generated_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true }) : "Just now"}</span>
            <div className="status-bar-divider"></div>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><IconActivity className="w-3 h-3" /> Auto refresh in 10 min</span>
            <button className="help-btn">
              <IconHelp className="w-3.5 h-3.5" /> Need Help? Call 1070
            </button>
          </div>
        </div>
      </section>


      {/* 1. EXECUTIVE AI SITUATIONAL ALERT BANNER */}
      <div className={`alert-banner banner-${overallStatus.toLowerCase()}`}>
        <div className="alert-banner-header">
          <div className="alert-badge-pill">
            <IconAlertTriangle className="w-5 h-5" />
            <span>{briefing.urgency || t.riskLevels[overallStatus] || `${overallStatus} FLOOD MONITORING`}</span>
          </div>
          <span className="alert-timestamp">● Real-Time Analysis: {new Date(data.generated_at).toLocaleTimeString()}</span>
        </div>

        <h2 className="alert-headline">{briefing.headline || `${location.basin_name || "Catchment"} Flood Hazard Alert`}</h2>
        <p className="alert-summary">{briefing.summary}</p>

        {briefing.actions && briefing.actions.length > 0 && (
          <div className="alert-actions-card">
            <h4 className="actions-card-title">
              <IconCheck className="w-4 h-4 text-emerald-500" />
              <span>{t.actionPlanTitle}</span>
            </h4>
            <div className="actions-grid">
              {briefing.actions.map((act, i) => (
                <div key={i} className="action-pill">
                  <span className="action-num">{i + 1}</span>
                  <span className="action-text">{act}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="alert-provenance-footer">
          <span>{briefing.ai_provenance || "Grounded in multi-sensor physical telemetry and AI regional hydrodynamic estimation."}</span>
        </div>
      </div>

      <DetailedReport data={data} language={language} />

      {/* 2. TOP ROW: GAUGE + ML DECISION DRIVERS + QUICK SUMMARY */}
      <div className="top-insights-grid">
        <RiskGauge 
          probability={probability} 
          riskScore={data?.prediction?.risk_score} 
          riskClass={riskClass} 
          confidencePct={data?.prediction?.confidence_pct}
          alert={data?.alert} 
          onExplain={onExplain} 
        />

        <FeatureImportanceChart
          evidence={evidence}
          onExplain={onExplain}
        />

        <div className="catchment-overview-card">
          <div className="overview-header">
            <div className="overview-title-group">
              <IconLocation className="w-5 h-5 text-copper" />
              <h3 className="overview-title">{location.basin_name || "Identified Basin"}</h3>
            </div>
            <span className="badge-basin-id">{location.basin_id || "BASIN"}</span>
          </div>

          <div className="overview-meta-list">
            <div className="overview-meta-item">
              <span className="meta-label">Coordinates:</span>
              <span className="meta-val">{location.latitude?.toFixed(4)}° N, {location.longitude?.toFixed(4)}° E</span>
            </div>
            <div className="overview-meta-item">
              <span className="meta-label">Administrative Area:</span>
              <span className="meta-val">{location.administrative_area}, {location.district}</span>
            </div>
            <div className="overview-meta-item">
              <span className="meta-label">Soil Runoff Proxy:</span>
              <span className="meta-val text-amber-700 font-bold">{soil.soil_runoff_proxy?.value ?? "Unavailable"}</span>
            </div>
            <div className="overview-meta-item">
              <span className="meta-label">Exposed Population:</span>
              <span className="meta-val text-rose-700 font-bold">{exposure.population?.value ? exposure.population.value.toLocaleString() : "Unavailable"}</span>
            </div>
          </div>

          <div className="overview-footer-badge">
            <span className="dot-live"></span>
            <span>HydroBASINS Level 6 Verified</span>
          </div>
        </div>
      </div>

      {/* 3. 6-PILLAR GEOSPATIAL & PHYSICAL TELEMETRY GRID */}
      <div className="telemetry-section-container">
        <div className="section-title-bar">
          <div>
            <span className="section-kicker">PHYSICAL GROUND TRUTH</span>
            <h3 className="section-heading">{t.telemetryTitle}</h3>
          </div>
          <span className="section-note">{t.learnMore}</span>
        </div>

        {/* PILLAR 1: METEOROLOGY & PRECIPITATION */}
        <div className="pillar-block">
          <div className="pillar-header">
            <IconRain className="w-5 h-5 text-copper" />
            <h4 className="pillar-title">{t.sections.weather}</h4>
          </div>
          <div className="metrics-grid">
            <MetricCard
              icon={IconRain}
              title={t.metrics.rain1h}
              dataObj={weather.rainfall_1h}
              subtitle="Doppler Radar Rate"
              trend={weather.rainfall_1h?.value > 15 ? "Heavy" : "Normal"}
              explainerData={{
                key: "rainfall_1h_proxy",
                name: "1-Hour Rainfall Intensity",
                category: "Meteorology & Radar",
                description: "Local precipitation recorded in the past 60 minutes via Doppler radar proxies and automatic weather stations."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconRain}
              title="Rain 3h"
              dataObj={weather.rainfall_3h}
              unit="mm"
              subtitle="3-Hour Accumulation"
              trend={weather.rainfall_3h > 30 ? "Heavy" : "Normal"}
              explainerData={{
                key: "rainfall_3h_proxy",
                name: "3-Hour Rainfall",
                category: "Meteorology & Radar",
                description: "Cumulative 3-hour rainfall volume."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconRain}
              title="Rain 6h"
              dataObj={weather.rainfall_6h}
              unit="mm"
              subtitle="6-Hour Accumulation"
              explainerData={{
                key: "rainfall_6h_proxy",
                name: "6-Hour Rainfall",
                category: "Meteorology & Radar",
                description: "Cumulative 6-hour rainfall volume."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconRain}
              title={t.metrics.rain24h}
              dataObj={weather.rainfall_24h}
              subtitle="24h Integrated Volume"
              trend={weather.rainfall_24h?.value > 70 ? "Intense Surge" : "Moderate"}
              explainerData={{
                key: "rainfall_24h_proxy",
                name: "24-Hour Cumulative Rainfall",
                category: "Meteorology & Radar",
                description: "Cumulative 24-hour rainfall determining catchment saturation and secondary tributary swelling."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconRain}
              title={t.metrics.rain72h}
              dataObj={weather.rainfall_72h}
              unit="mm"
              subtitle="3-Day Basin Total"
              trend="Severe Regional Loading"
              explainerData={{
                key: "rainfall_72h_proxy",
                name: "72-Hour Cumulative Rainfall",
                category: "Meteorology & Radar",
                description: "Three-day cumulative precipitation volume across the watershed basin, primary driver of embankment breaching."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconThermometer}
              title="Air Temperature"
              dataObj={weather.temperature}
              subtitle={`Humidity: ${weather.humidity?.value?.toFixed(0) || "—"}%`}
              explainerData={{
                key: "temperature",
                name: "Surface Ambient Temperature",
                category: "Meteorology & Radar",
                description: "Atmospheric surface temperature and relative humidity influencing evapotranspiration."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconDroplet}
              title="Humidity"
              dataObj={weather.humidity}
              subtitle="Relative Humidity"
              explainerData={{
                key: "humidity",
                name: "Relative Humidity",
                category: "Meteorology",
                description: "Current atmospheric relative humidity."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconWind}
              title="Wind Speed"
              dataObj={weather.wind_speed}
              subtitle="Surface Wind"
              explainerData={{
                key: "wind",
                name: "Wind Speed",
                category: "Meteorology",
                description: "Surface wind speed at 10m height."
              }}
              onExplain={onExplain}
            />
          </div>
        </div>

        {/* PILLAR 2: FORECAST / NWP */}
        <div className="pillar-block">
          <div className="pillar-header">
            <IconActivity className="w-5 h-5 text-copper" />
            <h4 className="pillar-title">Forecast / NWP</h4>
          </div>
          <div className="metrics-grid">
            <MetricCard
              icon={IconRain}
              title="NWP Rain 1h"
              dataObj={forecast.nwp_rain_1h}
              unit="mm"
              subtitle="Numerical Weather Prediction"
              explainerData={{
                key: "nwp_rain_1h",
                name: "NWP 1-Hour Forecast Rain",
                category: "Forecast",
                description: "Predicted rainfall for the next 1 hour from numerical weather models."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconRain}
              title="NWP Rain 3h"
              dataObj={forecast.nwp_rain_3h}
              unit="mm"
              subtitle="3-Hour Forecast"
              explainerData={{
                key: "nwp_rain_3h",
                name: "NWP 3-Hour Forecast Rain",
                category: "Forecast",
                description: "Predicted rainfall for the next 3 hours from numerical weather models."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconRain}
              title="NWP Rain 6h"
              dataObj={forecast.nwp_rain_6h}
              unit="mm"
              subtitle="6-Hour Forecast"
              explainerData={{
                key: "nwp_rain_6h",
                name: "NWP 6-Hour Forecast Rain",
                category: "Forecast",
                description: "Predicted rainfall for the next 6 hours from NWP ensemble."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconRain}
              title="NWP Rain 12h"
              dataObj={forecast.nwp_rain_12h}
              unit="mm"
              subtitle="12-Hour Forecast"
              explainerData={{
                key: "nwp_rain_12h",
                name: "NWP 12-Hour Forecast Rain",
                category: "Forecast",
                description: "Predicted rainfall for the next 12 hours from NWP ensemble."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconRain}
              title="NWP Rain 24h"
              dataObj={forecast.nwp_rain_24h}
              subtitle="24-Hour Forecast"
              trend={forecast.nwp_rain_24h?.value > 50 ? "Heavy Expected" : "Moderate"}
              explainerData={{
                key: "nwp_rain_24h",
                name: "NWP 24-Hour Forecast Rain",
                category: "Forecast",
                description: "Predicted rainfall for the next 24 hours."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconShield}
              title="Forecast Confidence"
              dataObj={forecast.confidence}
              unit={forecast.confidence_label ? "" : "%"}
              subtitle={`NWP Spread: ${forecast.spread?.value?.toFixed?.(1) || "—"} mm`}
              explainerData={{
                key: "forecast_confidence",
                name: "Forecast Confidence",
                category: "Forecast",
                description: "Confidence level of the numerical weather prediction based on ensemble spread."
              }}
              onExplain={onExplain}
            />
          </div>
        </div>

        {/* PILLAR 3: TERRAIN & TOPOGRAPHY */}
        <div className="pillar-block">
          <div className="pillar-header">
            <IconMountain className="w-5 h-5 text-copper" />
            <h4 className="pillar-title">{t.sections.terrain}</h4>
          </div>
          <div className="metrics-grid">
            <MetricCard
              icon={IconMountain}
              title={t.metrics.slope}
              dataObj={terrain.mean_slope_deg}
              subtitle="Topographical Gradient"
              trend={terrain.mean_slope_deg?.value < 3.0 ? "Flat / Waterlogging Prone" : "Moderate"}
              explainerData={{
                key: "mean_slope_deg",
                name: "Catchment Mean Slope",
                category: "Terrain & Topography",
                description: "Average topographical inclination angle derived from Copernicus DEM 30m. Low slope (< 3°) causes prolonged standing water."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconMountain}
              title={t.metrics.elevation}
              dataObj={terrain.elevation_m}
              subtitle="DEM Datum"
              explainerData={{
                key: "min_elevation_m",
                name: "Minimum Terrain Elevation",
                category: "Terrain & Topography",
                description: "Lowest topographical elevation point in the local catchment relative to mean sea level."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconMountain}
              title={t.metrics.elevationRatio}
              dataObj={terrain.elevation_range_ratio}
              unit="Ratio"
              subtitle="Relief Ruggedness"
              explainerData={{
                key: "elevation_range_ratio",
                name: "Elevation Range Ratio",
                category: "Terrain & Topography",
                description: "Normalized ratio of catchment peak to valley floor indicating potential flood wave kinetic energy."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconMountain}
              title="Flow Accumulation"
              dataObj={terrain.flow_accumulation}
              subtitle="Upstream contributing cells"
              explainerData={{
                key: "flow_accumulation",
                name: "Flow Accumulation",
                category: "Terrain & Topography",
                description: "Estimated upstream contributing area used as a flood routing proxy."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconWaves}
              title="Distance to River"
              dataObj={terrain.distance_to_river_km}
              unit="km"
              subtitle="Nearest channel"
              explainerData={{
                key: "distance_to_river_km",
                name: "Distance to River",
                category: "Terrain & Topography",
                description: "Approximate distance from the queried point to the nearest major river channel."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconMountain}
              title="Drainage Susceptibility"
              dataObj={terrain.risk
                ? { value: terrain.risk, unit: "", source: "Catchment model", sourceType: "DERIVED", status: "OK" }
                : probabilityMetric(estimatedDrainage, "")}
              explainerData={{
                key: "terrain_risk",
                name: "Terrain Drainage Susceptibility",
                category: "Terrain & Topography",
                description: "Susceptibility class based on flow accumulation and slope vector analysis."
              }}
              onExplain={onExplain}
            />
          </div>
        </div>

        {/* PILLAR 4: RIVERINE HYDROLOGY */}
        <div className="pillar-block">
          <div className="pillar-header">
            <IconWaves className="w-5 h-5 text-copper" />
            <h4 className="pillar-title">{t.sections.hydrology}</h4>
          </div>
          <div className="metrics-grid">
            <MetricCard
              icon={IconWaves}
              title="Modelled River Stage"
              dataObj={metricOrProbability(hydrology.river_stage, estimatedRiverStage)}
              explainerData={{
                key: "river_level",
                name: "Modelled River Stage",
                category: "Hydrology",
                description: "Hydrologic stage estimate from modelled discharge and terrain context, without reliance on a single observed gauge."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconWaves}
              title="GloFAS Modelled River Discharge"
              dataObj={hydrology.river_discharge}
              subtitle="GloFAS • MODELLED"
              explainerData={{
                key: "river_discharge",
                name: "GloFAS Modelled River Discharge",
                category: "Hydrology",
                description: "Modelled volume of water flowing through the river channel per second, from the GloFAS global flood monitoring system. Modelled hydrology, not an observed river stage."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconWaves}
              title="Mainstem River Area"
              dataObj={hydrology.river_area_km2}
              unit="km²"
              subtitle="Drainage Surface"
              explainerData={{
                key: "river_area_km2",
                name: "Mainstem River Surface Area",
                category: "Hydrology",
                description: "Total surface water channel coverage within the basin network."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconWaves}
              title="Upstream Reservoirs"
              dataObj={hydrology.reservoir_count}
              unit="Structures"
              subtitle="HydroLAKES Storage"
              explainerData={{
                key: "reservoir_count",
                name: "Catchment Reservoir Count",
                category: "Hydrology",
                description: "Number of monitored upstream dams and water retention structures capable of emergency discharge."
              }}
              onExplain={onExplain}
            />
          </div>
        </div>

        {/* PILLAR 5: SOIL PHYSICS & RUNOFF */}
        <div className="pillar-block">
          <div className="pillar-header">
            <IconLayers className="w-5 h-5 text-copper" />
            <h4 className="pillar-title">{t.sections.soil}</h4>
          </div>
          <div className="metrics-grid">
            <MetricCard
              icon={IconLayers}
              title={t.metrics.soilRunoff}
              dataObj={metricOrProbability(soil.soil_runoff_proxy, estimatedSoilRunoff)}
              unit="Index"
              explainerData={{
                key: "soil_runoff_proxy",
                name: "Soil Runoff Coefficient Proxy",
                category: "Soil & Surface",
                description: "Hydrological index indicating the fraction of rain that converts into immediate surface runoff."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconLayers}
              title={t.metrics.clay}
              dataObj={metricOrProbability(soil.clay_pct, estimatedClay)}
              explainerData={{
                key: "clay_fraction_pct",
                name: "Soil Clay Content Percentage",
                category: "Soil & Surface",
                description: "Proportion of fine clay particles in topsoil (0-30cm); high clay inhibits water absorption."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconLayers}
              title={t.metrics.sand}
              dataObj={metricOrProbability(soil.sand_fraction_pct, estimatedSand)}
              unit="%"
              subtitle="Permeable Fraction"
              explainerData={{
                key: "sand_fraction_pct",
                name: "Soil Sand Content Percentage",
                category: "Soil & Surface",
                description: "Proportion of coarse sand grains promoting groundwater percolation."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconLayers}
              title={t.metrics.silt}
              dataObj={metricOrProbability(soil.silt_fraction_pct, estimatedSilt)}
              unit="%"
              subtitle="Alluvial Silt Fraction"
              explainerData={{
                key: "silt_fraction_pct",
                name: "Soil Silt Content Percentage",
                category: "Soil & Surface",
                description: "Intermediate soil texture common in river deltas and floodplains."
              }}
              onExplain={onExplain}
            />
          </div>
        </div>

        {/* PILLAR 6: LAND USE & LAND COVER */}
        <div className="pillar-block">
          <div className="pillar-header">
            <IconLayers className="w-5 h-5 text-copper" />
            <h4 className="pillar-title">{t.sections.landcover}</h4>
          </div>
          <div className="metrics-grid">
            <MetricCard
              icon={IconLayers}
              title={t.metrics.cropland}
              dataObj={landCover.cropland_pct}
              subtitle="Catchment land-cover composition • ESTIMATED"
              trend={null}
              explainerData={{
                key: "cropland_pct",
                name: "Agricultural Cropland Percentage",
                category: "Land Cover",
                description: "Percentage of basin land dedicated to crop cultivation. Catchment land-cover composition estimated from regional databases."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconLayers}
              title={t.metrics.builtUp}
              dataObj={landCover.built_up_pct}
              subtitle="Impervious Surfaces"
              explainerData={{
                key: "built_up_pct",
                name: "Built-up Urban Surface Area",
                category: "Land Cover",
                description: "Paved urban footprint generating high flash flood runoff."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconLayers}
              title={t.metrics.treeCover}
              dataObj={landCover.tree_cover_pct}
              unit="%"
              subtitle="Natural Canopy Buffer"
              explainerData={{
                key: "tree_cover_pct",
                name: "Forest & Tree Canopy Cover",
                category: "Land Cover",
                description: "Forest vegetation aiding rainfall interception and soil retention."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconLayers}
              title={t.metrics.water}
              dataObj={landCover.water_pct}
              unit="%"
              subtitle="Permanent Water Bodies"
              explainerData={{
                key: "water_pct",
                name: "Permanent Surface Water Area",
                category: "Land Cover",
                description: "Perennial lakes, wetlands, and rivers."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconLayers}
              title="Wetland"
              dataObj={landCover.wetland_pct}
              unit="%"
              subtitle="Seasonal Wetland Areas"
              explainerData={{
                key: "wetland_pct",
                name: "Wetland Coverage",
                category: "Land Cover",
                description: "Seasonal and permanent wetland areas acting as natural flood buffers."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconLayers}
              title="Natural Vegetation"
              dataObj={metricOrProbability(landCover.natural_vegetation_pct, probabilityMetric(17.7, "%"))}
              unit="%"
              explainerData={{
                key: "natural_veg_pct",
                name: "Natural Vegetation",
                category: "Land Cover",
                description: "Grassland, shrubs and natural vegetation cover."
              }}
              onExplain={onExplain}
            />
          </div>
        </div>

        {/* PILLAR 7: VULNERABILITY & EXPOSURE */}
        <div className="pillar-block">
          <div className="pillar-header">
            <IconUsers className="w-5 h-5 text-copper" />
            <h4 className="pillar-title">{t.sections.exposure}</h4>
          </div>
          <div className="metrics-grid">
            <MetricCard
              icon={IconUsers}
              title={t.metrics.exposedPop}
              dataObj={exposureMetric("population")}
              explainerData={{
                key: "estimated_exposed_population",
                name: "Estimated Exposed Population",
                category: "Vulnerability & Exposure",
                description: "Estimated number of residents living within the active flood hazard perimeter."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconUsers}
              title={t.metrics.vulnerablePop}
              dataObj={exposureMetric("vulnerable_population")}
              isAiEstimate={exposure.is_ai_estimate}
              estimationSource={exposure.estimation_source}
              explainerData={{
                key: "vulnerable_population",
                name: "Vulnerable Demographics",
                category: "Vulnerability & Exposure",
                description: "Children under 5 and elderly residents requiring assisted evacuation."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconBuilding}
              title="Buildings Exposed"
              dataObj={exposureMetric("buildings_exposed")}
              explainerData={{
                key: "buildings_exposed",
                name: "Buildings in Flood Zone",
                category: "Vulnerability & Exposure",
                description: "Number of buildings within the estimated inundation perimeter."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconUsers}
              title={t.metrics.hospitals}
              dataObj={exposureMetric("hospitals_exposed")}
              explainerData={{
                key: "critical_infrastructure_exposed",
                name: "Critical Medical Infrastructure",
                category: "Vulnerability & Exposure",
                description: "Hospitals and clinics within the inundation zone requiring power backup."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconUsers}
              title="Schools Exposed"
              dataObj={exposureMetric("schools_exposed")}
              explainerData={{
                key: "schools_exposed",
                name: "Schools in Flood Zone",
                category: "Vulnerability & Exposure",
                description: "Number of schools within estimated flood extent."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconUsers}
              title={t.metrics.roads}
              dataObj={exposureMetric("roads_exposed_km")}
              explainerData={{
                key: "roads_exposed_km",
                name: "Inundated Road Network Length",
                category: "Vulnerability & Exposure",
                description: "Kilometers of primary and secondary roads submerged, affecting relief logistics."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconUsers}
              title="Bridges Exposed"
              dataObj={exposureMetric("bridges_exposed")}
              explainerData={{
                key: "bridges_exposed",
                name: "Bridges in Flood Zone",
                category: "Vulnerability & Exposure",
                description: "Number of road/rail bridges within the flood impact zone."
              }}
              onExplain={onExplain}
            />
          </div>
        </div>
      </div>

      {/* REMOTE SENSING & SATELLITE IMAGERY */}
      <div className="remote-sensing-section">
        <div className="section-title-bar">
          <div>
            <span className="section-kicker">REMOTE SENSING</span>
            <h3 className="section-heading">Radar, Satellite & DEM Imagery</h3>
          </div>
          <div className="rs-badges">
            <span className={`rs-badge ${remote.radar_available !== false ? "available" : ""}`}>Radar</span>
            <span className={`rs-badge ${remote.satellite_available !== false ? "available" : ""}`}>Satellite</span>
            <span className={`rs-badge ${remote.gauge_available !== false ? "available" : ""}`}>Gauge</span>
            <span className={`rs-badge ${hydrology.river_stage?.status === "OK" ? "available" : ""}`}>Hydrology</span>
            <span className={`rs-badge ${hydrology.river_discharge?.status === "OK" ? "available" : ""}`}>GloFAS</span>
          </div>
        </div>

        <div className="rs-grid">
          {/* Windy Radar Map */}
          <div className="rs-card">
            <div className="rs-card-header">
              <IconRadar className="w-4 h-4 text-copper" />
              <span>Live Radar Precipitation</span>
            </div>
            <div className="rs-iframe-wrap">
              <iframe
                src={`https://embed.windy.com/embed.html?type=map&location=coordinates&metricRain=mm&metricTemp=%C2%B0C&metricWind=km%2Fh&metricPressure=hPa&zoom=7&overlay=radar&product=radar&level=surface&lat=${location.latitude || 25.25}&lon=${location.longitude || 87.04}&message=true`}
                frameBorder="0"
                title="Radar Precipitation Map"
                loading="lazy"
                allowFullScreen
              ></iframe>
            </div>
          </div>

          {/* Satellite View */}
          <div className="rs-card">
            <div className="rs-card-header">
              <IconEye className="w-4 h-4 text-copper" />
              <span>Satellite Cloud & Rain View</span>
            </div>
            <div className="rs-iframe-wrap">
              <iframe
                src={`https://embed.windy.com/embed.html?type=map&location=coordinates&metricRain=mm&metricTemp=%C2%B0C&metricWind=km%2Fh&metricPressure=hPa&zoom=7&overlay=satellite&product=satellite&level=surface&lat=${location.latitude || 25.25}&lon=${location.longitude || 87.04}`}
                frameBorder="0"
                title="Satellite View"
                loading="lazy"
                allowFullScreen
              ></iframe>
            </div>
          </div>

          {/* DEM Elevation */}
          <div className="rs-card">
            <div className="rs-card-header">
              <IconMountain className="w-4 h-4 text-copper" />
              <span>DEM / topographic map</span>
            </div>
            <div className="rs-iframe-wrap">
              <img
                className="rs-tile-img"
                src={demTile}
                alt="OpenTopoMap DEM"
              />
            </div>
            <div className="dem-info">
              <div><strong>Elevation:</strong> {terrain.elevation_m?.value?.toFixed?.(0) ?? terrain.elevation_m?.value ?? "—"} m</div>
              <div><strong>Slope:</strong> {terrain.mean_slope_deg?.value?.toFixed?.(1) ?? terrain.mean_slope_deg?.value ?? "—"}°</div>
              <div><strong>Relief:</strong> {(terrain.relief_m?.value ?? terrain.relief_m) || "—"} m</div>
              <div><strong>Source:</strong> OpenTopoMap</div>
            </div>
          </div>

          <div className="rs-card">
            <div className="rs-card-header">
              <IconEye className="w-4 h-4 text-copper" />
              <span>Satellite imagery</span>
            </div>
            <div className="rs-iframe-wrap">
              <img className="rs-tile-img" src={satTile} alt="Esri World Imagery" />
            </div>
            <p className="rs-caption">
              Radar rain {remote.radar_rainfall_mm ?? "—"} mm · Satellite rain {remote.satellite_rainfall_mm ?? "—"} mm
            </p>
          </div>

        </div>
      </div>

      {/* FLOOD EXPOSURE SUMMARY */}
      <div className="flood-summary-section">
        <div className="section-title-bar">
          <div>
            <span className="section-kicker">FLOOD EXPOSURE</span>
            <h3 className="section-heading">Estimated Inundation Impact</h3>
          </div>
        </div>
        <div className="flood-summary-grid">
          <div className="flood-stat-card">
            <span className="flood-stat-label">Inundated Area</span>
            <span className="flood-stat-value">{inundatedArea} <small>km²</small></span>
          </div>
          <div className="flood-stat-card">
            <span className="flood-stat-label">Est. Flood Depth</span>
            <span className="flood-stat-value">{estimatedDepth} <small>m</small></span>
          </div>
          <div className="flood-stat-card">
            <span className="flood-stat-label">Max Expected Depth</span>
            <span className="flood-stat-value">{maxDepth} <small>m</small></span>
          </div>
          <div className="flood-stat-card">
            <span className="flood-stat-label">Agri Land Exposed</span>
            <span className="flood-stat-value">{agriExposed} <small>km²</small></span>
          </div>
          <div className="flood-stat-card">
            <span className="flood-stat-label">Population Exposed</span>
            <span className="flood-stat-value">{exposure.population?.value ? exposure.population.value.toLocaleString() : "Unavailable"}</span>
          </div>
          <div className="flood-stat-card">
            <span className="flood-stat-label">Buildings Exposed</span>
            <span className="flood-stat-value">{exposure.buildings_exposed?.value ? exposure.buildings_exposed.value.toLocaleString() : "Unavailable"}</span>
          </div>
        </div>
      </div>

      {/* AI FLOOD ASSESSMENT SUMMARY */}
      <div className="ai-assessment-section">
        <div className="section-title-bar">
          <div>
            <span className="section-kicker">AI FLOOD ASSESSMENT</span>
            <h3 className="section-heading">Machine Learning Risk Summary (ML Model Only)</h3>
          </div>
          <span className="section-note text-xs text-slate-400">Independent from a single observed gauge</span>
        </div>
        <div className="ai-assessment-card">
          <div className="ai-assess-main">
            <div className="ai-assess-probability">
              <span className="ai-assess-big-num">{probability?.toFixed(1)}%</span>
              <span className="ai-assess-sub">ML Inundation Probability</span>
            </div>
            <div className="ai-assess-label-col">
              <div className="ai-assess-label">{riskClass === "SEVERE" ? "🔴" : riskClass === "HIGH" ? "🟠" : riskClass === "MODERATE" ? "🟡" : "🟢"} AI Risk: {riskClass}</div>
              <div className="ai-assess-warning">Overall Combined Monitoring: <strong>{overallStatus}</strong></div>
              <div className="ai-assess-depth">Est. Depth: {estimatedDepth} m | Area: {inundatedArea} km²</div>
            </div>
          </div>

          <div className="ai-assess-details" aria-label="Flood assessment details">
            <div className="ai-assess-detail">
              <span>Monitoring status</span>
              <strong>{overallStatus}</strong>
            </div>
            <div className="ai-assess-detail">
              <span>Estimated depth</span>
              <strong>{estimatedDepth} m</strong>
            </div>
            <div className="ai-assess-detail">
              <span>Inundated area</span>
              <strong>{inundatedArea} km²</strong>
            </div>
            <div className="ai-assess-detail">
              <span>Model confidence</span>
              <strong>{data?.prediction?.confidence_pct ?? "—"}{data?.prediction?.confidence_pct !== undefined ? "%" : ""}</strong>
            </div>
          </div>

          <div className="risk-breakdown-grid">
            <h4 className="risk-breakdown-title">Risk Breakdown</h4>
            <div className="risk-pie-layout">
              <div className="risk-pie" style={{ background: `conic-gradient(${riskGradient || "#e3ddd1 0 100%"})` }}>
                <div className="risk-pie-center">
                  <strong>{Math.round(riskTotal)}</strong>
                  <span>Total score</span>
                </div>
              </div>
              <div className="risk-pie-legend">
                {riskEntries.map(([key, value], index) => (
                  <div key={key} className="risk-pie-legend-item">
                    <span className="risk-pie-swatch" style={{ background: riskColors[index % riskColors.length] }} />
                    <span className="rb-label">{key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</span>
                    <span className="rb-value">{value.toFixed(0)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* INTERACTIVE AI COPILOT CHAT */}
      <div className="copilot-section-wrap">
        <AICopilotChat
          telemetry={data}
          language={language}
          apiBase={apiBase}
          onExplain={onExplain}
        />
      </div>
    </div>
  );
}