"""Construct A, "done and wait inputs": candidate finder.

Candidate = one-bit, non-record INPUT port of the top entity (entity named as the
module) whose closed-set roles are only "condition" (and "read").

For each candidate the script prints every occurrence line with its enclosing
`case ... is` selector, the enclosing `when X =>` branch, and whether the if-block
that holds the test assigns a state (a `...state <=` line before the matching
`end if` / `elsif` / `else`). The hand reading is done on the printed lines; the
automatic flag is only an aid, checked by the self-test below.

Run: python -B construct_a.py   (prints SELF-TEST, the dump, and writes construct_a.json)
"""
import json, os, re

ROOT = r"E:\jobs\ff\test\Prepoison_subset"
INP = os.path.join(ROOT, "experiments", "03_two_phase_csa_pio", "lab", "inputs", "v1")
GT = os.path.join(ROOT, "data", "ground_truth", "manual_gt_neorv32.json")
SKIP = {"neorv32_boot_rom", "neorv32_fifo"}
ONE_BIT = re.compile(r"^(std_u?logic|bit)$", re.I)


def load_rtl(path):
    lines, order = {}, []
    for raw in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"^\s*(\d+) \|(?: (.*))?$", raw.rstrip("\n"))
        if not m:
            continue
        n = int(m.group(1))
        lines[n] = m.group(2) or ""
        order.append(n)
    return lines, order


def strip_comment(s):
    return s.split("--", 1)[0]


def parse_top_ports(lines, order, module):
    """Return {name: (direction, type_string, decl_line)} for the entity named `module`."""
    ent_re = re.compile(r"^\s*entity\s+%s\s+is\b" % re.escape(module), re.I)
    end_re = re.compile(r"^\s*end\s+(entity\s+)?%s\s*;" % re.escape(module), re.I)
    i0 = next((i for i, n in enumerate(order) if ent_re.match(lines[n])), None)
    if i0 is None:
        return {}
    ports, in_port, buf, buf_line = {}, False, "", None
    for n in order[i0 + 1:]:
        t = strip_comment(lines[n])
        if end_re.match(t):
            break
        if not in_port:
            if re.match(r"^\s*port\s*\(", t, re.I):
                in_port = True
                t = re.sub(r"^\s*port\s*\(", "", t, flags=re.I)
            else:
                continue
        if not buf.strip():
            buf_line = n
        buf += " " + t
        # the port list closes with an unbalanced ")" (more ")" than "(" in the buffer)
        while ";" in buf or (re.search(r"\)\s*$", buf) and buf.count(")") > buf.count("(")):
            if ";" in buf:
                decl, buf = buf.split(";", 1)
                while decl.count(")") > decl.count("("):   # the list's own closing ")" on a `);` line
                    decl = decl.rstrip()[:-1]
                    in_port = False
            else:
                decl, buf = re.sub(r"\)\s*$", "", buf), ""
                in_port = False
            m = re.match(r"^\s*([\w\s,]+?)\s*:\s*(in|out|inout|buffer)\s+(.+?)\s*$", decl, re.I)
            if m:
                names = [x.strip() for x in m.group(1).split(",")]
                ty = m.group(3).split(":=")[0].strip()
                for nm in names:
                    ports[nm] = (m.group(2).lower(), ty, buf_line)
            if buf.strip():
                buf_line = n
        if not in_port:
            break
    return ports


def closed_set_ports(cs, module):
    for e in cs["entity list"]:
        if e["entity name"] == module:
            return {p["port"]: p for p in e["port list"]}
    return {}


def enclosing(lines, order, n):
    """Walk backwards from line n: nearest `when X =>` and the `case Y is` that owns it."""
    idx = order.index(n)
    depth, when, sel = 0, None, None
    for k in range(idx - 1, -1, -1):
        t = strip_comment(lines[order[k]]).strip().lower()
        if re.match(r"^end\s+case\b", t):
            depth += 1
            continue
        m = re.match(r"^case\s+(.+?)\s+is\b", t)
        if m:
            if depth == 0:
                sel = m.group(1)
                break
            depth -= 1
            continue
        if depth == 0 and when is None:
            m = re.match(r"^when\s+(.+?)\s*=>", t)
            if m:
                when = m.group(1)
    return sel, when


def if_block_assigns_state(lines, order, n):
    """From line n (an if/elsif), look forward to the matching end if / next elsif/else and
    report any `...state <=` assignment inside the branch that the test opens."""
    idx = order.index(n)
    t0 = strip_comment(lines[n]).strip().lower()
    if not re.match(r"^(if|elsif)\b", t0):
        return None, []
    depth, hits = 0, []
    for k in range(idx, len(order)):
        t = strip_comment(lines[order[k]]).strip().lower()
        if k > idx and re.match(r"^if\b", t):
            depth += 1
        if re.match(r"^end\s+if\b", t):
            if depth == 0:
                break
            depth -= 1
            continue
        if depth == 0 and k > idx and re.match(r"^(elsif|else)\b", t):
            break
        if re.search(r"\bstate\s*<=", t) or re.search(r"\.state\s*<=", t):
            hits.append(order[k])
    return True, hits


