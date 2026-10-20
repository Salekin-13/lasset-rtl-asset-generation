"""Write v5_fixes.json from the v5 conflict-check workflow (wf_aa7e8d3b-38a, merged fixes, in the merger's order), then the
final verifier's fixes (wf_741bb2f0-1be).

  python write_v5_fixes.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "two_phase_v4a__gpt-5.6-luna__high__r0-r2" / "v5_conflict_result.json"


def main():
    R = json.loads(SRC.read_text(encoding="utf-8"))
    R = R.get("result", R)
    FX = []
    for x in R["merged"]["issues"]:
        f = Path(x["fix_file"].replace("\\", "/")).name
        assert f in ("common.md", "phase1.md", "phase2.md"), f
        FX.append({"id": x["id"].split(" ")[0], "file": f, "old": x["fix_old"], "new": x["fix_new"], "kind": x["kind"],
                   "changes_scope": x["changes_scope"], "reason": x["fix_reason"]})
    # then the final verifier's fixes (wf_741bb2f0-1be), numbered on
    V = json.loads((SRC.parent / "v5_verify_result.json").read_text(encoding="utf-8"))
    V = V.get("result", V)
    for i, x in enumerate(V["issues"], len(FX) + 1):
        f = Path(x["file"].replace("\\", "/")).name
        assert f in ("common.md", "phase1.md", "phase2.md"), f
        FX.append({"id": f"F{i}", "file": f, "old": x["fix_old"], "new": x["fix_new"], "kind": x["kind"] + " (final verifier)",
                   "changes_scope": False, "reason": x["problem"]})
    (HERE / "v5_fixes.json").write_text(json.dumps(FX, indent=1, ensure_ascii=False), encoding="utf-8")
    print("v5_fixes.json:", [(x["id"], x["file"], "scope" if x["changes_scope"] else "") for x in FX])


if __name__ == "__main__":
    main()
