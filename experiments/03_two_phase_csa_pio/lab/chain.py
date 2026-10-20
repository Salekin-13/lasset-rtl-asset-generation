"""Two-call chain runner and scorer converter for the two-phase lab prompts (lab/prompts/<version>/).

Per module: call 1 (common.md + phase1.md, user phase1_user.md) -> conceptual assets; call 2 (common.md + phase2.md,
user phase2_user.md with {concepts} = Phase 1's "conceptual assets" list) -> points and structural assets.
The converter keeps Phase 2's primary rows only and writes the scorer's format {"IP", "Assets": [{"Entity",
"Asset RTL", "Security Objective"}]}.
Two reply formats: v5's (lower-case keys; two_phase_v1 to v5) and the 2026-10-13 one (two_phase_v5f on: readable keys,
Phase 2 rows grouped under "Concept Walks"). A reply in the newer format is checked against it and stored in "reply"
mapped to v5's keys (see "reply formats" below), so the checks, the converter and the analysis scripts read one shape.

Folders (one per prompt version, input version and effort, never mixed):
  lab/runs/<version>__<input version>/<model>__<effort>/r<k>/
     _run_meta.json            prompt and template shas, model, effort, executor, input manifest sha
     phase1/<module>.json      request shas, usage, raw reply, parsed reply, problems (written as soon as the reply
                               arrives, before any check, so a paid reply is never lost)
     phase2/<module>.json      the same for call 2
     assets/<module>.json      the converter's output (scorer format)
     _failed_calls.jsonl       calls that came back incomplete or failed: status, usage, reason (not stored as replies)
     _failed/<key>.txt         the partial text of such a call
     _keys.jsonl               request key -> module and phase (to attribute failed calls)
     _pending/<key>.json       the id of an OpenAI background request in flight; a re-run collects it, never re-sends
A stored reply is never asked again, and a stored reply is used only for the exact message that produced it (system and
user sha); a mismatch stops the module with a message. Executors: openai(model, effort) for the notebook, or
pio_run.file_call(dir) for Claude agents (each request is saved as <key>.system.md / <key>.user.txt; the reply goes to
<key>.json). chain.file_call is that executor (labkit.file_call).

  python experiments/03_two_phase_csa_pio/lab/chain.py selftest
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
from collections import Counter
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[2]
for p in (LAB, ROOT / "src", ROOT / "assetgen_meta"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import check_lab_prompt as C  # noqa: E402
import labkit as K  # noqa: E402   (no graph code: the kit runs in any checkout with src/, assetgen_meta/, data/)

INPUT_VERSION = K.INPUT_VERSION
INPUTS = K.INPUTS
file_call = K.file_call                 # the Claude-agent executor (its NeedReply is the one run() catches)
QUESTIONS = ("confidentiality", "integrity", "availability", "undermined expected behavior")
WORD = {"C": "Confidentiality", "I": "Integrity", "A": "Availability"}
_CWD_LOCK = threading.Lock()
STOP = threading.Event()          # the latest run's stop flag; run() and run_many() each start a fresh one


def _stop_event() -> threading.Event:
    """The stop flag of the run this thread works for. run() and run_many() put their run's own flag on each worker
    thread (an attribute of the thread object, so it survives importlib.reload(chain)), and every run starts with a
    fresh flag instead of clearing the old one. A stopped run's flag stays set for good, so its leftover threads never
    send again, even after a reload or while a new run goes on. Threads that no run started use the module flag."""
    return getattr(threading.current_thread(), "lab_stop", None) or STOP


def _leftover_workers() -> list:
    """Worker threads of an earlier, stopped run that are still finishing a request: alive, with their flag set."""
    return [t for t in threading.enumerate()
            if t.is_alive() and getattr(t, "lab_stop", None) is not None and t.lab_stop.is_set()]


STOP_WAIT = 60                    # seconds a stopped run waits for its workers to end before it returns


class at_root:
    """The scorer (src/eval_assets.py) reads data/ground_truth and data/parsed_tuning18 relative to the working
    folder; every call that reaches it runs from the repository root."""

    def __enter__(self):
        import os
        _CWD_LOCK.acquire()
        self.old = os.getcwd()
        os.chdir(ROOT)

    def __exit__(self, *a):
        import os
        os.chdir(self.old)
        _CWD_LOCK.release()


def tuning_modules() -> list[str]:
    return K.gt_modules()["tuning"]


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def as_list(x) -> list:
    """A field the schema gives as a list: a list stays, one string becomes a one-item list, anything else is empty."""
    return x if isinstance(x, list) else ([x] if isinstance(x, str) and x else [])


def _key(x) -> str:
    return x if isinstance(x, str) else json.dumps(x, sort_keys=True)


# ------------------------------------------------------------------------------------------------ inputs ---
def module_dir(m: str) -> Path:
    for split in ("tuning", "heldout"):
        d = INPUTS / split / m
        if d.exists():
            return d
    raise FileNotFoundError(f"no inputs for {m} under {INPUTS}")


def inputs(m: str) -> dict:
    d = module_dir(m)
    return {f: (d / f).read_text(encoding="utf-8") for f in ("rtl.txt", "closed_set.json", "diagram.txt")}


def user_message(version: str, phase: int, m: str, concepts=None) -> str:
    """The user message of one call. The closed set goes in compact JSON (same content, no indentation); concepts is
    Phase 1's "conceptual assets" list (or, for size estimates, a string)."""
    x = inputs(m)
    t = (LAB / "prompts" / version / f"phase{phase}_user.md").read_text(encoding="utf-8")
    vals = {"module": m, "rtl": x["rtl.txt"], "diagram": x["diagram.txt"],
            "closed_set": json.dumps(json.loads(x["closed_set.json"]), separators=(",", ":"))}
    if phase == 2:
        vals["concepts"] = concepts if isinstance(concepts, str) else json.dumps(concepts, indent=1, ensure_ascii=False)
        if "{located}" in t:
            vals["located"] = "{}" if isinstance(concepts, str) else json.dumps(located(m, concepts), indent=1, ensure_ascii=False)
    return t.format(**vals)


def located(m: str, concepts) -> dict:
    """The LOCATED input of Phase 2 (versions whose phase2_user.md has a {located} slot; two_phase_v9m, 2026-10-18): for each
    concept of Phase 1's list, the closed-set elements its entry locates: the names in its Enters Through and Leaves Through
    that are closed-set names, and every closed-set element one of whose assignment lines (the "lines" of its counterparts
    under gets value from, decided by, reset by and clocked by, over every entity carrying the name) is one of the entry's Held
    Lines. Keys as written ("Concept ID", "Enters Through", "Leaves Through", "Held Lines") or the v5 keys ("id",
    "enters through", "leaves through", "held lines"). Deterministic: concept order kept, names sorted."""
    cn = closed_names(m)
    names = {x for (_, x) in cn}
    assign: dict[str, set] = {}
    for (_, x), fx in cn.items():
        ls = assign.setdefault(x, set())
        for key in ("gets value from", "decided by", "reset by", "clocked by"):
            for c in (fx.get("counterparts") or {}).get(key, []) or []:
                if isinstance(c, dict):
                    ls.update(int(l) for l in (c.get("lines") or []) if isinstance(l, int) or (isinstance(l, str) and l.isdigit()))

    def lst(v):
        return v if isinstance(v, list) else ([v] if isinstance(v, str) else [])
    out = {}
    for c in concepts or []:
        if not isinstance(c, dict):
            continue
        cid = c.get("Concept ID", c.get("id"))
        if not cid:
            continue
        ports = [p for p in lst(c.get("Enters Through", c.get("enters through"))) + lst(c.get("Leaves Through", c.get("leaves through"))) if isinstance(p, str)]
        held = {int(l) for l in lst(c.get("Held Lines", c.get("held lines"))) if isinstance(l, int) or (isinstance(l, str) and l.isdigit())}
        out[str(cid)] = sorted({p for p in ports if p in names} | {x for x, ls in assign.items() if ls & held})
    return out


def closed_names(m: str) -> dict[tuple[str, str], dict]:
    """(entity, name) -> closed-set entry, for ports, signals and record fields."""
    cs = json.loads(inputs(m)["closed_set.json"])
    out = {}
    for e in cs["entity list"]:
        for x in e["port list"] + e["signal list"]:
            out[(e["entity name"], x.get("port") or x.get("signal"))] = x
            for f in x.get("fields", []):
                out[(e["entity name"], f["field"])] = f
    return out


def rtl_lines(m: str) -> set[int]:
    return {int(mm.group(1)) for l in inputs(m)["rtl.txt"].splitlines() if (mm := re.match(r"\s*(\d+) \|", l))}


