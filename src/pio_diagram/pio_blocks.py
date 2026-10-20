"""PIO track: the flow graph drawn as an architectural block diagram (like P3164's figures), built by code.

A block is a piece of the RTL the designer wrote as one unit:
  process     a labelled process; its members are the elements it assigns
  generate    concurrent assignments inside a labelled generate statement
  logic       one concurrent assignment to an internal signal at architecture level
  instance    an instantiated entity: another IP (only its ports are visible) or an entity of this file (collapsed)
Ports sit on the unit's boundary, record ports grouped by their record. An arrow from block A to block B means some
element assigned in A flows into a statement inside B: solid when a value moves (explicit), dashed when A only decides
(implicit). Each arrow keeps the element pairs and RTL lines behind it. Clock and reset are listed per block, not drawn.

Sources: the map's driving records (each names the target's statement occurrence, `partner_at`), the occurrence
profiles' Context (which process / generate holds each statement), and the map's port-map connections. Same version as
pio_graph.py (final/branch_label/all_four_fixes).

  python src/pio_diagram/pio_blocks.py [module]      self-tests, then prints the module's diagram as text
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pio_graph as G  # noqa: E402

LHS = {"LHS_PROC", "LHS_CONC"}

# The key line written after ARROWS in diagram.txt (text(lines=False)), by input version. "v1" is the original shorthand,
# looser than the prompt's arrow rules (common.md 1(c), 2.2); "v1k" states them, checked by skeptics against every arrow
# of the 43 diagrams (lab/analysis/prompt_builds/DIAGRAM_KEY_FIX.md). lab/inputs/v1k is built from v1 by
# lab/analysis/prompt_builds/make_inputs_v1k.py, whose KEY_V1K must equal ARROWS_KEYS["v1k"].
ARROWS_KEYS = {
    "v1": "  ARROWS (==> a value moves; --> only decides; [the elements the arrow carries])",
    "v1k": ("  ARROWS (A ==> B: at least one listed element has an explicit flow into B, or B is an output port that A's own statements also assign; "
            "A --> B: no listed element has an explicit flow into B, and each one decides B or is an index; "
            "in either arrow, a listed element carries its value as an index only when the array element or slice it picks is read or "
            "written in an assignment to B, not when that element is only tested (2.2); "
            "[...]: A's elements the arrow stands for (rec.{a,b} is rec.a and rec.b; if the whole record rec also moves, it is not named "
            "separately), some of which may only decide; "
            "from an [inst] block whose port map writes output port B directly: the instance's own port (under the child entity if the instance "
            "is of this file; in no list if it is another IP's), left out when it has B's name; "
            "no [...] from any other block: A's own statements assign output port B, perhaps with constants only; "
            "a clock or reset wired into an instance block is drawn ==> and carries no value)"),
}


@lru_cache(maxsize=None)
def profiles(m) -> dict:
    p = G.FIX / "occurrence_profiles" / f"{m}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@lru_cache(maxsize=None)
def occ_context(m) -> dict:
    """{(entity, element, occurrence id): (line, sites, context)}"""
    out = {}
    for ent, els in profiles(m).items():
        for name, rows in els.items():
            for r in rows:
                ln = r.get("Occurrence Lines")
                ln = ln[0] if isinstance(ln, list) else ln
                out[(ent, name, r.get("Occurrence ID"))] = (ln, r.get("SITE Tagged") or [], r.get("Context") or "")
    return out


def _frames(context: str) -> list[str]:
    return [s.strip() for s in context.split(" in ")] if context else []


def statement_block(m, ent, name, occ_id) -> tuple[str, str] | None:
    """(kind, id) of the block holding this assignment occurrence; None when it is not an assignment.
    The id carries the start line, so processes that share a label in different generate branches stay apart."""
    ln, sites, ctx = occ_context(m).get((ent, name, occ_id), (None, [], ""))
    if not set(sites) & LHS:
        return None
    fr = _frames(ctx)
    for f in fr:                                    # innermost first
        mm = re.match(r"process\s+(\w+)\s+(\d+)-\d+$", f)
        if mm:
            return ("process", f"{ent}:{mm.group(1)}@{mm.group(2)}")
        mm = re.match(r"process\s+(\d+)-(\d+)$", f)
        if mm:
            return ("process", f"{ent}:process@{mm.group(1)}")
    for f in fr:
        mm = re.match(r"generate\s+(\w+)\s+(\d+)-\d+$", f)
        if mm:
            return ("generate", f"{ent}:{mm.group(1)}@{mm.group(2)}")
    return ("logic", f"{ent}:{name}")


@lru_cache(maxsize=None)
def instance_entity(m) -> dict:
    """{instance label: (child entity, same file?)}"""
    h = G.step2_hierarchy(m)
    return {i["label"]: (i["child"], i["same_file"]) for i in h["instances"]}


@lru_cache(maxsize=None)
def instance_parent(m) -> dict:
    """{instance label: entity whose architecture holds it}"""
    return {i["label"]: i["parent"] for i in G.step2_hierarchy(m)["instances"]}


@lru_cache(maxsize=None)
def child_block(m) -> dict:
    """{entity declared and instantiated in this file: block id of its OUTERMOST same-file instance}. A child of a
    child collapses into the outer block too (trng: neoTRNG_cell inside neoTRNG)."""
    roots = set(G.step2_hierarchy(m)["roots"])
    direct = {}
    for lb, (child, same) in instance_entity(m).items():
        if same:
            direct.setdefault(child, (lb, instance_parent(m).get(lb)))
    out = {}
    for child in direct:
        c, seen = child, set()
        while c in direct and direct[c][1] not in roots and direct[c][1] in direct and c not in seen:
            seen.add(c)
            c = direct[c][1]
        out[child] = f"inst:{direct[c][0]}"
    return out


@lru_cache(maxsize=None)
def child_blocks(m) -> dict:
    """{entity declared and instantiated in this file: set of the outermost blocks of ALL its instances}
    (cpu_counters: neorv32_cpu_counters_cnt is cycle_inst, instret_inst and hpmcnt_inst)."""
    roots = set(G.step2_hierarchy(m)["roots"])
    ie, par = instance_entity(m), instance_parent(m)

    def blocks_of(entity, seen):
        out = set()
        for lb, (child, same) in ie.items():
            if same and child == entity:
                p = par.get(lb)
                if p in roots or p not in {c for c, sm in ie.values() if sm}:
                    out.add(f"inst:{lb}")
                elif p not in seen:
                    out |= blocks_of(p, seen | {p})
        return out
    return {child: blocks_of(child, {child}) for child in child_block(m)}


def _fields(m, ent, name) -> list[str]:
    els = G.file_graph(m)["closed_set"]["elements"]
    return [e["name"] for e in els.values() if e["entity"] == ent and e["name"].startswith(name + ".")]


@lru_cache(maxsize=None)
def element_block_chains(m) -> dict:
    """{(node, block id): set of generate chains of the occurrences producing the node in that block}."""
    import pio_flowfix as F
    out = defaultdict(set)
    els = G.file_graph(m)["closed_set"]["elements"]
    cb = child_block(m)
    for (ent, name, oid), (ln, sites, ctx) in occ_context(m).items():
        node = f"{ent}:{name}"
        if node not in els or ent in cb or els[node]["top_level"]:
            continue
        b = statement_block(m, ent, name, oid)
        if b:
            out[(node, f"{b[0]}:{b[1]}")].add(F.gen_chain(m, ctx))
    for a in ("ports", "signals"):
        for e in (G.code_map(m) or {}).get(a, []):
            if e["entity"] in cb:
                continue
            for c in e.get("connections", []) or []:
                ctx = occ_context(m).get((e["entity"], e["name"], c.get("at")), (None, [], ""))[2]
                for nm in [e["name"]] + _fields(m, e["entity"], e["name"]):
                    out[(f"{e['entity']}:{nm}", f"inst:{c['instance']}")].add(F.gen_chain(m, ctx))
    return out


def element_blocks(m) -> dict:
    """{node: set of block ids where its value is produced}. Ports of a root entity are port nodes instead."""
    g = G.file_graph(m)
    els = g["closed_set"]["elements"]
    cb = child_block(m)
    out = defaultdict(set)
    for (ent, name, oid) in occ_context(m):
        node = f"{ent}:{name}"
        if node not in els:
            continue
        if ent in cb:
            if els[node]["dir"] != "in":                # a child's input port is assigned by the parent's port map
                out[node] |= child_blocks(m)[ent] or {cb[ent]}
            continue
        b = statement_block(m, ent, name, oid)
        if b and not els[node]["top_level"]:
            out[node].add(f"{b[0]}:{b[1]}")
    for a in ("ports", "signals"):
        for e in (G.code_map(m) or {}).get(a, []):
            if e["entity"] in cb:
                continue
            for c in e.get("connections", []) or []:
                child = instance_entity(m).get(c.get("instance"), (None, False))[0]
                mode = c.get("mode") or G.port_dir().get((child, c.get("formal")))
                if mode in ("out", "buffer", "inout"):
                    for nm in [e["name"]] + _fields(m, e["entity"], e["name"]):
                        node = f"{e['entity']}:{nm}"
                        if not els.get(node, {}).get("top_level"):
                            out[node].add(f"inst:{c['instance']}")
    return out


def port_node(e: dict) -> str:
    base = e["field_of"] if e["field_of"] else e["name"]
    return f"{'in' if e['dir'] in G.IN_DIRS else 'out'}:{e['entity']}:{base}"


def unit_of_block(m, bid: str, root_of_entity: dict) -> str | None:
    if bid.startswith("inst:"):
        par = instance_parent(m).get(bid[5:])
        return root_of_entity.get(par)
    ent = bid.split(":", 2)[1]
    return root_of_entity.get(ent)


def _label(bid: str) -> str:
    """Display label: the designer's label without the start line."""
    if bid.startswith("inst:"):
        return bid[5:]
    return bid.split(":")[-1].split("@")[0]


