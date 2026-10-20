"""PIO track, step 4 and the code step of step 5: the flow graph written as a block diagram.

P3164 section 4 (p19-21) needs an architectural block diagram at two zoom levels: the IP reduced to its inputs and
outputs (their Fig. 7), then the detailed blocks where the conceptual assets can be observed or influenced (Fig. 8).
The RTL comes with no diagram, so both views are written from the flow graph of pio_graph.py:

  interface_text(m)        zoomed out: each root entity's inputs and outputs, which input reaches which output
                           (E = its value moves there, I = only through decisions), clock/reset inputs, contained
                           entities and the other IPs it instantiates. Input to call A (conceptual assets).
  points(m, concept)       zoomed in, computed by code from the concept call A returned (its entry and exit ports):
                             carriers  elements the concept's value moves through: explicit-only paths from its entry
                                       ports and to its exit ports (Hu et al. 2021 sec. 2.4.1)
                             deciders  elements with an implicit edge into a carrier: they decide whether, which or how
                                       a carrier is assigned (sec. 2.4.2)
  points_text(m, concepts) the points with their facts, per concept. Input to call C (the four PIO questions).
  rtl_text(m)              the numbered, comment-free RTL every earlier arm used (final/record_scope/all_three_fixes).
"""
from __future__ import annotations

import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import pio_graph as G  # noqa: E402


# ------------------------------------------------------------------------------------------------ helpers ---
def rtl_text(m) -> str:
    p = G.FIX / "traced_inputs" / G.split_of(m) / f"{m}.txt"
    if not p.exists():                     # boot_rom and fifo: no reference entries, so no fixed traced input
        p = G.ROOT / "assetgen_meta/traced_inputs_v2" / G.split_of(m) / f"{m}.txt"
    t = p.read_text(encoding="utf-8")
    a = t.index("=== RTL")
    a = t.index("\n", a) + 1
    b = t.index("=== RELATIONSHIP MAP")
    return t[a:b].rstrip()


@lru_cache(maxsize=None)
def _multi(m) -> bool:
    return len(G.step1_closed_set(m)["entities"]) > 1


def show(m, node: str) -> str:
    """Element name as call A/C read and write it: bare in a one-entity file, '<entity>:<name>' otherwise."""
    return node if _multi(m) else node.split(":", 1)[1]


def group(m, nodes) -> str:
    """Names with record fields folded: bus_rsp_o.{ack,data,err}."""
    by = defaultdict(list)
    for n in sorted(nodes):
        s = show(m, n)
        base, _, field = s.rpartition(".") if "." in s.split(":")[-1] else (s, "", "")
        by[base].append(field)
    out = []
    for base, fs in sorted(by.items()):
        fs = [f for f in fs if f]
        if not fs:
            out.append(base)
        elif len(fs) == 1:
            out.append(f"{base}.{fs[0]}")
        else:
            out.append(f"{base}.{{{','.join(fs)}}}")
    return ", ".join(out)


def _kind(f: dict) -> str:
    if f["top_level"]:
        return "input port" if f["dir"] in G.IN_DIRS else "output port"
    if f["dir"]:
        return "port of a contained entity"
    return "stored" if f["stored"] else "combinational"


def _clock_reset_only(m) -> dict:
    """{top-level input node: 'clock'|'reset'|'clock and reset'} for inputs whose every edge is clock or reset."""
    g = G.file_graph(m)
    kinds = defaultdict(set)
    for e in g["edges"]:
        kinds[e["src"]].add(e["kind"] if e["via"] != "PORT_MAP" else "port map")
    out = {}
    for n, e in g["closed_set"]["elements"].items():
        if e["top_level"] and e["dir"] in G.IN_DIRS and kinds.get(n) and kinds[n] <= {"clock", "reset", "port map"} \
                and kinds[n] & {"clock", "reset"}:
            out[n] = " and ".join(sorted(kinds[n] & {"clock", "reset"}))
    return out