def diagram_names(m: str) -> dict:
    """Per unit: its input ports, output ports and block names as the ARROWS lines write them."""
    units, cur = {}, None
    for line in inputs(m)["diagram.txt"].splitlines():
        if line.startswith("UNIT "):
            cur = units.setdefault(line[5:].strip(), {"inputs": set(), "outputs": set(), "blocks": set()})
        elif cur is not None and line.strip().startswith(("INPUTS:", "OUTPUTS:")):
            k = "inputs" if line.strip().startswith("INPUTS:") else "outputs"
            cur[k] |= {x.strip() for x in line.split(":", 1)[1].split(",") if x.strip()}
        elif cur is not None and (mm := re.match(r"\s+\[(?:process|generate|logic|inst)\] (.+?)(?: \([\w]+, (?:this file|another IP)\))?: ", line)):
            cur["blocks"].add(mm.group(1))
    return units


def unit_entities(m: str) -> dict[str, set[str]]:
    """Per unit: the entities whose elements its analysis may report (the unit, and the entities of its instances of
    this file, recursively); precomputed in kit_data."""
    return K.unit_entities(m)


# ------------------------------------------------------------------------------------------------ checks ---
def _lines_problem(where: str, xs, lines: set[int]) -> list[str]:
    if not isinstance(xs, list):
        return [f"{where}: not a list of line numbers ({xs!r})"]
    bad_type = [x for x in xs if not isinstance(x, int) or isinstance(x, bool)]
    bad = [x for x in xs if isinstance(x, int) and not isinstance(x, bool) and x not in lines]
    return ([f"{where}: line entries that are not numbers {bad_type}"] if bad_type else []) + \
           ([f"{where}: lines not in the RTL {bad}"] if bad else [])


def phase1_concepts(reply) -> list[dict] | None:
    """Phase 1's "conceptual assets" if the reply has that key as a list of objects, else None (a schema failure)."""
    if not isinstance(reply, dict):
        return None
    ca = reply.get("conceptual assets")
    if not isinstance(ca, list) or not all(isinstance(c, dict) for c in ca):
        return None
    return ca


def check_phase1(m: str, obj) -> list[str]:
    """Schema and fact checks of a Phase 1 reply. Problems are reported, never repaired."""
    ca = phase1_concepts(obj)
    if ca is None:
        return ["schema: no 'conceptual assets' list of objects"]
    probs = []
    units, names, lines = diagram_names(m), closed_names(m), rtl_lines(m)
    ids = [_key(c.get("id")) for c in ca]
    dup = sorted(k for k, v in Counter(ids).items() if v > 1)
    if dup:
        probs.append(f"duplicate ids {dup}")
    for c in ca:
        cid, u = _key(c.get("id", "?")), c.get("unit")
        if not isinstance(u, str) or u not in units:
            probs.append(f"{cid}: unit {u!r} is not a UNIT of the diagram")
            u = None
        for k, side in (("enters through", "inputs"), ("leaves through", "outputs")):
            if not isinstance(c.get(k, []), (list, str)):
                probs.append(f"{cid}: {k} is neither a list nor a name ({c.get(k)!r})")
            for p in as_list(c.get(k)):
                if not isinstance(p, str):
                    probs.append(f"{cid}: {k} entry {p!r} is not a name")
                    continue
                if u is None or p.split(".")[0] not in units[u][side] or (u, p) not in names:
                    probs.append(f"{cid}: {k} {p!r} is not an {side[:-1]} port (or port field) of unit {u!r}")
        for k in ("entry lines", "held lines", "exit lines"):
            probs += _lines_problem(f"{cid}: {k}", c.get(k, []), lines)
        letters = c.get("objectives")
        if not isinstance(letters, list) or not letters or not set(map(_key, letters)) <= {"C", "I", "A"}:
            probs.append(f"{cid}: objectives {letters!r}")
        rub = c.get("rubric")
        if not isinstance(rub, dict):
            probs.append(f"{cid}: rubric is not an object")
        elif not any(rub.get(q) == "yes" for q in QUESTIONS):
            probs.append(f"{cid}: kept with no rubric 'yes'")
    if not isinstance(obj.get("considered, not kept", []), list):
        probs.append("schema: 'considered, not kept' is not a list")
    return probs


def phase2_lists(reply) -> tuple[list[dict], list[dict]] | None:
    if not isinstance(reply, dict):
        return None
    pts, sas = reply.get("points"), reply.get("structural assets")
    if not isinstance(pts, list) or not isinstance(sas, list):
        return None
    return [p for p in pts if isinstance(p, dict)], [a for a in sas if isinstance(a, dict)]


def check_phase2(m: str, obj, concepts: list[dict]) -> list[str]:
    lists = phase2_lists(obj)
    if lists is None:
        return ["schema: no 'points' and 'structural assets' lists"]
    pts, sas = lists
    probs = []
    if len(pts) != len(obj["points"]) or len(sas) != len(obj["structural assets"]):
        probs.append("schema: list items that are not objects")
    ids = {_key(c.get("id")): c for c in concepts}
    units, names, lines, ents = diagram_names(m), closed_names(m), rtl_lines(m), unit_entities(m)
    no_unit = {"inputs": set(), "outputs": set(), "blocks": set()}
    seen_points, seen_assets = Counter(), {}
    for p in pts:
        cid, name = _key(p.get("concept id")), p.get("point")
        if cid not in ids:
            probs.append(f"point {name!r}: unknown concept id {cid!r}")
            continue
        seen_points[cid] += 1
        cu = ids[cid].get("unit")
        u = units.get(cu, no_unit) if isinstance(cu, str) else no_unit
        if not isinstance(name, str) or (name not in u["blocks"] and name not in u["outputs"]):
            probs.append(f"{cid}: point {name!r} is not a block or output-port assignment of unit {ids[cid].get('unit')!r}")
        probs += _lines_problem(f"{cid}: point {name!r}", p.get("lines", []), lines)
    for a in sas:
        cid, el, ent = _key(a.get("concept id")), a.get("element"), a.get("entity")
        if cid not in ids:
            probs.append(f"asset {el!r}: unknown concept id {cid!r}")
        if not isinstance(a.get("same role", []), list):
            probs.append(f"{cid}: {el!r} 'same role' is not a list")
        for n in [el] + as_list(a.get("same role")):
            if not isinstance(n, str) or not isinstance(ent, str) or (ent, n) not in names:
                probs.append(f"{cid}: {n!r} is not a closed-set element of entity {ent!r}")
            elif cid in ids and isinstance(ids[cid].get("unit"), str) and ent not in ents.get(ids[cid]["unit"], {ent}):
                probs.append(f"{cid}: {n!r} belongs to entity {ent!r}, outside unit {ids[cid].get('unit')!r}")
            else:
                seen_assets.setdefault(cid, set()).add((ent, n))
        label = a.get("label")
        if label not in ("primary", "secondary"):
            probs.append(f"{cid}: {el!r} label {label!r}")
        links = a.get("links", [])
        if label == "secondary" and not (isinstance(links, list) and links):
            probs.append(f"{cid}: secondary {el!r} has no links")
        if label == "primary" and links:
            probs.append(f"{cid}: primary {el!r} has links")
        letters = a.get("objectives", [])
        if not isinstance(letters, list) or not set(map(_key, letters)) <= {"C", "I", "A"}:
            probs.append(f"{cid}: {el!r} objectives {letters!r}")
        elif label == "primary" and cid in ids and not set(letters) <= set(map(_key, as_list(ids[cid].get("objectives")))):
            probs.append(f"{cid}: primary {el!r} objectives {letters} not all listed by Phase 1 for the concept")
        probs += _lines_problem(f"{cid}: asset {el!r}", a.get("lines", []), lines)
    for cid, c in ids.items():
        if not seen_points[cid]:
            probs.append(f"{cid}: no point listed")
        for p in as_list(c.get("enters through")) + as_list(c.get("leaves through")):
            if isinstance(p, str) and not any(e == c.get("unit") and (n == p or n.startswith(p + ".") or p.startswith(n + "."))
                                              for e, n in seen_assets.get(cid, set())):
                probs.append(f"{cid}: anchor port {p!r} is not among its structural assets")
    return probs


# ------------------------------------------------------------------------------------------------ reply formats ---
# The reply format of two_phase_v5f and later (2026-10-13): keys a person can read, each key name once per format, each
# object starting with its own identifier, Phase 2 rows grouped under their conceptual asset ("Concept Walks").
# A version uses it when its phase file's OUTPUT section shows the new top-level list (new_format). Such a reply is
# checked against the format (problems start with "format:" or "consistency:"; reported, never repaired) and then
# mapped to v5's key names, which check_phase1/2, to_assets, readings and the analysis scripts read. The stored "raw"
# keeps the reply as written; Phase 2 receives Phase 1's "Conceptual Assets" list as written.
F1_TOP = ("IP", "Conceptual Assets", "Not Kept", "Notes")
F1_CONCEPT = ("Concept ID", "Concept Name", "Unit", "Information", "Rubric", "Rubric Reason", "Objectives At Risk",
              "Attack", "Enters Through", "Leaves Through", "Entry Lines", "Held Lines", "Exit Lines")
