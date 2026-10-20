"""What the occurrence profiles and relation maps say about the 41 modules, beyond the asset list.

Source: only the published code-built maps (step1/lasset_step1/relation_map_code_{tuning,heldout}/b0e767000ec2_codetags/
<module>.json, read through traced_inputs.load_map so sub-unit connection directions are filled in), the SITE tags of
each occurrence stored next to them (<same folder>/_sites/<module>.json), and the flow graphs
(assetgen_meta/traced_inputs_v2/<split>/_flow/<module>.json). No model call. Deterministic: no randomness anywhere.

Terms used below (all read from map fields):
  element        one entry of the map's "ports" or "signals" list, keyed by (entity, name).
  record parent  an element whose name is the prefix of another element of the same entity (ctrl for ctrl.lock).
  leaf           an element that is not a record parent. Counts of registers, roles etc. are over leaves.
  input port     a port with boundary.mode "in" or "inout". Output port: mode "out", "inout" or "buffer".
  stored         effective storage "edge" or "mixed". A field takes the storage of its nearest enclosing record when
                 that record is "edge" or "mixed": `arbiter <= arbiter_nxt` under a clock edge stores every field of
                 arbiter (neorv32_bus line 763), even if the field itself is only assigned in the reset arm.
  register       a stored leaf signal (ports are counted apart, as stored outputs).
  condition site an occurrence of Y tagged IF_COND (in the condition of an if or elsif) or WHEN_COND (in the
                 condition of a conditional assignment, `x <= a when c else b`). Operand site: tagged RHS_OPERAND or
                 VAR_RHS_OPERAND (Y is joined to other names by an operator on the right-hand side). In these maps
                 every GATES record has all its "at" occurrences at condition sites or all at operand sites, never a
                 mix, and none at a case expression (a case selector writes SELECTS records); the self-test checks both.
  value edge     Y -> X when Y has a CARRIES or SOURCES record to X, or a GATES record to X at an operand site (Y is an
                 operand of the value X is given, as in neorv32_wdt line 95: `ctrl.lock <= bus_req_i.data(ctrl_lock_c) and ctrl.enable;`).
  condition gate Y -> X when Y has a GATES record to X at a condition site.
  control record a GATES record whose "at" occurrences are condition sites, any SELECTS record (in these maps at a
                 case expression or an index), or any CONSTRAINS record (in these maps at IF_COND or WHEN_COND). A GATES
                 record at an operand site is a value edge, not control: `cnt_started <= ctrl.enable and ...`
                 (neorv32_wdt line 130) gives ctrl.enable no control over cnt_started; `if (ctrl.enable = '0')`
                 (line 131) does give it control over cnt.
  write-data port an input port leaf whose name contains "data" and that is either
                 (a) a field whose own name contains "data", of a record port whose declared type name ends in "_req_t"
                     (a request record; the type is read from the port's declaration occurrence in the map, e.g.
                     `bus_req_i : in bus_req_t;`, neorv32_wdt line 24). In these maps: bus_req_t (field data, "write
                     data", neorv32_package line 123) and dmi_req_t (field data, line 173); or
                 (b) named as write data: the last part of its name contains "wdata" (wdata_i, csr_wdata_i,
                     ctrl_i.csr_wdata; ctrl_bus_t.csr_wdata is "write data" at neorv32_package line 568).
                 Response data (fields of bus_rsp_t, dmi_rsp_t), read data (xcsr_rdata_i) and stream data
                 (slink_rx_data_i) are not write-data ports.
  input-written register  a register with a value edge from an input port, one step. "From write data" when at
                 least one of those input ports is a write-data port, "from another input" when none is. The map does
                 not say whether the write is a configuration write: this also covers pin synchronisers, operand
                 latches and RAM arrays.

Run:  python map_pipeline/module_insights.py            (self-test, then writes map_pipeline/module_insights/)
      python map_pipeline/module_insights.py --selftest
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict, deque
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import final_pipeline as FP          # noqa: E402

OUT = HERE / "module_insights"
MAPS = FP.STORED_MAPS
FLOW = FP.TRACED_V2
RTL = {"tuning": ROOT / "data/RTL_data", "heldout": ROOT / "data/RTL_heldout"}

FAMILY = {"data": ("CARRIES", "COPIES", "SOURCES", "DERIVES_FROM"),
          "control": ("GATES", "GATED_BY", "SELECTS", "SELECTED_BY", "CONSTRAINS", "CONSTRAINED_BY"),
          "timing": ("SEQUENCES", "CLOCKED_BY", "RESETS", "RESET_BY")}
VALUE_SITES = {"RHS_OPERAND", "VAR_RHS_OPERAND"}
COND_SITES = {"IF_COND", "WHEN_COND"}
CASE_SITES = {"CASE_EXPR", "CASE_COND"}
DECL_SITES = {"DECL_PORT", "DECL_FIELD"}
IN_MODES, OUT_MODES = ("in", "inout"), ("out", "inout", "buffer")
STORED = ("edge", "mixed")
HUB_MIN, GUARD_MIN = 5, 2
REQUEST_TYPE = re.compile(r"_req_t$")
ROLES = ("input port", "output port", "input-written register", "exported state register", "internal state register",
         "sub-unit interface", "combinational decision", "combinational data", "not assigned here")


# --------------------------------------------------------------------------------------------- loading ---
_NS = None


def _ns():
    """The pipeline modules, set up once (FP.setup: repo root as working directory, import paths)."""
    global _NS
    if _NS is None:
        _NS = FP.setup()
    return _NS


def _mods() -> dict:
    return FP.modules(_ns().ea)


@lru_cache(maxsize=None)
def _model(split: str, module: str) -> dict:
    """Everything the other functions read about one module, computed once. Do not mutate the result."""
    d = _ns().TI.load_map(split, module)
    if d is None:
        raise FileNotFoundError(f"no code-built map for {split}/{module}")
    sites = json.loads((MAPS[split] / "_sites" / f"{module}.json").read_text(encoding="utf-8"))
    fp = FLOW / split / "_flow" / f"{module}.json"
    flow = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else None

    els = {}
    for cls in ("ports", "signals"):
        for e in d.get(cls, []):
            k = (e.get("entity", ""), e["name"])
            els[k] = {"e": e, "port": cls == "ports", "mode": (e.get("boundary") or {}).get("mode"),
                      "lines": {o["id"]: o["line"] for o in e.get("occurrences", [])},
                      "texts": {o["id"]: o.get("text", "") for o in e.get("occurrences", [])},
                      "sites": {int(i): set(v) for i, v in sites.get(k[0], {}).get(k[1], {}).items()}}
    by_ent = defaultdict(set)
    for ent, n in els:
        by_ent[ent].add(n)
    parents = {(ent, n) for (ent, n) in els if any(o.startswith(n + ".") for o in by_ent[ent])}

    def enclosing(k):
        ent, n = k
        parts = n.split(".")
        return [(ent, ".".join(parts[:i])) for i in range(len(parts) - 1, 0, -1) if (ent, ".".join(parts[:i])) in els]

    def eff(k):
        s = els[k]["e"].get("storage")
        if s in STORED:
            return s
        for r in enclosing(k):
            if els[r]["e"].get("storage") in STORED:
                return els[r]["e"]["storage"]
        return s

    storage = {k: eff(k) for k in els}
    is_in = {k for k, v in els.items() if v["port"] and v["mode"] in IN_MODES}
    is_out = {k for k, v in els.items() if v["port"] and v["mode"] in OUT_MODES}

    value = defaultdict(lambda: defaultdict(list))      # Y -> X -> [(Y occurrence, [X occurrences])]
    cond = defaultdict(lambda: defaultdict(set))         # Y -> Y occurrence -> {X}
    cond_text = defaultdict(lambda: defaultdict(set))    # (Y, Y occurrence) -> guard text -> {X}
    ctl_out, hub = defaultdict(set), defaultdict(set)
    no_site = gates_mixed = gates_case = 0
    for y, v in els.items():
        ent = y[0]
        for r in v["e"].get("relationship", []) or []:
            t, pa, ats = r.get("type"), r.get("partner_at") or {}, r.get("at", [])
            at_cond = [bool(v["sites"].get(at, set()) & COND_SITES) for at in ats]
            if t == "GATES":
                gates_mixed += len(set(at_cond)) > 1
                gates_case += sum(1 for at in ats if v["sites"].get(at, set()) & CASE_SITES)
            control = t in ("SELECTS", "CONSTRAINS") or (t == "GATES" and any(at_cond))
            for x in r.get("targets", []):
                xk = (ent, x)
                if t in ("CARRIES", "SOURCES"):
                    for at in ats:
                        value[y][xk].append((at, pa.get(x, [])))
                elif t == "GATES":
                    for at in ats:
                        s = v["sites"].get(at, set())
                        if s & COND_SITES:
                            cond[y][at].add(xk)
                            cond_text[(y, at)][r.get("guard") or ""].add(xk)
                        elif s & VALUE_SITES:
                            value[y][xk].append((at, pa.get(x, [])))
                        else:
                            no_site += 1
                if control and xk != y:
                    ctl_out[y].add(xk)
                    if t != "CONSTRAINS":
                        hub[y].add(xk)
    into = defaultdict(set)
    for y, xs in value.items():
        for x in xs:
            into[x].add(y)

    def decl_type(k):                                    # the declared type of the port (of its record, for a field)
        base = k[1].split(".")[0]
        for i, s in sorted(els[k]["sites"].items()):
            if s & DECL_SITES:
                m = re.search(rf"(?<![\w.]){re.escape(base)}\s*:\s*(?:in|inout|out|buffer)\s+(\w+)",
                              els[k]["texts"].get(i, ""), re.I)
                if m:
                    return m.group(1).lower()
        return None

    leaves = [k for k in sorted(els) if k not in parents]
    port_type = {k: decl_type(k) for k in leaves if k in is_in}

    def write_data_rule(k):                              # "a", "b" (module docstring, write-data port) or None
        n = k[1].lower()
        last = n.split(".")[-1]
        if k not in port_type or "data" not in n:
            return None
        if "." in n and "data" in last and REQUEST_TYPE.search(port_type[k] or ""):
            return "a"
        return "b" if "wdata" in last else None

    write_data = {k: rl for k in port_type if (rl := write_data_rule(k))}
    regs = [k for k in leaves if not els[k]["port"] and storage[k] in STORED]
    written_from = {k: sorted(y for y in into.get(k, ()) if y in is_in) for k in regs}
    input_written = [k for k in regs if written_from[k]]
    from_write_data = {k for k in input_written if any(y in write_data for y in written_from[k])}

    def comb(k):                                         # a value may pass through it in the same cycle
        return k in els and not els[k]["port"] and storage[k] == "none"

    reaches, paths = {}, {}
    for k in regs:
        prev, q, hit = {k: None}, deque([k]), []
        while q:
            u = q.popleft()
            for x in sorted(value.get(u, ())):
                if x in prev:
                    continue
                prev[x] = u
                if x in is_out:
                    hit.append(x)
                elif comb(x):
                    q.append(x)
        reaches[k] = sorted(hit)
        paths[k] = {}
        for x in hit:
            p, c = [], x
            while c is not None:
                p.append(c[1])
                c = prev[c]
            paths[k][x[1]] = list(reversed(p))
    resets = {k for k in regs if any(r.get("type") == "RESET_BY" for kk in [k] + enclosing(k)
                                     for r in els[kk]["e"].get("relationship", []) or [])}
    clocks = sorted({n for (_e, n), v in els.items() if any(r.get("type") == "SEQUENCES" for r in v["e"].get("relationship", []) or [])})

    role = {}
    for k in leaves:
        v = els[k]
        if v["port"]:
            role[k] = "input port" if v["mode"] in IN_MODES else "output port" if v["mode"] in OUT_MODES else "not assigned here"
        elif storage[k] in STORED:
            role[k] = ("input-written register" if written_from[k] else
                       "exported state register" if reaches[k] else "internal state register")
        elif v["e"].get("connections"):
            role[k] = "sub-unit interface"
        elif storage[k] == "none":
            role[k] = "combinational decision" if ctl_out.get(k) else "combinational data"
        else:
            role[k] = "not assigned here"
    for k in parents:                                    # a record takes the first role (ROLES order) among its fields
        ent, n = k
        fr = [role[f] for f in leaves if f[0] == ent and f[1].startswith(n + ".")]
        role[k] = min(fr, key=ROLES.index) if fr else "not assigned here"

    guard_sites = defaultdict(dict)                      # Y -> Y occurrence -> protected registers (not Y)
    iw = set(input_written)
    for y, per in cond.items():
        for at, xs in per.items():
            prot = sorted(x for x in xs if x in iw and x != y)
            if prot:
                guard_sites[y][at] = prot
    guards = {y: s for y, s in guard_sites.items() if len({x for p in s.values() for x in p}) >= GUARD_MIN}
    return {"split": split, "module": module, "els": els, "parents": parents, "leaves": leaves, "storage": storage,
            "is_in": is_in, "is_out": is_out, "value": value, "cond": cond, "cond_text": cond_text, "ctl_out": ctl_out,
            "hub": hub, "regs": regs, "written_from": written_from, "input_written": input_written,
            "from_write_data": from_write_data, "write_data": write_data, "port_type": port_type,
            "reaches": reaches, "paths": paths, "resets": resets, "clocks": clocks, "role": role, "guards": guards,
            "flow": flow, "no_site_gates": no_site, "gates_mixed": gates_mixed, "gates_case": gates_case}


# ------------------------------------------------------------------------------------------- portraits ---
def portrait(split: str, module: str) -> dict:
    """One module in numbers. Columns (all from map fields; "leaf", "stored", "register", "control record",
    "write-data port" and "input-written register" as in the module docstring):
      entities              distinct entity names in the map
      ports, signals        entries of the map's "ports" and "signals" lists; elements = ports + signals
      record_parents        elements that are records with fields in the map
      occurrences           sum over elements of len(occurrences): every numbered name occurrence (Occurrence ID)
      records               relationship records as stored, both sides (a relation is written on both elements)
      records_data          records of type CARRIES, COPIES, SOURCES, DERIVES_FROM
      records_control       records of type GATES, GATED_BY, SELECTS, SELECTED_BY, CONSTRAINS, CONSTRAINED_BY, as
                            stored (GATES at operand sites included; this column is a record count, not control)
      records_timing        records of type SEQUENCES, CLOCKED_BY, RESETS, RESET_BY
      registers             stored leaf signals (storage "edge" or "mixed", own or inherited from the record)
      stored_outputs        leaf output ports that are stored (the port itself is a register)
      input_written_registers          registers with a value edge from an input port, one step
      input_written_from_write_data    of those, the ones with at least one write-data port among those inputs
      input_written_from_other_input   of those, the ones with no write-data port among those inputs (the two
                                       columns add up to input_written_registers)
      exported_registers    registers with a path of value edges to an output port through combinational signals only
                            (storage "none", not ports)
      registers_with_reset  registers with a RESET_BY record, on the register or on an enclosing record
      no_reset_share        1 - registers_with_reset / registers (None when there is no register). A map fact, not
                            exactly "no reset": the map writes no RESET_BY for a reset value built from a generic
                            (neorv32_cpu_control exe_engine.pc, line 271), so this is an upper bound.
      clocks                distinct names of elements that have a SEQUENCES record
      control_hubs          elements (ports included) with a GATES record at a condition site or a SELECTS record to at
                            least five distinct other elements (CONSTRAINS records are not counted here)
      top_hub               the hub with the most such targets, "name (n)"
      write_guards          elements with condition gates (GATES record at an IF_COND / WHEN_COND occurrence) to at
                            least two input-written registers other than themselves
      write_guards_internal write guards that are signals, not ports (state such as ctrl.lock, not the bus handshake)
      subunit_connections   entries of the elements' "connections" lists (one per port-map association)
      subunit_instances     distinct instance labels among those entries
      unused_elements       flow graph "no_local_use": no relationship, connection or constant driver. The flow graph
                            keys elements by name, so in the 7 files with several entities a name declared in two
                            entities is one node there (true for this and the next column only)
      control_only_sources  flow graph "control_only_inputs": sources that only gate or select, never carry a value
      reference_entries     entries of the manual reference for the module (not from the map; for comparison)

    Which elements each column counts:
      record parents included (every map element): entities, ports, signals, elements, occurrences, records,
        records_data, records_control, records_timing, subunit_connections, subunit_instances. record_parents counts
        only the parents.
      leaves only: registers, stored_outputs, input_written_registers, input_written_from_write_data,
        input_written_from_other_input, exported_registers, registers_with_reset, no_reset_share (all are counts of
        registers, which are leaves by definition), and the roles of roles() for leaves (a record parent there only
        copies a role from its fields).
      leaves in these maps: control_hubs, top_hub, write_guards, write_guards_internal and clocks are computed over
        every element, but no record parent has a GATES, SELECTS, CONSTRAINS or SEQUENCES record in the 41 maps
        (the self-test checks this), so every hub, guard and clock is a leaf. The registers a guard protects are leaves
        by definition; a hub's targets may be any element.
      not map elements: unused_elements and control_only_sources (flow graph nodes, keyed by name) and
        reference_entries (the manual reference)."""
    M = _model(split, module)
    els, leaves = M["els"], M["leaves"]
    rec = Counter()
    for v in els.values():
        for r in v["e"].get("relationship", []) or []:
            rec[r.get("type")] += 1
    hubs = sorted(((len(M["hub"][k]), k[1]) for k in M["hub"] if len(M["hub"][k]) >= HUB_MIN), key=lambda t: (-t[0], t[1]))
    regs = M["regs"]
    conns = [c for v in els.values() for c in v["e"].get("connections", []) or []]
    fl = M["flow"] or {}
    gt = _mods()["gt"]
    iw, wd = M["input_written"], M["from_write_data"]
    return {"module": module, "split": split,
            "entities": len({k[0] for k in els}),
            "ports": sum(v["port"] for v in els.values()), "signals": sum(not v["port"] for v in els.values()),
            "elements": len(els), "record_parents": len(M["parents"]),
            "occurrences": sum(len(v["lines"]) for v in els.values()),
            "records": sum(rec.values()),
            **{f"records_{f}": sum(rec[t] for t in ts) for f, ts in FAMILY.items()},
            "registers": len(regs),
            "stored_outputs": sum(1 for k in leaves if k in M["is_out"] and M["storage"][k] in STORED),
            "input_written_registers": len(iw),
            "input_written_from_write_data": sum(1 for k in iw if k in wd),
            "input_written_from_other_input": sum(1 for k in iw if k not in wd),
            "exported_registers": sum(1 for k in regs if M["reaches"][k]),
            "registers_with_reset": len(M["resets"]),
            "no_reset_share": round(1 - len(M["resets"]) / len(regs), 3) if regs else None,
            "clocks": len(M["clocks"]),
            "control_hubs": len(hubs), "top_hub": f"{hubs[0][1]} ({hubs[0][0]})" if hubs else "",
            "write_guards": len(M["guards"]),
            "write_guards_internal": sum(1 for k in M["guards"] if not els[k]["port"]),
            "subunit_connections": len(conns), "subunit_instances": len({c.get("instance") for c in conns}),
            "unused_elements": len(fl.get("no_local_use", [])), "control_only_sources": len(fl.get("control_only_inputs", {})),
            "reference_entries": len(gt.get(module, []))}


def portraits(mods: dict):
    """portrait() for every module of the tuning and held-out splits (41 rows), tuning first."""
    import pandas as pd
    return pd.DataFrame([portrait(s, m) for s in ("tuning", "heldout") for m in mods[s]])


# ----------------------------------------------------------------------------------------------- guards ---
def guards(split: str, module: str) -> list[dict]:
    """Write guards (see portrait): one dict per condition occurrence of a guard element that gates at least one
    input-written register. Keys: guard, entity, guard_role, line (of the guard's occurrence), condition (the guard
    texts of the records that gate the protected registers there, joined by " | "), rtl (the occurrence's line text),
    protects (input-written registers it gates there, itself left out), gates_itself (its own write is under the same
    condition: a sticky lock), protects_total (input-written registers it gates over all its occurrences)."""
    M = _model(split, module)
    out = []
    for y in sorted(M["guards"]):
        sites = M["guards"][y]
        total = len({x for p in sites.values() for x in p})
        for at in sorted(sites, key=lambda a: (M["els"][y]["lines"].get(a, 0), a)):
            mine = set(sites[at]) | {y}
            texts = sorted(t for t, xs in M["cond_text"].get((y, at), {}).items() if t and xs & mine)
            out.append({"module": module, "entity": y[0], "guard": y[1], "guard_role": M["role"][y],
                        "line": M["els"][y]["lines"].get(at), "condition": " | ".join(texts),
                        "rtl": M["els"][y]["texts"].get(at, ""), "protects": [x[1] for x in sites[at]],
                        "gates_itself": y in M["cond"][y].get(at, set()), "protects_total": total})
    return out


# ------------------------------------------------------------------------------------------------ roles ---
def roles(split: str, module: str) -> list[dict]:
    """A structural role for every element, from map fields only. Fixed order of tests:
      port, mode in/inout            input port
      port, mode out/buffer          output port
      stored signal + value edge from an input port              input-written register (stored, written from an
                                     input port in one step. The map does not tell a configuration write from a pin
                                     sample, an operand latch or a RAM write, so all of these are here. Column
                                     from_write_data splits them: True when a write-data port is among the inputs)
      stored signal + value path to an output port               exported state register
      other stored signal                                        internal state register
      not stored, has sub-unit connections                       sub-unit interface
      storage "none" + a control record to another element      combinational decision (a GATES record at a
                                     condition site, a SELECTS record or a CONSTRAINS record; a GATES record at an
                                     operand site does not count)
      other storage "none"                                       combinational data
      anything else (storage "not assigned", no connection)      not assigned here
    A record parent takes the first role, in that order, held by any of its fields.
    Column control_targets: distinct other elements this one reaches by a GATES record at a condition site or a
    SELECTS record (the control-hub count of portrait; CONSTRAINS not included)."""
    M = _model(split, module)
    out = []
    for k in sorted(M["els"]):
        v = M["els"][k]
        iw = k in M["written_from"] and bool(M["written_from"][k])
        out.append({"split": split, "module": module, "entity": k[0], "element": k[1], "role": M["role"][k],
                    "port": v["port"], "mode": v["mode"], "storage": M["storage"][k], "record_parent": k in M["parents"],
                    "written_from": [y[1] for y in M["written_from"].get(k, [])],
                    "from_write_data": (k in M["from_write_data"]) if iw else None,
                    "reaches_outputs": [x[1] for x in M["reaches"].get(k, [])],
                    "reset": k in M["resets"] if k in M["written_from"] else None,
                    "control_targets": len(M["hub"].get(k, ())), "write_guard": k in M["guards"]})
    return out


def all_roles(mods: dict):
    import pandas as pd
    return pd.DataFrame([r for s in ("tuning", "heldout") for m in mods[s] for r in roles(s, m)])


# ------------------------------------------------------------------------------------------ name matching ---
def match_element(split: str, module: str, name: str, entity: str = "", exclude=()):
    """The map element a listed name stands for, by the scorer's rule (eval_assets._hit_idx, strict): the exact name
    first; else a dotted name matches its record (ctrl.x -> ctrl) and a plain name matches a field of the same record.
    Names are lower-cased (VHDL is case-insensitive; the maps are lower-case). The listed entity breaks ties between
    entities. Without a matching entity, the candidates that share the first candidate's name (one per entity) are
    tried in sorted order, skipping those in exclude; when all of them are in exclude, the first one is returned.
    -> (entity, name) or None."""
    M = _model(split, module)
    n, keys, ent = name.strip().lower(), sorted(M["els"]), (entity or "").lower()
    for cand in ([k for k in keys if k[1] == n],
                 [k for k in keys if k[1] == n.split(".")[0]] if "." in n else [k for k in keys if k[1].split(".")[0] == n]):
        if cand:
            if ent:
                hit = next((k for k in cand if k[0] == ent), None)
                if hit is not None:
                    return hit
            same = [k for k in cand if k[1] == cand[0][1]]
            return next((k for k in same if k not in exclude), cand[0])
    return None


def resolve(items) -> list:
    """match_element for each entry (split, module, entity, name, ...) in list order, with one set of used element keys
    per (split, module): a second entry with the same name and no entity goes to the next entity's element."""
    used, out = defaultdict(set), []
    for split, m, ent, n, *_rest in items:
        k = match_element(split, m, n, ent, exclude=used[(split, m)])
        if k is not None:
            used[(split, m)].add(k)
        out.append(k)
    return out


def _labels(preds: list[str], ref: list) -> list[str]:
    """TP / FP per listed name, consumed exactly as eval_assets.score consumes them (strict)."""
    ea, used = _ns().ea, set()
    for rname, _o in ref:
        pi = ea._hit_idx({i: preds[i] for i in range(len(preds)) if i not in used}, rname, True)
        if pi is not None:
            used.add(pi)
    return ["TP" if i in used else "FP" for i in range(len(preds))]


def _complete(d: Path, names: list[str]) -> bool:
    return d.exists() and all((d / "_nested" / f"{m}.json").exists() for m in names)


def default_lists(ns, mods: dict) -> tuple[dict, dict]:
    """The lists role_enrichment compares: {label: [(split, module, entity, name, TP/FP or None)]} and a status dict.
    Every scored list is checked against eval_assets.score (its TP count must agree)."""
    gt, ea = mods["gt"], ns.ea
    import lasset_layer as LL
    lists, status = {}, {}

    def scored(label, per_split: dict):
        items, tp_expect = [], 0
        for split, runs in per_split.items():
            for run in runs:
                for m in mods[split]:
                    preds = run.get(m, [])
                    for (ent, n, _o), lab in zip(preds, _labels([p[1] for p in preds], gt[m])):
                        items.append((split, m, ent, n, lab))
                tp_expect += ea.score({m: run.get(m, []) for m in mods[split]}, gt, strict=True, only=set(mods[split]))["tp"]
        assert sum(1 for x in items if x[4] == "TP") == tp_expect, f"{label}: hit count differs from eval_assets.score"
        lists[label] = items

    lists["reference"] = [(s, m, "", n, None) for s in ("tuning", "heldout") for m in mods[s] for n, _o in gt[m]]
    lists["reference, tuning"] = [x for x in lists["reference"] if x[0] == "tuning"]
    rtl = LL.load_list("rtl_only")
    scored("LAsset RTL-only", {s: [LL.as_run({m: rtl.get(m, []) for m in mods[s]})] for s in ("tuning", "heldout")})
    claude = {"tuning": ROOT / "runs/assets_opt_v1_r0", "heldout": ROOT / "runs/assets_opt_heldout_v1_r0"}
    if all(_complete(d, mods[s]) for s, d in claude.items()):
        scored("final prompt, Claude, r0", {s: [ea.load_run(d)] for s, d in claude.items()})
        status["final prompt, Claude, r0"] = [d.name for d in claude.values()]
    else:
        status["final prompt, Claude, r0"] = "incomplete: " + ", ".join(d.name for s, d in claude.items() if not _complete(d, mods[s]))
    for split in ("tuning", "heldout"):
        done = [d for d in FP.run_dirs(split) if _complete(d, mods[split])]
        label = f"final prompt, gpt-5.4, {split}"
        if done:
            scored(label, {split: [ea.load_run(d) for d in done]})
            status[label] = [d.name for d in done]
        else:
            status[label] = "pending (no complete run: " + ", ".join(d.name for d in FP.run_dirs(split)) + ")"
    return lists, status


# ------------------------------------------------------------------------------------------ enrichment ---
def role_enrichment(ns, mods: dict, lists: dict | None = None):
    """Share of each role among all elements of the 41 modules and among each list's entries (default_lists).
    Each listed entry is matched to one map element (resolve: match_element in list order, with one set of used
    elements per module, so two entity-less entries with the same name go to two entities' elements); its role is
    that element's role. Columns per list: "<label> n" (entries with that role), "<label> share" (n / matched entries
    of the list), and for scored lists "<label> P" (precision inside the role: hits / n, strict scorer labels). The base
    column "all elements" counts every map element once (record parents included). The last row counts entries that
    matched no element; they are left out of the shares. df.attrs holds the denominators."""
    import pandas as pd
    if lists is None:
        lists, _ = default_lists(ns, mods)
    base = Counter(r for s in ("tuning", "heldout") for m in mods[s] for r in _model(s, m)["role"].values())
    cols, attrs = {}, {"all elements": sum(base.values())}
    cols["all elements n"] = [base[r] for r in ROLES] + [0]
    cols["all elements share"] = [round(base[r] / sum(base.values()), 3) for r in ROLES] + [None]
    for label, items in lists.items():
        cnt, hit, miss = Counter(), Counter(), 0
        for (split, m, ent, n, lab), k in zip(items, resolve(items)):
            if k is None:
                miss += 1
                continue
            r = _model(split, m)["role"][k]
            cnt[r] += 1
            hit[r] += lab == "TP"
        tot = sum(cnt.values())
        cols[f"{label} n"] = [cnt[r] for r in ROLES] + [miss]
        cols[f"{label} share"] = [round(cnt[r] / tot, 3) if tot else None for r in ROLES] + [None]
        if any(x[4] is not None for x in items):
            cols[f"{label} P"] = [round(hit[r] / cnt[r], 3) if cnt[r] else None for r in ROLES] + [None]
        attrs[label] = {"entries": len(items), "matched": tot, "not matched": miss,
                        "hits": sum(1 for x in items if x[4] == "TP") if any(x[4] for x in items) else None}
    df = pd.DataFrame(cols, index=list(ROLES) + ["(no map element; not in shares)"])
    df.attrs["denominators"] = attrs
    return df


# ------------------------------------------------------------------------------------------- deep dive ---
def _listed(name: str, ref_names: list[str]) -> bool:
    """Whether the reference lists this element, by the scorer's own matching."""
    ea = _ns().ea
    return any(ea._hit_idx({0: name}, r, True) is not None for r in ref_names)


def deep_dive(split: str = "tuning", module: str = "neorv32_wdt") -> dict:
    """One module for display: its write guards, input-written registers, what reaches each output port, its control
    hubs, and for each of these whether the manual reference lists it (scorer's matching)."""
    M = _model(split, module)
    ref = [n for n, _o in _mods()["gt"].get(module, [])]
    els = M["els"]
    g = guards(split, module)
    for x in g:
        x["listed"] = _listed(x["guard"], ref)
        x["protects_listed"] = [p for p in x["protects"] if _listed(p, ref)]
    guarded = defaultdict(set)
    for x in g:
        for p in x["protects"]:
            guarded[p].add(x["guard"])
    iw = []
    for k in M["input_written"]:
        lines = sorted({els[k]["lines"].get(i) for y in M["written_from"][k] for _a, ids in M["value"][y][k] for i in ids} - {None})
        iw.append({"register": k[1], "written_from": [y[1] for y in M["written_from"][k]],
                   "from_write_data": k in M["from_write_data"], "write_lines": lines,
                   "reset": k in M["resets"], "reaches_outputs": [x[1] for x in M["reaches"][k]],
                   "guarded_by": sorted(guarded.get(k[1], set())), "listed": _listed(k[1], ref)})
    outs = []
    for o in sorted(k for k in M["leaves"] if k in M["is_out"]):
        regs = sorted(r[1] for r in M["regs"] if o in M["reaches"][r])
        outs.append({"output": o[1], "registers": regs, "paths": {r: M["paths"][(o[0], r)][o[1]] for r in regs},
                     "listed": _listed(o[1], ref), "registers_listed": [r for r in regs if _listed(r, ref)]})
    hubs = sorted(({"element": k[1], "role": M["role"][k], "control_targets": len(v), "targets": sorted(x[1] for x in v),
                    "listed": _listed(k[1], ref)} for k, v in M["hub"].items() if len(v) >= HUB_MIN),
                  key=lambda h: (-h["control_targets"], h["element"]))
    cover = []
    for n, k in zip(ref, resolve([(split, module, "", n) for n in ref])):
        cover.append({"reference entry": n, "element": k[1] if k else None, "role": M["role"][k] if k else None,
                      "write guard": bool(k) and k in M["guards"], "input-written register": bool(k) and k in set(M["input_written"]),
                      "reaches an output": bool(k) and bool(M["reaches"].get(k)), "control hub": bool(k) and len(M["hub"].get(k, ())) >= HUB_MIN})
    return {"module": module, "split": split, "portrait": portrait(split, module), "write_guards": g,
            "input_written_registers": iw, "outputs": outs, "control_hubs": hubs, "reference": cover}


# -------------------------------------------------------------------------------------------- self-test ---
def _rtl(split: str, module: str, n: int, comment: bool = False) -> str:
    """Line n of the RTL file, spaces collapsed; the comment removed unless comment=True."""
    t = (RTL[split] / f"{module}.vhd").read_text(encoding="utf-8", errors="ignore").splitlines()[n - 1]
    return " ".join((t if comment else t.split("--")[0]).split())


def selftest(log=print) -> bool:
    """Facts read by hand from the RTL, with line numbers. Each fact first checks the RTL line still reads as quoted,
    then checks what this module derives from the map."""
    ok, n_chk, n_fail = True, 0, 0

    def chk(cond, msg):
        nonlocal ok, n_chk, n_fail
        n_chk += 1
        n_fail += not cond
        ok &= bool(cond)
        log(f"  [{'ok' if cond else 'FAIL'}] {msg}")

    def line_is(split, m, n, text, comment=False):
        chk(_rtl(split, m, n, comment) == " ".join(text.split()), f"{m} line {n} reads: {text}")

    def role(split, m, name, ent=None):
        M = _model(split, m)
        k = (ent or m, name)
        return M["role"].get(k)

    # --- thresholds the docstrings state in words ("at least five", "at least two") ---
    chk(HUB_MIN == 5 and GUARD_MIN == 2,
        f"thresholds pinned: control hub >= 5 targets, write guard >= 2 registers (got {HUB_MIN}, {GUARD_MIN})")

    # --- neorv32_wdt (tuning) ---
    T, W = "tuning", "neorv32_wdt"
    line_is(T, W, 93, "if (ctrl.lock = '0') then")
    for n, t in ((94, "ctrl.enable <= bus_req_i.data(ctrl_enable_c);"),
                 (95, "ctrl.lock <= bus_req_i.data(ctrl_lock_c) and ctrl.enable;"),
                 (96, "ctrl.strict <= bus_req_i.data(ctrl_strict_c);"),
                 (97, "ctrl.timeout <= bus_req_i.data(ctrl_timeout_msb_c downto ctrl_timeout_lsb_c);")):
        line_is(T, W, n, t)
    g = [x for x in guards(T, W) if x["guard"] == "ctrl.lock"]
    chk(len(g) == 1 and g[0]["line"] == 93 and {"ctrl.enable", "ctrl.strict", "ctrl.timeout"} <= set(g[0]["protects"]),
        "wdt: guards() has ctrl.lock at line 93 protecting ctrl.enable, ctrl.strict, ctrl.timeout" + ("" if g else " (none found)"))
    chk(bool(g) and g[0]["condition"] == "ctrl.lock = '0'", "wdt: the condition text of that guard is ctrl.lock = '0' (line 93)")
    chk(bool(g) and g[0]["gates_itself"], "wdt: ctrl.lock's own write (line 95) is also under line 93: a sticky lock")
    M = _model(T, W)
    chk(role(T, W, "ctrl.lock") == "input-written register" and M["written_from"][(W, "ctrl.lock")] == [(W, "bus_req_i.data")],
        "wdt: ctrl.lock is an input-written register written from bus_req_i.data (line 95)")
    chk(all(role(T, W, f"ctrl.{f}") == "input-written register" for f in ("enable", "strict", "timeout")),
        "wdt: ctrl.enable, ctrl.strict, ctrl.timeout are input-written registers (lines 94, 96, 97)")
    line_is(T, W, 131, "if (ctrl.enable = '0') or (reset_wdt = '1') then")
    chk((W, "ctrl.enable") not in M["guards"], "wdt: ctrl.enable's condition (line 131) gates cnt only, so it is no write guard")
    line_is(T, W, 140, "clkgen_en_o <= ctrl.enable;")
    chk("clkgen_en_o" in [x[1] for x in M["reaches"][(W, "ctrl.enable")]], "wdt: ctrl.enable reaches output clkgen_en_o (line 140)")
    line_is(T, W, 141, "prsc_tick <= clkgen_i(clk_div4096_c);")
    chk(role(T, W, "prsc_tick") in ("combinational decision", "combinational data"),
        "wdt: prsc_tick (concurrent assignment, line 141) is not a register")
    p = portrait(T, W)
    chk(p["registers"] == 12 and p["registers_with_reset"] == 12 and p["input_written_registers"] == 4 and p["clocks"] == 1,
        "wdt: 12 registers, all with a reset arm (lines 73-80, 124-127, 151-153, 168-169); 4 input-written registers; "
        f"1 clock clk_i (lines 81, 128, 154, 170) (got {p['registers']}, {p['registers_with_reset']}, "
        f"{p['input_written_registers']}, {p['clocks']})")

    # --- control = GATES at a condition site (wdt ctrl.enable: one condition, four operand uses) ---
    for n, t in ((130, "cnt_started <= ctrl.enable and (cnt_started or prsc_tick);"),
                 (155, "hw_rst_timeout <= ctrl.enable and cnt_timeout and prsc_tick;"),
                 (156, "hw_rst_access <= ctrl.enable and ctrl.strict and reset_force;")):
        line_is(T, W, n, t)
    chk(M["hub"].get((W, "ctrl.enable")) == {(W, "cnt")},
        "wdt: ctrl.enable controls cnt only (condition, line 131); its operand uses at lines 95, 130, 155, 156 are value "
        f"edges, not control (got {sorted(x[1] for x in M['hub'].get((W, 'ctrl.enable'), ()))})")
    chk({(W, "cnt_started"), (W, "hw_rst_timeout"), (W, "hw_rst_access"), (W, "ctrl.lock")} <= set(M["value"].get((W, "ctrl.enable"), {})),
        "wdt: those four operand uses are value edges from ctrl.enable (lines 95, 130, 155, 156)")
    mixed = sum(_model(s, m)["gates_mixed"] for s in ("tuning", "heldout") for m in _mods()[s])
    case = sum(_model(s, m)["gates_case"] for s in ("tuning", "heldout") for m in _mods()[s])
    chk(mixed == 0 and case == 0, "no GATES record mixes condition and operand 'at' sites, and none is at a case "
        f"expression, 41 modules ({mixed} mixed, {case} at CASE_EXPR / CASE_COND)")

    # --- write-data ports: the type of the record, read from the declaration occurrence ---
    line_is(T, "neorv32_package", 121, "type bus_req_t is record")
    line_is(T, "neorv32_package", 123, "data : std_ulogic_vector(31 downto 0); -- write data", comment=True)
    line_is(T, "neorv32_package", 170, "type dmi_req_t is record")
    line_is(T, "neorv32_package", 173, "data : std_ulogic_vector(31 downto 0);")
    line_is(T, "neorv32_package", 568, "csr_wdata : std_ulogic_vector(31 downto 0); -- write data", comment=True)
    line_is(T, W, 24, "bus_req_i : in bus_req_t;")
    chk(M["port_type"].get((W, "bus_req_i.data")) == "bus_req_t" and M["write_data"].get((W, "bus_req_i.data")) == "a"
        and (W, "ctrl.lock") in M["from_write_data"],
        "wdt: bus_req_i.data is a write-data port by rule (a), type bus_req_t read from line 24; ctrl.lock (line 95) is "
        "written from write data")
    chk(M["port_type"].get((W, "bus_req_i.rw")) == "bus_req_t" and (W, "bus_req_i.rw") not in M["write_data"],
        "wdt: bus_req_i.rw (same record, line 24) is no write-data port: its name has no 'data'")
    P_, PM = "neorv32_cpu_pmp", _model(T, "neorv32_cpu_pmp")
    line_is(T, P_, 34, "ctrl_i : in ctrl_bus_t;")
    line_is(T, P_, 129, "pmpcfg(i)(cfg_r_c) <= ctrl_i.csr_wdata((i mod 4)*8+cfg_r_c);")
    chk(PM["port_type"].get((P_, "ctrl_i.csr_wdata")) == "ctrl_bus_t" and PM["write_data"].get((P_, "ctrl_i.csr_wdata")) == "b"
        and (P_, "pmpcfg") in PM["from_write_data"],
        "cpu_pmp: ctrl_i.csr_wdata (ctrl_bus_t, line 34) is a write-data port by rule (b); pmpcfg (line 129) is written "
        "from write data")
    Dt, DT = "neorv32_debug_dtm", _model(T, "neorv32_debug_dtm")
    line_is(T, Dt, 36, "dmi_rsp_i : in dmi_rsp_t")
    line_is(T, Dt, 274, "dmi_ctrl.rdata <= dmi_rsp_i.data;")
    chk(DT["port_type"].get((Dt, "dmi_rsp_i.data")) == "dmi_rsp_t" and (Dt, "dmi_rsp_i.data") not in DT["write_data"]
        and (Dt, "dmi_ctrl.rdata") in DT["input_written"] and (Dt, "dmi_ctrl.rdata") not in DT["from_write_data"],
        "debug_dtm: dmi_rsp_i.data is response data (dmi_rsp_t, line 36), no write-data port; dmi_ctrl.rdata (line 274) "
        "is written from another input")

    # --- neorv32_hwspinlock (tuning) ---
    H = "neorv32_hwspinlock"
    line_is(T, H, 41, "if (rstn_i = '0') then")
    line_is(T, H, 42, "lock_q(i) <= '0';")
    line_is(T, H, 43, "elsif rising_edge(clk_i) then")
    line_is(T, H, 45, "lock_q(i) <= not bus_req_i.rw;")
    MH = _model(T, H)
    chk(role(T, H, "lock_q") == "input-written register" and (H, "lock_q") in MH["resets"],
        "hwspinlock: lock_q is an input-written register (written from bus_req_i.rw, line 45) with a reset record (line 42)")
    chk((H, "lock_q") not in MH["from_write_data"], "hwspinlock: lock_q is written from another input (bus_req_i.rw, line 45)")
    line_is(T, H, 70, "bus_rsp_o.data <= lock_q;")
    chk("bus_rsp_o.data" in [x[1] for x in MH["reaches"][(H, "lock_q")]], "hwspinlock: lock_q reaches bus_rsp_o.data (line 70)")
    line_is(T, H, 44, "if (bus_req_i.stb = '1') and (bus_req_i.addr(7) = '0') and (sel(i) = '1') then")
    line_is(T, H, 51, "sel(i) <= '1' when (bus_req_i.addr(6 downto 2) = std_ulogic_vector(to_unsigned(i, 5))) else '0';")
    chk(role(T, H, "sel") == "combinational decision", "hwspinlock: sel (concurrent, line 51) is a combinational decision (condition, line 44)")

    # --- neorv32_bus (tuning): a field stored through its whole record; a name in two entities ---
    B, BE = "neorv32_bus", "neorv32_bus_amo_rmw"
    line_is(T, B, 755, "arbiter_sync: process(rstn_i, clk_i)")
    line_is(T, B, 758, "arbiter.state <= S_IDLE;")
    line_is(T, B, 762, "elsif rising_edge(clk_i) then")
    line_is(T, B, 763, "arbiter <= arbiter_nxt;")
    MB = _model(T, B)
    chk(MB["storage"].get((BE, "arbiter.state")) == "edge" and (BE, "arbiter.state") in MB["regs"] and (BE, "arbiter.state") in MB["resets"],
        "bus: arbiter.state is a register through `arbiter <= arbiter_nxt` (line 763), reset at line 758")
    line_is(T, B, 773, "case arbiter.state is")
    line_is(T, B, 815, "sys_req_o.stb <= '1' when (arbiter.state = S_WRITE) else core_req_i.stb;")
    chk(len(MB["hub"].get((BE, "arbiter.state"), ())) >= HUB_MIN,
        "bus: arbiter.state is a control hub (case at line 773, when-conditions at lines 813-828)")
    line_is(T, B, 17, "entity neorv32_bus_switch is")
    line_is(T, B, 38, "signal state, state_nxt : state_t;")
    line_is(T, B, 878, "entity neorv32_bus_amo_rvs is")
    line_is(T, B, 894, "signal state : std_ulogic_vector(1 downto 0);")
    S1, S2 = ("neorv32_bus_amo_rvs", "state"), ("neorv32_bus_switch", "state")
    chk(match_element(T, B, "state") == S1 and match_element(T, B, "state", exclude={S1}) == S2
        and match_element(T, B, "state", exclude={S1, S2}) == S1 and match_element(T, B, "state", "neorv32_bus_switch", exclude={S2}) == S2,
        "bus: 'state' is declared in neorv32_bus_amo_rvs (line 894) and neorv32_bus_switch (line 38); without an entity "
        "the second use goes to the second, both used falls back to the first, a listed entity wins")
    ref_bus = [(T, B, "", n) for n, _o in _mods()["gt"][B]]
    got = [k for x, k in zip(ref_bus, resolve(ref_bus)) if x[3] == "state"]
    chk(got == [S1, S2], f"bus: the reference lists 'state' twice; resolve() gives the two entities' elements (got {got})")

    # --- neorv32_debug_dm (held-out): an authentication write guard ---
    Hd, D = "heldout", "neorv32_debug_dm"
    line_is(Hd, D, 212, "dmi_wren_auth <= dmi_wren when (not AUTHENTICATOR) or (auth.valid = '1') else '0';")
    line_is(Hd, D, 425, "if (dmi_wren_auth = '1') then")
    line_is(Hd, D, 426, "dm_reg.halt_req <= dmi_req_i.data(31);")
    line_is(Hd, D, 429, "dm_reg.hartsel <= dmi_req_i.data(18 downto 16);")
    line_is(Hd, D, 430, "dm_reg.dmcontrol_ndmreset <= dmi_req_i.data(1);")
    line_is(Hd, D, 432, "if (dmi_wren = '1') then")
    line_is(Hd, D, 433, "dm_reg.dmcontrol_dmactive <= dmi_req_i.data(0);")
    gd = [x for x in guards(Hd, D) if x["guard"] == "dmi_wren_auth"]
    at425 = next((x for x in gd if x["line"] == 425), None)
    chk(at425 is not None and {"dm_reg.halt_req", "dm_reg.hartsel", "dm_reg.dmcontrol_ndmreset"} <= set(at425["protects"]),
        "debug_dm: dmi_wren_auth (line 425) protects dm_reg.halt_req, dm_reg.hartsel, dm_reg.dmcontrol_ndmreset (lines 426-430)")
    chk(gd and all("dm_reg.dmcontrol_dmactive" not in x["protects"] for x in gd),
        "debug_dm: dm_reg.dmcontrol_dmactive (line 433) is under dmi_wren (line 432), not under dmi_wren_auth")
    chk(role(Hd, D, "dmi_wren_auth") == "combinational decision" and gd and gd[0]["guard_role"] == "combinational decision",
        "debug_dm: dmi_wren_auth is combinational (concurrent, line 212), a decision signal")
    MDd = _model(Hd, D)
    chk(MDd["write_data"].get((D, "dmi_req_i.data")) == "a" and MDd["port_type"].get((D, "dmi_req_i.data")) == "dmi_req_t"
        and (D, "dm_reg.halt_req") in MDd["from_write_data"],
        "debug_dm: dmi_req_i.data (dmi_req_t) is a write-data port by rule (a); dm_reg.halt_req (line 426) is written from it")

    # --- neorv32_gpio (held-out) ---
    G = "neorv32_gpio"
    line_is(Hd, G, 64, "elsif rising_edge(clk_i) then")
    line_is(Hd, G, 74, "when addr_out_c => port_out <= bus_req_i.data(GPIO_NUM-1 downto 0);")
    line_is(Hd, G, 112, "gpio_o(GPIO_NUM-1 downto 0) <= port_out;")
    MG = _model(Hd, G)
    chk(role(Hd, G, "port_out") == "input-written register" and "gpio_o" in [x[1] for x in MG["reaches"][(G, "port_out")]]
        and (G, "port_out") in MG["from_write_data"],
        "gpio: port_out is an input-written register from write data (line 74) that reaches output gpio_o (line 112)")
    line_is(Hd, G, 103, "port_in <= gpio_i(GPIO_NUM-1 downto 0);")
    chk(role(Hd, G, "port_in") == "input-written register" and (G, "port_in") not in MG["from_write_data"],
        "gpio: port_in (sampled from gpio_i, line 103) is an input-written register from another input, as documented")

    # --- neorv32_dmem (held-out): "mixed" storage counts as stored; a RAM written from the bus ---
    DM = "neorv32_dmem"
    line_is(Hd, DM, 81, "addr_ff <= (others => '0');")
    line_is(Hd, DM, 88, "if rising_edge(clk_i) then")
    line_is(Hd, DM, 89, "addr_ff <= addr;")
    line_is(Hd, DM, 92, "mem_ram_b0(to_integer(addr)) <= bus_req_i.data(7 downto 0);")
    MD = _model(Hd, DM)
    chk(MD["storage"].get((DM, "addr_ff")) == "mixed" and (DM, "addr_ff") in MD["regs"],
        "dmem: addr_ff is 'mixed' (line 81 concurrent in one generate branch, line 89 clocked in the other) and counts as a register")
    chk(role(Hd, DM, "mem_ram_b0") == "input-written register" and (DM, "mem_ram_b0") in MD["from_write_data"],
        "dmem: mem_ram_b0 (RAM written from bus_req_i.data, line 92) counts as written from write data, as documented")

    # --- neorv32_twi (tuning): an input-written bit with no reset ---
    line_is(T, "neorv32_twi", 122, "if (rstn_i = '0') then")
    line_is(T, "neorv32_twi", 124, "ctrl.enable <= '0';")
    line_is(T, "neorv32_twi", 126, "ctrl.cdiv <= (others => '0');")
    line_is(T, "neorv32_twi", 127, "elsif rising_edge(clk_i) then")
    line_is(T, "neorv32_twi", 139, "ctrl.clkstr <= bus_req_i.data(ctrl_clkstr_en_c);")
    MT = _model(T, "neorv32_twi")
    chk(("neorv32_twi", "ctrl.clkstr") in MT["regs"] and ("neorv32_twi", "ctrl.clkstr") not in MT["resets"]
        and ("neorv32_twi", "ctrl.enable") in MT["resets"],
        "twi: ctrl.clkstr (written at line 139) has no reset arm (lines 122-126 reset enable, prsc, cdiv only); ctrl.enable has")
    # --- neorv32_cpu_control (held-out): the documented gap of the reset count ---
    line_is(Hd, "neorv32_cpu_control", 266, "if (rstn_i = '0') then")
    line_is(Hd, "neorv32_cpu_control", 271, 'exe_engine.pc <= BOOT_ADDR(XLEN-1 downto 2) & "00";')
    line_is(Hd, "neorv32_cpu_control", 276, "exe_engine <= exe_engine_nxt;")
    MC = _model(Hd, "neorv32_cpu_control")
    chk((("neorv32_cpu_control", "exe_engine.pc") in MC["regs"]) and ("neorv32_cpu_control", "exe_engine.pc") not in MC["resets"],
        "cpu_control: exe_engine.pc is a register (line 276) reset at line 271, but the map has no RESET_BY for it "
        "(documented: the reset count is an upper bound)")

    # --- consistency with the flow graphs, coverage of the site rule, record parents ---
    fl = [m for s in ("tuning", "heldout") for m in _mods()[s]
          if (_model(s, m)["flow"] or {}).get("elements") != len({n for _e, n in _model(s, m)["els"]})]
    chk(not fl, f"flow graph element count = distinct element names of the map, 41 modules ({len(fl)} differ)")
    nos = sum(_model(s, m)["no_site_gates"] for s in ("tuning", "heldout") for m in _mods()[s])
    chk(nos == 0, f"every GATES occurrence has a condition or an operand SITE tag ({nos} without)")
    pc = sum(1 for s in ("tuning", "heldout") for m in _mods()[s] for k in _model(s, m)["parents"]
             if any(r.get("type") in ("GATES", "SELECTS", "CONSTRAINS", "SEQUENCES")
                    for r in _model(s, m)["els"][k]["e"].get("relationship", []) or []))
    chk(pc == 0, f"no record parent has a GATES, SELECTS, CONSTRAINS or SEQUENCES record, 41 modules ({pc} have): "
        "hubs, write guards and clocks are leaves (portrait docstring)")
    log(f"module_insights selftest: {'PASS' if ok else 'FAIL'} ({n_chk - n_fail} of {n_chk} checks passed)")
    return ok


# ------------------------------------------------------------------------------------------------ main ---
def _where(p: Path) -> str:
    """p relative to the repo root when it is inside it, else the absolute path."""
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p.resolve())


