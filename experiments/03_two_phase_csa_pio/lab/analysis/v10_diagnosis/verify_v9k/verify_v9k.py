"""Rebuild every stored two_phase_v9k request from the prompt files and the inputs, and compare its hashes with the
stored record. Own code only: no run_*.py, no API call. chain.py / check_lab_prompt.py are imported once, inside the
self-test, as a cross-check of the rebuilt texts; no reported number comes from them.

    python -B verify_v9k.py

Hash scheme (chain.py _ask / openai executor): system sha = sha12(system), user sha = sha12(user),
request key = sha12(system + "\\n\\n" + user), sha12 = sha256 hex[:12].
system = common.md.rstrip() + "\\n\\n" + phase<k>.md (check_lab_prompt.system).
user = phase<k>_user.md.format(module, rtl, diagram, closed_set compact JSON[, concepts]) (chain.user_message);
concepts = json.dumps(Phase 1 raw reply's "Conceptual Assets", indent=1, ensure_ascii=False).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]                                   # .../experiments/03_two_phase_csa_pio/lab
VERSION = "two_phase_v9k"
MODEL_DIR = "gpt-5.6-luna__high"
RUNS = [LAB / "runs" / f"{VERSION}__v1" / MODEL_DIR / f"r{k}" for k in (0, 1, 2)]
PROMPTS = LAB / "prompts" / VERSION
INPUTS = LAB / "inputs" / "v1"


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def parse_json(text: str) -> dict:
    """Same rule as labkit.parse_json, written here: strip a code fence, take the outermost braces."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


def module_dir(m: str) -> Path:
    for split in ("tuning", "heldout"):
        d = INPUTS / split / m
        if d.exists():
            return d
    raise FileNotFoundError(m)


def system_text(phase: int) -> str:
    common = (PROMPTS / "common.md").read_text(encoding="utf-8")
    ph = (PROMPTS / f"phase{phase}.md").read_text(encoding="utf-8")
    return common.rstrip() + "\n\n" + ph


def user_text(phase: int, m: str, concepts=None) -> str:
    d = module_dir(m)
    t = (PROMPTS / f"phase{phase}_user.md").read_text(encoding="utf-8")
    cs = json.loads((d / "closed_set.json").read_text(encoding="utf-8"))
    vals = {"module": m, "rtl": (d / "rtl.txt").read_text(encoding="utf-8"),
            "diagram": (d / "diagram.txt").read_text(encoding="utf-8"),
            "closed_set": json.dumps(cs, separators=(",", ":"))}
    if phase == 2:
        vals["concepts"] = json.dumps(concepts, indent=1, ensure_ascii=False)
    return t.format(**vals)


def selftest() -> list[str]:
    """Hand-checkable facts the hashing must reproduce, plus a negative control."""
    fails = []
    # sha256("abc") = ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad (FIPS 180 example)
    if sha12("abc") != "ba7816bf8f01":
        fails.append(f"sha12('abc') = {sha12('abc')}, expected ba7816bf8f01")
    # one changed character must change the hash (negative control)
    u = user_text(1, "neorv32_wdt")
    if sha12(u) == sha12(u[:-1] + ("x" if u[-1] != "x" else "y")):
        fails.append("negative control: a changed user text gave the same sha12")
    # the rebuilt user text must contain the template markers
    if "MODULE: neorv32_wdt" not in u or "=== CLOSED SET (JSON) ===" not in u:
        fails.append("user text lacks the template markers")
    # cross-check against the lab's own builders (allowed imports; not used for any reported number)
    try:
        os.environ["PIO_INPUT_VERSION"] = "v1"
        sys.path.insert(0, str(LAB))
        import chain  # noqa: E402
        import check_lab_prompt as C  # noqa: E402
        if C.system(VERSION, 1) != system_text(1) or C.system(VERSION, 2) != system_text(2):
            fails.append("system text differs from check_lab_prompt.system")
        if chain.user_message(VERSION, 1, "neorv32_wdt") != u:
            fails.append("phase 1 user text differs from chain.user_message")
    except Exception as e:  # noqa: BLE001
        fails.append(f"cross-check import failed: {type(e).__name__}: {e}")
    return fails


def count_lines(p: Path) -> int:
    return len([l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]) if p.exists() else 0


def count_files(p: Path, pattern: str = "*") -> int:
    return len([x for x in p.rglob(pattern) if x.is_file()]) if p.exists() else 0