# --------------------------------------------------------------------------------------- zoomed out (call A) ---
def interface_text(m) -> str:
    g, f = G.file_graph(m), G.node_facts(m)
    els, h = g["closed_set"]["elements"], g["hierarchy"]
    cr = _clock_reset_only(m)
    lines = []
    for r in h["roots"]:
        lines.append(f"UNIT {r}")
        inside = [i for i in h["instances"] if i["same_file"]]
        if inside:
            for i in inside:
                lines.append(f"  contains: instance {i['label']} of {i['child']} (declared in this file, inside {i['parent']}; "
                             f"its elements appear as {i['child']}:<name>)")
        for i in h["instances"]:
            if not i["same_file"] and i["parent"] in ({r} | {x["child"] for x in inside}):
                st = any(e.get("through_storage") for e in g["edges"] if e.get("instance") == i["label"])
                lines.append(f"  uses another IP: instance {i['label']} of {i['child']} (declared elsewhere; only its ports "
                             f"are visible here; a value passes through storage inside it: {'yes' if st else 'no'})")
        ports = [n for n, e in els.items() if e["entity"] == r and e["dir"]]
        for d, label in ((G.IN_DIRS, "INPUTS"), (G.OUT_DIRS, "OUTPUTS")):
            lines.append(f"  {label}")
            for n in ports:
                e = els[n]
                if e["dir"] not in d or e["field_of"]:
                    continue
                fields = sorted(x["name"].rsplit(".", 1)[1] for x in els.values()
                                if x["entity"] == r and x["field_of"] == e["name"])
                tag = f"   [{cr[n]} only]" if n in cr else ""
                lines.append(f"    {show(m, n)} : {e['type']}" + (f"   fields: {', '.join(fields)}" if fields else "") + tag)
        lines.append("  INTERFACE FLOWS (input -> the outputs it reaches; E = its value moves there by explicit flows, "
                     "I = it reaches there only through decisions)")
        for n in ports:
            e = els[n]
            if e["dir"] not in G.IN_DIRS or e["record"] or n in cr:
                continue
            reach = _out_reach(m, n)
            reach_e = sorted(o for o, k in reach.items() if k == "explicit")
            reach_i = sorted(o for o, k in reach.items() if k == "implicit")
            if not reach_e and not reach_i:
                lines.append(f"    {show(m, n)} -> (no output)")
                continue
            parts = []
            if reach_e:
                parts.append("E: " + group(m, reach_e))
            if reach_i:
                parts.append("I: " + group(m, reach_i))
            lines.append(f"    {show(m, n)} -> " + " | ".join(parts))
        lines.append("")
    return "\n".join(lines).rstrip()


def _out_reach(m, src) -> dict:
    """{top-level output node: 'explicit'|'implicit'} reached from the top-level input `src`."""
    return {o: f["from_inputs"][src] for o, f in G.node_facts(m).items()
            if f["top_level"] and f["dir"] in G.OUT_DIRS and src in f["from_inputs"]}


# -------------------------------------------------------------------------------- zoomed in (code step B) ---
def resolve_ports(m, names) -> tuple[list[str], list[str]]:
    """Port names as call A wrote them -> top-level port nodes (a whole record expands to its fields).
    -> (nodes, names not found)"""
    els = G.file_graph(m)["closed_set"]["elements"]
    by_show = {show(m, n): n for n in els}
    by_bare = defaultdict(list)
    for n, e in els.items():
        by_bare[e["name"]].append(n)
    nodes, missing = [], []
    for x in names or []:
        cand = [by_show[x]] if x in by_show else by_bare.get(x, [])
        cand = [n for n in cand if els[n]["top_level"]]
        if not cand:
            missing.append(x)
            continue
        for n in cand:
            nodes.append(n)
            nodes += [k for k, e in els.items() if e["entity"] == els[n]["entity"] and e["field_of"] == els[n]["name"]]
    return sorted(set(nodes)), missing


def points(m, entries, exits) -> dict:
    """Carriers and deciders of one concept, from its entry and exit port names."""
    g, f = G.file_graph(m), G.node_facts(m)
    els = g["closed_set"]["elements"]
    ein, miss_in = resolve_ports(m, entries)
    eout, miss_out = resolve_ports(m, exits)
    ex, rex = G._adj(g["edges"], ("explicit",)), G._adj(g["edges"], ("explicit",), True)
    carriers = set(ein) | set(eout)
    for s in ein:
        carriers |= G._reach(ex, s)
    for s in eout:
        carriers |= G._reach(rex, s)
    carriers = {n for n in carriers if not els[n]["record"]}
    deciders = {e["src"] for c in carriers for e in _index(m)[1].get(c, []) if e["kind"] == "implicit"} - carriers
    deciders = {n for n in deciders if not els[n]["record"]}
    return {"entries": ein, "exits": eout, "missing": miss_in + miss_out,
            "carriers": sorted(carriers), "deciders": sorted(deciders)}