def main(log=print) -> dict:
    """Self-test, then every table for the 41 modules, written under OUT (map_pipeline/module_insights/ by default; any folder
    works). Reports nothing if the self-test fails."""
    import pandas as pd
    if not selftest(log=lambda *a: None):
        selftest(log)
        log("SELF-TEST FAILED: nothing written, nothing reported")
        return {"selftest": False}
    ns, mods = _ns(), _mods()
    OUT.mkdir(parents=True, exist_ok=True)
    P = portraits(mods)
    G = pd.DataFrame([x for s in ("tuning", "heldout") for m in mods[s] for x in guards(s, m)])
    R = all_roles(mods)
    lists, status = default_lists(ns, mods)
    E = role_enrichment(ns, mods, lists)
    D = deep_dive()
    P.to_csv(OUT / "portraits.csv", index=False)
    G.to_csv(OUT / "guards.csv", index=False)
    R.to_csv(OUT / "roles.csv", index=False)
    E.to_csv(OUT / "role_enrichment.csv")
    (OUT / "deep_dive_neorv32_wdt.json").write_text(json.dumps(D, indent=1), encoding="utf-8")

    regs, iw = int(P["registers"].sum()), int(P["input_written_registers"].sum())
    iw_wd, iw_oth = int(P["input_written_from_write_data"].sum()), int(P["input_written_from_other_input"].sum())
    by_rule, both = Counter(), 0
    no_rec, no_ctl = [], 0              # no GATED_BY / SELECTED_BY record from an input port; same, control records only
    for s in ("tuning", "heldout"):
        for m in mods[s]:
            M = _model(s, m)
            for k in M["input_written"]:
                srcs = M["written_from"][k]
                by_rule.update({M["write_data"][y] for y in srcs if y in M["write_data"]})
                both += any(y in M["write_data"] for y in srcs) and any(y not in M["write_data"] for y in srcs)
                if not any(r.get("type") in ("GATED_BY", "SELECTED_BY") and (k[0], t) in M["is_in"]
                           for r in M["els"][k]["e"].get("relationship", []) or [] for t in r.get("targets", [])):
                    no_rec.append((m.replace("neorv32_", ""), k[1], k in M["from_write_data"], [y[1] for y in srcs]))
                if not any(k in M["hub"].get(y, ()) for y in M["is_in"]):
                    no_ctl += 1
    nr_wd = [x for x in no_rec if x[2]]
    gi = P[P["write_guards_internal"] > 0]
    summary = {
        "modules": f"{len(P)} (tuning {len(mods['tuning'])}, held-out {len(mods['heldout'])})",
        "elements": int(P["elements"].sum()), "occurrences": int(P["occurrences"].sum()),
        "records (both sides)": int(P["records"].sum()),
        "records data / control / timing": f"{int(P['records_data'].sum())} / {int(P['records_control'].sum())} / {int(P['records_timing'].sum())}",
        "registers": regs,
        "input-written registers": f"{iw}/{regs}",
        "  from a write-data port (bus or CSR write data)": f"{iw_wd}/{iw} (registers with a source matched by rule (a), "
            f"request-record data field: {by_rule['a']}; by rule (b), wdata name: {by_rule['b']}; "
            f"with both a write-data and another input source: {both})",
        "  from another input only": f"{iw_oth}/{iw}",
        "  with no GATED_BY or SELECTED_BY record naming an input port (GATES at any site)":
            f"{len(no_rec)}/{iw}: {len(nr_wd)} from a write-data port ("
            + ", ".join(f"{x[0]} {x[1]}" for x in nr_wd) + f"), {len(no_rec) - len(nr_wd)} from another input only",
        "  same, counting only control records (GATES at a condition site, or SELECTS) from an input port": f"{no_ctl}/{iw}",
        "  no GATED_BY / SELECTED_BY from an input port, registers from another input (module register <- inputs)":
            [f"{x[0]} {x[1]} <- {', '.join(x[3])}" for x in no_rec if not x[2]],
        "exported registers": f"{int(P['exported_registers'].sum())}/{regs}",
        "registers without a reset record": f"{regs - int(P['registers_with_reset'].sum())}/{regs}",
        "control hubs": int(P["control_hubs"].sum()),
        "modules with a write guard (any)": f"{int((P['write_guards'] > 0).sum())}/{len(P)}",
        "modules with an internal write guard": f"{len(gi)}/{len(P)}: " + ", ".join(
            f"{r.module.replace('neorv32_', '')} ({', '.join(sorted({x['guard'] for s in (r.split,) for x in guards(s, r.module) if x['guard_role'] not in ('input port', 'output port')}))})"
            for r in gi.itertuples()),
        "sub-unit connections": int(P["subunit_connections"].sum()),
        "run status": status,
        "enrichment denominators": E.attrs["denominators"],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    log("== module_insights: 41 modules, code-built maps only")
    for k, v in summary.items():
        if k == "enrichment denominators":
            continue
        log(f"  {k}: " + (f"{len(v)} listed in summary.json" if isinstance(v, list) else f"{v}"))
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        cols = ["module", "split", "elements", "occurrences", "records", "registers", "input_written_registers",
                "input_written_from_write_data", "exported_registers", "no_reset_share", "clocks", "control_hubs",
                "write_guards", "write_guards_internal", "subunit_connections", "reference_entries"]
        log("\n== portraits (selected columns; all columns in portraits.csv)")
        log(P[cols].assign(module=P["module"].str.replace("neorv32_", "")).rename(
            columns={"input_written_registers": "input_written", "input_written_from_write_data": "iw_write_data"}).to_string(index=False))
        log("\n== role enrichment (share = n / matched entries; P = precision inside the role, strict labels)")
        log(E.to_string())
        log("  denominators: " + json.dumps(E.attrs["denominators"]))
        log("\n== deep dive neorv32_wdt")
        for x in D["write_guards"]:
            log(f"  guard {x['guard']} line {x['line']} `{x['rtl']}` protects {x['protects']} gates_itself={x['gates_itself']} listed={x['listed']}")
        for x in D["input_written_registers"]:
            log(f"  input-written {x['register']} from {x['written_from']} (write data: {x['from_write_data']}) lines {x['write_lines']} "
                f"reaches {x['reaches_outputs']} guarded_by {x['guarded_by']} listed={x['listed']}")
        for x in D["outputs"]:
            if x["registers"]:
                log(f"  output {x['output']} <- {x['registers']} (listed: {x['registers_listed']})")
        for x in D["control_hubs"]:
            log(f"  hub {x['element']} ({x['role']}) {x['control_targets']} targets listed={x['listed']}")
        log(f"  reference: {[(c['reference entry'], c['role']) for c in D['reference']]}")
    log(f"\nwritten: {', '.join(sorted(p.name for p in OUT.iterdir()))} under {_where(OUT)}")
    return {"selftest": True, "summary": summary, "portraits": P, "guards": G, "roles": R, "enrichment": E, "deep_dive": D}


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)
    main()
