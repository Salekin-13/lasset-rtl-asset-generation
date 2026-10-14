"""Fix P4, code check: drop listed Phase 2 primaries that five existing v7 bars already exclude.

Run:  python check.py <out.json>
Reads ONLY the stored v7 replies (failure_analysis/raw/r<k>/phase2/<module>.json, k = 0, 1, 2) and the inputs
(inputs/v1/tuning/<module>/{rtl.txt, closed_set.json}). Opens no reference, scoring or analysis file.
Writes {"r0": {"<short module>": [{"element", "entity", "action": "drop", "test"}]}, "r1": {...}, "r2": {...}}.

Each test is the condition of a v7 bar, stated in closed-set facts (kind of element, direction, record or not, role in
RTL, counterparts) and, where the bar itself says so, RTL text or port names. No element name is used.

  A  read-back OR words (phase1.md:34, phase2.md:34 "a word that an instance outputs for reads of its own control and
     status registers, and that this unit reads only in an OR into the word another instance takes in ... these words
     (that word and the one the OR makes) never qualify"): an internal non-record signal Y set without a clock whose
     every source is an internal non-record signal W, two or more of them, where each W gets its value only from one
     instance output port and gives it only to Y; Y gives its value only to one instance input port, decides nothing,
     and its assigning RTL line is an OR. Port-name guard, as the bar says ("Judge from port names which instance
     outputs and inputs these are"): Y's destination input names a register read-back input (its name holds both
     "csr" and "rdata") and each W's source output names a register read output ("csr" or "rdata"). Drop Y and every W.
  B1 only-tested fields of an input record port that the bars name (phase2.md:34: operation selectors "instruction
     or request fields only picking the operation ... never qualify"; processor context fields "only refines a
     decision ... when this unit only tests it ... never qualify", "Judge what a field tells from port field names";
     bus request record fields "never qualify"; access command fields "register-select address bits, byte
     enables"): a field of a unit input record port whose role in RTL is only "condition", "selector" or "read"
     (never copied, operand or index, so never wired into an instance), AND either (code) the RTL reads it as a
     multi-bit code: a slice or single bit of it, a compare with a constant this unit declares or with a literal
     wider than one bit, or a case on it with declared-constant choices; or (context) its own name has a
     processor-context token (trap, priv, debug, dbg, fetch). A one-bit field tested only against '1' or '0' with no
     such token (a start trigger, a write enable, an acknowledge) is kept: the operation-selector rule judges "a
     start command or pulse" and "a register access's ... write enable" as usual.
  B2 operation-selector ports (phase2.md:34, operation selectors): a non-record unit input port whose role in RTL is
     only "condition", "selector" or "read" and that at least one RTL line compares with a constant this unit declares
     (an operation or format code), either "port = constant" or "case port" with constant choices. Reasoning: a start
     or write-enable flag is tested against a literal bit, an opcode against named codes.
  C  timing flags handed between instances (phase1.md:9 "An internal signal only timing one step of other information
     ... is part of what it times, not its own decision"; phase1.md:32 exempts only the hand-off kinds and says "judge
     from the port names at either end"): an internal non-record one-bit signal set by an instance, whose only source
     is one instance output port and whose only targets are instance input ports (no statement of this unit reads it),
     where a port name at either end has a completion or acknowledge word as a "_"-separated token (done, ack: what
     only times a step) and no port name at either end has a hand-off kind word (wait, err, fault, we, addr, adr).
     Reasoning: this rests on phase1.md:9 alone. phase2.md:34 judges "a completion flag" as usual in two rules, but
     a rule's spares hold "only from that rule's bar" (phase2.md:34), so they do not cover phase1.md:9.
  D  per-region results (common.md:97 "a per-region result is then its operand, not a primary ... unless it itself
     picks where a request goes"; phase1.md:44): an internal signal V whose only target (gives value to or decides) is
     one other signal F, where F takes its value from itself on every line V is read, and each such RTL line has the
     priority-chain form "F(r) <= ... when ... else F(r+1)" (or r-1): the per-region results merge into one decision.
  E  violation-reset setting (phase1.md:24, phase2.md:34 "a setting choosing only whether such a violation resets
     never qualify ... if their only uses, apart from a read-back, are to request a reset and record its cause"): a
     register written only from fields of a unit input record port (a bus write) and read back into a field of a unit
     output record port, whose every other target T gives value only to non-record unit output ports (one or more)
     and decides only registers set to constants only that are read back into a field of a unit output record port
     (the cause record, one or more). Reasoning: the output port T drives together with the cause record T sets is the
     reset request and its cause, read from structure, not from a name.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FA = HERE.parents[1]                      # failure_analysis
LAB = FA.parents[2]                       # final/pio/lab
RAW = FA / "raw"
INPUTS = LAB / "inputs" / "v1" / "tuning"
RUNS = ("r0", "r1", "r2")
ONLY_TESTED = {"condition", "selector", "read"}
# phase1.md:32 hand-off kinds as port-name tokens: wait; fault (err, fault); write-enable (we); access address
# (addr, adr). Reasoning: the token mapping is ours; on this corpus only "wait" and "fault" decide anything.
HANDOFF_TOKENS = {"wait", "err", "fault", "we", "addr", "adr"}
# phase1.md:9 "only timing one step": a completion or acknowledge word in a port name at either end.
TIMING_TOKENS = {"done", "ack"}
# phase2.md:34 processor-context fields ("privilege mode, ... debug mode or takes a trap, ... a fetch or data access");
# "Judge what a field tells from port field names". The read/write kind is left out on purpose: its tokens (we, rw)
# also name the write enables the same rule judges as usual.
CONTEXT_TOKENS = {"trap", "priv", "debug", "dbg", "fetch"}
# phase2.md:34 read-back bar: "Judge from port names which instance outputs and inputs these are".
READBACK_IN = ("csr", "rdata")       # the OR result's destination input names both
READBACK_OUT = ("csr", "rdata")      # each operand's source output names at least one


def short(m):
    return m.split("_", 1)[1] if "_" in m else m


# ------------------------------------------------------------------------------------------------ inputs ---
class Unit:
    """Closed set + RTL of one module. elems[(entity, name)] = dict(kind, direction, record, roles, cp, lines)."""

    def __init__(self, m):
        d = json.loads((INPUTS / m / "closed_set.json").read_text(encoding="utf-8"))
        self.elems = {}
        self.top = d["entity list"][0]["entity name"] if d["entity list"] else ""
        for ent in d["entity list"]:
            en = ent["entity name"]
            for lst, kind in (("port list", "port"), ("signal list", "signal")):
                for e in ent.get(lst, []):
                    n = e.get("port") or e.get("signal")
                    rec = bool(e.get("record type")) or bool(e.get("fields"))
                    self.elems[(en, n)] = {"kind": kind, "direction": e.get("direction"), "record": rec,
                                           "roles": set(e.get("role in RTL", [])), "cp": e.get("counterparts", {}),
                                           "lines": e.get("occurrence lines", []), "type": e.get("type")}
                    for f in e.get("fields", []) or []:
                        self.elems[(en, f["field"])] = {"kind": kind + " field", "direction": e.get("direction"),
                                                        "record": False, "parent record": True,
                                                        "roles": set(f.get("role in RTL", [])),
                                                        "cp": f.get("counterparts", {}),
                                                        "lines": f.get("occurrence lines", []), "type": f.get("type")}
        self.rtl = {}
        for t in (INPUTS / m / "rtl.txt").read_text(encoding="utf-8").splitlines():
            mm = re.match(r"^\s*(\d+) \| (.*)$", t)
            if mm:
                self.rtl[int(mm.group(1))] = mm.group(2)
        self.consts = {mm.group(1).lower() for t in self.rtl.values()
                       for mm in [re.match(r"\s*constant\s+(\w+)\s*:", t)] if mm}

    def get(self, ent, name):
        return self.elems.get((ent, name))

    def cps(self, e, key):
        return e["cp"].get(key, []) or []

    def is_internal_plain(self, ent, name):
        e = self.get(ent, name)
        return e is not None and e["kind"] == "signal" and not e["record"]

    def is_out_record_field(self, ent, name):
        e = self.get(ent, name)
        return e is not None and e["kind"] == "port field" and e["direction"] == "out"

    def is_in_record_field(self, ent, name):
        e = self.get(ent, name)
        return e is not None and e["kind"] == "port field" and e["direction"] == "in"

    def decl_line(self, e, name):
        for ln in e["lines"]:
            t = self.rtl.get(ln, "")
            if re.search(rf"\bsignal\b[^:]*\b{re.escape(name)}\b[^:]*:", t):
                return t
        return ""


# ------------------------------------------------------------------------------------------------ tests ---
def test_a(u):
    """Read-back OR words: returns {(entity, name): 'A'}."""
    out = {}
    for (en, y), e in u.elems.items():
        if not u.is_internal_plain(en, y) or "set without a clock" not in e["roles"]:
            continue
        src, dst = u.cps(e, "gets value from"), u.cps(e, "gives value to")
        if len(src) < 2 or any("element" not in c for c in src) or u.cps(e, "decides"):
            continue
        if len(dst) != 1 or "instance" not in dst[0]:
            continue
        dport = (dst[0].get("port") or "").lower()
        if not all(k in dport for k in READBACK_IN):
            continue
        ws = [c["element"] for c in src]
        ok = True
        for w in ws:
            we = u.get(en, w)
            if not u.is_internal_plain(en, w) or u.cps(we, "decides"):
                ok = False
                break
            ws_src, ws_dst = u.cps(we, "gets value from"), u.cps(we, "gives value to")
            if len(ws_src) != 1 or "instance" not in ws_src[0]:
                ok = False
                break
            if not any(k in (ws_src[0].get("port") or "").lower() for k in READBACK_OUT):
                ok = False
                break
            if [c.get("element") for c in ws_dst] != [y]:
                ok = False
                break
        lines = {ln for c in src for ln in c.get("lines", [])}
        if ok and lines and all(re.search(r"\bor\b", u.rtl.get(ln, ""), re.I) for ln in lines):
            out[(en, y)] = "A"
            for w in ws:
                out[(en, w)] = "A"
    return out


def reads_as_code(u, name, lines):
    """The field is read as a multi-bit code: a slice or single bit of it is read, or it is compared with a constant
    this unit declares or a literal wider than one bit, or it is a case selector with declared-constant choices."""
    nm = re.escape(name)
    lit = re.compile(rf"{nm}(\s*\([^)]*\))?\s*(/=|=)\s*(\"[01]{{2,}}\"|x\"[0-9a-f]+\")", re.I)
    for ln in lines:
        t = u.rtl.get(ln, "")
        if re.search(rf"{nm}\s*\(", t) or lit.search(t):
            return True
    return compares_with_constant(u, name, lines)


def test_b1(u):
    out = {}
    for (en, n), e in u.elems.items():
        if e["kind"] == "port field" and e["direction"] == "in" and e["roles"] and e["roles"] <= ONLY_TESTED \
                and e["roles"] & {"condition", "selector"}:
            code = reads_as_code(u, n, e["lines"])
            context = bool(tokens(n.split(".")[-1]) & CONTEXT_TOKENS)
            if code or context:
                out[(en, n)] = "B1"
    return out


def compares_with_constant(u, name, lines):
    pat = re.compile(rf"\b{re.escape(name)}\b(\s*\([^)]*\))?\s*(/=|=)\s*(\w+)", re.I)
    for ln in lines:
        t = u.rtl.get(ln, "")
        for mm in pat.finditer(t):
            if mm.group(3).lower() in u.consts:
                return True
        if re.search(rf"\bcase\s+{re.escape(name)}\b", t, re.I):
            for k in sorted(x for x in u.rtl if x > ln):
                tk = u.rtl[k]
                if re.search(r"\bend\s+case\b", tk, re.I):
                    break
                mm = re.match(r"\s*when\s+(.*?)=>", tk, re.I)
                if mm and any(tok.lower() in u.consts for tok in re.findall(r"[A-Za-z]\w*", mm.group(1))):
                    return True
    return False


def test_b2(u):
    out = {}
    for (en, n), e in u.elems.items():
        if e["kind"] == "port" and e["direction"] == "in" and not e["record"] and e["roles"] \
                and e["roles"] <= ONLY_TESTED and e["roles"] & {"condition", "selector"} \
                and compares_with_constant(u, n, e["lines"]):
            out[(en, n)] = "B2"
    return out


def tokens(port):
    return {t.lower() for t in port.split("_") if t}


def test_c(u):
    out = {}
    for (en, n), e in u.elems.items():
        if not u.is_internal_plain(en, n) or "set by an instance" not in e["roles"]:
            continue
        src, dst = u.cps(e, "gets value from"), u.cps(e, "gives value to")
        if len(src) != 1 or "instance" not in src[0] or not dst or any("instance" not in c for c in dst):
            continue
        if u.cps(e, "decides") or u.cps(e, "decided by"):
            continue
        decl = u.decl_line(e, n)
        if not re.search(r":\s*std_u?logic\s*(;|:=)", decl, re.I):        # one bit
            continue
        ports = [src[0]["port"]] + [c["port"] for c in dst]
        if any(tokens(p) & HANDOFF_TOKENS for p in ports):
            continue
        if not any(tokens(p) & TIMING_TOKENS for p in ports):
            continue
        out[(en, n)] = "C"
    return out


def test_d(u):
    out = {}
    for (en, v), e in u.elems.items():
        if e["kind"] not in ("signal", "signal field"):
            continue
        tg = [c for k in ("gives value to", "decides") for c in u.cps(e, k)]
        names = {c.get("element") for c in tg}
        if len(names) != 1 or None in names or v in names:
            continue
        f = names.pop()
        fe = u.get(en, f)
        if fe is None:
            continue
        self_lines = {ln for c in u.cps(fe, "gets value from") if c.get("element") == f for ln in c.get("lines", [])}
        v_lines = {ln for c in tg for ln in c.get("lines", [])}
        base = re.escape(f.split(".")[-1])
        chain = re.compile(rf"\b{base}\s*\(\s*(\w+)\s*\)\s*<=.*\bwhen\b.*\belse\s+{base}\s*\(\s*\1\s*[+-]\s*1\s*\)", re.I)
        if self_lines and v_lines and v_lines <= self_lines and all(chain.search(u.rtl.get(ln, "")) for ln in v_lines):
            out[(en, v)] = "D"
    return out


def test_e(u):
    out = {}
    for (en, s), e in u.elems.items():
        if e["kind"] not in ("signal", "signal field") or "held on a clock edge" not in e["roles"]:
            continue
        src = u.cps(e, "gets value from")
        if not src or not all("element" in c and u.is_in_record_field(en, c["element"]) for c in src):
            continue
        tg = [c for k in ("gives value to", "decides") for c in u.cps(e, k)]
        readback = [c for c in tg if "element" in c and u.is_out_record_field(en, c["element"])]
        others = [c for c in tg if c not in readback and c.get("element") != s]
        if not readback or not others or any("element" not in c for c in others):
            continue
        ok = True
        for c in others:
            t = u.get(en, c["element"])
            if t is None or t["kind"] not in ("signal", "signal field"):
                ok = False
                break
            gv, de = u.cps(t, "gives value to"), u.cps(t, "decides")
            outs = [x for x in gv if "element" in x and (u.get(en, x["element"]) or {}).get("kind") == "port"
                    and (u.get(en, x["element"]) or {}).get("direction") == "out"
                    and not (u.get(en, x["element"]) or {}).get("record")]
            if not outs or len(outs) != len(gv):
                ok = False
                break
            causes = []
            for x in de:
                ce = u.get(en, x.get("element", ""))
                if ce is None or "set to constants only" not in ce["roles"] or "held on a clock edge" not in ce["roles"]:
                    ok = False
                    break
                if not any("element" in y and u.is_out_record_field(en, y["element"]) for y in u.cps(ce, "gives value to")):
                    ok = False
                    break
                causes.append(x["element"])
            if not ok or not causes:
                ok = False
                break
        if ok:
            out[(en, s)] = "E"
    return out


TESTS = (test_a, test_b1, test_b2, test_c, test_d, test_e)


def flagged(u):
    out = {}
    for t in TESTS:
        for k, v in t(u).items():
            out.setdefault(k, v)
    return out


# ------------------------------------------------------------------------------------------------ replies ---
def listed_primaries(run, m):
    """Distinct (entity, element) of Phase 2 primary rows, "Same Role" names included (the scorer's listing)."""
    d = json.loads((RAW / run / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
    out = []
    for w in d.get("Concept Walks", []):
        for a in w.get("Assets", []):
            if a.get("Label") != "primary":
                continue
            for n in [a.get("Asset RTL")] + list(a.get("Same Role") or []):
                k = (a.get("Entity"), n)
                if isinstance(n, str) and n and k not in out:
                    out.append(k)
    return out


def modules():
    return sorted(p.stem for p in (RAW / "r0" / "phase2").glob("*.json"))


# ------------------------------------------------------------------------------------------------ self-test ---
def selftest():
    """Hand-read lines (RTL numbers), each with an operator fragment that the line must contain.
    Each case names the element by where it occurs, not by name: the unique element of the given kind whose
    occurrence lines include the line and, for 'assigned', whose own source counterparts cite that line."""
    units = {short(m): Unit(m) for m in modules()}

    def at(mod, line, kind, assigned=False, frag=None, after=None):
        """after: a regex the element's name must be followed by on that line (picks one of several on a line)."""
        u = units[mod]
        if frag is not None:
            assert frag in u.rtl.get(line, ""), f"{mod} RTL {line} lacks {frag!r}: {u.rtl.get(line)!r}"
        hits = [(k, e) for k, e in u.elems.items() if e["kind"] == kind and line in e["lines"]
                and (not assigned or any(line in c.get("lines", []) for c in u.cps(e, "gets value from")))
                and (after is None or re.search(re.escape(k[1]) + after, u.rtl.get(line, "")))]
        assert len(hits) == 1, f"{mod} RTL {line} {kind}: {len(hits)} elements"
        return hits[0][0]

    cases = [
        # A: RTL 279 is the OR of the four instance read words (hand-read: three ' or ' operators); its result is barred.
        ("cpu", 279, "signal", True, " or ", "A", True),
        # A: RTL 371 wires an instance's read-back word output to a unit signal that only feeds that OR.
        ("cpu", 371, "signal", True, "=>", "A", True),
        # A twin, kept: RTL 330 writes the register write-back value; one operand is a record field.
        ("cpu", 330, "signal", True, " or ", "A", False),
        # A twin, kept: RTL 263, the read-back output merged into the write-back value (the rule's own primary).
        ("cpu", 263, "signal", True, "=>", "A", False),
        # B1 (context): RTL 131 tests the processor's trap field ('= '1'') to leave the busy state: only tested,
        # and the field name says it tells whether the processor takes a trap.
        ("cpu_cp_muldiv", 131, "port field", False, "= '1'", "B1", True),
        # B1 (code): RTL 98 compares a slice of an instruction field with a seven-bit literal.
        ("cpu_cp_muldiv", 98, "port field", False, "downto", "B1", True),
        # B1 twin, kept: RTL 97, the coprocessor trigger field tested against the literal bit '1' (a start command,
        # judged as usual by the operation-selector rule); picked as the field followed by "= '1'" on that line.
        ("cpu_cp_muldiv", 97, "port field", False, "= '1'", "B1", False, r"\s*=\s*'1'"),
        # B1 twin, kept: RTL 113, a register write enable field of a control record tested against '1'.
        ("cpu_pmp", 113, "port field", False, "= '1'", "B1", False, r"\s*=\s*'1'"),
        # B1 twin, kept: RTL 275, a response acknowledge field tested against '1'.
        ("debug_dtm", 275, "port field", False, "= '1'", "B1", False),
        # B1/B2 twin, kept: RTL 154 decodes the multiply start (an internal record field, not a port field).
        ("cpu_cp_muldiv", 154, "signal field", False, "when", "B1", False),
        # B2: RTL 245 compares a one-bit input port with a declared constant (instruction type).
        ("cpu_cp_cfu", 245, "port", False, "= ", "B2", True),
        # B2 twin, kept: RTL 178 tests the register write enable against a literal bit.
        ("cpu_cp_cfu", 178, "port", False, "= '1'", "B2", False),
        # C: RTL 373 wires an instance's done output to a one-bit unit wire read only by another instance.
        ("cpu", 373, "signal", True, "=>", "C", True),
        # C twin, kept: RTL 390, the same shape for a wait output (a hand-off kind).
        ("cpu", 390, "signal", True, "=>", "C", False),
        # D: RTL 305 sets the per-region match result that only the priority chain at RTL 354 reads.
        ("cpu_pmp", 305, "signal", True, " and ", "D", True),
        # D twin, kept: RTL 354 is the priority chain itself (the merge point, which also drives the fault output).
        ("cpu_pmp", 354, "signal", True, "(r+1)", "D", False),
        # E: RTL 96 stores the strict-mode bit from bus write data; RTL 156 ANDs it into the access-violation reset.
        ("wdt", 96, "signal field", True, "<=", "E", True),
        # E twin, kept: RTL 97 stores the timeout limit, compared with the count at RTL 144.
        ("wdt", 97, "signal field", True, "<=", "E", False),
        # E twin, kept: RTL 94 stores the enable, which has many uses.
        ("wdt", 94, "signal field", True, "<=", "E", False),
    ]
    fails = []
    for case in cases:
        mod, line, kind, assigned, frag, test, want = case[:7]
        after = case[7] if len(case) > 7 else None
        try:
            k = at(mod, line, kind, assigned, frag, after)
        except AssertionError as ex:
            fails.append(str(ex))
            continue
        got = flagged(units[mod]).get(k)
        if (got == test) != want:
            fails.append(f"{mod} RTL {line}: test {test} expected {want}, got {got}")
    return not fails, fails


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ok, fails = selftest()
    print(json.dumps({"self-test": "PASS" if ok else "FAIL", "failures": fails}))
    if not ok:
        sys.exit(2)
    out = {r: {} for r in RUNS}
    for m in modules():
        u = Unit(m)
        fl = flagged(u)
        for r in RUNS:
            drops = [{"element": n, "entity": en, "action": "drop", "test": fl[(en, n)]}
                     for en, n in listed_primaries(r, m) if (en, n) in fl]
            if drops:
                out[r][short(m)] = drops
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1), encoding="utf-8")
    for r in RUNS:
        print(r, sum(len(v) for v in out[r].values()), {k: [d["element"] for d in v] for k, v in out[r].items()})


if __name__ == "__main__":
    main()
