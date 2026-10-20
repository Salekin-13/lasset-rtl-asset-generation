"""Independent re-derivation: can every stored two_phase_v9g request be rebuilt from the prompt folder and the inputs?

Follows chain.py's construction without importing it (only the stdlib is used):
  system(phase)  = common.md.rstrip() + "\n\n" + phase<k>.md                      (check_lab_prompt.system)
  user(phase 1)  = phase1_user.md.format(module, rtl, closed_set=compact JSON, diagram)   (chain.user_message)
  user(phase 2)  = phase2_user.md.format(..., concepts=json.dumps(<Phase 1 raw reply>["Conceptual Assets"],
                                                                indent=1, ensure_ascii=False))
  sha12(t)       = sha256(t.encode("utf-8")).hexdigest()[:12]                     (chain.sha12 / labkit.sha12)
  request key    = sha12(system + "\n\n" + user)                                  (chain.openai.f / _ask)
Every file is read with Path.read_text(encoding="utf-8"), as chain.py does (so "\r\n" becomes "\n" the same way).

  python -B rebuild_requests.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

LAB = Path(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab")
VERSION = "two_phase_v9g"
PROMPTS = LAB / "prompts" / VERSION
INPUTS = LAB / "inputs" / "v1"
RUN = LAB / "runs" / f"{VERSION}__v1" / "gpt-5.6-luna__high"
REPS = ("r0", "r1", "r2")
WANT_MODEL, WANT_EFFORT = "gpt-5.6-luna", "high"
OUT = Path(__file__).resolve().parent / "rebuild_result.json"


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def system(phase: int) -> str:
    return read(PROMPTS / "common.md").rstrip() + "\n\n" + read(PROMPTS / f"phase{phase}.md")


def module_dir(m: str) -> Path:
    for split in ("tuning", "heldout"):           # chain.module_dir looks in tuning first
        d = INPUTS / split / m
        if d.exists():
            return d
    raise FileNotFoundError(m)


def user_message(phase: int, m: str, concepts=None) -> str:
    d = module_dir(m)
    t = read(PROMPTS / f"phase{phase}_user.md")
    vals = {"module": m, "rtl": read(d / "rtl.txt"), "diagram": read(d / "diagram.txt"),
            "closed_set": json.dumps(json.loads(read(d / "closed_set.json")), separators=(",", ":"))}
    if phase == 2:
        vals["concepts"] = json.dumps(concepts, indent=1, ensure_ascii=False)
    return t.format(**vals)


def parse_json(text: str):
    """labkit.parse_json, re-written: strip a code fence, take the outermost {...}."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


def new_format(phase: int) -> bool:
    """chain.new_format: the OUTPUT section of phase<k>.md shows the 2026-10-13 top-level list."""
    t = read(PROMPTS / f"phase{phase}.md")
    i = t.rfind("\nOUTPUT")
    top = "Conceptual Assets" if phase == 1 else "Concept Walks"
    return i >= 0 and f'"{top}": [' in t[i:]


def has_parsed_reply(rec: dict, phase: int) -> tuple[bool, str]:
    """A record has a parsed reply when 'reply' is an object the checks ran on, and the raw text re-parses here into
    the phase's top-level list."""
    probs = rec.get("problems")
    if rec.get("check crashed"):
        return False, "check crashed"
    if probs == ["not checked yet"]:
        return False, "not checked yet"
    if any(str(p).startswith("unparseable reply") for p in (probs or [])):
        return False, "stored as unparseable"
    if not isinstance(rec.get("reply"), dict):
        return False, f"'reply' is {type(rec.get('reply')).__name__}"
    try:
        obj = parse_json(rec["raw"])
    except ValueError as e:
        return False, f"raw does not re-parse here: {e}"
    top = "Conceptual Assets" if phase == 1 else "Concept Walks"
    if not isinstance(obj, dict) or not isinstance(obj.get(top), list):
        return False, f"raw has no '{top}' list"
    v5 = "conceptual assets" if phase == 1 else "structural assets"
    if not isinstance(rec["reply"].get(v5), list):
        return False, f"'reply' has no '{v5}' list"
    return True, ""


# ------------------------------------------------------------------------------------------------ self-test ---
def selftest() -> list[str]:
    fails = []
    # 1. the hash helper against the published SHA-256 of "abc"
    if sha12("abc") != "ba7816bf8f01":
        fails.append(f"sha12('abc') = {sha12('abc')}, expected ba7816bf8f01")
    # 2. the template fill: the message starts with the module line and holds the RTL file verbatim
    m = "neorv32_gpio"
    u = user_message(1, m)
    rtl = read(module_dir(m) / "rtl.txt")
    if not u.startswith(f"MODULE: {m}\n"):
        fails.append("phase 1 user message does not start with the MODULE line")
    if rtl not in u:
        fails.append("phase 1 user message does not hold rtl.txt verbatim")
    if not u.endswith(f"Do Phase 1 for module '{m}' and return the JSON object.\n") and \
       not u.endswith(f"Do Phase 1 for module '{m}' and return the JSON object."):
        fails.append("phase 1 user message does not end with the closing line")
    # 3. negative control: one changed character must change the sha (the comparison can fail)
    if sha12(u) == sha12(u + " "):
        fails.append("sha12 did not change on a one-character change")
    # 4. the formats both phases are read in
    if not (new_format(1) and new_format(2)):
        fails.append(f"new_format: phase1={new_format(1)} phase2={new_format(2)}; expected both True for v9g")
    return fails


