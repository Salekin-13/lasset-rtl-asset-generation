"""Inputs for PIO prompt experiments, version v1: per module the RTL, the closed set (JSON) and the block diagram.

  rtl.txt           the module's entities, comments removed, blank lines left out, each line numbered as in the file
                    (pio_diagram.rtl_text, the RTL every earlier arm used)
  closed_set.json   every port and signal of every entity in the file, with its occurrence lines, a role from a fixed
                    list of tags, and its counterparts with lines (format and definitions: inputs/v1/README.md)
  diagram.txt       the block diagram (pio_blocks.text, lines=False): blocks, and arrows naming the elements they carry

Sources (no model): the closed set of map version final/branch_label/all_four_fixes, its occurrence profiles (the
profiler's lines), and graph g2 (that map + pio_flowfix), read through pio_blocks.diagram's element flows, so every
counterpart is a flow the block diagram draws. The user's choices of 2026-10-10: records nested with their fields,
role as tags, counterparts grouped with lines, signal type by clock edge.

Run   python src/pio_diagram/pio_inputs.py            (self-tests first; nothing is written if one fails)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import date
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pio_blocks as B    # noqa: E402
import pio_diagram as D   # noqa: E402
import pio_flowfix as F   # noqa: E402
import pio_graph as G     # noqa: E402

VERSION = "v1"
# ARROWS key line of diagram.txt (pio_blocks.ARROWS_KEYS): v1 keeps its original shorthand; any later input version
# gets the exact key that states common.md 1(c) and 2.2 (lab/analysis/prompt_builds/DIAGRAM_KEY_FIX.md).
ARROWS_KEY = "v1" if VERSION == "v1" else "v1k"
OUT = HERE / "lab" / "inputs" / VERSION
LHS = {"LHS_PROC", "LHS_CONC"}
DECL = {"DECL_PORT", "DECL_SIGNAL", "DECL_FIELD"}

# the fixed tag list; each tag is one fact of the graph (definitions also in inputs/v1/README.md)
TAGS_OUT = ("clock", "reset", "condition", "selector", "index", "copied", "operand")
TAGS_IN = ("held on a clock edge", "reset to a constant", "set without a clock", "set by an instance",
           "set to constants only")
TAGS_PORT = ("read", "not read", "driven", "tied to a constant", "undriven")
TAG_UNUSED = "not used in this module"
GROUPS = ("gets value from", "decided by", "gives value to", "decides", "clocked by", "reset by", "clocks", "resets")


# ------------------------------------------------------------------------------------------------ facts ---
@lru_cache(maxsize=None)
def occurrences(m) -> dict:
    """{(entity, element): [(line, sites)]} from the occurrence profiles of the map version (the profiler's lines)."""
    p = G.FIX / "occurrence_profiles" / f"{m}.json"
    out = defaultdict(list)
    for ent, els in json.loads(p.read_text(encoding="utf-8")).items():
        for name, rows in els.items():
            for r in rows:
                ls = r.get("Occurrence Lines")
                for ln in (ls if isinstance(ls, list) else [ls]):
                    out[(ent, name)].append((ln, frozenset(r.get("SITE Tagged") or [])))
    return dict(out)


@lru_cache(maxsize=None)
def flows(m) -> tuple[dict, dict, dict]:
    """(out, inn, ports): out[(ent, y)] / inn[(ent, x)] = [flow dicts]; ports[(ent, element)] = [port-map dicts]."""
    d = B.diagram(m)
    out, inn, pm = defaultdict(list), defaultdict(list), defaultdict(list)
    for f in d["element flows"]:
        out[(f["entity"], f["source"])].append(f)
        inn[(f["entity"], f["target"])].append(f)
    for p in d["port maps"]:
        pm[(p["entity"], p["element"])].append(p)
    return dict(out), dict(inn), dict(pm)


@lru_cache(maxsize=None)
def map_entries(m) -> dict:
    return {(e["entity"], e["name"]): e for a in ("ports", "signals") for e in (G.code_map(m) or {}).get(a, [])}


def _sites_on(m, ent, name, lines) -> set:
    return {s for ln, ss in occurrences(m).get((ent, name), []) if ln in lines for s in ss}


def _instance_out(m, ent, name) -> list:
    """Port maps where an instance's output drives this element."""
    return [p for p in flows(m)[2].get((ent, name), []) if p["direction"] in ("out", "buffer", "inout")]


def _instance_in(m, ent, name) -> list:
    return [p for p in flows(m)[2].get((ent, name), []) if p["direction"] in ("in", "inout")]


def _has_fields(m, ent, name) -> bool:
    els = G.file_graph(m)["closed_set"]["elements"]
    return any(e["entity"] == ent and e["field_of"] == name for e in els.values())


def element_flows(m, ent, n) -> tuple[list, list]:
    """(out, in) flows of one element. A field also takes the flows of its whole record whose partner has no fields
    to split them into (bus 367: `port_rsp(1) <= b_rsp_i;`, port_rsp an array of records), and every flow keeps only
    the lines where its source occurs (a variable's test line is where the variable is read, not the source)."""
    out, inn, _ = flows(m)
    fo, fi = list(out.get((ent, n), [])), list(inn.get((ent, n), []))
    if "." in n:
        base = n.split(".", 1)[0]
        fo += [{**f, "source": n, "inherited from": base} for f in out.get((ent, base), [])
               if not _has_fields(m, ent, f["target"])]
        fi += [{**f, "target": n, "inherited from": base} for f in inn.get((ent, base), [])
               if not _has_fields(m, ent, f["source"])]
    res = []
    for f in fo + fi:
        src = f.get("inherited from") if f in fo and f.get("inherited from") else f["source"]
        have = {ln for ln, _s in occurrences(m).get((ent, src), [])}
        ls = [ln for ln in f["lines"] if ln in have] or f["lines"]
        res.append({**f, "lines": ls})
    return res[:len(fo)], res[len(fo):]


def _statement(m, line) -> str:
    """The text of the statement that holds the line: back to the previous ';' (or a keyword that opens a statement
    list), forward to the next ';'."""
    src = F.source_lines(m)
    a = line
    while a - 1 in src and not re.search(r";\s*$|\b(then|else|begin|generate|is|=>)\s*$", src[a - 1].strip(), re.I) \
            and line - a < 12:
        a -= 1
    b = line
    while b in src and ";" not in src[b] and b - line < 20:
        b += 1
    return " ".join(src.get(i, "").strip() for i in range(a, b + 1))


_CONV = re.compile(r"^(std_ulogic_vector|std_logic_vector|unsigned|signed|std_ulogic|std_logic|to_bit|to_bitvector|"
                   r"to_stdulogic|to_stdulogicvector|to_stdlogicvector)\s*\((.*)\)$", re.I | re.S)


def _strip(x: str) -> str:
    x = x.strip()
    while True:
        mm = _CONV.match(x)
        if mm and _balanced(mm.group(2)):
            x = mm.group(2).strip()
            continue
        if x.startswith("(") and x.endswith(")") and _balanced(x[1:-1]):
            x = x[1:-1].strip()
            continue
        return x


def _balanced(x: str) -> bool:
    d = 0
    for c in x:
        d += c == "("
        d -= c == ")"
        if d < 0:
            return False
    return d == 0


def _top_split(x: str, sep: str) -> list[str]:
    parts, d, cur = [], 0, ""
    for c in x:
        d += c == "("
        d -= c == ")"
        if c == sep and d == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    return parts + [cur]


def _is_ref(p: str, names: set) -> bool:
    """An element (or variable or constant) written plainly: a name, then only index or slice groups and field
    selections (port_rsp(i).data). A name with groups must be an element, not a function."""
    mm = re.match(r"[A-Za-z_][\w.]*", p)
    if not mm:
        return False
    name, rest = mm.group(0), p[mm.end():].strip()
    grouped = False
    while rest:
        if rest.startswith("("):
            d = 0
            for i, c in enumerate(rest):
                d += c == "("
                d -= c == ")"
                if d == 0:
                    break
            if d:
                return False
            rest, grouped = rest[i + 1:].strip(), True
        elif re.match(r"\.[A-Za-z_]\w*", rest):
            rest = rest[re.match(r"\.[A-Za-z_]\w*", rest).end():].strip()
        else:
            return False
    return not grouped or name.lower() in names


def copy_kind(m, ent, y: str, line: int, names: set) -> set:
    """{'copied'} and / or {'operand'}: per value arm of the statement at line that holds y, 'copied' if y stands alone
    there (an index, a slice, a type conversion or a concatenation with other plain parts allowed), else 'operand'
    (muldiv 300: one arm computes with div.res_u, the other copies it, so both)."""
    ref = re.compile(rf"(?<![\w.]){re.escape(y)}(?![\w])", re.I)
    arms = []
    for one in _statement(m, line).split(";"):        # a line can hold two statements (bus 367)
        mrhs = re.search(r"(<=|:=)(.*)$", one, re.S)
        if mrhs and ref.search(mrhs.group(2)):
            arms += [p for p in re.split(r"\bwhen\b.*?(?:\belse\b|,(?![^()]*\))|$)", mrhs.group(2), flags=re.I | re.S)
                     if p.strip()]
    kinds = set()
    for arm in arms:
        if not ref.search(arm):
            continue
        parts = [_strip(p) for p in _top_split(_strip(arm), "&")]
        plain = all(_is_ref(p, names) or
                    re.fullmatch(r"'.'|\"[^\"]*\"|x\"[^\"]*\"|\d+|\(\s*others\s*=>\s*'.'\s*\)", p, re.I | re.S)
                    for p in parts)
        kinds.add("copied" if plain else "operand")
    return kinds or {"operand"}


@lru_cache(maxsize=None)
def _edge_frames(m) -> tuple[frozenset, frozenset]:
    """(branch frames that a clock-edge test opens, then-branch frames of an if whose later arm is that test)."""
    edge, reset = set(), set()
    info = F.occ_info(m)
    for (ent, _n, _o), (_l, s, ctx) in info.items():
        fr = F.frames(ctx)
        if "EDGE_CHECK" in s and len(fr) >= 2:
            edge.add((ent, " in ".join(fr)))
            me = re.match(r"elsif branch (\d+)-\d+$", fr[0])
            if me:
                for (e2, _n2, _o2), (_l2, _s2, c2) in info.items():
                    f2 = F.frames(c2)
                    for i in range(len(f2) - 1):
                        mt = re.match(r"(?:then|elsif) branch (\d+)-\d+$", f2[i])
                        if e2 == ent and mt and int(mt.group(1)) < int(me.group(1)) and f2[i + 1:] == fr[1:]:
                            reset.add((ent, " in ".join(f2[i:])))
    return frozenset(edge), frozenset(reset)


def set_without_clock(m, ent, n) -> bool:
    """An assignment of n neither under a clock-edge test nor in a reset arm before it."""
    edge, reset = _edge_frames(m)
    for (e, nm, _o), (_l, s, ctx) in F.occ_info(m).items():
        if e != ent or nm != n or not set(s) & LHS:
            continue
        fr = F.frames(ctx)
        sufs = {" in ".join(fr[i:]) for i in range(len(fr))}
        if not any((ent, x) in edge or (ent, x) in reset for x in sufs):
            return True
    return False


def tags(m, ent, e: dict) -> list[str]:
    """role in RTL: tags from the fixed list, each one fact of the graph."""
    n = e["name"]
    fo, fi = element_flows(m, ent, n)
    names = {x["name"].lower() for x in G.file_graph(m)["closed_set"]["elements"].values() if x["entity"] == ent}
    t = []
    kinds_out = {f["kind"] for f in fo}
    if "clock" in kinds_out:
        t.append("clock")
    if "reset" in kinds_out:
        t.append("reset")
    for f in fo:
        if f["kind"] != "implicit":
            continue
        s = _sites_on(m, ent, n, set(f["lines"]))
        if "INDEX" in s:
            t.append("index")
        elif "CASE_EXPR" in s or (f["via"] == "SELECTS" and not s & {"IF_COND", "WHEN_COND"}):
            t.append("selector")
        else:
            t.append("condition")                    # if / elsif / when tests, comparisons, decisions via a variable
    for f in fo:
        if f["kind"] == "explicit":
            src = f.get("inherited from", n)
            if f["via"] == "CARRIES":
                t.append("copied")
            else:
                t += sorted(set().union(*(copy_kind(m, ent, src, ln, names) for ln in f["lines"]))) or ["operand"]
    if _instance_in(m, ent, n) or _instance_in(m, ent, n.split(".", 1)[0]) and "." in n:
        t.append("copied")                           # wired unchanged into an instance's input
    me = map_entries(m).get((ent, n), {})
    assigns = [ln for ln, s in occurrences(m).get((ent, n), []) if s & LHS]
    if any(f["kind"] == "clock" for f in fi):
        t.append("held on a clock edge")
    if any(f["kind"] == "reset" for f in fi):
        t.append("reset to a constant")
    if set_without_clock(m, ent, n):
        t.append("set without a clock")
    if _instance_out(m, ent, n):
        t.append("set by an instance")
    if assigns and not any(f["kind"] == "explicit" for f in fi) and not _instance_out(m, ent, n):
        t.append("set to constants only")            # no value moves in: every assignment gives a constant
    if e["dir"]:
        if e["dir"] in G.IN_DIRS:
            t.append("read" if (fo or _instance_in(m, ent, n)) else "not read")
        if e["dir"] in G.OUT_DIRS:
            t.append("undriven" if not (assigns or _instance_out(m, ent, n)) else
                     "tied to a constant" if "set to constants only" in t else "driven")
    if not fo and not fi and not flows(m)[2].get((ent, n)) and \
            all(s <= DECL | {"PROCESS_TRIG"} or not s for _ln, s in occurrences(m).get((ent, n), [])):
        t.append(TAG_UNUSED)
    return list(dict.fromkeys(t))                    # once each, in the order of the fixed list as found


def record_tags(own: list[str], fields: list[list[str]]) -> list[str]:
    """A record's tags: what the RTL does with the whole record (own), with the port and use tags taken from its
    fields: read if any field is read, driven if any field is driven, not used only if no field is used."""
    t = [x for x in own if x not in TAGS_PORT and x != TAG_UNUSED]
    ft = {x for f in fields for x in f}
    if "read" in ft or "not read" in ft:
        t.append("read" if ("read" in ft or "read" in own) else "not read")
    if ft & {"driven", "tied to a constant", "undriven"}:
        t.append("driven" if ("driven" in ft or "driven" in own) else
                 "tied to a constant" if "tied to a constant" in ft else "undriven")
    if all(TAG_UNUSED in f for f in fields) and TAG_UNUSED in own:
        t.append(TAG_UNUSED)
    return t


def counterparts(m, ent, n) -> dict:
    """Grouped: incoming and outgoing flows by kind, each partner with the RTL lines of the flow."""
    fo, fi = element_flows(m, ent, n)
    groups = {g: defaultdict(set) for g in GROUPS}
    for f in fi:
        g = {"explicit": "gets value from", "implicit": "decided by", "clock": "clocked by", "reset": "reset by"}[f["kind"]]
        groups[g][("element", f["source"])] |= set(f["lines"])
    for f in fo:
        g = {"explicit": "gives value to", "implicit": "decides", "clock": "clocks", "reset": "resets"}[f["kind"]]
        groups[g][("element", f["target"])] |= set(f["lines"])
    for p in _instance_in(m, ent, n):
        groups["gives value to"][("port", p["instance"], p["port"])] |= set(p["lines"])
    for p in _instance_out(m, ent, n):
        groups["gets value from"][("port", p["instance"], p["port"])] |= set(p["lines"])
    res = {}
    for g in GROUPS:
        items = []
        for k, ls in sorted(groups[g].items()):
            item = {"element": k[1]} if k[0] == "element" else {"instance": k[1], "port": k[2]}
            item["lines"] = sorted(ls)
            items.append(item)
        if items:
            res[g] = items
    return res


def signal_type(m, ent, e: dict, field_types: list[str] | None = None) -> str:
    """reg: every assignment waits for a clock edge. wire: assigned only without a clock edge, or driven by an
    instance's output. other: clocked in some generic settings and not in others (map storage 'mixed'), or never
    assigned. A record: reg or wire when all its used fields agree, else other."""
    if field_types is not None:
        used = [t for t in field_types if t]
        return used[0] if used and all(t == used[0] for t in used) else "other"
    st = map_entries(m).get((ent, e["name"]), {}).get("storage")
    if st == "edge":
        return "reg"
    if st == "none" or (st == "not assigned" and _instance_out(m, ent, e["name"])):
        return "wire"
    return "other"


def _lines(m, ent, n, record: bool) -> list[int]:
    """The profiler's lines. A field also gets the lines where its whole record is wired to an instance port (cpu 199:
    `frontend_o => frontend`) or copied whole to or from an element without fields (bus 367): its counterparts cite
    them, and the field moves there."""
    occ = occurrences(m).get((ent, n), [])
    if record:                                        # the record's own lines: where the whole record is named
        occ = [(ln, s) for ln, s in occ if s != frozenset({"FIELD_USE"})]
    ls = {ln for ln, _s in occ}
    if "." in n:
        ls |= {ln for p in flows(m)[2].get((ent, n), []) for ln in p["lines"]}
        fo, fi = element_flows(m, ent, n)
        ls |= {ln for f in fo + fi if f.get("inherited from") for ln in f["lines"]
               if ln in {x for x, _s in occurrences(m).get((ent, f["inherited from"]), [])}}
    return sorted(ls)


def entry(m, ent, e: dict, els: dict) -> dict:
    n = e["name"]
    port = bool(e["dir"])
    key = "port" if port else "signal"
    d = {key: n}
    if port:
        d["direction"] = e["dir"]
    fields = sorted((x for x in els.values() if x["entity"] == ent and x["field_of"] == n), key=lambda x: x["name"])
    if fields:
        d["record type"] = e.get("type")
    d["occurrence lines"] = _lines(m, ent, n, bool(fields))
    d["role in RTL"] = tags(m, ent, e)
    d["counterparts"] = counterparts(m, ent, n)
    if fields:
        fl = []
        for f in fields:
            fd = {"field": f["name"]}
            if port:
                fd["direction"] = f["dir"]
            else:
                fd["type"] = signal_type(m, ent, f)
            fd["occurrence lines"] = _lines(m, ent, f["name"], False)
            fd["role in RTL"] = tags(m, ent, f)
            fd["counterparts"] = counterparts(m, ent, f["name"])
            fl.append(fd)
        if not port:
            d["type"] = signal_type(m, ent, e, [x.get("type") for x in fl if TAG_UNUSED not in x["role in RTL"]])
        d["role in RTL"] = record_tags(d["role in RTL"], [x["role in RTL"] for x in fl])
        d["fields"] = fl
    elif not port:
        d["type"] = signal_type(m, ent, e)
    if not port:                                      # the user's key order: signal, type, lines, role, counterparts
        d = {k: d[k] for k in ("signal", "record type", "type", "occurrence lines", "role in RTL", "counterparts",
                               "fields") if k in d}
    return d


def closed_set(m) -> dict:
    """{"module name", "entity list": [{"entity name", "port list", "signal list"}]}; record fields nested."""
    els = G.file_graph(m)["closed_set"]["elements"]
    first = defaultdict(lambda: 10 ** 9)
    for (ent, n), occ in occurrences(m).items():
        for ln, s in occ:
            if s & DECL:
                first[(ent, n)] = min(first[(ent, n)], ln)
    ents = []
    for ent in sorted({e["entity"] for e in els.values()}, key=lambda x: min(first[(x, e["name"])] for e in els.values()
                                                                             if e["entity"] == x)):
        top = [e for e in els.values() if e["entity"] == ent and not e["field_of"]]
        top.sort(key=lambda e: (first[(ent, e["name"])], e["name"]))
        ents.append({"entity name": ent,
                     "port list": [entry(m, ent, e, els) for e in top if e["dir"]],
                     "signal list": [entry(m, ent, e, els) for e in top if not e["dir"]]})
    return {"module name": m, "entity list": ents}


# ------------------------------------------------------------------------- an independent name extraction ---
@lru_cache(maxsize=None)
def _record_types() -> dict:
    """{record type name: [field names]} from every RTL file, package included, comments removed."""
    out = {}
    for split in G.RTL:
        for f in sorted(G.RTL[split].glob("*.vhd")):
            t = re.sub(r"--[^\n]*", "", f.read_text(encoding="utf-8", errors="ignore"))
            for mm in re.finditer(r"\btype\s+(\w+)\s+is\s+record\b(.*?)\bend\s+record\b", t, re.I | re.S):
                names = []
                for part in mm.group(2).split(";"):
                    md = re.match(r"\s*([\w\s,]+?)\s*:", part)
                    if md:
                        names += [x.strip().lower() for x in md.group(1).split(",") if x.strip()]
                out.setdefault(mm.group(1).lower(), {})[f.stem] = names
    return out


def rtl_names(m) -> dict:
    """{entity: set of port and signal names, record fields expanded one level} read from the comment-stripped RTL
    with plain text patterns, without the closed-set parser: the self-test the closed set is compared with."""
    t = re.sub(r"--[^\n]*", "", (G.RTL[G.split_of(m)] / f"{m}.vhd").read_text(encoding="utf-8", errors="ignore"))
    recs = _record_types()

    def rec_fields(typ, scope_text):
        typ = typ.strip().lower()
        local = re.search(rf"\btype\s+{typ}\s+is\s+record\b(.*?)\bend\s+record\b", scope_text, re.I | re.S)
        if local:
            names = []
            for part in local.group(1).split(";"):
                md = re.match(r"\s*([\w\s,]+?)\s*:", part)
                if md:
                    names += [x.strip().lower() for x in md.group(1).split(",") if x.strip()]
            return names
        cand = recs.get(typ, {})
        return cand.get("neorv32_package") or (next(iter(cand.values())) if cand else None)

    out = defaultdict(set)
    for me in re.finditer(r"\bentity\s+(\w+)\s+is\b(.*?)\bend\s+(?:entity\s+)?\1?\s*;", t, re.I | re.S):
        ent, body = me.group(1), me.group(2)
        mp = re.search(r"\bport\s*\((.*)\)\s*;", body, re.I | re.S)
        for part in (mp.group(1).split(";") if mp else []):
            md = re.match(r"\s*([\w\s,]+?)\s*:\s*(in|out|inout|buffer)\s+([\w.]+)", part.strip(), re.I | re.S)
            if md:
                for n in [x.strip() for x in md.group(1).split(",") if x.strip()]:
                    out[ent].add(n)
                    for f in rec_fields(md.group(3), t) or []:
                        out[ent].add(f"{n}.{f}")
        ma = re.search(rf"\barchitecture\s+\w+\s+of\s+{ent}\s+is\b(.*?)(?=\barchitecture\s+\w+\s+of\b|\Z)", t, re.I | re.S)
        if ma:
            for ms in re.finditer(r"\bsignal\s+([\w\s,]+?)\s*:\s*([\w.]+)", ma.group(1), re.I):
                for n in [x.strip() for x in ms.group(1).split(",") if x.strip()]:
                    out[ent].add(n)
                    for f in rec_fields(ms.group(2), ma.group(1)) or []:
                        out[ent].add(f"{n}.{f}")
    return {k: {x.lower() for x in v} for k, v in out.items()}


# ------------------------------------------------------------------------------------------------ write ---
def manifest_entry(d: Path) -> dict:
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest()[:12] for f in sorted(d.iterdir()) if f.is_file()}


