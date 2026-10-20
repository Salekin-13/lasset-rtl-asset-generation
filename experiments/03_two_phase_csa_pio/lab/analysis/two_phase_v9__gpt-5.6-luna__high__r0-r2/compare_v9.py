"""two_phase_v9 (v8 + the Forwarded transactions narrowing) against v8 on the seven modules where that rule acts: xbus
(held-out in the old split, tuning in tuning_v2), bus, cache, cpu, debug_dtm (tuning), cpu_icc and cpu_control (where v8
bars a separate CSR read-data port as relayed data). Read-only on stored files; writes compare_v9.json. Run after the
notebook job (cell 9: JOBS = v9 r0-r2, ALL = these seven modules).

Exact scorer of compare_v8.py. Readings, set before the run (prompts/two_phase_v9/README.md):
  R1  targets xbus_dat_o, xbus_dat_i, xbus_stb_o (v8: 0 of 3 runs each): "supports" if 2+ of them are found in 2+ v9
      runs; "FALSIFIED" if none is; "partial" otherwise. xbus_cyc_o, xbus_ack_i, xbus_err_i (v8: 1 each) reported.
  R2  xbus_adr_o and xbus_we_o (v8: 3 each) stay found in 2+ v9 runs each, else "FALSIFIED".
  R3  no cost on the tuning modules the rule acts on (bus + cache + cpu, pooled r0-r2; v8 TP 72, FP 56): "FALSIFIED" if
      v9 TP <= 66 or v9 FP >= 62 (a change of 6 = two runs' worth of v8's per-run spread; a chosen cut).
  R4  no leak into xbus's other elements: v9 xbus FP runs <= 25 (v8 19, plus at most 6 for xbus_sel_o and xbus_tag_o,
      which the reference does not list), else "FALSIFIED"; the new xbus FP names are listed.
  R6  scope, CSR read-data ports (v8 bars them as relayed data; none is in the reference): FP runs of cpu_icc csr_rdata_o,
      cpu_control xcsr_rdata_i and cpu_control csr_rdata_o, summed (v8 3): "FALSIFIED" if v9 >= 5.
  R7  scope, debug_dtm (v8 bars scan data passing from the JTAG data input to its data output as forwarded): "FALSIFIED"
      if v9 TP <= 10 (v8 13) or FP >= 23 (v8 20); tap_reg.bypass FP runs reported (v8 0).
  R5  mechanism (reported): per run, whether an xbus Phase 1 concept lists xbus_dat_o, xbus_stb_o or xbus_dat_i under
      Enters/Leaves Through, and which separate xbus ports Phase 1 Not Kept rows citing forwarding or relayed data name.
Checks first: both versions complete on the seven modules (both phases, assets file, nothing pending); the scorer's
self-test; v8's baseline equals the README's numbers; R5's extraction finds on v8 the ports the analysis found
(Not Kept rows naming xbus_cyc_o, xbus_dat_i, xbus_stb_o); the per-port counter gives v8's known
per-port runs found (added 2026-10-14 after it had compared a bare name with module:name strings and read 0 everywhere).

  python compare_v9.py
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402
import compare_v8 as C8  # noqa: E402

MODEL, EFF, REPS = "gpt-5.6-luna", "high", (0, 1, 2)
V8, V9 = "two_phase_v8", "two_phase_v9"
MODS = ["neorv32_xbus", "neorv32_bus", "neorv32_cache", "neorv32_cpu", "neorv32_debug_dtm", "neorv32_cpu_icc", "neorv32_cpu_control"]
TUN = ["neorv32_bus", "neorv32_cache", "neorv32_cpu"]
TARGETS = ["xbus_dat_o", "xbus_dat_i", "xbus_stb_o"]
OTHERS = ["xbus_cyc_o", "xbus_ack_i", "xbus_err_i"]
KEEP = ["xbus_adr_o", "xbus_we_o"]
V8_BASE = {"neorv32_xbus": (12, 19), "neorv32_bus": (32, 17), "neorv32_cache": (5, 16), "neorv32_cpu": (35, 23),
           "neorv32_debug_dtm": (13, 20), "neorv32_cpu_icc": (4, 10), "neorv32_cpu_control": (16, 175)}  # (TP, FP)
CSR_RD = [("neorv32_cpu_icc", "csr_rdata_o"), ("neorv32_cpu_control", "xcsr_rdata_i"), ("neorv32_cpu_control", "csr_rdata_o")]
XPORTS = ["xbus_adr_o", "xbus_dat_i", "xbus_dat_o", "xbus_tag_o", "xbus_we_o", "xbus_sel_o", "xbus_stb_o", "xbus_cyc_o",
          "xbus_ack_i", "xbus_err_i"]


def complete(v):
    probs = []
    for r in REPS:
        d = CH.run_dir(v, MODEL, r, EFF)
        for m in MODS:
            for p in ("phase1", "phase2", "assets"):
                if not (d / p / f"{m}.json").exists():
                    probs.append(f"{v} r{r} {p} {m}")
        if (d / "_pending").exists() and any((d / "_pending").iterdir()):
            probs.append(f"{v} r{r}: requests pending")
    return probs


def has(n, t):
    return bool(re.search(r"(?<![\w.])" + re.escape(n) + r"(?![\w])", t or ""))


def mechanism(v, r):
    m = "neorv32_xbus"
    rec = json.loads((CH.run_dir(v, MODEL, r, EFF) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
    cons = CH.phase1_concepts(rec["reply"]) or []
    anch = sorted({p for c in cons for p in CH.as_list(c.get("enters through")) + CH.as_list(c.get("leaves through"))
                   if p in TARGETS})
    raw = K.parse_json(rec["raw"])
    rows = raw.get("Not Kept") if isinstance(raw, dict) and "Not Kept" in raw else (rec["reply"] or {}).get("considered, not kept")
    named = set()
    for x in rows or []:
        t = json.dumps(x, ensure_ascii=False)
        if re.search(r"forward|relayed", t, re.I):
            named |= {p for p in XPORTS if has(p, t)}
    return {"target ports anchored by a kept concept": anch, "separate xbus ports named by forwarding/relayed Not Kept rows": sorted(named)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ref = C8.refs(sorted(set(MODS) | set(K.gt_modules()["tuning"])))
    probs = complete(V8) + complete(V9)
    if probs:
        print(f"not complete ({len(probs)}): {probs[:6]} -> nothing read")
        sys.exit(1)
    s = {(v, m): [C8.score(v, r, m, ref) for r in REPS] for v in (V8, V9) for m in MODS}
    base = {m: (sum(x[1] for x in s[(V8, m)]), sum(x[0] - x[1] for x in s[(V8, m)])) for m in MODS}
    v8_named = set().union(*(set(mechanism(V8, r)["separate xbus ports named by forwarding/relayed Not Kept rows"]) for r in REPS))
    ok = C8.selftest(ref) and base == V8_BASE and {"xbus_cyc_o", "xbus_dat_i", "xbus_stb_o"} <= v8_named
    ok &= sum(1 for m, n in CSR_RD for r in REPS if f"{m[8:]}:{n}" in s[(V8, m)][r][3]) == 3     # v8: 1 + 1 + 1 FP runs
    print(f"checks (complete, scorer self-test, v8 baseline {base}, R5 extraction on v8 {sorted(v8_named)}, v8 CSR read-data FP runs 3):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)

    def runs_found(v, n):          # runs of v in which xbus's reference entry n is a correct find ("xbus:<name>#k")
        return sum(1 for r in REPS if any(f.split(":", 1)[1].split("#")[0] == n for f in s[(v, "neorv32_xbus")][r][2]))
    # self-test of runs_found on v8 (counts read from v8's assets files in the held-out analysis, transitions.py)
    want8 = {"xbus_adr_o": 3, "xbus_we_o": 3, "xbus_dat_o": 0, "xbus_dat_i": 0, "xbus_stb_o": 0, "xbus_cyc_o": 1,
             "xbus_ack_i": 1, "xbus_err_i": 1, "timeout": 3}
    got8 = {n: runs_found(V8, n) for n in want8}
    print(f"self-test (per-port runs found on v8 = known counts): {'PASS' if got8 == want8 else 'FAIL ' + str(got8)}")
    if got8 != want8:
        sys.exit(1)

    out = {"modules": {m.replace("neorv32_", ""): {v[10:]: {"TP": sum(x[1] for x in s[(v, m)]), "FP": sum(x[0] - x[1] for x in s[(v, m)]),
                                                         "TP per run": [x[1] for x in s[(v, m)]]} for v in (V8, V9)} for m in MODS}}
    t8 = {n: runs_found(V8, n) for n in TARGETS + OTHERS + KEEP}
    t9 = {n: runs_found(V9, n) for n in TARGETS + OTHERS + KEEP}
    hit = [n for n in TARGETS if t9[n] >= 2]
    tun_tp = {v: sum(out["modules"][m.replace("neorv32_", "")][v[10:]]["TP"] for m in TUN) for v in (V8, V9)}
    tun_fp = {v: sum(out["modules"][m.replace("neorv32_", "")][v[10:]]["FP"] for m in TUN) for v in (V8, V9)}
    xfp = {v: out["modules"]["xbus"][v[10:]]["FP"] for v in (V8, V9)}
    fp_names = {v: Counter(n for r in REPS for n in s[(v, "neorv32_xbus")][r][3]
                           if not any(f.split(":")[1].split("#")[0] == n.split(":")[1] for f in s[(v, "neorv32_xbus")][r][2]))
                for v in (V8, V9)}
    new_fp = sorted(n for n in fp_names[V9] if fp_names[V9][n] > fp_names[V8].get(n, 0))

    def fp_runs(v, m, name):
        return sum(1 for r in REPS if f"{m.replace('neorv32_', '')}:{name}" in s[(v, m)][r][3]
                   and not any(f.split(":")[1].split("#")[0] == name for f in s[(v, m)][r][2]))
    csr = {v: sum(fp_runs(v, m, n) for m, n in CSR_RD) for v in (V8, V9)}
    dtm = {v: out["modules"]["debug_dtm"][v[10:]] for v in (V8, V9)}
    byp = {v: fp_runs(v, "neorv32_debug_dtm", "tap_reg.bypass") for v in (V8, V9)}
    out["READINGS"] = {
        "R1 targets found in 2+ v9 runs (v8 -> v9 runs)": {n: f"{t8[n]} -> {t9[n]}" for n in TARGETS},
        "R1 verdict": "supports" if len(hit) >= 2 else ("FALSIFIED" if not hit else "partial"),
        "R1 others (reported)": {n: f"{t8[n]} -> {t9[n]}" for n in OTHERS},
        "R2 adr_o / we_o (v8 -> v9 runs)": {n: f"{t8[n]} -> {t9[n]}" for n in KEEP},
        "R2 verdict": "held" if all(t9[n] >= 2 for n in KEEP) else "FALSIFIED",
        "R3 bus+cache+cpu TP / FP (v8 -> v9)": f"TP {tun_tp[V8]} -> {tun_tp[V9]}, FP {tun_fp[V8]} -> {tun_fp[V9]}",
        "R3 verdict": "FALSIFIED" if (tun_tp[V9] <= 66 or tun_fp[V9] >= 62) else "held",
        "R4 xbus FP runs (v8 -> v9)": f"{xfp[V8]} -> {xfp[V9]}; names listed more often in v9: {new_fp}",
        "R4 verdict": "FALSIFIED" if xfp[V9] > 25 else "held",
        "R6 CSR read-data ports, FP runs summed (v8 -> v9)": f"{csr[V8]} -> {csr[V9]}",
        "R6 verdict": "FALSIFIED" if csr[V9] >= 5 else "held",
        "R7 debug_dtm TP / FP (v8 -> v9)": f"TP {dtm[V8]['TP']} -> {dtm[V9]['TP']}, FP {dtm[V8]['FP']} -> {dtm[V9]['FP']}; tap_reg.bypass FP runs {byp[V8]} -> {byp[V9]}",
        "R7 verdict": "FALSIFIED" if (dtm[V9]["TP"] <= 10 or dtm[V9]["FP"] >= 23) else "held",
        "R5 mechanism per run": {f"{v[10:]} r{r}": mechanism(v, r) for v in (V8, V9) for r in REPS},
    }
    for k, v in out["READINGS"].items():
        print(f"{k}: {json.dumps(v) if isinstance(v, (dict, list)) else v}")
    for m, x in out["modules"].items():
        print(f"  {m:11s} v8 TP {x['v8']['TP']:3d} FP {x['v8']['FP']:3d} | v9 TP {x['v9']['TP']:3d} FP {x['v9']['FP']:3d} (runs {x['v9']['TP per run']})")
    (HERE / "compare_v9.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
