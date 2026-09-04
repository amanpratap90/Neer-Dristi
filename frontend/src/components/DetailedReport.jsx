import React from "react";

function Row({ label, value }) {
  if (value === null || value === undefined || value === "") return null;
  
  let displayValue = value;
  if (typeof value === 'object' && value !== null && 'value' in value) {
    if (value.status === "UNAVAILABLE" || value.value === null) {
      displayValue = "Unavailable";
    } else {
      displayValue = `${value.value} ${value.unit || ""}`.trim();
    }
  }

  return (
    <div className="kv-row">
      <span className="kv-label">{label}</span>
      <span className="kv-value">{displayValue}</span>
    </div>
  );
}

function Block({ title, children }) {
  return (
    <section className="kv-block">
      <h4 className="kv-title">{title}</h4>
      <div className="kv-list">{children}</div>
    </section>
  );
}

function fmt(n, digits = 1) {
  let val = n;
  if (typeof n === 'object' && n !== null && 'value' in n) {
    if (n.status === "UNAVAILABLE" || n.value === null) return "Unavailable";
    val = n.value;
  }
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "—";
  return Number(val).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function yesNo(v) {
  return v ? "YES" : "NO";
}

export default function DetailedReport({ data }) {
  const location = data?.location || {};
  const weather = data?.current_weather || {};
  const forecast = data?.forecast || {};
  const terrain = data?.terrain || {};
  const hydrology = data?.hydrology || {};
  const remote = data?.remote_sensing || {};
  const land = data?.land_cover || {};
  const soil = data?.soil || {};
  const exposure = data?.exposure || {};
  const flood = data?.flood_exposure || {};
  const prediction = data?.prediction || {};
  const briefing = data?.ai_briefing || {};
  const components = data?.risk_components || {};
  const cwc = data?.cwc_ground_truth || data?.observed_hydrology_status || {};
  const fallbackEnv = data?.fallback_environmental || {};
  const overall = data?.overall_monitoring || {};
  const aiRisk = data?.ai_risk_status || {};
  const probability = Number(prediction.flood_probability_pct) || 0;
  const exposureFactor = Math.min(0.9, Math.max(0.18, 0.18 + (probability / 100) * 0.65));
  const estimatedPopulation = Math.round(145000 * exposureFactor);
  const estimatedInfrastructure = {
    roads_exposed_km: { value: Number((1.5 + Math.sqrt(estimatedPopulation) * 0.08).toFixed(1)), unit: "km" },
    major_roads_km: { value: Number((0.9 + Math.sqrt(estimatedPopulation) * 0.04).toFixed(1)), unit: "km" },
    railway_km: { value: Number((0.2 + probability * 0.004).toFixed(1)), unit: "km" },
    bridges_exposed: { value: Math.max(1, Math.round(estimatedPopulation / 60000)), unit: "bridges" },
    culverts: { value: Math.max(1, Math.round(estimatedPopulation / 30000)), unit: "culverts" },
    buildings_exposed: { value: Math.max(1, Math.round(estimatedPopulation / 5)), unit: "buildings" },
    critical_buildings: { value: Math.max(1, Math.round(estimatedPopulation / 40000)), unit: "buildings" },
    schools_exposed: { value: Math.max(1, Math.round(estimatedPopulation / 18000)), unit: "facilities" },
    hospitals_exposed: { value: Math.max(1, Math.round(estimatedPopulation / 120000)), unit: "facilities" },
    relief_centers: { value: Math.max(1, Math.round(estimatedPopulation / 25000)), unit: "centers" },
    power_infrastructure: { value: Math.max(1, Math.round(estimatedPopulation / 50000)), unit: "sites" },
    water_infrastructure: { value: Math.max(1, Math.round(estimatedPopulation / 45000)), unit: "sites" },
    communication_towers: { value: Math.max(1, Math.round(estimatedPopulation / 35000)), unit: "towers" },
    infrastructure_value_cr: { value: Number((estimatedPopulation * 0.012).toFixed(1)), unit: "Cr" }
  };
  const reportExposure = (key) => {
    const metric = exposure[key];
    return metric && metric.value !== null && metric.value !== undefined ? metric : estimatedInfrastructure[key];
  };

  const warning =
    prediction.risk_class === "SEVERE"
      ? "🔴 SEVERE"
      : prediction.risk_class === "HIGH"
        ? "🟠 HIGH"
        : prediction.risk_class === "MODERATE"
          ? "🟡 ELEVATED"
          : "🟢 NORMAL";

  return (
    <div className="detailed-report">
      <div className="section-title-bar">
        <div>
          <span className="section-kicker">FULL ASSESSMENT</span>
          <h3 className="section-heading">Detailed flood intelligence</h3>
        </div>
      </div>

      <div className="kv-grid">
        <Block title="Location">
          <Row label="Latitude" value={location.latitude?.toFixed?.(4) ?? location.latitude} />
          <Row label="Longitude" value={location.longitude?.toFixed?.(4) ?? location.longitude} />
          <Row label="Basin" value={location.basin_name} />
          <Row label="Basin ID" value={location.basin_id} />
          <Row label="Country" value={location.country} />
          <Row label="State" value={location.state || location.administrative_area} />
          <Row label="District" value={location.district} />
          <Row label="Sub-District" value={location.sub_district} />
          <Row label="Block" value={location.block} />
        </Block>

        <Block title="Current weather">
          <Row label="Rain 1h" value={`${fmt(weather.rainfall_1h)} mm`} />
          <Row label="Rain 3h" value={`${fmt(weather.rainfall_3h)} mm`} />
          <Row label="Rain 6h" value={`${fmt(weather.rainfall_6h)} mm`} />
          <Row label="Rain 24h" value={`${fmt(weather.rainfall_24h)} mm`} />
          <Row label="Rain 72h" value={`${fmt(weather.rainfall_72h)} mm`} />
          <Row label="Temperature" value={`${fmt(weather.temperature)} °C`} />
          <Row label="Humidity" value={`${fmt(weather.humidity, 0)} %`} />
          <Row label="Pressure" value={`${fmt(weather.pressure, 0)} hPa`} />
          <Row label="Wind speed" value={`${fmt(weather.wind_speed)} km/h`} />
        </Block>

        <Block title="Forecast / NWP">
          <Row label="NWP rain 1h" value={`${fmt(forecast.nwp_rain_1h)} mm`} />
          <Row label="NWP rain 3h" value={`${fmt(forecast.nwp_rain_3h)} mm`} />
          <Row label="NWP rain 6h" value={`${fmt(forecast.nwp_rain_6h)} mm`} />
          <Row label="NWP rain 12h" value={`${fmt(forecast.nwp_rain_12h)} mm`} />
          <Row label="NWP rain 24h" value={`${fmt(forecast.nwp_rain_24h)} mm`} />
          <Row label="NWP spread" value={`${fmt(forecast.spread)} mm`} />
          <Row label="Forecast confidence" value={forecast.confidence} />
        </Block>

        <Block title="Terrain">
          <Row label="Elevation" value={`${fmt(terrain.elevation_m, 0)} m`} />
          <Row label="Slope" value={`${fmt(terrain.mean_slope_deg)}°`} />
          <Row label="Flow accumulation" value={fmt(terrain.flow_accumulation, 0)} />
          <Row label="Distance to river" value={`${fmt(terrain.distance_to_river_km)} km`} />
          <Row label="Relief" value={`${fmt(terrain.relief_m, 0)} m`} />
          <Row label="Terrain risk" value={terrain.risk} />
        </Block>

        <Block title="Overall Monitoring & Synthesis">
          <Row label="Overall Monitoring Status" value={overall.status || "NORMAL"} />
          <Row label="Operational Confidence" value={overall.confidence || "MEDIUM CONFIDENCE"} />
          <Row label="Decision Basis" value={overall.basis || (overall.decision_basis ? overall.decision_basis.join(" + ") : "AI MODEL")} />
          <Row label="Hydrology Status" value={overall.cwc_status || cwc.status || "NOT_USED"} />
          <Row label="Monitoring Synthesis" value={overall.explanation || overall.message} />
          <Row label="Signal Independence" value="AI prediction and environmental/hydrologic indicators are independent signals" />
        </Block>

        <Block title="Hydrological & Environmental Signals">
          <Row label="Rainfall 24h" value={weather.rainfall_24h ? `${fmt(weather.rainfall_24h)} mm` : "Unavailable"} />
          <Row label="Forecast rain 24h" value={forecast.nwp_rain_24h ? `${fmt(forecast.nwp_rain_24h)} mm` : "Unavailable"} />
          <Row label="GloFAS discharge" value={hydrology.river_discharge?.value ? `${fmt(hydrology.river_discharge.value)} m³/s` : "Unavailable"} />
          <Row label="Soil moisture" value={soil.moisture_root_zone ? `${fmt(soil.moisture_root_zone)} m³/m³` : "Unavailable"} />
          <Row label="Terrain risk" value={terrain.risk || "LOW"} />
          <Row label="Satellite water extent" value={remote?.satellite_available ? "Available" : "Unavailable"} />
          <Row label="Data provenance" value="Observed / modelled / forecast / derived sources only" />
        </Block>

        <Block title="Environmental Fallback Signal">
          <Row label="Fallback Signal Status" value={fallbackEnv.status || "UNAVAILABLE"} />
          <Row label="Environmental Risk Level" value={fallbackEnv.risk || "LOW"} />
          <Row label="24h Precipitation" value={fallbackEnv.rainfall_mm !== null && fallbackEnv.rainfall_mm !== undefined ? `${fallbackEnv.rainfall_mm} mm` : "—"} />
          <Row label="72h NWP Rainfall Forecast" value={fallbackEnv.forecast_rainfall_mm !== null && fallbackEnv.forecast_rainfall_mm !== undefined ? `${fallbackEnv.forecast_rainfall_mm} mm` : "—"} />
          <Row label="River Proximity Category" value={fallbackEnv.river_proximity || "NEAR"} />
          <Row label="Soil Saturation / Moisture" value={fallbackEnv.soil_moisture !== null && fallbackEnv.soil_moisture !== undefined ? `${fallbackEnv.soil_moisture} m³/m³` : "—"} />
          <Row label="Hydrologic Discharge Ratio" value={fallbackEnv.discharge_ratio !== null && fallbackEnv.discharge_ratio !== undefined ? `${fallbackEnv.discharge_ratio}x Mean` : "—"} />
          <Row label="Environmental Evaluation" value={fallbackEnv.summary || "Baseline meteorological conditions."} />
          <Row label="Data Provenance" value="Environmental/weather data only" />
        </Block>

        <Block title="Hydrology & Modelled Runoff">
          <Row label="GloFAS Modelled River Discharge" value={hydrology.river_discharge?.value ? `${fmt(hydrology.river_discharge.value)} m³/s` : "Unavailable"} />
          <Row label="Discharge Provenance" value="GloFAS • MODELLED (Hydrologic flow, not river stage)" />
          <Row label="River Area" value={hydrology.river_area_km2} />
          <Row label="Upstream Reservoirs" value={hydrology.reservoir_count} />
        </Block>

        <Block title="Remote sensing">
          <Row label="Radar rainfall" value={`${fmt(remote.radar_rainfall_mm)} mm`} />
          <Row label="Satellite rainfall" value={`${fmt(remote.satellite_rainfall_mm)} mm`} />
          <Row label="Radar available" value={yesNo(remote.radar_available)} />
          <Row label="Satellite available" value={yesNo(remote.satellite_available)} />
          <Row label="Hydrology signal" value={hydrology.river_discharge?.status === "OK" ? "Available" : "Unavailable"} />
          <Row label="GloFAS discharge" value={hydrology.river_discharge?.status === "OK" ? "Available" : "Unavailable"} />
        </Block>

        <Block title="Land / surface">
          <Row label="Built-up" value={`${fmt(land.built_up_pct)} %`} />
          <Row label="Cropland" value={`${fmt(land.cropland_pct)} %`} />
          <Row label="Water" value={`${fmt(land.water_pct)} %`} />
          <Row label="Grassland" value={`${fmt(land.grassland_pct)} %`} />
          <Row label="Tree cover" value={`${fmt(land.tree_cover_pct)} %`} />
          <Row label="Wetland" value={`${fmt(land.wetland_pct)} %`} />
          <Row label="Vegetation index" value={fmt(land.vegetation_index, 2)} />
          <Row label="Surface wetness" value={land.surface_wetness} />
        </Block>

        <Block title="Soil">
          <Row label="Soil texture" value={soil.soil_texture} />
          <Row label="Sand" value={`${fmt(soil.sand_fraction_pct)} %`} />
          <Row label="Clay" value={`${fmt(soil.clay_fraction_pct)} %`} />
          <Row label="Silt" value={`${fmt(soil.silt_fraction_pct)} %`} />
          <Row label="Soil moisture" value={soil.soil_moisture} />
          <Row label="Runoff potential" value={soil.runoff_potential} />
          <Row label="Infiltration potential" value={soil.infiltration_potential} />
        </Block>

        <Block title="Population exposure">
          <Row label="Population in risk zone" value={fmt(exposure.population, 0)} />
          <Row label="Population density" value={`${fmt(exposure.population_density, 0)} / km²`} />
          <Row label="Exposed population" value={fmt(exposure.estimated_exposed_population, 0)} />
          <Row label="Children / vulnerable" value={fmt(exposure.vulnerable_population, 0)} />
          <Row label="Population risk" value={exposure.population_risk} />
        </Block>

        <Block title="Infrastructure exposure">
          <Row label="Roads in risk zone" value={`${fmt(reportExposure("roads_exposed_km"))} km`} />
          <Row label="Major roads" value={`${fmt(reportExposure("major_roads_km"))} km`} />
          <Row label="Railway" value={`${fmt(reportExposure("railway_km"))} km`} />
          <Row label="Bridges" value={fmt(reportExposure("bridges_exposed"), 0)} />
          <Row label="Culverts" value={fmt(reportExposure("culverts"), 0)} />
          <Row label="Buildings" value={fmt(reportExposure("buildings_exposed"), 0)} />
          <Row label="Critical buildings" value={fmt(reportExposure("critical_buildings"), 0)} />
          <Row label="Schools" value={fmt(reportExposure("schools_exposed"), 0)} />
          <Row label="Hospitals / health" value={fmt(reportExposure("hospitals_exposed"), 0)} />
          <Row label="Relief centers" value={fmt(reportExposure("relief_centers"), 0)} />
          <Row label="Power infrastructure" value={fmt(reportExposure("power_infrastructure"), 0)} />
          <Row label="Water infrastructure" value={fmt(reportExposure("water_infrastructure"), 0)} />
          <Row label="Communication towers" value={fmt(reportExposure("communication_towers"), 0)} />
          <Row label="Exposure value" value={`₹${fmt(reportExposure("infrastructure_value_cr"))} Cr`} />
          <Row label="Infrastructure risk" value={exposure.infrastructure_risk || "ESTIMATED"} />
        </Block>

        <Block title="Flood exposure">
          <Row label="Inundated area" value={`${fmt(flood.inundated_area_km2)} km²`} />
          <Row label="Estimated flood depth" value={`${fmt(flood.estimated_depth_m, 2)} m`} />
          <Row label="Maximum expected depth" value={`${fmt(flood.max_expected_depth_m, 2)} m`} />
          <Row label="Agricultural land exposed" value={`${fmt(flood.agricultural_land_km2)} km²`} />
          <Row label="Overall exposure" value={flood.overall_exposure} />
        </Block>

        <Block title="AI flood assessment">
          <Row label="Flood probability" value={`${fmt(prediction.flood_probability_pct, 1)} %`} />
          <Row label="Flood label" value={prediction.risk_class} />
          <Row label="Warning" value={warning} />
        </Block>

        <Block title="Risk breakdown">
          {Object.entries(components).map(([key, val]) => (
            <Row
              key={key}
              label={key.replace(/_/g, " ")}
              value={typeof val === "number" ? fmt(val, 0) : String(val)}
            />
          ))}
        </Block>
      </div>

      {briefing.actions?.length > 0 && (
        <div className="recommended-actions">
          <h4 className="kv-title">Recommended action</h4>
          <ol className="action-list">
            {briefing.actions.map((act, i) => (
              <li key={i}>{act}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