F_ANSWERS = ("Confidentiality", "Integrity", "Availability", "Undermined Expected Behavior")   # in QUESTIONS order
F1_NOT_KEPT = ("Candidate Name", "Candidate Unit", "Merged Into", "Why Not Kept")
F2_TOP = ("IP", "Concept Walks", "Notes")
F2_WALK = ("Concept ID", "Points", "Assets", "Not Reported", "No Primary Reason")
F2_POINT = ("Point", "Reached By", "Point Answers", "Answer Lines", "Answer Reason")
F2_ASSET = ("Asset RTL", "Entity", "Label", "Same Role", "Found At", "Security Objectives", "Secondary To",
            "Functionality", "Justification", "Asset Lines")
F2_LINK = ("Primary RTL", "Primary Entity", "Direction")
F2_NOT_REPORTED = ("Element RTL", "Element Entity", "Why Not Reported")
# new key -> v5 key (only keys the reply has are copied, so a missing key stays missing for the v5 checks)
F1_CONCEPT_V5 = (("Concept ID", "id"), ("Unit", "unit"), ("Concept Name", "concept"), ("Information", "information"),
                 ("Rubric Reason", "rubric reason"), ("Objectives At Risk", "objectives"), ("Attack", "attack"),
                 ("Enters Through", "enters through"), ("Leaves Through", "leaves through"), ("Entry Lines", "entry lines"),
                 ("Held Lines", "held lines"), ("Exit Lines", "exit lines"))
F2_POINT_V5 = (("Point", "point"), ("Reached By", "reached by"), ("Answer Lines", "lines"), ("Answer Reason", "reason"))
F2_ASSET_V5 = (("Asset RTL", "element"), ("Entity", "entity"), ("Same Role", "same role"), ("Found At", "points"),
               ("Label", "label"), ("Security Objectives", "objectives"), ("Asset Lines", "lines"))
F2_LINK_V5 = (("Primary RTL", "primary"), ("Primary Entity", "entity"), ("Direction", "direction"))


def new_format(version: str, phase: int) -> bool:
    """True when the version's phase file asks for the 2026-10-13 reply format."""
    t = (LAB / "prompts" / version / f"phase{phase}.md").read_text(encoding="utf-8")
    i = t.rfind("\nOUTPUT")
    return i >= 0 and f'"{(F1_TOP if phase == 1 else F2_TOP)[1]}": [' in t[i:]


def _rename(x: dict, pairs) -> dict:
    return {old: x[new] for new, old in pairs if new in x}


def _shape(where: str, obj, keys) -> list[str]:
    """The format rule: every key shown, in the order shown, and no other key."""
    if not isinstance(obj, dict):
        return [f"format: {where} is not an object"]
    miss = [k for k in keys if k not in obj]
    extra = [k for k in obj if k not in keys]
    probs = ([f"format: {where} lacks {miss}"] if miss else []) + \
            ([f"format: {where} has keys the format does not show {extra}"] if extra else [])
    if [k for k in obj if k in keys] != [k for k in keys if k in obj]:
        probs.append(f"format: {where} keys out of order")
    return probs


def _duplicate_keys(text: str) -> list[str]:
    """Keys written twice in one object; json.loads keeps only the last, so they are found on the raw text."""
    dups = Counter()

    def hook(pairs):
        c = Counter(k for k, _ in pairs)
        dups.update({k: n - 1 for k, n in c.items() if n > 1})
        return dict(pairs)
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    try:
        json.loads(t[t.find("{"): t.rfind("}") + 1], object_pairs_hook=hook)
    except ValueError:
        return []
    return [f"format: key {k!r} written twice in one object ({n} time(s) more)" for k, n in sorted(dups.items())]


def _list(where: str, obj: dict, key: str) -> tuple[list, list[str]]:
    v = obj.get(key)
    if key in obj and not isinstance(v, list):
        return [], [f"format: {where} {key} is not a list"]
    return (v if isinstance(v, list) else []), []


def from_format_phase1(obj, text: str = "") -> tuple[object, list[str]]:
    """A Phase 1 reply in the 2026-10-13 format -> (the reply in v5 keys, format problems). Without a "Conceptual
    Assets" list the mapped reply has no "conceptual assets", so it stays a schema failure as before."""
    probs = _duplicate_keys(text) + _shape("reply", obj, F1_TOP)
    if not isinstance(obj, dict):
        return obj, probs
    out = _rename(obj, (("IP", "module name"), ("Notes", "notes")))
    ca = obj.get("Conceptual Assets")
    kept = set()
    if isinstance(ca, list):
        out["conceptual assets"] = []
        for i, c in enumerate(ca):
            where = f"conceptual asset {c.get('Concept ID') if isinstance(c, dict) and c.get('Concept ID') else i + 1}"
            probs += _shape(where, c, F1_CONCEPT)
            if not isinstance(c, dict):
                out["conceptual assets"].append(c)          # phase1_concepts then reports the schema failure
                continue
            kept.add(c.get("Concept ID"))
            v5 = _rename(c, F1_CONCEPT_V5)
            if "Rubric" in c:
                rub = c["Rubric"]
                probs += _shape(f"{where} Rubric", rub, F_ANSWERS)
                v5["rubric"] = {q: rub[Q] for q, Q in zip(QUESTIONS, F_ANSWERS) if Q in rub} if isinstance(rub, dict) else rub
            out["conceptual assets"].append(v5)
    nk, p = _list("reply", obj, "Not Kept")
    probs += p
    if "Not Kept" in obj:
        out["considered, not kept"] = []
        for i, x in enumerate(nk):
            where = f"not-kept entry {x.get('Candidate Name')!r}" if isinstance(x, dict) and x.get("Candidate Name") else f"not-kept entry {i + 1}"
            probs += _shape(where, x, F1_NOT_KEPT)
            if not isinstance(x, dict):
                out["considered, not kept"].append(x)
                continue
            mi, why = x.get("Merged Into"), x.get("Why Not Kept")
            if mi and mi not in kept:
                probs.append(f"consistency: {where}: Merged Into {mi!r} is not a kept Concept ID")
            if mi and why:
                probs.append(f"consistency: {where}: both Merged Into and Why Not Kept are filled")
            if not mi and not why:
                probs.append(f"consistency: {where}: neither Merged Into nor Why Not Kept is filled")
            v5 = _rename(x, (("Candidate Unit", "unit"), ("Candidate Name", "concept")))
            v5["reason"] = f"merged into {mi}" if mi else why
            v5["merged into"] = mi
            out["considered, not kept"].append(v5)
    return out, probs


