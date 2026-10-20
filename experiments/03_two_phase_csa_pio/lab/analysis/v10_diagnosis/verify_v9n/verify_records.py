"""Rebuild check of the stored two-phase records of the v9n prompt versions (2026-10-19).

For every run folder present under lab/runs/<version>__v1/gpt-5.6-luna__high/r<k>/ and every held-out module, this
script rebuilds the system and user messages of both phases from lab/prompts/<version>/ and lab/inputs/v1/, hashes them
(sha12 = sha256 hex[:12], as chain.py does) and compares with the shas stored in phase1/<m>.json and phase2/<m>.json.
It also re-parses every stored raw reply, counts asset files, counts Phase 2 records with a "format:" problem, lists
leftover _pending / failed-call files, and scores the asset files against the reference with the exact scorer given in
the task. Nothing here sends a request; chain is imported only for closed_names and run_dir.

  python -B verify_records.py
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
LAB = Path(__file__).resolve().parents[3]              # .../experiments/03_two_phase_csa_pio/lab
ROOT = LAB.parents[2]                                  # .../Prepoison_subset
sys.path.insert(0, str(LAB))
import chain  # noqa: E402  (closed_names, run_dir only)

VERSIONS = ["two_phase_v9n_place2", "two_phase_v9n_dbg"]
MODEL, EFFORT = "gpt-5.6-luna", "high"
HELDOUT = sorted(p.name for p in (LAB / "inputs" / "v1" / "heldout").iterdir() if p.is_dir())
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")           # universal newlines, as chain.py reads


def parse_json(text: str):
    """Same recipe as labkit.parse_json: strip a code fence, take the outermost braces, json.loads."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


def system_text(version: str, phase: int) -> str:
    d = LAB / "prompts" / version
    return read(d / "common.md").rstrip() + "\n\n" + read(d / f"phase{phase}.md")


def inputs(m: str) -> dict:
    d = LAB / "inputs" / "v1" / "heldout" / m
    return {f: read(d / f) for f in ("rtl.txt", "closed_set.json", "diagram.txt")}


def user_text(version: str, phase: int, m: str, concepts=None) -> str:
    x = inputs(m)
    t = read(LAB / "prompts" / version / f"phase{phase}_user.md")
    if "{located}" in t:
        raise RuntimeError(f"{version} phase {phase} template has a {{located}} slot; this rebuild does not fill it")
    vals = {"module": m, "rtl": x["rtl.txt"], "diagram": x["diagram.txt"],
            "closed_set": json.dumps(json.loads(x["closed_set.json"]), separators=(",", ":"))}
    if phase == 2:
        vals["concepts"] = json.dumps(concepts, indent=1, ensure_ascii=False)
    return t.format(**vals)


# ------------------------------------------------------------------------------------------------ scorer ---
def reference_rows(m: str) -> list[str]:
    """The reference elements of module m that are names in its closed set, in the reference's order."""
    gt = json.loads(read(GT))["modules"]
    names = {n for (_, n) in chain.closed_names(m)}
    return [r["element"] for r in gt.get(m, {}).get("assets", []) if r.get("element") in names]


def exact_score(listed_names: list[str], ref_rows: list[str]) -> dict:
    """Counter of listed names; reference rows walked in order, one whose element still has a copy consumes it and
    counts correct. listed = asset rows; findable = reference rows."""
    c = Counter(listed_names)
    correct = 0
    for el in ref_rows:
        if c[el] > 0:
            c[el] -= 1
            correct += 1
    return {"correct": correct, "listed": len(listed_names), "findable": len(ref_rows)}


