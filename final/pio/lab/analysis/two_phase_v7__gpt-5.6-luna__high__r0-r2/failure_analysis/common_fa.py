"""Shared helpers for the v7 failure analysis (two_phase_v7, gpt-5.6-luna, high, r0-r2, 15 tuning modules).

Read-only on the run folders, the inputs and the reference. Everything this analysis writes goes under this folder.

- The scorer is compare_condensed.score() (exact names, each reference entry used once, 109 findable per run), reached
  through compare_v7 as the task asks. Element keys are "<short>:<name>#<k>" (k = the k-th reference entry of that name).
- The raw replies are copied byte for byte from each stored record's "raw" field into raw/r<k>/phase<p>/<module>.json,
  so that "file:line" in the packs points into the model's own text. line_maps() finds each concept, walk, point, asset
  row and Not Kept row in those copies; every line it returns is checked to contain the key and value it stands for.
- Reference concepts (RC ids): analysis/two_phase_v6__gpt-5.6-luna__high__r0-r2/refconcepts.json. An entry's home
  concept is the k-th concept that has its name among its home elements (build_pack3.py's rule).
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
V7DIR = HERE.parent
AN = V7DIR.parent
LAB = AN.parent
ROOT = LAB.parents[2]
for p in (LAB, ROOT / "src", V7DIR, AN / "two_phase_v1__gpt-5.4__high__r0", AN / "two_phase_v1__gpt-5.4__high__r0" / "failure_patterns"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402
import compare_v7 as C7  # noqa: E402  (imports compare_condensed as C7.CC)

CC = C7.CC
VERSION, MODEL, EFF, REPS = "two_phase_v7", "gpt-5.6-luna", "high", (0, 1, 2)
MODS = CC.MODS
RUNS = [f"r{r}" for r in REPS]
RAW = HERE / "raw"
REFCONCEPTS = AN / "two_phase_v6__gpt-5.6-luna__high__r0-r2" / "refconcepts.json"
PROMPTS = LAB / "prompts" / "two_phase_v7"
INPUTS = LAB / "inputs" / "v1" / "tuning"


def short(m):
    return m.replace("neorv32_", "")


def rel(p):
    """Path relative to the repo root, forward slashes."""
    return str(Path(p).resolve().relative_to(ROOT)).replace("\\", "/")


def run_dir(r):
    return CH.run_dir(VERSION, MODEL, r, EFF)


def record(r, m, phase):
    return json.loads((run_dir(r) / f"phase{phase}" / f"{m}.json").read_text(encoding="utf-8"))


def raw_path(r, m, phase):
    return RAW / f"r{r}" / f"phase{phase}" / f"{m}.json"


def extract_raw():
    """Copy every stored reply's 'raw' text byte for byte; returns the number of files and a self-check."""
    n, ok = 0, True
    for r in REPS:
        for m in MODS:
            for ph in (1, 2):
                rec = record(r, m, ph)
                p = raw_path(r, m, ph)
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="") as f:
                    f.write(rec["raw"])
                with open(p, encoding="utf-8", newline="") as f:
                    ok &= f.read() == rec["raw"]
                n += 1
    return n, ok


def parsed(r, m, phase):
    return K.parse_json(record(r, m, phase)["raw"])


def assets(r, m):
    return json.loads((run_dir(r) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]


# ------------------------------------------------------------------------------------------- reference ---
def _refs():
    import eval_assets as ea
    with CH.at_root():
        r = ea.load_refs()["gt"]
    return r


REFS_ALL = _refs()
REFC = json.loads(REFCONCEPTS.read_text(encoding="utf-8"))


def ref_entries(m):
    """Findable reference entries of a module, in reference order: (key, name, k, home RC id)."""
    names = {n for (_, n) in CH.closed_names(m)}
    out, kth, kth_all = [], Counter(), Counter()
    for n, _obj in REFS_ALL[m]:
        kth_all[n] += 1
        if n not in names:
            continue
        kth[n] += 1
        homes = [c["id"] for c in REFC[m] if n in c["home_elements"]]
        home = homes[min(kth_all[n], len(homes)) - 1] if homes else None
        out.append((f"{short(m)}:{n}#{kth[n]}", n, kth[n], home))
    return out


def refc_line(m, rcid):
    """Line in refconcepts.json where this module's concept rcid starts ('"id": "RCx"' line of that module's block)."""
    lines = REFCONCEPTS.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith(f'"{m}"'))
    for i in range(start, len(lines)):
        if lines[i].strip() == f'"id": "{rcid}"' or lines[i].strip() == f'"id": "{rcid}",':
            return i + 1
    return None


