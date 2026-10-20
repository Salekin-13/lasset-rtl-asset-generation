"""What a "walk-found internals are secondaries" rule could give, simulated as a post-filter on the stored two_phase_v9j
output (no call sent; this is the rule's ceiling if the model followed it exactly, not a prompt test).
"Walk-found" (fp_v9j_detail D1, strict): a scored primary that Phase 1's entry does not locate: not an Enters/Leaves
Through port of its concept, and none of its assignment lines (gets-value-from, decided-by, reset-by, clocked-by
counterpart lines) is a held line of the concept.
Variants, scored with the exact scorer's logic per group, pooled over r0-r2, against v9j as is:
  V1 drop walk-found signal fields;  V2 drop walk-found signals, signal fields and record signals;
  V3 = V2 sparing the keep rules' intended cases and the bars' must-spare lists (N21-N25, K11-K13, B1-B5, the control-unit
     sparing sentence), as the keep blocks after a bar would.
Self-test: V0 (nothing dropped) reproduces read_v9j.json's J1 pooled correct / listed per group.
  python -B sim_walk_rule.py
"""
import json
import sys
from collections import Counter, defaultdict

import fp_v9j as J
import fp_v9j_detail as D
import run_v9i as RI

HERE, CH, TR, V, REPS = J.HERE, J.CH, J.TR, J.V, J.REPS
VER = J.VER
INTERNAL = ("signal", "signal field", "record signal")


def spared_set():
    s = set()
    for rid, e in json.loads((HERE / "v9g_targets.json").read_text(encoding="utf-8")):
        s.add(e if e.startswith("neorv32_") else "neorv32_" + e)
    for f in ("meta_v9h_shapes.json", "meta_v9i.json", "meta_v9k2.json", "meta_v9k.json"):
        p = HERE / "new_rules" / f
        if p.exists():
            for rid, mt in json.loads(p.read_text(encoding="utf-8")).items():
                for key in ("intended_cases", "must_spare", "targets"):
                    for e in mt.get(key, []) or []:
                        s.add(e if e.startswith("neorv32_") else "neorv32_" + e)
    s |= {"neorv32_cpu_control:" + x for x in ("ctrl_o", "irq_machine_i", "irq_fast_i", "irq_dbg_i", "lsu_err_i", "pmp_fault_i", "lsu_wait_i", "alu_cp_done_i", "debug_ctrl.run", "hwtrig_start")}
    return s


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    g, ref = V.R10.CV.groups_and_ref()
    mods = list(g["tuning"]) + list(g["held-out"])
    groups = RI.groups()
    spared = spared_set()
    # per (m, r): listed names with their class
    rows = {}
    for m in mods:
        al = D.assign_lines(m)
        kd, _ = TR.kinds(m)
        for r in REPS:
            a, p1 = J.load(m, r, "assets"), J.load(m, r, "phase1")
            if a is None:
                continue
            concepts = {c["id"]: c for c in (p1["reply"].get("conceptual assets") or []) if isinstance(c, dict) and c.get("id")}
            lst = []
            for row in a["Assets"]:
                e = row["Asset RTL"]
                strict = False
                for c in (row.get("Concepts") or []):
                    cc = concepts.get(c, {})
                    if e in set(cc.get("enters through") or []) | set(cc.get("leaves through") or []) or (al.get(e, set()) & set(cc.get("held lines") or [])):
                        strict = True
                lst.append((e, kd.get(e, "?"), strict, f"{m}:{e}" in spared))
            rows[(m, r)] = lst

    def keep(variant, e, kind, strict, sp):
        if variant == "V0" or strict:
            return True
        if variant == "V1":
            return kind != "signal field"
        if variant == "V2":
            return kind not in INTERNAL
        if variant == "V3":
            return kind not in INTERNAL or sp
        raise ValueError(variant)

    def score(variant, ms):
        c = l = f = 0
        dropped_ok = dropped_fp = 0
        for m in ms:
            for r in REPS:
                if (m, r) not in rows:
                    continue
                kept = [e for (e, k, s, sp) in rows[(m, r)] if keep(variant, e, k, s, sp)]
                drop = [e for (e, k, s, sp) in rows[(m, r)] if not keep(variant, e, k, s, sp)]
                cnt = Counter(kept)
                found = 0
                for n in ref[m]:
                    if cnt[n] > 0:
                        cnt[n] -= 1
                        found += 1
                # what the drops were worth under V0
                cnt0 = Counter(e for (e, *_rest) in rows[(m, r)])
                left0 = Counter(cnt0)
                for n in ref[m]:
                    if left0[n] > 0:
                        left0[n] -= 1
                fp0 = Counter(left0.elements())
                for e in drop:
                    if fp0[e] > 0:
                        fp0[e] -= 1
                        dropped_fp += 1
                    else:
                        dropped_ok += 1
                c += found
                l += len(kept)
                f += len(ref[m])
        return {"correct": c, "listed": l, "findable": f, "recall": round(c / f, 3), "precision": round(c / l, 3) if l else None, "dropped correct": dropped_ok, "dropped FP": dropped_fp}

    out = {}
    for variant in ("V0", "V1", "V2", "V3"):
        out[variant] = {name: score(variant, ms) for name, ms in groups.items()}
    rj = json.loads((HERE / "read_v9j.json").read_text(encoding="utf-8"))["J1"]
    ok = all(out["V0"][name]["correct"] == rj[name]["candidate"]["pooled"]["correct"] and out["V0"][name]["listed"] == rj[name]["candidate"]["pooled"]["listed"] for name in groups)
    print(f"self-test (V0 reproduces read_v9j.json pooled correct / listed per group): {'PASS' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)
    v9g = {name: rj[name]["v9g"]["pooled"] for name in groups}
    for variant in ("V0", "V1", "V2", "V3"):
        print(variant)
        for name in groups:
            x = out[variant][name]
            print(f"  {name:12} R {x['recall']:.3f} P {x['precision']:.3f}  correct {x['correct']} listed {x['listed']}  dropped correct {x['dropped correct']} FP {x['dropped FP']}")
        x = out[variant]["tuning_v2"]
        print(f"  does-not-hurt vs v9g on tuning_v2 (R, P each >= v9g - 0.02): {x['recall'] >= v9g['tuning_v2']['recall'] - 0.02 and x['precision'] >= v9g['tuning_v2']['precision'] - 0.02}; vs v9j: dR {x['recall'] - out['V0']['tuning_v2']['recall']:+.3f} dP {x['precision'] - out['V0']['tuning_v2']['precision']:+.3f}")
    out["spared set size"] = len(spared)
    (HERE / "sim_walk_rule.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