def main():
    gt = json.load(open(GT, encoding="utf-8"))["modules"]
    out = []
    for split in ("tuning", "heldout"):
        for module in sorted(os.listdir(os.path.join(INP, split))):
            d = os.path.join(INP, split, module)
            if module in SKIP or not os.path.isdir(d):
                continue
            lines, order = load_rtl(os.path.join(d, "rtl.txt"))
            cs = json.load(open(os.path.join(d, "closed_set.json"), encoding="utf-8"))
            ports = parse_top_ports(lines, order, module)
            csp = closed_set_ports(cs, module)
            ref = {a["element"] for a in gt[module]["assets"]}
            for name, (dirn, ty, dl) in ports.items():
                if dirn != "in" or not ONE_BIT.match(ty):
                    continue
                p = csp.get(name)
                if p is None:
                    continue
                roles = set(p["role in RTL"])
                if "condition" not in roles:
                    continue
                strict = roles <= {"condition", "read"}   # the task's filter; others are the widened pass
                occ = []
                for n in p["occurrence lines"]:
                    if n == dl or n not in lines:
                        continue
                    text = lines[n]
                    sel, when = enclosing(lines, order, n)
                    is_if, hits = if_block_assigns_state(lines, order, n)
                    occ.append({"line": n, "text": text.strip(), "case_sel": sel, "when": when,
                                "is_if": bool(is_if), "state_assign_lines": hits})
                out.append({"split": split, "module": module, "element": name, "type": ty,
                            "decl_line": dl, "roles": sorted(roles), "strict": strict,
                            "reference": name in ref, "occ": occ})
    # ---- self-test against hand-read lines (cpu_control, read by hand 2026-10-18) ----
    cc = {r["element"]: r for r in out if r["module"] == "neorv32_cpu_control"}
    assert set(cc) == {"alu_cp_done_i", "lsu_wait_i"}, set(cc)
    a = {o["line"]: o for o in cc["alu_cp_done_i"]["occ"]}
    assert 505 in a and a[505]["when"] == "ex_alu_wait" and a[505]["case_sel"] == "exe_engine.state", a
    assert a[505]["state_assign_lines"] == [507], a[505]
    w = {o["line"]: o for o in cc["lsu_wait_i"]["occ"]}
    assert 536 in w and w[536]["when"] == "ex_mem_rsp" and w[536]["state_assign_lines"] == [541], w
    assert cc["alu_cp_done_i"]["reference"] and cc["lsu_wait_i"]["reference"]
    allp = parse_top_ports(*load_rtl(os.path.join(INP, "heldout", "neorv32_cpu_control", "rtl.txt")), "neorv32_cpu_control")
    assert len(allp) == 17 and allp["ctrl_o"] == ("out", "ctrl_bus_t", 72), allp
    assert allp["irq_fast_i"] == ("in", "std_ulogic_vector(15 downto 0)", 87), allp["irq_fast_i"]
    dec = parse_top_ports(*load_rtl(os.path.join(INP, "heldout", "neorv32_cpu_decompressor", "rtl.txt")), "neorv32_cpu_decompressor")
    assert dec == {"instr_i": ("in", "std_ulogic_vector(15 downto 0)", 19), "instr_o": ("out", "std_ulogic_vector(31 downto 0)", 20)}, dec
    # hand-read negatives: a test inside a clocked process with no case/state (read by hand 2026-10-18)
    by = {(r["module"], r["element"]): r for r in out}
    o = {x["line"]: x for x in by[("neorv32_wdt", "rstn_dbg_i")]["occ"]}
    assert o[171]["case_sel"] is None and o[171]["when"] is None and o[171]["state_assign_lines"] == [], o
    o = {x["line"]: x for x in by[("neorv32_cpu_cp_cfu", "start_i")]["occ"]}
    assert o[204]["is_if"] and o[204]["state_assign_lines"] == [] and o[204]["case_sel"] is None, o
    o = {x["line"]: x for x in by[("neorv32_debug_auth", "enable_i")]["occ"]}
    assert list(o) == [54] and o[54]["state_assign_lines"] == [], o
    # widened pass: xbus_ack_i carries "operand" too (line 155), tested at line 92 with no case/state
    x = by[("neorv32_xbus", "xbus_ack_i")]
    assert x["strict"] is False and x["reference"] and sorted(y["line"] for y in x["occ"]) == [92, 155], x
    # xbus_err_i (the entity's last port) is the other widened entry: same test line 92 as the ack
    e = by[("neorv32_xbus", "xbus_err_i")]
    assert e["strict"] is False and 92 in [y["line"] for y in e["occ"]], e
    extra = [(r["module"], r["element"], r["roles"], r["type"]) for r in out
             if not r["strict"] and r["module"] != "neorv32_xbus"]
    assert not extra, f"unexpected widened entry: {extra}"
    print("SELF-TEST PASS")
    # ---- dump ----
    for r in out:
        print("=" * 100)
        print(f"{r['module']} [{r['split']}]  {r['element']} : in {r['type']}  decl {r['decl_line']}  roles {r['roles']}  strict={r['strict']}  REFERENCE={r['reference']}")
        for o in r["occ"]:
            flag = "FSM-NEXT-STATE" if o["state_assign_lines"] else ("if" if o["is_if"] else "-")
            print(f"   {o['line']:5d} | case {str(o['case_sel']):28} when {str(o['when']):22} {flag:15} {o['state_assign_lines']}")
            print(f"         {o['text']}")
    here = os.path.dirname(os.path.abspath(__file__))
    json.dump(out, open(os.path.join(here, "construct_a.json"), "w"), indent=1)
    print(f"\ncandidates={len(out)} reference={sum(r['reference'] for r in out)} non_reference={sum(not r['reference'] for r in out)}")


if __name__ == "__main__":
    main()