@lru_cache(maxsize=None)
def diagram(m) -> dict:
    """{"module", "units": [{"root", "inputs", "outputs", "clock_reset", "blocks", "arrows"}]}"""
    import pio_flowfix as F
    g = G.file_graph(m)
    els = g["closed_set"]["elements"]
    facts = G.node_facts(m)
    root_of = {f["entity"]: f["root"] for f in facts.values()}
    eb = element_blocks(m)
    st = G.sites(m)
    cb = child_block(m)
    occ = occ_context(m)

    def src_nodes(node):
        e = els[node]
        if e["top_level"] and e["dir"] in G.IN_DIRS:
            return {port_node(e)}
        if e["entity"] in cb:
            return {cb[e["entity"]]}
        return set(eb.get(node, set()))

    arrows = defaultdict(lambda: {"kinds": set(), "via": set()})
    clocking = defaultdict(lambda: {"clock": set(), "reset": set()})
    ef = defaultdict(set)          # element flows, inside a block too: (entity, Y, X, kind, map type) -> lines
    pm = defaultdict(set)          # port maps: (entity, element, instance, formal, direction) -> lines
    members = defaultdict(set)
    for node, bs in eb.items():
        for b in bs:
            members[b].add(els[node]["name"])
    # every labelled process is a block, even one that assigns no element (uart sim_tx)
    for (ent, name, oid), (ln, sites, ctx) in occ.items():
        if ent in cb:
            continue
        for f in _frames(ctx):
            mm = re.match(r"process\s+(\w+)\s+(\d+)-\d+$", f)
            if mm:
                members.setdefault(f"process:{ent}:{mm.group(1)}@{mm.group(2)}", set())

    def add(a, b, kind, y, x, lines):
        if a == b:
            return
        arrows[(a, b)]["kinds"].add(kind)
        arrows[(a, b)]["via"].add((y, x, tuple(sorted({l for l in lines if l is not None}))))

    def dst_of(ent, x, oid):
        if ent in cb:
            return cb[ent]
        sb = statement_block(m, ent, x, oid)
        return f"{sb[0]}:{sb[1]}" if sb else None

    def same_statement_lines(ent, y, at_ids, x, oid):
        """Lines of Y's occurrences that belong to the statement assigning X at oid: inside the statement (from X's
        line to the line that ends it with ';'), or a condition or selector whose if or case encloses it. When none
        is: the lines where Y feeds a process variable the statement reads; else Y's occurrences in the process."""
        xl, _, xctx = occ.get((ent, x, oid), (None, [], ""))
        if xl is None:
            return []
        pf = next((f for f in _frames(xctx) if f.startswith("process ")), None)
        src, end = F.source_lines(m), xl
        while end in src and ";" not in src[end]:
            end += 1
        got, proc = [], []
        for i in at_ids:
            yl, ys, yctx = occ.get((ent, y, i), (None, [], ""))
            if yl is None:
                continue
            yfr = yctx.split(" in ")
            control = set(ys) & G.COND_SITES and yl <= xl and any(        # the if / case / when that holds Y
                xctx.endswith(" in ".join(yfr[k:])) for k in (0, 1)
                if yfr[k:] and yfr[k].startswith(("if ", "case ", "when else", "with select")))
            if xl <= yl <= end or control:
                got.append(yl)
            elif pf and pf in _frames(yctx):
                proc.append(yl)
        return got or F.var_value_lines(m, ent, y, xctx, range(xl, end + 1), x) or proc

    def flow(ent, y, x, oid, kind, ylines, via=None):
        """One live flow Y -> X at X's occurrence oid."""
        ynode, xnode = f"{ent}:{y}", f"{ent}:{x}"
        dst = dst_of(ent, x, oid)
        if dst is None:
            return
        ef[(ent, y, x, kind, via)] |= {l for l in ylines if l is not None}
        xe = els.get(xnode, {})
        out_port = xe.get("top_level") and xe.get("dir") in G.OUT_DIRS
        if out_port and dst.startswith("logic:"):
            dst = None                                   # a concurrent drive of an output port
        if kind in ("clock", "reset"):
            if dst:
                clocking[dst][kind].add(y)
            return
        dch = F.gen_chain(m, occ.get((ent, x, oid), (None, [], ""))[2])
        chains = element_block_chains(m)
        for s in src_nodes(ynode):
            if (ynode, s) in chains and not any(F.compatible(c, dch) for c in chains[(ynode, s)]):
                continue                                 # this producer is never built with the reading statement
            if dst:
                add(s, dst, kind, y, x, ylines)
                if out_port:
                    add(dst, port_node(xe), "explicit", x, x, [occ.get((ent, x, oid), (None,))[0]])
            else:
                add(s, port_node(xe), kind, y, x, ylines)

    for arr in ("ports", "signals"):
        for e in (G.code_map(m) or {}).get(arr, []):
            ent, y = e["entity"], e["name"]
            ynode = f"{ent}:{y}"
            lines_of = {o["id"]: o["line"] for o in e.get("occurrences", [])}
            for r in e.get("relationship", []) or []:
                t = r["type"]
                if t not in G.FLOW_TYPES and t != "GATES":
                    continue
                if t == "GATES":
                    kinds = {("implicit" if set(st.get(ent, {}).get(y, {}).get(str(i), [])) & G.COND_SITES else "explicit")
                             for i in r.get("at") or []} or {"implicit"}
                else:
                    kinds = {G.FLOW_TYPES[t]}
                ylines = [lines_of[i] for i in r.get("at") or [] if i in lines_of]
                for x in r.get("targets", []):
                    for oid in F.live_partners(m, ent, y, x, (r.get("partner_at") or {}).get(x, [])):
                        own = same_statement_lines(ent, y, r.get("at") or [], x, oid) or ylines
                        reset = t == "GATES" and F.reset_like(m, ent, y, r.get("at") or [], x, oid)
                        for k in ({"reset"} if reset else kinds):
                            flow(ent, y, x, oid, k, own, "RESETS" if reset else t)
            for c in e.get("connections", []) or []:
                lb = c.get("instance")
                child = instance_entity(m).get(lb, (None, False))[0]
                mode = c.get("mode") or G.port_dir().get((child, c.get("formal")))
                ln = [lines_of[c["at"]]] if c.get("at") in lines_of else []
                pairs = [(y, c.get("formal"))] + [(f, c.get("formal", "") + f[len(y):]) for f in _fields(m, ent, y)]
                for yy, ff in pairs:
                    pm[(ent, yy, lb, ff, mode)] |= set(ln)
                if ent in cb:
                    continue                             # wiring inside a collapsed child stays inside its block
                pch = F.gen_chain(m, occ.get((ent, y, c.get("at")), (None, [], ""))[2])
                chains = element_block_chains(m)
                for yy, ff in pairs:
                    yn = f"{ent}:{yy}"
                    if mode in ("in", "inout"):
                        for s in src_nodes(yn):
                            if (yn, s) in chains and not any(F.compatible(cc, pch) for cc in chains[(yn, s)]):
                                continue                 # this producer is never built with the instance
                            add(s, f"inst:{lb}", "explicit", yy, ff, ln)
                    if mode in ("out", "buffer", "inout") and els.get(yn, {}).get("top_level"):
                        add(f"inst:{lb}", port_node(els[yn]), "explicit", ff, yy, ln)
    for ent, y, x, oid, lines in F.var_cond_flows(m):  # decisions through a process variable
        if F.live_partners(m, ent, y, x, [oid]):
            flow(ent, y, x, oid, "implicit", list(lines), "VAR_COND")
    for (ent, x, oid), (ln, _s, _c) in occ.items():   # every block that assigns an output port, constants included
        xe = els.get(f"{ent}:{x}", {})
        if ent in cb or not (xe.get("top_level") and xe.get("dir") in G.OUT_DIRS):
            continue
        dst = dst_of(ent, x, oid)
        if dst and not dst.startswith("logic:") and F.live_partners(m, ent, x, x, [oid]):
            add(dst, port_node(xe), "explicit", x, x, [ln])

    for ent, bs in child_blocks(m).items():
        for b in bs - {cb[ent]}:
            for k in ("clock", "reset"):
                clocking[b][k] |= clocking[cb[ent]][k]
    units = []
    for r in G.step2_hierarchy(m)["roots"]:
        def in_unit(bid):
            if bid.startswith(("in:", "out:")):
                return root_of.get(bid.split(":", 2)[1]) == r
            return unit_of_block(m, bid, root_of) == r
        ar = [{"src": a, "dst": b, "kind": "explicit" if "explicit" in v["kinds"] else "implicit",
               "via": sorted([list(x[:2]) + [list(x[2])] for x in v["via"]])}
              for (a, b), v in sorted(arrows.items()) if in_unit(a) and in_unit(b)]
        blocks = {}
        for bid in set(members) | {x for a in ar for x in (a["src"], a["dst"])}:
            if bid.startswith(("in:", "out:")) or not in_unit(bid):
                continue
            kind = bid.split(":", 1)[0]
            info = {"id": bid, "kind": kind, "label": _label(bid), "members": sorted(members.get(bid, set())),
                    "clock": sorted(clocking[bid]["clock"]), "reset": sorted(clocking[bid]["reset"])}
            if kind == "inst":
                child, same = instance_entity(m).get(bid[5:], (None, False))
                info.update({"entity": child, "same_file": same})
            blocks[bid] = info
        # a label used by several blocks (one per generate branch) gets its start line
        cnt = defaultdict(int)
        for b in blocks.values():
            cnt[b["label"]] += 1
        for b in blocks.values():
            if cnt[b["label"]] > 1 and "@" in b["id"]:
                b["label"] = f"{b['label']} (line {b['id'].split('@')[-1]})"
        ins = sorted({port_node(e) for e in els.values() if e["entity"] == r and e["dir"] in G.IN_DIRS})
        outs = sorted({port_node(e) for e in els.values() if e["entity"] == r and e["dir"] in G.OUT_DIRS})
        cr = sorted({x for b in blocks.values() for x in b["clock"] + b["reset"]})
        units.append({"root": r, "inputs": ins, "outputs": outs, "clock_reset": cr,
                      "blocks": sorted(blocks.values(), key=lambda b: b["id"]), "arrows": ar})
    flows = [{"entity": e, "source": y, "target": x, "kind": k, "via": v, "lines": sorted(ls)}
             for (e, y, x, k, v), ls in sorted(ef.items(), key=lambda kv: tuple(str(z) for z in kv[0]))]
    ports = [{"entity": e, "element": y, "instance": lb, "port": ff, "direction": d, "lines": sorted(ls)}
             for (e, y, lb, ff, d), ls in sorted(pm.items(), key=lambda kv: tuple(str(z) for z in kv[0]))]
    return {"module": m, "units": units, "element flows": flows, "port maps": ports}