# ------------------------------------------------------------------------------------------------ self-test ---
def selftest() -> list[str]:
    fails = []
    # 1. sha12 agrees with chain's own sha12 on a known string, and with a hand-computed value
    s = "abc"
    if sha12(s) != chain.sha12(s) or sha12(s) != "ba7816bf8f01":
        fails.append("sha12 differs from chain.sha12 or from the hand value for 'abc'")
    # 2. a planted one-character change in the rebuilt user message must change its sha (the mismatch detector works)
    m = HELDOUT[0]
    u = user_text(VERSIONS[0], 1, m)
    if sha12(u) == sha12(u[:-1] + ("x" if u[-1] != "x" else "y")):
        fails.append("planted change left the sha unchanged")
    # 3. the rebuilt template carries the module name and the compact closed set (no indentation)
    if m not in u or '"entity list":[' not in u:
        fails.append("rebuilt user message lacks the module name or the compact closed set")
    # 4. scorer on a hand-made case: listed a, a, b; reference a, a, a, c -> correct 2, listed 3, findable 4
    if exact_score(["a", "a", "b"], ["a", "a", "a", "c"]) != {"correct": 2, "listed": 3, "findable": 4}:
        fails.append("exact_score hand case")
    # 5. parse_json strips a fence and takes the outer object
    if parse_json("```json\n{\"a\": 1}\n```") != {"a": 1}:
        fails.append("parse_json fence case")
    return fails


