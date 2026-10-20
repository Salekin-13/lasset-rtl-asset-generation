"""Why does v7 fail on the 12 held-out modules that cause its drop (locate_degradation.py)? Code-only evidence from v7's
stored replies (runs r0-r2), the inputs and the exact scorer.

Misses (findable reference elements not listed primary), per element-run, where the element was lost:
  - "Not Kept": a Phase 1 Not Kept row names it; its reason is matched to the v7 Phase 1 rule it invokes (keywords from
    the rule titles; approximate) and the version that first had that rule (prompts/two_phase_v*/phase1.md);
  - "secondary": a Phase 2 asset row names it with label secondary (or not primary); the Justification is kept;
  - "not reported": a Phase 2 Not Reported row names it;
  - "in a concept's lines only": no row names it, but a kept concept cites one of its RTL lines;
  - "never named": none of the above.
False positives (listed primaries that are not reference finds), per listing: whether an existing v7 bar excludes it,
  read by the four rule checks of the rules round (failure_analysis/rules/P1-P4/check.py) used here as DETECTORS only
  (nothing is applied); each check encodes the condition of v7 bars the model broke on the tuning modules, so "flagged"
  means "a v7 bar already excludes it" and "not flagged" means "no bar the checks encode" (a lower bound for the first).
  Also the 2.6 clause the Justification uses (stored / computed / boundary / decision or setting; keyword match).
How the checks read held-out modules: their copies (check_ho.py next to each, made here) take the replies folder and
the inputs folder from RAW_DIR and INPUTS_DIR; INPUTS_DIR is a byte-for-byte copy of all 41 modules' inputs in one
folder, so their own self-tests (tuning modules) still run. Self-test of this script: on the tuning replies the copies
drop exactly what the originals dropped (rules/<P>/check_out.json).

  python diagnose_12.py            -> diagnose_12.json, and a summary on screen
"""
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
FA = HERE.parent / "failure_analysis"
LAB = HERE.parents[2]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402
import compare_v8 as C8  # noqa: E402

V, MODEL, EFF, REPS = "two_phase_v7", "gpt-5.6-luna", "high", (0, 1, 2)
LOC = json.loads((HERE / "locate_degradation.json").read_text(encoding="utf-8"))
MODS = ["neorv32_" + m for m in LOC["responsible modules (union)"]]
ALLIN, RAWH = HERE / "_allinputs", HERE / "_raw12"
VERS = ["two_phase_v1", "two_phase_v2", "two_phase_v2a", "two_phase_v3", "two_phase_v4", "two_phase_v4a", "two_phase_v5",
        "two_phase_v5f", "two_phase_v5g", "two_phase_v6", "two_phase_v6d", "two_phase_v7"]
KEYS = {  # v7 Phase 1 rule title -> words a reason uses when it invokes it (approximate)
    "Clocks and resets": ["clock", "reset"], "Build-time values": ["build-time", "constant", "generic"],
    "Pacing pulses": ["pacing", "tick"], "Forwarded transactions": ["forwarded", "relay", "pass through", "passes through", "only passes", "only copies"],
    "Bus handshake copies": ["handshake"], "Working values": ["working value", "intermediate", "partial result"],
    "Hand-offs": ["hand-off", "handoff"], "Register read-back": ["read-back", "readback"],
    "Port buffers": ["port buffer", "port-buffer", "only buffering"], "Cached copies": ["cache"],
    "Operation selectors": ["operation selector", "operation-selector", "opcode", "funct"], "Per-region checks": ["per-region"],
    "Arbitration bookkeeping": ["bookkeeping", "arbitration"], "Precedence": ["precedence"], "Second copies": ["second cop", "copy of another register", "copies another register"],
    "Slices": ["slice"], "Instance-driven records": ["instance-driven", "driven whole"], "Sequencing state": ["sequencing"],
    "Serial shift registers": ["shift register", "serial shift", "serial-shift"], "Buffer and engine status bits": ["status bit", "buffer-status", "engine status"],
    "Port options": ["port option"], "Held addresses": ["held address"], "Access command fields": ["access-command", "access command", "command field", "byte enable", "byte-enable"],
    "Processor context fields": ["processor context", "processor-context", "privilege"],
}


def first_version():
    out = {}
    for t in KEYS:
        for v in VERS:
            p = LAB / "prompts" / v / "phase1.md"
            if p.exists() and re.search(r"^- " + re.escape(t) + r"\.", p.read_text(encoding="utf-8"), re.M):
                out[t] = v.replace("two_phase_", "")
                break
    return out


