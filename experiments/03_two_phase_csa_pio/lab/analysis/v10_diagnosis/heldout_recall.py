"""Why recall on the original 26 held-out modules is low (user 2026-10-17: "why is recall on the 26 heldout so low?").
Read-only; writes heldout_recall.json. Sends nothing.

Versions: v1 (the first two-phase prompt, the highest held-out recall measured, 0.822 pooled: heldout-prompt-diagnosis),
v9 (working version), v10 (r0-r2); v11 and v11h (r0 only). Exact scorer (compare_v8.score: each reference entry once).
Measures, on the 26 held-out modules (the 15 tuning modules beside them for contrast):
  1. misses per module, and the 12 modules located on 2026-10-14 (tuning_v2's added 12) against the other 14;
  2. where each miss is lost, per (entry, run): transitions.where_lost's first-that-applies stages (labelled secondary in
     Phase 2, Not Kept in Phase 1, parent or field listed, anchor only, lines only, never named);
  3. the kind of each missed entry (port, record port, port field, signal, record signal, signal field);
  4. persistent misses: entries missed in all 3 runs of v9 AND all 3 of v10; for each, how many of v1's 3 runs found it
     and whether any stored run of any version v1-v11h found it.
Self-test: per-run correct counts equal compare_v8.score's (the figures reported earlier this session: held-out v9
134 / 136 / 130, v10 120 / 130 / 131, v11 122, v11h 126); stage counts sum to the misses.

  python -B heldout_recall.py
"""
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402

sys.path.insert(0, str(LAB / "analysis" / "heldout_versions__gpt-5.6-luna__high__r0-r2"))
import v11 as V  # noqa: E402
import transitions as TR  # noqa: E402

CH, R10 = V.CH, V.R10
VERS = {"v1": ("two_phase_v1", (0, 1, 2)), "v9": (V.V9, (0, 1, 2)), "v10": (V.V10, (0, 1, 2)),
        "v11": (V.V11, (0,)), "v11h": ("two_phase_v11h", (0,))}
OLDER = ["two_phase_v2", "two_phase_v4a", "two_phase_v5", "two_phase_v6", "two_phase_v7", "two_phase_v8"]
STAGES = ["secondary", "not reported", "Not Kept", "parent or field listed", "anchor only", "lines only", "never named"]


def names(v, r, m):
    f = CH.run_dir(v, MODEL, r, EFFORT) / "assets" / f"{m}.json"
    return [x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]] if f.exists() else None