# ------------------------------------------------------------------------------------------------ main ---
def check_version(version: str) -> dict:
    base = chain.run_dir(version, MODEL, 0, EFFORT).parent      # .../<version>__v1/gpt-5.6-luna__high
    runs = sorted((p for p in base.iterdir() if p.is_dir() and re.fullmatch(r"r\d+", p.name)),
                  key=lambda p: int(p.name[1:]))
    sys_sha = {1: sha12(system_text(version, 1)), 2: sha12(system_text(version, 2))}
    tmpl_sha = {k: sha12(read(LAB / "prompts" / version / f"phase{k}_user.md")) for k in (1, 2)}
    man = LAB / "inputs" / "v1" / "manifest.json"
    man_sha = sha12(read(man)) if man.exists() else None
    out = {"version": version, "folder": str(base), "rebuilt system sha": sys_sha, "rebuilt user template sha": tmpl_sha,
           "runs": {}}
    for rd in runs:
        meta = json.loads(read(rd / "_run_meta.json")) if (rd / "_run_meta.json").exists() else {}
        meta_mismatch = []
        for k, want in (("system sha phase 1", sys_sha[1]), ("system sha phase 2", sys_sha[2]),
                        ("user template sha phase 1", tmpl_sha[1]), ("user template sha phase 2", tmpl_sha[2]),
                        ("inputs manifest sha", man_sha), ("model", MODEL), ("effort", EFFORT),
                        ("prompt version", version), ("input version", "v1")):
            if meta.get(k) != want:
                meta_mismatch.append(f"{k}: stored {meta.get(k)!r} vs rebuilt {want!r}")
        r = {"run meta mismatches": meta_mismatch, "executor": meta.get("executor"),
             "phase1": {"present": 0, "rebuilt ok": 0, "mismatch": [], "parsed": 0, "unparsed": [], "problem flags": []},
             "phase2": {"present": 0, "rebuilt ok": 0, "mismatch": [], "parsed": 0, "unparsed": [], "problem flags": [],
                        "records with a format: problem": 0, "format problem modules": []},
             "model/effort pairs in records": Counter(), "request key mismatches": [],
             "assets": {"files": 0, "names": [], "not heldout": [], "missing heldout": []},
             "score": {"correct": 0, "listed": 0, "findable": 0},
             "leftovers": {}}
        for m in HELDOUT:
            p1 = rd / "phase1" / f"{m}.json"
            concepts = None
            raw1 = None
            if p1.exists():
                rec = json.loads(read(p1))
                r["phase1"]["present"] += 1
                s, u = system_text(version, 1), user_text(version, 1, m)
                if (rec.get("system sha"), rec.get("user sha")) == (sha12(s), sha12(u)) and rec.get("module") == m \
                        and rec.get("phase") == 1 and rec.get("prompt version") == version and rec.get("input version") == "v1":
                    r["phase1"]["rebuilt ok"] += 1
                else:
                    r["phase1"]["mismatch"].append({"module": m, "stored": (rec.get("system sha"), rec.get("user sha")),
                                                    "rebuilt": (sha12(s), sha12(u)), "module field": rec.get("module"),
                                                    "phase": rec.get("phase"), "prompt version": rec.get("prompt version")})
                if (rec.get("usage") or {}).get("request key") != sha12(s + "\n\n" + u):
                    r["request key mismatches"].append(f"{m} phase 1")
                r["model/effort pairs in records"][((rec.get("usage") or {}).get("model"), (rec.get("usage") or {}).get("effort"))] += 1
                raw1 = rec.get("raw")
                try:
                    obj = parse_json(raw1)
                    ok = isinstance(obj, dict) and isinstance(rec.get("reply"), dict)
                except (ValueError, TypeError):
                    ok = False
                if ok:
                    r["phase1"]["parsed"] += 1
                    concepts = obj.get("Conceptual Assets")
                else:
                    r["phase1"]["unparsed"].append(m)
                flags = [p for p in rec.get("problems", []) if str(p).startswith(("unparseable", "check crashed"))
                         or p == "not checked yet"] + (["check crashed"] if rec.get("check crashed") else [])
                if flags:
                    r["phase1"]["problem flags"].append({"module": m, "flags": flags})
            p2 = rd / "phase2" / f"{m}.json"
            if p2.exists():
                rec = json.loads(read(p2))
                r["phase2"]["present"] += 1
                s = system_text(version, 2)
                if concepts is None:
                    r["phase2"]["mismatch"].append({"module": m, "reason": "no parsed Phase 1 concepts to rebuild from"})
                else:
                    u = user_text(version, 2, m, concepts)
                    if (rec.get("system sha"), rec.get("user sha")) == (sha12(s), sha12(u)) and rec.get("module") == m \
                            and rec.get("phase") == 2 and rec.get("prompt version") == version and rec.get("input version") == "v1":
                        r["phase2"]["rebuilt ok"] += 1
                    else:
                        r["phase2"]["mismatch"].append({"module": m, "stored": (rec.get("system sha"), rec.get("user sha")),
                                                        "rebuilt": (sha12(s), sha12(u)), "module field": rec.get("module"),
                                                        "phase": rec.get("phase"), "prompt version": rec.get("prompt version")})
                    if (rec.get("usage") or {}).get("request key") != sha12(s + "\n\n" + u):
                        r["request key mismatches"].append(f"{m} phase 2")
                r["model/effort pairs in records"][((rec.get("usage") or {}).get("model"), (rec.get("usage") or {}).get("effort"))] += 1
                try:
                    obj = parse_json(rec.get("raw"))
                    ok = isinstance(obj, dict) and isinstance(rec.get("reply"), dict)
                except (ValueError, TypeError):
                    ok = False
                if ok:
                    r["phase2"]["parsed"] += 1
                else:
                    r["phase2"]["unparsed"].append(m)
                probs = rec.get("problems", [])
                if any(str(p).startswith("format:") for p in probs):
                    r["phase2"]["records with a format: problem"] += 1
                    r["phase2"]["format problem modules"].append(
                        {"module": m, "format problems": [p for p in probs if str(p).startswith("format:")]})
                flags = [p for p in probs if str(p).startswith(("unparseable", "check crashed"))
                         or p == "not checked yet"] + (["check crashed"] if rec.get("check crashed") else [])
                if flags:
                    r["phase2"]["problem flags"].append({"module": m, "flags": flags})
        # asset files and the exact score
        afiles = sorted((rd / "assets").glob("*.json")) if (rd / "assets").exists() else []
        names = [f.stem for f in afiles]
        r["assets"]["files"] = len(afiles)
        r["assets"]["names"] = names
        r["assets"]["not heldout"] = [n for n in names if n not in HELDOUT]
        r["assets"]["missing heldout"] = [m for m in HELDOUT if m not in names]
        per_mod = {}
        for m in HELDOUT:
            f = rd / "assets" / f"{m}.json"
            if not f.exists():
                continue
            a = json.loads(read(f))
            listed = [x.get("Asset RTL") for x in a.get("Assets", [])]
            sc = exact_score(listed, reference_rows(m))
            per_mod[m] = sc
            for k in sc:
                r["score"][k] += sc[k]
        r["score"]["modules scored"] = len(per_mod)
        r["score"]["precision"] = round(r["score"]["correct"] / r["score"]["listed"], 4) if r["score"]["listed"] else None
        r["score"]["recall"] = round(r["score"]["correct"] / r["score"]["findable"], 4) if r["score"]["findable"] else None
        # leftovers: pending ids, failed calls, partial texts, schema-failed moves
        pend = sorted(p.name for p in (rd / "_pending").iterdir()) if (rd / "_pending").exists() else []
        fl = rd / "_failed_calls.jsonl"
        failed_lines = [l for l in read(fl).splitlines() if l.strip()] if fl.exists() else []
        partial = sorted(p.name for p in (rd / "_failed").iterdir()) if (rd / "_failed").exists() else []
        sf = sorted(str(p.relative_to(rd)) for p in (rd / "_schema_failed").rglob("*")) if (rd / "_schema_failed").exists() else []
        r["leftovers"] = {"_pending dir exists": (rd / "_pending").exists(), "_pending files": pend,
                          "_failed_calls.jsonl exists": fl.exists(), "failed call lines": len(failed_lines),
                          "_failed partial texts": partial, "_schema_failed entries": sf}
        r["model/effort pairs in records"] = {f"{k[0]}/{k[1]}": v for k, v in r["model/effort pairs in records"].items()}
        out["runs"][rd.name] = r
    return out


