from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd


ROOT = Path("data/processed")

MASTER = ROOT / "master" / "chetakai_v1_master_phase8.csv"
FLOOD = ROOT / "flood_events" / "flood_events_model_ready.csv"

REGISTRY = ROOT / "basin_registry.csv"

BASIN_FILE = Path(
    "data/raw/basin_boundaries/cwc_basins.geojson"
)

OUT = ROOT / "master" / "chetakai_v1_master_phase9.csv"
REPORT = ROOT / "master" / "phase9_flood_label_report.csv"
EVENT_REPORT = ROOT / "master" / "phase9_event_alignment_report.csv"
BACKUP = ROOT / "master" / "chetakai_v1_master_phase8_backup.csv"


print("=" * 110)
print("CHETAKAI V1 — PHASE 9 FLOOD LABEL ENGINEERING")
print("=" * 110)


# ------------------------------------------------------------------
# PATH VALIDATION
# ------------------------------------------------------------------

for path, name in [
    (MASTER, "Phase 8 master"),
    (FLOOD, "Flood events"),
    (REGISTRY, "Basin registry"),
    (BASIN_FILE, "Basin geometry"),
]:
    if not path.exists():
        raise FileNotFoundError(
            f"{name} not found:\n{path}"
        )


# ------------------------------------------------------------------
# LOAD DATASETS
# ------------------------------------------------------------------

print("\nLOADING DATASETS")
print("-" * 110)

master = pd.read_csv(MASTER)
flood = pd.read_csv(FLOOD)
registry = pd.read_csv(REGISTRY)

print(
    f"MASTER   : rows={len(master):6} cols={len(master.columns):3}"
)

print(
    f"FLOOD    : rows={len(flood):6} cols={len(flood.columns):3}"
)

print(
    f"REGISTRY : rows={len(registry):6} cols={len(registry.columns):3}"
)


# ------------------------------------------------------------------
# MASTER VALIDATION
# ------------------------------------------------------------------

required_master = [
    "canonical_basin_id",
    "timestamp",
]

missing_master = [
    c for c in required_master
    if c not in master.columns
]

if missing_master:
    raise ValueError(
        f"Missing required master columns: {missing_master}"
    )


master["timestamp"] = pd.to_datetime(
    master["timestamp"],
    errors="coerce"
)

if master["timestamp"].isna().any():
    raise ValueError(
        "Invalid timestamps detected in Phase 8 master."
    )


master_key = [
    "canonical_basin_id",
    "timestamp",
]


if master.duplicated(
    subset=master_key
).any():

    raise ValueError(
        "Phase 8 contains duplicate basin/timestamp keys."
    )


print("\nMASTER VALIDATION")
print("-" * 110)

print(
    "Rows:",
    len(master)
)

print(
    "Basins:",
    master["canonical_basin_id"].nunique()
)

print(
    "Date:",
    master["timestamp"].min(),
    "→",
    master["timestamp"].max()
)


# ------------------------------------------------------------------
# BACKUP
# ------------------------------------------------------------------

OUT.parent.mkdir(
    parents=True,
    exist_ok=True
)

if not BACKUP.exists():

    master.to_csv(
        BACKUP,
        index=False
    )

    print("\nPhase 8 backup created:")
    print(BACKUP.resolve())

else:

    print("\nPhase 8 backup already exists:")
    print(BACKUP.resolve())


# ------------------------------------------------------------------
# REGISTRY VALIDATION
# ------------------------------------------------------------------

print("\nBASIN REGISTRY VALIDATION")
print("-" * 110)

required_registry = [
    "canonical_basin_id",
    "ba_code",
    "basin_name",
]

missing_registry = [
    c for c in required_registry
    if c not in registry.columns
]

if missing_registry:
    raise ValueError(
        f"Missing registry columns: {missing_registry}"
    )


registry = registry[
    required_registry
].copy()


registry["ba_code"] = (
    registry["ba_code"]
    .astype(str)
    .str.strip()
)


registry["canonical_basin_id"] = (
    registry["canonical_basin_id"]
    .astype(str)
    .str.strip()
)


if registry["ba_code"].duplicated().any():

    duplicates = (
        registry.loc[
            registry["ba_code"].duplicated(
                keep=False
            ),
            "ba_code"
        ]
        .unique()
        .tolist()
    )

    raise ValueError(
        f"Duplicate ba_code values in registry: {duplicates}"
    )


