"""Statement-level corrections to the flow graph, found by the block-diagram review of 2026-10-10.

The map's records say "Y flows into X at X's occurrence O". Three things the map does not account for:

  dead        O is overwritten later in the same process run: a later full assignment to X sits in the same statement
              list as O, or in one that encloses it (cache 159-161: `bus_req_o <= host_req_i;` then
              `bus_req_o.stb <= '0';`). A flow into a dead occurrence never reaches X.
  exclusive   Y is produced only in generate branches that can never be built together with O's branch
              (imem: addr_ff assigned under `if not alt_style_c generate`, read under `if alt_style_c generate`).
              Decided exactly: every condition is a boolean expression over generics and constants, and two branch
              chains are compatible when some assignment of values makes all their conditions true.
  var_cond    a process variable computed from elements is used as a case selector or an if/elsif condition
              (gpio 123-124: `sel_v := irq_typ(i) & irq_pol(i); case sel_v is`). The elements it was computed from
              decide every assignment under that case or if: implicit flows the map never recorded.

  reset_like  a condition tested in an if arm before the clock-edge arm, where the arm's assignment reads no element
              (only literals, constants or generics), is a reset, as with a literal (sysinfo 91-92:
              `sysinfo(0) <= std_ulogic_vector(to_unsigned(CLOCK_FREQUENCY, 32))`). The map calls it GATES because
              it counts a generic as not fixed.
  dead (partial) a slice assignment that a later assignment of the same slice, written the same way, replaces in the
              same statement list (decompressor 144 and 146: `decoded(instr_rd_msb_c downto instr_rd_lsb_c)`).

Used by pio_graph.file_graph and pio_blocks.diagram, so the graph and both diagram views agree.
"""
from __future__ import annotations

import itertools
import json
import re
from collections import defaultdict
from functools import lru_cache

import pio_graph as G

LHS = {"LHS_PROC", "LHS_CONC"}
PARTIAL = {"INDEXED_NAME", "PART_SELECT"}


@lru_cache(maxsize=None)
def occ_info(m) -> dict:
    """{(entity, element, occurrence id): (line, sites, context)} from the occurrence profiles of the map version."""
    p = G.FIX / "occurrence_profiles" / f"{m}.json"
    out = {}
    if not p.exists():
        return out
    for ent, els in json.loads(p.read_text(encoding="utf-8")).items():
        for name, rows in els.items():
            for r in rows:
                ln = r.get("Occurrence Lines")
                ln = ln[0] if isinstance(ln, list) else ln
                out[(ent, name, r.get("Occurrence ID"))] = (ln, tuple(r.get("SITE Tagged") or []), r.get("Context") or "")
    return out


def frames(ctx: str) -> list[str]:
    return [s.strip() for s in ctx.split(" in ")] if ctx else []


@lru_cache(maxsize=None)
def source_lines(m) -> dict:
    """{line number: text with comments removed} of the module's RTL file."""
    t = (G.RTL[G.split_of(m)] / f"{m}.vhd").read_text(encoding="utf-8", errors="ignore").split("\n")
    return {i: re.sub(r"--.*", "", l) for i, l in enumerate(t, 1)}


# ------------------------------------------------------------------------------------------- generate branches ---
def gen_chain(m, ctx: str) -> tuple[str, ...]:
    """Conditions of the generate-if branches that enclose an occurrence, outermost last."""
    out = []
    for f in frames(ctx):
        mm = re.match(r"generate if branch (\d+)-\d+$", f)
        if mm:
            t = source_lines(m).get(int(mm.group(1)), "")
            c = re.search(r"\b(?:if|elsif)\b(.*?)\bgenerate\b", t, re.I)
            out.append(c.group(1).strip() if c else "true")
    return tuple(out)


