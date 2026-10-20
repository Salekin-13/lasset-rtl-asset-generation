"""Independent re-derivation (2026-10-18) of the v9m vs v9j "internal, outside LOCATED" false-positive counts.

Reads only: the reference, the stored runs (assets/, phase1/ raw replies, phase2/ records), the built inputs and the
phase2_user.md templates. Imports chain only for chain.closed_names and chain.run_dir. Sends nothing.

Self-tests (all must pass before any figure is printed):
  T1 scorer: a hand-built listed/reference pair with duplicates.
  T2 LOCATED: the Phase 2 user message rebuilt with THIS file's LOCATED output must hash to the "user sha" stored in
     every v9m phase2 record (41 modules x 3 runs). That is the message the model was actually sent, so a match proves
     this LOCATED equals the one the run used, without calling chain.located.
  T3 LOCATED hand-read: one concept of one module, printed with the closed-set evidence for a reader to check.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
import chain  # noqa: E402  (only chain.closed_names and chain.run_dir are used)

MODEL, EFFORT, RUNS = "gpt-5.6-luna", "high", (0, 1, 2)
VERSIONS = ("two_phase_v9m", "two_phase_v9j")
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
INPUTS = LAB / "inputs" / "v1"
ASSIGN_KEYS = ("gets value from", "decided by", "reset by", "clocked by")


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def parse_json(text: str):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


def lst(v):
    return v if isinstance(v, list) else ([v] if isinstance(v, str) else [])


def ints(v):
    return {int(x) for x in lst(v) if isinstance(x, int) or (isinstance(x, str) and x.isdigit())}


# ---------------------------------------------------------------------------------------------- LOCATED rule ---
def located(m: str, concepts) -> dict:
    cn = chain.closed_names(m)
    names = {x for (_, x) in cn}
    assign: dict[str, set] = {}
    for (_, x), rec in cn.items():
        s = assign.setdefault(x, set())
        for key in ASSIGN_KEYS:
            for c in (rec.get("counterparts") or {}).get(key, []) or []:
                if isinstance(c, dict):
                    s.update(ints(c.get("lines") or []))
    out = {}
    for c in concepts or []:
        if not isinstance(c, dict) or not c.get("Concept ID"):
            continue
        ports = [p for p in lst(c.get("Enters Through")) + lst(c.get("Leaves Through")) if isinstance(p, str)]
        held = ints(c.get("Held Lines"))
        out[str(c["Concept ID"])] = sorted({p for p in ports if p in names} | {x for x, s in assign.items() if s & held})
    return out


def located_text(d: dict) -> str:
    return json.dumps(d, indent=1, ensure_ascii=False)


# ---------------------------------------------------------------------------------------------- exact scorer ---
def score_rows(listed: list, reference: list):
    """Per listed row: correct or not (the first copies of a name in list order are the correct ones); plus
    (correct, findable). Reference rows walked in order; a row whose element still has a listed copy consumes one."""
    copies = Counter(listed)
    correct_per_name = Counter()
    for el in reference:
        if copies[el] > 0:
            copies[el] -= 1
            correct_per_name[el] += 1
    flags, seen = [], Counter()
    for x in listed:
        seen[x] += 1
        flags.append(seen[x] <= correct_per_name[x])
    return flags, sum(correct_per_name.values()), len(reference)


# ---------------------------------------------------------------------------------------------- data ---
_GT = None


def reference_rows(m: str) -> list:
    global _GT
    if _GT is None:
        _GT = json.loads(GT.read_text(encoding="utf-8"))["modules"]
    if m not in _GT:
        return []
    names = {x for (_, x) in chain.closed_names(m)}
    return [r["element"] for r in _GT[m]["assets"] if r["element"] in names]


def groups() -> dict:
    tun = sorted(p.name for p in (INPUTS / "tuning").iterdir() if p.is_dir())
    ho = sorted(p.name for p in (INPUTS / "heldout").iterdir() if p.is_dir())
    sp = json.loads((LAB / "splits" / "tuning_v2.json").read_text(encoding="utf-8"))
    t15 = [m for m in tun if reference_rows(m)]
    return {"tuning 15": t15, "held-out 26": ho,
            "tuning_v2": list(sp["tuning"]), "heldout_v2": list(sp["heldout"]), "all 41": sorted(set(t15) | set(ho)),
            "no-reference tuning modules (not in any group)": [m for m in tun if not reference_rows(m)]}


def inputs(m: str) -> dict:
    for split in ("tuning", "heldout"):
        d = INPUTS / split / m
        if d.exists():
            return {f: (d / f).read_text(encoding="utf-8") for f in ("rtl.txt", "closed_set.json", "diagram.txt")}
    raise FileNotFoundError(m)


def phase1_concepts(rd: Path, m: str):
    rec = json.loads((rd / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
    try:
        return parse_json(rec["raw"]).get("Conceptual Assets"), None
    except Exception as e:  # noqa: BLE001
        return None, f"{m}: phase 1 raw unparseable ({e})"


# ---------------------------------------------------------------------------------------------- self-tests ---
def t1_scorer():
    flags, correct, findable = score_rows(["a", "a", "b", "c", "b"], ["a", "b", "b", "d"])
    assert flags == [True, False, True, False, True], flags
    assert (correct, findable) == (3, 4), (correct, findable)
    flags, correct, findable = score_rows([], ["a"])
    assert flags == [] and (correct, findable) == (0, 1)
    flags, correct, findable = score_rows(["x.y", "x"], ["x.y"])
    assert flags == [True, False] and (correct, findable) == (1, 1)
    print("T1 scorer self-test: PASS")


def t2_user_sha(version: str):
    """Rebuild each Phase 2 user message with this file's LOCATED and compare its sha12 with the stored 'user sha'."""
    t = (LAB / "prompts" / version / "phase2_user.md").read_text(encoding="utf-8")
    ok, n, bad = 0, 0, []
    for k in RUNS:
        rd = chain.run_dir(version, MODEL, k, EFFORT)
        for f in sorted((rd / "phase2").glob("*.json")):
            m = f.stem
            n += 1
            rec = json.loads(f.read_text(encoding="utf-8"))
            concepts, prob = phase1_concepts(rd, m)
            if prob:
                bad.append(f"r{k} {prob}")
                continue
            x = inputs(m)
            vals = {"module": m, "rtl": x["rtl.txt"], "diagram": x["diagram.txt"],
                    "closed_set": json.dumps(json.loads(x["closed_set.json"]), separators=(",", ":")),
                    "concepts": json.dumps(concepts, indent=1, ensure_ascii=False)}
            if "{located}" in t:
                vals["located"] = located_text(located(m, concepts))
            got = sha12(t.format(**vals))
            if got == rec.get("user sha"):
                ok += 1
            else:
                bad.append(f"r{k} {m}: rebuilt user message sha {got} != stored {rec.get('user sha')}")
    return ok, n, bad


