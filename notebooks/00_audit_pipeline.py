from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

print("=" * 100)
print("CHETAKAI V1 - COMPLETE NOTEBOOK + FEATURE PIPELINE AUDIT")
print("=" * 100)
print()
print("PROJECT ROOT :", ROOT)
print("NOTEBOOK DIR :", NOTEBOOKS)
print("RAW DIR      :", RAW)
print("PROCESSED DIR:", PROCESSED)
print()


# ---------------------------------------------------------------------
# 1. DISCOVER NOTEBOOK / PYTHON SCRIPTS
# ---------------------------------------------------------------------

scripts = sorted(
    NOTEBOOKS.glob("*.py"),
    key=lambda x: (
        int(re.match(r"(\d+)", x.name).group(1))
        if re.match(r"(\d+)", x.name)
        else 9999,
        x.name
    )
)

print("=" * 100)
print("1. NOTEBOOKS / PYTHON SCRIPTS FOUND")
print("=" * 100)

if not scripts:
    print("NO PYTHON SCRIPTS FOUND")
else:
    for script in scripts:
        print(script.name)

print()
print("TOTAL SCRIPTS:", len(scripts))
print()


# ---------------------------------------------------------------------
# 2. SHOW SCRIPT CONTENT SUMMARY
# ---------------------------------------------------------------------

print("=" * 100)
print("2. SCRIPT PURPOSE / INPUT / OUTPUT DETECTION")
print("=" * 100)

script_info = []

for script in scripts:

    try:
        text = script.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        text = ""

    lines = text.splitlines()

    functions = re.findall(
        r"^\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)",
        text,
        re.MULTILINE
    )

    outputs = []

    patterns = [
        r'["\']([^"\']*(?:processed|output|features|master)[^"\']*)["\']',
        r'Path\([^)]*["\']([^"\']+)["\']',
        r'to_csv\(\s*["\']([^"\']+)["\']',
        r'to_file\(\s*["\']([^"\']+)["\']',
        r'write_text\(\s*["\']([^"\']+)["\']'
    ]

    for pattern in patterns:
        try:
            matches = re.findall(pattern, text, re.IGNORECASE)
            outputs.extend(matches)
        except:
            pass

    outputs = list(dict.fromkeys(outputs))

    print()
    print("-" * 100)
    print("SCRIPT:", script.name)
    print("-" * 100)

    print("LINES:", len(lines))

    if functions:
        print("FUNCTIONS:")
        for fn in functions[:20]:
            print("  -", fn)

    if outputs:
        print("POSSIBLE OUTPUT REFERENCES:")
        for out in outputs[:20]:
            print("  -", out)

    script_info.append({
        "script": script.name,
        "lines": len(lines),
        "functions": len(functions),
        "output_refs": len(outputs)
    })

print()


# ---------------------------------------------------------------------
# 3. PROCESSED DATA INVENTORY
# ---------------------------------------------------------------------

print("=" * 100)
print("3. PROCESSED DATASET INVENTORY")
print("=" * 100)

processed_files = [
    p for p in PROCESSED.rglob("*")
    if p.is_file()
]

if not processed_files:
    print("NO PROCESSED FILES FOUND")

processed_rows = []

for p in sorted(processed_files):

    size_mb = p.stat().st_size / (1024 * 1024)

    processed_rows.append({
        "file": str(p.relative_to(ROOT)),
        "extension": p.suffix.lower(),
        "size_mb": round(size_mb, 2)
    })

for row in processed_rows:
    print(
        f"{row['file']:<85} "
        f"{row['size_mb']:>10} MB"
    )

print()
print("TOTAL PROCESSED FILES:", len(processed_files))
print()


# ---------------------------------------------------------------------
# 4. CSV DATASET SCHEMA + QUALITY
# ---------------------------------------------------------------------

print("=" * 100)
print("4. PROCESSED CSV FEATURE AUDIT")
print("=" * 100)

csv_files = sorted(PROCESSED.rglob("*.csv"))

if not csv_files:
    print("NO CSV FILES FOUND")

csv_summary = []

