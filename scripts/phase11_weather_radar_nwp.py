from pathlib import Path
import shutil
import numpy as np
import pandas as pd


ROOT = Path("data/processed")
MASTER = ROOT / "master" / "chetakai_v1_master_phase9.csv"

OUT_DIR = ROOT / "master" / "phase11"
OUT = OUT_DIR / "chetakai_v1_master_phase11.csv"
BACKUP = OUT_DIR / "chetakai_v1_master_phase9_backup.csv"
REPORT = OUT_DIR / "phase11_feature_report.csv"


print("=" * 110)
print("CHETAKAI V1 — PHASE 11 WEATHER / NWP / RADAR MVP FEATURE EXPANSION")
print("=" * 110)


# ------------------------------------------------------------------
# PATHS
# ------------------------------------------------------------------

if not MASTER.exists():
    raise FileNotFoundError(
        f"Phase 9 master not found:\n{MASTER}"
    )

OUT_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# LOAD FROZEN MASTER
# ------------------------------------------------------------------

print("\nLOADING FROZEN PHASE 9 MASTER")
print("-" * 110)

df = pd.read_csv(MASTER)

original_df = df.copy(deep=True)
original_columns = list(df.columns)
original_rows = len(df)

print(f"Rows       : {original_rows}")
print(f"Columns    : {len(original_columns)}")
print(f"Basins     : {df['canonical_basin_id'].nunique()}")
print(f"Date range : {df['timestamp'].min()} → {df['timestamp'].max()}")


# ------------------------------------------------------------------
# BACKUP
# ------------------------------------------------------------------

if not BACKUP.exists():
    shutil.copy2(MASTER, BACKUP)
    print(f"\nBackup created:\n{BACKUP}")
else:
    print(f"\nBackup already exists:\n{BACKUP}")


# ------------------------------------------------------------------
# REQUIRED COLUMNS
# ------------------------------------------------------------------

required = [
    "canonical_basin_id",
    "timestamp",
    "rainfall_mean_mm",
    "rainfall_sum_mm",
    "rainfall_min_mm",
    "rainfall_max_mm",
    "rainfall_std_mm",
    "rainfall_p90_mm",
    "rainfall_p95_mm",
    "rainfall_p99_mm",
    "rainfall_3month_sum_mm",
    "rainfall_6month_sum_mm",
    "rainfall_12month_sum_mm",
    "rainfall_climatology_mm",
    "rainfall_anomaly_mm",
    "rainfall_anomaly_pct",
    "annual_rainfall_mm",
]

missing = [c for c in required if c not in df.columns]

if missing:
    raise ValueError(
        f"Required source columns missing: {missing}"
    )


# ------------------------------------------------------------------
# DATE
# ------------------------------------------------------------------

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

if df["timestamp"].isna().any():
    raise ValueError("Invalid timestamps detected.")


df = df.sort_values(
    ["canonical_basin_id", "timestamp"]
).reset_index(drop=True)


# ------------------------------------------------------------------
# SAFE NUMERIC HELPER
# ------------------------------------------------------------------

def num(col):
    return pd.to_numeric(df[col], errors="coerce")


rain_mean = num("rainfall_mean_mm")
rain_sum = num("rainfall_sum_mm")
rain_min = num("rainfall_min_mm")
rain_max = num("rainfall_max_mm")
rain_std = num("rainfall_std_mm")
rain_p90 = num("rainfall_p90_mm")
rain_p95 = num("rainfall_p95_mm")
rain_p99 = num("rainfall_p99_mm")

rain_3m = num("rainfall_3month_sum_mm")
rain_6m = num("rainfall_6month_sum_mm")
rain_12m = num("rainfall_12month_sum_mm")

clim = num("rainfall_climatology_mm")
anom = num("rainfall_anomaly_mm")
anom_pct = num("rainfall_anomaly_pct")
annual = num("annual_rainfall_mm")


# ------------------------------------------------------------------
# FEATURE CONTAINER
# ------------------------------------------------------------------

new = pd.DataFrame(index=df.index)


# ==================================================================
# 1. OBSERVATIONAL WEATHER — MVP PROXIES
# ==================================================================

print("\n1. OBSERVATIONAL WEATHER PROXY FEATURES")
print("-" * 110)

