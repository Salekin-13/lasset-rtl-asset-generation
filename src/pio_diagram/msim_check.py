"""An independent check of the block diagrams (pio_blocks.py) with ModelSim: who drives and who reads each element.

pio_blocks builds the diagram from the relationship map, which an occurrence parser and a pair builder made from the
RTL. ModelSim builds its own design from the same RTL: `vcom` compiles it, `vsim` elaborates it under one setting of
the generics, and two commands report, per signal or record field, the processes that drive it (`drivers`) and the
processes that read it (`readers`), including processes inside instances reached through a port map. Nothing of the
map is used. Mapping a tool process to a diagram block uses only the RTL's labels and line numbers.

What it checks, per module and generic setting:
  members   every block the tool names as a driver of an element holds that element in the diagram, and every
            diagram block that the tool elaborates and that holds an element drives it (record fields one by one);
  arrows    the tool's block edges: element e driven in block A and read in block B (A != B), an input port read in
            B, an output port driven in B. Every tool edge must be a diagram arrow, or e must be B's clock or reset in
            the diagram. Every diagram arrow whose two ends the tool elaborates in some setting must be a tool edge in
            some setting.
What it cannot check: the arrow kind (value or decision) and the evidence lines; a reader that reads a signal without
any flow (only in a sensitivity list, or for a report) shows as a tool edge with no arrow; blocks only built under
generic settings that were not tried stay untested and are counted.

Outputs  src/pio_diagram/msim/<module>/<root>__<setting>.txt  raw tool answers;  src/pio_diagram/msim/result.json
Run      python src/pio_diagram/msim_check.py [module ...]      (default: the 15 tuning modules)
"""
from __future__ import annotations

import itertools
import json
import re
import subprocess
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pio_blocks as B   # noqa: E402
import pio_flowfix as F  # noqa: E402
import pio_graph as G    # noqa: E402

MSIM = Path("E:/general_programme_files/modelsim_ase/win32aloem")
OUT = HERE / "msim"
LIB = "neorv32"


