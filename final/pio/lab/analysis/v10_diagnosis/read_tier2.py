"""Tier 2 + the wording fix, one Phase 1-only run each (user 2026-10-19 17:10: "apply the word fix + tier 2 on the current working version.
finish within 30 mins"; scope cut to r0 screens). Arms against the working version two_phase_p1o_first (W; its Phase 1 r0 and pooled r0-r2):
  FIX two_phase_p1o_first2 (fixed port wording, indented slots, bar first); O1 bars first; O2 keeps first; O3 hard-to-easy; O4 easy-to-hard;
  O5 rules after OUTPUT (all five built on FIX, so each carries the fix too).
Readings (read_p1 definitions): located share r0, volume, concepts, not kept; paired per-entry sign test against W r0 (one run each side: an entry
counts up / down when located in one and not the other); the debug module's six reference entries, naming the reset-request output; the nine
traced entries; rule titles cited in not-kept reasons. One run per arm: differences under about 0.02 in share (four entries) are inside noise.
  python -B read_tier2.py
"""
import json
import re
import sys
from collections import Counter
from math import comb

import read_p1 as R

W = "two_phase_p1o_first"
ARMS = {"FIX first2": "two_phase_p1o_first2", "O1 bars first": "two_phase_p1t2_O1", "O2 keeps first": "two_phase_p1t2_O2",
        "O3 hard-to-easy": "two_phase_p1t2_O3", "O4 easy-to-hard": "two_phase_p1t2_O4", "O5 rules after OUTPUT": "two_phase_p1t2_O5"}
TRACED = [("neorv32_xbus", "xbus_dat_i"), ("neorv32_xbus", "xbus_stb_o"), ("neorv32_cpu_lsu", "err_o"), ("neorv32_debug_dm", "ndmrstn_o"), ("neorv32_gpio", "port_in"),
          ("neorv32_cpu_cp_cond", "ctrl_i"), ("neorv32_cpu_counters", "sel"), ("neorv32_cpu_counters", "cnt_en"), ("neorv32_cpu_counters", "rdata_o")]
DBG = "neorv32_debug_dm"


def p2(k, n):
    return min(1.0, sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n * 2) if n else 1.0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    g, ref = R.groups()
    ms = g["held-out 26"]
    rules = [m.group(1) for m in re.finditer(r"^- ([A-Z][^.\n]{2,60})\.", (R.LAB / "prompts" / W / "phase1.md").read_text(encoding="utf-8").replace("\r\n", "\n"), re.M)]
    def arm(v, r):
        names_all, cites = {}, Counter()
        for m in ms:
            names, reply = R.located_names(v, m, r)
            if names is None:
                return None
            names_all[m] = names
            for x in (reply.get("considered, not kept") or []):
                s = json.dumps(x, ensure_ascii=False).lower()
                for t in rules:
                    if t.lower() in s:
                        cites[t] += 1
        ent = {(m, n, i): int(n in names_all[m]) for m in ms for i, n in enumerate(ref[m])}
        return {"located": sum(ent.values()), "findable": len(ent), "volume": sum(len(x) for x in names_all.values()), "entries": ent,
                "debug ref": [n for n in ref[DBG] if n in names_all[DBG]], "debug count": len(names_all[DBG]),
                "traced": {f"{m[8:]}:{e}": int(e in names_all[m]) for m, e in TRACED}, "cites": dict(cites.most_common(6))}
    base = arm(W, 0)
    wp = R.read(W, ms, ref)["pooled"]
    out = {"W r0": {k: v for k, v in base.items() if k != "entries"}, "W pooled r0-r2": wp, "arms": {}}
    print(f"W {W} r0: located {base['located']}/{base['findable']} = {base['located']/base['findable']:.3f} vol {base['volume']} debug ref {len(base['debug ref'])}/6 count {base['debug count']} | pooled share {wp['share']}")
    print(f"   traced {base['traced']}")
    for name, v in ARMS.items():
        a = arm(v, 0)
        if a is None:
            print(f"{name:22} {v}: r0 incomplete"); out["arms"][name] = "incomplete"; continue
        up = sum(1 for k in base["entries"] if a["entries"][k] > base["entries"][k])
        down = sum(1 for k in base["entries"] if a["entries"][k] < base["entries"][k])
        share = a["located"] / a["findable"]
        out["arms"][name] = {k: v_ for k, v_ in a.items() if k != "entries"} | {"share": round(share, 3), "up vs W r0": up, "down": down, "p": round(p2(min(up, down), up + down), 3),
                                                                                  "reset output located": a["traced"]["debug_dm:ndmrstn_o"]}
        print(f"{name:22} r0: located {a['located']}/{a['findable']} = {share:.3f} (W r0 {base['located']/base['findable']:.3f}; up {up} down {down} p {p2(min(up, down), up + down):.2f}) vol {a['volume']} debug ref {len(a['debug ref'])}/6 count {a['debug count']} reset output {a['traced']['debug_dm:ndmrstn_o']}")
        print(f"   traced {a['traced']}  cites {a['cites']}")
    (R.HERE / "read_tier2.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
