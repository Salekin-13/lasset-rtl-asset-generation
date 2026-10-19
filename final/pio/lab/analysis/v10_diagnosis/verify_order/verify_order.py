"""Rebuild check for the order test records (two_phase_v9i_orderB r0-r2 and two_phase_v9i r1-r2, seven modules).

Independent of chain.py: the hash recipe is re-implemented here from reading chain.py / check_lab_prompt.py / labkit.py:
  sha12(t)      = sha256(t.encode("utf-8")).hexdigest()[:12]
  system(k)     = common.md.rstrip() + "\n\n" + phase<k>.md            (files read as text, utf-8, universal newlines)
  user(k)       = phase<k>_user.md.format(module, rtl, diagram, closed_set=compact JSON[, concepts])
  concepts      = json.dumps(<stored Phase 1 raw reply parsed>["Conceptual Assets"], indent=1, ensure_ascii=False)
  request key   = sha12(system + "\n\n" + user)
Every stored record must match on "system sha", "user sha" and usage["request key"]; _run_meta.json must match on the
system and user-template shas; the raw reply must parse (labkit.parse_json's rule) into the expected top-level list.
Then the two prompt folders are compared: phase1.md / phase2.md same multiset of lines (moves reported), common.md and
the user templates byte-identical. A self-test with planted faults runs first; nothing is reported if it fails.
Sends nothing; imports nothing from the lab.

  python -B verify_order.py
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
PROMPTS = LAB / "prompts"
RUNS = LAB / "runs"
INPUTS = LAB / "inputs" / "v1"
MODEL_DIR = "gpt-5.6-luna__high"
MODULES = ["neorv32_cpu_frontend", "neorv32_slink", "neorv32_cpu_icc", "neorv32_cpu_counters", "neorv32_cpu_control",
           "neorv32_debug_dm", "neorv32_xbus"]
JOBS = [("two_phase_v9i_orderB", 0), ("two_phase_v9i_orderB", 1), ("two_phase_v9i_orderB", 2),
        ("two_phase_v9i", 1), ("two_phase_v9i", 2)]


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def system(version: str, phase: int) -> str:
    d = PROMPTS / version
    return read(d / "common.md").rstrip() + "\n\n" + read(d / f"phase{phase}.md")


def module_dir(m: str) -> Path:
    for split in ("tuning", "heldout"):
        if (INPUTS / split / m).exists():
            return INPUTS / split / m
    raise FileNotFoundError(m)


def user(version: str, phase: int, m: str, concepts=None) -> str:
    d = module_dir(m)
    t = read(PROMPTS / version / f"phase{phase}_user.md")
    vals = {"module": m, "rtl": read(d / "rtl.txt"), "diagram": read(d / "diagram.txt"),
            "closed_set": json.dumps(json.loads(read(d / "closed_set.json")), separators=(",", ":"))}
    if phase == 2:
        vals["concepts"] = json.dumps(concepts, indent=1, ensure_ascii=False)
    return t.format(**vals)


def parse_json(text: str):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


# ------------------------------------------------------------------------------------------------ records ---
def check_record(version: str, rep: int, m: str, phase: int, concepts) -> dict:
    run = RUNS / f"{version}__v1" / MODEL_DIR / f"r{rep}"
    path = run / f"phase{phase}" / f"{m}.json"
    row = {"version": version, "rep": rep, "module": m, "phase": phase, "file": str(path.relative_to(LAB)),
           "exists": path.exists(), "mismatches": []}
    if not path.exists():
        row["mismatches"].append("record file missing")
        return row
    rec = json.loads(read(path))
    s = system(version, phase)
    u = user(version, phase, m, concepts)
    key = sha12(s + "\n\n" + u)
    row["system sha"] = {"stored": rec.get("system sha"), "rebuilt": sha12(s)}
    row["user sha"] = {"stored": rec.get("user sha"), "rebuilt": sha12(u)}
    usage = rec.get("usage") or {}
    row["request key"] = {"stored": usage.get("request key"), "rebuilt": key}
    for k in ("system sha", "user sha", "request key"):
        if row[k]["stored"] != row[k]["rebuilt"]:
            row["mismatches"].append(f"{k}: stored {row[k]['stored']} vs rebuilt {row[k]['rebuilt']}")
    # identity fields of the record
    for k, want in (("module", m), ("prompt version", version), ("input version", "v1"), ("phase", phase)):
        if rec.get(k) != want:
            row["mismatches"].append(f"record field {k}: {rec.get(k)!r} vs {want!r}")
    row["model"] = usage.get("model")
    row["effort"] = usage.get("effort")
    row["response id"] = usage.get("response id")
    row["tokens"] = {k: usage.get(k) for k in ("in", "out", "reasoning", "cached")}
    # the request key must be logged in _keys.jsonl for this module and phase
    keys = [json.loads(l) for l in read(run / "_keys.jsonl").splitlines() if l.strip()]
    logged = {x["key"] for x in keys if x.get("module") == m and x.get("phase") == phase}
    row["key logged"] = key in logged
    if key not in logged:
        row["mismatches"].append(f"request key {key} not in _keys.jsonl for {m} phase {phase} (logged: {sorted(logged)})")
    # the raw reply parses and has the expected top-level list
    raw = rec.get("raw")
    row["raw chars"] = len(raw) if isinstance(raw, str) else None
    want_key = "Conceptual Assets" if phase == 1 else "Concept Walks"
    try:
        obj = parse_json(raw)
        lst = obj.get(want_key) if isinstance(obj, dict) else None
        row["parsed"] = isinstance(lst, list)
        row["top-level keys"] = list(obj.keys()) if isinstance(obj, dict) else None
        row[f"{want_key} count"] = len(lst) if isinstance(lst, list) else None
        if not isinstance(lst, list):
            row["mismatches"].append(f"raw reply parses but has no {want_key!r} list")
    except (ValueError, TypeError) as e:
        row["parsed"] = False
        row["mismatches"].append(f"raw reply does not parse: {type(e).__name__}: {str(e)[:80]}")
        obj = None
    # the stored "reply" (v5 keys) agrees in size with the raw list
    rep_ = rec.get("reply")
    if phase == 1 and isinstance(rep_, dict) and isinstance(rep_.get("conceptual assets"), list) and obj is not None:
        if len(rep_["conceptual assets"]) != row.get("Conceptual Assets count"):
            row["mismatches"].append("stored 'reply' concept count differs from the raw 'Conceptual Assets'")
    row["problems"] = len(rec.get("problems") or [])
    row["problem texts"] = rec.get("problems") or []
    row["check crashed"] = bool(rec.get("check crashed"))
    if rec.get("problems") == ["not checked yet"] or rec.get("check crashed"):
        row["mismatches"].append("record never checked or check crashed")
    row["_obj"] = obj
    return row


def check_meta(version: str, rep: int) -> dict:
    run = RUNS / f"{version}__v1" / MODEL_DIR / f"r{rep}"
    meta = json.loads(read(run / "_run_meta.json"))
    d = PROMPTS / version
    want = {"prompt version": version, "input version": "v1", "model": "gpt-5.6-luna", "effort": "high",
            "system sha phase 1": sha12(system(version, 1)), "system sha phase 2": sha12(system(version, 2)),
            "user template sha phase 1": sha12(read(d / "phase1_user.md")),
            "user template sha phase 2": sha12(read(d / "phase2_user.md")),
            "inputs manifest sha": sha12(read(INPUTS / "manifest.json"))}
    diff = {k: {"stored": meta.get(k), "rebuilt": v} for k, v in want.items() if meta.get(k) != v}
    extras = {"pending files": sorted(p.name for p in (run / "_pending").glob("*")) if (run / "_pending").exists() else None,
              "failed calls file": (run / "_failed_calls.jsonl").exists(),
              "schema_failed folder": (run / "_schema_failed").exists(),
              "executor": meta.get("executor")}
    return {"run": str(run.relative_to(LAB)), "meta": meta, "mismatches": diff, **extras}


# ------------------------------------------------------------------------------------------------ prompts ---
def heading_before(lines: list[str], i: int) -> str:
    """The nearest earlier line that reads like a step or section heading (e.g. '3. ...', 'OUTPUT', 'RULES')."""
    for j in range(i - 1, -1, -1):
        l = lines[j]
        if re.match(r"^\d+\. ", l) or (l.strip() and l == l.upper() and len(l) < 60 and not l.startswith("-")):
            return f"line {j + 1}: {l[:70]}"
    return "(start)"


def blocks_of(lines: list[str]) -> list[dict]:
    """Split a file into blocks: a block starts at an unindented line and takes the indented lines after it (a rule
    with its Scope / Criteria / ... lines, or a one-line rule or paragraph). Blank lines are their own blocks, so the
    blocks concatenate back to the file exactly."""
    out = []
    for i, l in enumerate(lines):
        if l.startswith((" ", "\t")) and out and out[-1]["text"] and out[-1]["text"][-1].strip() != "":
            out[-1]["text"].append(l)
        else:
            out.append({"start": i + 1, "text": [l]})
    for b in out:
        b["end"] = b["start"] + len(b["text"]) - 1
        b["key"] = "\n".join(b["text"])
    return out


def lcs_keep(a: list[str], b: list[str]) -> tuple[set, set]:
    """Indices of a and b that lie on one longest common subsequence (blocks that kept their relative order)."""
    n, m = len(a), len(b)
    L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            L[i][j] = L[i + 1][j + 1] + 1 if a[i] == b[j] else max(L[i + 1][j], L[i][j + 1])
    i = j = 0
    ka, kb = set(), set()
    while i < n and j < m:
        if a[i] == b[j]:
            ka.add(i); kb.add(j); i += 1; j += 1
        elif L[i + 1][j] > L[i][j + 1]:
            i += 1
        else:
            j += 1          # on a tie the block orderB shows first is the one left off (called moved)
    return ka, kb


def heading_of(lines: list[str], i: int) -> str:
    """The nearest earlier unindented line that is a step ('4. Primary...'), 'Rules:' or 'OUTPUT'."""
    for j in range(i - 1, -1, -1):
        l = lines[j]
        if re.match(r"^\d+\. ", l) or l.rstrip() in ("Rules:", "OUTPUT"):
            return f"line {j + 1} ({l[:40].rstrip()!r})"
    return "(start)"


def moved_blocks(a: list[str], b: list[str]) -> list[dict]:
    """Blocks of a that are not on a longest common subsequence with b: each with its place in both files."""
    A, B = blocks_of(a), blocks_of(b)
    assert "\n".join(x["key"] for x in A) == "\n".join(a) and "\n".join(x["key"] for x in B) == "\n".join(b)
    ka, kb = lcs_keep([x["key"] for x in A], [x["key"] for x in B])
    used = set()
    moves = []
    for i, x in enumerate(A):
        if i in ka or not x["key"].strip():
            continue
        j = next((j for j, y in enumerate(B) if j not in kb and j not in used and y["key"] == x["key"]), None)
        if j is None:
            moves.append({"block head": x["text"][0][:90], "v9i lines": f"{x['start']}-{x['end']}", "orderB": "NOT FOUND"})
            continue
        used.add(j)
        y = B[j]
        prev_a = A[i - 1]["text"][0][:60] if i > 0 else "(start)"
        next_a = A[i + 1]["text"][0][:60] if i + 1 < len(A) else "(end)"
        prev_b = B[j - 1]["text"][0][:60] if j > 0 else "(start)"
        next_b = B[j + 1]["text"][0][:60] if j + 1 < len(B) else "(end)"
        moves.append({"block head": x["text"][0][:90], "lines in block": len(x["text"]),
                      "v9i": {"lines": f"{x['start']}-{x['end']}", "under": heading_of(a, x["start"] - 1),
                              "between": [prev_a, next_a]},
                      "orderB": {"lines": f"{y['start']}-{y['end']}", "under": heading_of(b, y["start"] - 1),
                                 "between": [prev_b, next_b]}})
    extra_b = [B[j]["text"][0][:90] for j in range(len(B)) if j not in kb and j not in used and B[j]["key"].strip()]
    return moves, extra_b, len(A), len(B)


def compare_phase_file(f: str) -> dict:
    a = read(PROMPTS / "two_phase_v9i" / f).split("\n")
    b = read(PROMPTS / "two_phase_v9i_orderB" / f).split("\n")
    out = {"file": f, "lines v9i": len(a), "lines orderB": len(b), "same multiset of lines": Counter(a) == Counter(b),
           "identical order": a == b}
    ca, cb = Counter(a), Counter(b)
    out["lines only in v9i"] = sorted((ca - cb).elements())
    out["lines only in orderB"] = sorted((cb - ca).elements())
    moves, extra_b, na, nb = moved_blocks(a, b)
    out["blocks v9i"], out["blocks orderB"] = na, nb
    out["moved blocks"] = moves
    out["orderB blocks matched to no moved v9i block"] = extra_b
    # the OUTPUT section (from its last "\nOUTPUT" on) must be identical
    ta, tb = "\n".join(a), "\n".join(b)
    ia, ib = ta.rfind("\nOUTPUT"), tb.rfind("\nOUTPUT")
    out["OUTPUT section identical"] = ia >= 0 and ib >= 0 and ta[ia:] == tb[ib:]
    # the part before the first rule block must be identical too
    out["text before the rules identical"] = (ta[:ta.index("\n- ")] == tb[:tb.index("\n- ")])
    return out


def compare_folders() -> dict:
    res = {"byte-identical": {}, "phase files": []}
    for f in ("common.md", "phase1_user.md", "phase2_user.md"):
        ba = (PROMPTS / "two_phase_v9i" / f).read_bytes()
        bb = (PROMPTS / "two_phase_v9i_orderB" / f).read_bytes()
        res["byte-identical"][f] = {"identical": ba == bb, "bytes v9i": len(ba), "bytes orderB": len(bb),
                                    "sha12 v9i": hashlib.sha256(ba).hexdigest()[:12],
                                    "sha12 orderB": hashlib.sha256(bb).hexdigest()[:12]}
    for f in ("phase1.md", "phase2.md"):
        ba = (PROMPTS / "two_phase_v9i" / f).read_bytes()
        bb = (PROMPTS / "two_phase_v9i_orderB" / f).read_bytes()
        r = compare_phase_file(f)
        r["bytes v9i"], r["bytes orderB"] = len(ba), len(bb)
        r["crlf v9i"], r["crlf orderB"] = b"\r\n" in ba, b"\r\n" in bb
        res["phase files"].append(r)
    return res


# ------------------------------------------------------------------------------------------------ self-test ---
def selftest(log) -> bool:
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        log(f"   {'ok  ' if cond else 'FAIL'} {label}")
    # 1. sha12 against a hand-known value: sha256("abc") = ba7816bf8f01cfea...
    check("sha12('abc') == 'ba7816bf8f01'", sha12("abc") == "ba7816bf8f01")
    # 2. the rebuilt system sha of v9i phase 1 equals the sha _run_meta.json stores (an independent write by chain._meta)
    meta = json.loads(read(RUNS / "two_phase_v9i__v1" / MODEL_DIR / "r1" / "_run_meta.json"))
    check("rebuilt system(v9i, 1) sha equals r1/_run_meta.json's", sha12(system("two_phase_v9i", 1)) == meta["system sha phase 1"])
    # 3. a planted one-character change in the user message is caught
    m = "neorv32_slink"
    u = user("two_phase_v9i", 1, m)
    rec = json.loads(read(RUNS / "two_phase_v9i__v1" / MODEL_DIR / "r1" / "phase1" / f"{m}.json"))
    check("rebuilt user sha equals the stored one (slink r1 phase 1)", sha12(u) == rec["user sha"])
    check("planted change (one space appended) is caught", sha12(u + " ") != rec["user sha"])
    # 4. a planted line change in the prompt comparison is caught
    a = ["x", "y", "z"]
    check("line-multiset check catches a changed line", Counter(a) != Counter(["x", "y", "q"]))
    check("line-multiset check accepts a reorder", Counter(a) == Counter(["z", "x", "y"]))
    # 5. parse_json strips a fence and reads the object
    check("parse_json reads a fenced object", parse_json("```json\n{\"a\": [1]}\n```")["a"] == [1])
    # 6. the block mover finds a planted move and nothing else
    pa = ["H:", "- A.", "  s1", "- B.", "  s2", "- C.", "", "OUTPUT"]
    pb = ["H:", "- A.", "  s1", "- C.", "- B.", "  s2", "", "OUTPUT"]
    mv, extra, na, nb = moved_blocks(pa, pb)
    # B and C swap: one of them is the moved block (a tie; the code names C, the one orderB shows first)
    check(f"planted swap of B and C found as exactly one moved block ({[m['block head'] for m in mv]}, extra {extra})",
          [m["block head"] for m in mv] == ["- C."] and not extra and mv[0]["v9i"]["lines"] == "6-6"
          and mv[0]["orderB"]["lines"] == "4-4" and na == nb == 6)
    check("no move reported for identical files", moved_blocks(pa, pa)[0] == [])
    return ok


# ------------------------------------------------------------------------------------------------ main ---
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("self-test")
    if not selftest(print):
        print("SELF-TEST FAILED: nothing reported")
        sys.exit(1)
    rows, metas = [], []
    for version, rep in JOBS:
        metas.append(check_meta(version, rep))
        for m in MODULES:
            r1 = check_record(version, rep, m, 1, None)
            obj1 = r1.pop("_obj", None)
            concepts = obj1.get("Conceptual Assets") if isinstance(obj1, dict) else None
            r2 = check_record(version, rep, m, 2, concepts)
            r2.pop("_obj", None)
            rows += [r1, r2]
    n = len(rows)
    exact = [r for r in rows if r["exists"] and not r["mismatches"]]
    bad = [r for r in rows if r["mismatches"]]
    by_job = {}
    for r in rows:
        k = f"{r['version']} r{r['rep']}"
        d = by_job.setdefault(k, {"records": 0, "exact": 0, "parsed": 0, "mismatched": 0})
        d["records"] += 1
        d["exact"] += not r["mismatches"]
        d["parsed"] += bool(r.get("parsed"))
        d["mismatched"] += bool(r["mismatches"])
    summary = {
        "records checked": n,
        "records expected": len(JOBS) * len(MODULES) * 2,
        "records rebuilt exactly (system sha, user sha, request key, key logged, identity fields)": len(exact),
        "records with any mismatch": len(bad),
        "parsed replies (raw -> expected top-level list)": sum(bool(r.get("parsed")) for r in rows),
        "records with check problems > 0": sum(r.get("problems", 0) > 0 for r in rows),
        "total check problems": sum(r.get("problems", 0) for r in rows),
        "models seen": dict(Counter(r.get("model") for r in rows)),
        "efforts seen": dict(Counter(r.get("effort") for r in rows)),
        "distinct response ids": len({r.get("response id") for r in rows if r.get("response id")}),
        "per job": by_job,
        "concepts per phase-1 record": {f"{r['version']} r{r['rep']} {r['module']}": r.get("Conceptual Assets count")
                                        for r in rows if r["phase"] == 1},
        "walks per phase-2 record": {f"{r['version']} r{r['rep']} {r['module']}": r.get("Concept Walks count")
                                     for r in rows if r["phase"] == 2},
        "tokens summed": {k: sum((r.get("tokens") or {}).get(k) or 0 for r in rows) for k in ("in", "out", "reasoning", "cached")},
    }
    folders = compare_folders()
    out = {"summary": summary, "run meta": metas, "mismatched records": bad, "prompt folders": folders,
           "shas rebuilt": {v: {"system phase 1": sha12(system(v, 1)), "system phase 2": sha12(system(v, 2)),
                               "user template phase 1": sha12(read(PROMPTS / v / "phase1_user.md")),
                               "user template phase 2": sha12(read(PROMPTS / v / "phase2_user.md"))}
                            for v in ("two_phase_v9i", "two_phase_v9i_orderB")},
           "records": rows}
    (HERE / "verify_order.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print()
    print(json.dumps({k: v for k, v in summary.items() if k not in ("concepts per phase-1 record", "walks per phase-2 record")},
                     indent=1, ensure_ascii=False))
    print("\nconcepts per phase-1 record:", json.dumps(summary["concepts per phase-1 record"], indent=1))
    print("\nwalks per phase-2 record:", json.dumps(summary["walks per phase-2 record"], indent=1))
    print("\nrun meta:")
    for x in metas:
        print(f"  {x['run']}: executor {x['executor']}; meta mismatches {x['mismatches'] or 'none'}; pending {x['pending files']}; "
              f"failed-calls file {x['failed calls file']}; _schema_failed {x['schema_failed folder']}")
    print("\nmismatched records:")
    for r in bad:
        print(f"  {r['file']}: {r['mismatches']}")
    if not bad:
        print("  none")
    print("\nshas rebuilt:", json.dumps(out["shas rebuilt"], indent=1))
    print("\nprompt folders:")
    print(json.dumps(folders["byte-identical"], indent=1))
    for r in folders["phase files"]:
        print(f"\n{r['file']}: lines {r['lines v9i']} vs {r['lines orderB']}; same multiset {r['same multiset of lines']}; "
              f"identical order {r['identical order']}; OUTPUT identical {r['OUTPUT section identical']}; "
              f"text before the rules identical {r['text before the rules identical']}; "
              f"bytes {r['bytes v9i']} vs {r['bytes orderB']}; crlf {r['crlf v9i']}/{r['crlf orderB']}; "
              f"only-in-v9i {len(r['lines only in v9i'])}, only-in-orderB {len(r['lines only in orderB'])}; "
              f"blocks {r['blocks v9i']} vs {r['blocks orderB']}; moved blocks {len(r['moved blocks'])}; "
              f"unmatched orderB blocks {r['orderB blocks matched to no moved v9i block']}")
        for mv in r["moved blocks"]:
            print("  ", json.dumps(mv, ensure_ascii=False, indent=4))
    print("\nproblem texts per record (phase 2 only, non-empty):")
    for r in rows:
        if r.get("problem texts"):
            print(f"  {r['version']} r{r['rep']} {r['module']} p{r['phase']}: {r['problem texts']}")


if __name__ == "__main__":
    main()
