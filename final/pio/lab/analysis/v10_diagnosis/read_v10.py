"""v10's readings V1-V6, exactly as prompts/two_phase_v10/README.md set them before the run (2026-10-16). Read-only;
writes read_v10.json. Uses compare_versions' exact scorer (compare_v8.score) through its own functions, without running
its main() (which rewrites compare_versions.json).

  V1 tuning_v2 (27 modules = compare_versions' "tuning" + "held-out: the 12"): pooled precision and pooled recall each
     not lower than v9's by more than 0.02 -> PASS.
  V2 run-to-run stability on tuning_v2: of the distinct (module, element) pairs listed primary in any run, the share
     listed in all 3 runs, v10 vs v9 (the README says "share of primary listings that appear in all 3 runs"; this is the
     distinct-pair reading, stated as such).
  V3 heldout_v2 (14 = "held-out: other 14"): precision and recall each not lower than v9's by more than 0.03.
  V4 the 17 G3 watch signals: (signal, run) pairs listed primary, v10 vs v9; a drop of more than 2 -> facts step next.
  V5 debug_dm dm_ctrl.busy primary runs v10 vs v9; the FIFO-flag and busy bits the status-bits rule bars (its luna
     rule-alone run v10e1, both repeats, Phase 2 wording) in uart, spi, slink: primary runs v10 vs v9.
  V6 output tokens per call, v10 vs v9, per phase (stored usage).
Self-test: the scorer reproduces v9's logged numbers (HANDOVER.md: tuning precision / recall 0.660 / 0.850, held-out
0.401 / 0.713 on the 15 / 26 split) before anything about v10 is printed.

  python -B read_v10.py
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT, register  # noqa: E402

ISO = register()
sys.path.insert(0, str(LAB / "analysis" / "heldout_versions__gpt-5.6-luna__high__r0-r2"))
import compare_versions as CV  # noqa: E402

C8, CH = CV.C8, CV.CH
V9, V10 = "two_phase_v9", "two_phase_v10"
REPS = (0, 1, 2)
V4 = {"neorv32_wdt": ["cnt", "cnt_timeout", "reset_wdt"],
      "neorv32_pwm": ["cfg_cdiv", "cfg_en", "cfg_prsc", "clkgen_en_o", "clkgen_i", "pwm_o", "we_i"],
      "neorv32_bus": ["keeper.cnt", "keeper.err", "keeper.halt"], "neorv32_debug_dm": ["dm_ctrl.busy"],
      "neorv32_cpu_lsu": ["mar"], "neorv32_cpu_cp_shifter": ["shifter.cnt", "shifter.done_ff"]}


def pooled(v, mods, ref):
    x = C8.runs(v, mods, ref)
    F = sum(len(ref[m]) for m in mods)
    T, L = sum(y["correct"] for y in x.values()), sum(y["listed"] for y in x.values())
    return {"TP": T, "listed": L, "FP": L - T, "FN": 3 * F - T, "findable per run": F,
            "precision": round(T / L, 3), "recall": round(T / (3 * F), 3),
            "per run (correct, listed)": [(x[r]["correct"], x[r]["listed"]) for r in REPS]}


def listed(v, m, r):
    return [x["Asset RTL"] for x in json.loads((CH.run_dir(v, MODEL, r, EFFORT) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, ref = CV.groups_and_ref()
    t15, h26 = groups["tuning"], groups["held-out"]
    p9t, p9h = pooled(V9, t15, ref), pooled(V9, h26, ref)
    ok = (p9t["precision"], p9t["recall"], p9h["precision"], p9h["recall"]) == (0.660, 0.850, 0.401, 0.713)
    print(f"self-test (v9 on 15 / 26 = HANDOVER 0.660 / 0.850, 0.401 / 0.713): {'PASS' if ok else 'FAIL'} "
          f"({p9t['precision']} / {p9t['recall']}, {p9h['precision']} / {p9h['recall']})")
    probs = CV.complete(V10, t15 + h26)
    if not ok or probs:
        sys.exit("self-test failed or v10 incomplete: " + "; ".join(probs[:3]))
    tv2 = groups["tuning"] + groups["held-out: the 12"]
    hv2 = groups["held-out: other 14"]
    out = {}
    for name, mods in (("tuning_v2", tv2), ("heldout_v2", hv2), ("all 41", t15 + h26)):
        out[name] = {"v9": pooled(V9, mods, ref), "v10": pooled(V10, mods, ref)}
    a, b = out["tuning_v2"]["v9"], out["tuning_v2"]["v10"]
    v1 = b["precision"] >= a["precision"] - 0.02 and b["recall"] >= a["recall"] - 0.02
    a3, b3 = out["heldout_v2"]["v9"], out["heldout_v2"]["v10"]
    v3 = b3["precision"] >= a3["precision"] - 0.03 and b3["recall"] >= a3["recall"] - 0.03
    stab = {}
    for v in (V9, V10):
        anyr = all3 = 0
        for m in tv2:
            sets = [set(listed(v, m, r)) for r in REPS]
            u = set.union(*sets)
            anyr += len(u)
            all3 += len(set.intersection(*sets))
        stab[v] = [all3, anyr, round(all3 / anyr, 3)]
    v4 = {v: sum(n in listed(v, m, r) for m, ns in V4.items() for n in ns for r in REPS) for v in (V9, V10)}
    v4cases = {v: {f"{m[8:]}:{n}": sum(n in listed(v, m, r) for r in REPS) for m, ns in V4.items() for n in ns} for v in (V9, V10)}
    ISO.use("v10e1")
    v5 = {}
    for m in ("neorv32_uart", "neorv32_spi", "neorv32_slink", "neorv32_debug_dm"):
        b2 = []
        for rep in (0, 1):
            f = ISO.run_root(rep=rep) / "P2" / "P1-17" / f"{m}.json"
            rec = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
            b2.append({x.get("element") for x in (rec.get("reply") or {}).get("barred") or [] if isinstance(x, dict)})
        cons = sorted(b2[0] & b2[1]) if len(b2) == 2 else []
        v5[m[8:]] = {e: {"v9": sum(e in listed(V9, m, r) for r in REPS), "v10": sum(e in listed(V10, m, r) for r in REPS)} for e in cons}
    ISO.use("v9")
    busy = {v: sum("dm_ctrl.busy" in listed(v, "neorv32_debug_dm", r) for r in REPS) for v in (V9, V10)}
    v6 = {}
    for v in (V9, V10):
        for ph in (1, 2):
            outs = [json.loads((CH.run_dir(v, MODEL, r, EFFORT) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))["usage"].get("out") or 0
                    for r in REPS for m in t15 + h26]
            v6[f"{v[10:]} phase {ph}"] = round(sum(outs) / len(outs))
    out.update({"V1 PASS": v1, "V2 stability (all 3 / any, share)": stab, "V3 PASS": v3,
                "V4 (signal, run) pairs primary": v4, "V4 cases": v4cases, "V4 drop more than 2": v4[V9] - v4[V10] > 2,
                "V5 dm_ctrl.busy primary runs": busy, "V5 status bits barred by the rule alone (both repeats), primary runs": v5,
                "V6 mean output tokens per call": v6})
    (HERE / "read_v10.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for name in ("tuning_v2", "heldout_v2", "all 41"):
        a, b = out[name]["v9"], out[name]["v10"]
        print(f"{name}: v9 P {a['TP']}/{a['listed']} = {a['precision']}, R {a['TP']}/{3 * a['findable per run']} = {a['recall']} | "
              f"v10 P {b['TP']}/{b['listed']} = {b['precision']}, R {b['TP']}/{3 * b['findable per run']} = {b['recall']}")
    print(f"V1 (tuning_v2, each within 0.02 of v9): {'PASS' if v1 else 'FAIL'}")
    print(f"V2 stability (distinct pairs listed in all 3 runs / in any run): v9 {stab[V9]}, v10 {stab[V10]}")
    print(f"V3 (heldout_v2, each within 0.03): {'PASS' if v3 else 'FAIL'}")
    print(f"V4 watch pairs: v9 {v4[V9]}, v10 {v4[V10]}; drop > 2: {out['V4 drop more than 2']}")
    print(f"V5 dm_ctrl.busy primary runs: v9 {busy[V9]}, v10 {busy[V10]}; status bits: {json.dumps(v5)}")
    print(f"V6 mean output tokens per call: {v6}")


if __name__ == "__main__":
    main()
