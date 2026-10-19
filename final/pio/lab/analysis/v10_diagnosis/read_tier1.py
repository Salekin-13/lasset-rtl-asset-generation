"""Tier 1 of PLAN_P1_ORDER.md: the position of one added Phase 1 block. Five arms on the held-out 26, three Phase 1-only runs each:
  P0 absent = two_phase_v9n_place (A), P1 first = two_phase_p1o_first, P2 after the control-unit bar = two_phase_v9n_place_dbg,
  P3 last = two_phase_p1o_last, S sham at P2 = two_phase_p1o_sham.
Readings (fixed in the plan, section 6): (1) pooled located share and a per-entry sign test against P0 (for each reference entry the
number of runs it is located in, 0-3; discordant entries counted up and down; two-sided exact binomial); (2) located volume; (3) the
bar's firing in the debug module (its six reference entries located; the module's located count); (4) the nine entries D96 traced;
(5) per-rule firing of the target lists; (6) rule titles cited in "Considered, not kept" reasons. Gates: share within 0.01 of P0 AND
(3) in at least two runs. Self-test: P0 reproduces read_p1's A figures (158 / 159 / 152 of 187).
  python -B read_tier1.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from math import comb

import read_p1 as R

ARMS = {"P0 absent (A)": "two_phase_v9n_place", "P1 first": "two_phase_p1o_first", "P2 after control-unit bar": "two_phase_v9n_place_dbg",
        "P3 last": "two_phase_p1o_last", "S sham at P2": "two_phase_p1o_sham"}
TRACED = [("neorv32_xbus", "xbus_dat_i"), ("neorv32_xbus", "xbus_dat_o"), ("neorv32_xbus", "xbus_stb_o"), ("neorv32_xbus", "xbus_cyc_o"),
          ("neorv32_cpu_lsu", "err_o"), ("neorv32_debug_dm", "ndmrstn_o"), ("neorv32_gpio", "port_in"), ("neorv32_cpu_cp_cond", "ctrl_i"), ("neorv32_cpu_cp_shifter", "res_o")]
DBG = "neorv32_debug_dm"


def binom_two_sided(k, n):
    if n == 0:
        return 1.0
    p = sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n * 2
    return min(1.0, p)


def titles():
    t = (R.LAB / "prompts" / "two_phase_v9n_place" / "phase1.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    return [m.group(1) for m in re.finditer(r"^- ([A-Z][^.\n]{2,60})\.", t, re.M)]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    g, ref = R.groups()
    ms = g["held-out 26"]
    rules = titles()
    per = {}
    entry_runs = {}
    for arm, v in ARMS.items():
        runs = {}
        er = defaultdict(int)
        dbg = []
        traced = {f"{m[8:]}:{e}": [] for m, e in TRACED}
        cites = Counter()
        for r in (0, 1, 2):
            names_all = {}
            for m in ms:
                names, reply = R.located_names(v, m, r)
                if names is None:
                    names_all = None
                    break
                names_all[m] = names
                for x in (reply.get("considered, not kept") or []):
                    s = json.dumps(x, ensure_ascii=False).lower()
                    for t in rules:
                        if t.lower() in s:
                            cites[t] += 1
            if names_all is None:
                continue
            for m in ms:
                for i, n in enumerate(ref[m]):
                    er[(m, n, i)] += n in names_all[m]
            dref = [n for n in ref[DBG] if n in names_all[DBG]]
            dbg.append({"run": r, "reference located": len(dref), "located count": len(names_all[DBG])})
            for m, e in TRACED:
                traced[f"{m[8:]}:{e}"].append(int(e in names_all[m]))
            runs[r] = True
        x = R.read(v, ms, ref)
        per[arm] = {"version": v, "runs": sorted(runs), "read": {k: {kk: vv for kk, vv in val.items() if kk != "rules"} for k, val in x.items()},
                    "rules": {k: val.get("rules") for k, val in x.items() if k != "pooled"}, "debug": dbg, "traced": traced, "cites": dict(cites.most_common(12))}
        entry_runs[arm] = er
    base = entry_runs["P0 absent (A)"]
    ok = [per["P0 absent (A)"]["read"][f"r{r}"]["located"] for r in (0, 1, 2)] == [158, 159, 152]
    print(f"read_tier1 self-test (P0 = A: 158 / 159 / 152 located): {'PASS' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)
    out = {"arms": per, "paired vs P0": {}}
    p0 = per["P0 absent (A)"]["read"]["pooled"]
    for arm, er in entry_runs.items():
        if arm.startswith("P0") or len(per[arm]["runs"]) < 3:
            continue
        up = sum(1 for k in base if er[k] > base[k])
        down = sum(1 for k in base if er[k] < base[k])
        share = per[arm]["read"]["pooled"]["share"]
        dbg_ok = sum(1 for d in per[arm]["debug"] if d["reference located"] >= 5 and d["located count"] <= 12)
        out["paired vs P0"][arm] = {"entries located in more runs than A": up, "in fewer": down, "sign test p": round(binom_two_sided(min(up, down), up + down), 3),
                                    "pooled share": share, "A": p0["share"], "difference": round(share - p0["share"], 3),
                                    "gate share within 0.01 of A": abs(share - p0["share"]) <= 0.01,
                                    "bar fires in debug module (ref >= 5 located, module located count <= 12) runs": dbg_ok}
    (R.HERE / "read_tier1.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for arm, x in per.items():
        rd = x["read"]
        line = " | ".join(f"r{r} {rd[f'r{r}']['located']}/{rd[f'r{r}']['findable']} vol {rd[f'r{r}']['volume']}" for r in (0, 1, 2) if f"r{r}" in rd)
        pooled = rd.get("pooled", {})
        print(f"{arm:26} {line} || pooled share {pooled.get('share')} vol {pooled.get('volume')} concepts {pooled.get('concepts')} not kept {pooled.get('not kept')}")
        print(f"   debug: {[(d['reference located'], d['located count']) for d in x['debug']]}  traced: {x['traced']}")
    print("paired vs P0:", json.dumps(out["paired vs P0"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