def rules_in(text):
    t = (text or "").lower()
    return sorted({r for r, ws in KEYS.items() if any(w in t for w in ws)})


def has(name, text):
    return bool(re.search(r"(?<![\w.])" + re.escape(name) + r"(?!\w)(?!\.\w)", text or ""))


def prepare():
    for m in K.gt_modules()["tuning"] + K.gt_modules()["heldout"]:
        d = ALLIN / m
        d.mkdir(parents=True, exist_ok=True)
        for f in ("rtl.txt", "closed_set.json", "diagram.txt"):
            shutil.copyfile(CH.module_dir(m) / f, d / f)
    for r in REPS:
        for m in MODS + K.gt_modules()["tuning"]:          # the checks' own self-tests read tuning modules from this folder
            for ph in (1, 2):
                rec = json.loads((CH.run_dir(V, MODEL, r, EFF) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))
                p = RAWH / f"r{r}" / f"phase{ph}" / f"{m}.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="") as f:
                    f.write(rec["raw"])
    scripts = {}
    for fx in ("P1", "P2", "P3", "P4"):
        src = (FA / "rules" / fx / "check.py").read_text(encoding="utf-8")
        src, n1 = re.subn(r'^RAW = FA / "raw"\s*$', 'RAW = __import__("pathlib").Path(__import__("os").environ.get("RAW_DIR", str(FA / "raw")))', src, flags=re.M)
        src, n2 = re.subn(r'^(INPUTS|TUNING) = LAB / "inputs" / "v1" / "tuning"\s*$',
                          r'\1 = __import__("pathlib").Path(__import__("os").environ.get("INPUTS_DIR", str(LAB / "inputs" / "v1" / "tuning")))', src, flags=re.M)
        assert n1 == 1 and n2 == 1, (fx, n1, n2)
        p = FA / "rules" / fx / "check_ho.py"
        p.write_text(src, encoding="utf-8")
        scripts[fx] = p
    return scripts


def run_check(fx, script, raw, out):
    env = dict(os.environ, RAW_DIR=str(raw), INPUTS_DIR=str(ALLIN))
    args = [sys.executable, "-I", str(script), str(out)]
    if fx in ("P1", "P3"):
        args += ["--raw", str(raw), "--inputs", str(ALLIN)]
    pr = subprocess.run(args, cwd=str(script.parent), env=env, capture_output=True, text=True, timeout=1200)
    if pr.returncode != 0 or not Path(out).exists():
        raise RuntimeError(f"{fx}: exit {pr.returncode}: {pr.stderr[-600:]}")
    return json.loads(Path(out).read_text(encoding="utf-8"))


