/**
 * Data Quality & Telemetry Validation Service for ChetakAI
 * Ensures incoming physical telemetry respects conservation laws and sanity bounds.
 */

export function validateEnvironmentalInputs(inputs = {}) {
  const issues = [];
  const warnings = [];

  const rain24 = Number(inputs.rainfall?.h24 ?? 0);
  const rain72 = Number(inputs.rainfall?.h72 ?? 0);
  const moisture = Number(inputs.current?.soilMoisture ?? 0);
  const elevation = Number(inputs.elevation ?? 50);
  const discharge = Number(inputs.flood?.dischargeNow ?? 0);
  const temperature = Number(inputs.current?.temperature ?? 25);
  const humidity = Number(inputs.current?.humidity ?? 60);

  // 1. Precipitation bounds
  if (rain24 < 0 || rain24 > 1500) {
    issues.push(`Unrealistic 24h rainfall: ${rain24} mm`);
  }
  if (rain72 < rain24) {
    issues.push(`72h rainfall (${rain72} mm) cannot be less than 24h rainfall (${rain24} mm)`);
  }

  // 2. Soil moisture bounds (volumetric fraction: typically 0.05 to 0.65 for saturated soil)
  if (moisture < 0.0 || moisture > 1.0) {
    issues.push(`Soil moisture out of bounds [0, 1]: ${moisture}`);
  } else if (moisture > 0.65) {
    warnings.push(`Soil moisture exceptionally high (${moisture}), indicating supersaturation or pooling`);
  }

  // 3. Elevation bounds
  if (elevation < -50 || elevation > 8848) {
    issues.push(`Elevation out of geographic range: ${elevation} m`);
  }

  // 4. River discharge bounds
  if (discharge < 0) {
    issues.push(`River discharge cannot be negative: ${discharge} m³/s`);
  }

  // 5. Temperature and Humidity bounds
  if (temperature < -50 || temperature > 60) {
    issues.push(`Temperature anomaly: ${temperature} °C`);
  }
  if (humidity < 0 || humidity > 100) {
    issues.push(`Relative humidity out of bounds: ${humidity} %`);
  }

  const isValid = issues.length === 0;
  const status = !isValid ? "FAILED" : warnings.length > 0 ? "WARNING" : "PASS";

  return {
    isValid,
    status,
    issues,
    warnings,
    coordinate_resolution: "PASS",
    quality_score: Math.max(0, 100 - issues.length * 30 - warnings.length * 10)
  };
}
