"""Construct D, "count increment inputs": find every counter (a register whose next
value is formed by an addition that includes the register itself) in the 41 modules,
and for each one say which non-record input ports (of the unit or of a child entity in
the same file) are TERMS of that sum (construct D) and which are only CONDITIONS that let
the count advance (not construct D).

Run:  python -B count_inc_inputs.py
Reads: inputs/v1/{tuning,heldout}/<module>/{rtl.txt,closed_set.json}, manual_gt_neorv32.json
Writes: count_inc_inputs.json next to this file, and a readable summary on stdout.

A self-test against hand-read lines (SELFTEST below) runs first; if it fails the script
prints the failures and exits 1 without reporting anything else.
"""
import json
import os
import re
import sys
from collections import defaultdict, deque

ROOT = r"E:\jobs\ff\test\Prepoison_subset"
INP = os.path.join(ROOT, "final", "pio", "lab", "inputs", "v1")
GT = os.path.join(ROOT, "data", "ground_truth", "manual_gt_neorv32.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "count_inc_inputs.json")
SKIP = {"neorv32_boot_rom", "neorv32_fifo"}

KW = set(
    "and or not xor nand nor xnor when else others downto to is then if elsif end case "
    "loop for in generate begin process null with select after until wait of all "
    "abs mod rem sll srl sla sra rol ror".split()
)
LINE_RE = re.compile(r"^\s*(\d+) \|(.*)$")
ID_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
DECL_START = (
    "constant", "signal", "variable", "type", "subtype", "attribute", "alias", "function",
    "procedure", "component", "generic", "port", "library", "use", "entity", "architecture",
    "end", "impure", "pure", "shared", "file",
)


# ---------------------------------------------------------------- loading
def load_rtl(path):
    lines = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            m = LINE_RE.match(raw.rstrip("\n"))
            if not m:
                continue
            ln = int(m.group(1))
            txt = m.group(2).split("--", 1)[0].strip()
            if txt:
                lines.append((ln, txt))
    return lines


def load_closed_set(path):
    with open(path, encoding="utf-8") as fh:
        cs = json.load(fh)
    ents = {}
    for e in cs["entity list"]:
        name = e["entity name"]
        ports = {}
        for p in e.get("port list", []):
            ports[p["port"]] = {
                "dir": p.get("direction"),
                "record": "record type" in p,
                "roles": p.get("role in RTL", []),
            }
        sigs = {}
        for s in e.get("signal list", []):
            sigs[s["signal"]] = {"type": s.get("type")}
        ents[name] = {"ports": ports, "signals": sigs}
    return cs["module name"], ents


# ---------------------------------------------------------------- text helpers
def clean_expr(t):
    t = re.sub(r'"[^"]*"', ' "" ', t)          # string literals
    t = re.sub(r"'[^']'", " '' ", t)           # char literals '0' '1'
    t = re.sub(r"'\w+", " ", t)                 # attributes 'left 'length
    return t


def index_regions(expr, is_name):
    """Character spans of (...) groups that directly follow a signal/port/variable name:
    those are index or slice expressions, not values."""
    spans = []
    for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_.]*)\s*\(", expr):
        if not is_name(m.group(1)):
            continue
        start = m.end() - 1
        depth = 0
        for i in range(start, len(expr)):
            if expr[i] == "(":
                depth += 1
            elif expr[i] == ")":
                depth -= 1
                if depth == 0:
                    spans.append((start, i))
                    break
    return spans


def ids_in(expr, is_name):
    """Return (value_ids, index_ids) found in expr (already comment-free)."""
    e = clean_expr(expr)
    spans = index_regions(e, is_name)

    def in_index(pos):
        return any(a < pos < b for a, b in spans)

    vals, idx = [], []
    for m in ID_RE.finditer(e):
        tok = m.group(0)
        if tok.lower() in KW or re.match(r"^\d", tok):
            continue
        # a name followed by '(' that is not a known name is a function/type: skip it
        after = e[m.end():m.end() + 2].strip()
        if after.startswith("(") and not is_name(tok):
            continue
        if not is_name(tok):
            continue
        (idx if in_index(m.start()) else vals).append(tok)
    return vals, idx


def value_plus(expr, is_name):
    """True when expr holds a '+' that is a value addition (not inside an index/slice
    group of a named signal, and not in a group holding 'downto'/'to')."""
    e = clean_expr(expr)
    spans = index_regions(e, is_name)
    # blank the index/slice groups of named signals so a nested "(63 downto 32)" does not
    # make the enclosing value group look like index arithmetic
    masked = list(e)
    for a, b in spans:
        for i in range(a + 1, b):
            masked[i] = " "
    e = "".join(masked)
    for m in re.finditer(r"\+", e):
        pos = m.start()
        if any(a < pos < b for a, b in spans):
            continue
        # innermost enclosing group
        depth, start = 0, None
        for i in range(pos - 1, -1, -1):
            if e[i] == ")":
                depth += 1
            elif e[i] == "(":
                if depth == 0:
                    start = i
                    break
                depth -= 1
        if start is not None:
            depth, end = 0, len(e)
            for i in range(start, len(e)):
                if e[i] == "(":
                    depth += 1
                elif e[i] == ")":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            grp = e[start:end + 1].lower()
            if " downto " in grp or re.search(r"\bto\b", grp):
                continue
        return True
    return False


def split_when_else(rhs):
    """'A when c1 else B when c2 else C' -> (values [A,B,C], conds [c1,c2])."""
    parts = re.split(r"\bwhen\b", rhs, flags=re.I)
    values, conds = [parts[0]], []
    for p in parts[1:]:
        ce = re.split(r"\belse\b", p, flags=re.I)
        conds.append(ce[0])
        values.extend(ce[1:])
    return values, conds


def base(name):
    return name.split(".")[0]


# ---------------------------------------------------------------- parse one module
def parse_module(module, folder):
    rtl = load_rtl(os.path.join(folder, "rtl.txt"))
    _, ents = load_closed_set(os.path.join(folder, "closed_set.json"))
    unit = module if module in ents else next(iter(ents))

    # pass 1: architecture -> entity, process ranges and clockedness, declared names
    arch_of_line = {}
    cur_ent = None
    proc_ranges = []   # (start_ln, end_ln, clocked)
    proc_start, proc_clocked = None, False
    declared = defaultdict(set)   # entity -> names (signals, variables, constants)
    for ln, t in rtl:
        low = t.lower()
        m = re.match(r"architecture\s+\w+\s+of\s+(\w+)\s+is", low)
        if m:
            cur_ent = next((e for e in ents if e.lower() == m.group(1)), m.group(1))
        arch_of_line[ln] = cur_ent
        if cur_ent:
            dm = re.match(r"(signal|variable|constant)\s+([\w\s,]+?)\s*:", low)
            if dm:
                for n in dm.group(2).split(","):
                    declared[cur_ent].add(n.strip())
        if re.match(r"(\w+\s*:\s*)?process\b", low):
            proc_start, proc_clocked = ln, False
        if proc_start is not None and ("rising_edge" in low or "falling_edge" in low):
            proc_clocked = True
        if re.match(r"end\s+process\b", low):
            proc_ranges.append((proc_start, ln, proc_clocked))
            proc_start = None

    def proc_of(ln):
        for a, b, c in proc_ranges:
            if a <= ln <= b:
                return (a, c)
        return None

    def names_for(ent):
        e = ents.get(ent, {"ports": {}, "signals": {}})
        return set(e["ports"]) | set(e["signals"]) | declared[ent]

    # pass 2: statements with context
    assigns = []     # dicts
    portmaps = []    # dicts
    stack = []
    buf, buf_ln = "", None
    pm = None        # current port map: dict(instance, entity, ln)
    in_generic_map = False

    def complete(low):
        if low.endswith(";"):
            return True
        if re.match(r"(if|elsif)\b", low):
            return low.endswith("then")
        if low.startswith("when "):
            return "=>" in low
        if low.startswith("case "):
            return low.endswith(" is")
        if low.startswith("for "):
            return low.endswith("loop") or low.endswith("generate")
        if low in ("else", "begin") or low.startswith("else "):
            return True
        if re.match(r"(\w+\s*:\s*)?process\b", low):
            return low.endswith(")") or low.endswith("is") or low.endswith("process")
        if re.match(r"^\w+\s*:\s*(entity\s+\w+\.)?\w+$", low):
            return True   # an instance label line: "cycle_inst: neorv32_cpu_counters_cnt"
        if re.search(r"\bgenerate$", low):
            return True
        if re.match(r"(architecture|entity|package|component)\b", low):
            return low.endswith(" is")
        if re.search(r"\b(port|generic)\s+map\s*\($", low) or re.search(r"\b(port|generic)\s*\($", low):
            return True
        return False

    def ctx_conds():
        out = []
        for fr in stack:
            if fr[0] in ("if", "case"):
                out.extend(fr[1])
        return out

    def handle(stmt, ln):
        nonlocal pm, in_generic_map
        low = stmt.lower()
        ent = arch_of_line.get(ln)
        # ---- port / generic map lines
        if in_generic_map:
            if low.count(")") >= low.count("(") and (low.endswith(")") or low.endswith(");")):
                in_generic_map = False
            return
        if pm is not None:
            m = re.match(r"(\w+)\s*=>\s*(.*?)\s*,?\s*(\)\s*;)?$", stmt)
            if m:
                expr = m.group(2).rstrip(",").strip()
                if expr.endswith(")") and m.group(3) is None and expr.count("(") < expr.count(")"):
                    expr = expr[:-1].rstrip()
                pm["assoc"].append({"port": m.group(1), "expr": expr, "ln": ln})
            if low.endswith(");") or low == ");" or low.endswith(") ;"):
                portmaps.append(pm)
                pm = None
            return
        m = re.match(r"(\w+)\s*:\s*(?:entity\s+\w+\.)?(\w+)\s*$", stmt)
        if m and (m.group(2) in ents or m.group(2).lower() in [e.lower() for e in ents]):
            pm = {"instance": m.group(1), "entity": m.group(2), "ln": ln, "assoc": [], "unit": ent, "open": False}
            return
        if pm is not None and low.startswith("generic map"):
            in_generic_map = low.count("(") > low.count(")")
            return
        if pm is not None and low.startswith("port map"):
            pm["open"] = True
            rest = stmt[stmt.lower().find("(") + 1:].strip()
            if rest:
                handle(rest, ln)
            return
        if re.match(r"generic\s+map", low):
            in_generic_map = not (low.endswith(")") and low.count("(") == low.count(")"))
            return
        # ---- structure
        if re.match(r"(\w+\s*:\s*)?process\b", low):
            stack.append(("proc", ln))
            return
        if re.match(r"end\s+process\b", low):
            while stack and stack[-1][0] != "proc":
                stack.pop()
            if stack:
                stack.pop()
            return
        if re.search(r"\bgenerate$", low) and not low.startswith("end"):
            stack.append(("gen", ln))
            return
        if re.match(r"end\s+generate\b", low):
            while stack and stack[-1][0] != "gen":
                stack.pop()
            if stack:
                stack.pop()
            return
        m = re.match(r"if\s+(.*)\s+then$", stmt, flags=re.I)
        if m:
            stack.append(("if", [(m.group(1), ln)]))
            return
        m = re.match(r"elsif\s+(.*)\s+then$", stmt, flags=re.I)
        if m:
            for fr in reversed(stack):
                if fr[0] == "if":
                    fr[1].append((m.group(1), ln))
                    break
            return
        if low == "else" or low.startswith("else "):
            return
        if re.match(r"end\s+if\b", low):
            while stack and stack[-1][0] != "if":
                stack.pop()
            if stack:
                stack.pop()
            return
        m = re.match(r"case\s+(.*)\s+is$", stmt, flags=re.I)
        if m:
            stack.append(("case", [(m.group(1), ln)]))
            return
        if re.match(r"end\s+case\b", low):
            while stack and stack[-1][0] != "case":
                stack.pop()
            if stack:
                stack.pop()
            return
        if low.startswith("when "):
            head, _, rest = stmt.partition("=>")
            if stack and stack[-1][0] == "when":
                stack.pop()
            stack.append(("when", head[4:].strip(), ln))
            if rest.strip():
                handle(rest.strip(), ln)
            return
        if re.match(r"for\s+.*\bloop$", low):
            stack.append(("loop", ln))
            return
        if re.match(r"end\s+loop\b", low):
            while stack and stack[-1][0] != "loop":
                stack.pop()
            if stack:
                stack.pop()
            return
        if low.startswith(DECL_START) and not re.match(r"\w+\s*<=", stmt):
            return
        # ---- assignments
        m = re.match(r"([A-Za-z_][\w.]*)\s*(\([^<]*?\))?\s*(<=|:=)\s*(.*);$", stmt)
        if not m or ent is None:
            return
        target, op, rhs = m.group(1), m.group(3), m.group(4)
        if op == ":=" and not any(fr[0] == "proc" for fr in stack):
            return
        in_proc = next((fr for fr in stack if fr[0] == "proc"), None)
        pr = proc_of(ln) if in_proc else None
        values, inline_conds = split_when_else(rhs)
        assigns.append({
            "ent": ent, "target": target, "ln": ln, "rhs": rhs,
            "values": [v.strip() for v in values],
            "inline_conds": [(c.strip(), ln) for c in inline_conds],
            "ctx_conds": list(ctx_conds()) if in_proc else [],
            "in_proc": bool(in_proc), "clocked": bool(pr and pr[1]),
            "nctx": len([fr for fr in stack if fr[0] in ("if", "case")]) if in_proc else 0,
        })

    for ln, t in rtl:
        if buf:
            buf = buf + " " + t
        else:
            buf, buf_ln = t, ln
        low = buf.lower().strip()
        if pm is not None or in_generic_map:
            handle(buf, buf_ln)
            buf = ""
            continue
        if complete(low):
            handle(buf.strip(), buf_ln)
            buf = ""
    return {
        "module": module, "unit": unit, "ents": ents, "declared": declared,
        "assigns": assigns, "portmaps": portmaps, "rtl": dict(rtl),
    }


# ---------------------------------------------------------------- analysis
def analyze(pm):
    ents, assigns = pm["ents"], pm["assigns"]
    res = {"module": pm["module"], "unit": pm["unit"], "counts": [], "other_additions": [],
           "feeders": []}
    by_ent = defaultdict(list)
    for a in assigns:
        by_ent[a["ent"]].append(a)

    for ent, alist in by_ent.items():
        e = ents.get(ent, {"ports": {}, "signals": {}})
        names = set(e["ports"]) | set(e["signals"]) | pm["declared"][ent]

        def is_name(tok, names=names):
            return tok in names or base(tok) in names

        def port_info(tok, e=e):
            p = e["ports"].get(base(tok))
            if not p:
                return None
            return p

        def is_clkrst(tok):
            p = port_info(tok)
            return bool(p and ("clock" in p["roles"] or "reset" in p["roles"]))

        # feed graph: target (full and base) -> [(value ids, ln, clocked, rhs text)]
        feeds = defaultdict(list)
        consumers = defaultdict(set)   # value id -> set of targets
        for a in alist:
            vids, iids = [], []
            for v in a["values"]:
                v1, i1 = ids_in(v, is_name)
                vids += v1
                iids += i1
            a["vids"], a["iids"] = vids, iids
            # conditions other than the clock/reset tests of a clocked process
            ectx = 0
            for ctext, _ in a["ctx_conds"] + a["inline_conds"]:
                cv, _ = ids_in(ctext, is_name)
                if any(not is_clkrst(x) for x in cv):
                    ectx += 1
            a["ectx"] = ectx
            feeds[a["target"]].append((vids, a["ln"], a["clocked"], a["rhs"], ectx, iids))
            for v in vids:
                consumers[v].add(a["target"])

        def rows_for(name):
            """Assignments that set `name`: its own, plus whole-record assignments of its
            record (ctrl <= ctrl_nxt sets ctrl.ofs from ctrl_nxt.ofs)."""
            rows = list(feeds.get(name, []))
            if "." in name:
                b, f = name.split(".", 1)
                for vids, ln, clk, rhs, ectx, iids in feeds.get(b, []):
                    tv = [(v + "." + f) if "." not in v and not port_info(v) and (v + "." + f) in feeds else v for v in vids]
                    rows.append((tv, ln, clk, rhs, ectx, iids))
            return rows

        def copy_src(sig):
            """If every non-constant assignment to sig reads exactly one and the same
            element (a copy, a bit pick, a widening or a reduction of it), return
            (that element, [(ln, clocked, rhs)]); else None."""
            rows = rows_for(sig)
            srcs, hops = set(), []
            for vids, ln, clk, rhs, ectx, iids in rows:
                if not vids:
                    continue            # constant (reset/clear) assignment
                if len(set(vids)) != 1 or ectx:
                    return None         # several sources, or a conditional copy
                srcs.add(vids[0])
                hops.append((ln, clk, rhs))
            if len(srcs) != 1:
                return None
            return (next(iter(srcs)), hops)

        def copy_chain(tok, depth=3):
            """Follow single-source copies from tok up to an input port."""
            chain, cur, seen = [], tok, {tok}
            for _ in range(depth):
                c = copy_src(cur)
                if not c:
                    return None
                src, hops = c
                chain.append({"signal": cur, "from": src, "hops": [{"line": h[0], "reg": h[1], "text": h[2]} for h in hops]})
                p = port_info(src)
                if p:
                    if p["dir"] == "in" and not p["record"] and not is_clkrst(src) and src == base(src):
                        return chain
                    return None
                if src in seen:
                    return None
                seen.add(src)
                cur = src
            return None

        def classify(tok):
            p = port_info(tok)
            if p:
                if p["record"]:
                    return ("record port field", None)
                if p["dir"] == "in":
                    if is_clkrst(tok):
                        return ("clock/reset port", None)
                    return ("input port", None)
                return ("output port", None)
            ch = copy_chain(tok)
            if ch:
                nreg = sum(1 for c in ch for h in c["hops"] if h["reg"])
                kind = "register copy" if nreg else "wire copy"
                if len(ch) > 1:
                    kind = "%d-hop copy chain (%d register)" % (len(ch), nreg)
                return (kind + " of input port", ch)
            return ("internal", None)

        def paths_to_ports(tok, depth=2):
            """Loose BFS over any value flow (ids combined by operators too)."""
            out = []
            seen = {tok}
            q = deque([(tok, [])])
            while q:
                cur, path = q.popleft()
                if len(path) >= depth:
                    continue
                for vids, ln, clk, rhs, ectx, iids in rows_for(cur):
                    for v in vids:
                        step = path + [(cur, v, ln, "reg" if clk else "wire")]
                        p = port_info(v)
                        if p and p["dir"] == "in" and not p["record"] and not is_clkrst(v):
                            out.append(step)
                        elif not p and v not in seen:
                            seen.add(v)
                            q.append((v, step))
            return out

        for a in alist:
            if not any(value_plus(v, is_name) for v in a["values"]):
                continue
            # self-feeding test: the sum's result comes back as a term of the sum,
            # directly (cnt <= cnt + 1), through a register that copies the sum in at least
            # one of its assignments (nxt <= lo_q + inc; lo_q <= nxt), or through the
            # two-process pattern (ctrl_nxt.f <= ctrl.f + 1; ctrl <= ctrl_nxt).
            t = a["target"]
            vset = set(a["vids"])
            images = {t}
            for R in consumers.get(t, set()):
                if any(set(row[0]) == {t} for row in feeds.get(R, [])):
                    images.add(R)
            if "." in t:
                b, f = t.split(".", 1)
                for R in consumers.get(b, set()):
                    if any(set(row[0]) == {b} for row in feeds.get(R, [])):
                        images.add(R + "." + f)
            is_count = bool(images & vset)
            reaches_reg = a["clocked"] or any(
                any(row[2] for row in feeds.get(c, [])) for c in consumers.get(t, set())
            ) or ("." in t and any(any(row[2] for row in feeds.get(c, [])) for c in consumers.get(base(t), set())))
            entry = {
                "entity": ent, "target": t, "line": a["ln"], "text": pm["rtl"][a["ln"]],
                "clocked": a["clocked"], "reaches_register": reaches_reg,
                "is_count": is_count, "self_images": sorted(images),
                "terms": [], "conditions": [],
            }
            for v in sorted(vset):
                if v in images:
                    continue
                cls, c = classify(v)
                d = {"id": v, "class": cls}
                if c:
                    d["copies"] = {"port": c[-1]["from"], "line": c[0]["hops"][0]["line"],
                                   "text": c[0]["hops"][0]["text"], "chain": c}
                entry["terms"].append(d)
            conds = a["ctx_conds"] + a["inline_conds"]
            for ctext, cln in conds:
                cv, ci = ids_in(ctext, is_name)
                for v in sorted(set(cv)):
                    cls, c = classify(v)
                    d = {"id": v, "class": cls, "line": cln, "text": pm["rtl"].get(cln, ctext)[:160]}
                    if c:
                        d["copies"] = {"port": c[-1]["from"], "line": c[0]["hops"][0]["line"],
                                       "text": c[0]["hops"][0]["text"], "chain": c}
                    if cls == "internal":
                        d["paths"] = paths_to_ports(v)
                    if cls in ("clock/reset port",):
                        continue
                    entry["conditions"].append(d)
            (res["counts"] if is_count else res["other_additions"]).append(entry)

    # port-map feeders for every child-entity input port
    for p in pm["portmaps"]:
        child = p["entity"]
        if child == pm["unit"]:
            continue
        unit_names = set(ents[pm["unit"]]["ports"]) | set(ents[pm["unit"]]["signals"]) | pm["declared"][pm["unit"]]
        for assoc in p["assoc"]:
            vids, _ = ids_in(assoc["expr"], lambda tok: tok in unit_names or base(tok) in unit_names)
            res["feeders"].append({"instance": p["instance"], "entity": child, "port": assoc["port"],
                                   "expr": assoc["expr"], "line": assoc["ln"], "unit_ids": sorted(set(vids))})
    return res


# ---------------------------------------------------------------- self-test
def selftest(results):
    r = {x["module"]: x for x in results}
    fails = []

    def count(mod, target, line):
        for c in r[mod]["counts"]:
            if c["target"] == target and c["line"] == line:
                return c
        return None

    # 1. counters: nxt <= '0'&lo_q + inc at 312 is a count (feeds lo_q at 305); inc_i term via wire inc (311)
    c = count("neorv32_cpu_counters", "nxt", 312)
    if not c:
        fails.append("counters: nxt at 312 not found as a count")
    else:
        t = [x for x in c["terms"] if x["id"] == "inc"]
        if not (t and t[0]["class"] == "wire copy of input port" and t[0]["copies"]["port"] == "inc_i" and t[0]["copies"]["line"] == 311):
            fails.append("counters: inc at 312 should be a wire copy of inc_i from 311: %s" % t)
        if not c["reaches_register"]:
            fails.append("counters: nxt should reach a register (lo_q at 305)")
    # 2. counters: hi_q <= hi_q + cy_q at 328 is a count with no port term or condition
    c = count("neorv32_cpu_counters", "hi_q", 328)
    if not c or any(x["class"] != "internal" for x in c["terms"]):
        fails.append("counters: hi_q at 328 should be a count with only internal terms: %s" % (c and c["terms"]))
    # 3. counters feeders: inc_i fed by cnt_en at 131, 150, 185
    f = sorted(x["line"] for x in r["neorv32_cpu_counters"]["feeders"] if x["port"] == "inc_i" and "cnt_en" in x["unit_ids"])
    if f != [131, 150, 185]:
        fails.append("counters: inc_i feeders should be cnt_en at 131,150,185, got %s" % f)
    # 4. pwm: cnt_cdiv + 1 at 219 under clkgen_i condition at 214 (direct), no port term
    c = count("neorv32_pwm", "cnt_cdiv", 219)
    if not c or not any(x["id"] == "clkgen_i" and x["class"] == "input port" and x["line"] == 214 for x in c["conditions"]):
        fails.append("pwm: cnt_cdiv at 219 should have clkgen_i as direct condition at 214: %s" % (c and c["conditions"]))
    if c and any(x["class"] != "internal" for x in c["terms"]):
        fails.append("pwm: cnt_cdiv terms should be internal only: %s" % c["terms"])
    # 5. spi: cdiv_cnt + 1 at 376 under clkgen_i at 371
    c = count("neorv32_spi", "cdiv_cnt", 376)
    if not c or not any(x["id"] == "clkgen_i" and x["class"] == "input port" and x["line"] == 371 for x in c["conditions"]):
        fails.append("spi: cdiv_cnt at 376 should have clkgen_i condition at 371: %s" % (c and c["conditions"]))
    # 6. twi: clk_gen.cnt + 1 at 262 under clkgen_i at 257
    c = count("neorv32_twi", "clk_gen.cnt", 262)
    if not c or not any(x["id"] == "clkgen_i" and x["class"] == "input port" and x["line"] == 257 for x in c["conditions"]):
        fails.append("twi: clk_gen.cnt at 262 should have clkgen_i condition at 257: %s" % (c and c["conditions"]))
    # 7. gptmr: timer.count + 1 at 124 under timer.tick at 120; timer.tick <= clkgen_i(...) at 117 (register copy)
    c = count("neorv32_gptmr", "timer.count", 124)
    ok = False
    if c:
        for x in c["conditions"]:
            if x["id"] == "timer.tick" and x["line"] == 120:
                if x["class"] == "register copy of input port" and x["copies"]["port"] == "clkgen_i" and x["copies"]["line"] == 117:
                    ok = True
    if not ok:
        fails.append("gptmr: timer.count at 124 should have timer.tick (reg copy of clkgen_i at 117) as condition at 120: %s" % (c and c["conditions"]))
    # 8. sys: cnt + 1 at 131 under en at 130; en <= or_reduce_f(enable_i) at 129
    c = count("neorv32_sys", "cnt", 131)
    ok = False
    if c:
        for x in c["conditions"]:
            if x["id"] == "en" and x["line"] == 130 and x.get("copies", {}).get("port") == "enable_i" and x["copies"]["line"] == 129:
                ok = True
    if not ok:
        fails.append("sys: cnt at 131 should have en (copy of enable_i at 129) as condition at 130: %s" % (c and c["conditions"]))
    # 9. cpu_control: monitor_cnt + 1 at 637, no port (direct or by a copy chain) in terms or conditions
    c = count("neorv32_cpu_control", "monitor_cnt", 637)
    if not c:
        fails.append("cpu_control: monitor_cnt at 637 not found")
    else:
        bad = [x for x in c["terms"] + c["conditions"] if x["class"] != "internal"]
        if bad:
            fails.append("cpu_control: monitor_cnt at 637 should have no port terms or conditions: %s" % bad)
    # 10. cpu_alu: addsub_res at 116 is an addition but not a count
    if not any(x["target"] == "addsub_res" and x["line"] == 116 for x in r["neorv32_cpu_alu"]["other_additions"]):
        fails.append("cpu_alu: addsub_res at 116 should be listed as a non-count addition")
    if any(x["target"] == "addsub_res" for x in r["neorv32_cpu_alu"]["counts"]):
        fails.append("cpu_alu: addsub_res should not be a count")
    # 11. every value addition found by eye in the corpus-wide '+' scan (41 lines; index
    # arithmetic, declarations, generics and generate ranges left out) is found, and nothing else
    expected = {
        ("neorv32_bus", 422), ("neorv32_bus", 840), ("neorv32_cache", 244),
        ("neorv32_cpu_cp_cfu", 216), ("neorv32_cpu_cp_cfu", 222), ("neorv32_cpu_cp_cfu", 238),
        ("neorv32_cpu_cp_muldiv", 227), ("neorv32_spi", 311), ("neorv32_spi", 376),
        ("neorv32_sys", 131), ("neorv32_trng", 359), ("neorv32_twi", 262), ("neorv32_twi", 382),
        ("neorv32_wdt", 134), ("neorv32_cpu_alu", 116), ("neorv32_cpu_control", 637),
        ("neorv32_cpu_counters", 312), ("neorv32_cpu_counters", 328),
        ("neorv32_cpu_cp_bitmanip", 257), ("neorv32_cpu_cp_bitmanip", 259),
        ("neorv32_cpu_cp_bitmanip", 298), ("neorv32_cpu_cp_bitmanip", 334),
        ("neorv32_cpu_cp_fpu", 851), ("neorv32_cpu_cp_fpu", 1124), ("neorv32_cpu_cp_fpu", 1137),
        ("neorv32_cpu_cp_fpu", 1761), ("neorv32_cpu_cp_fpu", 1956), ("neorv32_cpu_cp_fpu", 2363),
        ("neorv32_cpu_frontend", 102), ("neorv32_gptmr", 124), ("neorv32_neoled", 279),
        ("neorv32_neoled", 297), ("neorv32_neoled", 299), ("neorv32_onewire", 265),
        ("neorv32_onewire", 361), ("neorv32_onewire", 367), ("neorv32_pwm", 219),
        ("neorv32_pwm", 227), ("neorv32_sdi", 318), ("neorv32_twd", 413), ("neorv32_twd", 450),
    }
    found = {(x["module"], c["line"]) for x in results for c in x["counts"] + x["other_additions"]}
    if found != expected:
        fails.append("value additions differ from the hand list: missing %s, extra %s"
                     % (sorted(expected - found), sorted(found - expected)))
    return fails


# ---------------------------------------------------------------- main
def main():
    with open(GT, encoding="utf-8") as fh:
        gt = json.load(fh)["modules"]
    results = []
    for split in ("tuning", "heldout"):
        for module in sorted(os.listdir(os.path.join(INP, split))):
            folder = os.path.join(INP, split, module)
            if module in SKIP or not os.path.isdir(folder) or not os.path.exists(os.path.join(folder, "rtl.txt")):
                continue
            pm = parse_module(module, folder)
            res = analyze(pm)
            res["split"] = split
            res["reference"] = [row["element"] for row in gt[module]["assets"]]
            results.append(res)

    fails = selftest(results)
    if fails:
        print("SELF-TEST FAILED")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("SELF-TEST PASS (11 checks against hand-read lines)")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)

    n_mod = len(results)
    n_counts = sum(len(x["counts"]) for x in results)
    n_other = sum(len(x["other_additions"]) for x in results)
    print("modules: %d   counts (self-feeding additions): %d   other additions: %d" % (n_mod, n_counts, n_other))
    print()
    for x in results:
        if not x["counts"]:
            continue
        print("== %s (%s)  reference: %s" % (x["module"], x["split"], ", ".join(x["reference"])))
        for c in x["counts"]:
            flag = "clocked" if c["clocked"] else ("wire->reg" if c["reaches_register"] else "wire")
            print("  COUNT %s.%s  L%d  [%s]  %s" % (c["entity"], c["target"], c["line"], flag, c["text"].strip()[:110]))
            for t in c["terms"]:
                extra = ""
                if "copies" in t:
                    extra = "  <- %s at L%d: %s" % (t["copies"]["port"], t["copies"]["line"], t["copies"]["text"])
                print("     term %-24s %s%s" % (t["id"], t["class"], extra))
            seen = set()
            for d in c["conditions"]:
                key = (d["id"], d["line"])
                if key in seen:
                    continue
                seen.add(key)
                if d["class"] == "internal" and not d.get("paths"):
                    continue
                extra = ""
                if "copies" in d:
                    extra = "  <- %s: " % d["copies"]["port"] + " | ".join(
                        "%s<-%s@L%d" % (c["signal"], c["from"], c["hops"][0]["line"]) for c in d["copies"]["chain"])
                print("     cond %-24s %s  (L%d)%s" % (d["id"], d["class"], d["line"], extra))
                for p in d.get("paths", [])[:4]:
                    print("          loose path (combined): " + " -> ".join("%s<-%s@L%d(%s)" % s for s in p))
        # port-map feeders of the child ports that are terms or conditions of a count
        wanted = set()
        for c in x["counts"]:
            if c["entity"] == x["unit"]:
                continue
            for d in c["terms"] + c["conditions"]:
                if d["class"] == "input port":
                    wanted.add((c["entity"], d["id"]))
                elif "copies" in d:
                    wanted.add((c["entity"], d["copies"]["port"]))
        for f in x["feeders"]:
            if (f["entity"], f["port"]) in wanted:
                print("  feeder %s(%s).%s <= %s  L%d  unit ids %s" % (f["instance"], f["entity"], f["port"], f["expr"], f["line"], f["unit_ids"]))
    print()
    print("other additions (not self-feeding); port terms shown:")
    for x in results:
        for c in x["other_additions"]:
            pt = ["%s(%s)" % (t["id"], t["class"]) for t in c["terms"] if t["class"] != "internal"]
            print("  %s %s.%s L%d %s   %s" % (x["module"], c["entity"], c["target"], c["line"], c["text"].strip()[:90], "; ".join(pt)))


if __name__ == "__main__":
    main()
