"""R6 reviser scan: per prompt version, does holding the lines R6 asks for go with the target element being primary?

Reads only stored model replies under final/pio/lab/runs/two_phase_*/gpt-5.6-luna__high/r*/phase{1,2}/<module>.json
(normalized 'reply' field). Opens no reference file. Per version, never pooled.

Conditions (held lines are v7 RTL line numbers; the RTL input is the same for all v1 folders):
  wdt:    some concept holds 103 and not 105      -> reset_wdt primary?   reset_force primary?
  cpu:    some concept holds 389                  -> lsu_mar primary?
          some concept holds 370                  -> alu_add primary?
  muldiv: some concept holds all of 148-151       -> ctrl.rs1_is_signed and ctrl.rs2_is_signed primary?
Self-test first, against hand-read facts of the v7 replies; output is printed only if it passes.
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict

RUNS = "E:/jobs/ff/test/Prepoison_subset/final/pio/lab/runs"


def load(p):
    try:
        return json.load(open(p, encoding="utf-8")).get("reply") or {}
    except Exception:
        return None


def held(reply):
    out = []
    for c in reply.get("conceptual assets") or []:
        hl = c.get("held lines") or []
        out.append(set(x for x in hl if isinstance(x, int)))
    return out


def prim(reply):
    return set(a.get("element") for a in reply.get("structural assets") or [] if str(a.get("label", "")).lower() == "primary")


def run_facts(vdir, r, mod):
    p1 = load(f"{vdir}/{r}/phase1/{mod}.json")
    p2 = load(f"{vdir}/{r}/phase2/{mod}.json")
    if p1 is None or p2 is None:
        return None
    return held(p1), prim(p2)


def selftest():
    v7 = f"{RUNS}/two_phase_v7__v1/gpt-5.6-luna__high"
    ok = True
    h, p = run_facts(v7, "r0", "neorv32_cpu")
    ok &= any({370, 386, 389, 394} == s for s in h) and {"lsu_mar", "alu_add"} <= p
    h, p = run_facts(v7, "r1", "neorv32_cpu")
    ok &= not any(389 in s for s in h) and "lsu_mar" not in p and any(s == {394} for s in h)
    h, p = run_facts(v7, "r2", "neorv32_wdt")
    ok &= any(s == {102, 103} for s in h) and "reset_wdt" in p
    h, p = run_facts(v7, "r0", "neorv32_wdt")
    ok &= not any(103 in s for s in h) and "reset_wdt" not in p and any(s == {102} for s in h)
    h, p = run_facts(v7, "r0", "neorv32_cpu_cp_muldiv")
    ok &= any(s == {148, 149, 150, 151} for s in h) and {"ctrl.rs1_is_signed", "ctrl.rs2_is_signed"} <= p
    h, p = run_facts(v7, "r2", "neorv32_cpu_cp_muldiv")
    ok &= not any(148 in s for s in h) and "ctrl.rs1_is_signed" not in p
    return bool(ok)


def main():
    if not selftest():
        print("SELF-TEST FAILED: nothing reported")
        sys.exit(1)
    print("self-test passed")
    rows = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))  # version -> key -> [cond runs, target hits, extra]
    nruns = defaultdict(lambda: defaultdict(int))
    for vdir in sorted(glob.glob(f"{RUNS}/two_phase_*/gpt-5.6-luna__high")):
        ver = re.search(r"two_phase_(\w+?)__(v1k?)", vdir.replace("\\", "/"))
        ver = ver.group(1) + ("" if ver.group(2) == "v1" else "(" + ver.group(2) + ")")
        for rd in sorted(glob.glob(f"{vdir}/r*")):
            r = os.path.basename(rd)
            f = run_facts(vdir, r, "neorv32_wdt")
            if f:
                h, p = f
                nruns[ver]["wdt"] += 1
                if any(103 in s and 105 not in s for s in h):
                    x = rows[ver]["wdt hold103 not105"]
                    x[0] += 1; x[1] += "reset_wdt" in p; x[2] += "reset_force" in p
                if any(103 in s and 105 in s for s in h) or not any(103 in s for s in h):
                    x = rows[ver]["wdt other shapes"]
                    x[0] += 1; x[1] += "reset_wdt" in p; x[2] += "reset_force" in p
            f = run_facts(vdir, r, "neorv32_cpu")
            if f:
                h, p = f
                nruns[ver]["cpu"] += 1
                if any(389 in s for s in h):
                    x = rows[ver]["cpu hold389"]; x[0] += 1; x[1] += "lsu_mar" in p
                else:
                    x = rows[ver]["cpu no389"]; x[0] += 1; x[1] += "lsu_mar" in p
                if any(370 in s for s in h):
                    x = rows[ver]["cpu hold370"]; x[0] += 1; x[1] += "alu_add" in p
                else:
                    x = rows[ver]["cpu no370"]; x[0] += 1; x[1] += "alu_add" in p
            f = run_facts(vdir, r, "neorv32_cpu_cp_muldiv")
            if f:
                h, p = f
                nruns[ver]["muldiv"] += 1
                both = {"ctrl.rs1_is_signed", "ctrl.rs2_is_signed"} <= p
                if any({148, 149, 150, 151} <= s for s in h):
                    x = rows[ver]["muldiv hold148-151"]; x[0] += 1; x[1] += both
                else:
                    x = rows[ver]["muldiv no148-151"]; x[0] += 1; x[1] += both
    out = {v: {"runs": dict(nruns[v]), **{k: {"cond runs": a, "target primary": b, "reset_force primary" if k.startswith("wdt") else "-": c}
                                         for k, (a, b, c) in rows[v].items()}} for v in rows}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
