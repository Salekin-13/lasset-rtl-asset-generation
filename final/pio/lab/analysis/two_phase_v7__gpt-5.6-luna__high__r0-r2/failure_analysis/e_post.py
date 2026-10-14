"""Stage E scoring (code): the blind judges' answers (E/judge<j>_<module>.json; the journal return if a file write was
blocked) scored with blind/score_v6.py (its self-test runs first), in both modes:
  - "either judge": a change counts when either judge made it (used for correct finds lost and false positives added);
  - "both judges": only when both made it (used for correct finds gained and false positives removed).
Per fix (rule_ids): correct lost, false positives removed, correct gained, false positives added. A fix's counts are
complete only when both judges returned on every module. Elements on which the two judges disagree are listed.
Writes E/blind_result.json.   python e_post.py <stage E run id>
"""
import json
import sys
from collections import defaultdict

import common_fa as F
import b2

sys.path.insert(0, str(F.HERE / "blind"))
import score_v6 as S  # noqa: E402  (loads ../blind_key/boundary_key.json)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    run_id = sys.argv[1]
    s0 = S.score(S.primaries({}, []))
    cmp = F.C7.runs(F.VERSION, F.REPS)
    ok = all((s0[r]["listed"], s0[r]["correct"]) == (cmp[r]["listed"], cmp[r]["correct"]) for r in F.REPS)
    print("score_v6 self-test (no change = compare_v7.runs):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(2)
    J = b2.journal(run_id)
    judges, missing = [], []
    for m in F.MODS:
        s = F.short(m)
        for j in (1, 2):
            p = F.HERE / "E" / f"judge{j}_{s}.json"
            x = json.loads(p.read_text(encoding="utf-8")) if p.exists() else (J.get(f"judge{j}:{s}:rerun") or J.get(f"judge{j}:{s}"))
            if x is None:
                missing.append(f"judge{j}:{s}")
                continue
            judges.append(x)
    res = {"missing judges": missing, "modes": {}}
    for mode in ("either", "both"):
        r = S.evaluate(judges, mode)
        res["modes"][mode] = r
        print(f"\n== {mode}")
        for k in F.REPS:
            print(f"  r{k}: listed {s0[k]['listed']} -> {r['score'][k]['listed']}, correct {s0[k]['correct']} -> {r['score'][k]['correct']}")
        for fx, v in r["per rule"].items():
            print(f"    {fx}: {v}")
    # per fix ranking counts: losses and added FPs from "either", gains and removed FPs from "both"
    fixes = sorted({f for j in judges for f in j.get("fixes_applied", [])})
    rank = {}
    for fx in fixes:
        e, b = res["modes"]["either"]["per rule"].get(fx, {}), res["modes"]["both"]["per rule"].get(fx, {})
        stopped = [x for x in missing]
        rank[fx] = {"correct lost (either)": e.get("correct lost", 0), "false positives added (either)": e.get("false positives added", 0),
                    "correct gained (both)": b.get("correct gained", 0), "false positives removed (both)": b.get("false positives removed", 0),
                    "complete": not stopped}
    res["per fix"] = rank
    # disagreements: elements changed by one judge and not the other
    per_judge = defaultdict(dict)
    for j in judges:
        lab = S.labels_from(j)
        per_judge[j["module"]][j["judge"]] = {rid: v for rid, v in lab.items()}
    dis = []
    for m, d in per_judge.items():
        a, b = d.get(1, {}), d.get(2, {})
        for rid in sorted(set(a) ^ set(b)):
            k = S.KEY.get(rid, {})
            dis.append(f"{rid} {k.get('elements')} only judge {'1' if rid in a else '2'}: {(a.get(rid) or b.get(rid))}")
    res["disagreements"] = dis
    print("\nper fix:", json.dumps(rank, indent=1))
    print(f"judges missing: {missing or 'none'}; row-level disagreements between the two judges: {len(dis)}")
    (F.HERE / "E" / "blind_result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
