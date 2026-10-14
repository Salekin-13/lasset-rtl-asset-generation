"""Fix P1, code check: drop listed primaries that a v7 bar already says never qualify as primary.

Run:  python check.py <out.json>        (add --scan to also print every closed-set element each test matches)

Reads ONLY the stored v7 Phase 2 replies (failure_analysis/raw/r<k>/phase2/<module>.json, k = 0, 1, 2) and the inputs
(inputs/v1/tuning/<module>/{rtl.txt, closed_set.json}). It opens no reference file. Writes
  {"r0": {"<module short name>": [{"element", "entity", "action": "drop"}]}, "r1": {...}, "r2": {...}}

Each test is the testable condition of a v7 bar, read in closed-set facts (role in RTL, counterparts, record type,
direction) and in the element's own assignment lines of rtl.txt; no test names an element.
  COPY    phase1.md:28 / phase2.md:34 "Second copies": an internal register (not a port) that directly copies bits of
          one other register of its own entity, not as an index, whose other assignments write only constants, and
          that no condition reads.
  OPERAND phase1.md:42 / phase2.md:34 operand-copy sentence, read with common.md:98 ("a copy kept only while the value
          moves ... not a primary"): a clocked element (not a port) written whole (not at an index: a memory is a store)
          whose value, apart from constants and itself, comes only from one input port or input-port field, directly
          or through its next-value wire (a wire giving value to nothing else), a sign bit of that input ANDed with one
          other element being allowed; that gives value on to some element other than itself and that wire; and whose
          value reaches no output port and no instance port except through another clocked element (the result's
          holder). The unit clause of the v7 sentence (a unit executing processor-issued operations) is not tested.
  RECORD  phase1.md:33 / phase2.md:34 instance-driven records, and phase1.md:27 / phase2.md:34 "a record this unit only
          wires between a unit port and the port map of an instance": a record, or a field of one, whose own entry has
          non-empty counterparts only of kind 'gets value from' / 'gives value to', every one an instance port (a
          signal record: exactly one instance port drives it; a port record: no field has a counterpart that is an
          element of this unit, apart from its clock and reset).
  BUSREC  common.md:99 / phase2.md:34: a bus request record port (its fields carry an address, data and a strobe) or a
          bus response record port (its fields carry data, an acknowledge and an error flag), or any field of one.
  SHIFT   phase1.md:37 / phase2.md:34 serial shift registers: a clocked register that gets value from itself in an
          assignment joining a slice of itself with another value (a shift), that is next to a non-record unit data
          port (through elements only carrying one value), and that is decided, directly or through deciders and their
          sources, by a register a bus write sets (the unit's own rate setting, not a peer's clock).
Not tested: the port-option bar (phase1.md:39). Its closed-set form needs to know which ports are interrupt requests or
flow-control handshakes, which v7 judges from port names; a form without names also matched rate and timeout settings.
"""
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
FA = HERE.parent.parent                       # failure_analysis
LAB = FA.parent.parent.parent                 # final/pio/lab
RAW = FA / "raw"
INPUTS = LAB / "inputs" / "v1" / "tuning"
RUNS = (0, 1, 2)

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
GETS, GIVES, DECBY, DECS = "gets value from", "gives value to", "decided by", "decides"


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


def load_cs(m):
    d = json.loads((INPUTS / m / "closed_set.json").read_text(encoding="utf-8"))
    return {e["entity name"]: Ent(e) for e in d["entity list"]}


# ----------------------------------------------------------------------------------------- RTL helpers ---
def assignments(E, n, rtl):
    """Assignment lines of element n in rtl: list of (line, indexed, rhs or None when the statement spans lines).
    A whole-record assignment to n's record counts as an assignment to n."""
    i = E.get(n)
    targets = [n] + ([i["parent"]] if i and i["parent"] else [])
    lines = set(i["lines"]) if i else set()
    if i and i["parent"]:
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
    copy = re.compile(rf"^{re.escape(p)}\s*(\([^()]*\))?$")
    asg = assignments(E, n, rtl)
    ncopy = 0
    for _L, indexed, rhs in asg:
        if indexed or rhs is None:
            return False
        if copy.match(rhs):
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
    holder, nv = n, None
    if len(src) == 1 and not E.is_port(src[0]) and E.get(src[0]) and not E.clocked(src[0]):
        w = src[0]
        if [g for g in E.partners(w, GIVES) if g != w] == [n]:
            nv, holder = w, w                          # next-value wire: a wire giving value to nothing but n
            src = [s for s in E.partners(w, GETS) if s not in (n, w)]
            if any(not isinstance(s, str) for s in src):
                return False
    ins = [s for s in src if E.is_port(s) and (E.get(s)["direction"] == "in")]
    if len(ins) != 1:
        return False
    p = ins[0]
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
    return True


def _last(f):
    return f.rsplit(".", 1)[-1]


def is_bus_record_port(E, r):
    ri = E.get(r)
    if not ri or ri["kind"] != "port" or not ri["record type"] or ri["parent"]:
        return False
    fs = {_last(f) for f in ri["fields"]}
    return {"data", "ack", "err"} <= fs or {"addr", "data", "stb"} <= fs


def is_bus_request_field(E, n):
    i = E.get(n)
    return bool(i) and i["kind"] == "port" and bool(i["parent"]) and i["direction"] == "in" and is_bus_record_port(E, i["parent"])


def is_bus_response_field(E, n):
    i = E.get(n)
    return bool(i) and i["kind"] == "port" and bool(i["parent"]) and i["direction"] == "out" and is_bus_record_port(E, i["parent"])


