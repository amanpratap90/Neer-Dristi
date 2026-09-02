import React from "react";

function Row({ label, value }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="kv-row">
      <span className="kv-label">{label}</span>
      <span className="kv-value">{value}</span>
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
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: digits });
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
          <Row label="Forecast confidence" value={forecast.confidence_label || `${forecast.confidence}%`} />
        </Block>

        <Block title="Terrain">
          <Row label="Elevation" value={`${fmt(terrain.elevation_m, 0)} m`} />
          <Row label="Slope" value={`${fmt(terrain.mean_slope_deg)}°`} />
          <Row label="Flow accumulation" value={fmt(terrain.flow_accumulation, 0)} />
          <Row label="Distance to river" value={`${fmt(terrain.distance_to_river_km)} km`} />
          <Row label="Relief" value={`${fmt(terrain.relief_m, 0)} m`} />
          <Row label="Terrain risk" value={terrain.risk} />
        </Block>

        <Block title="Hydrology">
          <Row label="River level" value={`${fmt(hydrology.river_level, 2)} m`} />
          <Row label="River level change" value={`${hydrology.river_level_change > 0 ? "+" : ""}${fmt(hydrology.river_level_change, 2)} m`} />
          <Row label="River level trend" value={hydrology.river_level_trend} />
          <Row label="Hydrological loading" value={hydrology.hydrological_loading} />
        </Block>

        <Block title="Remote sensing">
          <Row label="Radar rainfall" value={`${fmt(remote.radar_rainfall_mm)} mm`} />
          <Row label="Satellite rainfall" value={`${fmt(remote.satellite_rainfall_mm)} mm`} />
          <Row label="Radar available" value={yesNo(remote.radar_available)} />
          <Row label="Satellite available" value={yesNo(remote.satellite_available)} />
          <Row label="Gauge available" value={yesNo(remote.gauge_available)} />
          <Row label="River available" value={yesNo(remote.river_available)} />
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
          <Row label="Roads in risk zone" value={`${fmt(exposure.roads_exposed_km)} km`} />
          <Row label="Major roads" value={`${fmt(exposure.major_roads_km)} km`} />
          <Row label="Railway" value={`${fmt(exposure.railway_km)} km`} />
          <Row label="Bridges" value={fmt(exposure.bridges_exposed, 0)} />
          <Row label="Culverts" value={fmt(exposure.culverts, 0)} />
          <Row label="Buildings" value={fmt(exposure.buildings_exposed, 0)} />
          <Row label="Critical buildings" value={fmt(exposure.critical_buildings, 0)} />
          <Row label="Schools" value={fmt(exposure.schools_exposed, 0)} />
          <Row label="Hospitals / health" value={fmt(exposure.hospitals_exposed, 0)} />
          <Row label="Relief centers" value={fmt(exposure.relief_centers, 0)} />
          <Row label="Power infrastructure" value={fmt(exposure.power_infrastructure, 0)} />
          <Row label="Water infrastructure" value={fmt(exposure.water_infrastructure, 0)} />
          <Row label="Communication towers" value={fmt(exposure.communication_towers, 0)} />
          <Row label="Exposure value" value={`₹${fmt(exposure.infrastructure_value_cr)} Cr`} />
          <Row label="Infrastructure risk" value={exposure.infrastructure_risk} />
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