if registry["canonical_basin_id"].duplicated().any():

    duplicates = (
        registry.loc[
            registry["canonical_basin_id"].duplicated(
                keep=False
            ),
            "canonical_basin_id"
        ]
        .unique()
        .tolist()
    )

    raise ValueError(
        "Duplicate canonical_basin_id values in registry: "
        f"{duplicates}"
    )


print(
    "Registry basins:",
    registry["canonical_basin_id"].nunique()
)

print(
    "Registry ba_codes:",
    registry["ba_code"].nunique()
)


# ------------------------------------------------------------------
# LOAD BASIN GEOMETRY
# ------------------------------------------------------------------

print("\nLOADING BASIN GEOMETRY")
print("-" * 110)

basins = gpd.read_file(
    BASIN_FILE
)

print(
    "Geometry rows:",
    len(basins)
)

print(
    "Geometry CRS:",
    basins.crs
)

print(
    "Geometry columns:",
    list(basins.columns)
)


required_geometry = [
    "ba_code",
    "geometry",
]

missing_geometry = [
    c for c in required_geometry
    if c not in basins.columns
]

if missing_geometry:
    raise ValueError(
        f"Missing geometry columns: {missing_geometry}"
    )


if basins.crs is None:
    raise ValueError(
        "Basin geometry has no CRS."
    )


basins["ba_code"] = (
    basins["ba_code"]
    .astype(str)
    .str.strip()
)


basins = basins[
    [
        "ba_code",
        "geometry",
    ]
].copy()


basins = basins.dropna(
    subset=[
        "ba_code",
        "geometry",
    ]
)


basins = basins.drop_duplicates(
    subset=["ba_code"],
    keep="first"
)


print(
    "Unique basin polygons:",
    basins["ba_code"].nunique()
)


# ------------------------------------------------------------------
# VERIFY GEOMETRY ↔ REGISTRY
# ------------------------------------------------------------------

print("\nVERIFYING GEOMETRY ↔ REGISTRY")
print("-" * 110)

geometry_codes = set(
    basins["ba_code"]
)

registry_codes = set(
    registry["ba_code"]
)


geometry_without_registry = (
    geometry_codes - registry_codes
)

registry_without_geometry = (
    registry_codes - geometry_codes
)


if geometry_without_registry:

    raise ValueError(
        "Geometry ba_code values missing from registry: "
        f"{sorted(geometry_without_registry)}"
    )


if registry_without_geometry:

    print(
        "WARNING: Registry ba_codes without geometry:",
        sorted(registry_without_geometry)
    )


print(
    "Geometry ↔ registry mapping validated."
)


# ------------------------------------------------------------------
# CREATE CANONICAL ID IN GEOMETRY
# ------------------------------------------------------------------

basins = basins.merge(
    registry[
        [
            "ba_code",
            "canonical_basin_id",
        ]
    ],
    on="ba_code",
    how="left",
    validate="one_to_one"
)


if basins["canonical_basin_id"].isna().any():

    raise ValueError(
        "Some basin polygons could not be assigned "
        "a canonical_basin_id."
    )


print(
    "Canonical basin polygons:",
    basins["canonical_basin_id"].nunique()
)


# ------------------------------------------------------------------
# FLOOD DATA INSPECTION
# ------------------------------------------------------------------

print("\nFLOOD DATASET INSPECTION")
print("-" * 110)

print(
    "Flood columns:"
)

print(
    list(flood.columns)
)

print(
    "\nFirst rows:"
)

print(
    flood.head(5).to_string(
        index=False
    )
)


# ------------------------------------------------------------------
# IDENTIFY DATE COLUMN
# ------------------------------------------------------------------

date_candidates = [
    "timestamp",
    "event_date",
    "date",
    "flood_date",
    "start_date",
    "event_start",
]

flood_date_col = None

for col in date_candidates:

    if col in flood.columns:

        flood_date_col = col
        break


if flood_date_col is None:

    raise ValueError(
        "Could not identify flood event date column."
    )


flood[flood_date_col] = pd.to_datetime(
    flood[flood_date_col],
    errors="coerce"
)


invalid_dates = int(
    flood[flood_date_col].isna().sum()
)


print(
    "\nFlood date column:",
    flood_date_col
)

print(
    "Invalid flood dates:",
    invalid_dates
)


