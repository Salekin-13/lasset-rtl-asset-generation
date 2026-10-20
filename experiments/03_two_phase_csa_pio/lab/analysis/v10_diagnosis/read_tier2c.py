"""Tier 2 confirmation (user 2026-10-19: "Run two more Phase 1-only runs each of two_phase_p1t2_O4 and two_phase_p1t2_O5 ... measure against
the working version with the paired per-entry test"). Arms O4 easy-to-hard and O5 rules-after-OUTPUT, runs r0-r2, against the working version
two_phase_p1o_first r0-r2 (W), on the held-out 26. Readings as Tier 1 (read_tier1.py): pooled located share; per-entry runs located (0-3) per arm
against W, sign test on discordant entries; volume; the debug module's reference entries and names; the traced entries; not-kept citations.
Gate (as section 6): share at least W's pooled share (0.825) and volume not above W's (324 mean) for an order to be a candidate.
  python -B read_tier2c.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from math import comb

import read_p1 as R

W = "two_phase_p1o_first"
ARMS = {"O4 easy-to-hard": "two_phase_p1t2_O4", "O5 rules after OUTPUT": "two_phase_p1t2_O5", "O3 hard-to-easy (r0 only)": "two_phase_p1t2_O3", "O2 keeps first (r0 only)": "two_phase_p1t2_O2", "O1 bars first (r0 only)": "two_phase_p1t2_O1", "FIX first2 (r0 only)": "two_phase_p1o_first2"}
TRACED = [("neorv32_xbus", "xbus_dat_i"), ("neorv32_xbus", "xbus_stb_o"), ("neorv32_cpu_lsu", "err_o"), ("neorv32_debug_dm", "ndmrstn_o"), ("neorv32_gpio", "port_in"),
          ("neorv32_cpu_cp_cond", "ctrl_i"), ("neorv32_cpu_counters", "sel"), ("neorv32_cpu_counters", "cnt_en"), ("neorv32_cpu_counters", "rdata_o")]
DBG = "neorv32_debug_dm"


def p2(k, n):
    return min(1.0, sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n * 2) if n else 1.0


def arm(v, ms, ref):
    runs, er, dbg, traced, vol = [], defaultdict(int), [], defaultdict(list), []
    for r in (0, 1, 2):
        names_all = {}
        for m in ms:
            names, reply = R.located_names(v, m, r)
            if names is None:
                names_all = None
                break
            names_all[m] = names
        if names_all is None:
            continue
        runs.append(r)
        vol.append(sum(len(x) for x in names_all.values()))
        for m in ms:
            for i, n in enumerate(ref[m]):
                er[(m, n, i)] += n in names_all[m]
        dbg.append((sum(1 for n in ref[DBG] if n in names_all[DBG]), len(names_all[DBG])))
        for m, e in TRACED:
            traced[f"{m[8:]}:{e}"].append(int(e in names_all[m]))
    return {"runs": runs, "entries": er, "located": sum(er.values()), "findable": len(ref_entries(ms, ref)) * len(runs), "volume": vol, "debug": dbg, "traced": dict(traced)}


def ref_entries(ms, ref):
    return [(m, n, i) for m in ms for i, n in enumerate(ref[m])]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    g, ref = R.groups()
    ms = g["held-out 26"]
    base = arm(W, ms, ref)
    out = {"W": {"runs": base["runs"], "located": base["located"], "findable": base["findable"], "share": round(base["located"] / base["findable"], 3), "volume": base["volume"], "debug": base["debug"], "traced": base["traced"]}, "arms": {}}
    print(f"W {W}: runs {base['runs']} located {base['located']}/{base['findable']} = {base['located']/base['findable']:.3f} volume {base['volume']} debug {base['debug']}")
    for name, v in ARMS.items():
        a = arm(v, ms, ref)
        if not a["runs"]:
            print(f"{name}: no complete run"); continue
        nb = len(base["runs"]); na = len(a["runs"])
        # per-entry comparison on run counts, scaled when the arm has fewer runs: compare located share per entry (runs located / runs)
        up = down = 0
        for k in base["entries"]:
            sa, sb = a["entries"][k] / na, base["entries"][k] / nb
            up += sa > sb; down += sa < sb
        share = a["located"] / a["findable"]
        gate = share >= 0.825 and (sum(a["volume"]) / na) <= 324
        out["arms"][name] = {"version": v, "runs": a["runs"], "located": a["located"], "findable": a["findable"], "share": round(share, 3), "volume": a["volume"], "up vs W": up, "down": down,
                             "sign test p": round(p2(min(up, down), up + down), 3), "debug": a["debug"], "traced": a["traced"], "gate (share >= 0.825 and mean volume <= 324)": gate}
        print(f"{name:28} runs {a['runs']}: located {a['located']}/{a['findable']} = {share:.3f} (W {base['located']/base['findable']:.3f}); up {up} down {down} p {p2(min(up, down), up + down):.3f}; volume {a['volume']}; debug {a['debug']}; gate {gate}")
        print(f"   traced {a['traced']}")
    (R.HERE / "read_tier2c.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
