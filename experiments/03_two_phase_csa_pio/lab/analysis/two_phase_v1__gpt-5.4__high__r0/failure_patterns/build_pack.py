"""Data pack for the failure-pattern analysis of two_phase_v1 on gpt-5.4 (run r0), 15 tuning modules.

Writes, next to this file:
  pack.json               everything below, in one file (the source for the report)
  views/gt_<module>.md    reference side only, blind to the model: reference rows, 'why' texts, element facts
  views/model_<module>.md model side: Phase 1 concepts (kept and not kept), Phase 2 elements per concept, and where the
                          reference elements appear in the model's output

Exact matching (the user's rule, 2026-10-11): a reference entry matches a listed element only when the names are equal
(no whole-record <-> field credit); each listed element is used once. Reference names that occur nowhere in the inputs
(RTL, closed set, diagram) are kept apart as 'absent'.

The self-test against hand-read lines runs first; nothing is written if it fails.

  python build_pack.py
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE.parent
LAB = HERE.parents[2]
ROOT = HERE.parents[5]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(ANALYSIS))
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402
import rule_check as RC  # noqa: E402

VERSION, MODEL, EFFORT, REP = "two_phase_v1", "gpt-5.4", "high", 0
OUT = CH.run_dir(VERSION, MODEL, REP, EFFORT)
GT_FILE = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
CP_KEYS = ("gets value from", "gives value to", "decided by", "decides", "set by instance", "sets instance input")


def rtl_lines(m):
    return {int(mm.group(1)): l.split("|", 1)[1].rstrip() for l in CH.inputs(m)["rtl.txt"].splitlines()
            if (mm := re.match(r"\s*(\d+) \|", l))}


def diagram(m):
    """unit -> {'blocks': {block: (kind, [members])}, 'arrows': [line], 'inputs': [..], 'outputs': [..]}"""
    units, cur, sec = {}, None, None
    for raw in CH.inputs(m)["diagram.txt"].splitlines():
        l = raw.strip()
        if raw.startswith("UNIT "):
            cur = raw[5:].strip()
            units[cur] = {"blocks": {}, "arrows": [], "inputs": [], "outputs": []}
            continue
        if not cur or not l:
            continue
        if l.startswith("INPUTS:"):
            units[cur]["inputs"] = [x.strip() for x in l[7:].split(",") if x.strip()]
        elif l.startswith("OUTPUTS:"):
            units[cur]["outputs"] = [x.strip() for x in l[8:].split(",") if x.strip()]
        elif l.startswith("BLOCKS"):
            sec = "blocks"
        elif l.startswith("ARROWS"):
            sec = "arrows"
        elif sec == "blocks" and (mm := re.match(r"\[(\w+)\]\s+([^:]+?)(?:\s*\(.*?\))?:\s*(.*)$", l)):
            members = [x.strip() for x in mm.group(3).split(";")[0].split(",") if x.strip()]
            units[cur]["blocks"][mm.group(2).strip()] = (mm.group(1), members)
        elif sec == "arrows":
            units[cur]["arrows"].append(l)
    return units


def tokens(line):
    line = re.sub(r"([\w.()]+?)\.\{([^}]*)\}", lambda mm: " ".join(f"{mm.group(1)}.{f.strip()}" for f in mm.group(2).split(",")), line)
    return set(re.findall(r"[\w.]+", line))


class Module:
    def __init__(self, m):
        self.m = m
        self.f, self.ep = RC.facts(m)
        self.names = CH.closed_names(m)
        self.rtl = rtl_lines(m)
        self.dg = diagram(m)
        self.ue = K.unit_entities(m)
        self.inputs = CH.inputs(m)

    def entities_of(self, name):
        return sorted(e for (e, n) in self.f if n == name)

    def present(self, name):
        pat = re.compile(r"(?<![\w.])" + re.escape(name) + r"(?![\w])")
        return any(pat.search(self.inputs[k]) for k in self.inputs)

    def facts(self, ent, name, n_lines=6):
        x = self.f.get((ent, name))
        if x is None:
            return None
        cs = self.names.get((ent, name)) or {}
        cp = {k: sorted({c["element"] if "element" in c else f"{c.get('instance')}.{c.get('port')} (instance port)"
                         for c in v if isinstance(c, dict) and ("element" in c or "port" in c)})
              for k, v in (cs.get("counterparts") or {}).items()}
        units = [u for u, es in self.ue.items() if ent in es]
        member_of, arrows = [], []
        base = name.split(".")[0]
        for u in units:
            for b, (kind, mem) in self.dg[u]["blocks"].items():
                if name in mem or base in mem:
                    member_of.append(f"{b} [{kind}]")
            arrows += [a for a in self.dg[u]["arrows"] if name in tokens(a) or (base != name and base in tokens(a.split("[")[0]))]
        lines = sorted(x["lines"])
        return {"entity": ent, "name": name, "kind": x["kind"], "direction": x.get("direction"), "type": x.get("type"),
                "record type": x.get("record type"), "whole record": x.get("whole record", False),
                "tags": sorted(x["tags"]), "counterparts": cp, "member of": member_of, "arrows": arrows[:6],
                "n arrows": len(arrows), "lines": lines,
                "rtl": [f"{l}: {self.rtl[l].strip()}" for l in lines[:n_lines] if l in self.rtl]}


def role_signature(fx):
    """A short mechanical description of an element's role, from closed-set facts only."""
    if fx is None:
        return {"where": "absent", "role": "absent", "record": "-", "influence": "-"}
    k = fx["kind"]
    where = {"top-level port": "unit port", "top-level port field": "unit port field", "child port": "sub-unit port",
             "child port field": "sub-unit port field", "signal": "internal signal", "signal field": "internal record field"}[k]
    t = set(fx["tags"])
    used, decides = bool(t & {"copied", "operand"}), bool(t & {"condition", "selector", "index"})
    d = fx.get("direction") if k != "signal" and k != "signal field" else None
    if fx.get("whole record") and not t & {"copied", "operand", "condition", "selector", "index", "held on a clock edge", "set by an instance"}:
        role = "whole record, used through its fields"
    elif t & {"clock", "reset"}:
        role = "clock/reset"
    elif d == "in":
        role = "input, value used" if used else "input, decides only" if decides else "input, read only"
    elif d in ("out", "inout"):
        role = ("output, stored (register)" if "held on a clock edge" in t else "output, set by an instance" if "set by an instance" in t
                else "output, set only to literal values" if "set to constants only" in t else "output, computed without a clock")
    elif "held on a clock edge" in t:
        role = "stored (register)"
    elif "set by an instance" in t:
        role = "set by an instance"
    elif decides and not used:
        role = "decides only"
    elif used:
        role = "carries a value"
    elif "set to constants only" in t:
        role = "set only to literal values"
    else:
        role = "other: " + (", ".join(sorted(t)) or "no tags")
    rt = fx.get("record type") or ""
    record = ("bus/transaction record" if rt in RC.TX else "FIFO record" if "fifo" in rt else
              f"record {rt}" if rt else "-")
    cp = fx["counterparts"]
    infl = []
    if cp.get("gives value to"):
        infl.append("gives value to " + ", ".join(cp["gives value to"][:4]) + (" ..." if len(cp["gives value to"]) > 4 else ""))
    if cp.get("decides"):
        infl.append("decides " + ", ".join(cp["decides"][:4]) + (" ..." if len(cp["decides"]) > 4 else ""))
    return {"where": where, "role": role, "record": record, "influence": "; ".join(infl) or "-"}