if invalid_dates == len(flood):

    raise ValueError(
        "All flood event dates are invalid."
    )


flood = flood.dropna(
    subset=[flood_date_col]
).copy()


# ------------------------------------------------------------------
# IDENTIFY COORDINATES
# ------------------------------------------------------------------

longitude_candidates = [
    "longitude",
    "lon",
    "lng",
    "LONGITUDE",
]

latitude_candidates = [
    "latitude",
    "lat",
    "LATITUDE",
]


longitude_col = None
latitude_col = None


for col in longitude_candidates:

    if col in flood.columns:

        longitude_col = col
        break


for col in latitude_candidates:

    if col in flood.columns:

        latitude_col = col
        break


if longitude_col is None or latitude_col is None:

    raise ValueError(
        "Flood dataset must contain latitude and longitude."
    )


print(
    "Longitude column:",
    longitude_col
)

print(
    "Latitude column:",
    latitude_col
)


flood[longitude_col] = pd.to_numeric(
    flood[longitude_col],
    errors="coerce"
)

flood[latitude_col] = pd.to_numeric(
    flood[latitude_col],
    errors="coerce"
)


invalid_coordinates = (
    flood[longitude_col].isna()
    | flood[latitude_col].isna()
    | ~flood[longitude_col].between(
        -180,
        180
    )
    | ~flood[latitude_col].between(
        -90,
        90
    )
)


invalid_coordinate_count = int(
    invalid_coordinates.sum()
)


print(
    "Invalid coordinates:",
    invalid_coordinate_count
)


flood = flood.loc[
    ~invalid_coordinates
].copy()


if flood.empty:

    raise ValueError(
        "No valid flood events remain."
    )


# ------------------------------------------------------------------
# CREATE FLOOD POINT GEOMETRY
# ------------------------------------------------------------------

print("\nCREATING FLOOD EVENT POINTS")
print("-" * 110)

flood_gdf = gpd.GeoDataFrame(
    flood.copy(),
    geometry=gpd.points_from_xy(
        flood[longitude_col],
        flood[latitude_col]
    ),
    crs="EPSG:4326"
)


# Reproject to basin CRS.

if flood_gdf.crs != basins.crs:

    flood_gdf = flood_gdf.to_crs(
        basins.crs
    )


print(
    "Flood point CRS:",
    flood_gdf.crs
)


# ------------------------------------------------------------------
# SPATIAL JOIN
# ------------------------------------------------------------------

print("\nSPATIAL FLOOD → BASIN ASSIGNMENT")
print("-" * 110)


joined = gpd.sjoin(
    flood_gdf,
    basins[
        [
            "ba_code",
            "canonical_basin_id",
            "geometry",
        ]
    ],
    how="left",
    predicate="within"
)


if "index_right" in joined.columns:

    joined = joined.drop(
        columns=["index_right"]
    )


assigned_count = int(
    joined[
        "canonical_basin_id"
    ].notna().sum()
)


unassigned_count = int(
    joined[
        "canonical_basin_id"
    ].isna().sum()
)


assignment_rate = (
    assigned_count
    / len(joined)
    * 100
)


print(
    "Valid flood events:",
    len(joined)
)

print(
    "Assigned to basin:",
    assigned_count
)

print(
    "Unassigned:",
    unassigned_count
)

print(
    f"Assignment rate: {assignment_rate:.2f}%"
)


if assigned_count == 0:

    raise RuntimeError(
        "No flood events could be assigned to basins."
    )


# ------------------------------------------------------------------
# KEEP ALIGNED EVENTS
# ------------------------------------------------------------------

aligned_events = joined[
    joined["canonical_basin_id"].notna()
].copy()


# ------------------------------------------------------------------
# TEMPORAL NORMALIZATION
# ------------------------------------------------------------------

aligned_events["timestamp"] = (
    aligned_events[
        flood_date_col
    ]
    .dt.to_period("M")
    .dt.to_timestamp()
)


# ------------------------------------------------------------------
# FLOOD SEVERITY
# ------------------------------------------------------------------

def severity_score(value):

    if pd.isna(value):

        return 1.0

    value = str(
        value
    ).strip().lower()

    mapping = {
        "low": 1.0,
        "minor": 1.0,
        "moderate": 2.0,
        "medium": 2.0,
        "high": 3.0,
        "severe": 3.0,
        "very high": 4.0,
        "extreme": 4.0,
        "critical": 5.0,
    }

    return mapping.get(
        value,
        1.0
    )