# ------------------------------------------------------------------------------------------------ compile ---
def _run(args, cwd=OUT, timeout=900) -> str:
    r = subprocess.run([str(MSIM / args[0])] + args[1:], cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return r.stdout + r.stderr


def compile_all(log=print) -> dict:
    """Every RTL file of both splits into library neorv32, package first, then repeated passes until nothing more
    compiles (direct entity instantiation needs the child compiled first)."""
    OUT.mkdir(parents=True, exist_ok=True)
    if not (OUT / LIB).exists():
        _run(["vlib", LIB])
    _run(["vmap", LIB, LIB])
    files = sorted(set(G.RTL["tuning"].glob("*.vhd")) | set(G.RTL["heldout"].glob("*.vhd")))
    pkg = [f for f in files if f.name == "neorv32_package.vhd"]
    rest = [f for f in files if f not in pkg]
    out = _run(["vcom", "-2008", "-work", LIB, "-quiet", str(pkg[0])])
    if "Error" in out:
        raise RuntimeError("package did not compile:\n" + out[-2000:])
    # imem and boot_rom use memory-image packages that NEORV32's image generator writes; the corpus has none. These
    # stand-ins hold four placeholder words and no logic, so they change no driver or reader.
    stubs = OUT / "_stubs"
    stubs.mkdir(exist_ok=True)
    for pkg_name, pre in (("neorv32_application_image", "application"), ("neorv32_bootloader_image", "bootloader")):
        f = stubs / f"{pkg_name}.vhd"
        f.write_text(f"library ieee;\nuse ieee.std_logic_1164.all;\nlibrary neorv32;\nuse neorv32.neorv32_package.all;\n"
                     f"package {pkg_name} is\n  constant {pre}_init_size_c : natural := 16;\n"
                     f"  constant {pre}_init_image_c : mem32_t := (x\"00000013\", x\"00000013\", x\"00000013\", "
                     f"x\"00000013\");\nend {pkg_name};\n", encoding="utf-8")
        o = _run(["vcom", "-2008", "-work", LIB, "-quiet", str(f)])
        if "Error" in o:
            raise RuntimeError(f"{pkg_name} stand-in did not compile:\n" + o[-1500:])
    pending, done = rest, []
    while pending:
        failed = []
        for f in pending:
            o = _run(["vcom", "-2008", "-work", LIB, "-quiet", str(f)])
            (failed if re.search(r"\*\* Error", o) else done).append(f)
        if len(failed) == len(pending):
            break
        pending = failed
    log(f"   compiled {len(done) + 1} files; failed: {[f.name for f in pending]}")
    return {"compiled": len(done) + 1, "failed": [f.name for f in pending]}


# ------------------------------------------------------------------------------------------------ generics ---
def generics(m, ent) -> list[tuple[str, str, str]]:
    """[(name, type, default)] of an entity's generic clause, from the RTL text."""
    t = re.sub(r"--[^\n]*", "", (G.RTL[G.split_of(m)] / f"{m}.vhd").read_text(encoding="utf-8", errors="ignore"))
    me = re.search(rf"\bentity\s+{ent}\s+is(.*?)\bport\s*\(", t, re.I | re.S)
    mg = re.search(r"\bgeneric\s*\((.*)\)\s*;", me.group(1), re.I | re.S) if me else None
    out = []
    for part in (mg.group(1).split(";") if mg else []):
        mm = re.match(r"\s*([\w\s,]+?)\s*:\s*([^:=]+?)\s*(?::=\s*(.+))?\s*$", part.strip(), re.S)
        if mm:
            for n in mm.group(1).split(","):
                out.append((n.strip(), " ".join(mm.group(2).split()), (mm.group(3) or "").strip()))
    return out


def _value(name, typ, high: bool) -> str | None:
    t = typ.lower()
    if t == "boolean":
        return "true" if high else "false"
    if t.startswith("string"):
        return '"neorv32.log"'
    mv = re.match(r"std_u?logic_vector\((\d+) downto 0\)", t)
    if mv:
        return '"' + ("1" if high else "0") * (int(mv.group(1)) + 1) + '"'
    if t.startswith(("natural", "integer", "positive")):
        mr = re.search(r"range\s+(\S+)\s+to\s+(\S+)", t)
        lo = int(eval(mr.group(1))) if mr else (1 if t.startswith("positive") else 0)
        hi = int(eval(mr.group(2).replace("**", "**"))) if mr else 1 << 16
        pick = {True: 4, False: 1}[high]
        if re.search(r"width", name, re.I):
            pick = 64 if high else 32
        if re.search(r"size|blocks", name, re.I):
            pick = 4096 if high and "imem" in name.lower() else (16 if high else 4)
        if re.search(r"granularity", name, re.I):
            pick = 4
        if re.search(r"timeout", name, re.I):
            pick = 16 if high else 0                  # 0 switches the timeout logic off (xbus 130)
        return str(min(max(pick, lo), hi))
    return None


def settings(m, ent, limit=16) -> list[dict]:
    """Generic settings to elaborate: all booleans true with larger numbers, all false with small numbers, and, when an
    entity has at most four booleans, every combination of them (both number choices)."""
    gs = [g for g in generics(m, ent)]
    if not gs:
        return [{}]
    bools = [n for n, t, d in gs if t.lower() == "boolean"]
    out = []
    for high in (True, False):
        out.append({n: v for n, t, d in gs if (v := _value(n, t, high)) is not None})
    if 0 < len(bools) <= 4:
        for combo in itertools.product(("true", "false"), repeat=len(bools)):
            for high in (True, False):
                s = {n: v for n, t, d in gs if (v := _value(n, t, high)) is not None}
                s.update(dict(zip(bools, combo)))
                if s not in out:
                    out.append(s)
    return out[:limit]


def flip_settings(m, ent) -> list[dict]:
    """For entities with more than four booleans: all true but one, and all false but one (crypto: aes_disabled
    with block_cyphers_enabled needs one cipher off and another on)."""
    gs = generics(m, ent)
    bools = [n for n, t, d in gs if t.lower() == "boolean"]
    if len(bools) <= 4:
        return []
    out = []
    for high in (True, False):
        base = {n: v for n, t, d in gs if (v := _value(n, t, high)) is not None}
        for b in bools:
            out.append({**base, b: "false" if high else "true"})
    return out


# ------------------------------------------------------------------------------------------------ the tool ---
def _elements(m, ent) -> list[str]:
    els = G.file_graph(m)["closed_set"]["elements"]
    return sorted(e["name"] for e in els.values() if e["entity"] == ent)


def dump(m, ent, setting: dict, tag: str) -> tuple[str, str]:
    """Elaborate ent under setting; ask drivers and readers of every closed-set element of ent. -> (raw text, log)."""
    d = OUT / m
    d.mkdir(parents=True, exist_ok=True)
    raw = d / f"{ent}__{tag}.txt"
    do = d / f"{ent}__{tag}.do"
    lines = [f'set f [open "{raw.as_posix()}" w]', f'puts $f "INSTANCES: [find instances -r /{ent}/*]"']
    for n in _elements(m, ent):
        p = f"/{ent}/{n}"
        lines += [f'puts $f "@@@ {n}"',
                  f'if {{[catch {{set r [readers {p}]}} e]}} {{ puts $f "READERS-ERROR: $e" }} else {{ puts $f $r }}',
                  f'if {{[catch {{set r [drivers {p}]}} e]}} {{ puts $f "DRIVERS-ERROR: $e" }} else {{ puts $f $r }}']
    lines += ["close $f", "quit -f"]
    do.write_text("\n".join(lines), encoding="utf-8")
    args = ["vsim", "-c", "-voptargs=+acc"] + [f"-g{k}={v}" for k, v in setting.items()] + [f"{LIB}.{ent}", "-do",
                                                                                              do.as_posix()]
    log = _run(args, timeout=1800)
    if not raw.exists() or "Error loading design" in log:
        return "", log
    return raw.read_text(encoding="utf-8", errors="replace"), log


def parse(raw: str) -> tuple[dict, list[str]]:
    """-> ({element: {"D": set(paths), "R": set(paths)}}, instance paths)."""
    out = defaultdict(lambda: {"D": set(), "R": set(), "S": set()})
    inst = re.findall(r"\{?(/[^\s{}]+) \(", raw.split("\n", 1)[0])
    cur = None
    for line in raw.splitlines():
        mm = re.match(r"@@@ (\S+)", line)
        if mm:
            cur = mm.group(1)
            out[cur]
            continue
        if cur is None:
            continue
        mr = re.match(r"\s*Reader : (\S+)", line)
        if mr:
            out[cur]["R"].add(mr.group(1))
            continue
        ms = re.match(r"\s*Signal : (\S+)", line)          # the net continues into a port of an instance
        if ms:
            out[cur]["S"].add(ms.group(1))
            continue
        md = re.search(r": Driver (\S+)", line)
        if md:
            out[cur]["D"].add(md.group(1))
    return dict(out), inst


# ------------------------------------------------------------------------------------------------ mapping ---
@lru_cache(maxsize=None)
def _lhs_by_line(m) -> dict:
    """{(entity, line): diagram block id of the assignment(s) on that line}."""
    out = {}
    for (ent, name, oid), (ln, sites, ctx) in B.occ_context(m).items():
        b = B.statement_block(m, ent, name, oid)
        if b:
            out.setdefault((ent, ln), f"{b[0]}:{b[1]}")
    return out


@lru_cache(maxsize=None)
def _stmts_on_line(m) -> dict:
    """{(entity, line): diagram blocks of the assignments that start on that line, in the order they are written}
    (bus 366: `a_req_o <= port_req(0); port_rsp(0) <= a_rsp_i;`)."""
    src = F.source_lines(m)
    found = defaultdict(lambda: defaultdict(set))       # (entity, line) -> position of the target -> blocks
    for (ent, name, oid), (ln, sites, ctx) in B.occ_context(m).items():
        b = B.statement_block(m, ent, name, oid)
        if not b:
            continue
        base = name.split(".")[0]
        hit = re.search(rf"\b{re.escape(base)}\b[^;]*?<=", src.get(ln, ""), re.I)
        if hit:
            found[(ent, ln)][hit.start()].add(f"{b[0]}:{b[1]}")
    return {k: [v[p] for p in sorted(v)] for k, v in found.items()}


def _stmt_line(m, ent, n: int) -> int:
    """The line where the statement holding line n starts its target: a selected assignment is named by the tool
    after the line of its first choice (cpu_control 1062-1065: `with ... select csr.wdata <=` then 1063)."""
    src, k = F.source_lines(m), n
    while (ent, k) not in _stmts_on_line(m) and k - 1 in src and ";" not in src[k - 1] and n - k < 12:
        k -= 1
    return k if (ent, k) in _stmts_on_line(m) else n


def blocks_of(m, ent, path: str, elem: str | None = None) -> set:
    """block_of as a set: a statement that assigns a whole record is one block per field in the diagram. With elem
    (a driver), only the block that assigns elem."""
    leaf = re.sub(r"\(.*\)$", "", path.strip("/").split("/")[-1])
    ml = re.match(r"line__(\d+)(?:__(\d+))?$", leaf)
    comps = [re.sub(r"\(.*\)$", "", c) for c in path.strip("/").split("/")[1:]]
    if ml and not any(c in B.instance_entity(m) for c in comps) and not _process_ids(m).get((ent, int(ml.group(1)))):
        order = _stmts_on_line(m).get((ent, _stmt_line(m, ent, int(ml.group(1)))), [])
        k = int(ml.group(2) or 0)
        s = set(order[k]) if k < len(order) else set()
        if elem and s:
            s = {b for b in s if b == f"logic:{ent}:{elem}"} or s
        return s
    b = block_of(m, ent, path)
    return {b} if b else set()


@lru_cache(maxsize=None)
def _process_ids(m) -> dict:
    """{(entity, label or start line): process block id}"""
    out = {}
    for (ent, name, oid), (ln, sites, ctx) in B.occ_context(m).items():
        for f in B._frames(ctx):
            mm = re.match(r"process\s+(\w+)\s+(\d+)-\d+$", f)
            if mm:
                out.setdefault((ent, mm.group(1)), set()).add(f"process:{ent}:{mm.group(1)}@{mm.group(2)}")
            mm = re.match(r"process\s+(\d+)-\d+$", f)
            if mm:
                out.setdefault((ent, int(mm.group(1))), set()).add(f"process:{ent}:process@{mm.group(1)}")
    return out


def block_of(m, ent, path: str) -> str | None:
    """A tool process path (/top/[gen(i)/...]/leaf) -> the diagram block it belongs to, or None."""
    comps = [re.sub(r"\(.*\)$", "", c) for c in path.strip("/").split("/")[1:]]
    labels = B.instance_entity(m)
    for c in comps[:-1] if len(comps) > 1 else []:
        if c in labels:
            return f"inst:{c}"
    if comps and comps[0] in labels:
        return f"inst:{comps[0]}"
    if not comps:
        return None
    leaf = comps[-1]
    ml = re.match(r"line__(\d+)(?:__(\d+))?$", leaf)      # line__N__k: the statement after k others on line N
    if ml:
        n, k = int(ml.group(1)), int(ml.group(2) or 0)
        ids = _process_ids(m).get((ent, n))
        if ids:
            return sorted(ids)[0]
        order = _stmts_on_line(m).get((ent, _stmt_line(m, ent, n)), [])
        return sorted(order[k])[0] if k < len(order) else _lhs_by_line(m).get((ent, n))
    ids = _process_ids(m).get((ent, leaf))
    if ids:
        if len(ids) == 1:
            return next(iter(ids))
        # one label in several generate branches (imem: four mem_access): the one inside the generate the path names
        hit = sorted(i for i in ids if len(comps) > 1 and comps[-2] in _process_gens(m).get(i, set()))
        return hit[0] if len(hit) == 1 else None
    return None


@lru_cache(maxsize=None)
def _process_gens(m) -> dict:
    """{process block id: labels of the generate statements around it}"""
    out = defaultdict(set)
    for (ent, name, oid), (ln, sites, ctx) in B.occ_context(m).items():
        fr = B._frames(ctx)
        pid = None
        for f in fr:
            mm = re.match(r"process\s+(\w+)\s+(\d+)-\d+$", f)
            if mm:
                pid = f"process:{ent}:{mm.group(1)}@{mm.group(2)}"
            mm = re.match(r"process\s+(\d+)-\d+$", f)
            if mm:
                pid = f"process:{ent}:process@{mm.group(1)}"
        if pid:
            out[pid] |= {mm.group(1) for f in fr if (mm := re.match(r"generate\s+(\w+)\s+\d+-\d+$", f))}
    return dict(out)


def _alias(m, ent, b):
    """logic:<ent>:<x> where x (or the record it is a field of) is an output port of ent -> that port's node."""
    if not b or not b.startswith("logic:"):
        return b
    els = G.file_graph(m)["closed_set"]["elements"]
    e2, x = b.split(":", 2)[1:]
    e = els.get(f"{e2}:{x}") or els.get(f"{e2}:{x.split('.')[0]}")
    if e and e2 == ent and e["top_level"] and e["dir"] in G.OUT_DIRS:
        return B.port_node(e)
    return b


# ------------------------------------------------------------------------------------------------ compare ---
def diagram_view(m, ent) -> dict:
    """The diagram unit of root ent: arrows {(src, dst)}, members {element: set(block)}, clocking {block: set}."""
    d = B.diagram(m)
    u = next(x for x in d["units"] if x["root"] == ent)
    arrows = {(a["src"], a["dst"]) for a in u["arrows"]}
    # source elements per arrow, as the tool would name them: an output port's own marker pair is not a read, and a
    # port-map pair into an instance names the parent's element
    sources = defaultdict(set)
    for a in u["arrows"]:
        for y, x, _ls in a["via"]:
            if not (y == x and a["dst"].startswith("out:")) and not (a["src"].startswith("inst:") and a["dst"].startswith("out:")):
                sources[(a["src"], a["dst"])].add(y)
    clk = {b["id"]: set(b["clock"]) | set(b["reset"]) for b in u["blocks"]}
    eb = B.element_blocks(m)
    els = G.file_graph(m)["closed_set"]["elements"]
    names = {k.split(":", 1)[1] for k in els if k.startswith(ent + ":")}
    members = {n.split(":", 1)[1]: set(bs) for n, bs in eb.items() if n.split(":", 1)[0] == ent
               and not any(x.startswith(n.split(":", 1)[1] + ".") for x in names)}     # records: field by field
    return {"arrows": arrows, "members": members, "clocking": clk, "blocks": {b["id"] for b in u["blocks"]},
            "sources": dict(sources)}


def _span(m, ent, path: str) -> list[int] | None:
    """RTL lines of the statement a tool reader path stands for: a concurrent statement (line__N to its ';'), a
    process (its line range), or an instance (its label line to the end of its port map). None: unknown."""
    src = F.source_lines(m)
    comps = [re.sub(r"\(.*\)$", "", c) for c in path.strip("/").split("/")[1:]]
    labels = B.instance_entity(m)
    for c in comps:
        if c in labels:
            start = next((i for i, t in sorted(src.items()) if re.match(rf"\s*{c}\s*:", t)), None)
            if start is None:
                return None
            end, seen_map = start, False
            while end in src:
                seen_map |= bool(re.search(r"\bport\s+map\b", src[end], re.I))
                if seen_map and ";" in src[end]:
                    break
                end += 1
            return list(range(start, end + 1))
    leaf = comps[-1] if comps else ""
    ml = re.match(r"line__(\d+)(?:__\d+)?$", leaf)
    if ml:
        n = int(ml.group(1))
        ids = _process_ids(m).get((ent, n))
        if not ids:
            end = n
            while end in src and ";" not in src[end]:
                end += 1
            return list(range(n, end + 1))
        leaf_id = sorted(ids)[0]
    else:
        leaf_id = block_of(m, ent, path)
    if leaf_id and leaf_id.startswith("process:"):
        rng = _process_range(m).get(leaf_id)
        return list(range(rng[0], rng[1] + 1)) if rng else None
    return None


@lru_cache(maxsize=None)
def _process_range(m) -> dict:
    out = {}
    for (ent, name, oid), (ln, sites, ctx) in B.occ_context(m).items():
        for f in B._frames(ctx):
            mm = re.match(r"process\s+(\w+)\s+(\d+)-(\d+)$", f)
            if mm:
                out[f"process:{ent}:{mm.group(1)}@{mm.group(2)}"] = (int(mm.group(2)), int(mm.group(3)))
            mm = re.match(r"process\s+(\d+)-(\d+)$", f)
            if mm:
                out[f"process:{ent}:process@{mm.group(1)}"] = (int(mm.group(1)), int(mm.group(2)))
    return out


def _names_field(m, ent, path: str, n: str) -> bool:
    """ModelSim lists readers per signal, so a reader of any field of a record is listed for every field. Keep the
    reader of record field base.f only if its statement's text names base.f, or uses base whole (no '.' after it)."""
    if "." not in n:
        return True
    lines = _span(m, ent, path)
    if lines is None:
        return True
    src = F.source_lines(m)
    text = " ".join(src.get(i, "") for i in lines)
    text = re.sub(r"\bprocess\s*\([^()]*\)", "process", text, flags=re.I)   # a sensitivity list is no read
    base, field = n.split(".", 1)
    return bool(re.search(rf"\b{re.escape(base)}\s*(?:\([^()]*\))?\s*\.\s*{re.escape(field)}\b", text, re.I)
                or re.search(rf"\b{re.escape(base)}\b(?!\s*(?:\([^()]*\))?\s*\.)", text, re.I))


def tool_view(m, ent, parsed: dict) -> dict:
    els = G.file_graph(m)["closed_set"]["elements"]
    edges, members, unmapped = defaultdict(set), defaultdict(set), set()
    seen = set()
    for n, dr in parsed.items():
        e = els.get(f"{ent}:{n}")
        if e is None:
            continue
        D = set()
        for p in dr["D"]:
            bs = blocks_of(m, ent, p, n)
            (D.update(bs) if bs else unmapped.add(p))
        R = set()
        for p in dr["R"]:
            bs = blocks_of(m, ent, p)
            if not bs:
                unmapped.add(p)
            elif _names_field(m, ent, p, n):
                if len(bs) > 1 and "." in n:           # a whole-record copy: field f goes to the block of field f
                    f = "." + n.split(".", 1)[1]
                    bs = {b for b in bs if b.endswith(f)} or bs
                R |= bs
        for p in dr.get("S", ()):                        # connected into an instance: read there (input side)
            b = block_of(m, ent, p)
            if b and b.startswith("inst:") and p.count("/") > 2 and _names_field(m, ent, p, n):
                R.add(b)
        out_port = e["top_level"] and e["dir"] in G.OUT_DIRS
        in_port = e["top_level"] and e["dir"] in G.IN_DIRS
        port = B.port_node(e) if e["top_level"] else None
        # a concurrent drive of an output port has no block in the diagram: the tool's line__N stands for the port
        D, R = {_alias(m, ent, b) for b in D}, {_alias(m, ent, b) for b in R}
        seen |= D | R
        if any(x.startswith(n + ".") for x in (k.split(":", 1)[1] for k in els if k.startswith(ent + ":"))):
            continue                                   # a record is compared field by field
        if not e["top_level"]:
            members[n] |= D
        for r in R:
            if in_port:
                edges[(port, r)].add(n)
            for d in D:
                if d != r:
                    edges[(d, r)].add(n)
        if out_port:
            for d in D:
                if d != port:
                    edges[(d, port)].add(n)
    return {"edges": dict(edges), "members": dict(members), "seen": seen, "unmapped": sorted(unmapped)}


def compare(m, ent, tools: list[dict]) -> dict:
    """Diagram vs the union of the tool's views over the generic settings tried."""
    dv = diagram_view(m, ent)
    tedges = defaultdict(set)
    tmem = defaultdict(set)
    seen, unmapped = set(), set()
    together = set()                                   # block pairs elaborated in one setting
    for t in tools:
        for k, v in t["edges"].items():
            tedges[k] |= v
        for k, v in t["members"].items():
            tmem[k] |= v
        seen |= t["seen"]
        unmapped |= set(t["unmapped"])
        s = t["seen"] | {k[0] for k in t["edges"]} | {k[1] for k in t["edges"]}
        together |= {(a, b) for a in s for b in s}
    # tool edges the diagram lacks: neither an arrow nor the reader's clock or reset
    missing = []
    for (a, b), via in sorted(tedges.items()):
        if (a, b) in dv["arrows"]:
            continue
        clocking = dv["clocking"].get(b, set())
        rest = {n for n in via if n not in clocking and n.split(".")[0] not in clocking}
        if rest:
            missing.append({"src": a, "dst": b, "elements": sorted(rest)})
    # diagram arrows the tool never shows although both ends were elaborated together
    extra, untested = [], []
    for (a, b) in sorted(dv["arrows"]):
        if (a, b) in tedges:
            continue
        ends_ok = (a, b) in together or (a.startswith(("in:", "out:")) and (b, b) in together) or \
            (b.startswith(("in:", "out:")) and (a, a) in together)
        (extra if ends_ok else untested).append({"src": a, "dst": b})
    # members
    mem_missing, mem_extra = [], []
    for n, bs in sorted(tmem.items()):
        ours = dv["members"].get(n, set())
        for b in sorted(bs - ours):
            mem_missing.append({"element": n, "block": b})
    for n, bs in sorted(dv["members"].items()):
        for b in sorted(bs & seen - tmem.get(n, set())):
            mem_extra.append({"element": n, "block": b})
    # arrow labels: the source elements the diagram names on an arrow vs the elements the tool sees driven in the
    # source block and read in the target block (records by field)
    label_extra, label_missing = [], []
    for (a, b), ys in sorted(dv["sources"].items()):
        if (a, b) not in tedges:
            continue
        tool_ys = tedges[(a, b)]
        clocking = dv["clocking"].get(b, set())
        # a whole record on the label stands for its fields (the tool is asked field by field)
        ex = sorted(y for y in ys if y not in tool_ys and not any(t.startswith(y + ".") for t in tool_ys))
        own = b.split(":")[-1] if b.startswith("out:") else None   # the block driving an output port: no read
        mi = sorted(y for y in tool_ys - ys if y not in clocking and y.split(".")[0] not in clocking
                    and y.split(".")[0] not in ys and y.split(".")[0] != own)
        if ex:
            label_extra.append({"src": a, "dst": b, "elements": ex})
        if mi:
            label_missing.append({"src": a, "dst": b, "elements": mi})
    return {"tool edges": len(tedges), "diagram arrows": len(dv["arrows"]),
            "arrows confirmed": len(dv["arrows"] & set(tedges)),
            "arrow source elements the tool does not see": label_extra,
            "elements the tool sees on an arrow that its label lacks": label_missing,
            "arrow labels checked": sum(1 for k in dv["sources"] if k in tedges),
            "blocks seen by the tool": len(seen & dv["blocks"]), "diagram blocks": len(dv["blocks"]),
            "tool edges with no arrow": missing, "arrows the tool does not show": extra,
            "arrows not elaborated in any setting": untested,
            "members the diagram lacks": mem_missing, "members the tool does not confirm": mem_extra,
            "unmapped tool processes": sorted(unmapped)}


# A branch chosen by a constant, not a generic, cannot be built by any generic setting. A variant compiles a copy of
# the file with that constant changed on its own line (line numbers stay), then the original is compiled back.
VARIANTS = {m: [("alt_style_c true", "constant alt_style_c : boolean := false;",
                   "constant alt_style_c : boolean := true; ")] for m in ("neorv32_imem", "neorv32_dmem")}


def _with_variant(m, old, new, fn):
    f = G.RTL[G.split_of(m)] / f"{m}.vhd"
    text = f.read_text(encoding="utf-8", errors="ignore")
    assert old in text, (m, old)
    v = OUT / "_variants" / f.name
    v.parent.mkdir(parents=True, exist_ok=True)
    v.write_text(text.replace(old, new), encoding="utf-8")
    try:
        o = _run(["vcom", "-2008", "-work", LIB, "-quiet", str(v)])
        if "** Error" in o:
            raise RuntimeError(o[-1500:])
        return fn()
    finally:
        _run(["vcom", "-2008", "-work", LIB, "-quiet", str(f)])


def check_module(m, log=print) -> dict:
    res = {}
    for ent in G.step2_hierarchy(m)["roots"]:
        tools, used, failed = [], [], []
        runs = [(None, s, f"s{i}") for i, s in enumerate(settings(m, ent))]
        runs += [(v, s, f"v{j}s{i}") for j, v in enumerate(VARIANTS.get(m, [])) for i, s in enumerate(settings(m, ent))]
        for variant, s, tag in runs:
            if variant:
                raw, lg = _with_variant(m, variant[1], variant[2], lambda: dump(m, ent, s, tag))
            else:
                raw, lg = dump(m, ent, s, tag)
            if not raw:
                failed.append({"setting": s, "variant": variant and variant[0], "log": lg[-600:]})
                continue
            parsed, _inst = parse(raw)
            tools.append(tool_view(m, ent, parsed))
            used.append({**s, **({"variant": variant[0]} if variant else {})})
        r = compare(m, ent, tools) if tools else {}
        if r.get("arrows not elaborated in any setting"):  # second pass: one boolean flipped at a time
            for i, s in enumerate(flip_settings(m, ent)):
                raw, lg = dump(m, ent, s, f"f{i}")
                if not raw:
                    failed.append({"setting": s, "variant": None, "log": lg[-600:]})
                    continue
                tools.append(tool_view(m, ent, parse(raw)[0]))
                used.append(s)
            r = compare(m, ent, tools)
        r.update({"settings elaborated": len(used), "settings failed": len(failed), "failed": failed[:2],
                  "settings": used})
        res[ent] = r
        log(f"   {m:24s} {ent:28s} settings {len(used)}/{len(used) + len(failed)}; arrows confirmed "
            f"{r.get('arrows confirmed')}/{r.get('diagram arrows')}; tool edges w/o arrow "
            f"{len(r.get('tool edges with no arrow', []))}; arrows not shown {len(r.get('arrows the tool does not show', []))}; "
            f"untested {len(r.get('arrows not elaborated in any setting', []))}; members missing "
            f"{len(r.get('members the diagram lacks', []))}, unconfirmed {len(r.get('members the tool does not confirm', []))}; "
            f"unmapped {len(r.get('unmapped tool processes', []))}")
    return res


def recompare(m) -> dict:
    """compare() again from the saved tool answers of the last run (no simulation): files <root>__<tag>.txt."""
    out = {}
    for ent in G.step2_hierarchy(m)["roots"]:
        tools = []
        for f in sorted((OUT / m).glob(f"{ent}__*.txt")):
            if re.fullmatch(rf"{ent}__(s\d+|v\d+s\d+|f\d+)\.txt", f.name):
                tools.append(tool_view(m, ent, parse(f.read_text(encoding="utf-8", errors="replace"))[0]))
        out[ent] = compare(m, ent, tools) if tools else {}
        out[ent]["tool answers read"] = len(tools)
    return out


# ------------------------------------------------------------------------------------------------ self-test ---
def selftest(log=print) -> bool:
    """Hand-read data/RTL_data/neorv32_wdt.vhd: cnt is driven by process wdt_counter (122-137) and read by the
    concurrent assignment at 144 (cnt_timeout) and by wdt_counter; ctrl.enable is driven by bus_access (71-117)."""
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        log(f"   {'ok  ' if cond else 'FAIL'} {label}")
    raw, lg = dump("neorv32_wdt", "neorv32_wdt", {}, "selftest")
    check("wdt elaborates", bool(raw))
    p, _ = parse(raw)
    check(f"wdt cnt: drivers {sorted(p.get('cnt', {}).get('D', []))}, readers {sorted(p.get('cnt', {}).get('R', []))}",
          p.get("cnt", {}).get("D") == {"/neorv32_wdt/wdt_counter"}
          and p.get("cnt", {}).get("R") == {"/neorv32_wdt/line__144", "/neorv32_wdt/wdt_counter"})
    w = "neorv32_wdt"
    check("wdt mapping: line__144 -> logic cnt_timeout; wdt_counter -> its process block; bus_access -> its block",
          block_of("neorv32_wdt", w, "/neorv32_wdt/line__144") == f"logic:{w}:cnt_timeout"
          and block_of("neorv32_wdt", w, "/neorv32_wdt/wdt_counter") == f"process:{w}:wdt_counter@122"
          and block_of("neorv32_wdt", w, "/neorv32_wdt/bus_access") == f"process:{w}:bus_access@71")
    # hand-read data/RTL_data/neorv32_imem.vhd: mem_access at 78 (imem_rom_default) and 89 (imem_rom_alternative)
    check("imem mapping: a label used in several generates goes to the one the path names",
          block_of("neorv32_imem", "neorv32_imem", "/neorv32_imem/imem_rom/imem_rom_default/mem_access")
          == "process:neorv32_imem:mem_access@78"
          and block_of("neorv32_imem", "neorv32_imem", "/neorv32_imem/imem_rom/imem_rom_alternative/mem_access")
          == "process:neorv32_imem:mem_access@89")
    # hand-read data/RTL_data/neorv32_bus.vhd 366: `a_req_o <= port_req(0); port_rsp(0) <= a_rsp_i;`
    g = "neorv32_bus_gateway"
    check("bus 366: line__366 is the a_req_o statement, line__366__1 the port_rsp one",
          blocks_of("neorv32_bus", g, f"/{g}/line__366", "a_req_o") == {f"logic:{g}:a_req_o"}
          and blocks_of("neorv32_bus", g, f"/{g}/line__366__1") == {f"logic:{g}:port_rsp"})
    check("cache mapping: a process inside the same-file child -> the instance block",
          block_of("neorv32_cache", "neorv32_cache", "/neorv32_cache/neorv32_cache_memory_inst/status_memory")
          == "inst:neorv32_cache_memory_inst")
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    import pio_run as R
    mods = sys.argv[1:] or R.gt_modules()["tuning"]
    compile_all()
    assert selftest(), "self-test failed: nothing reported"
    allres = {}
    for m in mods:
        allres[m] = check_module(m)
    (OUT / "result.json").write_text(json.dumps(allres, indent=1, default=sorted), encoding="utf-8")
