"""Rebuild check of the stored records of two prompt versions (two_phase_v9n_place_dbg, two_phase_v9n_place), held-out 26,
every run present. Independent of chain.py except chain.closed_names and chain.run_dir: the system prompt, the user
message, sha12 and the request key are recomputed here from lab/prompts/<version> and lab/inputs/v1.

  python -B verify_v9n.py

Self-tests first (a known sha256, a hand-made scorer case, my closed-set reading vs chain.closed_names, my system and
template shas vs the shas chain wrote to _run_meta.json). If any fails, nothing else is reported.
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
LAB = Path(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab")
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
import chain  # noqa: E402  -- only closed_names and run_dir are used

closed_names, run_dir = chain.closed_names, chain.run_dir

VERSIONS = ["two_phase_v9n_place_dbg", "two_phase_v9n_place"]
MODEL, EFFORT = "gpt-5.6-luna", "high"
INPUTS = LAB / "inputs" / "v1"
HELDOUT = sorted(p.name for p in (INPUTS / "heldout").iterdir() if p.is_dir())
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
BAD_PROBLEM = ("unparseable reply", "not checked yet", "check crashed")


# ----------------------------------------------------------------------------------------------- rebuild ---
def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def system(version: str, k: int) -> str:
    d = LAB / "prompts" / version
    return read(d / "common.md").rstrip() + "\n\n" + read(d / f"phase{k}.md")


def parse_json(text: str):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


def new_format(version: str, k: int) -> bool:
    t = read(LAB / "prompts" / version / f"phase{k}.md")
    i = t.rfind("\nOUTPUT")
    top = "Conceptual Assets" if k == 1 else "Concept Walks"
    return i >= 0 and f'"{top}": [' in t[i:]


def inputs(m: str) -> dict:
    d = INPUTS / "heldout" / m
    return {f: read(d / f) for f in ("rtl.txt", "closed_set.json", "diagram.txt")}


def user(version: str, k: int, m: str, concepts_text: str | None = None) -> str:
    t = read(LAB / "prompts" / version / f"phase{k}_user.md")
    if "{located}" in t:
        raise RuntimeError(f"{version} phase{k}_user.md has a {{located}} slot; this script does not rebuild it")
    x = inputs(m)
    vals = {"module": m, "rtl": x["rtl.txt"], "diagram": x["diagram.txt"],
            "closed_set": json.dumps(json.loads(x["closed_set.json"]), separators=(",", ":"))}
    if k == 2:
        vals["concepts"] = concepts_text
    return t.format(**vals)


def my_closed_names(m: str) -> set[tuple[str, str]]:
    cs = json.loads(inputs(m)["closed_set.json"])
    out = set()
    for e in cs["entity list"]:
        for x in e["port list"] + e["signal list"]:
            out.add((e["entity name"], x.get("port") or x.get("signal")))
            for f in x.get("fields", []):
                out.add((e["entity name"], f["field"]))
    return out


# ----------------------------------------------------------------------------------------------- scorer ---
def reference(m: str) -> list[str]:
    g = json.load(open(GT, encoding="utf-8"))["modules"]
    names = {n for (_, n) in closed_names(m)}
    return [r["element"] for r in g[m]["assets"] if r["element"] in names]


def score(listed_names: list[str], ref_rows: list[str]) -> tuple[int, int, int]:
    """(correct, listed, findable): reference rows walked in order; a row whose element still has a copy consumes one."""
    c = Counter(listed_names)
    correct = 0
    for el in ref_rows:
        if c[el] > 0:
            c[el] -= 1
            correct += 1
    return correct, len(listed_names), len(ref_rows)


# ----------------------------------------------------------------------------------------------- self-test ---
def selftest() -> bool:
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'ok  ' if cond else 'FAIL'} {label}")
    check("sha12('abc') == 'ba7816bf8f01' (sha256 of 'abc' = ba7816bf8f01cfea...)", sha12("abc") == "ba7816bf8f01")
    check("scorer hand case: listed [a,a,b], reference [a,a,a,c] -> (2, 3, 4)", score(["a", "a", "b"], ["a", "a", "a", "c"]) == (2, 3, 4))
    check("scorer hand case: empty listed -> (0, 0, n)", score([], ["a", "b"]) == (0, 0, 2))
    check("held-out folder has 26 modules", len(HELDOUT) == 26)
    same = all(my_closed_names(m) == set(closed_names(m)) for m in HELDOUT)
    check("my closed-set reading == chain.closed_names keys on all 26 modules", same)
    for v in VERSIONS:
        d = LAB / "prompts" / v
        for r in sorted((LAB / "runs" / f"{v}__v1" / f"{MODEL}__{EFFORT}").glob("r*")):
            meta = json.loads(read(r / "_run_meta.json"))
            for k in (1, 2):
                check(f"{v} {r.name}: my system sha phase {k} == _run_meta ({meta[f'system sha phase {k}']})",
                      sha12(system(v, k)) == meta[f"system sha phase {k}"])
                check(f"{v} {r.name}: my user template sha phase {k} == _run_meta ({meta[f'user template sha phase {k}']})",
                      sha12(read(d / f"phase{k}_user.md")) == meta[f"user template sha phase {k}"])
            man = INPUTS / "manifest.json"
            check(f"{v} {r.name}: inputs manifest sha == _run_meta ({meta['inputs manifest sha']})",
                  sha12(read(man)) == meta["inputs manifest sha"])
            check(f"{v} {r.name}: _run_meta model/effort == {MODEL}/{EFFORT}", (meta["model"], meta["effort"]) == (MODEL, EFFORT))
        check(f"{v}: new reply format (2026-10-13) in phase1.md and phase2.md", new_format(v, 1) and new_format(v, 2))
    # hand-read anchor (seen in the stored files before this script was written):
    rec = json.loads(read(run_dir("two_phase_v9n_place", MODEL, 0, EFFORT) / "phase1" / "neorv32_gpio.json"))
    check("hand-read anchor: place r0 gpio phase 1 request key 3ec84df74257 == sha12(system + two newlines + user)",
          rec["usage"]["request key"] == "3ec84df74257" == sha12(system("two_phase_v9n_place", 1) + "\n\n" + user("two_phase_v9n_place", 1, "neorv32_gpio")))
    return ok


# ----------------------------------------------------------------------------------------------- one run ---
def check_run(version: str, run: Path) -> dict:
    res = {"version": version, "run": run.name, "records expected": 2 * len(HELDOUT), "records present": 0,
           "rebuilt (system sha, user sha and request key all match)": 0, "mismatches": [],
           "meta mismatches (module/phase/prompt version/input version)": [],
           "model/effort of records": Counter(), "parsed replies": 0, "unparsed or unchecked": [],
           "phase 1 records": 0, "phase 2 records": 0,
           "phase 2 records with a format problem": [], "assets files in folder": 0, "assets files for the 26": 0,
           "assets files not for a held-out module": [], "pending files": [], "failed-call files": [],
           "other leftover folders": [], "keys.jsonl lines": 0, "keys.jsonl distinct": 0,
           "keys.jsonl keys with no stored record": [], "stored records whose key is not in keys.jsonl": [],
           "score": {}}
    stored_keys = set()
    correct = listed = findable = 0
    sys1, sys2 = system(version, 1), system(version, 2)
    for m in HELDOUT:
        usr1 = user(version, 1, m)
        concepts_text = None
        for k, s in ((1, sys1), (2, sys2)):
            p = run / f"phase{k}" / f"{m}.json"
            if not p.exists():
                res["mismatches"].append(f"{m} phase {k}: no record")
                continue
            res["records present"] += 1
            res[f"phase {k} records"] += 1
            rec = json.loads(read(p))
            if k == 2:
                if concepts_text is None:
                    res["mismatches"].append(f"{m} phase 2: Phase 1 concepts could not be rebuilt")
                    continue
                u = user(version, 2, m, concepts_text)
            else:
                u = usr1
            ss, us, key = sha12(s), sha12(u), sha12(s + "\n\n" + u)
            usage = rec.get("usage") or {}
            stored_keys.add(usage.get("request key"))
            bad = []
            if rec.get("system sha") != ss:
                bad.append(f"system sha {rec.get('system sha')} vs rebuilt {ss}")
            if rec.get("user sha") != us:
                bad.append(f"user sha {rec.get('user sha')} vs rebuilt {us}")
            if usage.get("request key") != key:
                bad.append(f"request key {usage.get('request key')} vs rebuilt {key}")
            if bad:
                res["mismatches"].append(f"{m} phase {k}: " + "; ".join(bad))
            else:
                res["rebuilt (system sha, user sha and request key all match)"] += 1
            want = {"module": m, "phase": k, "prompt version": version, "input version": "v1"}
            off = {f: rec.get(f) for f in want if rec.get(f) != want[f]}
            if off:
                res["meta mismatches (module/phase/prompt version/input version)"].append(f"{m} phase {k}: {off}")
            res["model/effort of records"][f"{usage.get('model')}/{usage.get('effort')}"] += 1
            # parsed: the raw text parses here, the stored reply is an object, and no problem says otherwise
            try:
                parsed = parse_json(rec["raw"])
                parsed_ok = isinstance(parsed, dict)
            except ValueError:
                parsed, parsed_ok = None, False
            probs = [str(x) for x in rec.get("problems", [])]
            if parsed_ok and isinstance(rec.get("reply"), dict) and not rec.get("check crashed") \
                    and not any(x.startswith(BAD_PROBLEM) for x in probs):
                res["parsed replies"] += 1
            else:
                res["unparsed or unchecked"].append(f"{m} phase {k}: {probs[:2]}")
            if k == 1 and parsed_ok:
                concepts = parsed.get("Conceptual Assets") if new_format(version, 1) else (rec.get("reply") or {}).get("conceptual assets")
                if concepts is not None:
                    concepts_text = json.dumps(concepts, indent=1, ensure_ascii=False)
            if k == 2 and any(x.startswith("format:") for x in probs):
                res["phase 2 records with a format problem"].append(m)
        a = run / "assets" / f"{m}.json"
        if a.exists():
            res["assets files for the 26"] += 1
            rows = json.load(open(a, encoding="utf-8"))["Assets"]
            c, l, f = score([r["Asset RTL"] for r in rows], reference(m))
            correct, listed, findable = correct + c, listed + l, findable + f
    res["assets files in folder"] = len(list((run / "assets").glob("*.json")))
    res["assets files not for a held-out module"] = sorted(p.stem for p in (run / "assets").glob("*.json") if p.stem not in HELDOUT)
    res["pending files"] = sorted(p.name for p in (run / "_pending").glob("*")) if (run / "_pending").exists() else []
    fc = run / "_failed_calls.jsonl"
    if fc.exists():
        res["failed-call files"].append(f"_failed_calls.jsonl ({len([l for l in read(fc).splitlines() if l.strip()])} lines)")
    if (run / "_failed").exists():
        res["failed-call files"] += [f"_failed/{p.name}" for p in (run / "_failed").glob("*")]
    for d in ("_schema_failed", "_broken"):
        if (run / d).exists():
            res["other leftover folders"] += [p.relative_to(run).as_posix() for p in (run / d).rglob("*") if p.is_file()]
    kl = run / "_keys.jsonl"
    keys, bad_lines = [], 0
    for l in (read(kl).splitlines() if kl.exists() else []):
        if not l.strip():
            continue
        try:
            keys.append(json.loads(l)["key"])
        except (ValueError, KeyError, TypeError):   # two workers appended at once: keys are pulled from the text instead
            bad_lines += 1
            keys += re.findall(r'"key": "([0-9a-f]{12})"', l)
    res["keys.jsonl lines"], res["keys.jsonl distinct"] = len(keys), len(set(keys))
    res["keys.jsonl lines that are not one JSON object"] = bad_lines
    res["keys.jsonl keys with no stored record"] = sorted(set(keys) - stored_keys)
    res["stored records whose key is not in keys.jsonl"] = sorted(k for k in stored_keys if k and k not in set(keys))
    res["model/effort of records"] = dict(res["model/effort of records"])
    res["score"] = {"correct": correct, "listed": listed, "findable": findable,
                    "precision": round(correct / listed, 3) if listed else None,
                    "recall": round(correct / findable, 3) if findable else None,
                    "modules scored": res["assets files for the 26"]}
    return res


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    print("SELF-TEST")
    if not selftest():
        print("SELF-TEST FAILED: nothing reported")
        return 1
    print("self-test passed\n")
    out = []
    for v in VERSIONS:
        base = LAB / "runs" / f"{v}__v1" / f"{MODEL}__{EFFORT}"
        runs = sorted(base.glob("r*"), key=lambda p: int(p.name[1:]))
        assert all(run_dir(v, MODEL, int(r.name[1:]), EFFORT) == r for r in runs)
        for r in runs:
            out.append(check_run(v, r))
    print("PER RUN")
    for x in out:
        print(json.dumps(x, indent=1, ensure_ascii=False))
    print("\nSUMMARY")
    for x in out:
        s = x["score"]
        fmt = x["phase 2 records with a format problem"]
        print(f"{x['version']:28s} {x['run']}: records {x['records present']}/{x['records expected']}, "
              f"rebuilt {x['rebuilt (system sha, user sha and request key all match)']}, mismatches {len(x['mismatches'])}, "
              f"parsed {x['parsed replies']}, assets {x['assets files for the 26']}/{x['assets files in folder']}, "
              f"P2 format problems {len(fmt)} {fmt}, pending {len(x['pending files'])}, failed {x['failed-call files']}, "
              f"other {x['other leftover folders']}, keys {x['keys.jsonl lines']}/{x['keys.jsonl distinct']}, "
              f"model/effort {x['model/effort of records']}, score {s['correct']}/{s['listed']} listed, "
              f"{s['correct']}/{s['findable']} findable (P {s['precision']}, R {s['recall']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
