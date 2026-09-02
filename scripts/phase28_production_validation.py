import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES={
"phase21":ROOT/"data/processed/models/phase21/latest_risk_snapshot.json",
"phase22":ROOT/"data/processed/models/phase22/latest_risk_engine.json",
"phase23":ROOT/"data/processed/models/phase23/latest_alert.json",
"phase24":ROOT/"data/processed/models/phase24/latest_rag_context.json",
"phase25":ROOT/"data/processed/models/phase25/latest_weather_assessment.json",
"phase26":ROOT/"data/processed/models/phase26/latest_agent_response.json",
"phase27":ROOT/"data/processed/models/phase27/latest_e2e_response.json"}
OUT=ROOT/"data/processed/models/phase28";OUT.mkdir(parents=True,exist_ok=True)
def load(p):
    with open(p,encoding="utf-8") as f:return json.load(f)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--strict",action="store_true");args=ap.parse_args()
    checks=[]; docs={}
    for name,p in FILES.items():
        ok=p.exists()
        if ok:
            try: docs[name]=load(p); ok=isinstance(docs[name],dict)
            except Exception: ok=False
        checks.append((name,"artifact",ok))
    if all(k in docs for k in ("phase21","phase22","phase23","phase24","phase25","phase26","phase27")):
        checks += [
          ("basin_consistency","single basin",docs["phase21"].get("state",{}).get("basin_state_consistency") is True),
          ("risk_contract","no cross basin",docs["phase22"].get("contract",{}).get("no_cross_basin_prediction") is True),
          ("rag_grounding","grounded",docs["phase25"].get("contract",{}).get("grounded") is True),
          ("llm_no_fabrication","missing values marked",docs["phase25"].get("contract",{}).get("missing_data_not_invented") is True),
          ("orchestration","all deps",all(v=="PASS" for v in docs["phase26"].get("pipeline",{}).values())),
          ("api","status OK",docs["phase27"].get("status")=="OK"),
        ]
    passed=sum(x[2] for x in checks); total=len(checks); status="PASS" if passed==total else "FAIL"
    audit={"phase":"28","status":status,"checks":[{"name":n,"rule":r,"pass":ok} for n,r,ok in checks],
           "passed":passed,"total":total}
    out=OUT/"phase28_production_validation.json";out.write_text(json.dumps(audit,indent=2),encoding="utf-8")
    print("="*110);print("CHETAKAI V1 — PHASE 28 PRODUCTION VALIDATION");print("="*110)
    for n,r,ok in checks: print(f"[{'PASS' if ok else 'FAIL'}] {n:<24} {r}")
    print(f"RESULT                : {passed}/{total}");print(f"OUTPUT                : {out}")
    print(f"PHASE 28 STATUS       : {status}");print("="*110)
    if args.strict and status!="PASS": raise SystemExit(1)
if __name__=="__main__":main()