def found_occ(ref_m, listed):
    """per reference occurrence (name, k): found or not, the exact scorer's multiset rule."""
    left, k, out = Counter(listed), Counter(), {}
    for n in ref_m:
        k[n] += 1
        hit = left[n] > 0
        if hit:
            left[n] -= 1
        out[(n, k[n])] = hit
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    g, ref = R10.CV.groups_and_ref()
    ho, tu, the12 = g["held-out"], g["tuning"], set(g["held-out: the 12"])
    # self-test 1
    want = {("v9", 0): 134, ("v9", 1): 136, ("v9", 2): 130, ("v10", 0): 120, ("v10", 1): 130, ("v10", 2): 131,
            ("v11", 0): 122, ("v11h", 0): 126}
    got = {}
    for key, (v, reps) in VERS.items():
        for r in reps:
            got[(key, r)] = sum(R10.CV.C8.score(v, r, m, ref)[1] for m in ho)
            mine = sum(sum(found_occ(ref[m], names(v, r, m)).values()) for m in ho)
            if mine != got[(key, r)]:
                sys.exit(f"self-test FAIL: occurrence count {mine} != compare_v8 {got[(key, r)]} for {key} r{r}")
    ok1 = all(got[k] == x for k, x in want.items())
    print(f"self-test (per-run held-out correct = compare_v8.score = this session's figures): {'PASS' if ok1 else 'FAIL'}")
    if not ok1:
        sys.exit(1)
    out = {"held-out modules": len(ho), "reference entries per run": sum(len(ref[m]) for m in ho)}
    # 1. recall by group
    grp = {}
    for key, (v, reps) in VERS.items():
        row = {}
        for gname, ms in (("the 12", [m for m in ho if m in the12]), ("other 14", [m for m in ho if m not in the12]),
                          ("tuning 15", tu)):
            fd = sum(len(ref[m]) for m in ms) * len(reps)
            T = sum(R10.CV.C8.score(v, r, m, ref)[1] for m in ms for r in reps)
            row[gname] = f"{T}/{fd} = {T / fd:.3f}"
        grp[key] = row
    out["recall by group (pooled over the version's runs)"] = grp
    # per module, v9 and v10 pooled misses
    per = {}
    for m in ho:
        per[m[8:]] = {"reference": len(ref[m]), "in the 12": m in the12,
                      **{k: sum(len(ref[m]) - R10.CV.C8.score(VERS[k][0], r, m, ref)[1] for r in VERS[k][1]) for k in ("v1", "v9", "v10")}}
    out["misses per module (summed over 3 runs)"] = dict(sorted(per.items(), key=lambda t: -t[1]["v9"]))
    # 2-3. stages and kinds
    stages, kinds_c, detail = {}, {}, defaultdict(list)
    for key, (v, reps) in VERS.items():
        st, kc = Counter(), Counter()
        for m in ho:
            kd, _ = TR.kinds(m)
            for r in reps:
                ls = names(v, r, m)
                for (n, k), hit in found_occ(ref[m], ls).items():
                    if hit:
                        continue
                    s, why = TR.where_lost(v, r, m, n, ls)
                    st[s] += 1
                    kc[kd.get(n, "?")] += 1
                    if key in ("v9", "v10"):
                        detail[(m, n, k)].append({"version": key, "run": r, "stage": s, "why": why[:2]})
        stages[key] = {s: st[s] for s in STAGES if st[s]}
        stages[key]["total"] = sum(st.values())
        kinds_c[key] = dict(kc)
    if any(stages[k]["total"] != sum(len(ref[m]) for m in ho) * len(VERS[k][1]) - sum(got[(k, r)] for r in VERS[k][1]) for k in VERS):
        sys.exit("self-test FAIL: stage counts do not sum to the misses")
    print("self-test (stage counts sum to the misses): PASS")
    out["where misses are lost (entry-runs)"] = stages
    out["kind of missed entry (entry-runs)"] = kinds_c
    ref_kinds = Counter()
    for m in ho:
        kd, _ = TR.kinds(m)
        ref_kinds.update(kd.get(n, "?") for n in ref[m])
    out["kind of every held-out reference entry (one run)"] = dict(ref_kinds)
    # 4. persistent misses
    pers = []
    for m in ho:
        for (n, k) in found_occ(ref[m], []):
            miss_all = all(not found_occ(ref[m], names(VERS[key][0], r, m))[(n, k)] for key in ("v9", "v10") for r in (0, 1, 2))
            if not miss_all:
                continue
            v1 = sum(found_occ(ref[m], names("two_phase_v1", r, m))[(n, k)] for r in (0, 1, 2))
            anyv = []
            for v in ["two_phase_v1"] + OLDER + [V.V11, "two_phase_v11h"]:
                for r in (0, 1, 2):
                    ls = names(v, r, m)
                    if ls is not None and found_occ(ref[m], ls)[(n, k)]:
                        anyv.append(f"{v.replace('two_phase_', '')} r{r}")
            kd, _ = TR.kinds(m)
            pers.append({"module": m[8:], "entry": n, "occurrence": k, "kind": kd.get(n, "?"), "in the 12": m in the12,
                         "v1 runs found (of 3)": v1, "found by any stored run": anyv,
                         "v9/v10 stages": dict(Counter(d["stage"] for d in detail[(m, n, k)]))})
    out["persistent misses (missed in all 6 runs of v9 and v10)"] = {
        "count": len(pers), "in the 12": sum(p["in the 12"] for p in pers),
        "v1 found in 2+ of 3": sum(p["v1 runs found (of 3)"] >= 2 for p in pers),
        "found by no stored run of any version": sum(not p["found by any stored run"] for p in pers),
        "by kind": dict(Counter(p["kind"] for p in pers)),
        "by module": dict(Counter(p["module"] for p in pers).most_common()),
        "list": pers}
    out["v9/v10 detail (persistent misses only)"] = {f"{m[8:]}:{n}#{k}": d for (m, n, k), d in detail.items()
                                                     if any(p["module"] == m[8:] and p["entry"] == n and p["occurrence"] == k for p in pers)}
    (HERE / "heldout_recall.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if not k.startswith("v9/v10 detail") and k != "persistent misses (missed in all 6 runs of v9 and v10)"}, indent=1))
    p = out["persistent misses (missed in all 6 runs of v9 and v10)"]
    print(json.dumps({k: v for k, v in p.items() if k != "list"}, indent=1))
    for x in p["list"]:
        print(f"  {x['module']}:{x['entry']}#{x['occurrence']} ({x['kind']}) v1 {x['v1 runs found (of 3)']}/3, any: {len(x['found by any stored run'])}, stages {x['v9/v10 stages']}")


if __name__ == "__main__":
    main()
