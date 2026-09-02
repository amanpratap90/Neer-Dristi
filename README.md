CHETAKAI V1 — COMPLETE END-TO-END TECHNICAL DOCUMENTATION
==============================================================================
Version: V1
Date: September 2026

Purpose
-------
This document explains ChetakAI from data collection through preprocessing, feature engineering, machine learning, spatial resolution, risk scoring, alerting, RAG, Weather LLM, orchestration, API integration and dashboard presentation.

ChetakAI is a location-specific flood intelligence system. Its core principle is that flood risk is a multi-factor environmental phenomenon and therefore cannot responsibly be represented by rainfall alone.

IMPORTANT STATUS NOTE
---------------------
The V1 system contains implemented production components plus fields designed for future data integrations. Where a live weather, radar, gauge, population, infrastructure, administrative or other source is unavailable, ChetakAI reports "Unavailable" or "—". It does not fabricate measurements.

The implemented production chain includes the production feature/risk pipeline, Phase 21 production inference, Phase 22 risk engine, Phase 23 alert engine, Phase 24 RAG, Phase 25 Weather LLM/report generation, Phase 26 agent orchestration, Phase 27 end-to-end execution, and the Node/Express + React web integration.


1. EXECUTIVE SUMMARY
==============================================================================
ChetakAI takes a latitude and longitude and converts that location into a structured flood-intelligence report.

High-level flow:

USER
  |
  v
LATITUDE + LONGITUDE
  |
  v
SPATIAL RESOLUTION
  |
  v
DATA + FEATURES
  |
  v
PRODUCTION ML MODEL
  |
  v
FLOOD PROBABILITY
  |
  v
RISK ENGINE
  |
  v
ALERT ENGINE
  |
  v
RAG / EVIDENCE
  |
  v
WEATHER LLM
  |
  v
AGENT ORCHESTRATOR
  |
  v
PHASE 27 E2E RESPONSE
  |
  v
NODE/EXPRESS API
  |
  v
REACT DASHBOARD

The model predicts. The risk engine interprets. The alert engine classifies operational severity. RAG supplies grounded knowledge. The LLM explains structured evidence. The backend exposes it. The frontend visualizes it.

The frontend never calculates flood probability.


2. THE PROBLEM:-

Flooding is not caused by one variable. Heavy rainfall can create little flooding in one location and severe flooding in another because terrain, soil, drainage, river state, land cover and exposure are different.

Therefore:

FLOOD RISK = f(rainfall, forecast, terrain, hydrology, soil, surface, remote sensing, history, exposure)

ChetakAI aims to answer:
- Where is the requested location?
- Which basin is it in?
- What has happened recently?
- What is forecast to happen?
- What is the terrain and drainage situation?
- What is the soil/surface condition?
- What is the hydrological state when available?
- What population/infrastructure may be exposed?
- What is the predicted flood probability?
- What is the overall risk?
- Why is the location risky?
- What action is appropriate based on the available evidence?


3. DESIGN PRINCIPLES
==============================================================================
1. DATA FIRST
Data quality and spatial/temporal alignment come before model complexity.

2. MULTI-SOURCE FUSION
Different sources observe different parts of the flood process.

3. LOCATION-SPECIFIC PROCESSING
Every request coordinate must be processed for that coordinate; previous snapshots cannot become another location's answer.

4. NO FABRICATION
Unavailable evidence is explicitly marked unavailable.

5. ML FOR PREDICTION, LLM FOR EXPLANATION
The language model does not replace the scientific prediction model.

6. STRICT VALIDATION
Critical model inputs and contracts are validated before inference.



4. DATA COLLECTION STRATEGY
==============================================================================
ChetakAI does not begin by attempting to download every dataset for all of India. V1 uses a controlled basin-oriented strategy.

The workflow is:

SOURCE
 -> INVENTORY
 -> COVERAGE CHECK
 -> QUALITY CHECK
 -> SPATIAL ALIGNMENT
 -> TEMPORAL ALIGNMENT
 -> FEATURE ENGINEERING
 -> MASTER DATASET
 -> MODEL

V1 development focused on selected river basins including Godavari, Mahanadi and east-flowing rivers between Mahanadi and Pennar. Other basins were also examined during development.

The purpose of basin selection is reproducibility, manageable data volume and meaningful hydrological context. National scaling is an extension after the basin-level pipeline is validated.


5. RAINFALL DATA
==============================================================================
ROLE
Rainfall represents water entering the land/basin system.

IMPORTANT FEATURES
- mean
- sum/accumulation
- minimum
- maximum
- standard deviation
- P90/P95/P99
- rolling rainfall
- rainfall anomaly
- lagged rainfall
- seasonal/time features

IMPORTANT WINDOWS
3 hour, 6 hour, 12 hour, 24 hour and 72 hour windows.

WHY IT HELPS
A flood can result from short-duration extreme rain or from several days of accumulation. A 24-hour total captures recent loading; a 72-hour total captures antecedent wetness and accumulated rainfall.

CROSS-QUESTION
Q: Why not use only today's rainfall?
A: Because flood response depends on recent history. A saturated basin responds differently from a dry basin to the same new rainfall.

Q: Why use P95/P99?
A: Percentiles measure extremeness relative to a rainfall distribution, which is more informative than an isolated raw number.

Q: Why multiple windows?
A: Different flood mechanisms operate at different time scales.


6. HISTORICAL FLOOD EVENTS
==============================================================================
ROLE
Historical flood events provide examples linking environmental conditions to observed flood outcomes.

Possible fields:
- event date
- location
- basin
- flood occurrence
- flood extent
- depth where available
- severity
- duration
- source/event identifier