for csv in csv_files:

    print()
    print("-" * 100)
    print("FILE:", csv.relative_to(ROOT))
    print("-" * 100)

    try:

        df = pd.read_csv(csv)

        print("ROWS   :", len(df))
        print("COLUMNS:", len(df.columns))

        print()
        print("FEATURES:")

        for col in df.columns:
            print("  -", col)

        print()
        print("NULL COUNTS:")

        nulls = df.isna().sum()

        for col, value in nulls.items():
            if value > 0:
                print(f"  - {col}: {value}")

        print()
        print("DUPLICATE ROWS:", df.duplicated().sum())

        if len(df) > 0:
            print()
            print("SAMPLE:")
            print(df.head(3).to_string(index=False))

        csv_summary.append({
            "file": str(csv.relative_to(ROOT)),
            "rows": len(df),
            "columns": len(df.columns),
            "duplicates": int(df.duplicated().sum()),
            "null_cells": int(df.isna().sum().sum()),
            "status": "READABLE"
        })

    except Exception as e:

        print("ERROR READING CSV:")
        print(e)

        csv_summary.append({
            "file": str(csv.relative_to(ROOT)),
            "rows": None,
            "columns": None,
            "duplicates": None,
            "null_cells": None,
            "status": "FAILED"
        })

print()


# ---------------------------------------------------------------------
# 5. RAW DATASET INVENTORY
# ---------------------------------------------------------------------

print("=" * 100)
print("5. RAW DATASET INVENTORY")
print("=" * 100)

raw_dirs = sorted([
    p for p in RAW.iterdir()
    if p.is_dir()
])

raw_summary = []

for directory in raw_dirs:

    files = [
        p for p in directory.rglob("*")
        if p.is_file()
    ]

    size_mb = sum(
        p.stat().st_size / (1024 * 1024)
        for p in files
    )

    print(
        f"{directory.name:<35} "
        f"files={len(files):>6} "
        f"size={size_mb:>12.2f} MB"
    )

    raw_summary.append({
        "dataset": directory.name,
        "files": len(files),
        "size_mb": round(size_mb, 2)
    })

print()


# ---------------------------------------------------------------------
# 6. SPECIAL DATASET CHECKS
# ---------------------------------------------------------------------

print("=" * 100)
print("6. SPECIAL DATASET CHECKS")
print("=" * 100)


checks = {
    "RAIN_CHIRPS":
        list((RAW / "rainfall").rglob("*.tif"))
        if (RAW / "rainfall").exists() else [],

    "DEM":
        list((RAW / "dem").rglob("*.tif"))
        if (RAW / "dem").exists() else [],

    "SOIL":
        list((RAW / "soil").rglob("*"))
        if (RAW / "soil").exists() else [],

    "SATELLITE":
        list((RAW / "satellite").rglob("*"))
        if (RAW / "satellite").exists() else [],

    "LULC":
        list((RAW / "land_use_land_cover").rglob("*"))
        if (RAW / "land_use_land_cover").exists() else [],

    "RIVER_LEVEL":
        list((RAW / "river_water_level").rglob("*"))
        if (RAW / "river_water_level").exists() else [],

    "DISCHARGE":
        list((RAW / "river_discharge").rglob("*"))
        if (RAW / "river_discharge").exists() else [],

    "FLOOD_EVENTS":
        list((RAW / "flood_events").rglob("*"))
        if (RAW / "flood_events").exists() else [],

    "RESERVOIRS":
        list((RAW / "reservoirs").rglob("*"))
        if (RAW / "reservoirs").exists() else [],

    "POPULATION":
        list((RAW / "population").rglob("*"))
        if (RAW / "population").exists() else [],

    "ADMINISTRATIVE":
        list((RAW / "administrative").rglob("*"))
        if (RAW / "administrative").exists() else [],

    "INFRASTRUCTURE":
        list((RAW / "infrastructure").rglob("*"))
        if (RAW / "infrastructure").exists() else [],

    "HYDROGRAPHY":
        list((RAW / "hydrography").rglob("*"))
        if (RAW / "hydrography").exists() else [],
}

for name, files in checks.items():

    real_files = [
        p for p in files
        if p.is_file()
    ]

    print(
        f"{name:<25} "
        f"{'AVAILABLE' if real_files else 'MISSING'} "
        f"({len(real_files)} files)"
    )

print()


# ---------------------------------------------------------------------
# 7. AUTOMATIC DATASET STATUS
# ---------------------------------------------------------------------

print("=" * 100)
print("7. DATASET PIPELINE STATUS")
print("=" * 100)

