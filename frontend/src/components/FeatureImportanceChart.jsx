import React from "react";
import { IconLayers, IconHelp } from "./Icons";

export default function FeatureImportanceChart({ evidence = [], onExplain }) {
  const topFeatures = evidence.slice(0, 6);

  const featureLabels = {
    reservoir_area_km2: "Upstream Reservoir Storage Area",
    river_area_km2: "Mainstem River Surface Area",
    basin_area_km2: "Total Watershed Catchment Area",
    river_length_km: "Active Drainage Network Length",
    rainfall_sum_mm: "Total Integrated Precipitation",
    river_area_fraction_pct: "River Surface Area Density",
    obs_rain_variability_proxy: "Doppler Radar Rain Variability",
    reservoir_count: "Catchment Reservoir Count",
    rainfall_std_mm: "Precipitation Standard Deviation",
    radar_spatial_variability_proxy: "Radar Spatial Variability"
  };

  const maxImportance = Math.max(...topFeatures.map(f => f.model_importance || 0.01), 0.06);

  return (
    <div className="feature-importance-card">
      <div className="importance-header">
        <div className="importance-title-wrap">
          <IconLayers className="w-5 h-5 text-copper" />
          <h3 className="importance-title">Top ML Decision Drivers</h3>
        </div>
        <button
          className="btn-help-sm"
          onClick={() => onExplain({
            key: "model_evidence",
            name: "Machine Learning Permutation Importance",
            category: "Model Interpretability",
            value: "Ensemble Feature Weights",
            description: "Permutation feature importance calculated across the random forest & gradient boosting trees, quantifying which physical factors contributed most to the flood probability.",
            flood_importance: "Provides scientific transparency for why the AI flagged this location as high risk.",
            calculation_method: "Mean decrease in accuracy (MDA) across out-of-fold validation splits."
          })}
          title="Explain ML decision drivers"
        >
          <IconHelp className="w-4 h-4" />
        </button>
      </div>

      <div className="importance-bars-list">
        {topFeatures.map((feat, idx) => {
          const importancePct = ((feat.model_importance || 0) / maxImportance) * 100;
          const label = featureLabels[feat.feature] || feat.feature.replace(/_/g, " ");

          return (
            <div key={idx} className="importance-bar-item">
              <div className="bar-label-row">
                <span className="bar-feat-name">{label}</span>
                <span className="bar-feat-val">{(feat.model_importance * 100).toFixed(1)}% weight</span>
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