def from_format_phase2(obj, text: str = "", concept_ids=None) -> tuple[object, list[str]]:
    """A Phase 2 reply in the 2026-10-13 format -> (the reply in v5 keys, format problems). Each row takes its walk's
    "Concept ID" as "concept id"; an asset's "reason" is its Functionality and Justification joined (both are also kept
    as "functionality" and "justification"); "Not Reported" and "No Primary Reason" are kept as "not reported" and
    "no primary reason". concept_ids: Phase 1's ids, in order, to check that the walks cover them. Without a "Concept
    Walks" list the mapped reply has no "points" and "structural assets", so it stays a schema failure as before."""
    probs = _duplicate_keys(text) + _shape("reply", obj, F2_TOP)
    if not isinstance(obj, dict):
        return obj, probs
    out = _rename(obj, (("IP", "module name"), ("Notes", "notes")))
    walks = obj.get("Concept Walks")
    if not isinstance(walks, list):
        if "Concept Walks" in obj:
            probs.append("format: reply Concept Walks is not a list")
        return out, probs
    pts, sas, nrep, noprim, seen = [], [], [], {}, []
    for i, w in enumerate(walks):
        where = f"walk {w.get('Concept ID')}" if isinstance(w, dict) and w.get("Concept ID") else f"walk {i + 1}"
        probs += _shape(where, w, F2_WALK)
        if not isinstance(w, dict):
            continue
        cid = w.get("Concept ID")
        seen.append(cid)
        wp, p = _list(where, w, "Points")
        probs += p
        for j, x in enumerate(wp):
            pw = f"{where} point {x.get('Point')!r}" if isinstance(x, dict) and x.get("Point") else f"{where} point {j + 1}"
            probs += _shape(pw, x, F2_POINT)
            if not isinstance(x, dict):
                pts.append(x)                                 # check_phase2 counts items that are not objects
                continue
            v5 = {"concept id": cid, **_rename(x, F2_POINT_V5)}
            ans = x.get("Point Answers")
            if "Point Answers" in x:
                probs += _shape(f"{pw} Point Answers", ans, F_ANSWERS)
                if isinstance(ans, dict):
                    v5.update({q: ans[Q] for q, Q in zip(QUESTIONS, F_ANSWERS) if Q in ans})
            pts.append(v5)
        wa, p = _list(where, w, "Assets")
        probs += p
        names_here = set()
        for j, x in enumerate(wa):
            aw = f"{where} asset {x.get('Asset RTL')!r}" if isinstance(x, dict) and x.get("Asset RTL") else f"{where} asset {j + 1}"
            conf0 = x.pop("Confidence", None) if isinstance(x, dict) else None
            probs += _shape(aw, x, F2_ASSET)
            if conf0 is not None:
                x["Confidence"] = conf0
            if not isinstance(x, dict):
                sas.append(x)
                continue
            names_here.add((x.get("Entity"), x.get("Asset RTL")))
            conf = x.pop("Confidence", None)                  # optional key (two_phase_v9n_conf, 2026-10-18); absent elsewhere
            v5 = {"concept id": cid, **_rename(x, F2_ASSET_V5)}
            if conf is not None:
                v5["confidence"] = conf
            if "Secondary To" in x:
                links = x["Secondary To"]
                if isinstance(links, list):
                    for k, l in enumerate(links):
                        probs += _shape(f"{aw} Secondary To entry {k + 1}", l, F2_LINK)
                    v5["links"] = [_rename(l, F2_LINK_V5) if isinstance(l, dict) else l for l in links]
                else:
                    v5["links"] = links
            fn, js = x.get("Functionality"), x.get("Justification")
            if "Functionality" in x or "Justification" in x:
                v5["reason"] = " ".join(s for s in (fn, js) if isinstance(s, str) and s.strip())
                v5["functionality"], v5["justification"] = fn, js
            sas.append(v5)
        wn, p = _list(where, w, "Not Reported")
        probs += p
        for j, x in enumerate(wn):
            nw = f"{where} not-reported entry {x.get('Element RTL')!r}" if isinstance(x, dict) and x.get("Element RTL") else f"{where} not-reported entry {j + 1}"
            probs += _shape(nw, x, F2_NOT_REPORTED)
            if isinstance(x, dict):
                if (x.get("Element Entity"), x.get("Element RTL")) in names_here:
                    probs.append(f"consistency: {nw} is also under Assets in the same walk")
                nrep.append({"concept id": cid, **_rename(x, (("Element RTL", "element"), ("Element Entity", "entity"),
                                                              ("Why Not Reported", "reason")))})
        npr = w.get("No Primary Reason")
        has_primary = any(isinstance(x, dict) and x.get("Label") == "primary" for x in wa)
        if has_primary and isinstance(npr, str) and npr.strip():
            probs.append(f"consistency: {where} has a primary and a No Primary Reason")
        if not has_primary and not (isinstance(npr, str) and npr.strip()):
            probs.append(f"consistency: {where} has no primary and an empty No Primary Reason")
        if isinstance(npr, str) and npr.strip():
            noprim[_key(cid)] = npr
    if concept_ids is not None:
        want, got = [_key(c) for c in concept_ids], [_key(c) for c in seen]
        miss = [c for c in want if c not in got]
        extra = [c for c in got if c not in want]
        dup = sorted(c for c, n in Counter(got).items() if n > 1)
        if miss:
            probs.append(f"format: Concept Walks miss {miss}")
        if extra:
            probs.append(f"format: Concept Walks have ids not in CONCEPTS {extra}")
        if dup:
            probs.append(f"format: Concept Walks repeat {dup}")
        if not (miss or extra or dup) and got != want:
            probs.append("format: Concept Walks are not in the order CONCEPTS gives")
    out["points"], out["structural assets"] = pts, sas
    out["not reported"], out["no primary reason"] = nrep, noprim
    return out, probs


def concepts_as_written(rec: dict, version: str):
    """The concept list Phase 2 receives: Phase 1's list as the model wrote it (for the 2026-10-13 format, its
    "Conceptual Assets" re-read from the stored raw reply; for earlier versions, the stored "conceptual assets")."""
    if new_format(version, 1):
        return K.parse_json(rec["raw"]).get("Conceptual Assets")
    return phase1_concepts(rec.get("reply"))


# ------------------------------------------------------------------------------------------------ converter ---
def to_assets(m: str, phase2: dict, concepts: list[dict]) -> dict:
    """Phase 2 -> scorer format. Primary rows only; "same role" names expanded to their own rows; one row per
    (entity, element), merging the concepts it is primary for. Security Objective: Confidentiality if any of its
    objectives is C, else Integrity, else Availability (the serialization rule of the final prompt); a primary with no
    objectives takes its concepts' objectives. Names outside the closed set are kept (the scorer counts them) and listed
    in "_invalid"; rows the reply gave in a form that cannot be read are counted in "_skipped"."""
    obj_of = {_key(c.get("id")): {x for x in as_list(c.get("objectives")) if isinstance(x, str) and x in WORD} for c in concepts}
    names = closed_names(m)
    rows: dict[tuple[str, str], dict] = {}
    skipped = 0
    lists = phase2_lists(phase2) or ([], [])
    for a in lists[1]:
        if a.get("label") != "primary":
            continue
        ent, cid = a.get("entity", ""), _key(a.get("concept id"))
        if not isinstance(ent, str):
            skipped += 1
            continue
        letters = {x for x in as_list(a.get("objectives")) if isinstance(x, str) and x in WORD} or obj_of.get(cid, set())
        for n in [a.get("element")] + as_list(a.get("same role")):
            if not isinstance(n, str) or not n:
                skipped += 1
                continue
            r = rows.setdefault((ent, n), {"letters": set(), "Concepts": [], "Points": []})
            if a.get("confidence") is not None:
                r["Confidence"] = "sure" if (r.get("Confidence") == "sure" or a.get("confidence") == "sure") else str(a.get("confidence"))
            r["letters"] |= letters
            if cid not in r["Concepts"]:
                r["Concepts"].append(cid)
            r["Points"] += [p for p in as_list(a.get("points")) if isinstance(p, str) and p not in r["Points"]]
    out = []
    for (ent, n), r in rows.items():
        letter = next((x for x in ("C", "I", "A") if x in r["letters"]), "")
        row = {"Asset RTL": n, "Entity": ent, "Security Objective": WORD.get(letter, ""),
               "Objectives": sorted(r["letters"]), "Concepts": r["Concepts"], "Points": r["Points"]}
        if "Confidence" in r:
            row["Confidence"] = r["Confidence"]
        out.append(row)
    invalid = sorted(f"{e}:{n}" for (e, n) in rows if (e, n) not in names)
    return {"IP": m, "Assets": out, "_invalid": invalid, "_skipped": skipped}