new["obs_rain_intensity_proxy_mm"] = (
    rain_max.clip(lower=0)
)

new["obs_rain_mean_intensity_proxy_mm"] = (
    rain_mean.clip(lower=0)
)

new["obs_rain_variability_proxy"] = (
    rain_std.clip(lower=0)
)

new["obs_heavy_rain_ratio_proxy"] = (
    rain_p95 / rain_mean.replace(0, np.nan)
).replace([np.inf, -np.inf], np.nan)

new["obs_extreme_rain_ratio_proxy"] = (
    rain_p99 / rain_mean.replace(0, np.nan)
).replace([np.inf, -np.inf], np.nan)

new["obs_rain_range_proxy_mm"] = (
    rain_max - rain_min
).clip(lower=0)

new["obs_rain_p90_excess_proxy_mm"] = (
    rain_p90 - rain_mean
).clip(lower=0)

new["obs_rain_p95_excess_proxy_mm"] = (
    rain_p95 - rain_mean
).clip(lower=0)

new["obs_rain_p99_excess_proxy_mm"] = (
    rain_p99 - rain_mean
).clip(lower=0)


# ==================================================================
# 2. SHORT-TERM PRECIPITATION WINDOWS
# ==================================================================

print("\n2. SHORT-TERM PRECIPITATION WINDOW FEATURES")
print("-" * 110)

new["rainfall_1h_proxy"] = rain_mean
new["rainfall_3h_proxy"] = rain_mean * 3
new["rainfall_6h_proxy"] = rain_mean * 6
new["rainfall_12h_proxy"] = rain_mean * 12
new["rainfall_24h_proxy"] = rain_mean * 24
new["rainfall_72h_proxy"] = rain_mean * 72


# ==================================================================
# 3. RADAR-LIKE PRECIPITATION FEATURES
# ==================================================================

print("\n3. RADAR-LIKE MVP PROXY FEATURES")
print("-" * 110)

new["radar_rain_rate_proxy"] = (
    rain_mean.clip(lower=0)
)

new["radar_intensity_proxy"] = (
    rain_max.clip(lower=0)
)

new["radar_mean_intensity_proxy"] = (
    rain_p90.clip(lower=0)
)

new["radar_max_intensity_proxy"] = (
    rain_p99.clip(lower=0)
)

new["radar_accumulation_1h_proxy"] = (
    rain_mean.clip(lower=0)
)

new["radar_accumulation_3h_proxy"] = (
    rain_mean.clip(lower=0) * 3
)

new["radar_accumulation_6h_proxy"] = (
    rain_mean.clip(lower=0) * 6
)

new["radar_accumulation_12h_proxy"] = (
    rain_mean.clip(lower=0) * 12
)

new["radar_accumulation_24h_proxy"] = (
    rain_mean.clip(lower=0) * 24
)

new["radar_accumulation_72h_proxy"] = (
    rain_mean.clip(lower=0) * 72
)

new["radar_spatial_variability_proxy"] = (
    rain_std.clip(lower=0)
)

new["radar_extreme_cell_proxy"] = (
    rain_p99 - rain_p95
).clip(lower=0)

new["radar_convective_intensity_proxy"] = (
    (
        rain_p99 - rain_p90
    ) /
    rain_mean.replace(0, np.nan)
).replace([np.inf, -np.inf], np.nan)


# ==================================================================
# 4. NWP-LIKE PRECIPITATION FEATURES
# ==================================================================

print("\n4. NWP-LIKE MVP PROXY FEATURES")
print("-" * 110)

new["nwp_rain_1h_proxy"] = rain_mean
new["nwp_rain_3h_proxy"] = rain_mean * 3
new["nwp_rain_6h_proxy"] = rain_mean * 6
new["nwp_rain_12h_proxy"] = rain_mean * 12
new["nwp_rain_24h_proxy"] = rain_mean * 24
new["nwp_rain_72h_proxy"] = rain_mean * 72


# ==================================================================
# 5. NWP ANOMALY / FORECAST-STYLE SIGNAL
# ==================================================================

print("\n5. NWP-STYLE ANOMALY FEATURES")
print("-" * 110)

new["nwp_rain_anomaly_proxy_mm"] = anom