The supervised-learning relationship is:

ENVIRONMENTAL FEATURES -> HISTORICAL FLOOD LABEL

CROSS-QUESTION
Q: Why are historical events necessary?
A: A supervised model needs examples of conditions associated with known outcomes.

Q: Why are flood labels difficult?
A: Different records can be point reports, administrative reports or satellite-derived spatial extents. They must be harmonized in space and time before being treated as equivalent labels.


7. DEM AND TERRAIN
==============================================================================
DEM means Digital Elevation Model. ChetakAI uses approximately 30 m class terrain sources such as Copernicus DEM/SRTM-derived data.

The project maintained a large DEM tile inventory and preserved the required terrain data.

FEATURES
- minimum elevation
- maximum/elevation range
- mean slope
- elevation range ratio
- flow accumulation
- river distance
- other drainage/terrain descriptors where available

WHY ELEVATION?
Low-lying terrain can be more susceptible to water accumulation.

WHY SLOPE?
Slope affects runoff velocity and drainage. Flat terrain can retain water longer, while steep terrain can create rapid runoff.

WHY FLOW ACCUMULATION?
It approximates where upstream water converges and identifies drainage concentration.

WHY RIVER DISTANCE?
Proximity to rivers can increase flood susceptibility, especially during rising river conditions.

CROSS-QUESTION
Q: Does low elevation automatically mean flood?
A: No. Terrain is one factor. Rainfall, hydrology, drainage and surface conditions must also be considered.

Q: Why preserve DEM instead of downloading again?
A: Existing validated terrain data is an important project asset. Re-downloading increases risk, storage and reproducibility problems.


8. HYDROGRAPHY AND RESERVOIRS
==============================================================================
Hydrography describes the drainage network.

FEATURES USED/AVAILABLE
- river area
- river length
- river density
- river distance
- reservoir count
- reservoir area

Observed production-state examples included:
river_area_km2
river_length_km
river_density_km_per_km2
reservoir_count
reservoir_area_km2

WHY IT HELPS
Water is connected through drainage networks. Rainfall at one location can contribute to downstream flow.

CROSS-QUESTION
Q: Why reservoir data?
A: Reservoirs provide storage and hydrological context. Actual operational discharge data is stronger when available.

Q: Is reservoir count enough to predict flooding?
A: No. It is contextual information, not a complete hydrological model.


9. RIVER WATER LEVEL AND DISCHARGE
==============================================================================
ROLE
River observations describe the hydrological state directly.

USEFUL VARIABLES
- current level
- previous level
- level change
- rising/falling trend
- discharge
- anomaly
- warning-level status

Rainfall asks: what water is entering the system?
River level asks: how is the river system responding?

CROSS-QUESTION
Q: Why is river level valuable?
A: It can capture upstream accumulated response that local rainfall alone cannot see.

Q: What if the gauge is unavailable?
A: The field is marked unavailable. The system must not invent a level. Other valid evidence may still be used.


10. SOIL DATA
==============================================================================
Soil controls infiltration and runoff.

FEATURES
- sand
- clay
- silt
- soil organic carbon
- bulk density
- pH
- cation exchange capacity
- moisture where available
- runoff proxy

Production-state examples included:
cec_mean
phh2o_mean
soc_mean
bdod_mean
silt_mean
sand_mean
clay_mean
soil_runoff_proxy

WHY IT HELPS
Clay-heavy or already-wet soils can reduce available infiltration and increase runoff. Sandy soils generally permit greater infiltration, although real behavior depends on structure, moisture and other factors.

CROSS-QUESTION
Q: Does clay automatically mean flood?
A: No. Soil is a contributing feature, not a standalone flood classifier.

Q: Why create a runoff proxy?
A: It converts multiple soil properties into a compact signal representing expected runoff behavior.


11. LAND USE / LAND COVER
==============================================================================
Land/surface characteristics affect runoff and exposure.

USEFUL CLASSES
- built-up
- cropland
- tree cover
- natural vegetation
- water
- wetland
- bare/sparse land

WHY BUILT-UP?
Impervious surfaces can increase surface runoff.

WHY VEGETATION?
Vegetation affects interception, infiltration, evapotranspiration and soil behavior.

WHY CROPLAND?
Agricultural areas have different surface characteristics and can be highly exposed to inundation.

CROSS-QUESTION
Q: Is high built-up percentage automatically high flood risk?
A: No. It is a surface/exposure signal and must be interpreted with rainfall, terrain and drainage.


12. SATELLITE AND REMOTE SENSING
==============================================================================
The project inventory contained 80 satellite rasters: 72 TIFF files and 8 JP2 files. Available Sentinel-2 bands included B02, B03, B04 and B08 at 10 m resolution, with scenes from 2024, 2025 and 2026.

Existing imagery was intentionally processed rather than expanding the download scope unnecessarily.

POSSIBLE DERIVED INDICATORS
- NDVI
- NDWI
- vegetation fraction
- water fraction
- surface wetness indicators

SATELLITE FLOOD MAPS
Historical satellite-derived inundation can also be used as validation/label information where suitable.

CROSS-QUESTION
Q: Why satellite?
A: It gives spatial surface observations that rainfall and DEM cannot provide.

Q: Why not download unlimited imagery?
A: Data volume, cloud contamination, preprocessing, temporal consistency and storage make uncontrolled expansion undesirable for V1.


13. WEATHER FORECAST / NWP
==============================================================================
NWP means Numerical Weather Prediction.

NWP provides future atmospheric information such as forecast rainfall.

WHY IT HELPS
An early-warning system must look forward. Historical observations tell us what has happened; NWP helps estimate what may happen next.