# ------------------------------------------------------------------------------------------------ executors ---
def openai(model: str = "gpt-5.4", effort: str = "high", out: Path | None = None, max_tokens: int = 128000,
           poll: int = 15, timeout: int = 4 * 3600, retry_incomplete: bool = False, rate_retries: int = 10):
    """f(system, user) -> (text, usage) on the OpenAI Responses API in background mode (needs API.env). out = the run
    folder (run_dir(...)); pending ids, failed calls and partial texts go there.

    Each request is created once, unless the reply to the create request itself is lost: its id is saved in
    out/_pending/<key>.json before polling, and it stays there until _ask has written the reply to disk (f.done), so a
    re-run after a crash, an interrupt or a kernel restart collects the same response instead of paying again. Create
    is never retried by the client; polling is. The one exception: a create refused with HTTP 429 for a rate limit (the
    request was not accepted, so nothing is created or billed) is sent again after Retry-After or a back-off of 15, 30,
    60, ... up to 300 s, at most rate_retries times; a 429 for insufficient quota is not retried. A response that ends
    in any status other than 'completed' is logged in out/_failed_calls.jsonl with its usage and reason (its partial
    text in out/_failed/<key>.txt) and raises. A request that was cut short ('incomplete') with the same max_tokens is
    not sent again unless retry_incomplete=True. A stop (the flag of the run this thread works for, _stop_event(); set
    when run() or run_many() is interrupted) ends a rate-limit wait or a poll wait at once: nothing is created after a
    stop, and a request already created keeps its pending id and is collected on the next run."""
    import os
    import time
    import openai as _oa
    from openai import OpenAI
    RateLimitError = getattr(_oa, "RateLimitError", None) or type("RateLimitError", (Exception,), {})
    if out is None:
        raise ValueError("openai(): give the run folder as out=")
    out = Path(out)
    env = next((p for p in (ROOT / "API.env", ROOT.parents[2] / "API.env") if p.exists()), ROOT / "API.env")
    if env.exists() and not os.environ.get("OPENAI_API_KEY"):
        for l in env.read_text(encoding="utf-8").splitlines():
            if l.strip().startswith("OPENAI_API_KEY"):
                os.environ["OPENAI_API_KEY"] = l.split("=", 1)[1].strip().strip('"')
    base = OpenAI()
    creator = base.with_options(timeout=600, max_retries=0)
    poller = base.with_options(timeout=120, max_retries=5)
    pend, failed_log, partial = out / "_pending", out / "_failed_calls.jsonl", out / "_failed"
    pend.mkdir(parents=True, exist_ok=True)

    def usage_of(r) -> dict:
        u = getattr(r, "usage", None)
        if not u:
            return {}
        d = getattr(u, "output_tokens_details", None)
        c = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", None)
        return {"in": u.input_tokens, "out": u.output_tokens, "reasoning": getattr(d, "reasoning_tokens", None),
                "cached": c}

    def cut_before(key) -> bool:
        if retry_incomplete or not failed_log.exists():
            return False
        for l in failed_log.read_text(encoding="utf-8").splitlines():
            x = json.loads(l) if l.strip() else {}
            if x.get("key") == key and x.get("status") == "incomplete" and x.get("max_tokens") == max_tokens:
                return True
        return False

    def f(system, user):
        key = sha12(system + "\n\n" + user)
        pf = pend / f"{key}.json"
        stop = _stop_event()                        # this run's flag; every wait below ends as soon as it is set
        if pf.exists():
            p = json.loads(pf.read_text(encoding="utf-8"))
            if (p.get("model"), p.get("effort")) != (model, effort):
                raise RuntimeError(f"{pf} belongs to {p.get('model')}/{p.get('effort')}, not {model}/{effort}")
            r = poller.responses.retrieve(p["id"])
        else:
            if stop.is_set():
                raise RuntimeError("stopped before sending")
            if cut_before(key):
                raise RuntimeError(f"request {key} was cut short before with max_tokens={max_tokens}; not sent again "
                                   "(use retry_incomplete=True or a larger max_tokens)")
            for attempt in range(rate_retries + 1):
                try:
                    r = creator.responses.create(model=model, instructions=system, input=user, reasoning={"effort": effort},
                                                 max_output_tokens=max_tokens, text={"format": {"type": "json_object"}},
                                                 background=True, metadata={"lab_key": key})
                    break
                except RateLimitError as e:
                    body = getattr(e, "body", None)
                    if isinstance(body, dict) and isinstance(body.get("error"), dict):
                        body = body["error"]
                    code = getattr(e, "code", None) or (body.get("code") if isinstance(body, dict) else None)
                    if code == "insufficient_quota" or attempt == rate_retries or stop.is_set():
                        raise
                    hdr = getattr(getattr(e, "response", None), "headers", None) or {}
                    try:
                        wait_s = float(hdr.get("retry-after"))
                    except (TypeError, ValueError):
                        wait_s = min(300.0, 15.0 * 2 ** attempt)
                    if stop.wait(wait_s):               # a stop ends the wait at once; the refused request was never created
                        raise RuntimeError("stopped before sending (during a rate-limit wait; nothing was created)")
            pf.write_text(json.dumps({"id": r.id, "model": model, "effort": effort, "created": time.time()}),
                          encoding="utf-8")
        t0 = time.time()
        while getattr(r, "status", None) in ("queued", "in_progress"):
            if stop.is_set():
                raise RuntimeError(f"stopped while waiting; response {r.id} is kept and collected on the next run")
            if time.time() - t0 > timeout:
                raise TimeoutError(f"response {r.id} still {r.status} after {timeout}s; re-run to keep waiting")
            if stop.wait(poll):
                continue                             # stopped during the wait: the check above raises
            r = poller.responses.retrieve(r.id)
        usage = {**usage_of(r), "model": getattr(r, "model", model), "effort": effort, "response id": r.id,
                 "request key": key}
        if r.status != "completed":
            reason = getattr(getattr(r, "incomplete_details", None), "reason", None)
            partial.mkdir(parents=True, exist_ok=True)
            (partial / f"{key}.txt").write_text(getattr(r, "output_text", "") or "", encoding="utf-8")
            with open(failed_log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"key": key, "status": r.status, "reason": reason, "max_tokens": max_tokens,
                                     "usage": usage}) + "\n")
            try:
                pf.unlink(missing_ok=True)
            except OSError:
                pass
            raise RuntimeError(f"reply status {r.status!r} ({reason}); usage {usage}; not stored")
        return r.output_text, usage

    def done(key):
        try:
            (pend / f"{key}.json").unlink(missing_ok=True)
        except OSError:
            pass
    f.done = done
    return f


# ------------------------------------------------------------------------------------------------ running ---
def run_dir(version: str, model: str, rep: int = 0, effort: str = "high") -> Path:
    return LAB / "runs" / f"{version}__{INPUT_VERSION}" / f"{model}__{effort}" / f"r{rep}"


def _meta(version: str, model: str, effort: str, executor: str) -> dict:
    man = INPUTS / "manifest.json"
    d = LAB / "prompts" / version
    return {"prompt version": version, "input version": INPUT_VERSION, "model": model, "effort": effort,
            "executor": executor, "system sha phase 1": sha12(C.system(version, 1)),
            "system sha phase 2": sha12(C.system(version, 2)),
            "user template sha phase 1": sha12((d / "phase1_user.md").read_text(encoding="utf-8")),
            "user template sha phase 2": sha12((d / "phase2_user.md").read_text(encoding="utf-8")),
            "inputs manifest sha": sha12(man.read_text(encoding="utf-8")) if man.exists() else None}


GUARD = ("prompt version", "input version", "model", "effort", "executor", "system sha phase 1", "system sha phase 2",
         "user template sha phase 1", "user template sha phase 2", "inputs manifest sha")


def _ask(call, system: str, user: str, path: Path, check, meta: dict, adapt=None) -> dict:
    """One call, stored once. A stored record is returned only for the same system and user message. The reply is
    written to disk as soon as it arrives; parsing and checks run after, and a check that crashes is recorded as a
    problem, so a paid reply is never lost. adapt(parsed, raw text) -> (reply in v5 keys, format problems), for a
    version whose reply format is the 2026-10-13 one (from_format_phase1/2); "reply" then holds the mapped reply and
    "raw" the reply as written."""
    ss, us = sha12(system), sha12(user)
    if path.exists():
        rec = json.loads(path.read_text(encoding="utf-8"))
        if (rec.get("system sha"), rec.get("user sha")) != (ss, us):
            raise RuntimeError(f"{path} was asked with another message (system {rec.get('system sha')} vs {ss}, user "
                               f"{rec.get('user sha')} vs {us}); move it, the later phases and assets/ away to ask again")
        if not (rec.get("check crashed") or rec.get("problems") == ["not checked yet"]
                or any(str(p).startswith("unparseable reply") for p in rec.get("problems", []))):
            return rec
        rec.pop("check crashed", None)                 # a stored paid reply is re-parsed and re-checked, never re-asked
    else:
        if _stop_event().is_set():
            raise RuntimeError("stopped before sending")
        key = sha12(system + "\n\n" + user)
        path.parent.parent.mkdir(parents=True, exist_ok=True)
        with open(path.parent.parent / "_keys.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": key, "module": meta.get("module"), "phase": meta.get("phase")}) + "\n")
        text, usage = call(system, user)
        rec = {**meta, "system sha": ss, "user sha": us, "usage": usage, "raw": text, "reply": None,
               "problems": ["not checked yet"]}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        if hasattr(call, "done"):
            call.done(key)
    text = rec["raw"]
    try:
        rec["reply"] = K.parse_json(text)
    except ValueError as e:                      # json.JSONDecodeError is a ValueError
        rec["problems"] = [f"unparseable reply: {e}"]
    else:
        try:
            pre = []
            if adapt is not None:
                rec["reply"], pre = adapt(rec["reply"], text)
                rec["reply keys"] = "the 2026-10-13 format as written in 'raw'; 'reply' holds it in v5 keys"
            rec["problems"] = pre + check(rec["reply"])
        except Exception as e:  # noqa: BLE001 -- recorded; the reply is kept
            rec["problems"] = [f"check crashed: {type(e).__name__}: {e}"]
            rec["check crashed"] = True
    path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    return rec


