from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
COMMON_CSV_CANDIDATES: List[Path] = [
    PROJECT_ROOT / "data" / "raw" / "flood_events" / "india_flood_inventory" / "India_Flood_Inventory_v3.csv",
    PROJECT_ROOT / "backend" / "data" / "raw" / "flood_events" / "india_flood_inventory" / "India_Flood_Inventory_v3.csv",
    PROJECT_ROOT / "backend" / "data" / "processed" / "flood_events" / "flood_events_model_ready.csv",
    PROJECT_ROOT / "data" / "processed" / "flood_events" / "flood_events_model_ready.csv",
]


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None and not (isinstance(value, float) and np.isnan(value)):
            return value
    return None


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
        if np.isfinite(number):
            return number
    except (TypeError, ValueError):
        return None
    return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rlat1 = np.radians(lat1)
    rlat2 = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2.0) ** 2
    )
    c = 2 * np.arcsin(np.sqrt(a))
    return 6371.0 * c


def _severity_score(value: Any) -> float:
    if value is None:
        return 0.0
    cleaned = str(value).strip().lower().replace("_", " ")
    mapping = {
        "low": 0.3,
        "moderate": 0.55,
        "medium": 0.55,
        "high": 0.8,
        "very high": 1.0,
        "severe": 1.0,
        "extreme": 1.2,
    }
    if cleaned in mapping:
        return mapping[cleaned]
    try:
        score = float(value)
        if np.isfinite(score):
            return max(0.0, min(1.2, score / 100.0))
    except (TypeError, ValueError):
        pass
    return 0.0


def load_historical_inventory() -> pd.DataFrame:
    for candidate in COMMON_CSV_CANDIDATES:
        if candidate.exists():
            try:
                df = pd.read_csv(candidate)
                if not df.empty:
                    return df
            except Exception:
                continue
    return pd.DataFrame()


def normalize_historical_inventory(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events.copy()

    df = events.copy()
    date_candidates = [
        "start_date",
        "Start Date",
        "StartDate",
        "start",
        "date",
        "Date",
        "event_date",
    ]
    end_candidates = [
        "end_date",
        "End Date",
        "EndDate",
        "end",
        "date_end",
    ]
    lat_candidates = ["latitude", "Latitude", "lat", "y"]
    lon_candidates = ["longitude", "Longitude", "lon", "lng", "x"]
    severity_candidates = ["Severity", "severity", "SEVERITY", "flood_severity"]
    area_candidates = ["Area Affected", "area_affected", "AreaAffected", "area_affected_km2"]

    for date_col in date_candidates:
        if date_col in df.columns:
            df["start_date"] = pd.to_datetime(df[date_col], errors="coerce")
            break
    else:
        df["start_date"] = pd.NaT

    for end_col in end_candidates:
        if end_col in df.columns:
            df["end_date"] = pd.to_datetime(df[end_col], errors="coerce")
            break
    else:
        df["end_date"] = df["start_date"]

    for lat_col in lat_candidates:
        if lat_col in df.columns:
            df["latitude"] = pd.to_numeric(df[lat_col], errors="coerce")
            break
    else:
        df["latitude"] = np.nan

    for lon_col in lon_candidates:
        if lon_col in df.columns:
            df["longitude"] = pd.to_numeric(df[lon_col], errors="coerce")
            break
    else:
        df["longitude"] = np.nan

    for severity_col in severity_candidates:
        if severity_col in df.columns:
            df["severity_score"] = df[severity_col].map(_severity_score)
            break
    else:
        df["severity_score"] = 0.0

    for area_col in area_candidates:
        if area_col in df.columns:
            df["area_affected"] = pd.to_numeric(df[area_col], errors="coerce").fillna(0.0)
            break
    else:
        df["area_affected"] = 0.0

    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
    return df.dropna(subset=["start_date"]).copy()


def summarize_historical_flood_context(
    events: Optional[pd.DataFrame] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    reference_date: Optional[datetime] = None,
    max_radius_km: float = 30.0,
) -> Dict[str, Any]:
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    if events is None:
        events = load_historical_inventory()

    df = normalize_historical_inventory(events if isinstance(events, pd.DataFrame) else pd.DataFrame())

    if df.empty or latitude is None or longitude is None:
        return {
            "available": False,
            "event_count_5y": 0,
            "days_since_last_flood": None,
            "recent_severity_index": 0.0,
            "historical_flood_risk": 0.0,
            "recurrence_risk_factor": 0.0,
            "source": "NONE",
            "nearby_events": 0,
            "latest_event_date": None,
        }

    window_start = reference_date - timedelta(days=5 * 365)
    recent = df[(df["start_date"] >= pd.Timestamp(window_start)) & (df["start_date"] < pd.Timestamp(reference_date))].copy()

    if recent.empty:
        return {
            "available": False,
            "event_count_5y": 0,
            "days_since_last_flood": None,
            "recent_severity_index": 0.0,
            "historical_flood_risk": 0.0,
            "recurrence_risk_factor": 0.0,
            "source": "NONE",
            "nearby_events": 0,
            "latest_event_date": None,
        }

    recent["distance_km"] = recent.apply(
        lambda row: _haversine_km(float(latitude), float(longitude), float(row["latitude"]), float(row["longitude"])),
        axis=1,
    )
    nearby = recent[recent["distance_km"] <= max_radius_km].copy()

    if nearby.empty:
        return {
            "available": True,
            "event_count_5y": 0,
            "days_since_last_flood": None,
            "recent_severity_index": 0.0,
            "historical_flood_risk": 0.0,
            "recurrence_risk_factor": 0.0,
            "source": "HISTORICAL_INVENTORY",
            "nearby_events": 0,
            "latest_event_date": None,
        }

    nearby = nearby.sort_values("start_date", ascending=False)
    latest_event = nearby.iloc[0]["start_date"]
    days_since_last = max(0, (reference_date - latest_event.to_pydatetime()).days)
    event_count = len(nearby)
    severity_index = float(nearby["severity_score"].mean())
    area_weight = float(nearby["area_affected"].sum()) / max(1.0, float(nearby["area_affected"].max() or 1.0))
    recurrence = min(1.0, event_count / 4.0)
    age_factor = min(1.0, 365.0 / max(days_since_last + 30, 1))
    historical_risk = min(1.0, 0.14 * recurrence + 0.34 * severity_index + 0.28 * min(1.0, area_weight / 2.0) + 0.24 * age_factor)
    recurrence_factor = min(1.0, recurrence * 0.7 + age_factor * 0.3)

    return {
        "available": True,
        "event_count_5y": int(event_count),
        "days_since_last_flood": int(days_since_last),
        "recent_severity_index": round(severity_index, 3),
        "historical_flood_risk": round(float(historical_risk), 4),
        "recurrence_risk_factor": round(float(recurrence_factor), 4),
        "source": "HISTORICAL_INVENTORY",
        "nearby_events": int(event_count),
        "latest_event_date": latest_event.isoformat(),
    }