USEFUL VARIABLES
- forecast rainfall
- forecast temperature
- forecast wind
- ensemble spread
- forecast confidence

CROSS-QUESTION
Q: Why not trust NWP completely?
A: Forecasts contain uncertainty and can have spatial/temporal errors. ChetakAI treats NWP as one evidence source.

Q: What is NWP spread?
A: In an ensemble forecast, different members produce different outcomes. Greater spread generally indicates greater uncertainty.


14. DATA QUALITY LAYER
==============================================================================
Before modeling, data is checked for:
- missing values
- invalid coordinates
- duplicate records
- invalid timestamps
- inconsistent units
- impossible values
- CRS mismatches
- corrupted rasters
- temporal gaps
- spatial gaps
- schema mismatches

Examples:
Latitude must be -90 to 90.
Longitude must be -180 to 180.
Rainfall should not be negative.
Spatial calculations require correct CRS handling.

CROSS-QUESTION
Q: Why is this more important than using a more complex model?
A: A sophisticated model trained on corrupted or misaligned data can produce scientifically wrong predictions.


15. SPATIAL AND TEMPORAL ALIGNMENT
==============================================================================
Flood intelligence requires two kinds of alignment.

SPATIAL ALIGNMENT
Rainfall, DEM, soil, land cover, rivers and other datasets must refer to the same geographic location.

TEMPORAL ALIGNMENT
Weather observations, rainfall windows, flood labels and forecasts must correspond to compatible times.

Conceptually:

LAT/LON
 -> basin polygon
 -> DEM cell
 -> soil cell
 -> LULC cell
 -> hydrography
 -> satellite footprint
 -> administrative polygon

CROSS-QUESTION
Q: Why can a CRS mismatch be dangerous?
A: Distances, areas and raster intersections can be wrong even though the code technically runs.

Q: Why is timestamp alignment important?
A: Using future information to predict a past flood creates data leakage.


16. FEATURE ENGINEERING
==============================================================================
Raw environmental data is converted into model-ready predictors.

TECHNIQUES
- lag features
- rolling statistics
- seasonal features
- anomaly features
- one-hot encoding
- interaction features
- climatology

Examples:
rainfall_lag
rainfall_24h
rainfall_72h
rainfall_anomaly
month_sin
month_cos

WHY SIN/COS?
Months are cyclical. December and January are adjacent, so representing month as a simple integer can introduce an artificial discontinuity.

WHY INTERACTIONS?
Flood behavior can depend on combinations such as rainfall + slope, rainfall + soil, or rainfall + hydrological state.

CROSS-QUESTION
Q: Why feature engineering when tree models can learn nonlinear patterns?
A: Tree models are powerful, but explicitly representing temporal accumulation, seasonality and domain relationships gives the model useful structure and can improve robustness.


17. MASTER DATASET
==============================================================================
The project created a master ML dataset at:

data/processed/master/chetakai_v1_master_ml_dataset.csv

Recorded inventory:
approximately 3300 rows and 42 columns.

An earlier Phase 12 master dataset contained approximately 3168 rows and 186 columns.

The master dataset is the bridge between raw sources and modeling.

Conceptually:
ROW = location/basin + time + engineered environmental features + target

The goal is to make heterogeneous sources behave like one consistent modeling table.


18. MODELING STRATEGY
==============================================================================
The central supervised task is flood probability/risk classification.

The model learns:

X -> y

where X is the engineered feature vector and y represents the defined flood-event target.

The production model artifact is:

data/processed/models/phase19/best_phase19_flood_model.joblib

The artifact contains a model estimator under the "model" key.

Production feature count:
60

Production decision threshold:
0.34

A representative successful request at latitude 25.1234, longitude 86.5678 produced:
Flood probability = 0.7388969489891041
Flood probability = 73.89%
Threshold = 0.34
Risk = HIGH
Production status = PRODUCTION_READY

CROSS-QUESTION
Q: Why not just use a deep neural network?
A: Model complexity should match the data and target. Tree-based models are often strong for engineered tabular environmental data and are easier to validate and interpret. CNN/ConvLSTM/transformer models are useful extensions for spatial or sequence-heavy problems.


19. PRODUCTION FEATURE CONTRACT
==============================================================================
A feature contract defines the exact interface expected by the production model.

It prevents:
- missing features
- wrong feature order
- unexpected columns
- silent substitutions
- preprocessing mismatch

The production contract was created during the feature-builder stage and maintained with the production model artifacts.

CROSS-QUESTION
Q: Why is a contract necessary?
A: A model can technically execute even if its inputs have changed meaning. A contract makes inference fail or warn when the expected interface is not satisfied.


20. DECISION THRESHOLD
==============================================================================
A classifier can output a probability without automatically deciding a class.

Example:
P(flood) = 0.7389

With threshold 0.34:
0.7389 >= 0.34
therefore the event crosses the production decision boundary.

The threshold is explicitly locked in the production contract.

CROSS-QUESTION
Q: Why not use 0.5?
A: 0.5 is not universally optimal. In early warning, false negatives can be costly. The threshold should be selected using validation and operational trade-offs.


21. PHASE 21 — PRODUCTION INFERENCE / PREFLIGHT
==============================================================================
Phase 21 validates the production request and performs model inference.

Responsibilities:
1. Validate latitude/longitude.
2. Resolve geographic context.
3. Build production features.
4. Validate DEM/terrain availability.
5. Validate the model artifact.
6. Validate the feature contract.
7. Validate the decision threshold.
8. Run inference.
9. Produce flood probability/risk classification.
10. Report production readiness.