def stopped(rec: dict, phase: int):
    """True when a stored record stops the module: no readable reply in the phase's schema, or a check that crashed or
    never ran. run_module and readings use the same rule."""
    if rec.get("check crashed") or rec.get("problems") == ["not checked yet"]:
        return True
    return (phase1_concepts(rec.get("reply")) if phase == 1 else phase2_lists(rec.get("reply"))) is None


def run_module(version: str, m: str, call, out: Path) -> dict:
    """Phase 1 then Phase 2 for one module, then the converter. Returns a status row. A Phase 1 reply without a
    readable concept list stops the module (no Phase 2, no assets file); an explicitly empty list gives an empty
    assets file. An earlier assets file is removed first, so a module that stops leaves none to be scored."""
    meta = {"module": m, "prompt version": version, "input version": INPUT_VERSION}
    (out / "assets" / f"{m}.json").unlink(missing_ok=True)
    r1 = _ask(call, C.system(version, 1), user_message(version, 1, m), out / "phase1" / f"{m}.json",
              lambda o: check_phase1(m, o), {**meta, "phase": 1},
              adapt=from_format_phase1 if new_format(version, 1) else None)
    concepts = phase1_concepts(r1.get("reply"))       # v5 keys, for the checks and the converter
    if stopped(r1, 1):
        return {"module": m, "status": "phase 1 schema failure", "problems": r1["problems"][:5]}
    if concepts:
        ids = [c.get("id") for c in concepts]
        r2 = _ask(call, C.system(version, 2), user_message(version, 2, m, concepts_as_written(r1, version)),
                  out / "phase2" / f"{m}.json", lambda o: check_phase2(m, o, concepts), {**meta, "phase": 2},
                  adapt=(lambda o, t: from_format_phase2(o, t, ids)) if new_format(version, 2) else None)
        if stopped(r2, 2):
            return {"module": m, "status": "phase 2 schema failure", "problems": r2["problems"][:5]}
        phase2 = r2["reply"]
    else:
        r2, phase2 = {"problems": [], "usage": None}, {"points": [], "structural assets": [], "notes": []}
    try:
        a = to_assets(m, phase2, concepts)
    except Exception as e:  # noqa: BLE001
        return {"module": m, "status": f"converter failed: {type(e).__name__}: {e}"}
    (out / "assets").mkdir(parents=True, exist_ok=True)
    (out / "assets" / f"{m}.json").write_text(json.dumps(a, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"module": m, "status": "done", "concepts": len(concepts), "primary rows": len(a["Assets"]),
            "invalid names": len(a["_invalid"]), "problems phase 1": len(r1["problems"]),
            "problems phase 2": len(r2["problems"]), "usage": [r1.get("usage"), r2.get("usage")]}


def _prepare(version: str, model: str, effort: str, rep: int, executor: str) -> Path:
    """The guard of a run: refuses a version whose prompt check fails, and a run folder that holds another prompt,
    template, input version, model, effort or executor; writes _run_meta.json on first use. Returns the run folder."""
    if not C.check(version, log=lambda *_: None):
        raise RuntimeError(f"prompt {version} fails check_lab_prompt; nothing sent")
    out = run_dir(version, model, rep, effort)
    out.mkdir(parents=True, exist_ok=True)
    meta = _meta(version, model, effort, executor)
    mp = out / "_run_meta.json"
    if mp.exists():
        old = json.loads(mp.read_text(encoding="utf-8"))
        diff = [k for k in GUARD if old.get(k) != meta[k]]
        if diff:
            raise RuntimeError(f"{out} holds another set-up ({', '.join(f'{k}: {old.get(k)} vs {meta[k]}' for k in diff)});"
                               " use a new prompt version or rep")
    else:
        mp.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return out


def _one(version: str, m: str, call, out: Path) -> dict:
    """run_module with its errors turned into a status row, so the other modules go on."""
    try:
        return run_module(version, m, call, out)
    except K.NeedReply as e:
        return {"module": m, "status": f"waiting for reply {e}"}
    except Exception as e:  # noqa: BLE001 -- reported per module; the others go on
        return {"module": m, "status": f"ERROR {type(e).__name__}: {e}"}


def _schema_retry(version: str, m: str, call, out: Path, row: dict) -> dict:
    """The one-retry rule for a reply that fails the format check (the notebook's former cell-8 rule): the failed
    phase file moves to out/_schema_failed/phase<N>/<module>.json, a line goes to its README.txt, and the module runs
    once more. A module whose failed file is already there has had its retry and is left as it is."""
    import shutil
    if "schema failure" not in str(row.get("status")):
        return row
    ph = 1 if "phase 1" in row["status"] else 2
    dest = out / "_schema_failed" / f"phase{ph}"
    if (dest / f"{m}.json").exists():
        return {**row, "status": f"{row['status']} (again after its one retry; left as is)"}
    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(out / f"phase{ph}" / f"{m}.json"), str(dest / f"{m}.json"))
    with open(out / "_schema_failed" / "README.txt", "a", encoding="utf-8") as fh:
        fh.write(f"{m} phase {ph}: the first reply failed the format check; moved here and asked once more.\n")
    again = _one(version, m, call, out)
    return {**again, "retried": True}


def _new_run_flag() -> threading.Event:
    """A fresh stop flag for a run that is about to start (never clear an old one: a stopped run's threads must stay
    stopped). Refuses while workers of an earlier stopped run are still finishing a request: they send nothing new,
    but a re-run could ask again what one of them is about to store as pending."""
    global STOP
    import time
    end = time.monotonic() + 2                       # a worker that just ended its task may need a moment to exit
    for t in _leftover_workers():
        t.join(max(0.0, end - time.monotonic()))
    left = _leftover_workers()
    if left:
        raise RuntimeError(f"{len(left)} worker(s) of an earlier stopped run are still finishing a request (they send "
                           "nothing new); run again in a minute. Do not restart the kernel while they run: a request "
                           "still being created would lose its id and be paid again")
    STOP = threading.Event()
    return STOP


def _stop_pool(stop: threading.Event, pool, futs, log=print) -> None:
    """On an interrupt: set the run's flag (no new call is sent, every rate-limit or poll wait ends, a request already
    created keeps its pending id), cancel the tasks not started, and wait up to STOP_WAIT seconds for the running ones.
    Any still running after that are reported, and the next run refuses to start until they end."""
    from concurrent.futures import wait
    stop.set()
    pool.shutdown(wait=False, cancel_futures=True)
    _, left = wait([f for f in futs if not f.done()], timeout=STOP_WAIT)
    if left:
        log(f"stopped; {len(left)} worker(s) still finishing a request after {STOP_WAIT}s. They send nothing new; the "
            "next run refuses to start until they end. Do not restart the kernel while they run: a request still being "
            "created would lose its id and be paid again")


def run_many(jobs, modules, make_call, model: str, effort: str = "high", executor: str = "openai",
             workers: int | None = None, schema_retry: bool = True, log=print) -> dict:
    """Several runs in ONE worker pool, so they run at the same time instead of one after another.
    jobs: [(version, rep), ...] (for example three reps of one version, or the reps of two versions). Each job keeps its
    own run folder and guard exactly as run() does; make_call(out) returns the executor for one run folder (for the
    notebook: lambda out: openai(MODEL, EFFORT, out=out)), because pending ids live in that folder. workers: default
    every (job, module) pair at once; any smaller number queues the rest, largest modules first. schema_retry: the
    one-retry rule of _schema_retry, done inside the worker. Returns {(version, rep): [rows]} in module order.
    A stop (KeyboardInterrupt, at any moment once the pool exists) sets this run's flag: nothing new is sent, every
    wait ends, and the call waits up to STOP_WAIT s for requests in flight before it re-raises. Refuses to start while
    workers of an earlier stopped run are still finishing a request."""
    from concurrent.futures import ThreadPoolExecutor, wait
    modules = list(dict.fromkeys(modules or []))
    jobs = list(dict.fromkeys((v, int(r)) for v, r in jobs))
    if not modules or not jobs:
        raise ValueError("no modules or no jobs given")
    stop = _new_run_flag()                                                       # refuses while a stopped run's workers live
    outs = {j: _prepare(j[0], model, effort, j[1], executor) for j in jobs}      # every guard before any call
    calls = {j: make_call(outs[j]) for j in jobs}
    size = {m: len(user_message(jobs[0][0], 1, m)) for m in modules}             # start the largest inputs first
    tasks = [(j, m) for m in sorted(modules, key=lambda m: -size[m]) for j in jobs]

    def one(j, m):
        threading.current_thread().lab_stop = stop   # this run's flag, kept by the thread even after a reload
        row = _one(j[0], m, calls[j], outs[j])
        return _schema_retry(j[0], m, calls[j], outs[j], row) if schema_retry else row
    pool = ThreadPoolExecutor(max_workers=max(1, workers or len(tasks)))
    futs = {}
    try:
        for j, m in tasks:                           # inside the try: a stop while the pool fills is caught too
            futs[(j, m)] = pool.submit(one, j, m)
        pending = set(futs.values())
        while pending:
            _, pending = wait(pending, timeout=1)
    except BaseException:                            # a stop (KeyboardInterrupt) or any other way out
        _stop_pool(stop, pool, list(futs.values()), log)
        raise
    pool.shutdown(wait=True)
    res = {j: [futs[(j, m)].result() for m in modules] for j in jobs}
    for j, rows in res.items():
        bad = [r for r in rows if r.get("status") != "done"]
        log(f"{j[0]} r{j[1]}: {len(rows) - len(bad)} of {len(rows)} modules done"
            + (f"; not done: {[(r['module'], r['status']) for r in bad]}" if bad else ""))
    return res