# ------------------------------------------------------------------------------------------- scoring ---
def score_run(r):
    """Per module: (listed, correct, found keys, listed (module, element) pairs), from compare_condensed.score()."""
    return {m: CC.score(VERSION, r, m) for m in MODS}


def fp_listings(r, m):
    """The listed primaries of one module and run that no reference entry consumed (exact; each entry used once).
    When a name is listed under more than one entity and the reference holds fewer entries of it, the later listings
    in the assets file are the false positives (the scorer counts names only)."""
    a = assets(r, m)
    need = Counter(n for (_k, n, _kk, _h) in ref_entries(m))
    out = []
    for x in a:
        n = x["Asset RTL"]
        if need[n] > 0:
            need[n] -= 1
            continue
        out.append({"element": n, "entity": x["Entity"], "concepts": x.get("Concepts", [])})
    return out


# ------------------------------------------------------------------------------------------- reply line maps ---
def _find(lines, pat, lo, hi):
    rx = re.compile(pat)
    for i in range(lo, hi):
        if rx.search(lines[i]):
            return i
    return None


def _q(s):
    return re.escape(json.dumps(s, ensure_ascii=False)[1:-1]) if isinstance(s, str) else re.escape(str(s))


def line_maps(r, m):
    """1-based lines in the raw copies. phase1: concept id -> line; not kept index -> line. phase2: walk id -> {line,
    points: [line], assets: [line], not_reported: [line], npr: line}. Every line is checked to hold its key and value;
    a failed check raises."""
    p1, p2 = parsed(r, m, 1), parsed(r, m, 2)
    L1 = raw_path(r, m, 1).read_text(encoding="utf-8").splitlines()
    L2 = raw_path(r, m, 2).read_text(encoding="utf-8").splitlines()
    out = {"phase1": {}, "not kept": [], "phase2": {}}
    ca = _find(L1, r'"Conceptual Assets"\s*:', 0, len(L1))
    pos = ca or 0
    for c in p1.get("Conceptual Assets", []) or []:
        if not isinstance(c, dict):
            continue
        i = _find(L1, r'"Concept ID"\s*:\s*"' + _q(c.get("Concept ID")) + '"', pos, len(L1))
        if i is None:
            raise AssertionError(f"line map: r{r} {m} phase1 concept {c.get('Concept ID')} not found")
        out["phase1"][c.get("Concept ID")] = i + 1
        pos = i + 1
    nk = _find(L1, r'"Not Kept"\s*:', 0, len(L1))
    pos = nk if nk is not None else len(L1)
    for x in p1.get("Not Kept", []) or []:
        if not isinstance(x, dict):
            out["not kept"].append(None)
            continue
        i = _find(L1, r'"Candidate Name"\s*:\s*"' + _q(x.get("Candidate Name")) + '"', pos, len(L1))
        if i is None:
            raise AssertionError(f"line map: r{r} {m} not kept {x.get('Candidate Name')} not found")
        out["not kept"].append(i + 1)
        pos = i + 1
    walks = [w for w in (p2.get("Concept Walks") or []) if isinstance(w, dict)]
    cw = _find(L2, r'"Concept Walks"\s*:', 0, len(L2)) or 0
    starts, pos = [], cw
    for w in walks:
        i = _find(L2, r'"Concept ID"\s*:\s*"' + _q(w.get("Concept ID")) + '"', pos, len(L2))
        if i is None:
            raise AssertionError(f"line map: r{r} {m} walk {w.get('Concept ID')} not found")
        starts.append(i)
        pos = i + 1
    for j, w in enumerate(walks):
        lo, hi = starts[j], (starts[j + 1] if j + 1 < len(starts) else len(L2))
        d = {"line": lo + 1, "points": [], "assets": [], "not reported": [], "npr": None}
        pos = lo
        for p in w.get("Points") or []:
            i = _find(L2, r'"Point"\s*:\s*"' + _q(p.get("Point") if isinstance(p, dict) else "") + '"', pos, hi)
            d["points"].append(None if i is None else i + 1)
            pos = (i + 1) if i is not None else pos
        pos = lo
        for a in w.get("Assets") or []:
            i = _find(L2, r'"Asset RTL"\s*:\s*"' + _q(a.get("Asset RTL") if isinstance(a, dict) else "") + '"', pos, hi)
            d["assets"].append(None if i is None else i + 1)
            pos = (i + 1) if i is not None else pos
        pos = lo
        for x in w.get("Not Reported") or []:
            i = _find(L2, r'"Element RTL"\s*:\s*"' + _q(x.get("Element RTL") if isinstance(x, dict) else "") + '"', pos, hi)
            d["not reported"].append(None if i is None else i + 1)
            pos = (i + 1) if i is not None else pos
        i = _find(L2, r'"No Primary Reason"\s*:', lo, hi)
        d["npr"] = None if i is None else i + 1
        out["phase2"].setdefault(w.get("Concept ID"), d)
    return out


