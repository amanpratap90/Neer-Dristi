import React from "react";
import { IconLayers, IconHelp } from "./Icons";

export default function FeatureImportanceChart({ evidence = [], onExplain }) {
  const topFeatures = evidence.slice(0, 6);

  const featureLabels = {
    rainfall_72h_mm: "72h Cumulative Rainfall",
    rainfall_24h_mm: "24h Rainfall",
    rainfall_12h_mm: "12h Rainfall",
    rainfall_6h_mm: "6h Rainfall",
    rainfall_3h_mm: "3h Rainfall",
    rainfall_1h_mm: "1h Rainfall",
    scs_runoff_depth_mm: "SCS Runoff Depth",
    root_zone_soil_moisture: "Root Zone Soil Moisture",
    soil_moisture_0_to_1cm: "Surface Soil Moisture",
    soil_moisture_1_to_3cm: "Shallow Soil Moisture",
    soil_moisture_3_to_9cm: "Mid Soil Moisture",
    soil_moisture_9_to_27cm: "Deep Soil Moisture",
    elevation_m: "Elevation",
    slope_deg: "Terrain Slope",
    relief_m: "Relief",
    drainage_density_km_km2: "Drainage Density",
    scs_curve_number: "SCS Curve Number",
    scs_potential_retention_s_mm: "Soil Retention Capacity",
    glofas_discharge_ratio: "GloFAS Discharge Ratio",
    glofas_discharge_exceedance_pct: "Discharge Exceedance",
    antecedent_precipitation_index: "Antecedent Precipitation Index",
    evapotranspiration_72h: "72h Evapotranspiration",
    soil_clay_pct: "Clay Content",
    soil_sand_pct: "Sand Content",
    soil_silt_pct: "Silt Content",
    lc_cropland_pct: "Cropland Area",
    lc_built_up_pct: "Built-up Area",
    lc_water_pct: "Surface Water Area",
    forecast_72h_mm: "72h Forecast Rainfall"
  };

  const maxImportance = Math.max(...topFeatures.map(f => f.model_importance || 0.01), 0.06);

  if (topFeatures.length === 0) {
    return (
      <div className="feature-importance-card">
        <div className="importance-header">
          <div className="importance-title-wrap">
            <IconLayers className="w-5 h-5 text-copper" />
            <h3 className="importance-title">Top ML Prediction Drivers</h3>
          </div>
        </div>
        <div className="importance-bars-list" style={{ padding: "1rem", textAlign: "center", color: "#888" }}>
          Model drivers unavailable — prediction may have failed or features were insufficient.
        </div>
      </div>
    );
  }

  return (
    <div className="feature-importance-card">
      <div className="importance-header">
        <div className="importance-title-wrap">
          <IconLayers className="w-5 h-5 text-copper" />
          <h3 className="importance-title">Top ML Prediction Drivers</h3>
        </div>
        <button
          className="btn-help-sm"
          onClick={() => onExplain({
            key: "model_evidence",
            name: "ML Feature Importance",
            category: "Model Interpretability",
            value: "Ensemble Feature Weights",
            description: "Relative feature importance from the random forest ensemble. These values indicate which physical factors the model weighted most heavily when making this prediction. They are NOT direct percentage contributions to flood probability.",
            flood_importance: "Provides scientific transparency for the model's reasoning.",
            calculation_method: "Combined global feature importance and local decision path contribution across 30 ensemble trees."
          })}
          title="Explain ML decision drivers"
        >
          <IconHelp className="w-4 h-4" />
        </button>
      </div>

      <p style={{ fontSize: "0.7rem", color: "#999", margin: "0 0.75rem 0.5rem", fontStyle: "italic" }}>
        Relative feature importance; not direct percentage contribution to flood probability.
      </p>

      <div className="importance-bars-list">
        {topFeatures.map((feat, idx) => {
          const importancePct = ((feat.model_importance || 0) / maxImportance) * 100;
          const label = featureLabels[feat.feature] || feat.feature.replace(/_/g, " ");

          return (
            <div key={idx} className="importance-bar-item">
              <div className="bar-label-row">
                <span className="bar-feat-name">{label}</span>
                <span className="bar-feat-val">{(feat.model_importance * 100).toFixed(1)}% importance</span>
              </div>
              <div className="bar-track">
                <div
                  className="bar-fill animate-grow-width"
                  style={{ width: `${Math.min(100, Math.max(10, importancePct))}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
