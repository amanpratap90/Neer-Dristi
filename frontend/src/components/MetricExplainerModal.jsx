import React, { useEffect } from "react";
import { IconHelp, IconClose, IconCheck, IconAlertTriangle } from "./Icons";

export default function MetricExplainerModal({ metric, language = "en", onClose }) {
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!metric) return null;

  const translation = metric.translations?.[language] || {};
  const name = translation.name || metric.name || metric.key;
  const description = translation.description || metric.description || "Detailed parameter used in ChetakAI hydrodynamic & flood prediction pipeline.";
  const floodImportance = metric.flood_importance || "Critical variable for predicting peak water stage, catchment saturation, and overland runoff.";
  const calculationMethod = metric.calculation_method || "Calculated from spatial raster contracts and machine learning feature pipelines.";
  const thresholds = metric.thresholds || null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card animate-scale-up" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-badge-group">
            <span className="modal-category-tag">{metric.category || "Physical Telemetry"}</span>
            {metric.is_ai_estimate ? (
              <span className="badge-ai-estimate">AI Regional Estimate</span>
            ) : (
              <span className="badge-sensor-verified">Sensor Verified</span>
            )}
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close">
            <IconClose className="w-5 h-5" />
          </button>
        </div>

        <div className="modal-title-row">
          <div className="modal-icon-pill">
            <IconHelp className="w-5 h-5 text-copper" />
          </div>
          <div>
            <h3 className="modal-title">{name}</h3>
            <div className="modal-current-val">
              Current Telemetry: <strong className="text-teal">{metric.value ?? "—"} {metric.unit || ""}</strong>
            </div>
          </div>
        </div>

        <div className="modal-body-content">
          <div className="modal-section">
            <h4 className="modal-section-title">Plain Language Definition</h4>
            <p className="modal-text">{description}</p>
          </div>

          <div className="modal-section">
            <h4 className="modal-section-title">Significance in Flood Prediction</h4>
            <p className="modal-text">{floodImportance}</p>
          </div>

          <div className="modal-section">
            <h4 className="modal-section-title">Measurement & Calculation Method</h4>
            <div className="modal-method-box">
              <p className="modal-text-sm">{calculationMethod}</p>
              {metric.estimation_source && (
                <div className="modal-provenance-note">
                  <strong>Source Provenance:</strong> {metric.estimation_source}
                </div>
              )}
            </div>
          </div>

          {thresholds && (
            <div className="modal-section">
              <h4 className="modal-section-title">Hazard & Safety Thresholds</h4>
              <div className="thresholds-grid">
                {Object.entries(thresholds).map(([lvl, range]) => (
                  <div key={lvl} className={`threshold-item threshold-${lvl}`}>
                    <span className="threshold-level">{lvl.toUpperCase()}:</span>
                    <span className="threshold-range">{range}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn-primary" onClick={onClose}>
            Understood
          </button>
        </div>
      </div>
    </div>
  );
}
