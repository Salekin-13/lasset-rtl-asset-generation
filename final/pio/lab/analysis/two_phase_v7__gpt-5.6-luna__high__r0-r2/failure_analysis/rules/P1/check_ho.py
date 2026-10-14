"""Fix P1 (revised), code check: drop listed primaries that a v7 bar already says never qualify as primary.

Run:  python check.py <out.json> [--scan] [--raw DIR] [--inputs DIR] [--runs 0,1,2]
  Defaults: --raw failure_analysis/raw (the stored v7 replies), --inputs inputs/v1/tuning, --runs 0,1,2.
  --raw / --inputs / --runs let the same check run on a new v7 run or on held-out modules (the falsifier needs this).
  --scan also prints every closed-set element each test matches.

Reads ONLY the Phase 2 replies (<raw>/r<k>/phase2/<module>.json) and the inputs (<inputs>/<module>/{rtl.txt,
closed_set.json}). It opens no reference file. Writes
  {"r0": {"<module short name>": [{"element", "entity", "action": "drop"}]}, "r1": {...}, "r2": {...}}

Each test is the testable condition of a v7 bar, read in closed-set facts (role in RTL, counterparts, record type,
direction) and in the element's own RTL lines (assignment lines, port declaration, generate branches). No test names an
element, a field or a type of the design.

  Register-access record ports (used by BUSREC, OPERAND and SHIFT). A pair (P, Q): P is an input record port, Q an
          output record port of the same entity, and some clocked internal element X takes its value from a field of P
          (directly or through its next-value wire), is decided by another field of P (the strobe or address that
          lets the access happen), and gives its value straight to a field of Q (the read-back). That is a bus that
          writes and reads this unit's registers: common.md:99 "a bus request record port (one that carries an
          address, data and a strobe) or bus response record port (one that carries data, an acknowledge and an error
          flag)". P is its request port, Q its response port. Record ports the unit only forwards are not found here.
  COPY    phase1.md:28 / phase2.md:34 "Second copies": an internal register (not a port) that directly copies bits of
          one other register of its own entity, not as an index, whose other assignments write only constants, and
          that no condition reads.
  OPERAND phase1.md:42 / phase2.md:34 operand-copy sentence: a clocked element (not a port) written whole (not at an
          index) whose value, apart from constants and itself, comes only from one input port or input-port field,
          directly or through its next-value wire (a sign bit of that input ANDed with one other element allowed);
          (unit clause) that input is not a field of a register-access request port: phase1.md:42 "A plain bus read or
          write is not covered", so a register a plain bus write sets is a setting, not an operand of an operation a
          processor issues; (operation clause) on its way through wires to the next clocked element, some statement
          applies an arithmetic, logic or compare operator to its value (the operation uses it; a copy, slice,
          concatenation or multiplexer path does not); and its value reaches no output port and no instance port
          except through another clocked element (the result's holder). Not tested: "when the operation starts".
  RECORD  phase1.md:33 / phase2.md:34 instance-driven records, and phase1.md:27 / phase2.md:34 "a record this unit only
          wires between a unit port and the port map of an instance ... (a constant tied to it in a generate branch
          lacking the instance is no such statement)": a record, or a field of one, whose own entry has non-empty
          counterparts only of kind 'gets value from' / 'gives value to', every one an instance port (a signal record:
          exactly one instance port drives it; a port record: no field has a counterpart that is an element of this
          unit, apart from its clock and reset, and every line where this unit assigns the record or a field lies in a
          generate branch whose lines map the record to no instance port).
  BUSREC  common.md:99 / phase2.md:34: a register-access request or response record port, or any field of one.
  SHIFT   phase1.md:37 / phase2.md:34 serial shift registers: a clocked register that gets value from itself in an
          assignment joining a slice of itself with another value (a shift); next to a one-bit (serial) non-record
          unit data port (declared without a range), through elements only carrying one value; and decided, through
          deciders and their sources up to PACE_HOPS steps away, by a register a register-access request port writes
          (the unit's own setting, not a peer's clock). Not tested: that this setting is a rate rather than an enable.
Not tested: the port-option bar (phase1.md:39). v7 judges interrupt-request and flow-control ports from port names; no
closed-set form without names was built.
"""
import copy
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
FA = HERE.parent.parent                       # failure_analysis
LAB = FA.parent.parent.parent                 # final/pio/lab
RAW = __import__("pathlib").Path(__import__("os").environ.get("RAW_DIR", str(FA / "raw")))
INPUTS = __import__("pathlib").Path(__import__("os").environ.get("INPUTS_DIR", str(LAB / "inputs" / "v1" / "tuning")))
RUNS = (0, 1, 2)
PACE_HOPS = 4                                 # decider steps followed by SHIFT (the C1 test's bound, FPA-P5 skeptic B)

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
GETS, GIVES, DECBY, DECS = "gets value from", "gives value to", "decided by", "decides"
OPS = re.compile(r"(\+|-|\*|/|<|>|=|\b(?:and|or|xor|nand|nor|xnor|not|mod|rem|abs|sll|srl|sla|sra|rol|ror)\b)", re.I)