def t3_hand_read():
    """One concept, with the evidence a reader needs to check the rule by hand."""
    m, version, k = "neorv32_spi", "two_phase_v9m", 0
    concepts, prob = phase1_concepts(chain.run_dir(version, MODEL, k, EFFORT), m)
    assert not prob, prob
    c = concepts[0]
    loc = located(m, concepts)[str(c["Concept ID"])]
    cn = chain.closed_names(m)
    held = ints(c.get("Held Lines"))
    print(f"T3 hand-read ({version} r{k} {m} {c['Concept ID']}): Enters {lst(c.get('Enters Through'))}, "
          f"Leaves {lst(c.get('Leaves Through'))}, Held Lines {sorted(held)}")
    for (ent, x), rec in sorted(cn.items()):
        hits = []
        for key in ASSIGN_KEYS:
            for cp in (rec.get("counterparts") or {}).get(key, []) or []:
                if isinstance(cp, dict) and ints(cp.get("lines") or []) & held:
                    hits.append((key, cp.get("element") or cp.get("port") or cp.get("instance"),
                                 sorted(ints(cp.get("lines")) & held)))
        if hits:
            print(f"   closed-set element {x} ({ent}) has assignment lines in Held Lines: {hits}")
    print(f"   -> LOCATED[{c['Concept ID']}] = {loc}")
    rtl = {}
    for line in inputs(m)["rtl.txt"].splitlines():
        mm = re.match(r"\s*(\d+) \|", line)
        if mm:
            rtl[int(mm.group(1))] = line
    for n in sorted(held):
        print(f"   RTL line {n}: {rtl.get(n, '<missing>').strip()}")
    return loc