A validated example had:
60/60 required features present.
Flood probability 73.89%.
Risk HIGH.

CROSS-QUESTION
Q: Why fail when a critical feature is missing?
A: Silent fallback can produce a plausible-looking but scientifically invalid result. Strict mode prioritizes trustworthiness.


22. LOCATION RESOLUTION
==============================================================================
A coordinate is used to resolve geographic context.

The resolver may identify:
- basin
- DEM coverage
- nearby rivers
- soil context
- land cover
- satellite footprint
- administrative context

This is how the system becomes location-specific.

A request for coordinate A must not receive a stale snapshot created for coordinate B.

CROSS-QUESTION
Q: Can nearby coordinates produce similar values?
A: Yes. Physical conditions vary continuously, so nearby points can legitimately be similar. Similarity is not the same as reusing a previous response.


23. PHASE 22 — RISK ENGINE
==============================================================================
The ML probability is only one layer.

The risk engine can expose components such as:
- rainfall risk
- forecast risk
- terrain risk
- hydrology risk
- surface/soil risk
- population exposure
- infrastructure exposure
- agriculture exposure

A representative result:
Flood probability ~73.89%
Risk engine score ~73.75
Rainfall risk ~81.24
Terrain risk ~77.4
Final class HIGH

Some components may be unavailable when their source data is absent.

CROSS-QUESTION
Q: Why not make ML probability the final score?
A: Probability and operational risk are different concepts. The risk engine makes contributing factors explicit and supports interpretable decision logic.


24. PHASE 23 — ALERT ENGINE
==============================================================================
The alert engine translates risk into an operational severity.

Typical classes:
LOW
MODERATE
HIGH
SEVERE

A validated example produced:
HIGH / P2

The exact alert policy should be versioned and documented.

CROSS-QUESTION
Q: Why create an alert layer?
A: A percentage alone does not communicate operational priority. An alert classification turns a model signal into a decision-support state.


25. PHASE 24 — RAG
==============================================================================
RAG = Retrieval-Augmented Generation.

Pipeline:

DOCUMENTS
 -> CLEANING
 -> CHUNKING
 -> EMBEDDINGS
 -> VECTOR DATABASE
 -> RETRIEVAL
 -> RERANKING
 -> CONTEXT BUILDER
 -> LLM

The ChetakAI architecture considered Qdrant for vector storage and embedding options such as OpenAI embeddings, BGE Small or E5 Small depending on deployment requirements.

RAG can retrieve:
- domain guidance
- disaster-management procedures
- definitions
- warning policies
- source context
- operational documentation

CROSS-QUESTION
Q: Why RAG?
A: The predictive model cannot be expected to contain every operational policy or domain document. RAG supplies relevant external knowledge and reduces unsupported generation.


26. PHASE 25 — WEATHER LLM
==============================================================================
The Weather LLM receives structured evidence rather than inventing sensor data.

Example input:
Flood probability = 73.89%
Risk = HIGH
24h rainfall = 110.29 mm
72h rainfall = 330.88 mm
Terrain risk = HIGH
Surface/soil risk = SEVERE
River level = Unavailable

The LLM converts these facts into a human-readable report.

It must NOT invent:
- river levels
- radar detections
- population counts
- satellite observations
- weather observations
- administrative names
- flood depth or inundation area

unless they are present in the evidence.

CROSS-QUESTION
Q: What is the LLM's role?
A: Explanation, summarization and grounded communication.

Q: What is not its role?
A: Replacing the scientific model or hallucinating measurements.


27. PHASE 26 — AGENT ORCHESTRATOR
==============================================================================
The orchestrator coordinates tools and intelligence stages.

Conceptually:

REQUEST
 -> PLANNER/ROUTER
 -> LOCATION
 -> WEATHER
 -> MODEL
 -> RISK
 -> RAG
 -> ALERT
 -> REPORT

It combines outputs and maintains a coherent final answer.

Agentic behavior should be constrained by available tools and evidence rather than allowing free-form invention.


28. PHASE 27 — END-TO-END PIPELINE
==============================================================================
Phase 27 executes the integrated chain:

Phase 21 -> Phase 22 -> Phase 23 -> Phase 24 -> Phase 25 -> Phase 26

The final response is written to:

data/processed/models/phase27/latest_e2e_response.json

Important production properties include:
dynamic = true
demoFallback = false
coordinate_source = REQUEST
coordinate_validated = true
coordinate_locked_to_request = true
fresh_phase21_snapshot = true
snapshot_locked = true
utf8_safe_subprocess = true
windows_console_safe = true

The coordinate is explicitly passed to the production inference stage and validated so the system does not simply display a stored demonstration snapshot.


29. NODE / EXPRESS BACKEND
==============================================================================
The web-facing backend is Node.js + Express.

NODE RESPONSIBILITIES
- HTTP API
- request validation
- frontend communication
- invoking Phase 27
- response normalization
- CORS
- application-level error handling

PYTHON RESPONSIBILITIES
- scientific data processing
- feature engineering
- ML inference
- risk intelligence
- RAG/LLM components
- geospatial processing

This separation keeps the web layer independent from the ML execution layer.

Known configuration:
PORT=8000
FRONTEND_ORIGIN=http://localhost:5173,http://127.0.0.1:5173
GEOCODER_USER_AGENT=ChetakAI-Flood-Intelligence/1.0
CHETAKAI_PROJECT_ROOT=C:\Users\vinee\OneDrive\Desktop\ChetakAI
CHETAKAI_PHASE27_SCRIPT=scripts\phase27_end_to_end_api.py


30. API
==============================================================================
Health:
GET /health

