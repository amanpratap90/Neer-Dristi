#!/usr/bin/env python3
"""Validate a list of candidate flood-prone coordinates against the live FastAPI endpoint."""

from __future__ import annotations

import json
import sys
from typing import Iterable, List, Tuple
from urllib import error, request

DEFAULT_BASE_URL = "http://localhost:8000"

COORDS: List[Tuple[float, float, str]] = [
    (25.323611, 83.037500, "Varanasi"),
    (26.1924, 87.0614, "Kosi Basin, Bihar"),
    (25.2801, 85.9000, "Gaya / Bihar flood corridor"),
    (25.4487, 86.1365, "North Bihar river plain"),
    (23.8203, 87.8200, "Eastern India flood belt"),
    (27.5252, 89.8843, "Brahmaputra floodplain edge"),
    (23.0125, 87.8032, "West Bengal delta fringe"),
    (21.7100, 83.2910, "Mahanadi basin edge"),
    (26.1857, 85.8234, "Muzaffarpur"),
    (24.1667, 85.5000, "Gaya"),
]


def fetch_payload(lat: float, lon: float, base_url: str = DEFAULT_BASE_URL) -> dict:
    url = f"{base_url}/api/flood-monitoring?lat={lat}&lon={lon}&language=en"
    req = request.Request(url, headers={"Accept": "application/json"})
    with request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def print_row(index: int, lat: float, lon: float, name: str, payload: dict) -> None:
    ai = payload.get("ai", {})
    overall = payload.get("overall", {})
    hist = payload.get("historical_flood_context", {})

    ai_risk = ai.get("risk", "UNKNOWN")
    ai_prob = ai.get("probability_pct")
    overall_status = overall.get("status", "UNKNOWN")
    hist_n = hist.get("event_count_5y", 0)
    hist_days = hist.get("days_since_last_flood")

    print(
        f"{index:02d}. {name:28} | lat={lat:8.4f}, lon={lon:8.4f} | "
        f"AI={ai_risk:<8} {ai_prob}% | Overall={overall_status:<10} | "
        f"Historical={hist_n} events | Days since last={hist_days}"
    )


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    print(f"Validating flood coordinates against {base_url}")
    print("=" * 120)

    for idx, (lat, lon, name) in enumerate(COORDS, start=1):
        try:
            payload = fetch_payload(lat, lon, base_url)
            print_row(idx, lat, lon, name, payload)
        except Exception as exc:
            print(f"{idx:02d}. {name:28} | ERROR: {exc}")

    print("=" * 120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