def text(m, cap: int | None = 6, lines: bool = True, key: str = "v1") -> str:
    """The block diagram in words (the form a prompt would read). cap = evidence pairs shown per arrow (None: all).
    lines=False: each arrow names the elements it carries, without element pairs or line numbers; key picks its
    ARROWS key line from ARROWS_KEYS (default "v1", so inputs v1 rebuild unchanged)."""
    if not lines:
        return _text_labels(m, key)
    d = diagram(m)
    out = []
    for u in d["units"]:
        out.append(f"UNIT {u['root']}")
        nm = lambda x: x.split(":")[-1] if x.startswith(("in:", "out:")) else labels.get(x, _label(x))  # noqa: E731
        labels = {b["id"]: b["label"] for b in u["blocks"]}
        out.append("  INPUTS: " + ", ".join(nm(p) for p in u["inputs"]))
        out.append("  OUTPUTS: " + ", ".join(nm(p) for p in u["outputs"]))
        out.append("  BLOCKS")
        for b in u["blocks"]:
            extra = f" ({b['entity']}, {'this file' if b['same_file'] else 'another IP'})" if b["kind"] == "inst" else ""
            ck = (f"; clocked by {', '.join(b['clock'])}" if b["clock"] else "") + (
                f"; reset by {', '.join(b['reset'])}" if b["reset"] else "")
            out.append(f"    [{b['kind']}] {b['label']}{extra}: {', '.join(b['members']) or '-'}{ck}")
        out.append("  ARROWS (solid = a value moves; dashed = only decides)")
        for a in u["arrows"]:
            shown = a["via"] if cap is None else a["via"][:cap]
            ev = "; ".join(f"{y}->{x}@{','.join(map(str, ls))}" for y, x, ls in shown)
            more = f"; and {len(a['via']) - len(shown)} more" if len(a["via"]) > len(shown) else ""
            out.append(f"    {nm(a['src'])} {'==>' if a['kind'] == 'explicit' else '-->'} {nm(a['dst'])}   [{ev}{more}]")
        out.append("")
    return "\n".join(out).rstrip()


