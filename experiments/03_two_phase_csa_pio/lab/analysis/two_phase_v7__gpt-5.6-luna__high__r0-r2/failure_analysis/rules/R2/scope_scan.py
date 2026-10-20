"""R2 scope scan (closed-set facts only, no reference files).

Part A: non-record unit input ports whose bit reaches the unit's logic only
through synchronizer stages (registers whose value comes only from that port
and their own bits; wires only copying a stage), whose stage elements give
value to nothing outside the chain and decide only state registers.
Part B: output ports of a this-file child entity, non-record, assigned one bit
of another element of that entity (a count bit), printed with the RTL line.

Self-test against hand-read lines:
  debug_dtm jtag_tms_i: RTL 101 (tms_ff <= tms_ff(1 downto 0) & jtag_tms_i),
    110 (tms <= tms_ff(2)), 123-138 (tms decides tap_ctrl_state) -> MATCH
  uart uart_ctsn_i: RTL 337 (cts <= cts(0) & uart_ctsn_i), 359 (decides
    tx_engine.state) -> MATCH
  debug_dtm jtag_tdi_i: RTL 111, 181, 194-197 (tdi gives value to tap_reg.*) -> NO
  uart uart_rxd_i: RTL 434 (sync(2) shifted into rx_engine.sreg) -> NO
  trng valid_o: RTL 367 (valid_o <= sample_cnt(sample_cnt'left)) -> Part B hit
"""
import json, os, re, sys

ROOT = r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab\inputs\v1\tuning"


def els(entity):
    out = {}
    for p in entity["port list"]:
        out[p["port"]] = p
        for f in p.get("fields", []):
            out[f["field"]] = f
    for s in entity["signal list"]:
        out[s["signal"]] = s
        for f in s.get("fields", []):
            out[f["field"]] = f
    return out


def partners(e, group):
    return [c["element"] for c in e.get("counterparts", {}).get(group, [])
            if isinstance(c.get("element"), str)]


def is_state_register(e):
    # a register that decides itself (its own value picks its next value) and is a case selector or condition
    roles = e.get("role in RTL", [])
    name = e.get("signal") or e.get("field")
    return ("held on a clock edge" in roles and name in partners(e, "decided by")
            and ("selector" in roles or "condition" in roles))


def part_a(module):
    cs = json.load(open(os.path.join(ROOT, module, "closed_set.json"), encoding="utf-8"))
    dg = open(os.path.join(ROOT, module, "diagram.txt"), encoding="utf-8").read()
    units = set(re.findall(r"^UNIT (\S+)", dg, re.M))
    hits = []
    for ent in cs["entity list"]:
        if ent["entity name"] not in units:
            continue
        E = els(ent)
        for p in ent["port list"]:
            if p["direction"] != "in" or "record type" in p:
                continue
            roles = p.get("role in RTL", [])
            if "clock" in roles or "reset" in roles:
                continue
            first = partners(p, "gives value to")
            if not first or partners(p, "decides"):
                continue
            chain, todo, ok = set(), list(first), True
            while todo:
                n = todo.pop()
                if n in chain:
                    continue
                e = E.get(n)
                if e is None:
                    ok = False
                    break
                src = set(partners(e, "gets value from")) - {n}
                if not src <= ({p["port"]} | chain | set(first)):
                    ok = False
                    break
                chain.add(n)
                for g in partners(e, "gives value to"):
                    if g == n:
                        continue
                    ge = E.get(g)
                    # a wire only copying a stage bit counts as part of the chain
                    if ge is not None and ge.get("type") == "wire" and set(partners(ge, "gets value from")) <= chain | {n}:
                        todo.append(g)
                    else:
                        ok = False
            if not ok or not chain:
                continue
            decided = set()
            for n in chain:
                decided |= set(partners(E[n], "decides"))
            decided -= chain
            if decided and all(d in E and is_state_register(E[d]) for d in decided):
                hits.append((p["port"], sorted(chain), sorted(decided)))
    return hits


def rtl_lines(module):
    out = {}
    for ln in open(os.path.join(ROOT, module, "rtl.txt"), encoding="utf-8"):
        m = re.match(r"\s*(\d+) \|(.*)", ln)
        if m:
            out[int(m.group(1))] = m.group(2)
    return out


def part_b(module):
    cs = json.load(open(os.path.join(ROOT, module, "closed_set.json"), encoding="utf-8"))
    dg = open(os.path.join(ROOT, module, "diagram.txt"), encoding="utf-8").read()
    children = set(re.findall(r"\[inst\] \S+ \((\S+), this file\)", dg))
    R = rtl_lines(module)
    hits = []
    for ent in cs["entity list"]:
        if ent["entity name"] not in children:
            continue
        for p in ent["port list"]:
            if p["direction"] != "out" or "record type" in p:
                continue
            for c in p.get("counterparts", {}).get("gets value from", []):
                for L in c.get("lines", []):
                    txt = R.get(L, "")
                    # one bit of another element: x(x'left), x(x'high) or x(<digit>)
                    if re.search(r"<=\s*\w[\w.]*\((\w[\w.]*'(left|high|low|right)|\d+)\)\s*;", txt):
                        hits.append((ent["entity name"], p["port"], c["element"], L, txt.strip()))
    return hits


def selftest():
    a_dtm = {h[0] for h in part_a("neorv32_debug_dtm")}
    a_uart = {h[0] for h in part_a("neorv32_uart")}
    b_trng = {(h[1], h[3]) for h in part_b("neorv32_trng")}
    checks = [
        ("jtag_tms_i matches", "jtag_tms_i" in a_dtm),
        ("jtag_tdi_i does not match", "jtag_tdi_i" not in a_dtm),
        ("jtag_tck_i does not match", "jtag_tck_i" not in a_dtm),
        ("uart_ctsn_i matches", "uart_ctsn_i" in a_uart),
        ("uart_rxd_i does not match", "uart_rxd_i" not in a_uart),
        ("trng valid_o at RTL 367 found", ("valid_o", 367) in b_trng),
        ("trng data_o not found (whole register, RTL 366)", not any(p == "data_o" for p, _ in b_trng)),
    ]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print("SELFTEST", "PASS" if ok else "FAIL", n)
    return not bad


if __name__ == "__main__":
    if not selftest():
        print("SELF-TEST FAILED: report nothing from this run")
        sys.exit(1)
    for m in sorted(os.listdir(ROOT)):
        for h in part_a(m):
            print("A", m, h)
        for h in part_b(m):
            print("B", m, h)
