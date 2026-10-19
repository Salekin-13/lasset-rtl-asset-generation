"""Rebuild check for the stored two_phase_v9i run-0 records (gpt-5.6-luna, high).

Own code only: nothing is imported from chain.py or labkit.py. The message-building rules are copied by hand from
chain.py (user_message, _ask, sha12) and check_lab_prompt.py (system): read 2026-10-18.

  sha12(t)  = sha256(t.encode("utf-8")).hexdigest()[:12]
  system_k  = common.md.rstrip() + "\\n\\n" + phase<k>.md
  user_k    = phase<k>_user.md.format(module=m, rtl=rtl.txt, diagram=diagram.txt,
                                      closed_set=json.dumps(json.loads(closed_set.json), separators=(",", ":")),
                                      [concepts=json.dumps(<Phase 1 raw reply>["Conceptual Assets"], indent=1,
                                                           ensure_ascii=False)  for k == 2])
  stored    = record["system sha"], record["user sha"], record["usage"]["request key"] == sha12(system+"\\n\\n"+user)

No API call is made. Run:  python -B verify_v9i.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

LAB = Path(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab")
INPUTS = LAB / "inputs" / "v1"
HERE = Path(__file__).resolve().parent

RUN_V9I = LAB / "runs" / "two_phase_v9i__v1" / "gpt-5.6-luna__high" / "r0"
RUN_V9H = LAB / "runs" / "two_phase_v9h__v1" / "gpt-5.6-luna__high" / "r0"
PROMPTS_V9I = LAB / "prompts" / "two_phase_v9i"

# Hand-read from the files on 2026-10-18 (printed in the session before this script was written):
#   _run_meta.json of v9i r0: "system sha phase 1": "66fc3990b91c", "system sha phase 2": "d2539af80a7e"
#   phase1/neorv32_gpio.json: "system sha": "66fc3990b91c", "user sha": "44588a2b9271", usage "request key": "52addd7839e3"
#   phase2/neorv32_gpio.json: "system sha": "d2539af80a7e", "user sha": "28d36f5dc9f1", usage "request key": "24bd6ab56a20"
HAND_READ = {
    "system sha phase 1": "66fc3990b91c",
    "system sha phase 2": "d2539af80a7e",
    "gpio p1 user sha": "44588a2b9271",
    "gpio p1 request key": "52addd7839e3",
    "gpio p2 user sha": "28d36f5dc9f1",
    "gpio p2 request key": "24bd6ab56a20",
}


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def parse_json(text: str) -> dict:
    """Same rule as labkit.parse_json: strip a code fence, take the outermost {...}."""
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


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def system(prompts: Path, phase: int) -> str:
    return read(prompts / "common.md").rstrip() + "\n\n" + read(prompts / f"phase{phase}.md")


def user(prompts: Path, phase: int, m: str, concepts=None) -> str:
    d = module_dir(m)
    t = read(prompts / f"phase{phase}_user.md")
    vals = {"module": m, "rtl": read(d / "rtl.txt"), "diagram": read(d / "diagram.txt"),
            "closed_set": json.dumps(json.loads(read(d / "closed_set.json")), separators=(",", ":"))}
    if phase == 2:
        vals["concepts"] = json.dumps(concepts, indent=1, ensure_ascii=False)
    return t.format(**vals)


def load(p: Path) -> dict:
    return json.loads(read(p))


def parsed_ok(rec: dict) -> bool:
    """A record has a parsed reply when 'reply' is a dict, the raw text parses with the kit's rule, and no problem
    says the reply was unparseable, unchecked, or crashed the check."""
    bad = ("not checked yet", "unparseable reply", "check crashed")
    probs = [str(x) for x in rec.get("problems", [])]
    if any(p.startswith(b) for p in probs for b in bad) or rec.get("check crashed"):
        return False
    if not isinstance(rec.get("reply"), dict) or not rec["reply"]:
        return False
    try:
        parse_json(rec["raw"])
    except Exception:  # noqa: BLE001
        return False
    return True


def format_problem_counts(run: Path) -> dict:
    """Phase 2 records of one run: how many have at least one 'format:' problem, and how many such entries in all."""
    recs = sorted((run / "phase2").glob("*.json"))
    with_fmt, entries, examples = 0, 0, {}
    for p in recs:
        r = load(p)
        f = [str(x) for x in r.get("problems", []) if str(x).startswith("format:")]
        if f:
            with_fmt += 1
            entries += len(f)
            examples[p.stem] = f
    return {"phase 2 records": len(recs), "records with a format: problem": with_fmt,
            "format: entries in all": entries, "examples": examples}


def main() -> int:
    out = {"run": str(RUN_V9I), "prompts": str(PROMPTS_V9I)}

    # ---- self-test against hand-read values ---------------------------------------------------------------------
    s1, s2 = system(PROMPTS_V9I, 1), system(PROMPTS_V9I, 2)
    meta = load(RUN_V9I / "_run_meta.json")
    g1 = load(RUN_V9I / "phase1" / "neorv32_gpio.json")
    g2 = load(RUN_V9I / "phase2" / "neorv32_gpio.json")
    u1 = user(PROMPTS_V9I, 1, "neorv32_gpio")
    u2 = user(PROMPTS_V9I, 2, "neorv32_gpio", parse_json(g1["raw"]).get("Conceptual Assets"))
    selftest = {
        "system sha phase 1 == hand-read": sha12(s1) == HAND_READ["system sha phase 1"],
        "system sha phase 2 == hand-read": sha12(s2) == HAND_READ["system sha phase 2"],
        "hand-read system shas == _run_meta": (meta["system sha phase 1"], meta["system sha phase 2"])
                                               == (HAND_READ["system sha phase 1"], HAND_READ["system sha phase 2"]),
        "gpio p1 user sha == hand-read": sha12(u1) == HAND_READ["gpio p1 user sha"],
        "gpio p1 request key == hand-read": sha12(s1 + "\n\n" + u1) == HAND_READ["gpio p1 request key"],
        "gpio p2 user sha == hand-read": sha12(u2) == HAND_READ["gpio p2 user sha"],
        "gpio p2 request key == hand-read": sha12(s2 + "\n\n" + u2) == HAND_READ["gpio p2 request key"],
        # planted fault: one changed character must break the match (the check can fail)
        "planted fault caught (user)": sha12(u1 + " ") != HAND_READ["gpio p1 user sha"],
        "planted fault caught (system)": sha12(s1.rstrip()) != HAND_READ["system sha phase 1"]
                                          or not s1.endswith("\n"),
        "user template sha p1 == _run_meta": sha12(read(PROMPTS_V9I / "phase1_user.md")) == meta["user template sha phase 1"],
        "user template sha p2 == _run_meta": sha12(read(PROMPTS_V9I / "phase2_user.md")) == meta["user template sha phase 2"],
        "inputs manifest sha == _run_meta": sha12(read(INPUTS / "manifest.json")) == meta["inputs manifest sha"],
    }
    out["selftest"] = selftest
    if not all(selftest.values()):
        print("SELF-TEST FAILED:", {k: v for k, v in selftest.items() if not v})
        (HERE / "verify_v9i_result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        return 2
    print("self-test: all", len(selftest), "checks pass")

    # ---- module sets ------------------------------------------------------------------------------------------
    p1_mods = sorted(p.stem for p in (RUN_V9I / "phase1").glob("*.json"))
    p2_mods = sorted(p.stem for p in (RUN_V9I / "phase2").glob("*.json"))
    as_mods = sorted(p.stem for p in (RUN_V9I / "assets").glob("*.json"))
    pending = sorted(p.name for p in (RUN_V9I / "_pending").glob("*")) if (RUN_V9I / "_pending").exists() else []
    failed = (RUN_V9I / "_failed_calls.jsonl")
    out["counts"] = {"phase1 records": len(p1_mods), "phase2 records": len(p2_mods), "asset files": len(as_mods),
                     "records in all": len(p1_mods) + len(p2_mods),
                     "same module set in phase1/phase2/assets": p1_mods == p2_mods == as_mods,
                     "_pending files": len(pending),
                     "_failed_calls.jsonl lines": (len(read(failed).splitlines()) if failed.exists() else 0)}

    # ---- keys.jsonl: request key -> (module, phase) -------------------------------------------------------------
    keys = {}
    kp = RUN_V9I / "_keys.jsonl"
    if kp.exists():
        for line in read(kp).splitlines():
            if line.strip():
                k = json.loads(line)
                keys.setdefault(k["key"], []).append((k["module"], k["phase"]))

    # ---- rebuild every record -----------------------------------------------------------------------------------
    rebuilt, mismatches, parsed, models, efforts, meta_models, meta_efforts = 0, [], 0, Counter(), Counter(), Counter(), Counter()
    not_parsed, key_not_logged, meta_mismatch = [], [], []
    for m in p1_mods:
        r1 = load(RUN_V9I / "phase1" / f"{m}.json")
        r2 = load(RUN_V9I / "phase2" / f"{m}.json") if m in p2_mods else None
        concepts = None
        try:
            concepts = parse_json(r1["raw"]).get("Conceptual Assets")
        except Exception as e:  # noqa: BLE001
            mismatches.append((m, 1, f"phase 1 raw does not parse: {e}"))
        for phase, rec, sysmsg in ((1, r1, s1), (2, r2, s2)):
            if rec is None:
                mismatches.append((m, phase, "record missing"))
                continue
            try:
                um = user(PROMPTS_V9I, phase, m) if phase == 1 else user(PROMPTS_V9I, 2, m, concepts)
            except Exception as e:  # noqa: BLE001
                mismatches.append((m, phase, f"cannot build user message: {e}"))
                continue
            want = (sha12(sysmsg), sha12(um), sha12(sysmsg + "\n\n" + um))
            got = (rec.get("system sha"), rec.get("user sha"), (rec.get("usage") or {}).get("request key"))
            if want == got:
                rebuilt += 1
            else:
                mismatches.append((m, phase, {"stored": got, "rebuilt": want}))
            if got[2] not in keys or (m, phase) not in keys.get(got[2], []):
                key_not_logged.append((m, phase, got[2]))
            # model / effort as stored
            u = rec.get("usage") or {}
            models[u.get("model")] += 1
            efforts[u.get("effort")] += 1
            # top-level record meta should name this module, phase and version
            if (rec.get("module"), rec.get("phase"), rec.get("prompt version"), rec.get("input version")) != \
                    (m, phase, "two_phase_v9i", "v1"):
                meta_mismatch.append((m, phase))
            if parsed_ok(rec):
                parsed += 1
            else:
                not_parsed.append((m, phase, rec.get("problems", [])[:3]))
    out["rebuild"] = {"records checked": len(p1_mods) + len(p2_mods), "rebuild exactly": rebuilt,
                      "mismatches": mismatches}
    out["parsed"] = {"records with a parsed reply": parsed, "not parsed": not_parsed}
    out["stored model (usage.model)"] = dict(models)
    out["stored effort (usage.effort)"] = dict(efforts)
    out["_run_meta model/effort/executor"] = {k: meta.get(k) for k in ("model", "effort", "executor", "prompt version",
                                                                      "input version")}
    out["record meta mismatches (module/phase/version)"] = meta_mismatch
    out["request keys missing from _keys.jsonl"] = key_not_logged

    # ---- format: problems in Phase 2, v9i r0 and v9h r0 ---------------------------------------------------------
    out["phase 2 format problems"] = {"two_phase_v9i r0": format_problem_counts(RUN_V9I),
                                      "two_phase_v9h r0": format_problem_counts(RUN_V9H)}

    (HERE / "verify_v9i_result.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    # ---- print -----------------------------------------------------------------------------------------------
    print(json.dumps({k: v for k, v in out.items() if k != "selftest"}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