def t_busrec(E, n, rtl):
    r = E.record_of(n)
    return bool(r) and is_bus_record_port(E, r)


def _plain_port(E, n, dirs):
    i = E.get(n)
    return bool(i) and i["kind"] == "port" and not i["parent"] and not i["record type"] and i["direction"] in dirs \
        and not (i["roles"] & {"clock", "reset"})


def _carrier_back_to_input(E, n):
    """Through elements whose value comes from exactly one other element (wires, synchronizer stages)."""
    seen, todo = {n}, [s for s in E.partners(n, GETS) if s != n]
    while todo:
        s = todo.pop()
        if not isinstance(s, str) or s in seen:
            continue
        seen.add(s)
        if _plain_port(E, s, ("in", "inout")):
            return True
        if E.get(s) and not E.is_port(s):
            ss = [x for x in E.partners(s, GETS) if x != s]
            if len(ss) == 1:
                todo += ss
    return False


def _carrier_on_to_output(E, n):
    seen, todo = {n}, [g for g in E.partners(n, GIVES) if g != n]
    while todo:
        g = todo.pop()
        if not isinstance(g, str) or g in seen:
            continue
        seen.add(g)
        if _plain_port(E, g, ("out", "inout")):
            return True
        if E.get(g) and not E.is_port(g):
            ss = [x for x in E.partners(g, GETS) if x != g]
            if ss and all(x in seen for x in ss):
                todo += [x for x in E.partners(g, GIVES) if x != g]
    return False


def bus_written(E, n):
    return any(isinstance(s, str) and is_bus_request_field(E, s) for s in E.partners(n, GETS))


def t_shift(E, n, rtl):
    i = E.get(n)
    if not i or i["kind"] == "port" or not E.clocked(n) or n not in E.partners(n, GETS):
        return False
    shift = re.compile(rf"(&\s*{re.escape(n)}\s*\()|({re.escape(n)}\s*\([^;]*\)\s*&)")
    if not any(rhs is not None and shift.search(rhs) for _L, _ix, rhs in assignments(E, n, rtl)):
        return False
    if not (_carrier_back_to_input(E, n) or _carrier_on_to_output(E, n)):
        return False
    seen, todo = {n}, [d for d in E.partners(n, DECBY) if isinstance(d, str) and d != n]
    while todo:
        d = todo.pop()
        if d in seen or E.get(d) is None:
            continue
        seen.add(d)
        if bus_written(E, d):
            return True
        todo += [x for x in E.partners(d, DECBY) + E.partners(d, GETS) if isinstance(x, str)]
    return False


TESTS = (("COPY", t_copy), ("OPERAND", t_operand), ("RECORD", t_record), ("BUSREC", t_busrec),
         ("SHIFT", t_shift))


def which(E, n, rtl):
    return [k for k, f in TESTS if f(E, n, rtl)]


# ----------------------------------------------------------------------------------------------- replies ---
def primaries(r, m):
    d = json.loads((RAW / f"r{r}" / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
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
# (element hash, RTL line, hash of that line's text after '|' stripped, test, expected)
SELFTEST = [
    ("a5ee0d6c36a6", 266, "bfe249383907", "COPY", True),      # copies a slice of a scan register
    ("1086a64cc70e", 248, "d8383c70d0cf", "COPY", False),     # copy, but a condition reads it (RTL 256)
    ("69c9a0389b43", 274, "c3c8a308b6e6", "COPY", False),     # source is a response port field
    ("d466e6f55b3d", 171, "8609dfba616b", "OPERAND", True),   # operand with its sign bit ANDed with signedness
    ("468f381b1294", 184, "6c2234d97551", "OPERAND", False),  # result register
    ("8a19a947d37f", 205, "5b432aeb398e", "OPERAND", True),   # operand copied at start
    ("4bad5f6a6da0", 179, "8bf07274bd17", "OPERAND", False),  # key store written at an index
    ("c79e0823d862", 378, "868abcf3af00", "SHIFT", True),     # data shift register next to the serial data port
    ("82a21e4a0924", 117, "4f7cd7cf549b", "BUSREC", True),    # bus response record port field
    ("3128f3dffcb0", 105, "b850dbeb6b78", "BUSREC", False),   # bus-written enable register
    ("b6f9e918ea2b", 199, "efdf88c3874d", "RECORD", True),    # field of a record one instance drives
    ("46ad58e2e30a", 420, "81b400389ae8", "RECORD", False),   # non-record signal one instance drives
]


def modules():
    return sorted(p.stem for p in (RAW / "r0" / "phase2").glob("*.json"))


def index_all():
    """{element hash: (module, Ent, element, rtl)} over every closed-set element of the run modules."""
    out = {}
    for m in modules():
        rtl = load_rtl(m)
        for en, E in load_cs(m).items():
            for n in E.names():
                out[h(f"{m}|{en}|{n}")] = (m, E, n, rtl)
    return out


def selftest(idx):
    fails = []
    for eh, L, lh, test, exp in SELFTEST:
        if eh not in idx:
            fails.append(f"{eh}: element not found")
            continue
        m, E, n, rtl = idx[eh]
        if h(rtl.get(L, "").split("|")[-1].strip()) != lh:
            fails.append(f"{eh}: RTL line {L} is not the hand-read line")
        got = dict(TESTS)[test](E, n, rtl)
        if got != exp:
            fails.append(f"{eh}: {test} gave {got}, hand reading says {exp}")
    return fails


# -------------------------------------------------------------------------------------------------- main ---
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("usage: python check.py <out.json> [--scan]")
        sys.exit(2)
    idx = index_all()
    fails = selftest(idx)
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