def run(version: str, modules, call, model: str, effort: str = "high", rep: int = 0, executor: str = "openai",
        workers: int = 4, log=print) -> list[dict]:
    """Every module through both phases. Refuses a version whose prompt check fails, and a run folder that holds
    another prompt, template, input version, model, effort or executor. A file executor's missing reply is reported
    as 'waiting for reply'. A stop and a stopped run's leftover workers are handled as in run_many()."""
    modules = list(dict.fromkeys(modules or []))
    if not modules:
        raise ValueError("no modules given")
    stop = _new_run_flag()                           # refuses while a stopped run's workers live
    out = _prepare(version, model, effort, rep, executor)
    from concurrent.futures import ThreadPoolExecutor, wait

    def one(m):
        threading.current_thread().lab_stop = stop   # this run's flag, kept by the thread even after a reload
        return _one(version, m, call, out)
    pool = ThreadPoolExecutor(max_workers=max(1, workers))
    futs = []
    try:
        for m in modules:                            # inside the try: a stop while the pool fills is caught too
            futs.append(pool.submit(one, m))
        pending = set(futs)
        while pending:
            _, pending = wait(pending, timeout=1)
    except BaseException:                            # a stop (KeyboardInterrupt) or any other way out
        _stop_pool(stop, pool, list(futs), log)
        raise
    pool.shutdown(wait=True)
    rows = [f.result() for f in futs]
    for r in rows:
        log(r)
    return rows