if "Severity" in aligned_events.columns:

    aligned_events[
        "flood_severity_score"
    ] = (
        aligned_events[
            "Severity"
        ].apply(
            severity_score
        )
    )

else:

    aligned_events[
        "flood_severity_score"
    ] = 1.0


# ------------------------------------------------------------------
# NUMERIC FLOOD FIELDS
# ------------------------------------------------------------------

numeric_mapping = {
    "AreaAffected": "flood_area_affected",
    "Area Affected": "flood_area_affected",
    "Human fatality": "flood_fatalities",
    "Human injured": "flood_injured",
    "Human Displaced": "flood_displaced",
    "Animal Fatality": "flood_animal_fatalities",
    "Duration(Days)": "flood_duration_days",
}


for source_col, output_col in numeric_mapping.items():

    if source_col in aligned_events.columns:

        aligned_events[
            output_col
        ] = pd.to_numeric(
            aligned_events[
                source_col
            ],
            errors="coerce"
        )


# ------------------------------------------------------------------
# EVENT REPORT
# ------------------------------------------------------------------

event_report_columns = [
    c for c in [
        "UEI",
        flood_date_col,
        "end_date",
        "canonical_basin_id",
        "ba_code",
        "district_event",
        "State",
        "Main Cause",
        "Severity",
        longitude_col,
        latitude_col,
        "timestamp",
    ]
    if c in aligned_events.columns
]


event_report = aligned_events[
    event_report_columns
].copy()


event_report[
    "event_assigned_to_basin"
] = 1


EVENT_REPORT.parent.mkdir(
    parents=True,
    exist_ok=True
)


event_report.to_csv(
    EVENT_REPORT,
    index=False
)


# ------------------------------------------------------------------
# MONTHLY AGGREGATION
# ------------------------------------------------------------------

print("\nMONTHLY FLOOD LABEL AGGREGATION")
print("-" * 110)


group_keys = [
    "canonical_basin_id",
    "timestamp",
]


aggregation = {
    "flood_event_count": (
        "canonical_basin_id",
        "size"
    ),
    "flood_severity_score": (
        "flood_severity_score",
        "sum"
    ),
}


if "flood_area_affected" in aligned_events.columns:

    aggregation[
        "flood_area_affected"
    ] = (
        "flood_area_affected",
        "sum"
    )


if "flood_fatalities" in aligned_events.columns:

    aggregation[
        "flood_fatalities"
    ] = (
        "flood_fatalities",
        "sum"
    )


if "flood_injured" in aligned_events.columns:

    aggregation[
        "flood_injured"
    ] = (
        "flood_injured",
        "sum"
    )


if "flood_displaced" in aligned_events.columns:

    aggregation[
        "flood_displaced"
    ] = (
        "flood_displaced",
        "sum"
    )


if "flood_animal_fatalities" in aligned_events.columns:

    aggregation[
        "flood_animal_fatalities"
    ] = (
        "flood_animal_fatalities",
        "sum"
    )


if "flood_duration_days" in aligned_events.columns:

    aggregation[
        "flood_duration_days"
    ] = (
        "flood_duration_days",
        "sum"
    )


monthly_labels = (
    aligned_events
    .groupby(group_keys)
    .agg(**aggregation)
    .reset_index()
)


# ------------------------------------------------------------------
# BINARY TARGET
# ------------------------------------------------------------------

monthly_labels[
    "flood_event_flag"
] = (
    monthly_labels[
        "flood_event_count"
    ] > 0
).astype("int8")


monthly_labels[
    "target_flood"
] = (
    monthly_labels[
        "flood_event_flag"
    ]
).astype("int8")


# ------------------------------------------------------------------
# MERGE WITH PHASE 8
# ------------------------------------------------------------------

print("\nMERGING FLOOD LABELS INTO PHASE 8")
print("-" * 110)


before_rows = len(master)


master = master.merge(
    monthly_labels,
    on=master_key,
    how="left",
    validate="one_to_one"
)


if len(master) != before_rows:

    raise RuntimeError(
        "Row count changed during flood merge: "
        f"{before_rows} → {len(master)}"
    )


# ------------------------------------------------------------------
# FILL NON-FLOOD MONTHS
# ------------------------------------------------------------------

label_columns = [
    c for c in monthly_labels.columns
    if c not in master_key
]