def norm(o):
    return sorted((r, m, x.get("entity"), x.get("element")) for r, mods in o.items() for m, rows in (mods or {}).items() for x in rows)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    fv = first_version()
    scripts = prepare()
    # self-test: copies on the tuning replies = the originals' outputs
    ok = True
    for fx, sc in scripts.items():
        a = run_check(fx, sc, FA / "raw", HERE / f"_selftest_{fx}.json")
        b = json.loads((FA / "rules" / fx / "check_out.json").read_text(encoding="utf-8"))
        same = norm(a) == norm(b)
        ok &= same
        print(f"self-test {fx}: copy on the tuning replies = original output: {same}")
        (HERE / f"_selftest_{fx}.json").unlink()
    if not ok:
        sys.exit("self-test failed: nothing reported")
    flags = defaultdict(set)
    for fx, sc in scripts.items():
        o = run_check(fx, sc, RAWH, HERE / f"_flags_{fx}.json")
        for r, m, e, el in norm(o):
            mfull = "neorv32_" + m if not m.startswith("neorv32_") else m
            if mfull in MODS:                                   # keep the 12 modules only
                flags[(r, mfull, el)].add(fx)
    ref = C8.refs(MODS)
    out = {"rule first version": fv, "modules": {}}
    tot_m, tot_f = Counter(), Counter()
    rule_m = Counter()
    for m in MODS:
        s = m.replace("neorv32_", "")
        mm = {"misses": [], "false positives": [], "concepts per run": [], "primaries per run": []}
        for r in REPS:
            p1, p2 = (K.parse_json(json.loads((CH.run_dir(V, MODEL, r, EFF) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))["raw"]) for ph in (1, 2))
            listed, correct, found, lset = C8.score(V, r, m, ref)
            cons = [c for c in p1.get("Conceptual Assets", []) if isinstance(c, dict)]
            mm["concepts per run"].append(len(cons))
            mm["primaries per run"].append(listed)
            walks = [w for w in p2.get("Concept Walks", []) if isinstance(w, dict)]
            names = CH.closed_names(m)
            found_names = Counter(f.split(":", 1)[1].split("#")[0] for f in found)
            need = Counter(ref[m])
            for n in need:
                miss = need[n] - found_names[n]
                if miss <= 0:
                    continue
                lines = set()
                for (e, x), fx in names.items():
                    if x == n:
                        lines |= set(fx.get("occurrence lines") or [])
                rows = [(w.get("Concept ID"), a.get("Label"), a.get("Justification")) for w in walks for a in (w.get("Assets") or [])
                        if isinstance(a, dict) and (a.get("Asset RTL") == n or n in (a.get("Same Role") or []))]
                nr = [(w.get("Concept ID"), x.get("Why Not Reported")) for w in walks for x in (w.get("Not Reported") or []) if isinstance(x, dict) and x.get("Element RTL") == n]
                nk = [(x.get("Candidate Name"), x.get("Merged Into"), x.get("Why Not Kept")) for x in (p1.get("Not Kept") or []) if isinstance(x, dict) and has(n, json.dumps(x))]
                cited = [c.get("Concept ID") for c in cons if lines & (set(CH.as_list(c.get("Held Lines"))) | set(CH.as_list(c.get("Entry Lines"))) | set(CH.as_list(c.get("Exit Lines"))))]
                if rows:
                    where, why = "secondary", " | ".join(f"{c} {lab}: {j}" for c, lab, j in rows[:2])
                elif nr:
                    where, why = "not reported", " | ".join(f"{c}: {y}" for c, y in nr[:2])
                elif nk:
                    where, why = "Not Kept" + (" (merged)" if any(mi for _, mi, _ in nk) else ""), " | ".join(f"{c}: {mi or y}" for c, mi, y in nk[:2])
                elif cited:
                    where, why = "in a concept's lines only", f"concepts {cited}"
                else:
                    where, why = "never named", ""
                rl = rules_in(why) if where.startswith("Not Kept") or where in ("secondary", "not reported") else []
                for _ in range(miss):
                    mm["misses"].append({"run": f"r{r}", "element": n, "where lost": where, "rules named": rl, "reason": why[:400]})
                    tot_m[where] += 1
                    for x in rl:
                        rule_m[x] += 1
            # false positives
            assets = json.loads((CH.run_dir(V, MODEL, r, EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]
            left = Counter(ref[m])
            for a in assets:
                n = a["Asset RTL"]
                if left[n] > 0:
                    left[n] -= 1
                    continue
                js = [x.get("Justification") or "" for w in walks for x in (w.get("Assets") or []) if isinstance(x, dict) and x.get("Asset RTL") == n and x.get("Label") == "primary"]
                j = " ".join(js).lower()
                clause = [k for k, ws in (("stored", ["stored", "holds", "held", "register"]), ("computed", ["computed", "computes", "combin"]),
                                          ("boundary", ["boundary", "crosses", "output port", "input port"]), ("decision or setting", ["decision", "decides", "setting", "makes"])) if any(w in j for w in ws)]
                fl = sorted(flags.get((f"r{r}", m, n), set()))
                mm["false positives"].append({"run": f"r{r}", "element": n, "entity": a["Entity"], "concepts": a.get("Concepts", []),
                                              "v7 bar detected by": fl, "2.6 clause in the justification": clause, "justification": (js[0] if js else "")[:300]})
                tot_f["a v7 bar excludes it (detected)" if fl else "no bar detected"] += 1
        out["modules"][s] = mm
    out["misses: where lost"] = dict(tot_m)
    out["misses: rules named in the reasons"] = {k: {"count": v, "first in": fv.get(k)} for k, v in rule_m.most_common()}
    out["false positives"] = dict(tot_f)
    (HERE / "diagnose_12.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nmisses (element-runs) by where lost:", dict(tot_m))
    print("rules named in miss reasons (approximate keyword match) and the version that first had them:")
    for k, v in rule_m.most_common():
        print(f"   {k:32s} {v:3d}  first in {fv.get(k)}")
    print("false positives:", dict(tot_f))
    print("\nper module: misses by where lost | FPs detected / total | concepts and primaries per run")
    for s, mm in out["modules"].items():
        w = Counter(x["where lost"] for x in mm["misses"])
        fpd = sum(1 for x in mm["false positives"] if x["v7 bar detected by"])
        print(f"  {s:16s} misses {sum(w.values()):3d} {dict(w)} | FP {fpd}/{len(mm['false positives'])} | concepts {mm['concepts per run']} primaries {mm['primaries per run']}")


if __name__ == "__main__":
    main()