def _text_labels(m, key: str = "v1") -> str:
    out = []
    for u in diagram(m)["units"]:
        labels = {b["id"]: b["label"] for b in u["blocks"]}
        nm = lambda x: x.split(":")[-1] if x.startswith(("in:", "out:")) else labels.get(x, _label(x))  # noqa: E731
        out.append(f"UNIT {u['root']}")
        out.append("  INPUTS: " + ", ".join(nm(p) for p in u["inputs"]))
        out.append("  OUTPUTS: " + ", ".join(nm(p) for p in u["outputs"]))
        out.append("  BLOCKS")
        for b in u["blocks"]:
            extra = f" ({b['entity']}, {'this file' if b['same_file'] else 'another IP'})" if b["kind"] == "inst" else ""
            ck = (f"; clocked by {', '.join(b['clock'])}" if b["clock"] else "") + (
                f"; reset by {', '.join(b['reset'])}" if b["reset"] else "")
            out.append(f"    [{b['kind']}] {b['label']}{extra}: {', '.join(b['members']) or '-'}{ck}")
        out.append(ARROWS_KEYS[key])
        for a in u["arrows"]:
            lab = _arrow_label(a, cap=10 ** 6)
            out.append(f"    {nm(a['src'])} {'==>' if a['kind'] == 'explicit' else '-->'} {nm(a['dst'])}"
                       + (f"   [{lab}]" if lab else ""))
        out.append("")
    return "\n".join(out).rstrip()


