"""Phase 1-only readings for the rule order / position study (PLAN_P1_ORDER.md). They need only phase1/<module>.json records,
so a variant can be measured from Phase 1 calls alone (about USD 0.53 per run on the held-out 26 against 1.26 for both phases).
  located share   = reference entries that Phase 1 locates (chain.located: Enters / Leaves Through ports, or an element assigned at a
                    held line) / findable. An upper bound on recall except for walk-found names (section 15); tracks final recall across
                    the 24 stored version-runs of 2026-10-18/19 (calibration table in PLAN_P1_ORDER.md).
  located volume  = distinct located names over the group (the candidate pool; A's cut of listed names shows in it).
  concepts, not kept = counts per group.
  per-rule firing = for each rule with a target or must-spare list (v9g_targets.json, meta_v9h_shapes.json intended_cases, meta_v9i.json
                    must_spare): the share of its entries Phase 1 locates. A rule "fires" in Phase 1 when its targets are located.
Self-test: v9j r0 on the held-out 26 gives located 156 / 187 (the figure computed by hand in the session on 2026-10-19).
  python -B read_p1.py <version> [<version> ...]   (runs r0-r2 where phase1 records exist; prints per run and pooled)
"""
import json
import os
import sys
from collections import defaultdict

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402
import run_v9g as RG  # noqa: E402

V, CH = RG.V, RG.CH


def groups():
    g, ref = V.R10.CV.groups_and_ref()
    return {"held-out 26": list(g["held-out"]), "tuning 15": list(g["tuning"])}, ref


def rule_lists():
    lists = defaultdict(set)
    for rid, e in json.loads((HERE / "v9g_targets.json").read_text(encoding="utf-8")):
        lists[rid].add(e if e.startswith("neorv32_") else "neorv32_" + e)
    for f, key in (("meta_v9h_shapes.json", "intended_cases"), ("meta_v9i.json", "must_spare"), ("meta_v9k2.json", "must_spare"), ("meta_v9k.json", "must_spare")):
        p = HERE / "new_rules" / f
        if p.exists():
            for rid, mt in json.loads(p.read_text(encoding="utf-8")).items():
                for e in mt.get(key, []) or []:
                    lists[f"{rid} {key}"].add(e if e.startswith("neorv32_") else "neorv32_" + e)
    return lists


def located_names(v, m, r):
    f = CH.run_dir(v, MODEL, r, EFFORT) / "phase1" / f"{m}.json"
    if not f.exists():
        return None, None
    rec = json.loads(f.read_text(encoding="utf-8"))
    L = CH.located(m, CH.concepts_as_written(rec, v))
    names = set().union(*L.values()) if L else set()
    return names, rec["reply"]


def read(v, ms, ref, reps=(0, 1, 2)):
    lists = rule_lists()
    out = {}
    for r in reps:
        loc = tot = vol = nc = nk = 0
        fire = {rid: [0, 0] for rid in lists}
        done = 0
        for m in ms:
            names, reply = located_names(v, m, r)
            if names is None:
                continue
            done += 1
            vol += len(names)
            nc += len(reply.get("conceptual assets") or [])
            nk += len(reply.get("considered, not kept") or [])
            for n in ref[m]:
                tot += 1
                loc += n in names
            for rid, ents in lists.items():
                for e in ents:
                    mm, x = e.split(":", 1)
                    if mm == m:
                        fire[rid][1] += 1
                        fire[rid][0] += x in names
        if done:
            out[f"r{r}"] = {"modules": done, "located": loc, "findable": tot, "share": round(loc / tot, 3), "volume": vol, "concepts": nc, "not kept": nk,
                            "rules": {rid: f"{a}/{b}" for rid, (a, b) in fire.items() if b}}
    runs = [x for x in out.values() if x["modules"] == len(ms)]
    if runs:
        loc, tot = sum(x["located"] for x in runs), sum(x["findable"] for x in runs)
        out["pooled"] = {"runs": len(runs), "located": loc, "findable": tot, "share": round(loc / tot, 3), "volume": round(sum(x["volume"] for x in runs) / len(runs), 1),
                         "concepts": round(sum(x["concepts"] for x in runs) / len(runs), 1), "not kept": round(sum(x["not kept"] for x in runs) / len(runs), 1)}
    return out


def selftest():
    g, ref = groups()
    x = read("two_phase_v9j", g["held-out 26"], ref, (0,))["r0"]
    ok = (x["located"], x["findable"]) == (156, 187)
    print(f"read_p1 self-test (v9j r0 held-out 26 located 156 / 187): {'PASS' if ok else 'FAIL ' + str(x)}")
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if not selftest():
        sys.exit(1)
    g, ref = groups()
    for v in sys.argv[1:]:
        for name, ms in g.items():
            x = read(v, ms, ref)
            if x:
                print(v, name, json.dumps({k: {kk: vv for kk, vv in val.items() if kk != "rules"} for k, val in x.items()}, ensure_ascii=False))