Main intelligence endpoint:
POST /api/v1/intelligence/analyze

Conceptual request:
{
  "latitude": 25.1234,
  "longitude": 86.5678,
  "strict": true
}

The backend passes the location to the actual ChetakAI pipeline and returns structured intelligence.

The frontend should use a clean API base such as:
http://127.0.0.1:8000
and call the appropriate endpoint rather than embedding the endpoint twice.


31. FRONTEND
==============================================================================
The frontend intentionally remains simple.

PAGE 1:
Location input.

PAGE 2:
Flood intelligence dashboard.

The dashboard contains:
LOCATION
CURRENT WEATHER
FORECAST / NWP
TERRAIN
HYDROLOGY
REMOTE SENSING
LAND / SURFACE
SOIL
POPULATION EXPOSURE
INFRASTRUCTURE EXPOSURE
AI FLOOD ASSESSMENT
RISK BREAKDOWN
OVERALL FLOOD RISK
RECOMMENDED ACTION

React only visualizes the authoritative backend response.

If the backend fails, the frontend must show an error instead of replacing the result with a hard-coded demo dashboard.


32. DASHBOARD FIELD DEFINITIONS
==============================================================================
LOCATION
Latitude, Longitude, Basin, Administrative Area.

CURRENT WEATHER
Rainfall, Temperature, Humidity, Pressure, Wind.

FORECAST / NWP
Forecast rainfall, NWP spread, Confidence.

TERRAIN
Elevation, Slope, Flow accumulation, River distance, Terrain risk.

HYDROLOGY
River level, Change, Trend, Hydrological loading.

REMOTE SENSING
Radar, Satellite, Gauge, River.

LAND / SURFACE
Land cover, Built-up, Cropland, Water, Vegetation, Wetness.

SOIL
Texture, Moisture, Runoff, Infiltration.

POPULATION EXPOSURE
Population, Exposed population, Vulnerable population.

INFRASTRUCTURE EXPOSURE
Roads, Railways, Bridges, Buildings, Schools, Hospitals.

AI FLOOD ASSESSMENT
Flood Probability, Risk Label, Depth, Inundation Area, Warning.

RISK BREAKDOWN
Rainfall, Forecast, Terrain, Hydrology, Surface, Population, Infrastructure, Agriculture.

OVERALL FLOOD RISK
Final severity/risk state.

RECOMMENDED ACTION
Evidence-grounded operational guidance.


33. MISSING-DATA POLICY
==============================================================================
If a value exists:
DISPLAY IT.

If a value does not exist:
DISPLAY "Unavailable" or "—".

Never create a fake number to make the UI look complete.

Examples that must not be fabricated:
river level
radar status
population
infrastructure count
temperature
humidity
pressure
wind
flood depth
inundation area
administrative name

This policy is especially important in a safety-relevant system.

CROSS-QUESTION
Q: Does showing unavailable fields make the product weaker?
A: No. It demonstrates scientific honesty and lets the user distinguish measured evidence from unavailable evidence.


34. EXAMPLE LOCATION-SPECIFIC RESULT
==============================================================================
For latitude 25.1234 and longitude 86.5678, a validated pipeline example produced:

Basin: CWC_BASIN_012
Flood probability: 73.89%
Threshold: 0.34
ML risk: HIGH
Risk-engine score: approximately 73.75
Rainfall risk: approximately 81.24
Terrain risk: approximately 77.4
Alert: HIGH / P2

Example rainfall:
3h  = 13.79 mm
6h  = 27.57 mm
12h = 55.15 mm
24h = 110.29 mm
72h = 330.88 mm

Example NWP:
1h rainfall approximately 4.60 mm

Example terrain:
minimum elevation approximately -38.13 m
mean slope approximately 4.39 degrees
elevation range ratio approximately 6.97

Example surface:
cropland approximately 58.83%
built-up approximately 3.09%
water approximately 1.52%
tree cover approximately 19.52%
natural vegetation approximately 34.23%

Example soil:
sand approximately 33.27%
clay approximately 28.61%
silt approximately 38.12%

Some live weather, hydrological, administrative and exposure values were unavailable in that runtime. Those fields were not fabricated.


35. WHY MULTI-SOURCE FUSION MATTERS
==============================================================================
Consider three locations.

A:
Heavy rain + steep terrain + low river + good drainage.

B:
Moderate rain + flat terrain + wet soil + rising river.

C:
Heavy rain + low elevation + dense built-up area + poor drainage.

A rainfall-only model can treat them too similarly.

A multi-source system can distinguish:
- hazard
- susceptibility
- hydrological loading
- surface response
- potential impact

This is the fundamental reason ChetakAI collects more than rainfall.


36. PREDICTION VS RISK VS IMPACT
==============================================================================
PREDICTION:
What probability does the model assign to the target flood condition?

RISK:
How should that prediction be interpreted using model and domain components?

IMPACT:
What people, infrastructure, roads, agriculture or critical services could be affected?

Conceptually:

HAZARD
 -> FLOOD PROBABILITY
 -> RISK
 -> EXPOSURE
 -> IMPACT

This separation prevents the common mistake of treating flood probability and disaster impact as the same quantity.


37. POPULATION, INFRASTRUCTURE AND AGRICULTURE
==============================================================================
Population exposure answers how many people may be affected.

Infrastructure exposure answers which critical assets may be affected:
roads, railways, bridges, buildings, schools and hospitals.

Agriculture exposure represents cropland/crop vulnerability.

These are impact layers, not replacements for hazard prediction.

Example:
A remote area may have high flood probability but low population exposure.
A city may have moderate flood probability but very high population and infrastructure exposure.


