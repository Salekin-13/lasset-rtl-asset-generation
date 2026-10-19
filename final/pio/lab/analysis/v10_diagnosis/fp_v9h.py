"""False positives of two_phase_v9h on the 41 modules (user 2026-10-18: "analyze the failure patterns of v9h prompt on the
41 modules. what are the FPs that it consistently emits? are there patterns in them?"). Read-only; sends nothing.

Data: every stored run of two_phase_v9h (r0-r2 on the seven Stage C cell modules; r0 and r1 elsewhere, as sent). An FP
is a listed name (assets file, exact scorer's leftover after the reference rows consume their copies) that is not a
reference entry of the module. "Consistent" = listed in every stored run of its module (at least two runs).
Per FP: kind (port / record port / port field / signal / record signal / signal field; transitions.kinds), the closed-set
role tags, the concepts it was listed under with the reply's justification text (Phase 2 "structural assets" rows,
label primary), and a shape key built from code only: direction, record-ness, the tags ("held on a clock edge",
"set without a clock", "set to constants only", "condition", "copied", ...), whether a bus write feeds it (a "gets value
from" partner that is a field of a bus request record port), whether a bus read returns it (a "gives value to" partner
that is a bus response record field), whether it drives a non-record output port. Patterns = shape keys shared by
consistent FPs across modules, each with the reference entries of the same shape key (what a bar on the shape would
cost). Writes fp_v9h.json and FP_V9H_TABLE.md.
Self-test: per module and run, listed - correct equals the FP count (compare_v8.score), and FP + TP = listed.

  python -B fp_v9h.py
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402

sys.path.insert(0, str(LAB / "analysis" / "heldout_versions__gpt-5.6-luna__high__r0-r2"))
import v11 as V  # noqa: E402
import transitions as TR  # noqa: E402
import heldout_recall as HR  # noqa: E402

CH = V.CH
VER = os.environ.get("FP_VERSION", "two_phase_v9h")
TAGS = ["held on a clock edge", "set without a clock", "set to constants only", "condition", "selector", "index", "copied", "operand",
        "driven", "tied to a constant", "read", "not read", "set by an instance", "reset to a constant"]


def runs_of(m):
    return [r for r in (0, 1, 2) if HR.names(VER, r, m) is not None]


def fps(m, r, ref_m):
    """leftover listed names after the reference rows consume their copies (the exact scorer's complement)."""
    listed = HR.names(VER, r, m)
    left = Counter(listed)
    for n in ref_m:
        if left[n] > 0:
            left[n] -= 1
    return sorted(left.elements())


def facts(m, n):
    for (e, x), fx in CH.closed_names(m).items():
        if x == n:
            return e, fx
    return None, {}


def is_bus_field(m, name):
    """name is a field of a bus request or response record port (a record port whose fields include addr/data/stb or data/ack/err)."""
    if "." not in name:
        return False
    rec = name.split(".")[0]
    _, fx = facts(m, rec)
    if not fx or "port" not in fx or not fx.get("record type"):
        return False
    fn = {f["field"] for f in fx.get("fields", [])}
    return ({"addr", "data", "stb"} <= fn) or ({"data", "ack", "err"} <= fn)


def shape(m, n, kd):
    e, fx = facts(m, n)
    tags = sorted(t for t in TAGS if t in (fx.get("role in RTL") or []))
    cp = fx.get("counterparts") or {}
    def partners(key):
        out = []
        for g in cp.get(key, []) or []:
            p = g.get("partner") if isinstance(g, dict) else g
            if isinstance(p, dict):
                out.append(p.get("port") or json.dumps(p))
            else:
                out.append(str(p))
        return out
    gets, gives, decides, decided = partners("gets value from"), partners("gives value to"), partners("decides"), partners("decided by")
    bus_written = any(is_bus_field(m, p) for p in gets)
    bus_read = any(is_bus_field(m, p) for p in gives)
    drives_out = any(("port" in facts(m, p)[1]) and facts(m, p)[1].get("direction") == "out" for p in gives if p and "." not in p)
    key = "|".join([kd.get(n, "?"), fx.get("direction") or "", "rec" if fx.get("record type") else "", ",".join(tags),
                    "bus-written" if bus_written else "", "bus-read" if bus_read else "", "drives-out" if drives_out else ""])
    return {"entity": e, "kind": kd.get(n, "?"), "tags": tags, "gets": gets[:6], "gives": gives[:6], "decides": decides[:6], "decided_by": decided[:6],
            "bus_written": bus_written, "bus_read": bus_read, "drives_out": drives_out, "key": key}


def rows_for(m, r, n):
    d = CH.run_dir(VER, MODEL, r, EFFORT)
    rec2 = json.loads((d / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
    out = []
    for a in (rec2.get("reply") or {}).get("structural assets") or []:
        if isinstance(a, dict) and a.get("element") == n and a.get("label") == "primary":
            out.append({"concept": a.get("concept id"), "why": (a.get("justification") or a.get("reason") or "")[:220]})
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    g, ref = V.R10.CV.groups_and_ref()
    mods = list(g["tuning"]) + list(g["held-out"])
    out, ok = {"version": VER, "modules": {}, "consistent": [], "one_run": []}, True
    key_fp, key_ref = defaultdict(list), defaultdict(list)
    for m in mods:
        rs = runs_of(m)
        if not rs:
            continue
        kd, _ = TR.kinds(m)
        per = {}
        for r in rs:
            f = fps(m, r, ref[m])
            sc = V.R10.CV.C8.score(VER, r, m, ref)
            if sc is None or len(f) != sc[0] - sc[1]:
                ok = False
            per[r] = f
        all_fp = set().union(*[set(x) for x in per.values()])
        cons = sorted(n for n in all_fp if all(n in per[r] for r in rs)) if len(rs) >= 2 else []
        once = sorted(all_fp - set(cons))
        out["modules"][m[8:]] = {"runs": rs, "reference": len(ref[m]), "fp per run": {f"r{r}": len(per[r]) for r in rs},
                                 "consistent": cons, "not consistent or single run": once}
        for n in cons:
            sh = shape(m, n, kd)
            why = {f"r{r}": rows_for(m, r, n) for r in rs}
            out["consistent"].append({"module": m[8:], "element": n, **sh, "rows": why})
            key_fp[sh["key"]].append(f"{m[8:]}:{n}")
        for n in once:
            out["one_run"].append({"module": m[8:], "element": n, "kind": kd.get(n, "?"), "runs listed": [r for r in rs if n in per[r]]})
        for n in ref[m]:
            key_ref[shape(m, n, kd)["key"]].append(f"{m[8:]}:{n}")
    print(f"self-test (per run listed - correct = FP count, compare_v8.score): {'PASS' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)
    patterns = []
    for key, items in sorted(key_fp.items(), key=lambda t: -len(t[1])):
        patterns.append({"shape": key, "consistent FPs": len(items), "modules": len({i.split(':')[0] for i in items}), "examples": items[:12],
                         "reference entries of the same shape": len(key_ref.get(key, [])), "reference examples": key_ref.get(key, [])[:8]})
    out["patterns by shape"] = patterns
    out["totals"] = {"modules with runs": len(out["modules"]), "consistent FPs": len(out["consistent"]), "one-run FPs": len(out["one_run"]),
                     "by kind (consistent)": dict(Counter(x["kind"] for x in out["consistent"])),
                     "bus-written (consistent)": sum(x["bus_written"] for x in out["consistent"]),
                     "bus-read (consistent)": sum(x["bus_read"] for x in out["consistent"]),
                     "drives an output port (consistent)": sum(x["drives_out"] for x in out["consistent"])}
    (HERE / "fp_v9h.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    lines = [f"# {VER}: consistent false positives on the 41 modules (fp_v9h.py)", "", json.dumps(out["totals"]), "",
             "| module | element | kind | tags | bus-written | bus-read | drives out | concepts (r0) | justification (r0) |", "|---|---|---|---|---|---|---|---|---|"]
    for x in out["consistent"]:
        r0 = next(iter(x["rows"].values()), [])
        lines.append(f"| {x['module']} | {x['element']} | {x['kind']} | {', '.join(x['tags'])} | {x['bus_written']} | {x['bus_read']} | {x['drives_out']} | "
                     f"{', '.join(str(y['concept']) for y in r0)} | {(r0[0]['why'] if r0 else '').replace('|', '/')} |")
    lines += ["", "## Patterns by shape key", "", "| shape | consistent FPs | modules | reference entries of the same shape | examples |", "|---|---|---|---|---|"]
    for p in patterns:
        lines.append(f"| {p['shape']} | {p['consistent FPs']} | {p['modules']} | {p['reference entries of the same shape']} | {', '.join(p['examples'][:6])} |")
    (HERE / "FP_V9H_TABLE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(out["totals"], indent=1))
    for p in patterns[:25]:
        print(f"{p['consistent FPs']:3} FPs in {p['modules']:2} modules | ref same shape {p['reference entries of the same shape']:3} | {p['shape']} | {p['examples'][:4]}")


if __name__ == "__main__":
    main()