from functools import lru_cache  # noqa: E402


@lru_cache(maxsize=None)
def _index(m):
    """Edges of one file by source and by target."""
    out_e, in_e = defaultdict(list), defaultdict(list)
    for e in G.file_graph(m)["edges"]:
        out_e[e["src"]].append(e)
        in_e[e["dst"]].append(e)
    return out_e, in_e


def _edge_lines(m, a, b, kind, via_sub=False) -> list[int]:
    return sorted({ln for e in _index(m)[0].get(a, []) if e["dst"] == b and e["kind"] == kind
                   and (e["via"] == "SUB_BLOCK") == via_sub for ln in e["lines"]})


def point_facts(m, p: dict, node: str) -> dict:
    """What call C reads about one point, all computed from the graph. Edges inside this file are listed one by one;
    edges that pass through another IP are grouped by its instance."""
    f = G.node_facts(m)
    x = f[node]
    members = set(p["carriers"]) | set(p["deciders"])
    carriers = set(p["carriers"])
    out_e, in_e = _index(m)
    o_dir = [e for e in out_e.get(node, []) if e["via"] != "SUB_BLOCK"]
    i_dir = [e for e in in_e.get(node, []) if e["via"] != "SUB_BLOCK"]
    val_from = sorted({e["src"] for e in i_dir if e["kind"] == "explicit" and e["src"] in members})
    val_to = sorted({e["dst"] for e in o_dir if e["kind"] == "explicit" and e["dst"] in members})
    dec_by = sorted({e["src"] for e in i_dir if e["kind"] == "implicit"})
    decides = sorted({e["dst"] for e in o_dir if e["kind"] == "implicit" and e["dst"] in carriers})
    into, outof = defaultdict(lambda: defaultdict(set)), defaultdict(lambda: defaultdict(set))
    for e in out_e.get(node, []):
        if e["via"] == "SUB_BLOCK" and e["dst"] in members:
            into[e["instance"]][e["kind"]].add(e["dst"])
    for e in in_e.get(node, []):
        if e["via"] == "SUB_BLOCK" and e["src"] in members:
            outof[e["instance"]][e["kind"]].add(e["src"])
    other_in = {s: k for s, k in x["from_inputs"].items() if s not in p["entries"]}
    return {"node": node, "role": "carrier" if node in p["carriers"] else "decider", "kind": _kind(x),
            "value from": [(s, _edge_lines(m, s, node, "explicit")) for s in val_from],
            "value to": [(t, _edge_lines(m, node, t, "explicit")) for t in val_to],
            "decided by": [(s, _edge_lines(m, s, node, "implicit")) for s in dec_by],
            "decides": [(t, _edge_lines(m, node, t, "implicit")) for t in decides],
            "through another IP, to": {i: {k: sorted(v) for k, v in d.items()} for i, d in into.items()},
            "through another IP, from": {i: {k: sorted(v) for k, v in d.items()} for i, d in outof.items()},
            "other inputs reaching it": other_in, "outputs it reaches": dict(x["to_outputs"]),
            "clock": x["clock"], "reset": x["reset"]}


CAP = 8


def _pairs(m, xs, cap=CAP) -> str:
    s = [f"{show(m, n)}@{','.join(map(str, ls)) or '-'}" for n, ls in xs[:cap]]
    return ", ".join(s) + (f", and {len(xs) - cap} more" if len(xs) > cap else "")


def _capped_group(m, nodes, cap=CAP) -> str:
    nodes = sorted(nodes)
    txt = group(m, nodes[:cap])
    return txt + (f", and {len(nodes) - cap} more" if len(nodes) > cap else "")


def _reach_str(m, d: dict) -> str:
    e = [n for n, k in d.items() if k == "explicit"]
    i = [n for n, k in d.items() if k == "implicit"]
    parts = ([f"E: {_capped_group(m, e)}"] if e else []) + ([f"I: {_capped_group(m, i)}"] if i else [])
    return " | ".join(parts) or "none"


def _sub_str(m, d: dict) -> str:
    return "; ".join(f"{inst} ({_reach_str(m, {n: k for k, ns in kinds.items() for n in ns})})" for inst, kinds in sorted(d.items()))


