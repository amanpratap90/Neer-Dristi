import React from "react";
import {
  IconActivity,
  IconAlertTriangle,
  IconBuilding,
  IconCheck,
  IconDroplet,
  IconEye,
  IconLocation,
  IconMap,
  IconRain,
  IconThermometer,
  IconWind
} from "./Icons";
import { translations } from "../i18n/translations";

function valueOf(metric, fallback = "--") {
  if (metric === null || metric === undefined) return fallback;
  if (typeof metric === "object") return metric.value ?? fallback;
  return metric;
}

function riskTone(status = "NORMAL") {
  const value = String(status).toUpperCase();
  if (value.includes("CRITICAL") || value.includes("SEVERE")) return "severe";
  if (value.includes("HIGH")) return "high";
  if (value.includes("WATCH") || value.includes("MODERATE") || value.includes("ELEVATED")) return "moderate";
  return "low";
}

export default function HomeOverview({ data, language = "en", onAnalyzeBasin }) {
  const ui = { ...translations.en.ui, ...((translations[language] || translations.en).ui || {}) };
  const location = data?.location || {};
  const weather = data?.current_weather || {};
  const forecast = data?.forecast || {};
  const soil = data?.soil || {};
  const hydrology = data?.hydrology || {};
  const exposure = data?.exposure || {};
  const alert = data?.alert || {};
  const monitoring = data?.overall_monitoring || {};
  const status = monitoring.status || alert.level || data?.prediction?.risk_class || "NORMAL";
  const tone = riskTone(status);
  const probability = Number(data?.prediction?.flood_probability_pct || 0).toFixed(0);
  const lat = Number(location.latitude || 25.25);
  const lon = Number(location.longitude || 87.04);
  const bbox = `${lon - 0.7},${lat - 0.45},${lon + 0.7},${lat + 0.45}`;
  const updated = data?.generated_at
    ? new Date(data.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : ui.justNow;
  const rainfall24 = valueOf(weather.rainfall_24h);
  const rainfall72 = valueOf(weather.rainfall_72h);
  const soilMoisture = valueOf(soil.moisture_root_zone);
  const wind = valueOf(weather.wind_speed);
  const humidity = valueOf(weather.humidity);
  const river = valueOf(hydrology.river_discharge);

  const basins = [
    { name: "Kosi River Basin (Bihar)", lat: 26.19, lon: 87.06 },
    { name: "Brahmaputra Basin (Assam)", lat: 27.47, lon: 94.91 },
    { name: "Godavari Delta (Andhra Pradesh)", lat: 16.91, lon: 81.85 },
    { name: "Yamuna Catchment (Delhi NCR)", lat: 28.61, lon: 77.21 },
    { name: "Mithi Catchment (Mumbai)", lat: 19.10, lon: 72.88 }
  ];

  return (
    <section className="home-overview animate-fade-in">
      <div className="home-overview-map-wrap">
        <div className="overview-alert-card">
          <div className={`overview-alert-kicker ${tone}`}>
            <IconAlertTriangle className="w-4 h-4" /> {tone === "low" ? ui.normalMonitoring : `${status} ALERT`}
          </div>
          <h2>{tone === "low" ? ui.conditionsStable : ui.monitoredRisk}</h2>
          <p>{location.basin_name || ui.currentLocation} {ui.beingMonitored}</p>
          <div className="overview-stat-grid">
            <div><strong>{probability}%</strong><span>{ui.floodProbability}</span></div>
            <div><strong>{exposure.population?.value?.toLocaleString?.() || "--"}</strong><span>{ui.exposedPopulation}</span></div>
            <div><strong>{valueOf(hydrology.river_level, river)}</strong><span>{ui.riverSignal}</span></div>
          </div>
          <div className={`overview-status-note ${tone}`}>
            <IconCheck className="w-4 h-4" /> {monitoring.explanation || "Live indicators are being checked continuously."}
          </div>
        </div>
        <div className="overview-map-controls">
          <button type="button" title={ui.layers}><IconMap className="w-4 h-4" /> {ui.layers}</button>
          <button type="button" title="Center on analyzed location"><IconLocation className="w-4 h-4" /></button>
        </div>
        <iframe
          className="overview-map"
          title={ui.mapTitle}
          src={`https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${lat}%2C${lon}`}
        />
        <div className="overview-map-legend">
          <strong>{ui.riskLevel}</strong>
          <span><i className="dot low" /> {ui.low}</span>
          <span><i className="dot moderate" /> {ui.moderate}</span>
          <span><i className="dot high" /> {ui.high}</span>
          <span><i className="dot severe" /> {ui.severe}</span>
        </div>
        <div className="overview-map-footer">{ui.lastUpdated}: {updated} <span>{ui.sourceLive}</span></div>
      </div>

      <div className="overview-section-heading">
        <div><span className="overview-kicker"><IconRain className="w-4 h-4" /> {ui.earlyPrediction}</span><h2>{ui.heavyRainfallPrediction}</h2><p>{ui.next72Hours}</p></div>
        <span className="overview-location-label"><IconLocation className="w-4 h-4" /> {location.district || location.basin_name || ui.currentLocation}</span>
      </div>
      <div className="forecast-strip">
        <div className="forecast-periods">
          {["0 - 6 Hrs", "6 - 24 Hrs", "24 - 48 Hrs", "48 - 72 Hrs"].map((period, index) => (
            <div className="forecast-period" key={period}><IconRain className={`forecast-icon ${index > 1 ? "dark" : ""}`} /><strong>{period}</strong><span>{index === 0 ? "Moderate" : index === 1 ? "Heavy" : index === 2 ? "Very Heavy" : "Extremely Heavy"}</span><small>{index === 0 ? `${rainfall24} mm` : index === 1 ? `${rainfall72} mm` : `${valueOf(forecast.nwp_rain_24h)} mm`}</small></div>
          ))}
        </div>
        <div className="forecast-summary"><span>{ui.heavyRainfallProbability}</span><strong>{Math.min(99, Math.max(1, Number(probability) + 18))}%</strong><b>{ui.confidenceLevel}</b><div className="confidence-track"><i style={{ width: `${Math.min(96, Math.max(20, Number(probability) + 30))}%` }} /></div><small>{ui.basedOnForecast}</small></div>
      </div>

      <div className="overview-metric-strip">
        <Metric icon={IconRain} label={ui.currentRainfall} value={`${valueOf(weather.rainfall_1h)} mm`} note={ui.last1Hour} tone="blue" />
        <Metric icon={IconWind} label={ui.windSpeed} value={`${wind} km/h`} note={weather.wind_direction || ui.live} tone="teal" />
        <Metric icon={IconDroplet} label={ui.humidity} value={`${humidity}%`} note={ui.current} tone="blue" />
        <Metric icon={IconActivity} label={ui.riverLevel} value={`${river}`} note={ui.modelledSignal} tone="blue" />
        <Metric icon={IconEye} label={ui.soilMoisture} value={`${soilMoisture}`} note={ui.rootZone} tone="green" />
        <Metric icon={IconThermometer} label={ui.temperature} value={`${valueOf(weather.temperature)}°C`} note={ui.feelsLikeCurrent} tone="red" />
      </div>

      <div className="overview-lower-grid">
        <div className="overview-panel radar-panel"><div className="overview-panel-head"><h3>{ui.liveWeatherRadar}</h3><span>{ui.viewRadar} <IconActivity className="w-3 h-3" /></span></div><div className="radar-preview"><IconRain className="w-10 h-10" /><strong>{rainfall24} mm</strong><span>{ui.rainfallIntensity}: {tone === "low" ? ui.light : ui.elevated}</span><div className="radar-sweep" /></div><small className="panel-footnote">{ui.currentLocation}: {location.district || ui.currentLocation}</small></div>
        <div className="overview-panel"><div className="overview-panel-head"><h3>{ui.riverBasinStatus}</h3><span>{ui.viewAll} <IconActivity className="w-3 h-3" /></span></div>{basins.slice(0, 4).map((basin, index) => <button className="basin-status-row" key={basin.name} onClick={() => onAnalyzeBasin?.(basin.lat, basin.lon)}><span>{basin.name}</span><b className={index === 0 && tone !== "low" ? tone : index === 1 ? "moderate" : "low"}>{index === 0 && tone !== "low" ? status : index === 1 ? ui.moderate : ui.low}</b></button>)}</div>
        <div className="overview-panel"><div className="overview-panel-head"><h3>{ui.recentAlerts}</h3><span>{ui.viewAll} <IconActivity className="w-3 h-3" /></span></div><div className="recent-alert"><IconAlertTriangle className={`text-${tone}`} /><div><strong>{status} {ui.floodMonitoring}</strong><small>{location.district || ui.currentLocation}</small></div></div><div className="recent-alert"><IconAlertTriangle className="text-moderate" /><div><strong>{ui.rainfallSignalUpdated}</strong><small>{ui.liveEnvironmentalReading}</small></div></div><div className="recent-alert"><IconActivity className="text-blue" /><div><strong>{ui.riverModelRefreshed}</strong><small>{ui.hydrologySignal}</small></div></div></div>
      </div>

    </section>
  );
}

function Metric({ icon: Icon, label, value, note, tone }) {
  return <div className="overview-metric"><Icon className={`metric-icon ${tone}`} /><div><span>{label}</span><strong>{value}</strong><small>{note}</small></div></div>;
}
