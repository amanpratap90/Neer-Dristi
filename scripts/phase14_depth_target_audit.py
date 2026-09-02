from pathlib import Path
import pandas as pd

ROOT = Path("data")

print("=" * 110)
print("CHETAKAI V1 — PHASE 14 FLOOD DEPTH / INUNDATION TARGET AUDIT")
print("=" * 110)

keywords = [
    "depth",
    "inund",
    "water_depth",
    "flood_depth",
    "water_level",
    "river_level",
    "flood_area",
    "flood_extent",
    "flood_severity",
    "flood_duration",
    "water_surface",
    "flood_height",
]

matches = []

csv_files = list(ROOT.rglob("*.csv"))

print()
print("CSV FILES FOUND :", len(csv_files))
print("-" * 110)

for path in csv_files:
    try:
        df = pd.read_csv(path, nrows=5)
        columns = list(df.columns)

        matched = [
            c for c in columns
            if any(k in c.lower() for k in keywords)
        ]

        if matched:
            matches.append({
                "file": str(path),
                "matched_columns": matched,
                "column_count": len(columns),
            })

            print()
            print("FILE :", path)
            print("MATCHED COLUMNS :", matched)

    except Exception as e:
        print("SKIPPED :", path)
        print("REASON  :", str(e))

print()
print("=" * 110)
print("PHASE 14 TARGET AUDIT SUMMARY")
print("=" * 110)

print()
print("Files with depth/inundation-related fields :", len(matches))

if not matches:
    print()
    print("NO DIRECT DEPTH / INUNDATION TARGET FOUND")
    print("Next step: build clearly labeled MVP depth/inundation proxy.")
else:
    print()
    print("POTENTIAL TARGET SOURCES FOUND")
    print("-" * 110)

    for item in matches:
        print()
        print(item["file"])
        print("  ", item["matched_columns"])

print()
print("=" * 110)
print("IMPORTANT")
print("=" * 110)

print("""
Do NOT use:
    flood_event_count
    flood_severity_score
    flood_duration_days
    flood_event_flag
    target_flood

as flood-depth regression targets.

Do NOT use:
    flood_area_affected

unless it contains non-zero, meaningful inundation measurements.

River level is hydrological information and is NOT automatically flood depth.
""")

print("=" * 110)
print("PHASE 14A TARGET AUDIT COMPLETE")
print("=" * 110)