_TOK = re.compile(r"\s*([A-Za-z_]\w*|\d+|<=|>=|/=|=|<|>|\(|\))")
_CMP = {"=": "==", "/=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}
_KEYWORDS = {"and", "or", "not", "true", "false"}


def _tokens(cond: str) -> list[str]:
    """Words, numbers, operators and parentheses; a name followed by a parenthesised index stays one token
    (dev_en_list_c(i)), a keyword never takes one (`and (x > 0)`)."""
    raw = [t for t in _TOK.findall(cond) if t.strip()]
    out, i = [], 0
    while i < len(raw):
        t = raw[i]
        if re.match(r"[A-Za-z_]\w*$", t) and t.lower() not in _KEYWORDS and i + 1 < len(raw) and raw[i + 1] == "(":
            depth, j = 0, i + 1
            while j < len(raw):
                depth += {"(": 1, ")": -1}.get(raw[j], 0)
                if depth == 0:
                    break
                j += 1
            out.append(t + "".join(raw[i + 1:j + 1]))
            i = j + 1
            continue
        out.append(t)
        i += 1
    return out


def _compile(cond: str):
    """-> (python expression over v[...], boolean atoms, numeric atoms, numbers) for a VHDL generate condition."""
    toks = _tokens(cond)
    out, booleans, numerics, numbers = [], set(), set(), set()
    for i, t in enumerate(toks):
        tl = t.lower()
        if tl in ("and", "or", "not"):
            out.append(f" {tl} ")
        elif tl in ("true", "false"):
            out.append(" True " if tl == "true" else " False ")
        elif t in _CMP:
            out.append(_CMP[t])
        elif t.isdigit():
            out.append(t)
            numbers.add(int(t))
        elif t in "()":
            out.append(t)
        else:
            key = re.sub(r"\s+", "", t).lower()
            prev = toks[i - 1] if i else ""
            nxt = toks[i + 1] if i + 1 < len(toks) else ""
            (numerics if prev in _CMP or nxt in _CMP else booleans).add(key)
            out.append(f"v[{key!r}]")
    return "".join(out), booleans, numerics, numbers


@lru_cache(maxsize=None)
def compatible(chain_a: tuple, chain_b: tuple) -> bool:
    """True when some values of the generics make every condition of both chains true."""
    conds = list(chain_a) + list(chain_b)
    if not conds:
        return True
    parts = [_compile(c) for c in conds]
    booleans = set().union(*(p[1] for p in parts))
    numerics = set().union(*(p[2] for p in parts)) - booleans
    numbers = set().union(*(p[3] for p in parts)) | {0, 1}
    dom = sorted({n + d for n in numbers for d in (-1, 0, 1)})
    names = sorted(booleans) + sorted(numerics)
    domains = [[False, True]] * len(booleans) + [dom] * len(numerics)
    exprs = [p[0] for p in parts]
    for vals in itertools.product(*domains):
        v = dict(zip(names, vals))
        try:
            if all(eval(e, {"__builtins__": {}}, {"v": v}) for e in exprs):  # noqa: S307 - our own expressions
                return True
        except Exception:  # noqa: BLE001 - an expression we cannot evaluate is treated as satisfiable
            return True
    return False


@lru_cache(maxsize=None)
def source_chains(m, ent, name) -> tuple | None:
    """Generate chains of the places that produce Y (assignments, port-map actuals); None when nothing produces it
    here (an input port, a constant)."""
    ch = {gen_chain(m, ctx) for (e, n, _), (_, s, ctx) in occ_info(m).items()
          if e == ent and n == name and (set(s) & LHS or "ASSOC_ACTUAL" in s)}
    return tuple(sorted(ch)) if ch else None


# --------------------------------------------------------------------------------------------------- dead ---
@lru_cache(maxsize=None)
def dead(m) -> frozenset:
    """Assignment occurrences overwritten later in the same process run (see the module docstring)."""
    by = defaultdict(list)
    for (ent, name, oid), (ln, s, ctx) in occ_info(m).items():
        if "LHS_PROC" in s:
            by[(ent, name)].append((ln, oid, s, ctx))
    src = source_lines(m)

    def lhs(ln):
        t = src.get(ln, "")
        return re.sub(r"\s+", "", t.split("<=", 1)[0]).lower() if t.count("<=") == 1 else None
    out = set()
    for (ent, name), occs in by.items():
        for ln1, o1, s1, c1 in occs:
            for ln2, o2, s2, c2 in occs:
                if ln2 <= ln1 or "process " not in c2 or not c1.endswith(c2):
                    continue
                if not set(s2) & PARTIAL or (set(s1) & PARTIAL and lhs(ln1) is not None and lhs(ln1) == lhs(ln2)):
                    out.add((ent, name, o1))
                    break
    return frozenset(out)


def live_partners(m, ent, y, x, partner_ids) -> list:
    """The target occurrences a record Y -> X really reaches: not dead, and buildable together with some place that
    produces Y."""
    info, dd = occ_info(m), dead(m)
    src = source_chains(m, ent, y)
    out = []
    for oid in partner_ids:
        if (ent, x, oid) in dd:
            continue
        if src is not None:
            ctx = info.get((ent, x, oid), (None, (), ""))[2]
            chx = gen_chain(m, ctx)
            if not any(compatible(cs, chx) for cs in src):
                continue
        out.append(oid)
    return out


# ------------------------------------------------------------------------------------------------ var_cond ---
@lru_cache(maxsize=None)
def process_vars(m) -> dict:
    """{(entity, process frame): (variables, {variable: assignment lines}, {variable: {element: lines where it feeds
    the variable, directly or through other variables}})} for every process that declares variables."""
    info, src = occ_info(m), source_lines(m)
    procs = {}                                       # (entity, frame string) -> (a, b)
    for (ent, _, _), (_, _, ctx) in info.items():
        for f in frames(ctx):
            mm = re.match(r"process (?:\w+ )?(\d+)-(\d+)$", f)
            if mm:
                procs[(ent, f)] = (int(mm.group(1)), int(mm.group(2)))
    out = {}
    for (ent, pf), (a, b) in procs.items():
        decl = " ".join(src.get(i, "") for i in range(a, b + 1))
        vars_ = set()
        for mm in re.finditer(r"\bvariable\s+([\w\s,]+?)\s*:", decl, re.I):
            vars_ |= {v.strip().lower() for v in mm.group(1).split(",") if v.strip()}
        if not vars_:
            continue
        in_proc = {k: v for k, v in info.items() if k[0] == ent and pf in v[2]}
        # direct element sources of each variable: elements read on the lines of the statements that assign it
        assign_lines = defaultdict(list)
        for i in range(a, b + 1):
            mm = re.match(r"\s*(\w+)(?:\s*\([^:]*?\))?(?:\.\w+)?\s*:=", src.get(i, ""))
            if mm and mm.group(1).lower() in vars_:
                j = i
                while j <= b and ";" not in src.get(j, ""):
                    j += 1
                assign_lines[mm.group(1).lower()].extend(range(i, j + 1))
        srcs = defaultdict(lambda: defaultdict(set))    # variable -> element -> lines where it feeds the variable
        for v, lines in assign_lines.items():
            for (e, n, o), (ln, s, ctx) in in_proc.items():
                if ln in lines and not set(s) & (LHS | {"DECL_SIGNAL", "DECL_PORT", "DECL_FIELD", "PROCESS_TRIG",
                                                         "FIELD_USE"}):
                    srcs[v][n].add(ln)
        # variables computed from other variables
        changed = True
        while changed:
            changed = False
            for v, lines in assign_lines.items():
                rhs = " ".join(src.get(i, "").split(":=", 1)[-1] for i in lines).lower()
                for w in vars_:
                    if w == v or not re.search(rf"\b{w}\b", rhs):
                        continue
                    for n, ls in list(srcs[w].items()):
                        if not ls <= srcs[v][n]:
                            srcs[v][n] |= ls
                            changed = True
        out[(ent, pf)] = (vars_, {v: list(ls) for v, ls in assign_lines.items()},
                          {v: {n: set(ls) for n, ls in d.items()} for v, d in srcs.items()})
    return out


def var_value_lines(m, ent, y, x_ctx, x_lines, x: str = "") -> list:
    """Lines where element Y feeds a process variable that the statement on x_lines reads. When X is a record field
    and the statement reads the bare record variable (bus 395: `int_rsp <= tmp_v;`, so int_rsp.ack gets tmp_v.ack),
    only the variable's own assignments to that field, or to the whole variable, count (390-392 build one field each)."""
    pf = next((f for f in frames(x_ctx) if f.startswith("process ")), None)
    pv = process_vars(m).get((ent, pf))
    if not pv:
        return []
    vars_, assign, srcs = pv
    src = source_lines(m)
    text = " ".join(src.get(i, "") for i in x_lines).split("<=", 1)[-1].lower()
    field = x.split(".", 1)[1].lower() if "." in x else None
    out = set()
    for v in vars_:
        if not re.search(rf"\b{v}\b", text):
            continue
        keep = set(srcs.get(v, {}).get(y, ()))
        if field and re.search(rf"\b{v}\s*;", text):
            own = set(assign.get(v, []))
            mine = {i for i in own if re.match(rf"\s*{v}\s*(?:\.\s*{field}\b|:=)", src.get(i, ""), re.I)}
            keep = {ln for ln in keep if ln not in own or ln in mine}
        out |= keep
    return sorted(out)


@lru_cache(maxsize=None)
def var_cond_flows(m) -> tuple:
    """((entity, source element, target element, target occurrence id, (lines...)), ...): implicit flows through a
    process variable used as a case selector or an if/elsif condition."""
    info, src = occ_info(m), source_lines(m)
    out = set()
    for (ent, pf), (vars_, assign_lines, srcs) in process_vars(m).items():
        in_proc = {k: v for k, v in info.items() if k[0] == ent and pf in v[2]}
        # conditions and selectors that use a variable
        cond_frames = {}
        for (_, _, _), (ln, s, ctx) in in_proc.items():
            for f in frames(ctx):
                mm = re.match(r"case (.+) (\d+)-(\d+)$", f)
                if mm:
                    cond_frames[("case", f, int(mm.group(2)))] = mm.group(1)
                mm = re.match(r"if (\d+)-(\d+)$", f)
                if mm:
                    i = int(mm.group(1))
                    cond_frames[("if", f, i)] = _cond_text(src, i, "if")
                mm = re.match(r"elsif branch (\d+)-(\d+)$", f)
                if mm:
                    i = int(mm.group(1))
                    cond_frames[("elsif", f, i)] = _cond_text(src, i, "elsif")
        for (kind, f, line), text in cond_frames.items():
            used = {w for w in vars_ if re.search(rf"\b{w}\b", text.lower())}
            elems = defaultdict(set)
            for w in used:
                for n, ls in srcs[w].items():
                    elems[n] |= ls
            if not elems:
                continue
            for (e, x, o), (ln, s, ctx) in in_proc.items():
                if "LHS_PROC" not in s:
                    continue
                if kind == "elsif":
                    parent = [g for g in frames(ctx) if g.startswith("if ")]
                    if f not in frames(ctx) and not any(_after_elsif(f, g, ln) for g in parent):
                        continue
                elif f not in frames(ctx):
                    continue
                for y, ls in elems.items():
                    out.add((ent, y, x, o, tuple(sorted(ls) + [line])))
    return tuple(sorted(out))


# ------------------------------------------------------------------------------------------------ reset_like ---
@lru_cache(maxsize=None)
def value_targets(m) -> frozenset:
    """{(entity, element, occurrence id)}: assignment occurrences whose statement reads an element as a value
    (CARRIES or SOURCES, or GATES from an operand site)."""
    st = G.sites(m)
    out = set()
    for arr in ("ports", "signals"):
        for e in (G.code_map(m) or {}).get(arr, []):
            ent, y = e["entity"], e["name"]
            for r in e.get("relationship", []) or []:
                t = r["type"]
                operand = t == "GATES" and any(not set(st.get(ent, {}).get(y, {}).get(str(i), [])) & G.COND_SITES
                                               for i in r.get("at") or [])
                if t in ("CARRIES", "SOURCES") or operand:
                    for x, ps in (r.get("partner_at") or {}).items():
                        out |= {(ent, x, p) for p in ps}
    return frozenset(out)


def reset_like(m, ent, y, at_ids, x, oid) -> bool:
    """Y, tested at one of at_ids in an if arm that comes before a clock-edge arm of the same if, decides X's
    assignment oid directly in that arm, and that assignment reads no element: a reset (see the module docstring)."""
    info = occ_info(m)
    xo = info.get((ent, x, oid))
    if xo is None or (ent, x, oid) in value_targets(m):
        return False
    for i in at_ids:
        yo = info.get((ent, y, i))
        if yo is None or "IF_COND" not in yo[1] or yo[2] != xo[2]:
            continue
        fr = frames(yo[2])
        mb = re.match(r"(?:then|elsif) branch (\d+)-\d+$", fr[0]) if fr else None
        if not mb or len(fr) < 2 or not fr[1].startswith("if "):
            continue
        for (e2, _n, _o), (_l, s2, c2) in info.items():
            f2 = frames(c2)
            if e2 == ent and "EDGE_CHECK" in s2 and len(f2) >= 2 and f2[1:] == fr[1:]:
                me = re.match(r"elsif branch (\d+)-\d+$", f2[0])
                if me and int(me.group(1)) > int(mb.group(1)):
                    return True
    return False


def _cond_text(src, i, kw) -> str:
    t = ""
    for j in range(i, i + 6):
        t += " " + src.get(j, "")
        if re.search(r"\bthen\b", src.get(j, ""), re.I):
            break
    mm = re.search(rf"\b{kw}\b(.*?)\bthen\b", t, re.I | re.S)
    return mm.group(1) if mm else t


def _after_elsif(elsif_frame, if_frame, line) -> bool:
    """An elsif condition at line c decides its own branch and every later branch of the same if."""
    c = int(re.match(r"elsif branch (\d+)-", elsif_frame).group(1))
    a, b = map(int, re.match(r"if (\d+)-(\d+)$", if_frame).groups())
    return a <= c <= b and line >= c


# ------------------------------------------------------------------------------------------------ self-tests ---
def _oid(m, ent, name, line):
    return next((o for (e, n, o), (l, _s, _c) in occ_info(m).items() if e == ent and n == name and l == line), None)


def selftest(log=print) -> bool:
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        log(f"   {'ok  ' if cond else 'FAIL'} {label}")

    check("conditions: IMEM_INIT/not alt_style_c vs IMEM_INIT/alt_style_c are exclusive",
          not compatible(("not alt_style_c", "IMEM_INIT"), ("alt_style_c", "IMEM_INIT")))
    check("conditions: (CNT_WIDTH <= 32) vs (CNT_WIDTH > 32) are exclusive",
          not compatible(("(CNT_WIDTH <= 32)",), ("(CNT_WIDTH > 32)",)))
    check("conditions: ZIHPM_EN and (HPM_NUM > 0) vs (not ZIHPM_EN) or (HPM_NUM = 0) are exclusive",
          not compatible(("ZIHPM_EN and (HPM_NUM > 0)",), ("(not ZIHPM_EN) or (HPM_NUM = 0)",)))
    check("conditions: not (A or B) vs (not A) and (not B) are compatible; REQ_REG_EN vs RSP_REG_EN compatible",
          compatible(("not (RISCV_ISA_Zba or RISCV_ISA_Zbb)",), ("(not RISCV_ISA_Zba) and (not RISCV_ISA_Zbb)",))
          and compatible(("REQ_REG_EN",), ("RSP_REG_EN",)))
    check("conditions: A or B vs not (A or B) are exclusive",
          not compatible(("A or B",), ("not (A or B)",)))
    check("conditions: dev_en_list_c(i) vs not dev_en_list_c(i) are exclusive",
          not compatible(("dev_en_list_c(i)",), ("not dev_en_list_c(i)",)))
    # hand-read data/RTL_data/neorv32_cache.vhd 159-161: `bus_req_o <= host_req_i;` `bus_req_o.stb <= '0';`
    # `bus_req_o.fence <= ...` (in process ctrl_engine_comb, same statement list)
    dd = dead("neorv32_cache")
    info = occ_info("neorv32_cache")
    d159 = {n for (e, n, o) in dd if info[(e, n, o)][0] == 159}
    check(f"cache 159: bus_req_o.stb and bus_req_o.fence copies are dead, bus_req_o.addr is not ({sorted(d159)})",
          {"bus_req_o.stb", "bus_req_o.fence"} <= d159 and "bus_req_o.addr" not in d159)
    # hand-read data/RTL_data/neorv32_imem.vhd: addr_ff at 84 (if IMEM_INIT / if not alt_style_c), 92 (IMEM_INIT /
    # alt_style_c), 134 (not IMEM_INIT / not alt_style_c), 142 (not IMEM_INIT / alt_style_c); rdata at 95 reads it
    ent = "neorv32_imem"
    occ95 = [o for (e, n, o), v in occ_info(ent).items() if n == "rdata" and v[0] == 95 and "LHS_CONC" in v[1]]
    ch95 = gen_chain(ent, occ_info(ent)[(ent, "rdata", occ95[0])][2]) if occ95 else ()
    srcs = source_chains(ent, ent, "addr_ff") or ()
    comp = [cs for cs in srcs if compatible(cs, ch95)]
    check(f"imem 95: of addr_ff's producers only the IMEM_INIT/alt_style_c one (92) can feed it ({comp})",
          len(comp) == 1 and "alt_style_c" in comp[0] and "IMEM_INIT" in comp[0] and not any("not" in c for c in comp[0]))
    # hand-read data/RTL_heldout/neorv32_gpio.vhd 123-129: `sel_v := irq_typ(i) & irq_pol(i); case sel_v is ...
    # irq_trig(i) <= ...`
    vf = var_cond_flows("neorv32_gpio")
    got = {(y, x) for (_, y, x, _, _) in vf}
    check(f"gpio 123-124: irq_typ and irq_pol decide irq_trig through sel_v ({sorted(got)[:4]})",
          {("irq_typ", "irq_trig"), ("irq_pol", "irq_trig")} <= got)
    vp = {y for (_, y, _, _, _) in var_cond_flows("neorv32_cpu_pmp")}
    check(f"pmp 134: sources through mode_v are fields, never the whole record ctrl_i ({sorted(vp)})",
          vp and "ctrl_i" not in vp)
    # hand-read data/RTL_heldout/neorv32_cpu_cp_fpu.vhd 630-678: cond_v(0) from comp_less_ff at 647/655 and from
    # ctrl_i.ir_funct3 at 640/645/647/651/653/655; cond_v(2) from rs1_class at 660; cond_v(1) from rs2_class at 661;
    # `case cond_v is` at 672
    fl = {y: ls for (_, y, x, _, ls) in var_cond_flows("neorv32_cpu_cp_fpu") if x == "fu_min_max.result"}
    want = {"comp_less_ff": (647, 655, 672), "ctrl_i.ir_funct3": (640, 645, 647, 651, 653, 655, 672),
            "fpu_operands.rs1_class": (660, 672), "fpu_operands.rs2_class": (661, 672)}
    check(f"fpu 630-678: lines per source of cond_v ({fl})", all(fl.get(k) == v for k, v in want.items()))
    # hand-read data/RTL_heldout/neorv32_cpu_decompressor.vhd 144/146: the same slice of decoded, then a constant
    d = "neorv32_cpu_decompressor"
    o144, o145 = _oid(d, d, "decoded", 144), _oid(d, d, "decoded", 145)
    check(f"decompressor 144 is overwritten by 146 (same slice); 145 is not ({o144}, {o145})",
          (d, "decoded", o144) in dead(d) and (d, "decoded", o145) not in dead(d))
    # hand-read data/RTL_heldout/neorv32_sysinfo.vhd 91-93: `if (rstn_i = '0') then sysinfo(0) <= ...(CLOCK_FREQUENCY..);
    # elsif rising_edge(clk_i)`; 94-95: a bus condition inside the edge arm is not a reset
    s_ = "neorv32_sysinfo"
    check("sysinfo 91-92: rstn_i is a reset of sysinfo (generic value)",
          reset_like(s_, s_, "rstn_i", [_oid(s_, s_, "rstn_i", 91)], "sysinfo", _oid(s_, s_, "sysinfo", 92)))
    ox95 = next((o for (e, n, o), (l, _s, _c) in occ_info(s_).items() if l == 95 and "LHS_PROC" in _s), None)
    n95 = next((n for (e, n, o), (l, _s, _c) in occ_info(s_).items() if l == 95 and "LHS_PROC" in _s), None)
    check(f"sysinfo 94-95: bus_req_i.stb decides {n95} but is no reset",
          not reset_like(s_, s_, "bus_req_i.stb", [_oid(s_, s_, "bus_req_i.stb", 94)], n95, ox95))
    # hand-read data/RTL_heldout/neorv32_cpu_control.vhd 266-272: reset arm sets exe_engine.pc from BOOT_ADDR (generic)
    c_ = "neorv32_cpu_control"
    opc = next((o for (e, n, o), (l, _s, _c) in occ_info(c_).items() if n == "exe_engine.pc" and 266 <= l <= 275
                and "LHS_PROC" in _s), None)
    check(f"cpu_control 266: rstn_i is a reset of exe_engine.pc (occurrence {opc})",
          reset_like(c_, c_, "rstn_i", [_oid(c_, c_, "rstn_i", 266)], "exe_engine.pc", opc))
    return ok