for col in label_columns:

    master[col] = master[
        col
    ].fillna(0)


integer_columns = [
    "flood_event_count",
    "flood_event_flag",
    "target_flood",
]


for col in integer_columns:

    if col in master.columns:

        master[col] = master[
            col
        ].astype("int32")


# ------------------------------------------------------------------
# CLEANUP
# ------------------------------------------------------------------

master = master.replace(
    [np.inf, -np.inf],
    np.nan
)


master = master.sort_values(
    [
        "canonical_basin_id",
        "timestamp",
    ]
).reset_index(
    drop=True
)


# ------------------------------------------------------------------
# FINAL VALIDATION
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("PHASE 9 FINAL VALIDATION")
print("=" * 110)


duplicate_keys = master.duplicated(
    subset=master_key
).sum()


print(
    "Rows:",
    len(master)
)

print(
    "Columns:",
    len(master.columns)
)

print(
    "Basins:",
    master[
        "canonical_basin_id"
    ].nunique()
)

print(
    "Date:",
    master[
        "timestamp"
    ].min(),
    "→",
    master[
        "timestamp"
    ].max()
)

print(
    "Duplicate keys:",
    duplicate_keys
)


if duplicate_keys:

    raise RuntimeError(
        "Duplicate basin/timestamp keys detected."
    )


if len(master) != before_rows:

    raise RuntimeError(
        "Final Phase 9 row count does not match Phase 8."
    )


# ------------------------------------------------------------------
# FLOOD TARGET REPORT
# ------------------------------------------------------------------

positive_rows = int(
    master[
        "target_flood"
    ].sum()
)


negative_rows = int(
    (
        master[
            "target_flood"
        ] == 0
    ).sum()
)


positive_percentage = (
    positive_rows
    / len(master)
    * 100
)


positive_basins = (
    master.loc[
        master[
            "target_flood"
        ] == 1,
        "canonical_basin_id"
    ]
    .nunique()
)


print("\nFLOOD TARGET")
print("-" * 110)

print(
    "Flood-positive rows:",
    positive_rows
)

print(
    "Flood-negative rows:",
    negative_rows
)

print(
    f"Flood-positive percentage: "
    f"{positive_percentage:.2f}%"
)

print(
    "Flood-positive basins:",
    positive_basins
)


# ------------------------------------------------------------------
# SAVE LABEL REPORT
# ------------------------------------------------------------------

report = pd.DataFrame(
    {
        "metric": [
            "phase8_rows",
            "phase9_rows",
            "phase8_columns",
            "phase9_columns",
            "master_basins",
            "raw_flood_events",
            "valid_flood_events",
            "assigned_flood_events",
            "unassigned_flood_events",
            "spatial_assignment_rate_pct",
            "monthly_flood_labels",
            "flood_positive_rows",
            "flood_negative_rows",
            "flood_positive_percentage",
            "flood_positive_basins",
            "duplicate_master_keys",
        ],
        "value": [
            before_rows,
            before_rows,
            len(
                pd.read_csv(
                    MASTER,
                    nrows=1
                ).columns
            ),
            len(master.columns),
            master[
                "canonical_basin_id"
            ].nunique(),
            len(
                pd.read_csv(
                    FLOOD
                )
            ),
            len(joined),
            assigned_count,
            unassigned_count,
            assignment_rate,
            len(monthly_labels),
            positive_rows,
            negative_rows,
            positive_percentage,
            positive_basins,
            duplicate_keys,
        ],
    }
)


report.to_csv(
    REPORT,
    index=False
)


# ------------------------------------------------------------------
# SAVE PHASE 9 MASTER
# ------------------------------------------------------------------

master.to_csv(
    OUT,
    index=False
)


# ------------------------------------------------------------------
# FINAL
# ------------------------------------------------------------------

print("\n" + "=" * 110)
print("🔥 PHASE 9 FLOOD LABEL ENGINEERING COMPLETE")
print("=" * 110)

print(
    "Input:",
    MASTER.resolve()
)

print(
    "Output:",
    OUT.resolve()
)

print(
    "Label report:",
    REPORT.resolve()
)

print(
    "Event alignment report:",
    EVENT_REPORT.resolve()
)

print(
    "Phase 8 backup:",
    BACKUP.resolve()
)

print("\n" + "=" * 110)
print("🔥 PHASE 9 PASS")
print("=" * 110)
