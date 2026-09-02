import React from "react";

function normalizeRisk(value) {
  if (!value) return "UNKNOWN";

  const text = String(value).toUpperCase();

  if (
    text.includes("EXTREME") ||
    text.includes("SEVERE") ||
    text.includes("HIGH")
  ) {
    return "HIGH";
  }

  if (text.includes("MODERATE")) {
    return "MODERATE";
  }

  if (
    text.includes("LOW") ||
    text.includes("SAFE")
  ) {
    return "LOW";
  }

  return text;
}

export default function RiskBadge({ risk }) {
  const normalized = normalizeRisk(risk);

  return (
    <div
      className={`risk-badge risk-${normalized.toLowerCase()}`}
    >
      <span />
      {normalized}
    </div>
  );
}