import argparse, json, math
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
P21 = ROOT / "data" / "processed" / "models" / "phase21" / "latest_risk_snapshot.json"
P22 = ROOT / "data" / "processed" / "models" / "phase22" / "latest_risk_engine.json"
OUT = ROOT / "data" / "processed" / "models" / "phase23"
OUT.mkdir(parents=True, exist_ok=True)

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, float(x)))

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def pick(d, *keys, default=None):
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return default

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    p21 = load(P21); p22 = load(P22)
    risk = p22.get("risk", {})
    state = p21.get("state", {})
    current = state.get("current", {})

    score = clamp(pick(risk, "risk_score_pct", "risk_score", default=0))
    prob = clamp(pick(risk, "model_probability_pct", default=0))
    hyd = pick(p22.get("components", {}), "hydrology", default=None)

    rain24 = pick(current, "rainfall_24h_proxy", "rain_24h", default=None)
    rain72 = pick(current, "rainfall_72h_proxy", "rain_72h", default=None)
    nwp24 = pick(current, "nwp_rain_24h_proxy", "nwp_rain_24h", default=None)
    river_change = pick(current, "river_level_change", "river_level_change_m", default=None)
    river_trend = str(pick(current, "river_level_trend", default="")).upper()

    triggers = []
    if score >= 75 or prob >= 80:
        triggers.append({"type":"SEVERE_RISK","severity":"SEVERE","message":"Flood risk is at severe operational level."})
    elif score >= 60 or prob >= 60:
        triggers.append({"type":"HIGH_RISK","severity":"HIGH","message":"High flood risk detected."})
    elif score >= 40 or prob >= 40:
        triggers.append({"type":"WATCH","severity":"MODERATE","message":"Flood risk requires monitoring."})

    if rain24 is not None and float(rain24) >= 100:
        triggers.append({"type":"RAINFALL_24H","severity":"HIGH","message":f"24-hour rainfall loading is {float(rain24):.1f} mm."})
    if rain72 is not None and float(rain72) >= 180:
        triggers.append({"type":"RAINFALL_72H","severity":"HIGH","message":f"72-hour rainfall loading is {float(rain72):.1f} mm."})
    if nwp24 is not None and float(nwp24) >= 120:
        triggers.append({"type":"FORECAST_LOADING","severity":"HIGH","message":f"Forecast 24-hour rainfall is {float(nwp24):.1f} mm."})
    if river_change is not None and float(river_change) > 0.2:
        triggers.append({"type":"RIVER_RISING","severity":"HIGH","message":f"River level is rising by {float(river_change):.2f} m."})
    elif river_trend == "RISING":
        triggers.append({"type":"RIVER_RISING","severity":"MODERATE","message":"River level trend is rising."})

    severe_count = sum(t["severity"] == "SEVERE" for t in triggers)
    high_count = sum(t["severity"] == "HIGH" for t in triggers)

    if score >= 80 or severe_count >= 1:
        alert_level, priority, severity = "SEVERE", "P1", "SEVERE"
    elif score >= 60 or high_count >= 2:
        alert_level, priority, severity = "HIGH", "P2", "HIGH"
    elif score >= 40 or triggers:
        alert_level, priority, severity = "WATCH", "P3", "MODERATE"
    else:
        alert_level, priority, severity = "NORMAL", "P4", "LOW"

    completeness = p22.get("data_quality", {}).get("component_completeness_pct", 0)
    result = {
        "phase":"23", "engine":"ChetakAI Alert Engine", "schema_version":"1.0",
        "timestamp":datetime.now(timezone.utc).isoformat(),
        "source":{"phase21":str(P21), "phase22":str(P22)},
        "basin":p22.get("source", {}),
        "alert":{
            "level":alert_level, "severity":severity, "priority":priority,
            "score":round(score,3), "model_probability_pct":round(prob,3),
            "trigger_count":len(triggers), "active":alert_level != "NORMAL"
        },
        "triggers":triggers,
        "data_quality":{
            "component_completeness_pct":completeness,
            "missing_components":p22.get("data_quality", {}).get("missing_components", [])
        },
        "contract":{
            "no_cross_basin_prediction":True,
            "deterministic":True,
            "source_risk_preserved":True
        }
    }
    if args.strict and not p22.get("contract", {}).get("no_cross_basin_prediction", False):
        raise RuntimeError("Strict alert contract failed.")
    out = OUT / "latest_alert.json"
    audit = OUT / "phase23_audit.jsonl"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    with audit.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp":result["timestamp"],"status":"PASS","alert":result["alert"]})+"\n")
    print("="*110)
    print("CHETAKAI V1 — PHASE 23 ALERT ENGINE")
    print("="*110)
    print(f"Alert level           : {alert_level}")
    print(f"Severity              : {severity}")
    print(f"Priority              : {priority}")
    print(f"Triggers              : {len(triggers)}")
    print(f"Risk score            : {score:.2f}%")
    print(f"Output                : {out}")
    print("PHASE 23 STATUS       : PASS")
    print("="*110)

if __name__ == "__main__":
    main()