38. UNCERTAINTY
==============================================================================
Uncertainty can come from:
- measurement error
- satellite cloud contamination
- NWP spread
- missing gauges
- model uncertainty
- spatial interpolation
- incomplete labels
- changing land use

A responsible system can report:
risk = HIGH
confidence = MODERATE

instead of claiming certainty.

Forecast spread and source availability can be used as uncertainty indicators where the data supports them.


39. VALIDATION
==============================================================================
For classification:
- Precision
- Recall
- F1
- ROC-AUC where appropriate
- PR-AUC
- Brier score
- calibration

For spatial flood extent:
- IoU
- Precision
- Recall
- F1
- CSI

For warnings:
- lead time
- false alarm ratio
- probability of detection

LEAD TIME EXAMPLE
Actual flood begins at 18:00.
Warning issued at 10:30.
Actionable lead time = 7.5 hours.

A flood-warning system should not be judged only by generic accuracy.


40. WHY ACCURACY ALONE IS DANGEROUS
==============================================================================
If 99% of pixels are non-flooded, a model that predicts non-flood everywhere can achieve 99% accuracy while being useless.

Therefore ChetakAI emphasizes event detection, recall, precision, calibration, spatial overlap and actionable warning lead time.


41. HISTORICAL SATELLITE VALIDATION
==============================================================================
A powerful validation workflow is:

Historical flood event
 -> collect weather/environment before event
 -> run ChetakAI
 -> generate predicted flood information
 -> compare with observed satellite flood extent
 -> calculate IoU, Precision, Recall, F1, CSI and lead time where applicable.

This provides evidence that the model predicts real spatial flood behavior rather than merely fitting tabular labels.


42. BASELINES AND ABLATION
==============================================================================
A strong scientific evaluation compares increasingly rich models.

Baseline 1:
Rainfall only.

Baseline 2:
Rainfall + terrain.

Baseline 3:
Rainfall + terrain + soil.

Baseline 4:
Rainfall + terrain + soil + hydrography.

ChetakAI:
All validated available sources plus production risk/uncertainty layers.

Ablation studies answer:
How much does each data source actually improve the result?

Metrics can include F1, recall, precision, Brier score, calibration, IoU and lead time.

This is stronger than simply claiming that "more features improved the model."


43. DATA LEAKAGE AND VALIDATION DESIGN
==============================================================================
Flood datasets are spatially and temporally correlated.

A random train/test split can leak information if nearly identical observations from the same event appear in both sets.

Better evaluation can use:
- time-based splits
- event-based splits
- spatial holdouts
- basin holdouts where feasible

CROSS-QUESTION
Q: Why does this matter?
A: A model that performs well only because the test set is nearly identical to training data may fail on a new flood event or basin.


44. CACHING
==============================================================================
Possible cache layers:
Redis:
sessions, frequent results, user state.

Prompt cache:
exact repeated LLM prompts.

Semantic cache:
similar queries, when safe.

KV cache:
LLM inference optimization.

CRITICAL LOCATION RULE
Flood intelligence is time-sensitive. Cache keys should include enough context such as:
latitude
longitude
time/data timestamp
model version
feature version
forecast cycle
dataset version

Otherwise a valid response for one environmental state could become a stale response for another.


45. FAILURE MODES AND SAFE BEHAVIOR
==============================================================================
Potential failures:
1. Invalid coordinate.
2. Unsupported geographic area.
3. Missing DEM.
4. Missing soil.
5. Missing satellite.
6. Weather source unavailable.
7. River gauge unavailable.
8. Model artifact missing.
9. Feature contract mismatch.
10. Python execution failure.
11. Node API failure.
12. Frontend network failure.
13. LLM failure.
14. RAG retrieval failure.

Safe behavior:
- invalid request -> reject
- critical model feature missing in strict mode -> fail
- optional source missing -> mark unavailable
- backend failure -> show error
- no fake dashboard fallback
- no fabricated scientific measurements.


46. STRICT MODE
==============================================================================
Strict mode is a production safety mechanism.

It requires critical:
- coordinates
- model artifact
- feature contract
- decision threshold
- terrain/DEM
- required features

to be valid.

Strict mode prevents silent fallback.

CROSS-QUESTION
Q: Why is silent fallback bad?
A: A system can return a number that looks authoritative even though the model did not receive the required evidence. In flood warning, that is unacceptable.


47. WINDOWS / UTF-8 RELIABILITY
==============================================================================
ChetakAI was developed on Windows PowerShell.

A subprocess encoding problem occurred because child-process output could contain Unicode characters incompatible with the Windows console encoding.

The production execution path uses UTF-8-safe subprocess handling such as:
encoding="utf-8"
errors="replace"

This is an operational reliability feature. Scientific correctness includes the ability to execute the pipeline reliably from start to finish.


48. OBSERVABILITY
==============================================================================
Production monitoring should record:
- request ID
- timestamp
- coordinate
- pipeline phase
- model version
- feature version
- execution duration
- source availability
- success/failure
- probability
- risk class
- alert class

This helps identify stale snapshots, missing data, slow phases, model failures and source outages.


49. VERSIONING AND REPRODUCIBILITY
==============================================================================
A prediction should ideally be reproducible.

Record:
- dataset version
- model artifact version
- feature contract version
- threshold
- pipeline version
- forecast cycle
- RAG knowledge version

If the same coordinate produces a different result after a model/data update, version information explains why.


50. SECURITY AND SAFETY
==============================================================================
The system should:
- validate coordinates
- validate request schema
- sanitize user-facing content
- restrict CORS
- protect environment variables
- avoid arbitrary command execution
- avoid exposing local filesystem paths
- log errors safely
- minimize unnecessary user-data retention

