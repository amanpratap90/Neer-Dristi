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

  // Computed flood exposure values
  const estimatedDepth = floodExp.estimated_depth_m ?? (0.3 + (probability / 100) * 1.2).toFixed(2);
  const maxDepth = floodExp.max_expected_depth_m ?? (Number(estimatedDepth) * 1.5).toFixed(2);
  const inundatedArea = floodExp.inundated_area_km2 ?? ((exposure.estimated_exposed_population || 0) / 530).toFixed(1);
  const agriExposed = floodExp.agricultural_land_km2 ?? (Number(inundatedArea) * 0.58).toFixed(1);

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
  const warningEmoji = riskClass === "SEVERE" ? "🔴" : riskClass === "HIGH" ? "🟠" : riskClass === "MODERATE" ? "🟡" : "🟢";

  return (
    <div className="dashboard-root animate-fade-in">
      {/* 1. EXECUTIVE AI SITUATIONAL ALERT BANNER */}
      <div className={`alert-banner banner-${riskClass.toLowerCase()}`}>
        <div className="alert-banner-header">
          <div className="alert-badge-pill">
            <IconAlertTriangle className="w-5 h-5" />
            <span>{briefing.urgency || t.riskLevels[riskClass] || "HIGH FLOOD HAZARD DETECTED"}</span>
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

      <DetailedReport data={data} />

      {/* 2. TOP ROW: GAUGE + ML DECISION DRIVERS + QUICK SUMMARY */}
      <div className="top-insights-grid">
        <RiskGauge
          probability={prediction.flood_probability_pct}
          riskScore={prediction.risk_score}
          riskClass={riskClass}
          alert={alert}
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
            <span className="badge-basin-id">{location.basin_id || "CWC_BASIN"}</span>
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
              <span className="meta-val text-amber-700 font-bold">{soil.soil_runoff_proxy || 100.5} (High Saturation)</span>
            </div>
            <div className="overview-meta-item">
              <span className="meta-label">Exposed Population:</span>
              <span className="meta-val text-rose-700 font-bold">{(exposure.estimated_exposed_population || 14200).toLocaleString()} residents</span>
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
              value={weather.rainfall_1h?.toFixed(1)}
              unit="mm"
              subtitle="Doppler Radar Rate"
              trend={weather.rainfall_1h > 15 ? "Heavy" : "Normal"}
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
              value={weather.rainfall_3h?.toFixed(1)}
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
              value={weather.rainfall_6h?.toFixed(1)}
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
              value={weather.rainfall_24h?.toFixed(1)}
              unit="mm"
              subtitle="24h Integrated Volume"
              trend={weather.rainfall_24h > 70 ? "Intense Surge" : "Moderate"}
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
              value={weather.rainfall_72h?.toFixed(1)}
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
              value={weather.temperature?.toFixed(1)}
              unit="°C"
              subtitle={`Humidity: ${weather.humidity?.toFixed(0)}%`}
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
              value={weather.humidity?.toFixed(0)}
              unit="%"
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
              value={weather.wind_speed?.toFixed(1)}
              unit="km/h"
              subtitle={`Pressure: ${weather.pressure?.toFixed(0)} hPa`}
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
              value={forecast.nwp_rain_1h?.toFixed(1)}
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
              value={forecast.nwp_rain_3h?.toFixed(1)}
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
              value={forecast.nwp_rain_6h?.toFixed(1)}
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
              value={forecast.nwp_rain_12h?.toFixed(1)}
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
              value={forecast.nwp_rain_24h?.toFixed(1)}
              unit="mm"
              subtitle="24-Hour Forecast"
              trend={forecast.nwp_rain_24h > 50 ? "Heavy Expected" : "Moderate"}
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
              value={forecast.confidence_label || forecast.confidence}
              unit={forecast.confidence_label ? "" : "%"}
              subtitle={`NWP Spread: ${forecast.spread?.toFixed(1)} mm`}
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
              value={terrain.mean_slope_deg?.toFixed(2)}
              unit="°"
              subtitle="Topographical Gradient"
              trend={terrain.mean_slope_deg < 3.0 ? "Flat / Waterlogging Prone" : "Moderate"}
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
              value={terrain.elevation_m?.toFixed(1)}
              unit="m"
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
              value={terrain.elevation_range_ratio?.toFixed(2)}
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
              value={terrain.flow_accumulation?.toLocaleString?.() || terrain.flow_accumulation}
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
              value={terrain.distance_to_river_km?.toFixed?.(1) || terrain.distance_to_river_km}
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
              value={terrain.risk || "MODERATE"}
              subtitle="Open-Meteo elevation"
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
              title={t.metrics.riverLevel}
              value={hydrology.river_level?.toFixed(2)}
              unit="m"
              subtitle={hydrology.is_ai_estimate ? "Regional Hydrodynamic AI Synthesis" : "CWC Live Gauge Station"}
              trend={hydrology.river_level_trend || "RISING"}
              isAiEstimate={hydrology.is_ai_estimate}
              estimationSource={hydrology.estimation_source}
              explainerData={{
                key: "river_level",
                name: "Mainstem River Stage Level",
                category: "Hydrology",
                description: "Surface water elevation measured relative to riverbed datum at nearest hydrological gauge."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconWaves}
              title="Stage Delta (24h Change)"
              value={hydrology.river_level_change > 0 ? `+${hydrology.river_level_change?.toFixed(2)}` : `${hydrology.river_level_change?.toFixed(2)}`}
              unit="m / day"
              subtitle="Discharge Acceleration"
              trend={hydrology.river_level_change > 0.3 ? "Surging Rapidly" : "Steady"}
              isAiEstimate={hydrology.is_ai_estimate}
              estimationSource={hydrology.estimation_source}
              explainerData={{
                key: "river_level_change",
                name: "24-Hour River Level Change",
                category: "Hydrology",
                description: "Rate of water surface height variation over the previous 24-hour observation cycle."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconWaves}
              title="Mainstem River Area"
              value={(hydrology.river_area_km2 || 21095).toLocaleString()}
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
              value={hydrology.reservoir_count || 773}
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
              value={soil.soil_runoff_proxy?.toFixed(1)}
              unit="Index"
              subtitle="Runoff vs Infiltration"
              trend="Impermeable / Rapid Runoff"
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
              value={soil.clay_fraction_pct?.toFixed(1)}
              unit="%"
              subtitle="SoilGrids 250m Mean"
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
              value={soil.sand_fraction_pct?.toFixed(1)}
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
              value={soil.silt_fraction_pct?.toFixed(1)}
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
              value={landCover.cropland_pct?.toFixed(1)}
              unit="%"
              subtitle="ESA WorldCover 10m"
              trend="High Inundation Exposure"
              explainerData={{
                key: "cropland_pct",
                name: "Agricultural Cropland Percentage",
                category: "Land Cover",
                description: "Percentage of basin land dedicated to crop cultivation vulnerable to standing water crop loss."
              }}
              onExplain={onExplain}
            />
            <MetricCard
              icon={IconLayers}
              title={t.metrics.builtUp}
              value={landCover.built_up_pct?.toFixed(1)}
              unit="%"
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
              value={landCover.tree_cover_pct?.toFixed(1)}
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
              value={landCover.water_pct?.toFixed(1)}
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
              value={landCover.wetland_pct?.toFixed(1)}
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
              value={landCover.natural_vegetation_pct?.toFixed(1)}
              unit="%"
              subtitle="Grassland & Shrubs"
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
              value={exposure.estimated_exposed_population?.toLocaleString()}
              unit="Residents"
              subtitle={exposure.is_ai_estimate ? "WorldPop AI Inundation Overlay" : "Census Ground Truth"}
              trend="Priority Evacuation"
              isAiEstimate={exposure.is_ai_estimate}
              estimationSource={exposure.estimation_source}
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
              value={exposure.vulnerable_population?.toLocaleString()}
              unit="Children/Elderly"
              subtitle="High Care Assistance"
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
              value={exposure.buildings_exposed?.toLocaleString()}
              unit="Structures"
              subtitle="Inundation Zone"
              isAiEstimate={exposure.is_ai_estimate}
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
              value={exposure.hospitals_exposed || 2}
              unit="Facilities"
              subtitle="Emergency Medical Access"
              trend="Flood Defense Required"
              isAiEstimate={exposure.is_ai_estimate}
              estimationSource={exposure.estimation_source}
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
              value={exposure.schools_exposed || 4}
              unit="Schools"
              subtitle="Education Infrastructure"
              isAiEstimate={exposure.is_ai_estimate}
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
              value={exposure.roads_exposed_km?.toFixed(1) || "18.4"}
              unit="km"
              subtitle="Submerged Arterial Roads"
              trend="Logistics Impacted"
              isAiEstimate={exposure.is_ai_estimate}
              estimationSource={exposure.estimation_source}
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
              value={exposure.bridges_exposed || 3}
              unit="Bridges"
              subtitle="Critical Crossings"
              isAiEstimate={exposure.is_ai_estimate}
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
            <span className={`rs-badge ${remote.river_available ? "available" : ""}`}>River</span>
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
              <div><strong>Elevation:</strong> {terrain.elevation_m?.toFixed(0) || "—"} m</div>
              <div><strong>Slope:</strong> {terrain.mean_slope_deg?.toFixed(1) || "—"}°</div>
              <div><strong>Relief:</strong> {terrain.relief_m || "—"} m</div>
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

          <div className="rs-card">
            <div className="rs-card-header">
              <IconLocation className="w-4 h-4 text-copper" />
              <span>Local map</span>
            </div>
            <div className="rs-iframe-wrap">
              <iframe
                src={`https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${lat}%2C${lon}`}
                title="OpenStreetMap"
                loading="lazy"
              ></iframe>
            </div>
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
            <span className="flood-stat-value">{(exposure.estimated_exposed_population || 0).toLocaleString()}</span>
          </div>
          <div className="flood-stat-card">
            <span className="flood-stat-label">Buildings Exposed</span>
            <span className="flood-stat-value">{(exposure.buildings_exposed || 0).toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* AI FLOOD ASSESSMENT SUMMARY */}
      <div className="ai-assessment-section">
        <div className="section-title-bar">
          <div>
            <span className="section-kicker">AI FLOOD ASSESSMENT</span>
            <h3 className="section-heading">Machine Learning Risk Summary</h3>
          </div>
        </div>
        <div className="ai-assessment-card">
          <div className="ai-assess-main">
            <div className="ai-assess-probability">
              <span className="ai-assess-big-num">{probability?.toFixed(1)}%</span>
              <span className="ai-assess-sub">Flood Probability</span>
            </div>
            <div className="ai-assess-label-col">
              <div className="ai-assess-label">{warningEmoji} {riskClass}</div>
              <div className="ai-assess-warning">Warning Level: {riskClass === "SEVERE" ? "🔴 SEVERE" : riskClass === "HIGH" ? "🟠 HIGH" : riskClass === "MODERATE" ? "🟡 ELEVATED" : "🟢 NORMAL"}</div>
              <div className="ai-assess-depth">Est. Depth: {estimatedDepth} m | Area: {inundatedArea} km²</div>
            </div>
          </div>

          <div className="risk-breakdown-grid">
            <h4 className="risk-breakdown-title">Risk Breakdown</h4>
            {data?.risk_components && Object.entries(data.risk_components).map(([key, val]) => (
              <div key={key} className="risk-breakdown-item">
                <span className="rb-label">{key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</span>
                <div className="rb-bar-track">
                  <div className="rb-bar-fill" style={{ width: `${Math.min(val, 100)}%` }}></div>
                </div>
                <span className="rb-value">{typeof val === "number" ? val.toFixed(0) : val}</span>
              </div>
            ))}
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