dataset_output_map = {

    "RAIN_CHIRPS":
        [
            "rainfall",
            "chirps_monthly_basin_features.csv"
        ],

    "DEM":
        [
            "dem",
            "dem_basin_features.csv"
        ],

    "HYDROGRAPHY":
        [
            "hydrography",
            "hydrography_basin_features.csv"
        ],

    "RESERVOIRS":
        [
            "reservoirs",
            "reservoir_basin_features.csv"
        ],

    "SATELLITE":
        [
            "satellite",
            "satellite_basin_features.csv"
        ],

    "SOIL":
        [
            "soil",
            "soil_basin_features.csv"
        ],

    "LULC":
        [
            "lulc",
            "lulc_basin_features.csv"
        ],

    "POPULATION":
        [
            "population",
            "population_admin_basin_features.csv"
        ],

    "ADMINISTRATIVE":
        [
            "administrative",
            "administrative_features.csv"
        ],

    "INFRASTRUCTURE":
        [
            "infrastructure",
            "infrastructure_basin_features.csv"
        ],

    "MASTER":
        [
            "master",
            "chetakai_v1_master_ml_dataset.csv"
        ]
}

for dataset, mapping in dataset_output_map.items():

    folder = PROCESSED / mapping[0]
    expected_name = mapping[1]

    expected = folder / expected_name

    candidates = []

    if folder.exists():
        candidates = [
            p for p in folder.rglob("*")
            if p.is_file()
        ]

    exact = expected.exists()

    if exact:

        size = expected.stat().st_size

        if size == 0:
            status = "EMPTY"
        else:
            status = "OUTPUT EXISTS"

    elif candidates:
        status = "OTHER OUTPUT EXISTS"

    else:
        status = "NO OUTPUT"

    print(
        f"{dataset:<20} -> "
        f"{status:<22} "
        f"folder={mapping[0]}"
    )

print()


# ---------------------------------------------------------------------
# 8. FIND FALLBACK / PLACEHOLDER OUTPUTS
# ---------------------------------------------------------------------

print("=" * 100)
print("8. POSSIBLE FALLBACK / PLACEHOLDER OUTPUTS")
print("=" * 100)

keywords = [
    "fallback",
    "dummy",
    "placeholder",
    "estimated",
    "synthetic",
    "approx",
    "approximation",
    "empty"
]

found_fallback = False

for csv in csv_files:

    try:
        df = pd.read_csv(csv)

        text = df.astype(str).to_string().lower()

        matches = [
            word for word in keywords
            if word in text
        ]

        if matches:
            print()
            print(csv.relative_to(ROOT))
            print("Possible indicators:", ", ".join(matches))
            found_fallback = True

    except:
        pass

if not found_fallback:
    print("No obvious fallback indicators detected.")

print()


# ---------------------------------------------------------------------
# 9. MASTER DATASET INSPECTION
# ---------------------------------------------------------------------

print("=" * 100)
print("9. MASTER DATASET CHECK")
print("=" * 100)

master_candidates = []

for p in PROCESSED.rglob("*"):
    if p.is_file() and "master" in p.name.lower():
        master_candidates.append(p)

if not master_candidates:

    print("NO MASTER DATASET FOUND")

else:

    for master in master_candidates:

        print()
        print("MASTER CANDIDATE:")
        print(master.relative_to(ROOT))
        print("SIZE MB:", round(master.stat().st_size / (1024 * 1024), 2))

        try:

            if master.suffix.lower() == ".csv":

                df = pd.read_csv(master)

                print("ROWS:", len(df))
                print("COLUMNS:", len(df.columns))

                print()
                print("COLUMNS:")

                for col in df.columns:
                    print("  -", col)

        except Exception as e:
            print("Could not inspect:", e)

print()


# ---------------------------------------------------------------------
# 10. FINAL AUDIT SUMMARY
# ---------------------------------------------------------------------

print("=" * 100)
print("10. FINAL AUDIT SUMMARY")
print("=" * 100)

print()
print("SCRIPTS FOUND       :", len(scripts))
print("RAW DATASET GROUPS  :", len(raw_dirs))
print("PROCESSED FILES     :", len(processed_files))
print("PROCESSED CSV FILES :", len(csv_files))

print()
print("""
IMPORTANT:

This audit does NOT decide that an output is scientifically correct.

It only establishes:

1. What scripts exist.
2. What raw datasets exist.
3. What processed outputs exist.
4. What columns/features those outputs contain.
5. Which outputs are empty or unreadable.
6. Which outputs may contain fallback/placeholder values.
7. Whether a master dataset currently exists.

After this audit we will classify every notebook as:

    [DONE]
    [DONE BUT NEEDS VALIDATION]
    [RERUN REQUIRED]
    [CODE FIX REQUIRED]
    [RAW DATA MISSING]
    [NOT STARTED]
    [MASTER DATASET DEPENDENCY]

DO NOT DELETE ANY DATA.
DO NOT REDOWNLOAD DATA.
DO NOT RUN ALL NOTEBOOKS YET.
""")

print("=" * 100)
print("AUDIT COMPLETE")
print("=" * 100)