ChetakAI should distinguish its own model assessment from an official government emergency warning unless formally integrated and authorized.


51. FUTURE EXTENSIONS
==============================================================================
Possible V2/V3 extensions:
1. Live weather observations.
2. Operational radar.
3. More river gauges.
4. NWP ensemble integration.
5. Population exposure.
6. Infrastructure exposure.
7. Flood-depth regression.
8. Spatial inundation segmentation.
9. Satellite flood-map validation at scale.
10. Probabilistic uncertainty.
11. Better administrative resolution.
12. Alert subscriptions.
13. PostGIS spatial database.
14. Redis.
15. MLflow model registry.
16. Docker/container deployment.
17. Monitoring and CI/CD.
18. National basin scaling.

Deep learning extensions can include CNNs, U-Net-like segmentation, ConvLSTM and transformer-based spatial-temporal models when data volume and validation justify them.


52. COMPLETE REQUEST LIFECYCLE
==============================================================================
1. User enters latitude and longitude.
2. Frontend validates basic input.
3. Frontend sends request to Node/Express.
4. Backend validates the request.
5. Backend invokes Phase 27.
6. Phase 21 validates coordinate.
7. Spatial resolver determines basin/context.
8. Terrain, soil, hydrography and other available features are resolved.
9. Production contract validates the 60-feature interface.
10. ML model generates flood probability.
11. Phase 22 calculates risk components.
12. Phase 23 generates alert severity.
13. Phase 24 retrieves grounding evidence.
14. Phase 25 generates the structured human-readable report.
15. Phase 26 orchestrates the final intelligence.
16. Phase 27 writes the end-to-end response.
17. Node normalizes and returns it.
18. React renders the dashboard.
19. Missing fields are shown as unavailable.


53. COMPLETE CROSS-QUESTIONING — GENERAL
==============================================================================
Q: Why not just use rainfall?
A: Flood response depends on terrain, soil, drainage, hydrology and surface conditions.

Q: Why historical floods?
A: They provide observed outcomes for supervised learning and validation.

Q: Why DEM?
A: Terrain controls drainage and water accumulation.

Q: Why soil?
A: Soil controls infiltration/runoff behavior.

Q: Why LULC?
A: Surface type changes runoff and exposure.

Q: Why satellite?
A: It provides spatial observations and can support validation.

Q: Why NWP?
A: Early warning requires future information.

Q: Why river level?
A: It directly describes hydrological response.

Q: Why RAG?
A: It grounds explanations in retrieved knowledge.

Q: Why LLM?
A: To turn structured evidence into understandable reports.

Q: Why Node?
A: Node/Express is the web-facing application layer; Python remains the scientific/ML layer.

Q: Why two-page frontend?
A: The project is an intelligence prototype, so the UI is deliberately simple and focused.

Q: How do you prevent hallucination?
A: Structured evidence, RAG grounding, explicit missing-data handling and a no-fabrication rule.

Q: How do you prevent stale location results?
A: The request coordinate is passed into Phase 21, validated and locked to the request; demo fallback is disabled.

Q: Can the system always provide every dashboard field?
A: No. It reports unavailable values when a source is not present.

Q: Can a flood probability be presented as exact flood depth?
A: No. Depth requires a validated depth model or observation.

Q: Can a probability be presented as exact inundation area?
A: No. Area requires spatial inundation information.

Q: What is the biggest practical challenge?
A: Reliable, temporally and spatially consistent access to heterogeneous environmental and operational data.


54. COMPLETE CROSS-QUESTIONING — MACHINE LEARNING
==============================================================================
Q: What is the model input?
A: The production feature vector defined by the feature contract.

Q: How many production features?
A: 60.

Q: What is the production threshold?
A: 0.34.

Q: Why a threshold?
A: Probability must be mapped to an operational classification.

Q: Why not 0.5?
A: The optimal threshold depends on validation and the cost of false negatives/false positives.

Q: Why tree models?
A: They are effective for nonlinear tabular environmental data and engineered features.

Q: Why deep learning later?
A: Spatial raster and temporal sequence problems may benefit from CNN/ConvLSTM/transformer architectures.

Q: How do you prevent leakage?
A: Use time/event/spatial-aware validation rather than blindly random splitting.

Q: What proves a feature is useful?
A: Ablation and validation results, not intuition alone.


55. COMPLETE CROSS-QUESTIONING — GENAI
==============================================================================
Q: Is ChetakAI an LLM flood predictor?
A: No. ML/environmental models perform prediction; the LLM communicates the evidence.

Q: Can the LLM override the model?
A: It should not invent or override scientific outputs without a defined deterministic policy.

Q: What does RAG provide?
A: Relevant trusted context.

Q: What does the LLM provide?
A: Explanation, summary and human-readable reporting.

Q: What happens if RAG returns nothing?
A: The report should rely only on the structured evidence available and state missing context where necessary.


56. COMPLETE CROSS-QUESTIONING — SYSTEM DESIGN
==============================================================================
Q: Why modular phases?
A: Each phase has a clear responsibility and can be tested independently.

Q: Why separate risk and prediction?
A: Prediction estimates an outcome; risk interpretation supports decision-making.

Q: Why separate backend and Python?
A: It separates web concerns from scientific inference.

Q: Why validate every phase?
A: A failure in one layer can otherwise be hidden by another layer.

Q: Why no demo fallback in production?
A: A demo snapshot can be mistaken for a real prediction and is dangerous for a location-specific warning system.


