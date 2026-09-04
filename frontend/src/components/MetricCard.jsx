import React from "react";
import { IconHelp } from "./Icons";

export default function MetricCard({
  icon: Icon,
  title,
  dataObj,
  subtitle,
  trend,
  explainerData,
  onExplain
}) {
  // If dataObj is not provided or it's a legacy plain value, adapt it.
  const obj = (typeof dataObj === 'object' && dataObj !== null && 'status' in dataObj)
    ? dataObj
    : { value: dataObj, unit: "", status: dataObj !== null && dataObj !== undefined ? "OK" : "UNAVAILABLE", source: "Unknown", sourceType: "UNKNOWN" };

  const isUnavailable = obj.status === "UNAVAILABLE" || obj.value === null;
  const displayValue = isUnavailable ? "Unavailable" : obj.value;
  const displayUnit = isUnavailable ? "" : obj.unit;
  const hideApproximationSource = String(obj.source || "").toLowerCase().includes("hardcoded");

  const failureReason = obj.failureReason || obj.reason;

  const handleHelpClick = (e) => {
    e.stopPropagation();
    if (onExplain && explainerData) {
      onExplain({
        ...explainerData,
        value: isUnavailable ? "Unavailable" : `${displayValue} ${displayUnit}`,
        source: obj.source,
        sourceType: obj.sourceType,
        observedAt: obj.observedAt
      });
    }
  };

  return (
    <div className={`metric-card animate-card-hover ${isUnavailable ? 'opacity-85' : ''}`} onClick={handleHelpClick}>
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
        <span className={`metric-main-value ${isUnavailable ? 'text-gray-400 text-lg' : ''}`}>
          {displayValue}
        </span>
        {displayUnit && <span className="metric-unit-text">{displayUnit}</span>}
      </div>

      <div className="metric-card-bottom">
        {subtitle && <span className="metric-subtitle">{subtitle}</span>}
        {isUnavailable && failureReason && (
          <span className="metric-reason text-xs text-amber-500/90 block mt-1">
            Reason: {failureReason}
          </span>
        )}
        {trend && !isUnavailable && (
          <span className={`metric-trend-badge trend-${trend.toLowerCase().replace(/\s+/g, "-")}`}>
            {trend}
          </span>
        )}
        {obj.observedAt && (
          <span className="text-[11px] text-slate-400 block mt-1">
            Observed at: {new Date(obj.observedAt).toLocaleTimeString()}
          </span>
        )}
        <div className="metric-provenance-tag mt-2">
          {obj.source && !hideApproximationSource && (
            <span className="text-xs text-slate-300 bg-slate-800/80 px-2 py-0.5 rounded-full border border-slate-700 font-mono">
              {obj.source} • {obj.sourceType}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}