new["nwp_rain_anomaly_pct_proxy"] = anom_pct

new["nwp_climatology_ratio_proxy"] = (
    rain_mean / clim.replace(0, np.nan)
).replace([np.inf, -np.inf], np.nan)

new["nwp_recent_3month_rain_proxy"] = rain_3m
new["nwp_recent_6month_rain_proxy"] = rain_6m
new["nwp_recent_12month_rain_proxy"] = rain_12m


# ==================================================================
# 6. PRECIPITATION TREND / MOMENTUM
# ==================================================================

print("\n6. PRECIPITATION MOMENTUM FEATURES")
print("-" * 110)

group = df.groupby("canonical_basin_id", sort=False)

new["rainfall_prev_month_proxy"] = group[
    "rainfall_mean_mm"
].shift(1)

new["rainfall_prev_2month_proxy"] = group[
    "rainfall_mean_mm"
].shift(2)

new["rainfall_prev_3month_proxy"] = group[
    "rainfall_mean_mm"
].shift(3)

new["rainfall_month_change_proxy"] = (
    rain_mean -
    new["rainfall_prev_month_proxy"]
)

new["rainfall_3month_momentum_proxy"] = (
    rain_mean -
    new["rainfall_prev_3month_proxy"]
)


# ==================================================================
# 7. CUMULATIVE RAINFALL PRESSURE
# ==================================================================

print("\n7. CUMULATIVE RAINFALL PRESSURE")
print("-" * 110)

new["rainfall_3m_pressure_proxy"] = (
    rain_3m / 3
)

new["rainfall_6m_pressure_proxy"] = (
    rain_6m / 6
)

new["rainfall_12m_pressure_proxy"] = (
    rain_12m / 12
)

new["rainfall_annual_pressure_proxy"] = (
    annual
)


# ==================================================================
# 8. SATELLITE-RELATED ADDITIVE PROXIES
# ==================================================================

print("\n8. SATELLITE-WETNESS PROXY FEATURES")
print("-" * 110)

if "ndwi_mean" in df.columns:
    ndwi = num("ndwi_mean")
    new["satellite_wetness_proxy"] = ndwi

if "water_fraction" in df.columns:
    water_fraction = num("water_fraction")
    new["satellite_surface_water_proxy"] = water_fraction

if "vegetation_fraction" in df.columns:
    vegetation = num("vegetation_fraction")
    new["satellite_vegetation_proxy"] = vegetation


# ==================================================================
# 9. RUNOFF / HYDROLOGICAL RESPONSE PROXY
# ==================================================================

print("\n9. HYDROLOGICAL RESPONSE PROXY FEATURES")
print("-" * 110)

if "soil_runoff_proxy" in df.columns:
    soil_runoff = num("soil_runoff_proxy")
else:
    soil_runoff = pd.Series(0.5, index=df.index)

if "river_density_km_per_km2" in df.columns:
    river_density = num("river_density_km_per_km2")
else:
    river_density = pd.Series(0.0, index=df.index)

if "water_fraction" in df.columns:
    water_frac = num("water_fraction").fillna(0)
else:
    water_frac = pd.Series(0.0, index=df.index)


new["runoff_pressure_proxy"] = (
    rain_3m *
    (0.5 + soil_runoff.fillna(0.5))
)

new["hydrological_loading_proxy"] = (
    rain_6m *
    (1 + river_density.fillna(0))
)

new["basin_wetness_pressure_proxy"] = (
    rain_12m *
    (1 + water_frac)
)


# ==================================================================
# 10. FLOOD-RELEVANT PRECIPITATION STRESS
# ==================================================================

print("\n10. FLOOD PRECIPITATION STRESS PROXIES")
print("-" * 110)

new["rainfall_flood_stress_proxy"] = (
    (
        rain_mean.fillna(0) *
        0.25
    )
    +
    (
        rain_3m.fillna(0) *
        0.25
    )
    +
    (
        rain_6m.fillna(0) *
        0.20
    )
    +
    (
        rain_12m.fillna(0) *
        0.10
    )
    +
    (
        rain_p95.fillna(0) *
        0.10
    )
    +
    (
        rain_p99.fillna(0) *
        0.10
    )
)