# ------------------------------------------------------------------------------------------- inputs ---
import build_pack as BP  # noqa: E402  (element facts and the diagram parser, self-tested there)

_MOD = {}


def module(m):
    if m not in _MOD:
        _MOD[m] = BP.Module(m)
    return _MOD[m]


def rtl_file_lines(m):
    """RTL line number -> (file line in rtl.txt, text)."""
    out = {}
    for i, l in enumerate((INPUTS / m / "rtl.txt").read_text(encoding="utf-8").splitlines(), 1):
        mm = re.match(r"\s*(\d+) \|(.*)$", l)
        if mm:
            out[int(mm.group(1))] = (i, mm.group(2).rstrip())
    return out


def diagram_file_lines(m):
    return (INPUTS / m / "diagram.txt").read_text(encoding="utf-8").splitlines()


def element_lines(m, name):
    """Union over entities of the closed-set occurrence lines of a name."""
    out = set()
    for (e, n), x in CH.closed_names(m).items():
        if n == name:
            out |= set(x.get("occurrence lines") or [])
    return sorted(out)


def element_roles(m, name):
    """Closed-set 'role in RTL' set per entity holding the name."""
    return {e: tuple(sorted(x.get("role in RTL") or [])) for (e, n), x in CH.closed_names(m).items() if n == name}


def element_port(m, name):
    """The unit port an element is or belongs to (itself for a port, its base for a port field), else None."""
    cs = json.loads((INPUTS / m / "closed_set.json").read_text(encoding="utf-8"))
    ports = {p["port"] for e in cs["entity list"] for p in e["port list"]}
    if name in ports:
        return name
    base = name.split(".")[0]
    return base if base != name and base in ports else None


def points_with_element(m, name):
    """Diagram places where an element appears: blocks whose member list has it (or its record base), and the port
    itself for a port or port field. Returns {point name: (diagram file line, why)}."""
    M = module(m)
    lines = diagram_file_lines(m)
    out = {}
    base = name.split(".")[0]
    ents = M.entities_of(name)
    units = [u for u, es in M.ue.items() if set(ents) & set(es)] or list(M.dg)
    for u in units:
        for b, (kind, mem) in M.dg[u]["blocks"].items():
            if name in mem or base in mem:
                ln = next((i + 1 for i, l in enumerate(lines) if re.match(r"\s+\[" + kind + r"\]\s+" + re.escape(b) + r"\b", l)), None)
                out[b] = (ln, f"[{kind}] block member" + (" (record base)" if name not in mem else ""))
        port = element_port(m, name)
        if port and (port in M.dg[u]["inputs"] or port in M.dg[u]["outputs"]):
            ln = next((i + 1 for i, l in enumerate(lines) if l.strip().startswith(("INPUTS:", "OUTPUTS:")) and re.search(r"(?<![\w.])" + re.escape(port) + r"(?![\w])", l)), None)
            out[port] = (ln, "unit port")
    return out


def arrows_with_element(m, name):
    """Diagram arrow lines that carry the element (or name it as an endpoint), with their file lines."""
    lines = diagram_file_lines(m)
    out = []
    for i, l in enumerate(lines, 1):
        if ("==>" in l or "-->" in l) and name in BP.tokens(l):
            out.append((i, l.strip()))
    return out


def has_name(name, text):
    return bool(re.search(r"(?<![\w.])" + re.escape(name) + r"(?!\w)(?!\.\w)", text or ""))
