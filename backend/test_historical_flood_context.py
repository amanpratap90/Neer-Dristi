from datetime import datetime

import pandas as pd

from app.services.historical_flood_service import summarize_historical_flood_context
from app.services.prediction_service import build_feature_vector


def test_historical_flood_context_infers_recent_recurring_floods():
    reference = pd.Timestamp("2024-08-01")
    events = pd.DataFrame(
        [
            {
                "start_date": pd.Timestamp("2023-07-15"),
                "end_date": pd.Timestamp("2023-07-18"),
                "latitude": 25.323611,
                "longitude": 83.037500,
                "Severity": "High",
                "Area Affected": 120.0,
            },
            {
                "start_date": pd.Timestamp("2024-06-20"),
                "end_date": pd.Timestamp("2024-06-24"),
                "latitude": 25.322000,
                "longitude": 83.036500,
                "Severity": "Very High",
                "Area Affected": 180.0,
            },
            {
                "start_date": pd.Timestamp("2022-09-10"),
                "end_date": pd.Timestamp("2022-09-14"),
                "latitude": 25.400000,
                "longitude": 83.100000,
                "Severity": "Moderate",
                "Area Affected": 80.0,
            },
        ]
    )

    context = summarize_historical_flood_context(
        events,
        latitude=25.323611,
        longitude=83.037500,
        reference_date=reference,
        max_radius_km=25.0,
    )

    assert context["event_count_5y"] >= 2
    assert context["days_since_last_flood"] <= 120
    assert context["historical_flood_risk"] > 0.0
    assert context["recurrence_risk_factor"] > 0.0


def test_build_feature_vector_uses_historical_flood_features():
    inputs = {
        "rainfall": {
            "h1": 1.1,
            "h3": 2.2,
            "h6": 4.5,
            "h12": 7.5,
            "h24": 18.0,
            "h72": 46.0,
            "forecast24h": 20.0,
            "forecast72h": 58.0,
            "antecedentPrecipitationIndex": 90.0,
            "evapotranspiration72h": 12.0,
        },
        "current": {
            "soilMoisture0_1": 0.30,
            "soilMoisture1_3": 0.32,
            "soilMoisture3_9": 0.35,
            "soilMoisture9_27": 0.38,
            "rootZoneSoilMoisture": 0.40,
        },
        "flood": {
            "dischargeNow": 240.0,
            "dischargeMean": 160.0,
        },
        "elevation": 20.0,
        "historical_flood_context": {
            "event_count_5y": 3,
            "days_since_last_flood": 21,
            "recent_severity_index": 0.75,
            "recurrence_risk_factor": 0.72,
            "historical_flood_risk": 0.68,
        },
    }
    catchment = {
        "soil": {"clay_fraction_pct": 35.0, "sand_fraction_pct": 30.0, "silt_fraction_pct": 35.0},
        "land_cover": {"cropland_pct": 65.0, "built_up_pct": 8.0, "water_pct": 5.0},
        "slope_deg": 1.8,
        "relief_m": 25.0,
        "drainage_density_km_km2": 1.8,
        "curve_number": 82.0,
    }

    feature_map = build_feature_vector(inputs, catchment)

    assert feature_map["historical_flood_count_5y"] == 3.0
    assert feature_map["days_since_last_flood"] == 21.0
    assert feature_map["historical_severity_index"] == 0.75
    assert feature_map["recurrence_risk_factor"] == 0.72
