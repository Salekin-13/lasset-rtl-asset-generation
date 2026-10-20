"""Error-analysis table of a two-phase lab run: one row per listed element (TP or FP, exactly as the strict scorer
decides) and one row per missed reference entry (FN), with the model's own reasons and the closed-set facts.

  python experiments/03_two_phase_csa_pio/lab/error_table.py [version] [model] [effort] [rep]

Writes lab/analysis/<version>__<model>__<effort>__r<rep>/table.json. The TP/FP decision mirrors eval_assets.score
(same _hit_idx, same order, each prediction consumed once); a self-test checks that the totals equal the scorer's and
that hand-read wdt rows land where expected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402


def element_facts(m: str) -> dict:
    """(entity, name) -> kind, direction or type, tags, record type, top-level port field."""
    cs = json.loads(CH.inputs(m)["closed_set.json"])
    pf = K.top_level_port_fields(m)
    units = set(CH.diagram_names(m))
    out = {}
    for e in cs["entity list"]:
        ent = e["entity name"]
        for lst, kind in (("port list", "port"), ("signal list", "signal")):
            for x in e[lst]:
                name = x.get(kind)
                base = {"direction": x.get("direction"), "type": x.get("type"), "tags": x.get("role in RTL", []),
                        "record type": x.get("record type")}
                top = kind == "port" and ent in units
                out[(ent, name)] = {**base, "kind": ("top-level " if top else "child-entity ") + kind if kind == "port" else "signal",
                                    "is record": "fields" in x}
                for f in x.get("fields", []):
                    out[(ent, f["field"])] = {"direction": f.get("direction"), "type": f.get("type"),
                                              "tags": f.get("role in RTL", []), "record type": x.get("record type"),
                                              "kind": (("top-level " if top else "child-entity ") + "port field") if kind == "port" else "signal field",
                                              "is record": False, "top-level port field": f"{ent}:{f['field']}" in pf}
    return out


def build(version="two_phase_v1", model="gpt-5.4", effort="high", rep=0) -> dict:
    import eval_assets as ea
    out = CH.run_dir(version, model, rep, effort)
    mods = K.gt_modules()["tuning"]
    with CH.at_root():
        refs = ea.load_refs()["gt"]
    rows, fns = [], []
    for m in mods:
        assets = json.loads((out / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]
        p1 = json.loads((out / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["reply"]
        p2 = json.loads((out / "phase2" / f"{m}.json").read_text(encoding="utf-8"))["reply"]
        concepts = {c["id"]: c for c in p1["conceptual assets"]}
        preds = [(a["Entity"], a["Asset RTL"], a["Security Objective"]) for a in assets]
        ref = refs.get(m, [])
        used, matched = set(), {}
        for ri, (rname, _robj) in enumerate(ref):                      # the scorer's loop, unchanged
            cand = {i: preds[i][1] for i in range(len(preds)) if i not in used}
            pi = ea._hit_idx(cand, rname, True)
            if pi is None:
                fns.append({"module": m, "reference entry": rname, "reference objective": ref[ri][1]})
                continue
            used.add(pi)
            matched[pi] = rname
        facts = element_facts(m)
        primaries = [a for a in p2["structural assets"] if a.get("label") == "primary"]
        secondaries = [a for a in p2["structural assets"] if a.get("label") == "secondary"]
        for i, a in enumerate(assets):
            ent, name = a["Entity"], a["Asset RTL"]
            src = [x for x in primaries if x.get("entity") == ent and (x.get("element") == name or name in (x.get("same role") or []))]
            via_same_role = bool(src) and all(x.get("element") != name for x in src)
            cids = sorted({x.get("concept id") for x in src})
            rows.append({
                "module": m, "entity": ent, "element": name, "verdict": "TP" if i in matched else "FP",
                "matched reference entry": matched.get(i), "objective listed": a["Security Objective"],
                **{k: v for k, v in facts.get((ent, name), {"kind": "not in closed set"}).items()},
                "from 'same role' expansion": via_same_role,
                "concepts": [{"id": c, "concept": concepts.get(c, {}).get("concept"),
                              "objectives": concepts.get(c, {}).get("objectives"),
                              "enters through": concepts.get(c, {}).get("enters through"),
                              "leaves through": concepts.get(c, {}).get("leaves through"),
                              "is an anchor port of it": any(name == p or name.startswith(p + ".") or p.startswith(name + ".")
                                                             for p in (concepts.get(c, {}).get("enters through") or [])
                                                             + (concepts.get(c, {}).get("leaves through") or []))}
                             for c in cids],
                "phase 2 reasons": [x.get("reason") for x in src][:4],
                "phase 2 lines": sorted({l for x in src for l in (x.get("lines") or []) if isinstance(l, int)})[:20],
                "points": sorted({p for x in src for p in (x.get("points") or []) if isinstance(p, str)}),
                "also secondary for": sorted({x.get("concept id") for x in secondaries
                                             if x.get("entity") == ent and x.get("element") == name}),
            })
    return {"run": str(out), "rows": rows, "false negatives": fns}


def selftest(t: dict, log=print) -> bool:
    import eval_assets as ea
    with CH.at_root():
        s = ea.score(t["run"] + "/assets", ea.load_refs()["gt"], strict=True, only=set(K.gt_modules()["tuning"]))
    tp = sum(r["verdict"] == "TP" for r in t["rows"])
    fp = sum(r["verdict"] == "FP" for r in t["rows"])
    ok = (tp, fp, len(t["false negatives"])) == (s["tp"], s["fp"], s["fn"])
    log(f"   {'ok  ' if ok else 'FAIL'} totals equal the scorer: TP {tp}/{s['tp']}, FP {fp}/{s['fp']}, FN {len(t['false negatives'])}/{s['fn']}")
    w = {r["element"]: r for r in t["rows"] if r["module"] == "neorv32_wdt"}
    # hand-read (pilot check, 2026-10-11): ctrl.enable listed and in the reference; bus_req_i.data listed, not in it;
    # cnt_timeout in the reference and not listed; bus_req_i.data is a field of a top-level input port
    c = (w.get("ctrl.enable", {}).get("verdict") == "TP" and w.get("bus_req_i.data", {}).get("verdict") == "FP"
         and w["bus_req_i.data"].get("kind") == "top-level port field" and w["bus_req_i.data"].get("direction") == "in"
         and any(f["reference entry"] == "cnt_timeout" for f in t["false negatives"] if f["module"] == "neorv32_wdt"))
    log(f"   {'ok  ' if c else 'FAIL'} hand-read wdt rows: ctrl.enable TP, bus_req_i.data FP (top-level input port field), cnt_timeout FN")
    return ok and c


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:] + [None] * 4
    args = dict(version=a[0] or "two_phase_v1", model=a[1] or "gpt-5.4", effort=a[2] or "high", rep=int(a[3] or 0))
    t = build(**args)
    if not selftest(t):
        sys.exit("self-test failed: table not written")
    d = LAB / "analysis" / f"{args['version']}__{args['model']}__{args['effort']}__r{args['rep']}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "table.json").write_text(json.dumps(t, indent=1, ensure_ascii=False), encoding="utf-8")
    print(d / "table.json", "| rows", len(t["rows"]), "| FN", len(t["false negatives"]))
