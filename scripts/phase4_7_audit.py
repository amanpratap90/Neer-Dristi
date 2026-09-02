from pathlib import Path
import pandas as pd

ROOT = Path("data/processed")

print("=" * 110)
print("CHETAKAI PHASE 4.7 — FINAL MISSING DATA AUDIT")
print("=" * 110)

feature_dirs = [
    "administrative",
    "dem",
    "hydrography",
    "infrastructure",
    "lulc",
    "population",
    "rainfall",
    "reservoirs",
    "satellite",
    "soil",
]

for folder in feature_dirs:
    folder_path = ROOT / folder

    if not folder_path.exists():
        print(f"\n[{folder}]")
        print("STATUS: DIRECTORY MISSING")
        continue

    csv_files = [
        f for f in folder_path.glob("*.csv")
        if "backup" not in f.name.lower()
    ]

    if not csv_files:
        print(f"\n[{folder}]")
        print("STATUS: NO CURRENT CSV")
        continue

    for file in csv_files:
        try:
            df = pd.read_csv(file)

            basin_cols = [
                c for c in df.columns
                if any(
                    x in c.lower()
                    for x in [
                        "canonical_basin_id",
                        "cwc_basin_id",
                        "basin_id",
                        "ba_code",
                        "bacode",
                        "ba_name",
                    ]
                )
            ]

            print(f"\n[{folder}/{file.name}]")
            print(f"Rows              : {len(df)}")
            print(f"Columns           : {len(df.columns)}")
            print(f"Basin columns     : {basin_cols}")
            print(f"Total null cells  : {int(df.isna().sum().sum())}")

            if basin_cols:
                col = basin_cols[0]
                print(f"Unique basins     : {df[col].nunique(dropna=True)}")
                print(f"Missing basin IDs : {int(df[col].isna().sum())}")

        except Exception as e:
            print(f"\n[{folder}/{file.name}]")
            print(f"ERROR: {e}")

print("\n" + "=" * 110)
print("PHASE 4.7 AUDIT COMPLETE")
print("=" * 110)