def write(modules=None, log=print) -> dict:
    mods = modules or [m for s in G.RTL for m in G.modules(s) if G.code_map(m) is not None]
    man = {"version": VERSION, "built": date.today().isoformat(),
           "sources": {"closed set and map": str(G.FIX.relative_to(G.ROOT).as_posix()),
                       "graph": G.GRAPH_VERSION, "rtl": "pio_diagram.rtl_text", "diagram": "pio_blocks.text(lines=False)" + ("" if ARROWS_KEY == "v1" else f", key {ARROWS_KEY}")},
           "modules": {}}
    for m in mods:
        d = OUT / G.split_of(m) / m
        d.mkdir(parents=True, exist_ok=True)
        (d / "rtl.txt").write_text(D.rtl_text(m), encoding="utf-8")
        (d / "diagram.txt").write_text(B.text(m, lines=False, key=ARROWS_KEY), encoding="utf-8")
        (d / "closed_set.json").write_text(json.dumps(closed_set(m), indent=1), encoding="utf-8")
        man["modules"][m] = {"split": G.split_of(m), "files": manifest_entry(d)}
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    log(f"   wrote {len(mods)} modules to {OUT}")
    return man


# ------------------------------------------------------------------------------------------------ checks ---
def _find(cs, name):
    for e in cs["entity list"]:
        for lst in ("port list", "signal list"):
            for x in e[lst]:
                if x.get("port", x.get("signal")) == name:
                    return x
                for f in x.get("fields", []):
                    if f["field"] == name:
                        return f
    return None