# ------------------------------------------------------------------------------------------------ readings ---
def readings(version: str, model: str, rep: int = 0, modules=None, effort: str = "high") -> dict:
    """The readings the version's README lists, each with its denominator: P and R of the primary rows (strict scorer)
    and the port-field convention row; Phase 1 kept vs considered per module and the share of concepts with C; Phase 2
    points and primaries per concept over the modules whose Phase 2 parsed; the share of primary rows that are
    top-level port fields; schema failures, problems and usage (stored replies, plus calls that failed)."""
    import eval_assets as ea
    out = run_dir(version, model, rep, effort)
    modules = list(dict.fromkeys(modules or tuning_modules()))
    if not modules:
        raise ValueError("no modules: the reference list was not found")
    missing = [m for m in modules if not (out / "assets" / f"{m}.json").exists()]
    res = {"run": str(out), "modules": len(modules), "missing assets": missing}
    if missing:
        res["caveat"] = f"{len(missing)} of {len(modules)} modules have no assets file; P and R are not computed"
    with at_root():
        refs = ea.load_refs()["gt"]
        if not missing:
            s = ea.score(str(out / "assets"), refs, strict=True, only=set(modules))
            sc = ea.score(K.collapse_port_fields(out / "assets"), refs, strict=True, only=set(modules))
            res["score"] = {k: s[k] for k in ("precision", "recall", "tp", "fp", "fn", "emit", "ref")}
            res["convention row (port fields collapsed)"] = {k: sc[k] for k in ("precision", "recall", "tp", "fp", "emit")}
    per1, schema = {}, {"phase 1": [], "phase 2": []}
    kept = considered = with_c = 0
    p2_mods = p2_concepts = points = prim_pairs = 0
    rows = port_field = 0
    probs, usage = Counter(), Counter()

    def add_usage(u):
        for k, v in (u or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                usage[k] += v
    for m in modules:
        f1, f2 = out / "phase1" / f"{m}.json", out / "phase2" / f"{m}.json"
        ca = None
        if f1.exists():
            r1 = json.loads(f1.read_text(encoding="utf-8"))
            add_usage(r1.get("usage"))
            probs["phase 1"] += len(r1.get("problems", []))
            ca = None if stopped(r1, 1) else phase1_concepts(r1.get("reply"))
            if ca is None:
                schema["phase 1"].append(m)
            else:
                dropped = r1["reply"].get("considered, not kept", [])
                nd = len(dropped) if isinstance(dropped, list) else 0
                nc = sum("C" in as_list(c.get("objectives")) for c in ca)
                per1[m] = {"kept": len(ca), "considered, not kept": nd, "with C": nc}
                kept, considered, with_c = kept + len(ca), considered + nd, with_c + nc
        if f2.exists():
            r2 = json.loads(f2.read_text(encoding="utf-8"))
            add_usage(r2.get("usage"))
            probs["phase 2"] += len(r2.get("problems", []))
            lists = None if stopped(r2, 2) else phase2_lists(r2.get("reply"))
            if lists is None or ca is None:
                schema["phase 2"].append(m)
            else:
                p2_mods += 1
                p2_concepts += len(ca)
                points += len(lists[0])
                prim_pairs += len({(_key(a.get("element")), _key(a.get("concept id"))) for a in lists[1]
                                   if a.get("label") == "primary"})
        fa = out / "assets" / f"{m}.json"
        if fa.exists():
            pf = K.top_level_port_fields(m)
            for x in json.loads(fa.read_text(encoding="utf-8"))["Assets"]:
                rows += 1
                port_field += f"{x['Entity']}:{x['Asset RTL']}" in pf
    failed = failed_calls(out, modules)
    fu = Counter()
    for x in failed:
        for k, v in (x.get("usage") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                fu[k] += v
    res["phase 1"] = {"per module": per1, "kept": kept, "considered, not kept": considered, "concepts with C": with_c,
                      "share of concepts with C": f"{with_c} of {kept}"}
    res["phase 2"] = {"modules with a parsed Phase 2": p2_mods, "their concepts": p2_concepts, "points": points,
                      "points per concept": round(points / p2_concepts, 2) if p2_concepts else None,
                      "(element, concept) primary pairs": prim_pairs,
                      "primaries per concept": round(prim_pairs / p2_concepts, 2) if p2_concepts else None}
    res["assets"] = {"scorer rows (distinct primary elements)": rows,
                     "top-level port fields among them": f"{port_field} of {rows}"}
    res["schema failures"] = schema
    res["problems"] = dict(probs)
    res["usage of stored replies"] = dict(usage)
    res["failed calls"] = {"count": len(failed), "by phase": dict(Counter(x.get("phase") for x in failed)),
                           "statuses": dict(Counter(f"{x.get('status')} ({x.get('reason')})" for x in failed)),
                           "usage": dict(fu)}
    return res


def failed_calls(out: Path, modules=None) -> list[dict]:
    """Entries of out/_failed_calls.jsonl, each with its module and phase (from out/_keys.jsonl), for the given
    modules only."""
    fl, kl = out / "_failed_calls.jsonl", out / "_keys.jsonl"
    if not fl.exists():
        return []
    where = {}
    if kl.exists():
        for l in kl.read_text(encoding="utf-8").splitlines():
            if l.strip():
                x = json.loads(l)
                where[x["key"]] = (x.get("module"), x.get("phase"))
    rows = []
    for l in fl.read_text(encoding="utf-8").splitlines():
        if l.strip():
            x = json.loads(l)
            m, ph = where.get(x.get("key"), (None, None))
            if modules is None or m in set(modules):
                rows.append({**x, "module": m, "phase": ph})
    return rows


# ------------------------------------------------------------------------------------------------ self-test ---
def selftest(log=print) -> bool:
    """Hand-made cases for the converter and the checks (wdt names, hand-read from its closed set and RTL), malformed
    replies, and an end-to-end chain on wdt with stub executors (no model)."""
    import tempfile
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        log(f"   {'ok  ' if cond else 'FAIL'} {label}")
    w = "neorv32_wdt"
    names = closed_names(w)
    check("wdt closed set has ctrl.enable, clk_i, bus_rsp_o.data", {(w, "ctrl.enable"), (w, "clk_i"), (w, "bus_rsp_o.data")} <= set(names))
    check("wdt RTL has lines 94 and 140, not 2", {94, 140} <= rtl_lines(w) and 2 not in rtl_lines(w))
    dn = diagram_names(w)
    check("wdt diagram: blocks bus_access/wdt_counter, output clkgen_en_o, input bus_req_i",
          {"bus_access", "wdt_counter"} <= dn[w]["blocks"] and "clkgen_en_o" in dn[w]["outputs"] and "bus_req_i" in dn[w]["inputs"])
    ue = unit_entities("neorv32_bus")
    check(f"bus: io_switch unit may report neorv32_bus_reg elements ({sorted(ue.get('neorv32_bus_io_switch', []))})",
          ue.get("neorv32_bus_io_switch") == {"neorv32_bus_io_switch", "neorv32_bus_reg"})
    concepts = [{"id": "C1", "unit": w, "objectives": ["I", "A"], "enters through": ["bus_req_i.data"]},
                {"id": "C2", "unit": w, "objectives": ["C"]}]
    p2 = {"points": [], "structural assets": [
        {"concept id": "C1", "element": "ctrl.enable", "entity": w, "label": "primary", "objectives": ["I"], "links": [], "points": ["bus_access"]},
        {"concept id": "C2", "element": "ctrl.enable", "entity": w, "label": "primary", "objectives": ["C"], "links": [], "points": ["bus_access"]},
        {"concept id": "C1", "element": "clkgen_en_o", "entity": w, "label": "secondary", "objectives": ["I"],
         "links": [{"primary": "ctrl.enable", "entity": w, "direction": "a"}]},
        {"concept id": "C1", "element": "cnt", "entity": w, "label": "primary", "objectives": [], "links": [], "same role": ["cnt_inc"]},
        {"concept id": "C1", "element": "cnt_started", "entity": w, "label": "primary", "objectives": [], "links": [], "same role": "reset_wdt"},
        {"concept id": "C1", "element": "no_such", "entity": w, "label": "primary", "objectives": ["A"], "links": []},
        "not an object"]}
    a = to_assets(w, p2, concepts)
    rows = {(x["Entity"], x["Asset RTL"]): x for x in a["Assets"]}
    check("converter: secondary rows dropped", (w, "clkgen_en_o") not in rows)
    check("converter: one row per element, C wins over I", rows.get((w, "ctrl.enable"), {}).get("Security Objective") == "Confidentiality"
          and rows[(w, "ctrl.enable")]["Concepts"] == ["C1", "C2"])
    check("converter: same role expanded (list and single string); empty objectives take the concept's (I)",
          rows.get((w, "cnt_inc"), {}).get("Security Objective") == "Integrity" and (w, "reset_wdt") in rows
          and not any(len(n) == 1 for _, n in rows))
    check("converter: invalid name kept and listed", (w, "no_such") in rows and a["_invalid"] == [f"{w}:no_such"])
    pr = check_phase2(w, {"points": [{"concept id": "C1", "point": "nowhere", "lines": [94, 2, [3, 4]]},
                                     {"concept id": "C1", "point": "bus_req_i"}],
                          "structural assets": p2["structural assets"]}, concepts)
    check(f"phase 2 checks: bad point, input port as point, bad line, nested line, invalid name, string same role, "
          f"anchor port missing, C2 without point ({len(pr)} problems)",
          any("'nowhere'" in x for x in pr) and any("'bus_req_i'" in x for x in pr) and any("[2]" in x for x in pr)
          and any("not numbers" in x for x in pr) and any("no_such" in x for x in pr) and any("'same role' is not a list" in x for x in pr)
          and any("anchor port 'bus_req_i.data'" in x for x in pr) and any(x.startswith("C2: no point") for x in pr))
    p1 = {"conceptual assets": [{"id": "C1", "unit": w, "objectives": ["I"], "rubric": {"integrity": "yes"},
                                 "enters through": ["bus_req_i.data", "clkgen_en_o"], "leaves through": ["clkgen_en_o", "nope_o"],
                                 "held lines": [94, 2, [3, 4]]},
                                {"id": "C1", "unit": w, "objectives": "I", "rubric": "yes"}, {}]}
    pr1 = check_phase1(w, p1)
    check(f"phase 1 checks: bad port, input/output side, bad and nested lines, duplicate and missing ids, string rubric ({len(pr1)})",
          any("nope_o" in x for x in pr1) and any("enters through 'clkgen_en_o'" in x for x in pr1) and any("[2]" in x for x in pr1)
          and any("not numbers" in x for x in pr1) and any("duplicate ids" in x for x in pr1) and any("rubric is not" in x for x in pr1)
          and not any("'bus_req_i.data'" in x for x in pr1))
    check("phase 1 schema: grouped by unit is a schema failure", phase1_concepts({"conceptual assets": {w: []}}) is None
          and check_phase1(w, ["x"]) == ["schema: no 'conceptual assets' list of objects"])
    # end to end with stub executors, in scratch run folders
    good1 = {"module name": w, "conceptual assets": [
        {"id": "C1", "unit": w, "concept": "x", "objectives": ["I"], "rubric": {"integrity": "yes"},
         "enters through": ["bus_req_i.data"], "leaves through": ["clkgen_en_o"], "entry lines": [94],
         "held lines": [94], "exit lines": [140]}], "considered, not kept": [], "notes": []}
    good2 = {"module name": w, "points": [{"concept id": "C1", "point": "bus_access", "integrity": "yes", "lines": [94]}],
             "structural assets": [{"concept id": "C1", "element": "ctrl.enable", "entity": w, "label": "primary",
                                    "objectives": ["I"], "links": [], "points": ["bus_access"], "lines": [94]}], "notes": []}
    sent = []

    def stub(replies):
        def f(system, user):
            ph = 2 if "=== CONCEPTS" in user else 1
            sent.append((ph, "THIS CALL: PHASE 2" in system, '"id": "C1"' in user))
            return json.dumps(replies[ph]), {"in": 0, "out": 0}
        return f
    with tempfile.TemporaryDirectory() as td:
        row = run_module("two_phase_v1", w, stub({1: good1, 2: good2}), Path(td))
        a = json.loads((Path(td) / "assets" / f"{w}.json").read_text(encoding="utf-8"))
        n = len(sent)
        again = run_module("two_phase_v1", w, stub({1: good1, 2: good2}), Path(td))
        asked_again = len(sent) - n
    check(f"chain: phase 1 then phase 2 with the right system prompt and the concepts passed ({sent[:2]})",
          sent[:2] == [(1, False, False), (2, True, True)])
    check(f"chain: assets written in scorer format ({row['status']})", row["status"] == "done"
          and a["Assets"][0]["Asset RTL"] == "ctrl.enable" and a["Assets"][0]["Security Objective"] == "Integrity")
    check("chain: stored replies are not asked again", again["status"] == "done" and asked_again == 0)
    bad1 = {**good1, "conceptual assets": [{**good1["conceptual assets"][0], "held lines": [[131, 132]], "rubric": "yes"}]}
    sent.clear()
    with tempfile.TemporaryDirectory() as td:
        r_a = run_module("two_phase_v1", w, stub({1: bad1, 2: good2}), Path(td))
        r_b = run_module("two_phase_v1", w, stub({1: bad1, 2: good2}), Path(td))
        stored = (Path(td) / "phase1" / f"{w}.json").exists()
    check(f"malformed but parseable reply: stored once, not asked again, module goes on ({r_a['status']}, calls {[s[0] for s in sent]})",
          stored and [s[0] for s in sent] == [1, 2] and r_b["status"] == "done")
    sent.clear()
    with tempfile.TemporaryDirectory() as td:
        r_c = run_module("two_phase_v1", w, stub({1: {"conceptual assets": {w: []}}, 2: good2}), Path(td))
        no_assets = not (Path(td) / "assets" / f"{w}.json").exists()
    check(f"Phase 1 grouped by unit: schema failure, no Phase 2 call, no assets ({r_c['status']})",
          r_c["status"] == "phase 1 schema failure" and [s[0] for s in sent] == [1] and no_assets)
    with tempfile.TemporaryDirectory() as td:
        run_module("two_phase_v1", w, stub({1: good1, 2: good2}), Path(td))
        other = {**good1, "conceptual assets": [{**good1["conceptual assets"][0], "id": "C9"}]}
        (Path(td) / "phase1" / f"{w}.json").unlink()
        try:
            run_module("two_phase_v1", w, stub({1: other, 2: good2}), Path(td))
            stale = False
        except RuntimeError as e:
            stale = "another message" in str(e)
    check("re-asked Phase 1 with a stale Phase 2 file: stops with a message instead of reusing it", stale)
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        sys.exit(0 if selftest() else 1)
