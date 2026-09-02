from __future__ import annotations

import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

API_PATH = (
    ROOT
    / "scripts"
    / "phase21_production_risk_api.py"
)

BACKUP_PATH = (
    ROOT
    / "scripts"
    / "phase21_production_risk_api.pre_state_resolution_fix.py"
)


NEW_RESOLVE_STATE = r'''
def resolve_state(
    df: pd.DataFrame,
    basin_id: Optional[str],
) -> Dict[str, Any]:
    """
    Production-safe basin state resolver.

    Resolution contract:

        coordinate
            ↓
        canonical basin ID
            ↓
        canonical_basin_id match
            ↓
        basin-specific rows ONLY
            ↓
        latest valid timestamp
            ↓
        state_basin_id == requested basin

    IMPORTANT:
        There is intentionally NO global fallback.

    A coordinate-specific flood prediction must never use the
    latest state belonging to another basin.
    """

    if basin_id is None:
        raise ValueError(
            "Cannot resolve state because coordinate basin ID is missing."
        )

    canonical_target = normalize_basin_id(
        basin_id
    )

    if canonical_target is None:
        raise ValueError(
            "Cannot resolve state because basin ID is invalid."
        )

    working = df.copy()

    # -------------------------------------------------------------------------
    # DISCOVER BASIN COLUMN
    # -------------------------------------------------------------------------

    basin_col = find_column(
        working,
        [
            # Canonical production column FIRST.
            "canonical_basin_id",

            # Other supported representations.
            "basin_id",
            "BASIN_ID",
            "basin",
            "BASIN",
            "cwc_basin",
            "CWC_BASIN",
            "cwc_basin_id",
            "cwc_id",
            "id",
        ],
    )

    if basin_col is None:
        raise ValueError(
            "Inference dataset has no recognized basin identifier column. "
            "Expected 'canonical_basin_id', 'basin_id', or another "
            "supported basin identifier."
        )

    # -------------------------------------------------------------------------
    # NORMALIZE BASIN IDS
    # -------------------------------------------------------------------------

    working["_phase21_normalized_basin_id"] = (
        working[basin_col]
        .map(normalize_basin_id)
    )

    # -------------------------------------------------------------------------
    # TIMESTAMP
    # -------------------------------------------------------------------------

    timestamp_col = find_column(
        working,
        [
            "timestamp",
            "datetime",
            "date",
            "time",
            "valid_time",
            "state_timestamp",
        ],
    )

    if timestamp_col is not None:

        working["_phase21_timestamp"] = pd.to_datetime(
            working[timestamp_col],
            errors="coerce",
        )

    else:

        working["_phase21_timestamp"] = pd.NaT

    # -------------------------------------------------------------------------
    # BASIN-SPECIFIC FILTER — NO GLOBAL FALLBACK
    # -------------------------------------------------------------------------

    basin_rows = working[
        working["_phase21_normalized_basin_id"]
        == canonical_target
    ].copy()

    if basin_rows.empty:

        available_basins = sorted(
            x
            for x in (
                working[
                    "_phase21_normalized_basin_id"
                ]
                .dropna()
                .unique()
                .tolist()
            )
            if x
        )

        raise ValueError(
            "No basin-specific inference state exists for "
            f"{canonical_target}. "
            f"Available canonical basins: {available_basins}"
        )

    # -------------------------------------------------------------------------
    # SELECT LATEST BASIN-SPECIFIC STATE
    # -------------------------------------------------------------------------

    if basin_rows["_phase21_timestamp"].notna().any():

        valid_timestamp_rows = basin_rows[
            basin_rows["_phase21_timestamp"].notna()
        ].copy()

        valid_timestamp_rows = (
            valid_timestamp_rows
            .sort_values(
                "_phase21_timestamp",
                ascending=True,
            )
        )

        selected = valid_timestamp_rows.iloc[-1]

        timestamp_value = selected[
            "_phase21_timestamp"
        ]

        state_timestamp = (
            timestamp_value.strftime(
                "%Y-%m-%d"
            )
        )

    else:

        selected = basin_rows.iloc[-1]

        state_timestamp = (
            "latest available basin-specific row"
        )

    # -------------------------------------------------------------------------
    # FINAL IDENTITY CHECK
    # -------------------------------------------------------------------------

    resolved_state_basin = normalize_basin_id(
        selected[basin_col]
    )

    if resolved_state_basin != canonical_target:

        raise ValueError(
            "CRITICAL STATE IDENTITY FAILURE: "
            f"selected state belongs to "
            f"'{resolved_state_basin}', "
            f"but requested coordinate basin is "
            f"'{canonical_target}'."
        )

    # -------------------------------------------------------------------------
    # RETURN
    # -------------------------------------------------------------------------

    return {
        "row": selected,

        "state_timestamp": state_timestamp,

        "state_resolution": "basin_matched",

        "state_basin_id": resolved_state_basin,

        "basin_state_consistency": True,

        "state_source": "basin_specific_inference_data",

        "state_basin_column": basin_col,

        "state_candidate_rows": int(
            len(basin_rows)
        ),

        "state_selection_rule": (
            "latest_valid_timestamp_within_requested_basin"
        ),
    }
'''