def _members_text(ms: list[str]) -> list[str]:
    """Record fields folded: ctrl.enable, ctrl.lock -> 'ctrl: enable, lock'."""
    by = defaultdict(list)
    for x in ms:
        base, _, f = x.partition(".")
        by[base].append(f)
    out = []
    for base, fs in sorted(by.items()):
        fs = [f for f in fs if f]
        out.append(f"{base}: {', '.join(fs)}" if fs else base)
    return out


def mermaid(m, unit: int = 0) -> str:
    """Mermaid flowchart of one unit: ports outside the unit box, blocks inside, arrows ==> (value) and -.-> (decides)."""
    u = diagram(m)["units"][unit]
    sid = lambda x: re.sub(r"\W", "_", x)  # noqa: E731
    kinds = {"process": "process", "generate": "generate", "logic": "logic", "inst": "instance"}
    L = ["flowchart LR"]
    used = {x for a in u["arrows"] for x in (a["src"], a["dst"])}
    for p in u["inputs"]:
        if p in used:
            L.append(f'  {sid(p)}["{p.split(":")[-1]}"]:::port')
    L.append(f'  subgraph UNIT["{u["root"]}"]')
    L.append("    direction LR")
    for b in u["blocks"]:
        head = b["label"] + (f" ({b['entity']})" if b["kind"] == "inst" else "")
        body = "<br/>".join(_members_text(b["members"])[:6]) if b["kind"] != "inst" else (
            "this file" if b["same_file"] else "another IP")
        L.append(f'    {sid(b["id"])}["<b>{head}</b><br/><i>{kinds[b["kind"]]}</i><br/>{body}"]:::{b["kind"]}')
    L.append("  end")
    for p in u["outputs"]:
        if p in used:
            L.append(f'  {sid(p)}["{p.split(":")[-1]}"]:::port')
    for a in u["arrows"]:
        lab = _arrow_label(a, cap=3)
        lab = f'|"{lab}"|' if lab else ""
        L.append(f'  {sid(a["src"])} {"==>" if a["kind"] == "explicit" else "-.->"}{lab} {sid(a["dst"])}')
    L += ["  classDef port fill:#F1EFE8,stroke:#888780,color:#2C2C2A",
          "  classDef process fill:#EEEDFE,stroke:#534AB7,color:#26215C",
          "  classDef generate fill:#E1F5EE,stroke:#0F6E56,color:#04342C",
          "  classDef logic fill:#E1F5EE,stroke:#0F6E56,color:#04342C",
          "  classDef inst fill:#FAECE7,stroke:#993C1D,color:#4A1B0C"]
    return "\n".join(L)


