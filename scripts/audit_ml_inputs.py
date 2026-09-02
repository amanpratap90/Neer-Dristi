from pathlib import Path
import pandas as pd
import json

ROOT = Path("data/processed")

SUPPORTED = {".csv", ".parquet", ".json", ".geojson"}

def inspect_file(path):
    result = {
        "file": str(path),
        "type": path.suffix.lower(),
        "rows": None,
        "columns": [],
        "time_min": None,
        "time_max": None,
        "missing_pct": None,
        "duplicates": None,
    }

    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        elif path.suffix.lower() == ".parquet":
            df = pd.read_parquet(path)
        elif path.suffix.lower() == ".json":
            df = pd.read_json(path)
        elif path.suffix.lower() == ".geojson":
            import geopandas as gpd
            df = gpd.read_file(path)
        else:
            return result

        result["rows"] = len(df)
        result["columns"] = list(df.columns)
        result["duplicates"] = int(df.duplicated().sum())

        if len(df.columns) > 0:
            result["missing_pct"] = round(
                float(df.isna().mean().mean() * 100), 2
            )

        time_candidates = [
            c for c in df.columns
            if c.lower() in {
                "timestamp",
                "datetime",
                "date",
                "time",
                "valid_time",
                "time_utc"
            }
        ]

        if time_candidates:
            c = time_candidates[0]
            t = pd.to_datetime(df[c], errors="coerce", utc=True)

            if t.notna().any():
                result["time_min"] = str(t.min())
                result["time_max"] = str(t.max())

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    if not ROOT.exists():
        print(f"ERROR: {ROOT} does not exist")
        return

    files = [
        p for p in ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED
    ]

    print("=" * 80)
    print("CHETAKAI ML INPUT AUDIT")
    print("=" * 80)
    print(f"Root       : {ROOT}")
    print(f"Files found: {len(files)}")
    print()

    results = []

    for path in sorted(files):
        print(f"Scanning: {path}")
        results.append(inspect_file(path))

    output = Path("data/ml")
    output.mkdir(parents=True, exist_ok=True)

    with open(output / "ml_input_audit.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Human-readable summary
    rows = []

    for r in results:
        rows.append({
            "file": r["file"],
            "rows": r["rows"],
            "columns": len(r["columns"]),
            "time_min": r["time_min"],
            "time_max": r["time_max"],
            "missing_pct": r["missing_pct"],
            "duplicates": r["duplicates"],
        })

    audit_df = pd.DataFrame(rows)

    audit_df.to_csv(
        output / "ml_input_audit.csv",
        index=False
    )

    print()
    print("=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)
    print(f"JSON : {output / 'ml_input_audit.json'}")
    print(f"CSV  : {output / 'ml_input_audit.csv'}")
    print()

    if not audit_df.empty:
        print(audit_df.to_string(index=False))


if __name__ == "__main__":
    main()