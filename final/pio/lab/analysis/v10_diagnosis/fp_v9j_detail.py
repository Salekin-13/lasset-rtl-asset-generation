"""Second readings on two_phase_v9j's false positives (after fp_v9j.py; reads fp_v9j.json and the stored runs; sends nothing).
  D1 strict anchoring: a primary is "anchored" only when Phase 1's entry names its port (enters/leaves through) or one of
     its ASSIGNMENT lines (gets-value-from, decided-by, reset-by, clocked-by counterpart lines) is a held line of the
     concept; else "walk-found". Precision of each class, overall and for FPs by stability.
  D2 the diagram's hand: for every primary whose points include its holding block, whether the element is listed as a
     member of that block in the diagram; FP vs correct. Member-list length of the blocks where FPs sit vs where correct
     primaries sit.
  D3 the 85 three-of-three FPs, one row each: kind, level (L1-L3), concept names (r0), v9h group, anchored, reached,
     block kinds; and the 12 "new" ones (not among v9h's 153 consistent FPs).
  D4 L3 (extra-concept) occurrences by module and concept name.
  D5 points whose block kind the diagram parse did not resolve.
  D6 hand-check prints: Phase 1 entry and Phase 2 rows for named cases (module:element, r0).
  python -B fp_v9j_detail.py
"""
import json
import re
import sys
from collections import Counter, defaultdict

import fp_v9j as J

CH, TR, HR, V, LAB, HERE, MODEL, EFFORT = J.CH, J.TR, J.HR, J.V, J.LAB, J.HERE, J.MODEL, J.EFFORT
VER, REPS = J.VER, J.REPS
CASES = ["cache:acc_tag", "bus:keeper.lock", "cpu:alu_cmp", "cpu:ctrl.csr_wdata", "cpu_cp_fpu:fpu_operands.rs1", "debug_dm:dm_reg.progbuf",
         "cpu_control:trap_ctrl.irq_buf", "twd:engine.cmd", "slink:route_dst", "neoled:ctrl.strobe"]


def diagram(m):
    """blocks: name -> (kind, members); outputs: set; units: count."""
    for grp in ("tuning", "heldout"):
        f = LAB / "inputs" / "v1" / grp / m / "diagram.txt"
        if f.exists():
            break
    else:
        return {}, set(), 0
    blocks, outs, units = {}, set(), 0
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("UNIT "):
            units += 1
        mo = re.match(r"^\s+\[(\w+)\] (\S+?)(?: (\([^)]*\)))?: (.*)$", line)
        if mo:
            mem = mo.group(4).split(";")[0].strip()
            members = set() if mem == "-" else {x.strip() for x in mem.split(",")}
            blocks.setdefault(mo.group(2), (mo.group(1), members))
            if mo.group(3):
                blocks.setdefault(f"{mo.group(2)} {mo.group(3)}", (mo.group(1), members))
        mo = re.match(r"^\s+OUTPUTS: (.*)$", line)
        if mo:
            outs |= {p.strip() for p in mo.group(1).split(", ")}
    return blocks, outs, units


def assign_lines(m):
    out = {}
    for (e, x), fx in CH.closed_names(m).items():
        ls = set()
        for key in ("gets value from", "decided by", "reset by", "clocked by"):
            for c in (fx.get("counterparts") or {}).get(key, []) or []:
                ls |= set(c.get("lines") or [])
        out[x] = ls
    return out


