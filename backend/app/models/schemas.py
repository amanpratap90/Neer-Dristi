from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# CWC Ground-Truth Schemas (Section 8 & 16)
# ---------------------------------------------------------

class CWCStation(BaseModel):
    id: str
    name: str
    river: str
    latitude: float
    longitude: float
    distance_km: Optional[float] = None
    state: Optional[str] = None
    basin: Optional[str] = None


class CWCObservation(BaseModel):
    water_level_m: Optional[float] = None
    timestamp: Optional[str] = None


class CWCThresholds(BaseModel):
    warning_level_m: Optional[float] = None
    danger_level_m: Optional[float] = None
    hfl_m: Optional[float] = None


class NormalizedCWCResponse(BaseModel):
    source: str = "CWC"
    status: str  # AVAILABLE, UNAVAILABLE, STALE, ERROR
    station: Optional[CWCStation] = None
    observation: Optional[CWCObservation] = None
    thresholds: Optional[CWCThresholds] = None
    condition: str  # NORMAL, ABOVE_WARNING, ABOVE_DANGER, EXTREME, UNAVAILABLE
    reason: Optional[str] = None
    data_source: str = "NWIC / CWC River Water Level (Telemetry - Hourly)"


# ---------------------------------------------------------
# Independent Multi-Signal Schemas
# ---------------------------------------------------------

class AISignal(BaseModel):
    source: str = "AI_MODEL"
    probability: float
    risk: str  # LOW, MEDIUM, HIGH, VERY HIGH
    label: Optional[str] = None
    sourceType: str = "MODELLED"


class WeatherSignal(BaseModel):
    source: str = "WEATHER_API"
    rainfall_mm: float
    forecast_rainfall_mm: float
    risk: str  # LOW, MEDIUM, HIGH


class FallbackEnvironmentalSignal(BaseModel):
    source: str = "FALLBACK_ENVIRONMENTAL"
    status: str  # AVAILABLE, UNAVAILABLE
    risk: str  # LOW, MEDIUM, HIGH
    rainfall_mm: Optional[float] = None
    forecast_rainfall_mm: Optional[float] = None
    river_proximity: str  # NEAR, MODERATE, FAR
    soil_moisture: Optional[float] = None
    discharge_ratio: Optional[float] = None
    summary: str


class OverallMonitoringSignal(BaseModel):
    status: str  # NORMAL, WATCH, HIGH ALERT, CRITICAL
    confidence: str  # HIGH CONFIDENCE, MEDIUM CONFIDENCE, LIMITED CONFIDENCE
    basis: List[str]
    cwc_status: str
    explanation: str


# ---------------------------------------------------------
# Canonical Flood Monitoring Schema (Section 15)
# ---------------------------------------------------------

class CanonicalFloodMonitoringResponse(BaseModel):
    location: Dict[str, Any]
    ai: AISignal
    weather: WeatherSignal
    cwc: NormalizedCWCResponse
    overall: OverallMonitoringSignal


# ---------------------------------------------------------
# Controller & React Compatible Request / Response Models
# ---------------------------------------------------------

class AnalyzeRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude between -90 and 90")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude between -180 and 180")
    strict: bool = False
    language: str = "en"
    lang: Optional[str] = None
    demoScenario: Optional[int] = None


class ChatRequest(BaseModel):
    message: str
    telemetry: Optional[Dict[str, Any]] = None
    language: str = "en"
    history: List[Dict[str, Any]] = []


class LocationSearchResponse(BaseModel):
    status: str = "success"
    query: str
    results: List[Dict[str, Any]]
