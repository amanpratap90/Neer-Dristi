import React from "react";
import { IconShield, IconHelp } from "./Icons";

export default function RiskGauge({ probability = 73.89, riskScore = 73.75, riskClass = "HIGH", alert = {}, onExplain }) {
  const prob = Number(probability) || 0;
  const score = Number(riskScore) || 0;

  // SVG Gauge calculations
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (prob / 100) * circumference;

  const colorMap = {
    LOW: { stroke: "#2e7d32", fill: "#e8f5e9", text: "text-emerald-600", label: "LOW RISK" },
    MODERATE: { stroke: "#f57c00", fill: "#fff3e0", text: "text-amber-600", label: "MODERATE RISK" },
    HIGH: { stroke: "#d32f2f", fill: "#ffebee", text: "text-rose-600", label: "HIGH RISK" },
    SEVERE: { stroke: "#b71c1c", fill: "#fce4ec", text: "text-red-700", label: "CRITICAL / SEVERE" }
  };

  const currentTheme = colorMap[riskClass] || colorMap.HIGH;

  return (
    <div className="risk-gauge-card">
      <div className="gauge-header">
        <div className="gauge-title-wrap">
          <IconShield className="w-5 h-5 text-copper" />
          <h3 className="gauge-title">Flood Risk Classification</h3>
        </div>
        <button
          className="btn-help-sm"
          onClick={() => onExplain({
            key: "risk_score",
            name: "Compound Flood Risk & ML Probability",
            category: "Ensemble Prediction",
            value: `${prob.toFixed(1)}% (Score: ${score.toFixed(1)}/100)`,
            description: "Calibrated empirical probability produced by ChetakAI HistGradientBoosting & RandomForest ensemble.",
            flood_importance: "Directly determines emergency civil defense response, warning trigger escalation, and shelter activation.",
            calculation_method: "Trained on 60 physical parameters combining Sentinel-1, IMD Radar, SoilGrids, and DEM slope vectors.",
            thresholds: {
              low: "< 35% Prob / < 40 Score",
              moderate: "35% - 60% Prob / 40 - 65 Score",
              high: "60% - 80% Prob / 65 - 80 Score",
              severe: "> 80% Prob / > 80 Score"
            }
          })}
          title="Explain this metric"
        >
          <IconHelp className="w-4 h-4" />
        </button>
      </div>

      <div className="gauge-visual-wrap">
        <svg className="gauge-svg" width="180" height="180" viewBox="0 0 180 180">
          <circle
            className="gauge-track"
            cx="90"
            cy="90"
            r={radius}
            strokeWidth="14"
          />
          <circle
            className="gauge-progress"
            cx="90"
            cy="90"
            r={radius}
            strokeWidth="14"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            stroke={currentTheme.stroke}
            transform="rotate(-90 90 90)"
          />
        </svg>

        <div className="gauge-center-content">
          <span className="gauge-pct-value">{prob.toFixed(1)}%</span>
          <span className="gauge-pct-label">Inundation Probability</span>
          <span className={`gauge-status-badge badge-${riskClass.toLowerCase()}`}>
            {riskClass}
          </span>
        </div>
      </div>

      <div className="gauge-metrics-footer">
        <div className="gauge-metric-tile">
          <span className="tile-label">Compound Score</span>
          <strong className="tile-val">{score.toFixed(1)} <span className="tile-unit">/100</span></strong>
        </div>
        <div className="gauge-metric-tile">
          <span className="tile-label">Alert Severity</span>
          <strong className="tile-val text-copper">{alert.priority || "P2"} — {alert.level || riskClass}</strong>
        </div>
        <div className="gauge-metric-tile">
          <span className="tile-label">Model Confidence</span>
          <strong className="tile-val text-teal">76.0%</strong>
        </div>
      </div>
    </div>
  );
}