def prec(rows):
    c, f = sum(1 for x in rows if x["correct"]), sum(1 for x in rows if x["fp"])
    return {"correct": c, "fp": f, "precision": round(c / (c + f), 3) if c + f else None}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads((HERE / "fp_v9j.json").read_text(encoding="utf-8"))
    cons = set(data["consistent"])
    g, ref = V.R10.CV.groups_and_ref()
    mods = list(g["tuning"]) + list(g["held-out"])
    refset = {m: set(ref[m]) for m in mods}
    prims, member_rows, unknown = [], [], Counter()
    fp_stab = defaultdict(set)
    for o in data["occurrences"]:
        fp_stab[(o["module"], o["element"])].add(o["run"])
    for m in mods:
        al = assign_lines(m)
        blocks, outs, units = diagram(m)
        for r in REPS:
            a, p1, p2 = J.load(m, r, "assets"), J.load(m, r, "phase1"), J.load(m, r, "phase2")
            if a is None:
                continue
            fps = Counter(J.F.fps(m, r, ref[m]))
            concepts = {c["id"]: c for c in (p1["reply"].get("conceptual assets") or []) if isinstance(c, dict) and c.get("id")}
            pts = {(x.get("concept id"), x.get("point")): x for x in (p2["reply"].get("points") or []) if isinstance(x, dict)}
            for row in a["Assets"]:
                e = row["Asset RTL"]
                is_fp = fps[e] > 0
                if is_fp:
                    fps[e] -= 1
                correct = e in refset[m] and not is_fp
                cids = [c for c in (row.get("Concepts") or []) if c]
                strict = False
                for c in cids:
                    cc = concepts.get(c, {})
                    if e in set(cc.get("enters through") or []) | set(cc.get("leaves through") or []) or (al.get(e, set()) & set(cc.get("held lines") or [])):
                        strict = True
                prims.append({"module": m[8:], "element": e, "run": r, "correct": correct, "fp": is_fp, "strict": strict,
                              "stab": len(fp_stab[(m[8:], e)]) if is_fp else 0})
                for c in cids:
                    for pt in row.get("Points") or []:
                        x = pts.get((c, pt))
                        if not x:
                            continue
                        if pt in blocks:
                            kind, members = blocks[pt]
                            if str(x.get("reached by", "")).startswith("holding"):
                                member_rows.append({"correct": correct, "fp": is_fp, "member": e in members, "n_members": len(members), "kind": kind})
                        elif pt not in outs:
                            unknown[f"{m[8:]}:{pt}"] += 1
    D1 = {"anchored (strict)": prec([x for x in prims if x["strict"]]), "walk-found (strict)": prec([x for x in prims if not x["strict"]]),
          "walk-found FP occurrences by stability": dict(Counter(x["stab"] for x in prims if x["fp"] and not x["strict"])),
          "anchored FP occurrences by stability": dict(Counter(x["stab"] for x in prims if x["fp"] and x["strict"]))}
    D2 = {"holding-block rows": len(member_rows), "element is a listed member of its holding block": prec([x for x in member_rows if x["member"]]),
          "element not in the block's member list": prec([x for x in member_rows if not x["member"]]),
          "mean member-list length at FP rows": round(sum(x["n_members"] for x in member_rows if x["fp"]) / max(1, sum(1 for x in member_rows if x["fp"])), 1),
          "mean member-list length at correct rows": round(sum(x["n_members"] for x in member_rows if x["correct"]) / max(1, sum(1 for x in member_rows if x["correct"])), 1),
          "by block kind": {k: prec([x for x in member_rows if x["kind"] == k]) for k in sorted({x["kind"] for x in member_rows})}}
    # D3 table
    groups9 = json.loads(open(J.GROUPS_FILE, encoding="utf-8").read())["groups"]
    g9 = {fp: x["name"].split(" ")[0] for x in groups9 for fp in x["fps"]}
    r0 = {}
    for o in data["occurrences"]:
        key = f"{o['module']}:{o['element']}"
        if key in cons and (key not in r0 or o["run"] < r0[key]["run"]):
            r0[key] = o
    strict_of = {}
    for x in prims:
        if x["fp"]:
            strict_of.setdefault(f"{x['module']}:{x['element']}", []).append(x["strict"])
    def just(mm, e, r):
        p2 = J.load("neorv32_" + mm, r, "phase2")
        for x in (p2["reply"].get("structural assets") or []) if p2 else []:
            if isinstance(x, dict) and x.get("element") == e and x.get("label") == "primary":
                return str(x.get("justification") or x.get("reason") or "").replace("|", "/").replace(chr(10), " ")
        return ""
    lines = ["| FP (3 of 3) | kind | level | concept (r0) | v9h group | P1 names it (strict, runs) | reached | block kinds | justification (r0) |", "|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(cons):
        o = r0[key]
        lines.append(f"| {key} | {o['kind']} | {o['level']} | {'; '.join(str(c) for c in o['concept names'])} | {g9.get(key, 'new')} | "
                     f"{sum(strict_of.get(key, []))}/{len(strict_of.get(key, []))} | {o['reached']} | {', '.join(o['block kinds'])} | {just(*key.split(':', 1), o['run'])[:240]} |")
    new = [k for k in sorted(cons) if k not in g9]
    D3 = {"new consistent FPs (not among v9h's 153)": new, "3-of-3 by level": dict(Counter(r0[k]["level"] for k in cons)),
          "3-of-3 by level and group": {lv: dict(Counter(g9.get(k, "new") for k in cons if r0[k]["level"] == lv)) for lv in ("L1", "L2", "L3")}}
    D4 = Counter(f"{o['module']} <- {o['concept names'][0]}" for o in data["occurrences"] if o["level"] == "L3")
    D5 = dict(unknown.most_common(20))
    # D7 the port-copy convention: a register whose every "gets value from" partner is a unit port or port field (a copy of
    # crossing information), and a register whose value leaves whole on an output port it drives; FPs vs reference entries.
    def port_copy_stats():
        res = {"copy of a unit port (every source a port/port field)": {"fp occ": 0, "fp elems": set(), "ref": [], "fp examples": []},
               "register driving an output port whole (gives value to an out port)": {"fp occ": 0, "fp elems": set(), "ref": [], "fp examples": []}}
        fp_occ = Counter((o["module"], o["element"]) for o in data["occurrences"])
        for m in mods:
            cn = CH.closed_names(m)
            ports = {x for (e, x), fx in cn.items() if "port" in fx or fx.get("direction")}
            pfields = {x for x in ports} | {f"{x}.{f['field']}" for (e, x), fx in cn.items() if fx.get("direction") for f in fx.get("fields", [])}
            outs = {x for (e, x), fx in cn.items() if fx.get("direction") == "out"}
            for (e, x), fx in cn.items():
                if fx.get("direction") or "port" in fx:
                    continue
                if "held on a clock edge" not in (fx.get("role in RTL") or []):
                    continue
                cp = fx.get("counterparts") or {}
                src = [c.get("element") or c.get("port") for c in cp.get("gets value from", []) or []]
                src = [s for s in src if s]
                dst = [c.get("element") for c in cp.get("gives value to", []) or [] if c.get("element")]
                key1 = "copy of a unit port (every source a port/port field)"
                key2 = "register driving an output port whole (gives value to an out port)"
                if src and all(s in pfields for s in src):
                    d = res[key1]
                    if x in refset[m]:
                        d["ref"].append(f"{m[8:]}:{x}")
                    if fp_occ[(m[8:], x)]:
                        d["fp occ"] += fp_occ[(m[8:], x)]; d["fp elems"].add(f"{m[8:]}:{x}"); d["fp examples"].append(f"{m[8:]}:{x}<-{src[:2]}")
                if any(t in outs for t in dst):
                    d = res[key2]
                    if x in refset[m]:
                        d["ref"].append(f"{m[8:]}:{x}")
                    if fp_occ[(m[8:], x)]:
                        d["fp occ"] += fp_occ[(m[8:], x)]; d["fp elems"].add(f"{m[8:]}:{x}"); d["fp examples"].append(f"{m[8:]}:{x}->{[t for t in dst if t in outs][:2]}")
        for d in res.values():
            d["fp elems"] = len(d["fp elems"]); d["ref n"] = len(d["ref"]); d["ref"] = d["ref"][:12]; d["fp examples"] = d["fp examples"][:12]
        return res
    D7 = port_copy_stats()
    # D8 the new consistent FPs: justification per run
    D8 = {k: [just(*k.split(":", 1), r)[:200] for r in REPS] for k in new}
    # D9 walk-found (strict) by kind, with the correct ones listed
    kd_cache = {}
    def kind_of(mm, e):
        m = "neorv32_" + mm
        if m not in kd_cache:
            kd_cache[m] = TR.kinds(m)[0]
        return kd_cache[m].get(e, "?")
    wf = [dict(x, kind=kind_of(x["module"], x["element"])) for x in prims if not x["strict"]]
    D9 = {"walk-found by kind": {k: prec([x for x in wf if x["kind"] == k]) for k in sorted({x["kind"] for x in wf})},
          "walk-found correct (module:element, runs)": sorted(Counter(f"{x['module']}:{x['element']}" for x in wf if x["correct"]).items()),
          "walk-found FP internals by stability": dict(Counter(x["stab"] for x in wf if x["fp"] and x["kind"] in ("signal", "signal field", "record signal")))}
    out = {"D1": D1, "D2": D2, "D3": D3, "D7 port-copy convention": D7, "D8 new consistent FPs, justification per run": D8, "D9 walk-found (strict) detail": D9, "D4 L3 occurrences by module and concept": dict(D4.most_common()), "D5 unresolved point names": D5}
    (HERE / "fp_v9j_detail.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "FP_V9J_TABLE.md").write_text("# two_phase_v9j: the 85 false positives listed in all three runs (fp_v9j.py, fp_v9j_detail.py)\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    for k, v in out.items():
        print(k, json.dumps(v, ensure_ascii=False)[:3000])
    # D6 hand-check prints
    for case in CASES:
        mm, e = case.split(":", 1)
        m = "neorv32_" + mm
        a, p1, p2 = J.load(m, 0, "assets"), J.load(m, 0, "phase1"), J.load(m, 0, "phase2")
        if a is None:
            continue
        row = next((x for x in a["Assets"] if x["Asset RTL"] == e), None)
        print(f"\n=== {case} r0: in reference {e in refset[m]}; assets row {json.dumps(row, ensure_ascii=False) if row else None}")
        if not row:
            continue
        for c in row.get("Concepts") or []:
            cc = next((x for x in p1["reply"]["conceptual assets"] if x.get("id") == c), {})
            print(f"  P1 {c}: {cc.get('concept')!r} unit {cc.get('unit')} enters {cc.get('enters through')} leaves {cc.get('leaves through')} held {cc.get('held lines')} | {str(cc.get('information'))[:200]}")
            rows = [(x.get("element"), x.get("label")) for x in p2["reply"]["structural assets"] if x.get("concept id") == c]
            print(f"  P2 rows: {rows}")
            print(f"  P2 not reported: {[x.get('element') for x in p2['reply']['not reported'] if x.get('concept id') == c]}")
            just = next((x.get("justification") or x.get("reason") for x in p2["reply"]["structural assets"] if x.get("concept id") == c and x.get("element") == e), "")
            print(f"  justification: {str(just)[:300]}")
        print(f"  reference entries of {mm}: {ref[m]}")


if __name__ == "__main__":
    main()
