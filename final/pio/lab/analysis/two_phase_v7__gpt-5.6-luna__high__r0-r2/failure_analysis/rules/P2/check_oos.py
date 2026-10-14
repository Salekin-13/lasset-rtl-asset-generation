"""Fix P2, code check (applied after the model). Drops a listed primary when it meets the testable condition of one of
five v7 bars the model did not follow. Every test reads only closed-set facts (port direction and record type, role
in RTL, counterparts with their lines) and the RTL text (declarations, the test enclosing an assignment, the operators
of a right-hand side). No element name and no field name is tested: where two names are compared, only their equality
is used (the same field of one record type on an input and an output port).

  T1  bus handshake copy (phase2.md:34 sentence "In a unit passing bus requests from an input bus request port to an
      output one, a register of one bit, or one bit per requester ..."; phase1.md:29). The strobe, lock bit and
      response error bit are found by a structural stand-in: a field of an input record port that the unit also passes
      on, through wires only, to the same field of an output port of that record type (a value the access already
      carries). The reader clause ("reads it only to start, pass on, route, time or end that access") is tested as:
      nothing takes its value (only its own next-value signal), and neither it nor an element it decides drives an
      output port that has no record type.
  T2  re-timed response bit (phase2.md:34 sentence "A one-bit register that one unconditional statement sets on every
      clock edge to a stored state bit or flag of this unit ..."; phase1.md:29).
  T3  started flag (phase2.md:34 sentence "A register only recording that a count has started, read only to let that
      count advance or to qualify a compare on it, is not primary"; phase1.md:9). The spare "a flag a request or
      command sets until served" is kept out: no field of an input record port reaches it, directly or through wires.
  T4  sequencing state outside a coprocessor (phase2.md:34 sentence "Outside a coprocessor, ... a state machine's state
      register (not ... the current grant ...) ... never qualify"; phase1.md:36). The code's proxies, not prompt text:
      the unit passes bus transactions on (an input and an output port of each of two record types) and has a single
      requester (no input record type with two ports). This reads "(a coprocessor, an atomic read-modify-write)"
      (phase1.md:42, phase2.md:34) as two different kinds of unit, so "outside a coprocessor" takes in the second.
  T5  merged bus responses (common.md:98 "a multiplexer path, or a word mixing it with other values ... not a primary";
      phase2.md:34 "Any other element that 2.6 says is not primary never qualifies either"; phase1.md:27 "merging
      several ports' bus responses into one (an OR or a multiplexer)").

Reads ONLY the stored v7 replies (raw/r<k>/phase2/<module>.json) and the inputs (inputs/v1/tuning/<module>/{rtl.txt,
closed_set.json}). It opens no reference, scoring or verdict file.

  python check.py <out.json>   -> writes {"r0": {"<short>": [{"element", "entity", "action": "drop"}]}, "r1": ..., "r2": ...}
A self-test on hand-read RTL lines runs first; if it fails, nothing is written and the exit code is 2.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FA = HERE.parents[1]                       # the failure analysis folder
RAW = __import__("pathlib").Path(__import__("os").environ["RAW_DIR"])
LAB = FA.parents[2]                        # .../lab
INPUTS = LAB / "inputs" / "v1" / "tuning"
RUNS = ("r0", "r1", "r2")

ONE_BIT_TYPES = re.compile(r"^(std_u?logic|bit)$", re.I)
CONST_RHS = re.compile(r"^\s*(?:'([01])'|\"([01]+)\"|\(\s*others\s*=>\s*'([01])'\s*\))\s*;?\s*$", re.I)
NAME = re.compile(r"[A-Za-z]\w*(?:\.[A-Za-z]\w*)*")


def short(stem):
    return stem.split("_", 1)[1] if "_" in stem else stem


# ------------------------------------------------------------------------------------------------- inputs ---
class Module:
    def __init__(self, stem):
        self.stem = stem
        self.ents = {}
        cs = json.loads((INPUTS / stem / "closed_set.json").read_text(encoding="utf-8"))
        for e in cs["entity list"]:
            el = {}
            for p in e["port list"]:
                el[p["port"]] = dict(p, kind="port", dir=p.get("direction"), rec=p.get("record type"))
                for f in p.get("fields") or []:
                    el[f["field"]] = dict(f, kind="port field", dir=p.get("direction"), rec=p.get("record type"), port=p["port"])
            for s in e["signal list"]:
                el[s["signal"]] = dict(s, kind="signal", rec=s.get("record type"))
                for f in s.get("fields") or []:
                    el[f["field"]] = dict(f, kind="signal field", base=s["signal"])
            self.ents[e["entity name"]] = el
        self.rtl = {}
        for l in (INPUTS / stem / "rtl.txt").read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*(\d+) \|(.*)$", l)
            if m:
                self.rtl[int(m.group(1))] = m.group(2).rstrip()
        self.nums = sorted(self.rtl)
        self.region, cur = {}, None
        for n in self.nums:
            m = re.match(r"\s*entity\s+(\w+)\s+is\b", self.rtl[n], re.I)
            if m:
                cur = m.group(1)
            self.region[n] = cur
        self._decls()

    def lines_of(self, ent):
        return [n for n in self.nums if self.region[n] == ent]

    def _decls(self):
        self.decl, self.recs, self.enums, self.generics = {}, {}, {}, {}
        for ent in set(self.region.values()):
            decl, recs, enums, gens = {}, {}, set(), set()
            rec, in_gen = None, False
            for n in self.lines_of(ent):
                t = re.sub(r"--.*$", "", self.rtl[n])
                s = t.strip()
                if re.match(r"generic\s*\(", s, re.I):
                    in_gen = True
                if in_gen:
                    gens |= set(re.findall(r"(?:^|;|\()\s*(\w+)\s*:", s))
                    if re.match(r"port\s*\(", s, re.I) or re.match(r"\)\s*;", s):
                        in_gen = False
                m = re.match(r"type\s+(\w+)\s+is\s+record\b", s, re.I)
                if m:
                    rec = m.group(1)
                    recs[rec] = {}
                    continue
                if rec:
                    if re.match(r"end\s+record", s, re.I):
                        rec = None
                        continue
                    m = re.match(r"(\w+)\s*:\s*(.+?);?$", s)
                    if m:
                        recs[rec][m.group(1)] = m.group(2).strip()
                    continue
                m = re.match(r"type\s+(\w+)\s+is\s*\(", s, re.I)
                if m:
                    enums.add(m.group(1))
                m = re.match(r"signal\s+([\w\s,]+?)\s*:\s*(.+?)\s*(?::=.*)?;", s, re.I)
                if m:
                    for nm in m.group(1).split(","):
                        decl[nm.strip()] = m.group(2).strip()
            self.decl[ent], self.recs[ent], self.enums[ent], self.generics[ent] = decl, recs, enums, gens

    def width(self, ent, name):
        """1, an int, 'enum', or None (unknown or not a literal width)."""
        parts = name.split(".")
        t = self.decl[ent].get(parts[0])
        for f in parts[1:]:
            if t is None or t not in self.recs[ent]:
                return None
            t = self.recs[ent][t].get(f)
        if t is None:
            return None
        if ONE_BIT_TYPES.match(t):
            return 1
        if t in self.enums[ent]:
            return "enum"
        m = re.match(r"\w*vector\s*\(\s*(\d+)\s+downto\s+(\d+)\s*\)$", t, re.I)
        if m:
            return int(m.group(1)) - int(m.group(2)) + 1
        return None

    def assignments(self, ent, name):
        """[(rtl line, right-hand side)] for statements assigning the name (or one of its bits)."""
        rx = re.compile(r"^\s*" + re.escape(name) + r"\s*(?:\(\s*\d+\s*\))?\s*<=\s*(.*)$")
        out = []
        for n in self.lines_of(ent):
            m = rx.match(self.rtl[n])
            if m:
                out.append((n, m.group(1)))
        return out

    def condition_text(self, n):
        """The test starting at line n (an if or elsif), continued until 'then'."""
        i = self.nums.index(n)
        parts = []
        for k in self.nums[i:]:
            parts.append(re.sub(r"--.*$", "", self.rtl[k]))
            if re.search(r"\bthen\b", self.rtl[k], re.I):
                break
        return " ".join(parts), (n, k)

    def enclosing_test(self, n):
        """(condition text, (first, last) line) of the innermost if/elsif enclosing line n, or None when the statement
        is unconditional inside its clocked branch, process or state-machine case branch (enclosing state conditions
        are allowed by the rule). An else branch counts as the tests of its if chain."""
        ind = len(self.rtl[n]) - len(self.rtl[n].lstrip())
        i = self.nums.index(n)
        for k in reversed(self.nums[:i]):
            t = self.rtl[k]
            if not t.strip():
                continue
            ik = len(t) - len(t.lstrip())
            if ik >= ind:
                continue
            s = t.strip().lower()
            if "rising_edge" in s or "falling_edge" in s or s.startswith(("when ", "case ", "begin", "process")) or " process" in s:
                return None
            if s.startswith(("if ", "if(", "elsif ", "elsif(")):
                return self.condition_text(k)
            if s.startswith("else"):
                texts, j = [], self.nums.index(k)
                for q in reversed(self.nums[:j]):
                    tq = self.rtl[q]
                    if len(tq) - len(tq.lstrip()) == ik and tq.strip().lower().startswith(("if", "elsif")):
                        texts.append(self.condition_text(q)[0])
                        if tq.strip().lower().startswith("if"):
                            return " ".join(texts), (q, k)
                return None
            ind = ik
        return None


def names(x, key):
    """Element names of one counterpart kind (instance ports are left out)."""
    return {c["element"] for c in (x.get("counterparts") or {}).get(key, []) if "element" in c}


def lines(x, key):
    return sorted({ln for c in (x.get("counterparts") or {}).get(key, []) for ln in c.get("lines", [])})


def tokens(text):
    text = re.sub(r"'[^']'|\"[^\"]*\"", " ", text)
    text = re.sub(r"'\w+", " ", text)          # attributes ('left, 'high)
    return set(NAME.findall(text))


class Entity:
    def __init__(self, M, ent):
        self.M, self.ent, self.el = M, ent, M.ents[ent]
        ports = [x for x in self.el.values() if x["kind"] == "port"]
        self.rec_in, self.rec_out = {}, {}
        for p in ports:
            if p.get("rec"):
                d = self.rec_in if p["dir"] == "in" else self.rec_out
                d[p["rec"]] = d.get(p["rec"], 0) + 1
        # a unit passing bus transactions on: two record types, each with an input port and an output port
        self.passing = sum(1 for r in self.rec_in if r in self.rec_out) >= 2

    def x(self, n):
        return self.el.get(n)

    def is_reg(self, n):
        x = self.x(n)
        return bool(x) and x["kind"] in ("signal", "signal field") and x.get("type") == "reg" and \
            "held on a clock edge" in (x.get("role in RTL") or [])

    def is_in_port_part(self, n):
        x = self.x(n)
        return bool(x) and x["kind"] in ("port", "port field") and x["dir"] == "in"

    def is_out_port_part(self, n):
        x = self.x(n)
        return bool(x) and x["kind"] in ("port", "port field") and x["dir"] == "out"

    def nxt_wires(self, n):
        """Wires that give value to nothing but n and from which n gets its value (its next-value signal)."""
        x = self.x(n)
        return {w for w in names(x, "gets value from") if self.x(w) and self.x(w).get("type") == "wire"
                and self.x(w)["kind"] in ("signal", "signal field") and names(self.x(w), "gives value to") == {n}}

    def is_counter(self, n):
        """A count: a register wider than one bit (or of no literal width) that an assignment, to it or to its
        next-value signal, sets to its own value plus or minus something."""
        if not self.is_reg(n) or self.M.width(self.ent, n) in (1, "enum"):
            return False
        for g in {n} | self.nxt_wires(n):
            for _ln, rhs in self.M.assignments(self.ent, g):
                if re.search(r"[+-]", rhs) and n in tokens(rhs):
                    return True
        return False

    def grant_selects(self):
        """Elements deciding an output-port field that takes its value from several input ports (a select between
        requesters)."""
        out = set()
        for g, x in self.el.items():
            if x["kind"] not in ("signal", "signal field"):
                continue
            for f in names(x, "decides"):
                fx = self.x(f)
                if fx and fx["kind"] == "port field" and fx["dir"] == "out":
                    srcp = {self.x(s)["port"] for s in names(fx, "gets value from")
                            if self.x(s) and self.x(s)["kind"] == "port field" and self.x(s)["dir"] == "in"}
                    if len(srcp) >= 2:
                        out.add(g)
        return out

    def is_internal_wire(self, n):
        x = self.x(n)
        return bool(x) and x["kind"] in ("signal", "signal field") and x.get("type") == "wire"

    def passed_on(self, s):
        """True when s is a field of an input record port of a record type the unit also has an output port of, and
        s reaches, through wires only (no register), the same field of an output port of that record type, or that
        output port whole: a value the access already carries and the unit passes on."""
        sx = self.x(s)
        if not (sx and sx["kind"] == "port field" and sx["dir"] == "in" and sx.get("rec") in self.rec_out):
            return False
        part = s[len(sx["port"]) + 1:]
        seen, todo = set(), [s]
        while todo:
            c = todo.pop()
            for t in names(self.x(c), "gives value to"):
                if t in seen:
                    continue
                seen.add(t)
                tx = self.x(t)
                if not tx:
                    continue
                if tx["kind"] == "port field" and tx["dir"] == "out" and tx.get("rec") == sx["rec"] \
                        and t[len(tx["port"]) + 1:] == part:
                    return True
                if tx["kind"] == "port" and tx["dir"] == "out" and tx.get("rec") == sx["rec"]:
                    return True
                if self.is_internal_wire(t):
                    todo.append(t)
        return False

    def reached_by_input_record_field(self, n):
        """True when a field (or whole) of an input record port gives value to or decides n, directly or through
        wires only."""
        seen, todo = set(), [n]
        while todo:
            c = todo.pop()
            for s in names(self.x(c), "gets value from") | names(self.x(c), "decided by"):
                if s in seen or s == n:
                    continue
                seen.add(s)
                sx = self.x(s)
                if not sx:
                    continue
                if sx["kind"] in ("port", "port field") and sx["dir"] == "in" and sx.get("rec"):
                    return True
                if self.is_internal_wire(s):
                    todo.append(s)
        return False

    def drives_plain_output(self, n):
        """True when n gives value to or decides an output port that has no record type."""
        for t in names(self.x(n), "gives value to") | names(self.x(n), "decides"):
            tx = self.x(t)
            if tx and tx["kind"] == "port" and tx["dir"] == "out" and not tx.get("rec"):
                return True
        return False

    def test_reads_only_access(self, cond):
        """True when every closed-set element a test reads is an input port or input port field; generics, constants,
        literals and function names are allowed (they are no closed-set element)."""
        for t in tokens(cond):
            if t in self.M.generics[self.ent]:
                continue
            if self.x(t) is None and t.split(".")[0] not in self.M.decl[self.ent]:
                continue
            if not self.is_in_port_part(t):
                return False
        return True


# ------------------------------------------------------------------------------------------------- tests ---
def T1(E, n):
    """Bus handshake copy (phase2.md:34)."""
    M = E.M
    if not E.passing or not E.is_reg(n):
        return False
    w = M.width(E.ent, n)
    per_requester = {k for r, k in E.rec_in.items() if k >= 2}
    if not (w == 1 or (isinstance(w, int) and w in per_requester)):
        return False
    W = E.nxt_wires(n)
    group = {n} | W
    src = set()
    for g in group:
        src |= names(E.x(g), "gets value from")
    src -= group
    if src:
        # every value it takes is a field the access carries and the unit passes on (stand-in for the strobe, lock
        # bit and response error bit), and every non-constant assignment only copies, ORs or places side by side
        # (one bit per requester) such fields and its own value: no function, slice, AND or other operator
        for s in src:
            if not E.passed_on(s):
                return False
        for g in group:
            for _ln, rhs in M.assignments(E.ent, g):
                if CONST_RHS.match(rhs):
                    continue
                rest = rhs
                for t in sorted(group | src, key=len, reverse=True):
                    rest = re.sub(r"(?<![\w.])" + re.escape(t) + r"(?![\w.(])", " ", rest)
                if re.sub(r"\bor\b|[()&;\s]", "", rest, flags=re.I):
                    return False
    else:
        # a route bit: set (to a non-zero constant) only under a test reading only the access's fields and build-time values
        sets = []
        for g in group:
            for ln, rhs in M.assignments(E.ent, g):
                c = CONST_RHS.match(rhs)
                if not c:
                    return False
                if set("".join(v for v in c.groups() if v)) != {"0"}:
                    sets.append(ln)
        if not sets:
            return False
        for ln in sets:
            t = M.enclosing_test(ln)
            if t is None or not E.test_reads_only_access(t[0]):
                return False
    # no test choosing between requesters reads it
    dec = set()
    for g in group:
        dec |= names(E.x(g), "decides")
    if dec & E.grant_selects():
        return False
    # judged as usual: a timeout count's error and suppression flag -> no test reading it also reads a count
    for g in group:
        for ln in lines(E.x(g), "decides"):
            text = M.condition_text(ln)[0] if re.match(r"\s*(if|elsif)\b", M.rtl[ln], re.I) else M.rtl[ln]
            if any(E.is_counter(t) for t in tokens(text) if E.x(t)):
                return False
    # read only to start, pass on, route, time or end that access: nothing takes its value but its own next-value
    # signal (no read-back word, no copy kept elsewhere), and neither it nor an element it decides drives an output
    # port that has no record type (an interrupt or status line)
    for g in group:
        if names(E.x(g), "gives value to") - group:
            return False
        if E.drives_plain_output(g):
            return False
        for d in names(E.x(g), "decides") - group:
            if E.x(d) and (E.x(d)["kind"] == "port" and E.x(d)["dir"] == "out" and not E.x(d).get("rec")
                           or E.drives_plain_output(d)):
                return False
    return True


def T2(E, n):
    """Re-timed response bit (phase2.md:34)."""
    M = E.M
    if not E.is_reg(n) or M.width(E.ent, n) != 1:
        return False
    x = E.x(n)
    asg = [(ln, rhs) for ln, rhs in M.assignments(E.ent, n) if not CONST_RHS.match(rhs)]
    if len(asg) != 1 or names(x, "decided by"):
        return False
    rhs = asg[0][1].lower()
    if re.search(r"\b(or|xor|nand|nor|when|else)\b|[+\-*&]", rhs):
        return False
    src = names(x, "gets value from") - {n}
    stored = {s for s in src if E.is_reg(s)}
    if not stored:
        return False
    for s in src - stored:
        if E.is_in_port_part(s):
            continue
        sx = E.x(s)
        if not (sx and sx.get("type") == "wire" and
                all(E.is_in_port_part(q) for q in names(sx, "gets value from") | names(sx, "decided by"))):
            return False
    gives = names(x, "gives value to")
    return bool(gives) and all(E.is_out_port_part(g) and E.x(g)["kind"] == "port field" for g in gives) \
        and not names(x, "decides")


def T3(E, n):
    """Started flag (phase2.md:34)."""
    M = E.M
    if not E.is_reg(n) or M.width(E.ent, n) != 1:
        return False
    x = E.x(n)
    if n not in names(x, "gets value from"):
        return False
    # spared: a flag a request or command sets until served -> no input record field reaches it
    if E.reached_by_input_record_field(n):
        return False
    readers = (names(x, "gives value to") | names(x, "decides")) - {n}
    if not readers:
        return False
    counters = {c for c in E.el if E.is_counter(c)}
    if not counters:
        return False
    for r in readers:
        if r in counters:
            continue
        rx = E.x(r)
        if rx is None:
            return False
        if (names(rx, "gives value to") | names(rx, "decides")) and \
                (names(rx, "gives value to") | names(rx, "decides")) <= counters:
            continue                                     # an increment pulse of the count
        if names(rx, "decided by") & counters or names(rx, "gets value from") & counters:
            continue                                     # a compare on the count
        return False
    return True


def T4(E, n):
    """Sequencing state of a unit passing bus transactions on, with one requester (no grant)."""
    M = E.M
    if not E.passing or any(k >= 2 for k in E.rec_in.values()):
        return False
    if not E.is_reg(n) or M.width(E.ent, n) != "enum":
        return False
    x = E.x(n)
    readers = (names(x, "gives value to") | names(x, "decides")) - {n}
    for r in readers:
        if E.is_out_port_part(r):
            continue
        rx = E.x(r)
        if rx and rx.get("type") == "wire" and rx["kind"] in ("signal", "signal field"):
            tgt = names(rx, "gives value to")
            if len(tgt) == 1 and E.is_reg(next(iter(tgt))) and r in names(E.x(next(iter(tgt))), "gets value from"):
                continue                                 # the next-value signal of a register (a load or a step)
        return False
    return bool(readers)


def T5(E, n):
    """Merged bus responses: an internal record signal of a port's record type (or its field) whose value comes only
    from several input ports of that type, directly or through per-port copies."""
    x = E.x(n)
    if x is None:
        return False
    base = x.get("base", n) if x["kind"] == "signal field" else n
    bx = E.x(base)
    if not bx or bx["kind"] != "signal" or not bx.get("rec"):
        return False
    rt = bx["rec"]
    if rt not in E.rec_in and rt not in E.rec_out:
        return False
    origin = set()
    srcs = names(bx, "gets value from")
    if not srcs:
        return False
    for s in srcs:
        sx = E.x(s)
        if sx and sx["kind"] == "port" and sx["dir"] == "in" and sx.get("rec") == rt:
            origin.add(s)
            continue
        if sx and sx["kind"] == "signal" and not sx.get("rec"):
            ps = names(sx, "gets value from")
            if ps and all(E.x(p) and E.x(p)["kind"] == "port" and E.x(p)["dir"] == "in" and E.x(p).get("rec") == rt
                          for p in ps):
                origin |= ps
                continue
        return False
    return len(origin) >= 2


TESTS = (("T1", T1), ("T2", T2), ("T3", T3), ("T4", T4), ("T5", T5))


def verdict(E, n):
    return [k for k, f in TESTS if f(E, n)]


# ------------------------------------------------------------------------------------------------- replies ---
def primaries(path):
    raw = path.read_text(encoding="utf-8")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        d = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    out = []
    for w in d.get("Concept Walks") or []:
        for a in (w.get("Assets") or []) if isinstance(w, dict) else []:
            if not isinstance(a, dict) or a.get("Label") != "primary":
                continue
            sr = a.get("Same Role") or []
            sr = [sr] if isinstance(sr, str) else sr
            for nm in [a.get("Asset RTL")] + list(sr):
                if isinstance(nm, str) and nm and (nm, a.get("Entity")) not in out:
                    out.append((nm, a.get("Entity")))
    return out


# ------------------------------------------------------------------------------------------------- self-test ---
def lhs(M, n):
    m = re.match(r"\s*([\w.]+)\s*(?:\(\s*\d+\s*\))?\s*<=", M.rtl[n])
    return m.group(1)


# (module short name, RTL line, test, expected); the element is the target of the assignment on that line, read by hand
CASES = [
    ("bus", 409, "T1", True),    # one-bit busy register copied from the request strobe, cleared at the answer
    ("bus", 410, "T1", True),    # one-bit register copied from the request lock bit
    ("bus", 51, "T1", True),     # one bit per requester, copied from the requesters' lock bits through its next value
    ("bus", 52, "T1", False),    # request register read by the test choosing between requesters
    ("bus", 412, "T1", False),   # error flag set to '1' under a test reading a count (judged as usual)
    ("bus", 413, "T1", False),   # copied from an internal address-decode wire, not a field the access carries
    ("cache", 120, "T1", True),  # ORs in the response error bit, which the unit also passes on to its host response
    ("cache", 121, "T1", True),  # route bit set under a test of the request's fields and a generic
    ("cache", 119, "T1", False), # ORs in a request field the unit consumes and does not pass on (a pending fence)
    ("cache", 118, "T1", False), # ORs in the request strobe, which this unit regenerates instead of passing on
    ("bus", 955, "T2", True),    # re-timed into the response: stored state bit ANDed with strobe, rw and a decode
    ("bus", 955, "T1", False),
    ("imem", 176, "T2", False),  # read enable from strobe and rw only: no stored state bit
    ("bus", 412, "T2", False),   # set to constants only
    ("wdt", 126, "T3", True),    # started flag: reads itself, read only by the increment pulse and the compare
    ("wdt", 125, "T3", False),   # the increment pulse: does not read itself
    ("wdt", 127, "T3", False),   # the count itself
    ("bus", 409, "T3", False),   # busy flag: set from the request strobe (a flag a request sets until served)
    ("bus", 758, "T4", True),    # enumerated state of a one-requester read-modify-write unit
    ("bus", 49, "T4", False),    # enumerated state of a two-requester switch: the grant
    ("bus", 395, "T5", True),    # OR of the per-port response copies
    ("bus", 690, "T5", True),
]


def selftest():
    mods = {s: Module(s) for s in (p.stem for p in sorted((RAW / "r0" / "phase2").glob("*.json")))}
    by_short = {short(s): M for s, M in mods.items()}
    fails = []
    # parser facts read by hand
    b, c, w = by_short["bus"], by_short["cache"], by_short["wdt"]
    for nm in [x.strip() for x in re.match(r"\s*signal\s+([\w\s,]+):", b.rtl[40]).group(1).split(",")]:
        if b.width(b.region[40], nm) != 2:
            fails.append(f"width at bus RTL 40: {nm} -> {b.width(b.region[40], nm)} (expected 2)")
    t = c.enclosing_test(173)
    if not t or t[1] != (171, 172):
        fails.append(f"enclosing test of cache RTL 173: {t} (expected lines 171-172)")
    if w.enclosing_test(130) is not None:
        fails.append("enclosing test of wdt RTL 130: expected none (unconditional inside the clocked branch)")
    if b.enclosing_test(424) is None or b.enclosing_test(424)[1][0] != 423:
        fails.append(f"enclosing test of bus RTL 424: {b.enclosing_test(424)} (expected from 423)")
    # T1 stand-in, read by hand: the input field on the right of each line is passed on (True) or not (False)
    def rhs_in_fields(M, ln):
        E = Entity(M, M.region[ln])
        rhs = M.rtl[ln].split("<=", 1)[1]
        return E, [t for t in tokens(rhs) if E.is_in_port_part(t) and E.x(t)["kind"] == "port field"]
    for sh, ln, exp in (("cache", 242, True),    # response error bit, also driven on the host response's same field
                        ("cache", 138, False),   # request field that only sets a pending register (output field tied)
                        ("cache", 137, False),   # request strobe; the output strobe is set to constants
                        ("bus", 419, True),      # request strobe, passed on through the per-port request wire
                        ("bus", 111, True)):     # both requesters' lock bits, driven on the output request
        E, fs = rhs_in_fields(by_short[sh], ln)
        if not fs or any(E.passed_on(f) != exp for f in fs):
            fails.append(f"passed_on at {sh} RTL {ln}: {[(f, E.passed_on(f)) for f in fs]} (expected {exp})")
    # T3 source clause, read by hand
    for sh, ln, exp in (("wdt", 130, False),     # started flag: enable setting register, a tick from a plain port, itself
                        ("bus", 419, True)):     # busy flag: copied from the request strobe
        M = by_short[sh]
        E = Entity(M, M.region[ln])
        if E.reached_by_input_record_field(lhs(M, ln)) != exp:
            fails.append(f"reached_by_input_record_field at {sh} RTL {ln}: expected {exp}")
    # planted: the reader clause must turn T1 off for a copy also read back as data or driving a plain output port
    M = b
    E = Entity(M, M.region[410])
    n = lhs(M, 410)
    plain_out = next((p for p, x in E.el.items() if x["kind"] == "port" and x["dir"] == "out" and not x.get("rec")),
                     None)
    for key in ("gives value to", "decides"):
        E2 = Entity(M, M.region[410])
        E2.el = json.loads(json.dumps(E.el))
        target = plain_out or next(p for p, x in E.el.items() if x["kind"] == "port field" and x["dir"] == "out")
        if plain_out is None:
            E2.el[target]["rec"] = None
            E2.el[target]["kind"] = "port"
        E2.el[n].setdefault("counterparts", {}).setdefault(key, []).append({"element": target, "lines": [426]})
        if T1(E2, n):
            fails.append(f"planted reader case ({key} a plain output port) did not turn T1 off at bus RTL 410")
    if not T1(E, n):
        fails.append("unplanted bus RTL 410 must stay T1 true")
    for sh, ln, tst, exp in CASES:
        M = by_short[sh]
        E = Entity(M, M.region[ln])
        n = lhs(M, ln)
        got = dict(TESTS)[tst](E, n)
        if got != exp:
            fails.append(f"{sh} RTL {ln} ({n}) {tst}: got {got}, expected {exp}")
    return not fails, fails, mods


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ok, fails, mods = selftest()
    print(json.dumps({"self-test": "PASS" if ok else "FAIL", "failures": fails}))
    if not ok:
        sys.exit(2)
    out, log = {}, []
    for r in RUNS:
        out[r] = {}
        for stem, M in mods.items():
            drops = []
            for nm, ent in primaries(RAW / r / "phase2" / f"{stem}.json"):
                if ent not in M.ents or nm not in M.ents[ent]:
                    continue
                v = verdict(Entity(M, ent), nm)
                if v:
                    drops.append({"element": nm, "entity": ent, "action": "drop"})
                    log.append((r, short(stem), nm, ent, v))
            if drops:
                out[r][short(stem)] = drops
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1), encoding="utf-8")
    for row in log:
        print(*row)
    print({r: sum(len(v) for v in out[r].values()) for r in RUNS})
    # the scan: every closed-set element any test fires on, listed or not (read before a run, for the falsifier)
    scan = []
    for stem, M in mods.items():
        for ent in M.ents:
            E = Entity(M, ent)
            for nm in M.ents[ent]:
                v = verdict(E, nm)
                if v:
                    scan.append((short(stem), ent, nm, v))
    print("scan:", len(scan), "closed-set elements fire")
    for row in scan:
        print("  ", *row)


if __name__ == "__main__":
    main()
