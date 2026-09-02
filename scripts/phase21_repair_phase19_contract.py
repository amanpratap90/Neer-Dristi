from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CONTRACT_PATH = (
    ROOT
    / "data"
    / "processed"
    / "models"
    / "phase19"
    / "phase19_feature_contract.json"
)

BACKUP_PATH = CONTRACT_PATH.with_suffix(
    ".pre_phase21_threshold_fix.json"
)

THRESHOLD = 0.34


def main() -> None:
    print("=" * 110)
    print("CHETAKAI V1 — PHASE 19 CONTRACT REPAIR")
    print("=" * 110)

    if not CONTRACT_PATH.exists():
        raise FileNotFoundError(
            f"Contract not found:\n{CONTRACT_PATH}"
        )

    with open(
        CONTRACT_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        contract = json.load(f)

    if not BACKUP_PATH.exists():
        shutil.copy2(
            CONTRACT_PATH,
            BACKUP_PATH,
        )

        print(
            f"Backup created : {BACKUP_PATH}"
        )
    else:
        print(
            f"Backup exists  : {BACKUP_PATH}"
        )

    features = contract.get("features")

    if not isinstance(features, list):
        raise ValueError(
            "Phase 19 contract does not contain a valid 'features' list."
        )

    if len(features) != 60:
        raise ValueError(
            f"Expected 60 features, found {len(features)}."
        )

    existing_threshold = contract.get("decision_threshold")

    if existing_threshold is not None:
        if abs(float(existing_threshold) - THRESHOLD) > 1e-12:
            raise ValueError(
                "Existing decision_threshold conflicts with Phase 21 "
                f"expected value {THRESHOLD}."
            )
    else:
        contract["decision_threshold"] = THRESHOLD

    contract["threshold_source"] = (
        "phase19_validation_threshold_locked_for_phase21"
    )

    contract["phase21_compatibility"] = {
        "enabled": True,
        "schema_version": "1.0",
        "decision_threshold": THRESHOLD,
        "locked_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    with open(
        CONTRACT_PATH,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            contract,
            f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")

    print()
    print("Contract feature count : 60")
    print(f"Decision threshold     : {THRESHOLD:.6f}")
    print(
        "Threshold source       : "
        "phase19_validation_threshold_locked_for_phase21"
    )
    print()
    print("PHASE 19 CONTRACT REPAIR: PASS")
    print("=" * 110)


if __name__ == "__main__":
    main()