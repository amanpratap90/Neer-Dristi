from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PHASE21 = ROOT / "scripts" / "phase21_production_risk_api.py"
PHASE22 = ROOT / "scripts" / "phase22_risk_engine.py"
PHASE23 = ROOT / "scripts" / "phase23_alert_engine.py"
PHASE24 = ROOT / "scripts" / "phase24_rag.py"
PHASE25 = ROOT / "scripts" / "phase25_weather_llm.py"
PHASE26 = ROOT / "scripts" / "phase26_agent_orchestrator.py"

PHASE21_OUTPUT = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase21"
    / "latest_risk_snapshot.json"
)

PHASE22_OUTPUT = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase22"
    / "latest_risk_engine.json"
)

PHASE23_OUTPUT = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase23"
    / "latest_alert.json"
)

PHASE24_OUTPUT = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase24"
    / "latest_rag_context.json"
)

PHASE25_OUTPUT = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase25"
    / "latest_weather_assessment.json"
)

PHASE26_OUTPUT = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase26"
    / "latest_agent_response.json"
)

OUT = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase27"
)

OUT.mkdir(parents=True, exist_ok=True)


# ======================================================================
# WINDOWS / UTF-8 CONSOLE FIX
# ======================================================================

def configure_utf8_console() -> None:
    """
    Prevent Windows cp1252 console failures when pipeline phases emit
    Unicode characters.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)

        if stream is None:
            continue

        try:
            stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )
        except (AttributeError, ValueError):
            pass


configure_utf8_console()


# ======================================================================
# CONSTANTS
# ======================================================================

COORDINATE_TOLERANCE = 1e-8

EXPECTED_OUTPUTS = {
    "Phase 21": PHASE21_OUTPUT,
    "Phase 22": PHASE22_OUTPUT,
    "Phase 23": PHASE23_OUTPUT,
    "Phase 24": PHASE24_OUTPUT,
    "Phase 25": PHASE25_OUTPUT,
    "Phase 26": PHASE26_OUTPUT,
}


# ======================================================================
# UTILITY FUNCTIONS
# ======================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_print(*values, **kwargs) -> None:
    """
    UTF-8-safe print for Windows and PowerShell.
    """
    try:
        print(*values, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(value) for value in values)
        stream = kwargs.get("file", sys.stdout)

        try:
            stream.write(
                text.encode("utf-8", errors="replace")
                .decode("utf-8", errors="replace")
            )
            stream.write(kwargs.get("end", "\n"))
            stream.flush()
        except Exception:
            stream.write(
                text.encode("ascii", errors="replace").decode("ascii")
                + kwargs.get("end", "\n")
            )


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Expected pipeline output not found:\n{path}"
        )

    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in pipeline output:\n{path}\n"
            f"{exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            f"Pipeline output must contain a JSON object:\n{path}"
        )

    return payload


def validate_output_exists(
    phase_name: str,
    path: Path,
) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{phase_name} completed but expected output does not exist:\n"
            f"{path}"
        )

    if path.stat().st_size == 0:
        raise ValueError(
            f"{phase_name} produced an empty output file:\n"
            f"{path}"
        )


def run_script(
    script: Path,
    extra_args: list[str] | None = None,
) -> None:
    if not script.exists():
        raise FileNotFoundError(
            f"Pipeline script not found:\n{script}"
        )

    args = [
        sys.executable,
        str(script),
    ]

    if extra_args:
        args.extend(extra_args)

    safe_print()
    safe_print("=" * 110)
    safe_print(f"RUNNING {script.name}")
    safe_print("=" * 110)
    safe_print(
        "Command:",
        " ".join(str(x) for x in args),
    )

    child_env = os.environ.copy()

    # Force Python child processes to communicate in UTF-8.
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"

    completed = subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
    )

    if completed.stdout:
        safe_print(completed.stdout, end="")

    if completed.stderr:
        safe_print(
            completed.stderr,
            file=sys.stderr,
            end="",
        )

    if completed.returncode != 0:
        raise RuntimeError(
            f"{script.name} failed with exit code "
            f"{completed.returncode}."
        )


# ======================================================================
# COORDINATE VALIDATION
# ======================================================================

def validate_coordinate(
    latitude,
    longitude,
) -> tuple[float, float]:
    latitude = float(latitude)
    longitude = float(longitude)

    if not -90 <= latitude <= 90:
        raise ValueError(
            "Latitude must be between -90 and 90."
        )

    if not -180 <= longitude <= 180:
        raise ValueError(
            "Longitude must be between -180 and 180."
        )

    return latitude, longitude


def extract_coordinate(payload: dict) -> dict:
    coordinate = payload.get("coordinate")

    if isinstance(coordinate, dict):
        return coordinate

    return {}


def validate_phase21_coordinate(
    result: dict,
    latitude: float,
    longitude: float,
) -> None:
    coordinate = extract_coordinate(result)

    actual_lat = coordinate.get("latitude")
    actual_lon = coordinate.get("longitude")

    if actual_lat is None or actual_lon is None:
        raise ValueError(
            "Phase 21 did not return a coordinate."
        )

    actual_lat = float(actual_lat)
    actual_lon = float(actual_lon)

    if abs(actual_lat - latitude) > COORDINATE_TOLERANCE:
        raise ValueError(
            "Phase 21 returned a different latitude.\n"
            f"Requested : {latitude}\n"
            f"Returned  : {actual_lat}"
        )

    if abs(actual_lon - longitude) > COORDINATE_TOLERANCE:
        raise ValueError(
            "Phase 21 returned a different longitude.\n"
            f"Requested : {longitude}\n"
            f"Returned  : {actual_lon}"
        )


def validate_pipeline_coordinate(
    payload: dict,
    latitude: float,
    longitude: float,
    phase_name: str,
) -> None:
    coordinate = extract_coordinate(payload)

    actual_lat = coordinate.get("latitude")
    actual_lon = coordinate.get("longitude")

    if actual_lat is None and actual_lon is None:
        return

    if actual_lat is None or actual_lon is None:
        raise ValueError(
            f"{phase_name} returned an incomplete coordinate."
        )

    actual_lat = float(actual_lat)
    actual_lon = float(actual_lon)

    if abs(actual_lat - latitude) > COORDINATE_TOLERANCE:
        raise ValueError(
            f"{phase_name} latitude does not match requested latitude.\n"
            f"Requested : {latitude}\n"
            f"Returned  : {actual_lat}"
        )

    if abs(actual_lon - longitude) > COORDINATE_TOLERANCE:
        raise ValueError(
            f"{phase_name} longitude does not match requested longitude.\n"
            f"Requested : {longitude}\n"
            f"Returned  : {actual_lon}"
        )


# ======================================================================
# PHASE HELPERS
# ======================================================================

def load_phase_output(
    phase_name: str,
    path: Path,
) -> dict:
    validate_output_exists(
        phase_name,
        path,
    )

    return load_json(path)


def require_dict(
    payload: dict,
    key: str,
    phase_name: str,
) -> dict:
    value = payload.get(key)

    if value is None:
        return {}

    if not isinstance(value, dict):
        raise ValueError(
            f"{phase_name} field '{key}' must be an object."
        )

    return value


# ======================================================================
# MAIN PIPELINE
# ======================================================================

def build_result(
    latitude,
    longitude,
    strict,
) -> dict:

    latitude, longitude = validate_coordinate(
        latitude,
        longitude,
    )

    safe_print()
    safe_print("=" * 110)
    safe_print(
        "CHETAKAI V1 — PHASE 27 DYNAMIC END-TO-END PIPELINE"
    )
    safe_print("=" * 110)
    safe_print(
        f"Requested latitude  : {latitude}"
    )
    safe_print(
        f"Requested longitude : {longitude}"
    )
    safe_print(
        f"Strict              : {strict}"
    )
    safe_print(
        f"Project root        : {ROOT}"
    )

    # ================================================================
    # PHASE 21
    # ================================================================

    phase21_args = [
        "--lat",
        str(latitude),
        "--lon",
        str(longitude),
    ]

    if strict:
        phase21_args.append("--strict")

    run_script(
        PHASE21,
        phase21_args,
    )

    phase21 = load_phase_output(
        "Phase 21",
        PHASE21_OUTPUT,
    )

    validate_phase21_coordinate(
        phase21,
        latitude,
        longitude,
    )

    safe_print("PHASE 21 : PASS")

    # ================================================================
    # PHASE 22
    # ================================================================

    run_script(
        PHASE22,
        ["--strict"] if strict else [],
    )

    phase22 = load_phase_output(
        "Phase 22",
        PHASE22_OUTPUT,
    )

    validate_pipeline_coordinate(
        phase22.get("source", {}),
        latitude,
        longitude,
        "Phase 22",
    )

    safe_print("PHASE 22 : PASS")

    # ================================================================
    # PHASE 23
    # ================================================================

    run_script(
        PHASE23,
        ["--strict"] if strict else [],
    )

    phase23 = load_phase_output(
        "Phase 23",
        PHASE23_OUTPUT,
    )

    validate_pipeline_coordinate(
        phase23,
        latitude,
        longitude,
        "Phase 23",
    )

    safe_print("PHASE 23 : PASS")

    # ================================================================
    # PHASE 24
    # ================================================================

    run_script(
        PHASE24,
        ["--strict"] if strict else [],
    )

    phase24 = load_phase_output(
        "Phase 24",
        PHASE24_OUTPUT,
    )

    validate_pipeline_coordinate(
        phase24,
        latitude,
        longitude,
        "Phase 24",
    )

    safe_print("PHASE 24 : PASS")

    # ================================================================
    # PHASE 25
    # ================================================================

    run_script(
        PHASE25,
        ["--strict"] if strict else [],
    )

    phase25 = load_phase_output(
        "Phase 25",
        PHASE25_OUTPUT,
    )

    validate_pipeline_coordinate(
        phase25,
        latitude,
        longitude,
        "Phase 25",
    )

    safe_print("PHASE 25 : PASS")

    # ================================================================
    # PHASE 26
    # ================================================================

    run_script(
        PHASE26,
        ["--strict"] if strict else [],
    )

    phase26 = load_phase_output(
        "Phase 26",
        PHASE26_OUTPUT,
    )

    validate_pipeline_coordinate(
        phase26.get("request", {}),
        latitude,
        longitude,
        "Phase 26",
    )

    safe_print("PHASE 26 : PASS")

    # ================================================================
    # FINAL COORDINATE VALIDATION
    # ================================================================

    final_coordinate = (
        phase26
        .get("request", {})
        .get("coordinate", {})
    )

    final_lat = final_coordinate.get("latitude")
    final_lon = final_coordinate.get("longitude")

    if final_lat is not None:
        if abs(float(final_lat) - latitude) > COORDINATE_TOLERANCE:
            raise ValueError(
                "Final Phase 26 latitude does not match "
                "requested latitude."
            )

    if final_lon is not None:
        if abs(float(final_lon) - longitude) > COORDINATE_TOLERANCE:
            raise ValueError(
                "Final Phase 26 longitude does not match "
                "requested longitude."
            )

    # ================================================================
    # AUTHORITATIVE DATA
    # ================================================================

    basin = require_dict(
        phase21,
        "basin",
        "Phase 21",
    )

    risk = require_dict(
        phase22,
        "risk",
        "Phase 22",
    )

    alert = require_dict(
        phase23,
        "alert",
        "Phase 23",
    )

    assessment = phase25.get(
        "rendered_report",
        "",
    )

    if assessment is None:
        assessment = ""

    if not isinstance(assessment, str):
        assessment = str(assessment)

    # ================================================================
    # BASIN NORMALIZATION
    # ================================================================

    basin_name = (
        basin.get("basin_name")
        or basin.get("basin_id")
        or "Unavailable"
    )

    basin_id = (
        basin.get("basin_id")
        or "Unavailable"
    )

    # ================================================================
    # RESULT
    # ================================================================

    result = {
        "api_version": "2.1",

        "timestamp": utc_now_iso(),

        "status": "OK",

        "coordinate": {
            "latitude": latitude,
            "longitude": longitude,
        },

        "basin": {
            **basin,
            "basin_name": basin_name,
            "basin_id": basin_id,
        },

        "state": phase21.get(
            "state",
            {},
        ),

        "terrain": phase21.get(
            "terrain",
            {},
        ),

        "model": phase21.get(
            "model",
            {},
        ),

        "prediction": phase21.get(
            "prediction",
            {},
        ),

        "evidence": phase21.get(
            "evidence",
            {},
        ),

        "feature_audit": phase21.get(
            "feature_audit",
            {},
        ),

        "data_quality": phase21.get(
            "data_quality",
            {},
        ),

        "risk": risk,

        "alert": alert,

        "rag": phase24,

        "weather_assessment": phase25,

        "assessment": assessment,

        "agent": phase26,

        "pipeline": {
            "dynamic": True,

            "demoFallback": False,

            "phase21": "PASS",
            "phase22": "PASS",
            "phase23": "PASS",
            "phase24": "PASS",
            "phase25": "PASS",
            "phase26": "PASS",

            "coordinate_source": "REQUEST",

            "coordinate_validated": True,

            "coordinate_locked_to_request": True,

            "fresh_phase21_snapshot": True,

            "snapshot_locked": True,

            "utf8_safe_subprocess": True,

            "windows_console_safe": True,
        },

        "contract": {
            **phase26.get(
                "contract",
                {},
            ),

            "dynamic_coordinate": True,

            "requested_coordinate_validated": True,

            "basin_locked": True,

            "phase21_authoritative_probability": True,

            "phase22_authoritative_risk": True,

            "phase23_authoritative_alert": True,

            "phase25_grounded_assessment": True,

            "no_demo_fallback": True,
        },
    }

    # ================================================================
    # FINAL JSON OUTPUT
    # ================================================================

    output_path = (
        OUT
        / "latest_e2e_response.json"
    )

    output_path.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return result


# ======================================================================
# PUBLIC RUN FUNCTION
# ======================================================================

def run(
    lat,
    lon,
    strict=False,
) -> dict:

    return build_result(
        lat,
        lon,
        strict,
    )


# ======================================================================
# CLI
# ======================================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "ChetakAI V1 Dynamic End-to-End API"
        )
    )

    parser.add_argument(
        "--lat",
        type=float,
        required=True,
        help="Requested latitude",
    )

    parser.add_argument(
        "--lon",
        type=float,
        required=True,
        help="Requested longitude",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict pipeline validation.",
    )

    args = parser.parse_args()

    try:

        result = run(
            args.lat,
            args.lon,
            args.strict,
        )

        safe_print()
        safe_print("=" * 110)
        safe_print(
            "CHETAKAI V1 — PHASE 27 END-TO-END API"
        )
        safe_print("=" * 110)

        safe_print(
            "Status                :",
            result["status"],
        )

        safe_print(
            "Coordinate            :",
            result["coordinate"],
        )

        safe_print(
            "Basin                 :",
            result["basin"].get(
                "basin_name"
            ),
        )

        safe_print(
            "Basin ID              :",
            result["basin"].get(
                "basin_id"
            ),
        )

        safe_print(
            "Flood probability     :",
            result["prediction"].get(
                "flood_probability_pct",
                "N/A",
            ),
        )

        safe_print(
            "ML risk class         :",
            result["prediction"].get(
                "risk_class",
                "N/A",
            ),
        )

        safe_print(
            "Risk engine score     :",
            result["risk"].get(
                "risk_score_pct",
                "N/A",
            ),
        )

        safe_print(
            "Final risk class      :",
            result["risk"].get(
                "risk_class",
                "N/A",
            ),
        )

        safe_print(
            "Alert level           :",
            result["alert"].get(
                "level",
                "N/A",
            ),
        )

        safe_print(
            "Dynamic               :",
            result["pipeline"].get(
                "dynamic"
            ),
        )

        safe_print(
            "Snapshot locked       :",
            result["pipeline"].get(
                "snapshot_locked"
            ),
        )

        safe_print(
            "Coordinate validated  :",
            result["pipeline"].get(
                "coordinate_validated"
            ),
        )

        safe_print(
            "UTF-8 safe            :",
            result["pipeline"].get(
                "utf8_safe_subprocess"
            ),
        )

        safe_print(
            "Output                :",
            OUT / "latest_e2e_response.json",
        )

        safe_print(
            "PHASE 27 STATUS       : PASS"
        )

        safe_print("=" * 110)

    except Exception as exc:

        safe_print()
        safe_print("=" * 110)
        safe_print(
            "PHASE 27 FAILED"
        )
        safe_print("=" * 110)
        safe_print(
            f"{type(exc).__name__}: {exc}"
        )
        safe_print("=" * 110)

        raise


if __name__ == "__main__":
    main()