def main() -> int:
    fails = selftest()
    if fails:
        print("SELF-TEST FAILED:", fails)
        return 1
    print("self-test passed (5 checks)")
    print(f"held-out modules: {len(HELDOUT)}")
    res = {"heldout modules": HELDOUT, "versions": {v: check_version(v) for v in VERSIONS}}
    out = Path(__file__).resolve().parent / "verify_results.json"
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for v, x in res["versions"].items():
        print(f"\n== {v}  ({x['folder']})")
        print(f"   rebuilt system sha: phase1 {x['rebuilt system sha'][1]}  phase2 {x['rebuilt system sha'][2]}; "
              f"user template sha: phase1 {x['rebuilt user template sha'][1]}  phase2 {x['rebuilt user template sha'][2]}")
        for rk, r in x["runs"].items():
            p1, p2 = r["phase1"], r["phase2"]
            print(f"  {rk}: executor {r['executor']}; run-meta mismatches {r['run meta mismatches'] or 'none'}")
            print(f"     phase1: present {p1['present']}, rebuilt ok {p1['rebuilt ok']}, mismatches {len(p1['mismatch'])}, "
                  f"parsed {p1['parsed']}, unparsed {p1['unparsed']}, problem flags {p1['problem flags']}")
            print(f"     phase2: present {p2['present']}, rebuilt ok {p2['rebuilt ok']}, mismatches {len(p2['mismatch'])}, "
                  f"parsed {p2['parsed']}, unparsed {p2['unparsed']}, problem flags {p2['problem flags']}")
            print(f"     phase2 records with a 'format:' problem: {p2['records with a format: problem']} "
                  f"{[d['module'] for d in p2['format problem modules']]}")
            print(f"     model/effort in records: {r['model/effort pairs in records']}; request-key mismatches {r['request key mismatches'] or 'none'}")
            print(f"     assets: {r['assets']['files']} files; not held-out {r['assets']['not heldout']}; missing {r['assets']['missing heldout']}")
            print(f"     exact score: {r['score']}")
            print(f"     leftovers: {r['leftovers']}")
            for d in p1["mismatch"] + p2["mismatch"]:
                print("     MISMATCH", d)
    print(f"\nresults written to {out}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