57. FINAL ARCHITECTURE
==============================================================================
USERS
                           |
                           v
                    REACT FRONTEND
                           |
                           v
                    NODE / EXPRESS
                           |
                           v
                  REQUEST VALIDATION
                           |
                           v
                       PHASE 27
                           |
             +-------------+-------------+
             |             |             |
             v             v             v
         PHASE 21      PHASE 22      PHASE 23
       ML INFERENCE   RISK ENGINE   ALERT ENGINE
             |             |             |
             +-------------+-------------+
                           |
                           v
                       PHASE 24
                          RAG
                           |
                           v
                       PHASE 25
                     WEATHER LLM
                           |
                           v
                       PHASE 26
                     ORCHESTRATOR
                           |
                           v
                    STRUCTURED JSON
                           |
                           v
                       DASHBOARD

DATA SOURCES
------------
Rainfall
Historical floods
DEM
Hydrography
Reservoirs
Soil
LULC
Satellite
River level
River discharge
NWP
Population
Infrastructure
Administrative boundaries

All data passes through validation and spatial/temporal alignment before being used.


58. ONE-MINUTE VIVA ANSWER
==============================================================================
ChetakAI is a location-specific AI flood intelligence platform. A user provides latitude and longitude, and the system resolves the geographic context and gathers the available rainfall, forecast, terrain, soil, hydrography, land-surface and other environmental evidence. We engineer temporal and spatial features and pass a validated 60-feature production vector to the flood model. The model produces flood probability, which is then interpreted by a separate risk engine and alert engine. RAG retrieves trusted contextual information, and the Weather LLM converts the structured evidence into an understandable report without inventing missing measurements. A Node/Express backend exposes the pipeline to a React dashboard. Every request is tied to its requested coordinate, and unavailable fields are explicitly marked rather than fabricated.


59. FIVE-MINUTE VIVA ANSWER
==============================================================================
Start with the problem: flood risk is multi-factor, so rainfall alone is insufficient.

Then describe data:
rainfall, historical floods, DEM, hydrography, reservoirs, soil, LULC, satellite, NWP, river observations and exposure data when available.

Then preprocessing:
validation, CRS handling, temporal alignment, spatial alignment, missing-data checks and feature engineering.

Then model:
60-feature production contract, trained flood-risk model, probability output and threshold 0.34.

Then risk:
rainfall, forecast, terrain, hydrology, surface/soil and exposure components are interpreted by the risk engine.

Then alert:
risk is converted to operational severity.

Then GenAI:
RAG supplies grounded context; the Weather LLM explains evidence.

Then orchestration:
Phase 26 coordinates the intelligence stages.

Then deployment:
Node/Express API connects Python inference to React.

Finally:
validation uses meaningful classification, spatial and warning metrics, including lead time. The system never invents unavailable measurements.


60. WHAT MAKES CHETAKAI A COMPLETE SYSTEM
==============================================================================
The value of ChetakAI is not one algorithm.

It is the integration of:

DATA
+
QUALITY
+
SPATIAL INTELLIGENCE
+
TEMPORAL FEATURES
+
ML
+
RISK ENGINE
+
ALERT ENGINE
+
RAG
+
LLM
+
ORCHESTRATION
+
API
+
DASHBOARD

This converts raw environmental observations into decision-oriented flood intelligence.

The core engineering lesson is:

MORE AI is not automatically BETTER AI.

Reliable data, correct spatial/temporal alignment, strict contracts, safe failure behavior, meaningful validation and evidence-grounded communication are what make an AI system trustworthy.


61. FINAL CHECKLIST
==============================================================================
DATA
[YES] Basin data
[YES] DEM
[YES] Rainfall
[YES] Historical flood events
[YES] Hydrography
[YES] Reservoirs
[YES] Existing satellite inventory
[PARTIAL] River discharge
[PARTIAL] River water level
[PARTIAL] Some soil/LULC integrations
[PARTIAL] Population
[PARTIAL] Infrastructure
[PARTIAL] Live weather/radar/NWP depending on source

ML
[YES] Master dataset
[YES] Feature engineering
[YES] Production feature contract
[YES] Production model
[YES] 60-feature interface
[YES] Threshold 0.34
[YES] Strict validation
[YES] Coordinate validation

INTELLIGENCE
[YES] Phase 21
[YES] Phase 22
[YES] Phase 23
[YES] Phase 24
[YES] Phase 25
[YES] Phase 26
[YES] Phase 27

WEB
[YES] Node/Express backend
[YES] React frontend
[YES] Location input
[YES] Dashboard
[YES] API integration
[YES] Location-specific execution
[YES] No fabricated missing values


62. FINAL CONCLUSION
==============================================================================
ChetakAI is not merely a flood classifier and not merely a weather chatbot.

It is an end-to-end environmental intelligence pipeline.

It starts with heterogeneous raw data.
It validates and aligns that data.
It creates meaningful spatial and temporal features.
It produces a model-based flood probability.
It interprets that probability through a risk engine.
It creates alerts.
It retrieves contextual knowledge.
It explains the evidence using an LLM.
It orchestrates the result.
It exposes the result through an API.
It presents the result through a simple dashboard.

The central rule is:

IF DATA EXISTS:
    USE IT.

IF DATA DOES NOT EXIST:
    SAY IT IS UNAVAILABLE.

NEVER INVENT IT.

The ultimate objective is not simply "predict flood".

The objective is:

Given a location, combine the best available environmental evidence, estimate flood risk, communicate uncertainty, explain the major drivers, identify potential impact where exposure data exists, and provide evidence-grounded decision support.

That is the ChetakAI architecture from raw data to final user-facing intelligence.

END OF DOCUMENTATION.
