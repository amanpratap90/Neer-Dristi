import React from "react";
import { IconHelp } from "./Icons";

export default function MetricCard({
  icon: Icon,
  title,
  value,
  unit = "",
  subtitle,
  trend,
  isAiEstimate = false,
  estimationSource,
  explainerData,
  onExplain
}) {
  const displayValue = value !== null && value !== undefined && value !== "" ? value : "—";

  const handleHelpClick = (e) => {
    e.stopPropagation();
    if (onExplain && explainerData) {
      onExplain({
        ...explainerData,
        value: `${displayValue} ${unit}`,
        is_ai_estimate: isAiEstimate,
        estimation_source: estimationSource
      });
    }
  };

  return (
    <div className="metric-card animate-card-hover" onClick={handleHelpClick}>
      <div className="metric-card-top">
        <div className="metric-icon-wrap">
          {Icon && <Icon className="w-5 h-5 text-copper" />}
          <span className="metric-title">{title}</span>
        </div>
        <button
          className="metric-help-btn"
          onClick={handleHelpClick}
          title="Click to understand this feature"
          aria-label={`Explain ${title}`}
        >
          <IconHelp className="w-4 h-4" />
        </button>
      </div>

      <div className="metric-value-row">
        <span className="metric-main-value">{displayValue}</span>
        {unit && <span className="metric-unit-text">{unit}</span>}
      </div>

      <div className="metric-card-bottom">
        {subtitle && <span className="metric-subtitle">{subtitle}</span>}
        {trend && (
          <span className={`metric-trend-badge trend-${trend.toLowerCase().replace(/\s+/g, "-")}`}>
            {trend}
          </span>
        )}
        <div className="metric-provenance-tag">
          {isAiEstimate ? (
            <span className="badge-ai-estimate-sm" title={estimationSource || "Regional Hydrodynamic AI Synthesis"}>
              AI Estimate
            </span>
          ) : (
            <span className="badge-sensor-verified-sm">
              Sensor Verified
            </span>
          )}
        </div>
      </div>
    </div>
  );
}