def short(m):
    return m.split("_", 1)[1] if "_" in m else m


def h(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


# ------------------------------------------------------------------------------------------------ inputs ---
def load_rtl(m):
    out = {}
    for raw in (INPUTS / m / "rtl.txt").read_text(encoding="utf-8").splitlines():
        mm = re.match(r"^\s*(\d+) \|(.*)$", raw)
        if mm:
            out[int(mm.group(1))] = mm.group(2).split("--")[0].rstrip()
    return out


class Ent:
    """One entity of a closed set: name -> info."""

    def __init__(self, e):
        self.name = e["entity name"]
        self.el = {}
        for kind, key in (("port", "port list"), ("signal", "signal list")):
            for x in e.get(key, []):
                n = x.get("port") or x.get("signal")
                self.el[n] = self._info(x, kind, None, x)
                for f in x.get("fields", []) or []:
                    self.el[f["field"]] = self._info(f, kind, n, x)
        self._pairs = None

    @staticmethod
    def _info(x, kind, parent, rec):
        cp = x.get("counterparts", {}) or {}
        return {"kind": kind, "parent": parent, "direction": x.get("direction") or (rec.get("direction") if parent else None),
                "record type": x.get("record type"), "type": x.get("type"), "roles": set(x.get("role in RTL", []) or []),
                "lines": x.get("occurrence lines", []) or [], "cp": cp,
                "fields": [f["field"] for f in (x.get("fields", []) or [])]}

    def names(self):
        return set(self.el)

    def get(self, n):
        return self.el.get(n)

    def partners(self, n, key):
        """Element partners (names) of one counterpart kind; instance entries come back as ('@', inst, port)."""
        out = []
        for c in (self.el[n]["cp"].get(key) or []):
            out.append(c["element"] if "element" in c else ("@", c.get("instance"), c.get("port")))
        return out

    def lines_of(self, n, key, partner):
        for c in (self.el[n]["cp"].get(key) or []):
            if c.get("element") == partner:
                return c.get("lines", [])
        return []

    def is_port(self, n):
        i = self.el.get(n)
        return bool(i) and i["kind"] == "port"

    def clocked(self, n):
        i = self.el.get(n)
        return bool(i) and "held on a clock edge" in i["roles"]

    def record_of(self, n):
        i = self.el.get(n)
        if not i:
            return None
        if i["parent"]:
            return i["parent"]
        return n if i["record type"] else None

    def port_record_field(self, n, direction):
        """The record port whose field n is, when that port has this direction; else None."""
        i = self.el.get(n)
        if not i or i["kind"] != "port" or not i["parent"]:
            return None
        return i["parent"] if i["direction"] == direction else None

    def next_value_wire(self, n):
        """The wire feeding n that gives value to nothing but n (and itself), or None."""
        src = [s for s in self.partners(n, GETS) if s != n]
        if len(src) == 1 and isinstance(src[0], str) and not self.is_port(src[0]) and self.get(src[0]) \
                and not self.clocked(src[0]):
            w = src[0]
            if [g for g in self.partners(w, GIVES) if g != w] == [n]:
                return w
        return None

    def access_pairs(self):
        """Register-access record ports: (set of request ports P, set of response ports Q)."""
        if self._pairs is not None:
            return self._pairs
        req, rsp = set(), set()
        for x in self.el:
            if self.is_port(x) or not self.clocked(x):
                continue
            nv = self.next_value_wire(x)
            src = [s for s in self.partners(x, GETS) if isinstance(s, str)]
            dec = [d for d in self.partners(x, DECBY) if isinstance(d, str)]
            if nv:
                src += [s for s in self.partners(nv, GETS) if isinstance(s, str)]
                dec += [d for d in self.partners(nv, DECBY) if isinstance(d, str)]
            outs = {self.port_record_field(g, "out") for g in self.partners(x, GIVES) if isinstance(g, str)} - {None}
            if not outs:
                continue
            for s in src:
                P = self.port_record_field(s, "in")
                if P and any(d != s and self.port_record_field(d, "in") == P for d in dec):
                    req.add(P)
                    rsp |= outs
        self._pairs = (req, rsp)
        return self._pairs


def load_cs(m):
    d = json.loads((INPUTS / m / "closed_set.json").read_text(encoding="utf-8"))
    return {e["entity name"]: Ent(e) for e in d["entity list"]}


# ----------------------------------------------------------------------------------------- RTL helpers ---
def assignments(E, n, rtl, with_parent=True):
    """Assignment lines of element n in rtl: list of (line, indexed, rhs or None when the statement spans lines).
    A whole-record assignment to n's record counts as an assignment to n."""
    i = E.get(n)
    targets = [n] + ([i["parent"]] if with_parent and i and i["parent"] else [])
    lines = set(i["lines"]) if i else set()
    if with_parent and i and i["parent"]:
        lines |= set(E.get(i["parent"])["lines"])
    out = []
    for L in sorted(lines):
        t = rtl.get(L, "").strip()
        for tg in targets:
            if not t.startswith(tg):
                continue
            rest = t[len(tg):]
            if rest[:1] and (rest[:1].isalnum() or rest[:1] in "_."):
                continue
            rest = rest.lstrip()
            indexed = False
            if rest.startswith("("):
                depth, k = 0, 0
                for k, ch in enumerate(rest):
                    depth += ch == "("
                    depth -= ch == ")"
                    if depth == 0:
                        break
                rest, indexed = rest[k + 1:].lstrip(), True
            if not rest.startswith("<="):
                continue
            rhs = rest[2:].strip()
            out.append((L, indexed, rhs[:-1].strip() if rhs.endswith(";") else None))
            break
    return out


def is_constant(E, rhs):
    return rhs is not None and not any(tok in E.el for tok in IDENT.findall(rhs))


def _word(v):
    return re.compile(rf"(?<![\w.]){re.escape(v)}(?!\w)")


def computes_line(text, v):
    """True if the statement on this line applies an arithmetic, logic or compare operator to v (not only a copy,
    slice, concatenation, multiplexer path, or a sign bit ANDed for sign extension)."""
    t = text.split("<=", 1)[1] if "<=" in text else text
    t = re.sub(r'"[^"]*"', " ", t)
    t = re.sub(r"'[^']'", " ", t)                       # character literals
    t = re.sub(r"'\w+", " ", t)                          # attributes such as 'left
    t = t.replace("=>", " ")
    t = re.sub(r"\(\s*[\w.]+\s*(?:\([^()]*\))?\s+and\s+[\w.]+\s*(?:\([^()]*\))?\s*\)", " ", t)   # sign-bit AND
    parts = re.split(r"\bwhen\b", t)
    keep = parts[0]
    for p in parts[1:]:
        m = re.search(r"\belse\b", p)
        cond, rest = (p[:m.start()], p[m.end():]) if m else (p, "")
        if _word(v).search(cond):
            keep += " " + cond
        keep += " " + rest
    if not _word(v).search(keep):
        return False
    return bool(OPS.search(keep))


def computes(E, n, rtl):
    """Operation clause: on the way from n through wires to the next clocked element, a statement computes with it."""
    seen, todo = {n}, [n]
    while todo:
        x = todo.pop()
        for c in (E.get(x)["cp"].get(GIVES) or []):
            g = c.get("element")
            if g is None or g == x:
                continue
            if any(computes_line(rtl.get(L, ""), x) for L in c.get("lines", [])):
                return True
            gi = E.get(g)
            if gi and gi["kind"] != "port" and not E.clocked(g) and g not in seen:
                seen.add(g)
                todo.append(g)
    return False


def one_bit_port(E, n, rtl):
    """The port's declaration line (one of its occurrence lines) gives a type with no range."""
    i = E.get(n)
    for L in i["lines"]:
        m = re.match(rf"^\s*{re.escape(n)}\s*:\s*(in|out|inout|buffer)\b(.*)$", rtl.get(L, ""), re.I)
        if m:
            return "(" not in m.group(2)
    return False


def in_branch_lacking_map(rtl, L, rec):
    """Line L lies in a generate branch none of whose lines maps rec to an instance port ('=> rec')."""
    keys = sorted(rtl)
    if L not in rtl:
        return False
    k = keys.index(L)
    depth, start = 0, None
    for j in range(k - 1, -1, -1):
        t = rtl[keys[j]]
        if re.search(r"\bend\s+generate\b", t, re.I):
            depth += 1
        elif re.search(r"\bgenerate\b", t, re.I):
            if depth == 0:
                start = j
                break
            depth -= 1
    if start is None:
        return False
    depth, end = 0, None
    for j in range(start + 1, len(keys)):
        t = rtl[keys[j]]
        if re.search(r"\bend\s+generate\b", t, re.I):
            if depth == 0:
                end = j
                break
            depth -= 1
        elif re.search(r"\bgenerate\b", t, re.I):
            depth += 1
    if end is None:
        return False
    mapped = re.compile(rf"=>\s*{re.escape(rec)}(?![\w])")
    return not any(mapped.search(rtl[keys[j]]) for j in range(start, end + 1))


# --------------------------------------------------------------------------------------------- the tests ---
def t_copy(E, n, rtl):
    i = E.get(n)
    if not i or i["kind"] == "port" or i["type"] != "reg" or i["record type"]:
        return False
    if i["roles"] & {"condition", "selector", "index"}:
        return False
    src = E.partners(n, GETS)
    if len(src) != 1 or not isinstance(src[0], str) or src[0] == n:
        return False
    p = src[0]
    pi = E.get(p)
    if not pi or pi["kind"] == "port" or pi["type"] != "reg":
        return False
    cp = re.compile(rf"^{re.escape(p)}\s*(\([^()]*\))?$")
    asg = assignments(E, n, rtl)
    ncopy = 0
    for _L, indexed, rhs in asg:
        if indexed or rhs is None:
            return False
        if cp.match(rhs):
            ncopy += 1
        elif not is_constant(E, rhs):
            return False
    return ncopy > 0


def _sign_and(text, p, x):
    a = rf"{re.escape(p)}\s*\([^()]*\)"
    b = re.escape(x)
    return bool(re.search(rf"\(\s*{a}\s+and\s+{b}\s*\)", text) or re.search(rf"\(\s*{b}\s+and\s+{a}\s*\)", text))


def t_operand(E, n, rtl):
    i = E.get(n)
    if not i or i["kind"] == "port" or not E.clocked(n):
        return False
    asg = assignments(E, n, rtl)
    if not asg or any(ix for _L, ix, _r in asg):
        return False                                   # a memory written at an index is a store, not an operand copy
    src = [s for s in E.partners(n, GETS) if s != n]
    if any(not isinstance(s, str) for s in src):
        return False
    holder, nv = n, E.next_value_wire(n)
    if nv:
        holder = nv
        src = [s for s in E.partners(nv, GETS) if s not in (n, nv)]
        if any(not isinstance(s, str) for s in src):
            return False
    ins = [s for s in src if E.is_port(s) and (E.get(s)["direction"] == "in")]
    if len(ins) != 1:
        return False
    p = ins[0]
    if E.port_record_field(p, "in") in E.access_pairs()[0]:
        return False                                   # unit clause: a plain bus write sets a setting, not an operand
    for x in src:
        if x == p:
            continue
        if E.is_port(x):
            return False
        ls = E.lines_of(holder, GETS, x)
        if not ls or not all(_sign_and(rtl.get(L, ""), p, x) for L in ls):
            return False
    if not [g for g in E.partners(n, GIVES) if g not in (n, nv)]:
        return False
    if not computes(E, n, rtl):
        return False                                   # operation clause: only copied, sliced, packed or multiplexed
    seen, todo = {n}, [g for g in E.partners(n, GIVES)]
    while todo:
        g = todo.pop()
        if not isinstance(g, str):
            return False                               # reaches an instance port through wires only
        if g in seen:
            continue
        seen.add(g)
        gi = E.get(g)
        if gi is None:
            continue
        if gi["kind"] == "port":
            if gi["direction"] in ("out", "inout"):
                return False                           # reaches an output port through wires only
            continue
        if E.clocked(g):
            continue                                   # another clocked element: the result's holder
        todo += E.partners(g, GIVES)
    return True


def _all_instance(cp, keys_ok):
    if not cp or set(cp) - keys_ok:
        return False
    return all("instance" in c for k in cp for c in cp[k])


def t_record(E, n, rtl):
    r = E.record_of(n)
    if not r:
        return False
    ri = E.get(r)
    if not ri["record type"] or not _all_instance(ri["cp"], {GETS, GIVES}):
        return False
    if ri["kind"] == "signal":
        return len(ri["cp"].get(GETS) or []) == 1 and bool(ri["cp"].get(GIVES))
    for f in ri["fields"]:
        if any("element" in c for k in E.get(f)["cp"] for c in E.get(f)["cp"][k] if k not in ("clocked by", "reset by")):
            return False
    writes = [L for x in [r] + ri["fields"] for (L, _ix, _rhs) in assignments(E, x, rtl, with_parent=False)]
    return all(in_branch_lacking_map(rtl, L, r) for L in writes)


def t_busrec(E, n, rtl):
    r = E.record_of(n)
    if not r or not E.is_port(r):
        return False
    req, rsp = E.access_pairs()
    return r in req or r in rsp


def _plain_port(E, n, dirs):
    i = E.get(n)
    return bool(i) and i["kind"] == "port" and not i["parent"] and not i["record type"] and i["direction"] in dirs \
        and not (i["roles"] & {"clock", "reset"})


def _carrier_back_to_input(E, n, rtl):
    """Through elements whose value comes from exactly one other element (wires, synchronizer stages)."""
    seen, todo = {n}, [s for s in E.partners(n, GETS) if s != n]
    while todo:
        s = todo.pop()
        if not isinstance(s, str) or s in seen:
            continue
        seen.add(s)
        if _plain_port(E, s, ("in", "inout")):
            if one_bit_port(E, s, rtl):
                return True
            continue
        if E.get(s) and not E.is_port(s):
            ss = [x for x in E.partners(s, GETS) if x != s]
            if len(ss) == 1:
                todo += ss
    return False


def _carrier_on_to_output(E, n, rtl):
    seen, todo = {n}, [g for g in E.partners(n, GIVES) if g != n]
    while todo:
        g = todo.pop()
        if not isinstance(g, str) or g in seen:
            continue
        seen.add(g)
        if _plain_port(E, g, ("out", "inout")):
            if one_bit_port(E, g, rtl):
                return True
            continue
        if E.get(g) and not E.is_port(g):
            ss = [x for x in E.partners(g, GETS) if x != g]
            if ss and all(x in seen for x in ss):
                todo += [x for x in E.partners(g, GIVES) if x != g]
    return False


def bus_written(E, n):
    req = E.access_pairs()[0]
    nv = E.next_value_wire(n)
    src = E.partners(n, GETS) + (E.partners(nv, GETS) if nv else [])
    return any(isinstance(s, str) and E.port_record_field(s, "in") in req for s in src)


def t_shift(E, n, rtl):
    i = E.get(n)
    if not i or i["kind"] == "port" or not E.clocked(n) or n not in E.partners(n, GETS):
        return False
    shift = re.compile(rf"(&\s*{re.escape(n)}\s*\()|({re.escape(n)}\s*\([^;]*\)\s*&)")
    if not any(rhs is not None and shift.search(rhs) for _L, _ix, rhs in assignments(E, n, rtl)):
        return False
    if not (_carrier_back_to_input(E, n, rtl) or _carrier_on_to_output(E, n, rtl)):
        return False
    seen = {n}
    frontier = [d for d in E.partners(n, DECBY) if isinstance(d, str) and d != n]
    for _hop in range(PACE_HOPS):
        nxt = []
        for d in frontier:
            if d in seen or E.get(d) is None:
                continue
            seen.add(d)
            if bus_written(E, d):
                return True
            nxt += [x for x in E.partners(d, DECBY) + E.partners(d, GETS) if isinstance(x, str)]
        frontier = nxt
    return False


TESTS = (("COPY", t_copy), ("OPERAND", t_operand), ("RECORD", t_record), ("BUSREC", t_busrec),
         ("SHIFT", t_shift))


def which(E, n, rtl):
    return [k for k, f in TESTS if f(E, n, rtl)]


# ----------------------------------------------------------------------------------------------- replies ---
def primaries(r, m):
    f = RAW / f"r{r}" / "phase2" / f"{m}.json"
    if not f.exists():
        return []
    d = json.loads(f.read_text(encoding="utf-8"))
    out = []
    for w in d.get("Concept Walks", []) or []:
        for a in w.get("Assets", []) or []:
            if str(a.get("Label", "")).strip().lower() == "primary":
                k = (a.get("Entity"), a.get("Asset RTL"))
                if k not in out:
                    out.append(k)
    return out


# --------------------------------------------------------------------------------------------- self-test ---
# Hand-read lines (read in rtl.txt this session). Names are hashed, not written: h("module|entity|element").
# (element hash, RTL line, hash of that line's text after '|' stripped, test, expected, plant)
# plant: None = the input as it is; otherwise a scratch copy changed as named, for a risk this input does not show:
#   "write-only"  remove every output-port partner from the element's 'gives value to' (a bus-set register with no
#                 read-back of its own; the unit clause must still spare it)
#   "wide-ports"  rewrite every non-record port declaration of the entity with a range (no serial port left)
#   "no-generate" delete the generate / end generate lines around the hand-read line (the constant tie is then a
#                 statement of this unit outside any generate branch)
SELFTEST = [
    ("a5ee0d6c36a6", 266, "bfe249383907", "COPY", True, None),       # copies a slice of a scan register
    ("1086a64cc70e", 248, "d8383c70d0cf", "COPY", False, None),      # copy, but a condition reads it (RTL 256)
    ("69c9a0389b43", 274, "c3c8a308b6e6", "COPY", False, None),      # source is a response port field
    ("d466e6f55b3d", 171, "8609dfba616b", "OPERAND", True, None),    # operand, sign bit ANDed with signedness; multiplied
    ("468f381b1294", 184, "6c2234d97551", "OPERAND", False, None),   # result register
    ("8a19a947d37f", 205, "5b432aeb398e", "OPERAND", True, None),    # operand copied at start; added/xored via a mux
    ("4bad5f6a6da0", 179, "8bf07274bd17", "OPERAND", False, None),   # key store written at an index
    ("69c9a0389b43", 274, "c3c8a308b6e6", "OPERAND", False, None),   # response data only packed into a scan word (229)
    ("@OPSYNC", 100, "@L100", "OPERAND", False, None),                # synchronizer stage (only re-sampled)
    ("@BAUD", 183, "@L183", "OPERAND", False, None),                  # bus-set setting with read-back
    ("@BAUD", 183, "@L183", "OPERAND", False, "write-only"),          # same, read-back removed: unit clause spares it
    ("@AMOW", 779, "@L779", "OPERAND", True, None),                   # atomic unit's write-data, via next-value wire
    ("c79e0823d862", 378, "868abcf3af00", "SHIFT", True, None),      # data shift register next to the serial data port
    ("c79e0823d862", 378, "868abcf3af00", "SHIFT", False, "wide-ports"),  # same, no one-bit port: spared
    ("@GENSREG", 360, "@L360", "SHIFT", False, None),                 # generator's sampling register, 8-bit output
    ("82a21e4a0924", 117, "4f7cd7cf549b", "BUSREC", True, None),     # register-access response port field
    ("3128f3dffcb0", 105, "b850dbeb6b78", "BUSREC", False, None),    # bus-written enable register
    ("b6f9e918ea2b", 199, "efdf88c3874d", "RECORD", True, None),     # field of a record one instance drives
    ("46ad58e2e30a", 420, "81b400389ae8", "RECORD", False, None),    # non-record signal one instance drives
    ("@ICCTX", 455, "@L455", "RECORD", True, None),                   # port record tied to a constant in a generate
    ("@ICCTX", 455, "@L455", "RECORD", False, "no-generate"),         # same tie outside any generate branch
]
SELFTEST_IDS = {}                                                    # filled below: '@' placeholders -> hashes


def modules():
    """Modules with a stored reply in the first run; with none (a scan of new inputs), every module of --inputs."""
    got = sorted(p.stem for p in (RAW / f"r{RUNS[0]}" / "phase2").glob("*.json"))
    return got or sorted(p.name for p in INPUTS.iterdir() if (p / "closed_set.json").exists())


def index_all():
    """{element hash: (module, Ent, element, rtl)} over every closed-set element of the run modules."""
    out = {}
    for m in modules():
        rtl = load_rtl(m)
        for en, E in load_cs(m).items():
            for n in E.names():
                out[h(f"{m}|{en}|{n}")] = (m, E, n, rtl)
    return out


def _plant(kind, E, n, rtl, L):
    E2, rtl2 = copy.deepcopy(E), dict(rtl)
    E2._pairs = None
    if kind == "write-only":
        cp = E2.el[n]["cp"]
        cp[GIVES] = [c for c in (cp.get(GIVES) or []) if not ("element" in c and E2.is_port(c["element"])
                                                                 and E2.get(c["element"])["direction"] != "in")]
    elif kind == "wide-ports":
        for p, i in E2.el.items():
            if i["kind"] == "port" and not i["parent"] and not i["record type"]:
                for k in i["lines"]:
                    rtl2[k] = re.sub(rf"^(\s*{re.escape(p)}\s*:\s*(?:in|out|inout|buffer)\s+\w+)(\s*;?)\s*$",
                                     r"\1_vector(7 downto 0)\2", rtl2.get(k, ""), flags=re.I)
    elif kind == "no-generate":
        keys = sorted(rtl2)
        k = keys.index(L)
        for j in range(k - 1, -1, -1):
            if re.search(r"\bgenerate\b", rtl2[keys[j]], re.I):
                del rtl2[keys[j]]
                break
        for j in range(k + 1, len(keys)):
            if re.search(r"\bend\s+generate\b", rtl2[keys[j]], re.I):
                del rtl2[keys[j]]
                break
    return E2, rtl2


# The placeholders below are SHA-256 prefixes, filled in by hand from a run of this script's index (no names here).
SELFTEST_IDS.update({
    "@OPSYNC": ("da83c5e9f8fc", "73f9fb0abeec"),
    "@BAUD": ("5215db4b34c3", "4d2f92bd26d9"),
    "@AMOW": ("578a0ca6e008", "05fc500e1bee"),
    "@GENSREG": ("0acd772c5711", "e10f09d51449"),
    "@ICCTX": ("00bc932597e6", "23cb2eec238a"),
})


def selftest(idx):
    fails = []
    for eh, L, lh, test, exp, plant in SELFTEST:
        if eh.startswith("@"):
            eh, lh = SELFTEST_IDS[eh]
        if eh not in idx:
            fails.append(f"{eh}: element not found")
            continue
        m, E, n, rtl = idx[eh]
        if h(rtl.get(L, "").split("|")[-1].strip()) != lh:
            fails.append(f"{eh}: RTL line {L} is not the hand-read line")
        if plant:
            E, rtl = _plant(plant, E, n, rtl, L)
        got = dict(TESTS)[test](E, n, rtl)
        if got != exp:
            fails.append(f"{eh}: {test}{' (' + plant + ')' if plant else ''} gave {got}, hand reading says {exp}")
    return fails


# -------------------------------------------------------------------------------------------------- main ---
def _opt(name, default):
    a = sys.argv[1:]
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def main():
    global RAW, INPUTS, RUNS
    sys.stdout.reconfigure(encoding="utf-8")
    RAW = Path(_opt("--raw", str(RAW)))
    INPUTS = Path(_opt("--inputs", str(INPUTS)))
    RUNS = tuple(int(x) for x in _opt("--runs", ",".join(map(str, RUNS))).split(","))
    skip = {i + 1 for i, a in enumerate(sys.argv[1:]) if a in ("--raw", "--inputs", "--runs")}
    args = [a for i, a in enumerate(sys.argv[1:]) if not a.startswith("--") and i not in skip]
    if not args:
        print("usage: python check.py <out.json> [--scan] [--raw DIR] [--inputs DIR] [--runs 0,1,2]")
        sys.exit(2)
    # The self-test reads the tuning inputs the hand-read lines come from, whatever --inputs says.
    run_inputs, run_raw, run_runs = INPUTS, RAW, RUNS
    INPUTS, RAW, RUNS = LAB / "inputs" / "v1" / "tuning", FA / "raw", (0, 1, 2)
    fails = selftest(index_all())
    INPUTS, RAW, RUNS = run_inputs, run_raw, run_runs
    print("self-test:", "PASS" if not fails else "FAIL")
    for f in fails:
        print("  ", f)
    if fails:
        sys.exit(1)
    cs = {m: load_cs(m) for m in modules()}
    rt = {m: load_rtl(m) for m in modules()}
    if "--scan" in sys.argv:
        for m in modules():
            for en, E in cs[m].items():
                for n in sorted(E.names()):
                    w = which(E, n, rt[m])
                    if w:
                        print("scan", short(m), en, n, ",".join(w))
    out, per = {}, defaultdict(int)
    for r in RUNS:
        out[f"r{r}"] = {}
        for m in modules():
            rows = []
            for en, n in primaries(r, m):
                E = cs[m].get(en)
                if E is None or E.get(n) is None:
                    continue
                w = which(E, n, rt[m])
                if w:
                    rows.append({"element": n, "entity": en, "action": "drop"})
                    per[f"r{r}"] += 1
                    print(f"r{r} {short(m)} drop {n} [{','.join(w)}]")
            if rows:
                out[f"r{r}"][short(m)] = rows
    Path(args[0]).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("dropped per run:", dict(per))


if __name__ == "__main__":
    main()