# ---------------------------------------------------------------------------------------------- main count ---
def count_run(version: str, k: int, modules: list):
    rd = chain.run_dir(version, MODEL, k, EFFORT)
    out = {m: None for m in modules}
    probs = []
    for m in modules:
        af = rd / "assets" / f"{m}.json"
        if not af.exists():
            probs.append(f"{version} r{k} {m}: no assets file")
            continue
        rows = json.loads(af.read_text(encoding="utf-8"))["Assets"]
        concepts, prob = phase1_concepts(rd, m)
        if prob:
            probs.append(f"{version} r{k} {prob}")
            concepts = []
        loc = located(m, concepts)
        cn = chain.closed_names(m)
        ref = reference_rows(m)
        flags, correct, findable = score_rows([r["Asset RTL"] for r in rows], ref)
        c = Counter()
        c["listed"], c["correct"], c["findable"] = len(rows), correct, findable
        for r, ok in zip(rows, flags):
            name = r["Asset RTL"]
            top = name.split(".")[0]
            rec = cn.get((r["Entity"], top))
            if rec is None:
                probs.append(f"{version} r{k} {m}: {r['Entity']}:{top} not in the closed set")
                continue
            internal = "direction" not in rec
            cids = [str(x) for x in lst(r.get("Concepts"))]
            if any(x not in loc for x in cids):
                c["rows citing a concept id with no Phase 1 entry"] += 1
            inside = any(name in loc.get(x, []) for x in cids)
            inside_top = any(top in loc.get(x, []) for x in cids)
            tag = "correct" if ok else "false"
            if internal:
                c["internal"] += 1
                c[("internal inside " if inside else "internal outside ") + tag] += 1
                if not inside:
                    DETAIL.append({"version": version, "run": k, "module": m, "entity": r["Entity"], "name": name,
                                   "concepts": cids, "correct": ok,
                                   "LOCATED of those concepts": sorted({y for x in cids for y in loc.get(x, [])})})
                # sensitivity: membership judged on the top-level name instead of the full name
                if not inside_top and not ok:
                    c["internal outside(top-level name) false"] += 1
            else:
                c["port"] += 1
                c[("port inside " if inside else "port outside ") + tag] += 1
        # primary rows whose justification/reason mentions LOCATED
        p2 = json.loads((rd / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
        sas = (p2.get("reply") or {}).get("structural assets") or []
        for r in sas:
            if not isinstance(r, dict) or r.get("label") != "primary":
                continue
            c["primary rows (phase 2)"] += 1
            txt = " ".join(str(r.get(f) or "") for f in ("justification", "reason"))
            if "LOCATED" in txt:
                c["primary rows mentioning LOCATED"] += 1
            if "located" in txt.lower():
                c["primary rows mentioning located (any case)"] += 1
        out[m] = c
    return out, probs


DETAIL = []     # every internal, outside-LOCATED row (both versions), written to internal_outside_rows.json

KEYS = ["listed", "correct", "findable", "internal", "port",
        "internal outside correct", "internal outside false", "internal inside correct", "internal inside false",
        "port outside correct", "port outside false", "port inside correct", "port inside false",
        "internal outside(top-level name) false",
        "rows citing a concept id with no Phase 1 entry",
        "primary rows (phase 2)", "primary rows mentioning LOCATED", "primary rows mentioning located (any case)"]


def main():
    t1_scorer()
    sha_ok = {}
    for v in VERSIONS:
        ok, n, bad = t2_user_sha(v)
        sha_ok[v] = (ok, n, bad)
        print(f"T2 user-sha self-test {v}: {ok}/{n} Phase 2 user messages rebuilt to the stored sha"
              + ("" if not bad else "; FAILURES: " + "; ".join(bad[:5])))
    t3_hand_read()
    if any(ok != n or bad for ok, n, bad in sha_ok.values()):
        print("SELF-TEST FAILED: no figures reported")
        return
    g = groups()
    print("groups:", {k: len(v) for k, v in g.items()}, "tuning 15 =", g["tuning 15"])
    assert len(g["tuning 15"]) == 15 and len(g["held-out 26"]) == 26 and len(g["all 41"]) == 41
    per, probs = {}, []
    out_dir = HERE / "located"
    every = g["all 41"]        # the two no-reference tuning modules have no run output (checked: no assets/phase1 files)
    for m in g.pop("no-reference tuning modules (not in any group)"):
        for v in VERSIONS:
            assert not (chain.run_dir(v, MODEL, 0, EFFORT) / "assets" / f"{m}.json").exists(), m
    for v in VERSIONS:
        for k in RUNS:
            per[(v, k)], p = count_run(v, k, every)
            probs += p
            rd = chain.run_dir(v, MODEL, k, EFFORT)
            d = out_dir / v / f"r{k}"
            d.mkdir(parents=True, exist_ok=True)
            for m in every:
                concepts, _ = phase1_concepts(rd, m)
                (d / f"{m}.json").write_text(located_text(located(m, concepts or [])), encoding="utf-8")
    report = {}
    for gname, mods in g.items():
        print(f"\n=== group {gname} ({len(mods)} modules) ===")
        for v in VERSIONS:
            pooled = Counter()
            for k in RUNS:
                c = Counter()
                for m in mods:
                    if per[(v, k)].get(m):
                        c.update(per[(v, k)][m])
                pooled.update(c)
                print(f"{v} r{k}: " + ", ".join(f"{key}={c[key]}" for key in KEYS))
                report[f"{gname}|{v}|r{k}"] = {key: c[key] for key in KEYS}
            print(f"{v} POOLED r0-r2: " + ", ".join(f"{key}={pooled[key]}" for key in KEYS))
            report[f"{gname}|{v}|pooled"] = {key: pooled[key] for key in KEYS}
    (HERE / "result.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (HERE / "internal_outside_rows.json").write_text(json.dumps(DETAIL, indent=1), encoding="utf-8")
    print(f"\ninternal, outside-LOCATED rows of two_phase_v9m ({sum(d['version'] == 'two_phase_v9m' for d in DETAIL)}):")
    for d in DETAIL:
        if d["version"] == "two_phase_v9m":
            print(f"   r{d['run']} {d['module']} {d['entity']}:{d['name']} concepts={d['concepts']} "
                  f"{'correct' if d['correct'] else 'false'}; LOCATED there = {d['LOCATED of those concepts']}")
    print("\nproblems:", len(probs))
    for p in probs[:40]:
        print("  ", p)


if __name__ == "__main__":
    main()