def _cp(x, group):
    return {(c.get("element") or f"{c.get('instance')}:{c.get('port')}"): c["lines"] for c in x["counterparts"].get(group, [])}


def selftest(log=print) -> bool:
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        log(f"   {'ok  ' if cond else 'FAIL'} {label}")
    w = closed_set("neorv32_wdt")
    # hand-read data/RTL_data/neorv32_wdt.vhd 48-54 (record ctrl_t, signal ctrl), 71-117, 122-137, 140, 144, 149-161
    ctrl = _find(w, "ctrl")
    check(f"wdt 54: ctrl is a signal of record type ctrl_t, type reg, own lines [54] ({ctrl and (ctrl.get('record type'), ctrl.get('type'), ctrl.get('occurrence lines'))})",
          ctrl and ctrl.get("record type") == "ctrl_t" and ctrl.get("type") == "reg" and ctrl.get("occurrence lines") == [54]
          and [f["field"] for f in ctrl["fields"]] == ["ctrl.enable", "ctrl.lock", "ctrl.strict", "ctrl.timeout"])
    en = _find(w, "ctrl.enable")
    check(f"wdt ctrl.enable lines 75 94 95 109 130 131 140 155 156 ({en['occurrence lines']})",
          {75, 94, 95, 109, 130, 131, 140, 155, 156} <= set(en["occurrence lines"]))
    check(f"wdt ctrl.enable tags ({en['role in RTL']})",
          set(en["role in RTL"]) == {"held on a clock edge", "reset to a constant", "condition", "copied", "operand"})
    check("wdt 94: ctrl.enable gets its value from bus_req_i.data at 94",
          _cp(en, "gets value from") == {"bus_req_i.data": [94]})
    check(f"wdt 90-93: ctrl.enable decided by bus_req_i.stb 90, rw 91, addr 92, ctrl.lock 93 ({_cp(en, 'decided by')})",
          _cp(en, "decided by") == {"bus_req_i.stb": [90], "bus_req_i.rw": [91], "bus_req_i.addr": [92], "ctrl.lock": [93]})
    check(f"wdt 95 109 130 140 155 156: ctrl.enable gives its value ({_cp(en, 'gives value to')})",
          _cp(en, "gives value to") == {"ctrl.lock": [95], "bus_rsp_o.data": [109], "cnt_started": [130],
                                        "clkgen_en_o": [140], "hw_rst_timeout": [155], "hw_rst_access": [156]})
    check("wdt 131: ctrl.enable decides cnt; 81/73: clocked by clk_i, reset by rstn_sys_i",
          _cp(en, "decides") == {"cnt": [131]} and _cp(en, "clocked by") == {"clk_i": [81]}
          and _cp(en, "reset by") == {"rstn_sys_i": [73]})
    ct = _find(w, "cnt_timeout")
    check(f"wdt 144: cnt_timeout is a wire set without a clock, decided by cnt, cnt_started, ctrl.timeout ({ct['type']}, {ct['role in RTL']})",
          ct["type"] == "wire" and "set without a clock" in ct["role in RTL"]
          and set(_cp(ct, "decided by")) == {"cnt", "cnt_started", "ctrl.timeout"} and _cp(ct, "gives value to") == {"hw_rst_timeout": [155]})
    cnt = _find(w, "cnt")
    check(f"wdt 134: cnt is a reg whose value comes from cnt; decided by ctrl.enable, reset_wdt (131), cnt_inc (133) ({_cp(cnt, 'gets value from')}, {_cp(cnt, 'decided by')})",
          cnt["type"] == "reg" and _cp(cnt, "gets value from") == {"cnt": [134]}
          and _cp(cnt, "decided by") == {"ctrl.enable": [131], "reset_wdt": [131], "cnt_inc": [133]})
    clk = _find(w, "clk_i")
    check(f"wdt clk_i: a read input with the clock tag, clocking at 81 128 154 170 ({clk['role in RTL']})",
          clk["direction"] == "in" and set(clk["role in RTL"]) == {"clock", "read"}
          and {ln for c in clk["counterparts"]["clocks"] for ln in c["lines"]} == {81, 128, 154, 170})
    bq, bo = _find(w, "bus_req_i"), _find(w, "bus_rsp_o")
    check(f"wdt 24/25: the record ports take read / driven from their fields ({bq['role in RTL']}, {bo['role in RTL']})",
          bq["role in RTL"] == ["read"] and "driven" in bo["role in RTL"])
    check(f"wdt 144: cnt_timeout <= '1' when ... else '0' is set to constants only ({ct['role in RTL']})",
          "set to constants only" in ct["role in RTL"])
    # the closed-set review of 2026-10-10 (inputs/v1/_review_result.json), each against the lines the reviewers cited
    bus = closed_set("neorv32_bus")
    am = next(f for e in bus["entity list"] if e["entity name"] == "neorv32_bus_switch" for x in e["port list"]
              for f in x.get("fields", []) if f["field"] == "a_req_i.amoop")
    check(f"bus 142: a_req_i.amoop moves unchanged into x_req_o.amoop: copied, not operand ({am['role in RTL']})",
          "copied" in am["role in RTL"] and "operand" not in am["role in RTL"])
    bd = next(f for e in bus["entity list"] if e["entity name"] == "neorv32_bus_gateway" for x in e["port list"]
              for f in x.get("fields", []) if f["field"] == "b_rsp_i.data")
    check(f"bus 367: b_rsp_i.data, copied whole into port_rsp(1), is read and gives its value to port_rsp ({bd['role in RTL']}, {_cp(bd, 'gives value to')})",
          {"read", "copied"} <= set(bd["role in RTL"]) and _cp(bd, "gives value to").get("port_rsp") == [367])
    md = closed_set("neorv32_cpu_cp_muldiv")
    check("muldiv 145: valid_o <= '1' when ... else '0' is set to constants only",
          "set to constants only" in _find(md, "valid_o")["role in RTL"])
    hs = closed_set("neorv32_hwspinlock")
    check("hwspinlock 51: sel <= '1' when ... else '0' is set to constants only",
          "set to constants only" in _find(hs, "sel")["role in RTL"])
    ua = closed_set("neorv32_uart")
    check(f"uart 154-155: bus_rsp_o is assigned whole only in the reset arm: not 'set without a clock' ({_find(ua, 'bus_rsp_o')['role in RTL']})",
          "set without a clock" not in _find(ua, "bus_rsp_o")["role in RTL"])
    pm = closed_set("neorv32_cpu_pmp")
    lines134 = [ln for g in _find(pm, "pmpcfg")["counterparts"].values() for c in g
                if c.get("element") == "ctrl_i.csr_wdata" for ln in c["lines"]]
    check(f"pmp 133-134: ctrl_i.csr_wdata feeds mode_v at 133; 134 only tests mode_v ({lines134})",
          133 in lines134 and 134 not in lines134)
    dt = closed_set("neorv32_debug_dtm")
    check("debug_dtm 111: tap_sync.tdi <= tap_sync.tdi_ff(2): tdi_ff is copied",
          "copied" in _find(dt, "tap_sync.tdi_ff")["role in RTL"])
    check("muldiv 300: div.res_u is computed with in one arm and copied in the other: both tags",
          {"copied", "operand"} <= set(_find(md, "div.res_u")["role in RTL"]))
    sy = closed_set("neorv32_sys")
    c2 = _find(sy, "cnt2")["role in RTL"]
    check(f"sys 140-147: cnt2 is only in 'cnt(k) and (not cnt2(k))': operand, not copied ({c2})",
          "operand" in c2 and "copied" not in c2)
    tw = closed_set("neorv32_twi")
    check("twi 408: twi_sda_i reaches io_con.sda_in through type conversions only: copied",
          "copied" in _find(tw, "twi_sda_i")["role in RTL"])
    cu = closed_set("neorv32_cpu")
    check(f"cpu 199: frontend.compr's lines include the port map 'frontend_o => frontend' ({_find(cu, 'frontend.compr')['occurrence lines']})",
          199 in _find(cu, "frontend.compr")["occurrence lines"])
    check("hwspinlock 61/64: bus_rsp_o.err only ever gets constants: tied to a constant",
          "tied to a constant" in _find(hs, "bus_rsp_o.err")["role in RTL"])
    cf = closed_set("neorv32_cpu_cp_cfu")
    check("cfu 232-233: xtea.opb is a value arm of tmp_a and tmp_b: copied",
          "copied" in _find(cf, "xtea.opb")["role in RTL"])
    ben = _find(w, "bus_req_i.ben")
    check(f"wdt 24: bus_req_i.ben is declared only: not read, not used ({ben['role in RTL']})",
          set(ben["role in RTL"]) == {"not read", TAG_UNUSED})
    err = _find(w, "bus_rsp_o.err")
    check(f"wdt 74/84: bus_rsp_o.err is set to constants only, held on the edge, reset to a constant: tied ({err['role in RTL']})",
          {"set to constants only", "held on a clock edge", "reset to a constant", "tied to a constant"} <= set(err["role in RTL"])
          and "driven" not in err["role in RTL"])
    ro = _find(w, "rstn_o")
    check(f"wdt 161: rstn_o is driven from hw_rst_timeout and hw_rst_access ({_cp(ro, 'gets value from')})",
          _cp(ro, "gets value from") == {"hw_rst_timeout": [161], "hw_rst_access": [161]} and "driven" in ro["role in RTL"])
    # hand-read data/RTL_data/neorv32_spi.vhd 218-236: rx_fifo.wdata wired into rx_fifo_inst's wdata_i at 234
    s = closed_set("neorv32_spi")
    wd = _find(s, "rx_fifo.wdata")
    check(f"spi 234: rx_fifo.wdata gives its value to rx_fifo_inst port wdata_i ({_cp(wd, 'gives value to')})",
          _cp(wd, "gives value to").get("rx_fifo_inst:wdata_i") == [234])
    # the independent extraction: every module, closed-set names = names read from the RTL text
    bad = {}
    for split in G.RTL:
        for m in G.modules(split):
            if G.code_map(m) is None:
                continue
            els = G.file_graph(m)["closed_set"]["elements"]
            cs = defaultdict(set)
            for e in els.values():
                cs[e["entity"]].add(e["name"].lower())
            rn = rtl_names(m)
            for ent in set(cs) | set(rn):
                a, b = cs.get(ent, set()), rn.get(ent, set())
                if a != b:
                    bad[(m, ent)] = (sorted(a - b)[:5], sorted(b - a)[:5])
    check(f"closed set = names read from the comment-stripped RTL, all files ({len(bad)} entities differ: {list(bad.items())[:3]})",
          not bad)
    return ok