# ------------------------------------------------------------------------------------------------ main ---
def main() -> int:
    st = selftest()
    print("SELF-TEST:", "PASS" if not st else "FAIL " + "; ".join(st))
    if st:
        return 1

    sys1, sys2 = system(1), system(2)
    ss = {1: sha12(sys1), 2: sha12(sys2)}
    tmpl = {k: sha12(read(PROMPTS / f"phase{k}_user.md")) for k in (1, 2)}
    man_sha = sha12(read(INPUTS / "manifest.json"))
    print(f"system sha phase 1 = {ss[1]}  phase 2 = {ss[2]}  user template sha 1 = {tmpl[1]}  2 = {tmpl[2]}  "
          f"manifest sha = {man_sha}")

    heldout = sorted(p.name for p in (INPUTS / "heldout").iterdir() if p.is_dir())
    res = {"records": 0, "exact": 0, "mismatch": [], "model_effort": Counter(), "parsed": 0, "unparsed": [],
           "problems_empty": 0, "run_meta": {}, "key_log": {}, "modules": {}, "field_mismatch": []}
    for rep in REPS:
        d = RUN / rep
        meta = json.loads(read(d / "_run_meta.json"))
        want_meta = {"prompt version": VERSION, "input version": "v1", "model": WANT_MODEL, "effort": WANT_EFFORT,
                     "system sha phase 1": ss[1], "system sha phase 2": ss[2],
                     "user template sha phase 1": tmpl[1], "user template sha phase 2": tmpl[2],
                     "inputs manifest sha": man_sha}
        res["run_meta"][rep] = {k: (meta.get(k) == v) for k, v in want_meta.items()}
        mods1 = sorted(p.stem for p in (d / "phase1").glob("*.json"))
        mods2 = sorted(p.stem for p in (d / "phase2").glob("*.json"))
        res["modules"][rep] = {"phase1": len(mods1), "phase2": len(mods2),
                               "phase1 == heldout folder": mods1 == heldout, "phase2 == phase1": mods2 == mods1,
                               "extra folders": sorted(p.name for p in d.iterdir()
                                                       if p.name not in ("phase1", "phase2", "assets", "_keys.jsonl",
                                                                         "_pending", "_run_meta.json"))}
        keys_stored = {}
        for m in mods1:
            # ---- phase 1
            r1 = json.loads(read(d / "phase1" / f"{m}.json"))
            u1 = user_message(1, m)
            k1 = sha12(sys1 + "\n\n" + u1)
            recs = [(1, r1, u1, k1)]
            # ---- phase 2 (needs Phase 1's concepts as written in the raw reply)
            p2 = d / "phase2" / f"{m}.json"
            if p2.exists():
                r2 = json.loads(read(p2))
                try:
                    concepts = parse_json(r1["raw"]).get("Conceptual Assets")
                    u2 = user_message(2, m, concepts)
                    k2 = sha12(sys2 + "\n\n" + u2)
                except (ValueError, KeyError, AttributeError) as e:
                    u2, k2 = None, f"(cannot build: {e})"
                recs.append((2, r2, u2, k2))
            for ph, rec, u, key in recs:
                res["records"] += 1
                name = f"{rep}/phase{ph}/{m}"
                why = []
                if rec.get("system sha") != ss[ph]:
                    why.append(f"system sha {rec.get('system sha')} != rebuilt {ss[ph]}")
                if u is None:
                    why.append(f"user message cannot be rebuilt {key}")
                elif rec.get("user sha") != sha12(u):
                    why.append(f"user sha {rec.get('user sha')} != rebuilt {sha12(u)}")
                usage = rec.get("usage") or {}
                if usage.get("request key") != key:
                    why.append(f"request key {usage.get('request key')} != rebuilt {key}")
                if why:
                    res["mismatch"].append({"record": name, "why": why})
                else:
                    res["exact"] += 1
                    keys_stored[key] = (m, ph)
                res["model_effort"][(usage.get("model"), usage.get("effort"))] += 1
                for k, v in (("module", m), ("phase", ph), ("prompt version", VERSION), ("input version", "v1")):
                    if rec.get(k) != v:
                        res["field_mismatch"].append(f"{name}: {k} = {rec.get(k)!r}")
                ok, reason = has_parsed_reply(rec, ph)
                if ok:
                    res["parsed"] += 1
                    if rec.get("problems") == []:
                        res["problems_empty"] += 1
                else:
                    res["unparsed"].append({"record": name, "why": reason})
        # ---- the key log: every stored record's key must be logged for its module and phase
        lines = [json.loads(l) for l in read(d / "_keys.jsonl").splitlines() if l.strip()]
        logged = Counter((x["key"], x["module"], x["phase"]) for x in lines)
        missing = [k for k, (m, ph) in keys_stored.items() if (k, m, ph) not in logged]
        no_record = sorted({(x["module"], x["phase"]) for x in lines if x["key"] not in keys_stored})
        repeated = sorted((m, ph, n) for (k, m, ph), n in logged.items() if n > 1)
        res["key_log"][rep] = {"lines": len(lines), "distinct keys": len({x["key"] for x in lines}),
                               "stored keys not logged": missing, "logged keys with no stored record": no_record,
                               "same key logged more than once (module, phase, times)": repeated,
                               "pending files": sorted(p.name for p in (d / "_pending").iterdir())}

    res["model_effort"] = {f"{m} / {e}": n for (m, e), n in res["model_effort"].items()}
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
