import asyncio

from app.services.intelligence_service import generate_flood_intelligence
from app.services.risk_service import calculate_overall_risk


def test_generate_flood_intelligence_does_not_require_cwc():
    payload = asyncio.run(generate_flood_intelligence(latitude=25.323611, longitude=83.037500))

    assert "cwc_ground_truth" not in payload
    assert payload["overall_monitoring"]["basis"]
    assert all("CWC" not in str(item) for item in payload["overall_monitoring"]["basis"])


def test_risk_engine_uses_environmental_signals_without_cwc():
    result = calculate_overall_risk(
        {"probability": 0.72, "risk": "HIGH"},
        {"status": "UNAVAILABLE", "condition": "UNKNOWN", "water_level_m": None},
        {"status": "AVAILABLE", "risk": "HIGH", "score": 78},
    )

    assert result["status"] in {"HIGH ALERT", "WATCH", "NORMAL"}
    assert all("CWC" not in str(item) for item in result["basis"])
    assert result["confidence"] != ""