MIRROR = {"gives value to": "gets value from", "decides": "decided by", "clocks": "clocked by", "resets": "reset by"}


def consistency(m) -> dict:
    """Checks on the written closed set of one module, against the closed set and the diagram it goes with."""
    d = OUT / G.split_of(m) / m
    cs = json.loads((d / "closed_set.json").read_text(encoding="utf-8"))
    els = G.file_graph(m)["closed_set"]["elements"]
    seen, entries = defaultdict(int), {}
    for e in cs["entity list"]:
        for lst in ("port list", "signal list"):
            for x in e[lst]:
                for y in [x] + x.get("fields", []):
                    nm = y.get("port") or y.get("signal") or y.get("field")
                    seen[(e["entity name"], nm)] += 1
                    entries[(e["entity name"], nm)] = y
    want = {(e["entity"], e["name"]) for e in els.values()}
    res = {"elements": len(want), "missing": sorted(want - set(seen)), "extra": sorted(set(seen) - want),
           "listed twice": sorted(k for k, v in seen.items() if v > 1)}
    unknown, asym = [], []
    for (ent, nm), y in entries.items():
        for g, items in y["counterparts"].items():
            for it in items:
                if "element" in it:
                    if (ent, it["element"]) not in want:
                        unknown.append((ent, nm, g, it["element"]))
                    if g in MIRROR or g in MIRROR.values():
                        back = MIRROR.get(g) or next(k for k, v in MIRROR.items() if v == g)
                        other = entries.get((ent, it["element"]), {}).get("counterparts", {}).get(back, [])
                        if not any(o.get("element") in (nm, nm.split(".", 1)[0]) and o["lines"] == it["lines"]
                                   for o in other) and not any(o.get("element") == nm for o in
                                   entries.get((ent, it["element"].split(".", 1)[0]), {}).get("counterparts", {}).get(back, [])):
                            asym.append((ent, nm, g, it["element"]))
    outside = [(ent, nm, g, ln) for (ent, nm), y in entries.items()
               for g in ("gives value to", "decides", "clocks", "resets") for it in y["counterparts"].get(g, [])
               for ln in it["lines"] if ln not in y["occurrence lines"]]
    res["outgoing counterpart lines not among the element's lines"] = outside[:10]
    res["counterparts not in the closed set"] = unknown[:10]
    res["counterparts without the mirror entry"] = asym[:10]
    res["counts"] = {"counterparts not in the closed set": len(unknown), "without mirror": len(asym)}
    # every element the diagram names is in the closed set
    names = {n for (_e, n) in want}
    dn = set()
    for u in B.diagram(m)["units"]:
        for b in u["blocks"]:
            dn |= set(b["members"]) | set(b["clock"]) | set(b["reset"])
        for a in u["arrows"]:
            for y, x, _ in a["via"]:
                dn.add(y)
    kids = {c for c, _s in B.instance_entity(m).values()}
    formals = {n for (c, n) in G.port_dir() if c in kids}
    res["diagram names not in the closed set"] = sorted(n for n in dn if n not in names and n not in formals)
    tagged = [y for y in entries.values()]
    res["types"] = dict(sorted(((t, sum(1 for y in tagged if y.get("type") == t)) for t in ("reg", "wire", "other"))))
    res["ok"] = not (res["missing"] or res["extra"] or res["listed twice"] or unknown or asym or outside
                     or res["diagram names not in the closed set"])
    return res


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    assert selftest(), "self-test failed: nothing written"
    write()
    bad = {m: r for m in json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))["modules"]
           if not (r := consistency(m))["ok"]}
    print(f"   consistency: {'all modules pass' if not bad else bad}")