def selftest():
    w, c, p = Module("neorv32_wdt"), Module("neorv32_cache"), Module("neorv32_cpu_pmp")
    fe = w.facts("neorv32_wdt", "ctrl.enable")
    fl = w.facts("neorv32_wdt", "ctrl.lock")
    ft = w.facts("neorv32_wdt", "cnt_timeout")
    fh = w.facts("neorv32_wdt", "hw_rst_timeout")
    fc = p.facts("neorv32_cpu_pmp", "ctrl_i")
    checks = [
        ("wdt line 94 reads 'ctrl.enable  <= bus_req_i.data(ctrl_enable_c);'",
         w.rtl[94].strip() == "ctrl.enable  <= bus_req_i.data(ctrl_enable_c);"),
        ("wdt ctrl.enable: record field, reg, held on a clock edge, line 94",
         fe["kind"] == "signal field" and fe["type"] == "reg" and "held on a clock edge" in fe["tags"] and 94 in fe["lines"]),
        ("wdt ctrl.enable gets value from bus_req_i.data", "bus_req_i.data" in fe["counterparts"].get("gets value from", [])),
        ("wdt line 155 'hw_rst_timeout <= ctrl.enable and cnt_timeout and prsc_tick;' -> ctrl.enable gives value to hw_rst_timeout",
         w.rtl[155].strip() == "hw_rst_timeout <= ctrl.enable and cnt_timeout and prsc_tick;"
         and "hw_rst_timeout" in fe["counterparts"].get("gives value to", [])
         and "ctrl.enable" in fh["counterparts"].get("gets value from", [])),
        ("wdt diagram: ctrl.lock is a member of process bus_access", "bus_access [process]" in fl["member of"]),
        ("wdt diagram: cnt_timeout is a member of logic cnt_timeout", "cnt_timeout [logic]" in ft["member of"]),
        ("cache line 284 '    inv_i   => cache_o.cmd_inv,'", c.rtl[284].strip() == "inv_i   => cache_o.cmd_inv,"),
        ("cache: reference names inval_i and cache_o.cmd_dir are absent from the inputs",
         not c.present("inval_i") and not c.present("cache_o.cmd_dir") and c.present("cache_o.cmd_inv")),
        ("pmp line 34 '    ctrl_i    : in  ctrl_bus_t;' -> unit port, in, record ctrl_bus_t",
         p.rtl[34].strip() == "ctrl_i    : in  ctrl_bus_t;" and fc["kind"] == "top-level port" and fc["direction"] == "in"
         and fc["record type"] == "ctrl_bus_t" and 34 in fc["lines"]),
        ("role signature: wdt ctrl.enable -> internal record field, stored", role_signature(fe)["where"] == "internal record field"
         and role_signature(fe)["role"] == "stored (register)"),
        ("pmp ctrl_i (whole record port; its own tags: only 'read', from sensitivity lists such as line 110 "
         "'csr_we_cfg: process(ctrl_i)') -> whole record, used through its fields",
         fc["tags"] == ["read"] and p.rtl[110].strip() == "csr_we_cfg: process(ctrl_i)"
         and role_signature(fc)["role"] == "whole record, used through its fields"),
        ("wdt line 140 'clkgen_en_o <= ctrl.enable;' -> output computed without a clock",
         w.rtl[140].strip() == "clkgen_en_o <= ctrl.enable;"
         and role_signature(w.facts("neorv32_wdt", "clkgen_en_o"))["role"] == "output, computed without a clock"),
        ("wdt bus_req_i.data (read into ctrl.enable at line 94) -> unit port field, input, value used",
         role_signature(w.facts("neorv32_wdt", "bus_req_i.data")) | {} == {**role_signature(w.facts("neorv32_wdt", "bus_req_i.data")),
                                                                           "where": "unit port field", "role": "input, value used"}),
    ]
    ok = all(v for _, v in checks)
    for lab, v in checks:
        print(f"   {'ok  ' if v else 'FAIL'} {lab}")
    return ok


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("self-test (hand-read lines):")
    if not selftest():
        sys.exit("self-test failed: nothing written")
    sys.path.insert(0, str(ROOT / "src"))
    import eval_assets as ea
    with CH.at_root():
        refs = ea.load_refs()["gt"]
    gt_json = json.loads(GT_FILE.read_text(encoding="utf-8"))["modules"]
    table = json.loads((ANALYSIS / "table.json").read_text(encoding="utf-8"))
    wf = json.loads((ANALYSIS / "fp_analysis_workflow.json").read_text(encoding="utf-8"))
    old_group = {i: b["bucket_id"] for b in wf["clustering"]["buckets"] for i in b["member_ids"]}
    order = ["B01", "B02", "B03", "B15", "B05", "B04", "B07", "B10", "B14", "B06", "B09", "B08", "B13", "B12", "B11"]
    old_gid = {b: f"G{i:02d}" for i, b in enumerate(order, 1)}
    mods = K.gt_modules()["tuning"]
    pack = {"run": str(OUT.relative_to(LAB)), "matching": "exact names; each listed element used once; absent reference names kept apart",
            "modules": {}}
    (HERE / "views").mkdir(exist_ok=True)
    tot = defaultdict(int)
    for m in mods:
        M = Module(m)
        p1 = json.loads((OUT / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["reply"]
        p2 = json.loads((OUT / "phase2" / f"{m}.json").read_text(encoding="utf-8"))["reply"]
        # ---------------- reference side: rows (as the reference groups them) and entries (as the scorer counts them)
        rows_, seen = [], set()
        for a in gt_json[m]["assets"]:
            key = (a["raw_cell"], a["why"])
            if key not in seen:
                seen.add(key)
                rows_.append({"row": f"{m.replace('neorv32_', '')}-r{len(rows_) + 1}", "cell": a["raw_cell"], "elements": [],
                              "objectives": a["objectives"], "why": a["why"], "cwe": a.get("cwe")})
            row = next(r for r in rows_ if (r["cell"], r["why"]) == key)
            if a["element"] not in row["elements"]:
                row["elements"].append(a["element"])
        entries = []
        for i, (name, obj) in enumerate(refs[m]):
            ents = M.entities_of(name)
            entries.append({"entry": f"{m.replace('neorv32_', '')}-e{i + 1}", "name": name, "objective": obj,
                            "rows": [r["row"] for r in rows_ if name in r["elements"]],
                            "absent": not M.present(name),
                            "facts": [M.facts(e, name) for e in ents]})
        # ---------------- model side
        listed = [r for r in table["rows"] if r["module"] == m]
        by_name = defaultdict(list)
        for r in sorted(listed, key=lambda r: (r["verdict"] != "TP" or r["matched reference entry"] != r["element"], r["id"])):
            by_name[r["element"]].append(r)
        used, tp = set(), {}
        for e in entries:
            cand = [r for r in by_name.get(e["name"], []) if r["id"] not in used]
            if cand and not e["absent"]:
                used.add(cand[0]["id"])
                tp[e["entry"]] = cand[0]["id"]
                e["found as"] = cand[0]["id"]
        concepts = p1["conceptual assets"]
        cname = {c["id"]: c["concept"] for c in concepts}
        p2rows = defaultdict(lambda: {"primary": [], "secondary": []})
        for a in p2["structural assets"]:
            for el in [a.get("element")] + list(a.get("same role") or []):
                if el and isinstance(el, str):
                    lab = "primary" if a.get("label") == "primary" else "secondary"
                    if (a.get("entity"), el) not in p2rows[a.get("concept id")][lab]:
                        p2rows[a.get("concept id")][lab].append((a.get("entity"), el))
        # where each reference element appears in the model's output (exact name; 'field of' / 'record of' noted)
        def rel(a, b):
            return "same" if a == b else "field of the reference record" if a.startswith(b + ".") else \
                "record of the reference field" if b.startswith(a + ".") else None
        for e in entries:
            pat = re.compile(r"(?<![\w.])" + re.escape(e["name"]) + r"(?![\w])")
            seen_in = []
            for c in concepts:
                for side in ("enters through", "leaves through"):
                    for x in c.get(side, []):
                        if rel(x, e["name"]):
                            seen_in.append(f"{c['id']} anchor ({side}) {x} [{rel(x, e['name'])}]")
                if pat.search(c.get("information", "") + " " + c.get("rubric reason", "") + " " + c.get("attack", "")):
                    seen_in.append(f"{c['id']} named in its Phase 1 text")
            for cid, d in p2rows.items():
                for lab in ("primary", "secondary"):
                    for ent, el in d[lab]:
                        if rel(el, e["name"]):
                            seen_in.append(f"{cid} Phase 2 {lab} {el} [{rel(el, e['name'])}]")
            for pt in p2["points"]:
                if pat.search(pt.get("reason", "")):
                    seen_in.append(f"{pt.get('concept id')} named in the reasoning of point {pt.get('point')}")
                elif pat.search(pt.get("reached by", "")):
                    seen_in.append(f"{pt.get('concept id')} named only in the walk path of point {pt.get('point')}")
            for x in p1.get("considered, not kept", []):
                if pat.search(json.dumps(x)):
                    seen_in.append(f"Phase 1 'considered, not kept': {x.get('concept')}")
            e["seen in model output"] = list(dict.fromkeys(seen_in))
        fps = []
        for r in listed:
            if r["id"] in used:
                continue
            fx = M.facts(r["entity"], r["element"])
            fps.append({"id": r["id"], "entity": r["entity"], "element": r["element"], "same role copy": r["from 'same role' expansion"],
                        "concepts": [x["id"] for x in r["concepts"]], "concept names": [cname.get(x["id"]) for x in r["concepts"]],
                        "model reason": (r.get("phase 2 reasons") or [""])[0], "points": r.get("points", []),
                        "old group": old_gid.get(old_group.get(r["id"], ""), "") or ("none (was a correct find under the record-field credit)"),
                        "signature": role_signature(fx), "facts": fx})
        tps = []
        for e in entries:
            if e["entry"] in tp:
                r = next(x for x in listed if x["id"] == tp[e["entry"]])
                fx = M.facts(r["entity"], r["element"])
                tps.append({"id": r["id"], "entity": r["entity"], "element": r["element"], "entry": e["entry"],
                            "concepts": [x["id"] for x in r["concepts"]], "signature": role_signature(fx), "facts": fx})
        fns = []
        for e in entries:
            if e["entry"] in tp:
                continue
            sig = [role_signature(fx) for fx in e["facts"]] or [role_signature(None)]
            fns.append({"entry": e["entry"], "name": e["name"], "objective": e["objective"], "rows": e["rows"], "absent": e["absent"],
                        "signature": sig[0], "facts": e["facts"], "seen in model output": e["seen in model output"]})
        pack["modules"][m] = {
            "reference rows": rows_, "reference entries": entries,
            "model concepts": concepts, "model not kept": p1.get("considered, not kept", []),
            "model phase 2 by concept": {cid: {k: [f"{el}" + (f" ({ent})" if ent != m else "") for ent, el in v] for k, v in d.items()}
                                         for cid, d in p2rows.items()},
            "listed": len(listed), "TP": tps, "FP": fps, "FN": fns,
        }
        tot["listed"] += len(listed)
        tot["tp"] += len(tps)
        tot["fp"] += len(fps)
        tot["fn"] += len(fns)
        tot["absent"] += sum(1 for x in fns if x["absent"])
        tot["entries"] += len(entries)
        # ---------------- agent views
        mm = m.replace("neorv32_", "")
        g = [f"# Reference (ground truth) for {m}", "",
             f"RTL given to the model: experiments/03_two_phase_csa_pio/lab/inputs/v1/tuning/{m}/rtl.txt (numbered lines); closed set and diagram "
             f"in the same folder.", "",
             "The reference lists structural assets only (element names), grouped in rows; each row has a 'why' text that says "
             "what is at risk. It has no conceptual-asset column.", ""]
        for r in rows_:
            g += [f"## Row {r['row']}: {r['cell']}", f"- objectives: {', '.join(r['objectives'])}", f"- why: {r['why']}",
                  f"- CWE: {r['cwe']}"]
            for name in r["elements"]:
                e = next(x for x in entries if x["name"] == name) if any(x["name"] == name for x in entries) else None
                if e is None:
                    g.append(f"- element {name}: (repeat of another row's entry)")
                    continue
                if e["absent"]:
                    g.append(f"- element {name}: ABSENT from this RTL (the name occurs nowhere in the RTL, closed set or diagram)")
                for fx in e["facts"]:
                    s = role_signature(fx)
                    g += [f"- element {name} in entity {fx['entity']}: {s['where']}, {fx['direction'] or fx['type'] or ''}"
                          f"{', record ' + fx['record type'] if fx['record type'] else ''}; role: {s['role']}; tags: {', '.join(fx['tags']) or '-'}",
                          f"  - counterparts: " + "; ".join(f"{k}: {', '.join(v[:8])}{' ...' if len(v) > 8 else ''}"
                                                           for k, v in fx["counterparts"].items() if k in CP_KEYS) or "  - counterparts: -",
                          f"  - diagram: member of {', '.join(fx['member of']) or '-'}",
                          "  - RTL: " + " | ".join(fx["rtl"])]
            g.append("")
        (HERE / "views" / f"gt_{mm}.md").write_text("\n".join(g), encoding="utf-8")
        v = [f"# Model output for {m} (two_phase_v1, gpt-5.4, run r0)", "", "## Phase 1: conceptual assets kept", ""]
        for c in concepts:
            v += [f"### {c['id']}: {c['concept']}", f"- information: {c.get('information', '')}",
                  f"- objectives: {', '.join(c.get('objectives', []))}; attack: {c.get('attack', '')}",
                  f"- enters through: {', '.join(c.get('enters through', [])) or '-'}; leaves through: {', '.join(c.get('leaves through', [])) or '-'}",
                  f"- held lines: " + " | ".join(f"{l}: {M.rtl[l].strip()}" for l in c.get("held lines", [])[:6] if l in M.rtl),
                  f"- Phase 2 primary: {', '.join(pack['modules'][m]['model phase 2 by concept'].get(c['id'], {}).get('primary', [])) or '-'}",
                  f"- Phase 2 secondary: {', '.join(pack['modules'][m]['model phase 2 by concept'].get(c['id'], {}).get('secondary', [])) or '-'}", ""]
        v += ["## Phase 1: considered, not kept", ""] + [f"- {x.get('concept')}: {x.get('reason', '')}" for x in p1.get("considered, not kept", [])]
        v += ["", "## Where each reference element appears in the model's output (exact name, or record/field of it)", ""]
        for e in entries:
            v.append(f"- {e['name']}" + (" (ABSENT from this RTL)" if e["absent"] else "") +
                     (f" -> listed as primary ({e['found as']})" if e.get("found as") else " -> not listed as primary") +
                     ": " + ("; ".join(e["seen in model output"]) or "nowhere"))
        (HERE / "views" / f"model_{mm}.md").write_text("\n".join(v), encoding="utf-8")
    # cross-check against the strict scorer's table: the only difference must be the record <-> field credit
    strict_tp = {r["id"] for r in table["rows"] if r["verdict"] == "TP"}
    exact_tp = {x["id"] for d in pack["modules"].values() for x in d["TP"]}
    diff = sorted(strict_tp ^ exact_tp)
    nonexact = sorted(r["id"] for r in table["rows"] if r["verdict"] == "TP" and r["matched reference entry"] != r["element"])
    assert diff == nonexact, (diff, nonexact)
    pack["totals"] = dict(tot)
    pack["differs from the strict scorer"] = diff
    (HERE / "pack.json").write_text(json.dumps(pack, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{tot['entries']} reference entries ({tot['absent']} absent from the RTL); listed {tot['listed']}; exact matching: "
          f"TP {tot['tp']}, FP {tot['fp']}, FN {tot['fn']} (of which {tot['absent']} absent).")
    print(f"differs from the strict scorer only in: {diff}")


if __name__ == "__main__":
    main()