def _arrow_label(a: dict, cap: int = 3) -> str:
    """The elements an arrow carries, record fields folded (bus_req_i.{addr,data}); the marker pairs of a block that
    assigns an output port carry no element and are left out."""
    ys = sorted({y for y, x, _ in a["via"] if not (y == x and a["dst"].startswith("out:"))})
    by = defaultdict(list)
    for y in ys:
        base, _, f = y.partition(".")
        by[base] += [f] if f else []
    parts = [f"{b}.{{{','.join(fs)}}}" if len(fs) > 1 else (f"{b}.{fs[0]}" if fs else b) for b, fs in sorted(by.items())]
    return ", ".join(parts[:cap]) + (f" +{len(parts) - cap}" if len(parts) > cap else "")


# ------------------------------------------------------------------------------------------------ self-tests ---
def selftest(log=print) -> bool:
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        log(f"   {'ok  ' if cond else 'FAIL'} {label}")

    d = diagram("neorv32_wdt")["units"][0]
    B = {b["label"]: b for b in d["blocks"]}
    # hand-read data/RTL_data/neorv32_wdt.vhd: process bus_access 71-117 assigns ctrl.* (75-78, 94-97), reset_wdt,
    # reset_force (79-80, 87-88, 99-104); process wdt_counter 122-137 assigns cnt, cnt_started, cnt_inc;
    # 140 clkgen_en_o <= ctrl.enable; 141 prsc_tick <= clkgen_i(...); 144 cnt_timeout <= ...; 161 rstn_o <= ...
    check(f"wdt bus_access holds ctrl.* and reset_wdt/reset_force ({B.get('bus_access', {}).get('members')})",
          set(B.get("bus_access", {}).get("members", [])) >= {"ctrl.enable", "ctrl.lock", "ctrl.strict", "ctrl.timeout",
                                                               "reset_wdt", "reset_force"})
    check(f"wdt wdt_counter holds cnt, cnt_started, cnt_inc ({B.get('wdt_counter', {}).get('members')})",
          set(B.get("wdt_counter", {}).get("members", [])) == {"cnt", "cnt_started", "cnt_inc"})
    check("wdt 141/144: prsc_tick and cnt_timeout are logic blocks; output ports are not blocks",
          B.get("prsc_tick", {}).get("kind") == "logic" and B.get("cnt_timeout", {}).get("kind") == "logic"
          and "clkgen_en_o" not in B and "rstn_o" not in B)
    lab = lambda x: x.split(":")[-1] if x.startswith(("in:", "out:")) else _label(x)  # noqa: E731
    A = {(lab(a["src"]), lab(a["dst"])): a for a in d["arrows"]}
    check("wdt 94: bus_req_i ==> bus_access (explicit)", A.get(("bus_req_i", "bus_access"), {}).get("kind") == "explicit")
    check("wdt 140: bus_access ==> clkgen_en_o (concurrent drive of an output port)",
          A.get(("bus_access", "clkgen_en_o"), {}).get("kind") == "explicit")
    check("wdt 111: reset_cause is read back by bus_access (reset_identifier ==> bus_access), and bus_access ==> bus_rsp_o",
          ("reset_identifier", "bus_access") in A and ("bus_access", "bus_rsp_o") in A
          and ("reset_identifier", "bus_rsp_o") not in A)
    check("wdt bus_access clocked by clk_i, reset by rstn_sys_i",
          B.get("bus_access", {}).get("clock") == ["clk_i"] and B.get("bus_access", {}).get("reset") == ["rstn_sys_i"])
    s = diagram("neorv32_spi")["units"][0]
    SB = {b["label"]: b for b in s["blocks"]}
    check("spi: the two FIFOs are instance blocks of another IP",
          SB.get("tx_fifo_inst", {}).get("kind") == "inst" and SB.get("tx_fifo_inst", {}).get("same_file") is False
          and "rx_fifo_inst" in SB)
    c = diagram("neorv32_cache")["units"][0]
    CB = {b["label"]: b for b in c["blocks"]}
    check("cache 273: neorv32_cache_memory is collapsed into its instance block (same file)",
          CB.get("neorv32_cache_memory_inst", {}).get("same_file") is True
          and not any(b["id"].startswith(("process:neorv32_cache_memory", "logic:neorv32_cache_memory")) for b in c["blocks"]))
    check("bus: five units", len(diagram("neorv32_bus")["units"]) == 5)

    def arrows_of(m, i=0):
        u = diagram(m)["units"][i]
        return {(_label(a["src"]) if not a["src"].startswith(("in:", "out:")) else a["src"].split(":")[-1],
                 _label(a["dst"]) if not a["dst"].startswith(("in:", "out:")) else a["dst"].split(":")[-1]): a
                for a in u["arrows"]}, {b["label"]: b for b in u["blocks"]}
    # review findings of 2026-10-10, each against the RTL lines the reviewers cited
    xa, _ = arrows_of("neorv32_xbus")
    check("xbus 74/88: reg_stage_inst ==> arbiter; 141: reg_stage_inst ==> xbus_adr_o; 75/154: bus_rsp.data ==> reg_stage_inst",
          xa.get(("reg_stage_inst", "arbiter"), {}).get("kind") == "explicit" and ("reg_stage_inst", "xbus_adr_o") in xa
          and ("bus_rsp.data", "reg_stage_inst") in xa)
    ca, _ = arrows_of("neorv32_cpu")
    check("cpu 253/441: neorv32_cpu_control_inst ==> neorv32_cpu_icc_inst",
          ("neorv32_cpu_control_inst", "neorv32_cpu_icc_inst") in ca)
    ta, tb = arrows_of("neorv32_trng")
    check(f"trng 296: neoTRNG_cell_inst sits inside neoTRNG_inst, not beside it ({sorted(tb)})",
          "neoTRNG_cell_inst" not in tb and "neoTRNG_inst" in tb)
    ia, ib = arrows_of("neorv32_imem")
    check(f"imem 78/89/111/139: four separate mem_access blocks ({sorted(k for k in ib if k.startswith('mem_access'))})",
          sum(1 for k in ib if k.startswith("mem_access")) == 4)
    check("imem 84 vs 95: no arrow between exclusive generate branches imem_rom_default and imem_rom_alternative",
          ("imem_rom_default", "imem_rom_alternative") not in ia and ("imem_ram_default", "imem_rom_alternative") not in ia)
    pa, _ = arrows_of("neorv32_cpu_pmp")
    check("pmp 257/278: no arrow nap_mode_disable -> addr_mask_napot_gen",
          ("nap_mode_disable", "addr_mask_napot_gen") not in pa)
    cha, _ = arrows_of("neorv32_cache")
    pairs = {(y, x) for a in cha.values() for y, x, _ in a["via"]}
    check("cache 159-161: no pair host_req_i.stb -> bus_req_o.stb; host_req_i.addr -> bus_req_o.addr kept",
          ("host_req_i.stb", "bus_req_o.stb") not in pairs and ("host_req_i.addr", "bus_req_o.addr") in pairs)
    ga, _ = arrows_of("neorv32_gpio")
    check("gpio 123-124: bus_access --> irq_trigger (through the variable sel_v)", ("bus_access", "irq_trigger") in ga)
    bl = {(y, x): ls for u in diagram("neorv32_bus")["units"] for a in u["arrows"] for y, x, ls in a["via"]}
    # hand-read neorv32_bus.vhd 150-152 (one statement over three lines); muldiv 148-149, 150-151
    check(f"bus 150-152: b_req_i.data->x_req_o.data at 150 and 152 ({bl.get(('b_req_i.data', 'x_req_o.data'))})",
          bl.get(("b_req_i.data", "x_req_o.data")) == [150, 152])
    check(f"bus 150-152: a_req_i.data->x_req_o.data at 151 and 152 ({bl.get(('a_req_i.data', 'x_req_o.data'))})",
          bl.get(("a_req_i.data", "x_req_o.data")) == [151, 152])
    ma, _ = arrows_of("neorv32_cpu_cp_muldiv")
    ml = {(y, x): ls for a in ma.values() for y, x, ls in a["via"]}
    check(f"muldiv 148-149 and 150-151 ({ml.get(('ctrl_i.ir_funct3', 'ctrl.rs1_is_signed'))}, "
          f"{ml.get(('ctrl_i.ir_funct3', 'ctrl.rs2_is_signed'))})",
          ml.get(("ctrl_i.ir_funct3", "ctrl.rs1_is_signed")) == [148, 149]
          and ml.get(("ctrl_i.ir_funct3", "ctrl.rs2_is_signed")) == [150, 151])
    ca, cbk = arrows_of("neorv32_cpu")
    # hand-read neorv32_cpu.vhd 452-456: icc_disabled (if not ICC_EN generate) assigns icc_tx_o <= icc_terminate_c
    check("cpu 455: icc_disabled ==> icc_tx_o (constant driver of an output port)", ("icc_disabled", "icc_tx_o") in ca)
    bu = {b["label"]: b for u in diagram("neorv32_bus")["units"] for b in u["blocks"]}
    rm = bu.get("neorv32_bus_reg_inst", {}).get("members", [])
    # hand-read neorv32_bus.vhd 198-204: clk_i, rstn_i, host_req_i, device_rsp_i are inputs of neorv32_bus_reg
    check(f"bus 198-204: collapsed neorv32_bus_reg_inst holds no input port of the child ({len(rm)} members)",
          rm and not any(x.split(".")[0] in ("clk_i", "rstn_i", "host_req_i", "device_rsp_i") for x in rm))
    # review of the 25 modules not used for fixing (2026-10-10), each against the RTL lines the reviewers cited
    aa, _ = arrows_of("neorv32_cpu_alu")
    # hand-read neorv32_cpu_alu.vhd 290-292/346-352 (cfu) and 249-251/278-281 (fpu): X / not X generate branches
    check("cpu_alu 291/347, 250/279: no arrow from a *_false generate into the instance of the *_true one",
          ("neorv32_cpu_cp_cfu_inst_false", "neorv32_cpu_cp_cfu_inst") not in aa
          and ("neorv32_cpu_cp_fpu_inst_false", "neorv32_cpu_cp_fpu_inst") not in aa
          and ("neorv32_cpu_cp_cfu_inst_true", "neorv32_cpu_cp_cfu_inst") in aa)
    ka, kb = arrows_of("neorv32_cpu_counters")
    # hand-read neorv32_cpu_counters.vhd: cycle_inst, instret_inst, hpmcnt_inst all instantiate neorv32_cpu_counters_cnt
    same = [kb.get(x, {}) for x in ("cycle_inst", "instret_inst", "hpmcnt_inst")]
    check(f"cpu_counters: every instance of neorv32_cpu_counters_cnt holds lo_q and is clocked by clk_i, reset by rstn_i "
          f"({[(len(b.get('members', [])), b.get('clock'), b.get('reset')) for b in same]})",
          all("lo_q" in b.get("members", []) and b.get("clock") == ["clk_i"] and b.get("reset") == ["rstn_i"] for b in same))
    sa, sb = arrows_of("neorv32_sysinfo")
    # hand-read neorv32_sysinfo.vhd 91-93: rstn_i resets sysinfo_clk with a generic value; no arrow
    check(f"sysinfo 91-93: sysinfo_clk reset by rstn_i, no rstn_i arrow ({sb.get('sysinfo_clk', {}).get('reset')})",
          sb.get("sysinfo_clk", {}).get("reset") == ["rstn_i"] and ("rstn_i", "sysinfo_clk") not in sa)
    da, _ = arrows_of("neorv32_cpu_decompressor")
    dpairs = {(y, x, tuple(ls)) for a in da.values() for y, x, ls in a["via"]}
    check("decompressor 144: no instr_i->decoded pair at the overwritten line 144",
          not any(y == "instr_i" and x == "decoded" and 144 in ls for y, x, ls in dpairs))
    # review of all 43 modules on graph g2 (2026-10-10): evidence lines
    def vias(m):
        return {(y, x, tuple(ls)) for u in diagram(m)["units"] for a in u["arrows"] for y, x, ls in a["via"]}
    bv = vias("neorv32_bus")
    # hand-read neorv32_bus.vhd 387-395: tmp_v.data/.ack/.err built on 390/391/392, then int_rsp <= tmp_v
    check("bus 390-395: port_rsp reaches int_rsp.data at 390, .ack at 391, .err at 392 only",
          {("port_rsp", "int_rsp.data", (390,)), ("port_rsp", "int_rsp.ack", (391,)), ("port_rsp", "int_rsp.err", (392,))} <= bv
          and not any(y == "port_rsp" and x == "int_rsp.ack" and ls != (391,) for y, x, ls in bv))
    mv = vias("neorv32_cpu_cp_bitmanip")
    # hand-read neorv32_cpu_cp_bitmanip.vhd 304/305 and 405/406: separate one-line conditional assignments
    check("bitmanip 304/305, 405/406: a one-line when-else condition is cited only for its own statement",
          not any(ls in ((304, 305), (405, 406)) for _, _, ls in mv))
    ia2, _ = arrows_of("neorv32_imem")
    lines_bad = [ls for a in ia2.values() if a["dst"].endswith("@137") for y, x, ls in a["via"] if 128 in ls]
    check(f"imem 128: no evidence line from process 111 on arrows into imem_ram_alternative ({lines_bad})", not lines_bad)
    _, ub = arrows_of("neorv32_uart")
    check("uart: the labelled process sim_tx has a block", "sim_tx" in ub)
    # every arrow's evidence is a real edge of the flow graph or a port-map connection
    bad = 0
    for split in G.RTL:
        for m in G.modules(split):
            if not G.code_map(m):
                continue
            edges = {(e["src"].split(":", 1)[1], e["dst"].split(":", 1)[1]) for e in G.file_graph(m)["edges"]}
            conns = {(e["name"], c.get("formal")) for a in ("ports", "signals") for e in G.code_map(m)[a]
                     for c in e.get("connections", []) or []}
            for u in diagram(m)["units"]:
                for a in u["arrows"]:
                    for y, x, _ in a["via"]:
                        by, bx = y.split(".")[0], x.split(".")[0]
                        bad += not ((y, x) in edges or (y, x) in conns or (x, y) in conns or y == x
                                    or (by, bx) in conns or (bx, by) in conns)
    check(f"every arrow's evidence is a flow-graph edge or a port-map connection ({bad} not)", bad == 0)
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    assert selftest(), "self-test failed"
    print(text(sys.argv[1] if len(sys.argv) > 1 else "neorv32_wdt"))