new["extreme_precipitation_stress_proxy"] = (
    rain_p99.fillna(0)
    +
    rain_p95.fillna(0)
    +
    rain_p90.fillna(0)
)

new["antecedent_wetness_proxy"] = (
    rain_3m.fillna(0)
    + rain_6m.fillna(0) * 0.5
)

new["flash_flood_precipitation_proxy"] = (
    rain_max.fillna(0)
    + rain_p99.fillna(0)
    + rain_std.fillna(0)
)


# ==================================================================
# 11. APPEND ONLY
# ==================================================================

print("\nAPPENDING NEW FEATURES")
print("-" * 110)

duplicate_new = sorted(
    set(new.columns).intersection(original_columns)
)

if duplicate_new:
    raise ValueError(
        "SAFETY ABORT: New feature names collide with existing columns:\n"
        + "\n".join(duplicate_new)
    )

df_final = pd.concat(
    [df, new],
    axis=1
)


# ==================================================================
# 12. HARD SAFETY VALIDATION
# ==================================================================

print("\nHARD SAFETY VALIDATION")
print("-" * 110)

if len(df_final) != original_rows:
    raise ValueError(
        "SAFETY ABORT: Row count changed."
    )

if list(df_final.columns[:len(original_columns)]) != original_columns:
    raise ValueError(
        "SAFETY ABORT: Original column order changed."
    )

for col in original_columns:
    a = original_df[col]
    b = df_final[col]

    if pd.api.types.is_numeric_dtype(a):
        equal = np.allclose(
            pd.to_numeric(a, errors="coerce").fillna(np.nan),
            pd.to_numeric(b, errors="coerce").fillna(np.nan),
            equal_nan=True
        )
    else:
        equal = a.astype(str).equals(b.astype(str))

    if not equal:
        raise ValueError(
            f"SAFETY ABORT: Existing column modified: {col}"
        )

print("Original rows unchanged      : PASS")
print("Original columns unchanged   : PASS")
print("Original values unchanged    : PASS")
print("Original column order intact : PASS")
print("Additive-only operation      : PASS")


# ==================================================================
# 13. FEATURE REPORT
# ==================================================================

report_rows = []

for col in new.columns:
    report_rows.append({
        "feature": col,
        "dtype": str(df_final[col].dtype),
        "null_count": int(df_final[col].isna().sum()),
        "null_pct": float(
            df_final[col].isna().mean() * 100
        ),
        "source_type": "derived_proxy",
    })

report = pd.DataFrame(report_rows)


# ==================================================================
# 14. SAVE
# ==================================================================

df_final.to_csv(
    OUT,
    index=False
)

report.to_csv(
    REPORT,
    index=False
)


# ==================================================================
# 15. FINAL VALIDATION
# ==================================================================

print("\n" + "=" * 110)
print("PHASE 11 FINAL VALIDATION")
print("=" * 110)

print(f"Original columns : {len(original_columns)}")
print(f"New columns      : {len(new.columns)}")
print(f"Final columns    : {len(df_final.columns)}")
print(f"Rows             : {len(df_final)}")
print(
    f"Basins           : "
    f"{df_final['canonical_basin_id'].nunique()}"
)
print(
    f"Date range       : "
    f"{df_final['timestamp'].min()} → "
    f"{df_final['timestamp'].max()}"
)

print("\nNEW FEATURES")
print("-" * 110)

for col in new.columns:
    print(f"  ADD: {col}")

print("\nOUTPUT")
print("-" * 110)

print(OUT)

print("\nREPORT")
print("-" * 110)

print(REPORT)

print("\n" + "=" * 110)
print("🔥 PHASE 11 PASS — ADDITIVE MVP WEATHER EXPANSION COMPLETE")
print("=" * 110)

print(
    f"""
Frozen source       : Phase 9 master
Original columns    : {len(original_columns)}
Added columns       : {len(new.columns)}
Final columns       : {len(df_final.columns)}
Rows                : {len(df_final)}

Existing data       : UNCHANGED
Existing columns    : UNCHANGED
Existing values     : UNCHANGED
Row count           : UNCHANGED

NWP features        : PROXY
Radar features      : PROXY
Observation weather : PROXY
Satellite wetness   : PROXY
Hydrological        : PROXY

No existing Phase 8/9/10 dataset was overwritten.
"""
)