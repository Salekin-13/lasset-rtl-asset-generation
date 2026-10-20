"""Rebuild check of the Phase 1 records of the three p1o arms (two_phase_p1o_first / _last / _sham), 26 held-out
modules x runs r0-r2, on gpt-5.6-luna / high.

For every stored record the system and user messages are rebuilt from lab/prompts/<version> and lab/inputs/v1 the
way chain.py does it (check_lab_prompt.system and chain.user_message, re-implemented here, not imported):
  system = common.md.rstrip() + "\n\n" + phase1.md
  user   = phase1_user.md.format(module, rtl, diagram, closed_set=compact JSON of closed_set.json)
  sha12  = sha256 hex[:12]; request key = sha12(system + "\n\n" + user)
and compared with the record's "system sha", "user sha" and usage["request key"], and with _keys.jsonl.
Also: usage model/effort of every record, whether the raw reply parses to a "Conceptual Assets" list of objects,
_run_meta.json against the rebuilt shas, leftovers (phase2/, assets/, _failed_calls.jsonl, _pending/*, _schema_failed/),
and token totals per arm. USD: chain.py and labkit.py expose no usage-to-USD function; cost_estimate.py does
(cost_estimate.usd with PRICES), so the token totals are the primary figure and a USD figure is computed HERE from the
gpt-5.6-luna row of that table (0.20 in / 0.02 cached in / 1.20 out per 1M tokens, "read 2026-10-11" per that file),
with the same formula: (in - cached) * in_price + cached * cached_price + out * out_price.

Only chain.run_dir is imported from chain (PIO_INPUT_VERSION=v1 set first). No API call is made.

  python -B verify_p1o_records.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]                      # .../experiments/03_two_phase_csa_pio/lab
assert LAB.name == "lab", LAB
sys.path.insert(0, str(LAB))
import chain  # noqa: E402  (only chain.run_dir is used)

MODEL, EFFORT = "gpt-5.6-luna", "high"
ARMS = ["two_phase_p1o_first", "two_phase_p1o_last", "two_phase_p1o_sham"]
REPS = (0, 1, 2)
HELDOUT = sorted(p.name for p in (LAB / "inputs" / "v1" / "heldout").iterdir() if p.is_dir())
# copied from cost_estimate.PRICES["gpt-5.6-luna"] (USD per 1M tokens); recomputed here, not imported
PRICE = {"in": 0.20, "cached": 0.02, "out": 1.20}


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def system_text(version: str, phase: int) -> str:
    d = LAB / "prompts" / version
    return (d / "common.md").read_text(encoding="utf-8").rstrip() + "\n\n" + (d / f"phase{phase}.md").read_text(encoding="utf-8")


def user_text(version: str, m: str) -> str:
    d = LAB / "inputs" / "v1" / "heldout" / m
    t = (LAB / "prompts" / version / "phase1_user.md").read_text(encoding="utf-8")
    cs = json.dumps(json.loads((d / "closed_set.json").read_text(encoding="utf-8")), separators=(",", ":"))
    return t.format(module=m, rtl=(d / "rtl.txt").read_text(encoding="utf-8"),
                    diagram=(d / "diagram.txt").read_text(encoding="utf-8"), closed_set=cs)


def parse_json(text: str):
    """labkit.parse_json, re-implemented: strip a code fence, take the outermost {...}."""
    import re
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    return json.loads(t[t.find("{"): t.rfind("}") + 1])


def usd(u: dict) -> float:
    i, c, o = u.get("in", 0) or 0, u.get("cached", 0) or 0, u.get("out", 0) or 0
    return ((i - c) * PRICE["in"] + c * PRICE["cached"] + o * PRICE["out"]) / 1e6


def selftest() -> bool:
    """The check must catch a planted change: a one-character change of the user message or the system message
    changes the sha; and sha12 agrees with hashlib on a known string."""
    ok = sha12("abc") == hashlib.sha256(b"abc").hexdigest()[:12]
    m = HELDOUT[0]
    s, u = system_text(ARMS[0], 1), user_text(ARMS[0], m)
    ok &= sha12(u + " ") != sha12(u) and sha12(s + " ") != sha12(s)
    ok &= sha12(s + "\n\n" + u) != sha12(s + "\n" + u)
    ok &= "{module}" not in u and m in u and "{rtl}" not in u and "{closed_set}" not in u
    ok &= len(HELDOUT) == 26
    return ok


def main() -> dict:
    res = {"selftest": selftest(), "heldout modules": len(HELDOUT), "arms": {}}
    if not res["selftest"]:
        print("SELF-TEST FAILED; nothing reported")
        return res
    # the prompt files of the three arms: which are identical across arms
    files = {}
    for v in ARMS:
        files[v] = {f: sha12((LAB / "prompts" / v / f).read_text(encoding="utf-8"))
                    for f in ("common.md", "phase1.md", "phase2.md", "phase1_user.md", "phase2_user.md")}
    res["prompt file sha12"] = files
    res["prompt files identical across the three arms"] = {
        f: len({files[v][f] for v in ARMS}) == 1 for f in files[ARMS[0]]}
    for v in ARMS:
        sys1, sys2 = system_text(v, 1), system_text(v, 2)
        ss1, ss2 = sha12(sys1), sha12(sys2)
        tpl1 = sha12((LAB / "prompts" / v / "phase1_user.md").read_text(encoding="utf-8"))
        tpl2 = sha12((LAB / "prompts" / v / "phase2_user.md").read_text(encoding="utf-8"))
        man = sha12((LAB / "inputs" / "v1" / "manifest.json").read_text(encoding="utf-8"))
        expect_meta = {"prompt version": v, "input version": "v1", "model": MODEL, "effort": EFFORT,
                       "executor": "openai", "system sha phase 1": ss1, "system sha phase 2": ss2,
                       "user template sha phase 1": tpl1, "user template sha phase 2": tpl2, "inputs manifest sha": man}
        arm = {"system sha phase 1 (rebuilt)": ss1, "records expected": len(HELDOUT) * len(REPS), "records found": 0,
               "rebuilt exactly": 0, "mismatches": [], "field mismatches": [], "keys.jsonl mismatches": [],
               "usage model": Counter(), "usage effort": Counter(), "parsed Conceptual Assets list": 0,
               "parse failures": [], "stored reply has conceptual assets": 0, "concepts total": 0,
               "records with problems": 0, "problem count": 0, "problems by prefix": Counter(),
               "stopped (schema/unparseable/not checked)": [],
               "run meta": {}, "leftovers": {}, "tokens": Counter(), "usd (own formula, cost_estimate prices)": 0.0,
               "usd per run": {}}
        for k in REPS:
            out = chain.run_dir(v, MODEL, k, EFFORT)
            assert out == LAB / "runs" / f"{v}__v1" / f"{MODEL}__{EFFORT}" / f"r{k}", out
            rk = f"r{k}"
            # run meta
            mp = out / "_run_meta.json"
            if mp.exists():
                meta = json.loads(mp.read_text(encoding="utf-8"))
                diff = {kk: (meta.get(kk), expect_meta[kk]) for kk in expect_meta if meta.get(kk) != expect_meta[kk]}
                extra = sorted(set(meta) - set(expect_meta))
                arm["run meta"][rk] = {"agrees": not diff and not extra, "differences": diff, "extra keys": extra}
            else:
                arm["run meta"][rk] = {"agrees": False, "differences": "no _run_meta.json"}
            # leftovers
            lo = {"phase2 files": len(list((out / "phase2").glob("*.json"))) if (out / "phase2").exists() else 0,
                  "assets files": len(list((out / "assets").glob("*.json"))) if (out / "assets").exists() else 0,
                  "_failed_calls.jsonl lines": len([l for l in (out / "_failed_calls.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()])
                  if (out / "_failed_calls.jsonl").exists() else 0,
                  "_pending files": len(list((out / "_pending").iterdir())) if (out / "_pending").exists() else 0,
                  "_schema_failed files": len(list((out / "_schema_failed").rglob("*.json"))) if (out / "_schema_failed").exists() else 0,
                  "phase1 files total": len(list((out / "phase1").glob("*.json"))),
                  "phase1 files not held-out": sorted(p.stem for p in (out / "phase1").glob("*.json") if p.stem not in HELDOUT)}
            arm["leftovers"][rk] = lo
            # keys.jsonl
            keys = {}
            kl = out / "_keys.jsonl"
            if kl.exists():
                for l in kl.read_text(encoding="utf-8").splitlines():
                    if l.strip():
                        x = json.loads(l)
                        keys.setdefault(x["key"], []).append((x.get("module"), x.get("phase")))
            run_usd = 0.0
            for m in HELDOUT:
                f = out / "phase1" / f"{m}.json"
                if not f.exists():
                    arm["mismatches"].append({"run": rk, "module": m, "why": "no record"})
                    continue
                arm["records found"] += 1
                rec = json.loads(f.read_text(encoding="utf-8"))
                u = user_text(v, m)
                us, key = sha12(u), sha12(sys1 + "\n\n" + u)
                usage = rec.get("usage") or {}
                why = []
                if rec.get("system sha") != ss1:
                    why.append(f"system sha {rec.get('system sha')} != {ss1}")
                if rec.get("user sha") != us:
                    why.append(f"user sha {rec.get('user sha')} != {us}")
                if usage.get("request key") != key:
                    why.append(f"request key {usage.get('request key')} != {key}")
                if why:
                    arm["mismatches"].append({"run": rk, "module": m, "why": why})
                else:
                    arm["rebuilt exactly"] += 1
                fields = {"module": m, "prompt version": v, "input version": "v1", "phase": 1}
                fd = {kk: rec.get(kk) for kk, want in fields.items() if rec.get(kk) != want}
                if fd:
                    arm["field mismatches"].append({"run": rk, "module": m, "got": fd})
                if keys.get(key) != [(m, 1)]:
                    arm["keys.jsonl mismatches"].append({"run": rk, "module": m, "keys.jsonl has": keys.get(key)})
                arm["usage model"][str(usage.get("model"))] += 1
                arm["usage effort"][str(usage.get("effort"))] += 1
                for kk in ("in", "out", "reasoning", "cached"):
                    val = usage.get(kk)
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        arm["tokens"][kk] += val
                    else:
                        arm["tokens"][f"{kk} missing"] += 1
                run_usd += usd(usage)
                # parse the raw reply
                try:
                    obj = parse_json(rec["raw"])
                    ca = obj.get("Conceptual Assets") if isinstance(obj, dict) else None
                    if isinstance(ca, list) and all(isinstance(c, dict) for c in ca):
                        arm["parsed Conceptual Assets list"] += 1
                        arm["concepts total"] += len(ca)
                    else:
                        arm["parse failures"].append({"run": rk, "module": m, "why": "no Conceptual Assets list of objects"})
                except ValueError as e:
                    arm["parse failures"].append({"run": rk, "module": m, "why": f"unparseable: {e}"})
                rp = rec.get("reply")
                if isinstance(rp, dict) and isinstance(rp.get("conceptual assets"), list):
                    arm["stored reply has conceptual assets"] += 1
                probs = rec.get("problems") or []
                if probs:
                    arm["records with problems"] += 1
                    arm["problem count"] += len(probs)
                    for p in probs:
                        arm["problems by prefix"][str(p).split(":")[0]] += 1
                if rec.get("check crashed") or probs == ["not checked yet"] or any(str(p).startswith(("unparseable", "schema:")) for p in probs):
                    arm["stopped (schema/unparseable/not checked)"].append({"run": rk, "module": m, "problems": probs[:3]})
            arm["usd per run"][rk] = round(run_usd, 4)
            arm["usd (own formula, cost_estimate prices)"] += run_usd
        arm["usd (own formula, cost_estimate prices)"] = round(arm["usd (own formula, cost_estimate prices)"], 4)
        for kk in ("usage model", "usage effort", "tokens", "problems by prefix"):
            arm[kk] = dict(arm[kk])
        res["arms"][v] = arm
    return res


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    r = main()
    (HERE / "rebuild_check.json").write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"self-test: {r['selftest']}; held-out modules: {r['heldout modules']}")
    if r["selftest"]:
        print("prompt files identical across the three arms:", r["prompt files identical across the three arms"])
        for v, a in r["arms"].items():
            print(f"\n== {v}  (system sha phase 1 rebuilt {a['system sha phase 1 (rebuilt)']})")
            print(f"  records found {a['records found']} of {a['records expected']}; rebuilt exactly {a['rebuilt exactly']}; "
                  f"mismatches {len(a['mismatches'])}; field mismatches {len(a['field mismatches'])}; "
                  f"_keys.jsonl mismatches {len(a['keys.jsonl mismatches'])}")
            print(f"  usage model {a['usage model']}; effort {a['usage effort']}")
            print(f"  parsed 'Conceptual Assets' list: {a['parsed Conceptual Assets list']} of {a['records found']}; "
                  f"stored reply has 'conceptual assets': {a['stored reply has conceptual assets']}; concepts total {a['concepts total']}; "
                  f"parse failures {len(a['parse failures'])}; stopped {len(a['stopped (schema/unparseable/not checked)'])}")
            print(f"  records with problems {a['records with problems']}; problem count {a['problem count']}; by prefix {a['problems by prefix']}")
            print(f"  run meta: {json.dumps(a['run meta'])}")
            print(f"  leftovers: {json.dumps(a['leftovers'])}")
            print(f"  tokens: {a['tokens']}")
            print(f"  USD (own formula; gpt-5.6-luna prices from cost_estimate.py): {a['usd (own formula, cost_estimate prices)']}; per run {a['usd per run']}")
            for x in a["mismatches"] + a["field mismatches"] + a["keys.jsonl mismatches"] + a["parse failures"]:
                print("   !!", x)
        print(f"\nwritten: {HERE / 'rebuild_check.json'}")
