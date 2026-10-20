"""PIO track, steps 1-3 (code only, no model): closed set N, module hierarchy, flow graph.

  Step 1  closed set N    every port (with its direction), signal and record field of a file, from the fixed closed sets
                          (final/branch_label/all_four_fixes). The top-level inputs and outputs are the ports of the
                          file's root entities: the entities no other entity of the same file instantiates.
  Step 2  hierarchy       every instance in the file: label, parent entity, child entity, the file that declares the
                          child, and whether that file is this one.
  Step 3  flow graph      nodes = elements of N, written "<entity>:<name>". Edges come from the code-built relationship
                          map of the same version (step1/code_pairs_v2.py, frozen b0e767000ec2, plus the three map fixes):
                            explicit  the value moves into the target (Hu et al. 2021, sec. 2.4.1): CARRIES, SOURCES, and
                                      GATES where the record's occurrence is an operand of the assignment
                            implicit  the value decides whether, which or how the target is assigned (sec. 2.4.2): GATES
                                      where the record's occurrence is a condition, CONSTRAINS, SELECTS
                            clock     SEQUENCES (kept apart: a timing relation, not a value flow)
                            reset     RESETS (kept apart: forces a fixed value)
                          A port-map association is an explicit edge between the actual and the child port. A child
                          declared in this file is part of the graph. A child declared in another file is a separate IP:
                          its internal elements are not nodes here; each of its input ports is linked to each output
                          port it reaches inside the child (computed from the child's own graph), labelled explicit when
                          an explicit-only path exists, else implicit.
  Per node, for the root entity it belongs to: the top-level inputs that reach it and the top-level outputs it reaches,
  each labelled explicit (an explicit-only path exists) or implicit (only paths through a decision).

  Output: src/pio_diagram/graph/<split>/<module>.json
Run:  python src/pio_diagram/pio_graph.py            (self-tests first; nothing is written if one fails)
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
ROOT = HERE.parents[1]
FIX = ROOT / "final/branch_label/all_four_fixes"     # all_three_fixes + the branch_check context fix
GRAPH_VERSION = "g2"     # g1: all_three_fixes, no flowfix (PIO run 0, audit a1); g2: this map + pio_flowfix
RTL = {"tuning": ROOT / "data/RTL_data", "heldout": ROOT / "data/RTL_heldout"}
OUT = HERE / "graph"

FLOW_TYPES = {"CARRIES": "explicit", "SOURCES": "explicit", "CONSTRAINS": "implicit", "SELECTS": "implicit",
              "SEQUENCES": "clock", "RESETS": "reset"}            # GATES: by the SITE at the record's occurrence
COND_SITES = {"IF_COND", "WHEN_COND", "CASE_EXPR", "EDGE_CHECK"}
FLOW = ("explicit", "implicit")
IN_DIRS, OUT_DIRS = ("in", "inout"), ("out", "inout", "buffer")


# ------------------------------------------------------------------------------------------------ inputs ---
def modules(split):
    return sorted(p.stem for p in RTL[split].glob("*.vhd"))


def split_of(m):
    return next(s for s in RTL if (RTL[s] / f"{m}.vhd").exists())


def _json(p):
    return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else None


@lru_cache(maxsize=None)
def closed_set(m):
    return _json(FIX / "closed_sets" / split_of(m) / f"{m}.json")


@lru_cache(maxsize=None)
def code_map(m):
    return _json(FIX / "maps" / split_of(m) / f"{m}.json")


@lru_cache(maxsize=None)
def sites(m):
    return _json(FIX / "maps" / split_of(m) / "_sites" / f"{m}.json") or {}


@lru_cache(maxsize=None)
def entity_file() -> dict:
    """{entity: module} over every file of both splits."""
    out = {}
    for s in RTL:
        for m in modules(s):
            for e in (closed_set(m) or {}).get("entities", []):
                out.setdefault(e, m)
    return out


@lru_cache(maxsize=None)
def port_dir() -> dict:
    """{(entity, port element): dir} over every file."""
    out = {}
    for s in RTL:
        for m in modules(s):
            for p in (closed_set(m) or {}).get("ports", []):
                out[(p["entity"], p["name"])] = p["dir"]
    return out


def _strip_comments(t: str) -> str:
    return re.sub(r"--[^\n]*", "", t)


@lru_cache(maxsize=None)
def instance_labels(m) -> dict:
    """{instance label: child entity} from the RTL: '<label>: entity [lib.]<entity>' and the component form
    '<label>: [component] <entity> generic map | port map'."""
    t = _strip_comments((RTL[split_of(m)] / f"{m}.vhd").read_text(encoding="utf-8", errors="ignore"))
    out = {a: b for a, b in re.findall(r"(\w+)\s*:\s*entity\s+(?:\w+\.)?(\w+)", t, re.I)}
    for a, b in re.findall(r"(\w+)\s*:\s*(?:component\s+)?(\w+)\s+(?:generic|port)\s+map\b", t, re.I):
        if b.lower() != "entity":
            out.setdefault(a, b)
    return out


# ------------------------------------------------------------------------------------ steps 1 and 2 ---
@lru_cache(maxsize=None)
def step1_closed_set(m) -> dict:
    """N with the top-level ports marked. -> {"entities", "roots", "elements": {node: {...}}}"""
    cs, hier = closed_set(m), step2_hierarchy(m)
    roots = set(hier["roots"])
    els = {}
    for p in cs.get("ports", []):
        els[f"{p['entity']}:{p['name']}"] = {"entity": p["entity"], "name": p["name"], "dir": p["dir"], "type": p.get("type"),
                                             "top_level": p["entity"] in roots}
    for s in cs.get("signals", []):
        els[f"{s['entity']}:{s['name']}"] = {"entity": s["entity"], "name": s["name"], "dir": None, "type": s.get("type"),
                                             "top_level": False}
    for e in els.values():
        e["field_of"] = e["name"].rsplit(".", 1)[0] if "." in e["name"] else None
    whole = {(e["entity"], e["field_of"]) for e in els.values() if e["field_of"]}
    for e in els.values():
        e["record"] = (e["entity"], e["name"]) in whole
    return {"entities": cs.get("entities", []), "roots": hier["roots"], "elements": els}


@lru_cache(maxsize=None)
def step2_hierarchy(m) -> dict:
    """Instances and root entities. The parent of an instance is the entity of the elements wired to it."""
    cs, mp = closed_set(m), code_map(m) or {"ports": [], "signals": []}
    labels, ef = instance_labels(m), entity_file()
    parent = {}
    for a in ("ports", "signals"):
        for e in mp.get(a, []):
            for c in e.get("connections", []) or []:
                parent.setdefault(c.get("instance"), e["entity"])
    insts = []
    for label, child in labels.items():
        insts.append({"label": label, "parent": parent.get(label), "child": child, "child_file": ef.get(child),
                      "same_file": child in cs.get("entities", [])})
    inside = {i["child"] for i in insts if i["same_file"]}
    roots = [e for e in cs.get("entities", []) if e not in inside]
    return {"module": m, "entities": cs.get("entities", []), "roots": roots, "instances": insts,
            "unknown_instances": sorted(set(parent) - set(labels))}


# -------------------------------------------------------------------------------------------- step 3 ---
def _gates_kinds(site_lists: list[list[str]]) -> set[str]:
    """A GATES record holds at one or more occurrences: implicit where the occurrence is a condition, else explicit."""
    return {("implicit" if set(s) & COND_SITES else "explicit") for s in site_lists} or {"implicit"}


@lru_cache(maxsize=None)
def file_graph(m) -> dict:
    import pio_flowfix as F
    """Nodes and edges of one file (same-file children inside, other-file children as summaries)."""
    n1, h = step1_closed_set(m), step2_hierarchy(m)
    mp, st = code_map(m) or {"ports": [], "signals": []}, sites(m)
    els = n1["elements"]
    inst = {i["label"]: i for i in h["instances"]}
    edges, unresolved = [], []
    occ_line = {}
    for a in ("ports", "signals"):
        for e in mp.get(a, []):
            occ_line[(e["entity"], e["name"])] = {o["id"]: o["line"] for o in e.get("occurrences", [])}

    def add(src, dst, kind, via, lines, **kw):
        edges.append({"src": src, "dst": dst, "kind": kind, "via": via, "lines": sorted(set(lines)), **kw})

    pending = defaultdict(lambda: {"in": [], "out": []})          # other-file instances: actual <-> child port
    for a in ("ports", "signals"):
        for e in mp.get(a, []):
            ent, y = e["entity"], e["name"]
            src = f"{ent}:{y}"
            lines_of = occ_line[(ent, y)]
            for r in e.get("relationship", []) or []:
                t = r["type"]
                if t not in FLOW_TYPES and t != "GATES":
                    continue                                     # receiving records mirror the driving ones
                ats = r.get("at") or []
                if t == "GATES":
                    by_kind = defaultdict(list)
                    for i in ats:
                        k = "implicit" if set(st.get(ent, {}).get(y, {}).get(str(i), [])) & COND_SITES else "explicit"
                        by_kind[k].append(i)
                    if not by_kind:
                        by_kind["implicit"] = []
                else:
                    by_kind = {FLOW_TYPES[t]: ats}
                for x in r.get("targets", []):
                    live = F.live_partners(m, ent, y, x, (r.get("partner_at") or {}).get(x, []))
                    if not live:
                        continue                                 # dead target, or built never with Y's producers
                    rl = [o for o in live if t == "GATES" and F.reset_like(m, ent, y, ats, x, o)]
                    if rl:                                       # a reset arm with a generic-valued assignment
                        add(src, f"{ent}:{x}", FLOW_TYPES["RESETS"], "RESETS", [lines_of[i] for i in ats if i in lines_of])
                    for k, ids in by_kind.items():
                        if k == "implicit" and len(rl) == len(live):
                            continue
                        add(src, f"{ent}:{x}", k, t, [lines_of[i] for i in ids if i in lines_of])
            for c in e.get("connections", []) or []:
                i = inst.get(c.get("instance"))
                if i is None:
                    unresolved.append((src, c.get("instance")))
                    continue
                child, formal = i["child"], c.get("formal")
                mode = c.get("mode") or port_dir().get((child, formal))
                ln = [lines_of[c["at"]]] if c.get("at") in lines_of else []
                # a whole record wired to a whole record: link the fields both sides declare
                pairs = [(y, formal)]
                fields = [n for (ee, n) in occ_line if ee == ent and n.startswith(y + ".")]
                for f in fields:
                    fo = formal + f[len(y):]
                    if (child, fo) in port_dir():
                        pairs.append((f, fo))
                for yy, ff in pairs:
                    a_node = f"{ent}:{yy}"
                    if i["same_file"]:
                        c_node = f"{child}:{ff}"
                        if mode in ("in", "inout", None):
                            add(a_node, c_node, "explicit", "PORT_MAP", ln, instance=i["label"])
                        if mode in ("out", "buffer", "inout", None):
                            add(c_node, a_node, "explicit", "PORT_MAP", ln, instance=i["label"])
                    else:
                        if mode in ("in", "inout", None):
                            pending[i["label"]]["in"].append((a_node, ff, ln))
                        if mode in ("out", "buffer", "inout", None):
                            pending[i["label"]]["out"].append((ff, a_node, ln))
    for ent, y, x, oid, lines in F.var_cond_flows(m):              # decisions through a process variable
        if F.live_partners(m, ent, y, x, [oid]):
            add(f"{ent}:{y}", f"{ent}:{x}", "implicit", "VAR_COND", list(lines))
    summaries = {}
    for label, io in pending.items():
        child = inst[label]["child"]
        sm = port_summary(child)
        summaries[label] = {"child": child, "child_file": inst[label]["child_file"], "pairs": len(sm)}
        for a_node, fi, l1 in io["in"]:
            for fo, z_node, l2 in io["out"]:
                k = sm.get((fi, fo))
                if k:
                    add(a_node, z_node, k["kind"], "SUB_BLOCK", l1 + l2, instance=label, child=child,
                        through_storage=k["through_storage"])
    nodes = set(els)
    stray = sorted({x for ed in edges for x in (ed["src"], ed["dst"]) if x not in nodes})
    return {"module": m, "hierarchy": h, "closed_set": n1, "edges": edges, "sub_blocks": summaries,
            "unresolved_connections": unresolved, "nodes_not_in_closed_set": stray}


def _adj(edges, kinds, reverse=False):
    g = defaultdict(set)
    for e in edges:
        if e["kind"] in kinds:
            a, b = (e["dst"], e["src"]) if reverse else (e["src"], e["dst"])
            g[a].add(b)
    return g


def _reach(g, start) -> set:
    seen, q = {start}, deque([start])
    while q:
        u = q.popleft()
        for v in g.get(u, ()):
            if v not in seen:
                seen.add(v)
                q.append(v)
    seen.discard(start)
    return seen


@lru_cache(maxsize=None)
def stored_nodes(m) -> frozenset:
    """Elements the map says are stored on a clock edge (storage "edge" or "mixed")."""
    mp = code_map(m) or {}
    return frozenset(f"{e['entity']}:{e['name']}" for a in ("ports", "signals") for e in mp.get(a, [])
                     if e.get("storage") in ("edge", "mixed"))


@lru_cache(maxsize=None)
def port_summary(entity) -> dict:
    """{(input port element, output port element): {"kind", "through_storage"}} inside `entity`, from its own file's
    graph. kind = explicit when an explicit-only path exists, else implicit."""
    m = entity_file().get(entity)
    if m is None or code_map(m) is None:
        return {}
    g = file_graph(m)
    els = g["closed_set"]["elements"]
    ins = [n for n, e in els.items() if e["entity"] == entity and e["dir"] in IN_DIRS]
    outs = {n for n, e in els.items() if e["entity"] == entity and e["dir"] in OUT_DIRS}
    ex, anyk = _adj(g["edges"], ("explicit",)), _adj(g["edges"], FLOW)
    stored = stored_nodes(m)
    out = {}
    for s in ins:
        r_any, r_ex = _reach(anyk, s), _reach(ex, s)
        # through storage: reachable from a stored node that s reaches (or s itself stored)
        via_store = set()
        for t in (r_any & stored):
            via_store |= _reach(anyk, t) | {t}
        for t in r_any & outs:
            out[(els[s]["name"], els[t]["name"])] = {"kind": "explicit" if t in r_ex else "implicit",
                                                     "through_storage": t in via_store}
    return out


@lru_cache(maxsize=None)
def node_facts(m) -> dict:
    """Per node: storage, root entity, top-level inputs that reach it and top-level outputs it reaches (labelled),
    direct controls / controlled-by (implicit edges), clock and reset sources."""
    g = file_graph(m)
    els, h = g["closed_set"]["elements"], g["hierarchy"]
    # root entity of each entity (same-file descendants belong to the root that instantiates them)
    kids = defaultdict(set)
    for i in h["instances"]:
        if i["same_file"] and i["parent"]:
            kids[i["parent"]].add(i["child"])
    root_of = {}
    for r in h["roots"]:
        q = deque([r])
        while q:
            u = q.popleft()
            root_of.setdefault(u, r)
            q.extend(kids[u])
    ex, anyk = _adj(g["edges"], ("explicit",)), _adj(g["edges"], FLOW)
    rex, rany = _adj(g["edges"], ("explicit",), True), _adj(g["edges"], FLOW, True)
    facts = {}
    for n, e in els.items():
        facts[n] = {"entity": e["entity"], "root": root_of.get(e["entity"]), "dir": e["dir"],
                    "top_level": e["top_level"], "record": e["record"], "stored": n in stored_nodes(m),
                    "from_inputs": {}, "to_outputs": {}, "controls": [], "controlled_by": [], "clock": [], "reset": []}
    for ed in g["edges"]:
        if ed["kind"] == "implicit":
            facts[ed["dst"]]["controlled_by"].append(ed["src"])
            facts[ed["src"]]["controls"].append(ed["dst"])
        elif ed["kind"] in ("clock", "reset"):
            facts[ed["dst"]][ed["kind"]].append(ed["src"])
    for n, f in facts.items():
        for k in ("controls", "controlled_by", "clock", "reset"):
            f[k] = sorted(set(f[k]))
    tops_in = [n for n, e in els.items() if e["top_level"] and e["dir"] in IN_DIRS]
    tops_out = [n for n, e in els.items() if e["top_level"] and e["dir"] in OUT_DIRS]
    for s in tops_in:
        r_ex = _reach(ex, s)
        for t in _reach(anyk, s):
            if t in facts and facts[t]["root"] == facts[s]["root"]:
                facts[t]["from_inputs"][s] = "explicit" if t in r_ex else "implicit"
    for s in tops_out:
        r_ex = _reach(rex, s)
        for t in _reach(rany, s):
            if t in facts and facts[t]["root"] == facts[s]["root"]:
                facts[t]["to_outputs"][s] = "explicit" if t in r_ex else "implicit"
    return facts


def build(m) -> dict:
    g = file_graph(m)
    return {"module": m, "version": f"pio_graph {GRAPH_VERSION} on {FIX.relative_to(ROOT).as_posix()}",
            "hierarchy": g["hierarchy"], "sub_blocks": g["sub_blocks"],
            "elements": g["closed_set"]["elements"], "edges": g["edges"], "facts": node_facts(m),
            "unresolved_connections": g["unresolved_connections"], "nodes_not_in_closed_set": g["nodes_not_in_closed_set"]}


# ------------------------------------------------------------------------------------------------ self-tests ---
def _has(edges, src, dst, kind, via=None, line=None):
    return any(e["src"] == src and e["dst"] == dst and e["kind"] == kind and (via is None or e["via"] == via)
               and (line is None or line in e["lines"]) for e in edges)


def selftest(log=print) -> bool:
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        log(f"   {'ok  ' if cond else 'FAIL'} {label}")

    W = "neorv32_wdt:"
    e = file_graph("neorv32_wdt")["edges"]
    # hand-read data/RTL_data/neorv32_wdt.vhd
    check("wdt 93 `if (ctrl.lock = '0') then` -> 94 ctrl.enable: implicit",
          _has(e, W + "ctrl.lock", W + "ctrl.enable", "implicit", "GATES", 93))
    check("wdt 94 `ctrl.enable <= bus_req_i.data(ctrl_enable_c);`: explicit",
          _has(e, W + "bus_req_i.data", W + "ctrl.enable", "explicit", "SOURCES", 94))
    check("wdt 95 `ctrl.lock <= bus_req_i.data(ctrl_lock_c) and ctrl.enable;`: ctrl.enable explicit (operand)",
          _has(e, W + "ctrl.enable", W + "ctrl.lock", "explicit", "GATES", 95))
    check("wdt 102 `if (bus_req_i.data(31 downto 0) = reset_pwd_c) then` -> 103 reset_wdt: implicit",
          _has(e, W + "bus_req_i.data", W + "reset_wdt", "implicit", "GATES", 102))
    check("wdt 109 `bus_rsp_o.data(ctrl_enable_c) <= ctrl.enable;`: explicit",
          _has(e, W + "ctrl.enable", W + "bus_rsp_o.data", "explicit", "CARRIES", 109))
    check("wdt 94 is not also an implicit edge from bus_req_i.data to ctrl.enable",
          not _has(e, W + "bus_req_i.data", W + "ctrl.enable", "implicit"))
    f = node_facts("neorv32_wdt")
    check("wdt ctrl.enable: reached explicitly from bus_req_i.data, reaches bus_rsp_o.data explicitly",
          f[W + "ctrl.enable"]["from_inputs"].get(W + "bus_req_i.data") == "explicit"
          and f[W + "ctrl.enable"]["to_outputs"].get(W + "bus_rsp_o.data") == "explicit")
    check("wdt clk_i reaches no element by a value flow (clock edges kept apart)",
          not any(W + "clk_i" in x["from_inputs"] for x in f.values()))

    # hand-read data/RTL_data/neorv32_cache.vhd 273-291 (component form, same file)
    C = file_graph("neorv32_cache")
    h = C["hierarchy"]
    check("cache: neorv32_cache_memory_inst is a same-file child; root is neorv32_cache only",
          any(i["label"] == "neorv32_cache_memory_inst" and i["same_file"] and i["parent"] == "neorv32_cache"
              for i in h["instances"]) and h["roots"] == ["neorv32_cache"])
    check("cache 283 `clr_i => cache_o.cmd_clr`: explicit edge into the child port",
          _has(C["edges"], "neorv32_cache:cache_o.cmd_clr", "neorv32_cache_memory:clr_i", "explicit", "PORT_MAP", 283))
    check("cache 291 `rdata_o => cache_i.data`: explicit edge out of the child port",
          _has(C["edges"], "neorv32_cache_memory:rdata_o", "neorv32_cache:cache_i.data", "explicit", "PORT_MAP", 291))

    # hand-read data/RTL_data/neorv32_spi.vhd 186-208 (other-file child: neorv32_fifo)
    S = file_graph("neorv32_spi")
    check("spi 202/207 `wdata_i => tx_fifo.wdata`, `rdata_o => tx_fifo.rdata`: summary edge through the FIFO, "
          "explicit, through storage",
          any(x["src"] == "neorv32_spi:tx_fifo.wdata" and x["dst"] == "neorv32_spi:tx_fifo.rdata" and x["via"] == "SUB_BLOCK"
              and x["kind"] == "explicit" and x["through_storage"] and 202 in x["lines"] and 207 in x["lines"]
              for x in S["edges"]))
    check("spi: no FIFO-internal element appears as a node",
          not any(x[k].startswith("neorv32_fifo:") for x in S["edges"] for k in ("src", "dst")))
    # every file: every edge end is an element of N; every connection's instance label is known
    for split in RTL:
        bad = []
        for m in modules(split):
            if code_map(m) is None:
                continue
            g = file_graph(m)
            if g["nodes_not_in_closed_set"] or g["unresolved_connections"] or g["hierarchy"]["unknown_instances"]:
                bad.append((m, g["nodes_not_in_closed_set"][:3], g["unresolved_connections"][:3],
                            g["hierarchy"]["unknown_instances"]))
        check(f"{split}: every edge end is in N and every instance is resolved ({bad[:3]})", not bad)
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    assert selftest(), "self-test failed: nothing written"
    for split in RTL:
        (OUT / split).mkdir(parents=True, exist_ok=True)
        for m in modules(split):
            if code_map(m) is None:
                continue
            d = build(m)
            (OUT / split / f"{m}.json").write_text(json.dumps(d, indent=1), encoding="utf-8")
            print(f"{split:8s} {m:28s} N={len(d['elements']):4d} edges={len(d['edges']):5d} "
                  f"roots={d['hierarchy']['roots']} sub-blocks={sorted(d['sub_blocks'])}")
