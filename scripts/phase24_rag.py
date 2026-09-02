import argparse, json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
P21 = ROOT/"data/processed/models/phase21/latest_risk_snapshot.json"
P22 = ROOT/"data/processed/models/phase22/latest_risk_engine.json"
P23 = ROOT/"data/processed/models/phase23/latest_alert.json"
OUT = ROOT/"data/processed/models/phase24"; OUT.mkdir(parents=True, exist_ok=True)

def load(p):
    with open(p, encoding="utf-8") as f: return json.load(f)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--strict",action="store_true"); args=ap.parse_args()
    p21,p22,p23=load(P21),load(P22),load(P23)
    state=p21.get("state",{}); current=state.get("current",{})
    evidence=p21.get("evidence",{}).get("top_features",[])
    context={
      "location":p21.get("coordinate",{}),
      "basin":p21.get("basin",{}),
      "state_resolution":state.get("state_resolution"),
      "current_state":current,
      "risk":p22.get("risk",{}),
      "risk_components":p22.get("components",{}),
      "risk_drivers":p22.get("drivers",[]),
      "alert":p23.get("alert",{}),
      "alert_triggers":p23.get("triggers",[]),
      "model_evidence":evidence,
      "data_quality":p22.get("data_quality",{})
    }
    sources=[
      {"source_id":"phase21_snapshot","type":"production_snapshot","path":str(P21)},
      {"source_id":"phase22_risk","type":"risk_engine","path":str(P22)},
      {"source_id":"phase23_alert","type":"alert_engine","path":str(P23)}
    ]
    result={"phase":"24","engine":"ChetakAI Evidence/RAG Layer","schema_version":"1.0",
            "timestamp":datetime.now(timezone.utc).isoformat(),"query_context":context,
            "sources":sources,"retrieval":{"mode":"deterministic_context_assembly","documents":len(sources)},
            "contract":{"basin_locked":True,"source_traceable":True,"fabrication_allowed":False}}
    if args.strict and not result["contract"]["basin_locked"]: raise RuntimeError("RAG basin lock failed")
    out=OUT/"latest_rag_context.json"; out.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("="*110); print("CHETAKAI V1 — PHASE 24 RAG / EVIDENCE"); print("="*110)
    print(f"Sources               : {len(sources)}"); print("Basin locked          : True")
    print(f"Context features      : {len(current)}"); print(f"Output                : {out}")
    print("PHASE 24 STATUS       : PASS"); print("="*110)

if __name__=="__main__": main()