def main() -> dict:
    st = selftest()
    out = {"selftest": "PASS" if not st else f"FAIL: {st}"}
    if st:
        print(json.dumps(out, indent=1))
        return out
    sys_sha = {1: sha12(system_text(1)), 2: sha12(system_text(2))}
    out["system sha rebuilt"] = {f"phase {k}": v for k, v in sys_sha.items()}
    out["user template sha rebuilt"] = {f"phase {k}": sha12((PROMPTS / f"phase{k}_user.md").read_text(encoding="utf-8"))
                                        for k in (1, 2)}
    meta_sha, per_run, mismatches = {}, {}, []
    for rd in RUNS:
        r = rd.name
        meta = json.loads((rd / "_run_meta.json").read_text(encoding="utf-8"))
        meta_sha[r] = {k: meta.get(k) for k in ("prompt version", "input version", "model", "effort", "executor",
                                                  "system sha phase 1", "system sha phase 2",
                                                  "user template sha phase 1", "user template sha phase 2")}
        mods = sorted(p.stem for p in (rd / "phase1").glob("*.json"))
        mods2 = sorted(p.stem for p in (rd / "phase2").glob("*.json"))
        assets = sorted(p.stem for p in (rd / "assets").glob("*.json"))
        row = {"phase1 files": len(mods), "phase2 files": len(mods2), "assets files": len(assets),
               "rebuilt": 0, "system sha match": 0, "user sha match": 0, "request key match": 0,
               "parsed phase1": 0, "parsed phase2": 0, "phase2 with format: problem": 0,
               "phase1 with any problem": 0, "phase2 with any problem": 0,
               "models": Counter(), "efforts": Counter(),
               "modules not in both phases": sorted(set(mods) ^ set(mods2)),
               "assets missing for": sorted(set(mods) - set(assets))}
        for m in mods:
            rec1 = json.loads((rd / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
            concepts = None
            try:
                concepts = parse_json(rec1["raw"]).get("Conceptual Assets")
            except (ValueError, TypeError, AttributeError):
                concepts = None
            recs = [(1, rec1, None)]
            if m in mods2:
                recs.append((2, json.loads((rd / "phase2" / f"{m}.json").read_text(encoding="utf-8")), concepts))
            for ph, rec, cc in recs:
                s = system_text(ph)
                u = user_text(ph, m, cc)
                row["rebuilt"] += 1
                usage = rec.get("usage") or {}
                ok_s = rec.get("system sha") == sha12(s)
                ok_u = rec.get("user sha") == sha12(u)
                ok_k = usage.get("request key") == sha12(s + "\n\n" + u)
                row["system sha match"] += ok_s
                row["user sha match"] += ok_u
                row["request key match"] += ok_k
                if not (ok_s and ok_u and ok_k):
                    mismatches.append({"run": r, "module": m, "phase": ph, "system": ok_s, "user": ok_u, "key": ok_k,
                                       "stored": [rec.get("system sha"), rec.get("user sha"), usage.get("request key")],
                                       "rebuilt": [sha12(s), sha12(u), sha12(s + "\n\n" + u)]})
                row["models"][usage.get("model")] += 1
                row["efforts"][usage.get("effort")] += 1
                probs = rec.get("problems") or []
                reply = rec.get("reply")
                crashed = bool(rec.get("check crashed")) or probs == ["not checked yet"] \
                    or any(str(p).startswith("unparseable reply") for p in probs)
                if ph == 1:
                    parsed = isinstance(reply, dict) and isinstance(reply.get("conceptual assets"), list) \
                        and all(isinstance(c, dict) for c in reply["conceptual assets"]) and not crashed
                    row["parsed phase1"] += parsed
                    row["phase1 with any problem"] += bool(probs)
                else:
                    parsed = isinstance(reply, dict) and isinstance(reply.get("points"), list) \
                        and isinstance(reply.get("structural assets"), list) and not crashed
                    row["parsed phase2"] += parsed
                    row["phase2 with any problem"] += bool(probs)
                    row["phase2 with format: problem"] += any(str(p).startswith("format:") for p in probs)
        row["models"] = dict(row["models"])
        row["efforts"] = dict(row["efforts"])
        row["_pending files"] = count_files(rd / "_pending")
        row["_failed_calls.jsonl lines"] = count_lines(rd / "_failed_calls.jsonl")
        row["_failed files"] = count_files(rd / "_failed")
        row["_schema_failed files"] = count_files(rd / "_schema_failed", "*.json")
        row["_keys.jsonl lines"] = count_lines(rd / "_keys.jsonl")
        per_run[r] = row
    out["run meta"] = meta_sha
    out["meta system sha matches rebuilt"] = {r: (v["system sha phase 1"] == sys_sha[1] and v["system sha phase 2"] == sys_sha[2])
                                              for r, v in meta_sha.items()}
    out["meta user template sha matches rebuilt"] = {
        r: (v["user template sha phase 1"] == out["user template sha rebuilt"]["phase 1"]
            and v["user template sha phase 2"] == out["user template sha rebuilt"]["phase 2"]) for r, v in meta_sha.items()}
    out["per run"] = per_run
    keys = ("rebuilt", "system sha match", "user sha match", "request key match", "assets files", "parsed phase1",
            "parsed phase2", "phase2 with format: problem", "phase2 with any problem", "phase1 with any problem",
            "_pending files", "_failed_calls.jsonl lines", "_failed files", "_schema_failed files")
    out["totals"] = {k: sum(v[k] for v in per_run.values()) for k in keys}
    out["totals"]["mismatches"] = len(mismatches)
    out["mismatches"] = mismatches
    (HERE / "verify_v9k_result.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