def points_text(m, concepts: list[dict]) -> tuple[str, dict]:
    """-> (text for call C, {concept id: points dict}). A concept with no resolvable port gets no points."""
    out, pts = [], {}
    for c in concepts:
        cid = c.get("id", "?")
        p = points(m, c.get("enters through", []), c.get("leaves through", []))
        pts[cid] = p
        out.append(f"CONCEPT {cid}: {c.get('concept', '')}")
        out.append(f"  enters through: {group(m, p['entries']) or 'none'}")
        out.append(f"  leaves through: {group(m, p['exits']) or 'none'}")
        if p["missing"]:
            out.append(f"  port names not found in this file (ignored): {', '.join(p['missing'])}")
        for role, key in (("CARRIERS (the concept's value moves through them by explicit flows)", "carriers"),
                          ("DECIDERS (they decide whether, which or how a carrier is assigned)", "deciders")):
            out.append(f"  {role}")
            if not p[key]:
                out.append("    none")
            for n in p[key]:
                q = point_facts(m, p, n)
                out.append(f"    {show(m, n)}   [{q['kind']}]")
                for k in ("value from", "value to", "decided by", "decides"):
                    if q[k]:
                        out.append(f"      {k}: {_pairs(m, q[k])}")
                for k in ("through another IP, from", "through another IP, to"):
                    if q[k]:
                        out.append(f"      {k}: {_sub_str(m, q[k])}")
                if q["other inputs reaching it"]:
                    out.append(f"      other inputs reaching it: {_reach_str(m, q['other inputs reaching it'])}")
                out.append(f"      outputs it reaches: {_reach_str(m, q['outputs it reaches'])}")
                if q["reset"]:
                    out.append(f"      reset by: {group(m, q['reset'])}")
        out.append("")
    return "\n".join(out).rstrip(), pts


# ------------------------------------------------------------------------------------------------ self-tests ---
def selftest(log=print) -> bool:
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        log(f"   {'ok  ' if cond else 'FAIL'} {label}")

    t = interface_text("neorv32_wdt")
    check("wdt interface lists bus_req_i with its fields and bus_rsp_o as an output", "bus_req_i : bus_req_t   fields:" in t
          and "    bus_rsp_o : bus_rsp_t" in t)
    check("wdt interface: clk_i marked clock only", "clk_i : std_ulogic   [clock only]" in t)
    # hand-read wdt 94 (bus_req_i.data -> ctrl.enable) and 109 (ctrl.enable -> bus_rsp_o.data): the value of
    # bus_req_i.data reaches bus_rsp_o.data by an explicit path
    check("wdt interface flow: bus_req_i.data -> E includes bus_rsp_o.data",
          any(l.strip().startswith("bus_req_i.data -> E:") and "bus_rsp_o.data" in l.split("|")[0] for l in t.split("\n")))
    p = points("neorv32_wdt", ["bus_req_i.data"], [])
    check("wdt concept entering at bus_req_i.data: ctrl.enable is a carrier (94), ctrl.lock decides it (93)",
          "neorv32_wdt:ctrl.enable" in p["carriers"] and "neorv32_wdt:ctrl.lock" in p["carriers"] + p["deciders"])
    q = point_facts("neorv32_wdt", p, "neorv32_wdt:ctrl.enable")
    check("wdt ctrl.enable point: value from bus_req_i.data at line 94; decided by ctrl.lock at line 93",
          ("neorv32_wdt:bus_req_i.data", [94]) in q["value from"] and ("neorv32_wdt:ctrl.lock", [93]) in q["decided by"])
    pw, _ = resolve_ports("neorv32_wdt", ["bus_req_i"])
    check("a whole record port name expands to its fields", "neorv32_wdt:bus_req_i.data" in pw and len(pw) > 2)
    tb = interface_text("neorv32_bus")
    check("bus: five units, names qualified by entity", tb.count("UNIT ") == 5 and "neorv32_bus_switch:" in tb)
    ts = interface_text("neorv32_spi")
    check("spi: the two FIFOs are listed as other IPs with storage", ts.count("uses another IP") == 2
          and "of neorv32_fifo (declared elsewhere" in ts and "storage inside it: yes" in ts)
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    assert selftest(), "self-test failed"
    print(interface_text(sys.argv[1] if len(sys.argv) > 1 else "neorv32_wdt"))