def main() -> None:

    print("=" * 110)
    print("CHETAKAI V1 — PHASE 21 STATE RESOLUTION REPAIR")
    print("=" * 110)

    if not API_PATH.exists():
        raise FileNotFoundError(
            f"Phase 21 API not found:\n{API_PATH}"
        )

    text = API_PATH.read_text(
        encoding="utf-8"
    )

    # -------------------------------------------------------------------------
    # BACKUP
    # -------------------------------------------------------------------------

    if not BACKUP_PATH.exists():

        shutil.copy2(
            API_PATH,
            BACKUP_PATH,
        )

        print()
        print(
            f"Backup created : {BACKUP_PATH}"
        )

    else:

        print()
        print(
            f"Backup exists  : {BACKUP_PATH}"
        )

    # -------------------------------------------------------------------------
    # FIND resolve_state()
    # -------------------------------------------------------------------------

    start_match = re.search(
        r"^def resolve_state\(",
        text,
        flags=re.MULTILINE,
    )

    if not start_match:

        raise RuntimeError(
            "Could not locate resolve_state() in Phase 21 API."
        )

    start = start_match.start()

    # Find the next top-level section after resolve_state.
    end_match = re.search(
        r"^# =+\n# TERRAIN SUPPORT\n# =+\n",
        text[start:],
        flags=re.MULTILINE,
    )

    if not end_match:

        raise RuntimeError(
            "Could not locate TERRAIN SUPPORT section after "
            "resolve_state()."
        )

    end = start + end_match.start()

    # -------------------------------------------------------------------------
    # REPLACE FUNCTION
    # -------------------------------------------------------------------------

    updated = (
        text[:start]
        + NEW_RESOLVE_STATE.strip()
        + "\n\n\n"
        + text[end:]
    )

    API_PATH.write_text(
        updated,
        encoding="utf-8",
    )

    # -------------------------------------------------------------------------
    # VERIFY
    # -------------------------------------------------------------------------

    final_text = API_PATH.read_text(
        encoding="utf-8"
    )

    required_markers = [
        '"canonical_basin_id"',
        '"basin_specific_inference_data"',
        '"latest_valid_timestamp_within_requested_basin"',
        '"basin_matched"',
    ]

    missing = [
        marker
        for marker in required_markers
        if marker not in final_text
    ]

    if missing:

        raise RuntimeError(
            "State resolver verification failed. "
            f"Missing markers: {missing}"
        )

    if "global_latest_fallback" in final_text:

        raise RuntimeError(
            "UNSAFE STATE FALLBACK STILL EXISTS in Phase 21 API."
        )

    print()
    print("State resolver replaced successfully.")

    print()
    print("NEW RESOLUTION CONTRACT:")
    print("  1. Read canonical_basin_id")
    print("  2. Normalize basin ID")
    print("  3. Filter requested basin ONLY")
    print("  4. Select latest valid timestamp")
    print("  5. Verify state basin == coordinate basin")
    print("  6. No global fallback")
    print("  7. No cross-basin prediction")

    print()
    print("Expected for current test:")
    print("  Coordinate basin : CWC_BASIN_012")
    print("  State basin      : CWC_BASIN_012")
    print("  State resolution : basin_matched")
    print("  Consistency      : True")

    print()
    print("PHASE 21 STATE RESOLUTION REPAIR: PASS")
    print("=" * 110)


if __name__ == "__main__":
    main()