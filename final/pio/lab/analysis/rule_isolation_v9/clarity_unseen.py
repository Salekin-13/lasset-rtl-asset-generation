"""Clarity test on modules no run, rule or fix has read (user 2026-10-15: "do the clarity test"). Code only, read-only
on the runs; writes clarity_unseen.json. CLARITY ONLY: these modules have no reference entries, so nothing here is
precision or recall. It measures whether each rule gives the same answer twice (disagreement rate, ambiguity_by_rule),
old wording (v9) against the latest wording, on modules the fixes were not made from.

Runs (notebook cell 16; isolation.UNSEEN_PLAN): the 17 rules re-tested since v9, alone, 2 repeats, on neorv32_crc,
neorv32_dma, neorv32_clint, neorv32_cfs (inputs built by unseen6/build_maps.py + build_inputs.py) and neorv32_fifo,
neorv32_boot_rom (inputs/v1): v9 wordings ("v9__unseen6") and the latest wordings ("v10r__unseen6" 13 rules,
"v10f__unseen6" Sequencing state and Port options, "v10f2__unseen6" Clocks and resets, "v10f3__unseen6" Slices), plus
Slices without "(never the whole element)" ("v10f4__unseen6" and "v10f4" on the 41).

Measure (ambiguity_by_rule.measure, unchanged): disagreement rate = signals one run bars and the other does not /
signals either run bars, pooled over modules and wordings. These modules were not picked for disagreeing, so no
regression to the mean flatters either side. Each latest wording also changed the shared context and, for the
facts-first rules, the reply format, as on the 41 modules.

Readings set before the run (2026-10-15; cuts chosen, stated as such):
  U1 (primary) summed over the 17 rules, the latest wordings' pooled disagreement rate on the 6 modules is below v9's
     by at least 18% of v9's rate (half the relative drop on the 41 modules: 0.347 -> 0.221, -36%). Pass = the
     clarity gains carry over to new modules; a smaller drop or a rise = they were tuned to the 41. Read as "too few
     to tell" if either side decides fewer than 100 signals (on the 41, v9 decided 2,976 over 41 modules).
  U2 (read, not gated) per rule deciding something in 3+ module-wordings on both sides: does its rate move in the same
     direction as on the 41 (v9 -> latest)?
  U3 (read) Phase 1 / Phase 2 stable disagreements summed over the 17 rules, v9 -> latest, on the 6 modules.
  S1 (Slices) on the 41: v10f4's pooled disagreement rate below v10f3's, and its Phase 1 / Phase 2 stable
     disagreements below v10f3's 4. Judged on the total, not on named signals. Watch only (tests the reasoning that
     criterion (2) excludes it): imem addr_ff (data/RTL_data/neorv32_imem.vhd 101 `addr <= unsigned(bus_req_i.addr(
     addr_hi_c downto 2));`, 92 `addr_ff <= addr;`) barred in no run.
Self-test (nothing is reported if it fails): on the stored 41-module runs the same code gives v9 1,033 / 2,976 = 0.347
and latest 508 / 2,303 = 0.221 for the 17 rules (ambiguity_by_rule.json, 2026-10-15), and v10f3 Slices 4 P1/P2.

  python -B clarity_unseen.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402
import analyze_isolation as A  # noqa: E402
import ambiguity_by_rule as AB  # noqa: E402

LATEST_OF = {r: v for v, rs in ISO.LATEST.items() for r in rs}


def collect(variant, rules):
    """{rule: {"flips", "union", "split", "deciding", "P1/P2", per phase}} for the stored replies of `variant`."""
    R, _texts = AB.load(variant)
    R = {k: v for k, v in R.items() if k[0] in rules}
    if not R:
        return {}
    rep = A.analyze(R, None, {})
    out = {}
    for rid in rules:
        if rid not in rep:
            continue
        row = {"flips": 0, "union": 0, "split": 0, "deciding": 0, "modules": 0,
               "P1/P2": len(rep[rid]["Phase 1 / Phase 2 stable disagreements"]),
               "P1/P2 list": rep[rid]["Phase 1 / Phase 2 stable disagreements"]}
        for ph in ("P1", "P2"):
            if ph not in rep[rid]:
                continue
            x = AB.measure(R, None, rep, rid, ph)
            row[ph] = {k: v for k, v in x.items() if not k.startswith("_")}
            for k, kk in (("flips", "flips"), ("union", "decided (union)"), ("split", "split modules"),
                          ("deciding", "deciding"), ("modules", "modules")):
                row[k] += x[kk]
        row["rate"] = round(row["flips"] / row["union"], 3) if row["union"] else None
        out[rid] = row
    return out


def pooled(rows):
    f = sum(r["flips"] for r in rows)
    u = sum(r["union"] for r in rows)
    return f, u, (f / u if u else None)


def side(suffix, rules17):
    """v9 side and latest side for the 17 rules (suffix "" = the 41 modules, "__unseen6" = the 6)."""
    old = collect("v9" + suffix, rules17)
    new = {}
    for v, rs in ISO.LATEST.items():
        new.update(collect(v + suffix, rs))
    return old, new


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    # self-test on the stored 41-module runs
    o41, n41 = side("", ISO.RULES17)
    f9, u9, r9 = pooled(o41.values())
    fl, ul, rl = pooled(n41.values())
    s3 = collect("v10f3", ["P1-09"]).get("P1-09", {})
    ok = (f9, u9, fl, ul) == (1033, 2976, 508, 2303) and s3.get("P1/P2") == 4
    print(f"self-test (41 modules: v9 {f9}/{u9}, latest {fl}/{ul}, v10f3 Slices P1/P2 {s3.get('P1/P2')}; "
          f"expected 1033/2976, 508/2303, 4): {'PASS' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)
    out = {"41 modules": {"v9": [f9, u9, round(r9, 3)], "latest": [fl, ul, round(rl, 3)], "relative change": round(rl / r9 - 1, 3)}}

    # the 6 unseen modules
    ou, nu = side("__unseen6", ISO.RULES17)
    if not ou or not nu:
        print("the __unseen6 runs are not stored yet (notebook cell 16)")
        return
    have = sorted({k[2] for k in AB.load("v9__unseen6")[0]})
    print(f"unseen modules with replies (v9 side): {have}")
    F9, U9, R9 = pooled(ou.values())
    FL, UL, RL = pooled(nu.values())
    rel = (RL / R9 - 1) if R9 else None
    few = U9 < 100 or UL < 100
    u1 = None if few else (RL < R9 and rel <= -0.18)
    out["6 unseen modules"] = {"v9": [F9, U9, round(R9, 3) if R9 is not None else None],
                               "latest": [FL, UL, round(RL, 3) if RL is not None else None],
                               "relative change": round(rel, 3) if rel is not None else None,
                               "U1 pass": u1, "U1 too few to tell": few}
    print(f"\nU1: 17 rules pooled, disagreement rate v9 -> latest: 41 modules {r9:.3f} -> {rl:.3f} ({rl / r9 - 1:+.0%}); "
          f"6 unseen {R9:.3f} -> {RL:.3f} ({rel:+.0%}); signals decided {U9} / {UL}; "
          f"{'TOO FEW TO TELL' if few else ('PASS' if u1 else 'FAIL')} (cut: -18% or more)")
    # U2 per rule
    print(f"\n{'rule':6s} {'title':30s} | 41: v9 -> latest | unseen: v9 -> latest (split/deciding) | same direction")
    titles = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    per, agree, n2 = {}, 0, 0
    for rid in ISO.RULES17:
        a41, b41 = o41.get(rid), n41.get(rid)
        a, b = ou.get(rid), nu.get(rid)
        enough = a and b and a["deciding"] >= 3 and b["deciding"] >= 3
        same = None
        if enough and a41 and b41 and a["rate"] is not None and b["rate"] is not None:
            d41, du = b41["rate"] - a41["rate"], b["rate"] - a["rate"]
            same = (d41 < 0) == (du < 0) if d41 != 0 and du != 0 else None
            if same is not None:
                n2 += 1
                agree += same
        per[rid] = {"title": titles[rid]["title"], "latest variant": LATEST_OF[rid],
                    "41": [a41["rate"] if a41 else None, b41["rate"] if b41 else None],
                    "unseen": [a["rate"] if a else None, b["rate"] if b else None],
                    "unseen split/deciding": [f"{a['split']}/{a['deciding']}" if a else None, f"{b['split']}/{b['deciding']}" if b else None],
                    "unseen P1/P2": [a["P1/P2"] if a else None, b["P1/P2"] if b else None], "same direction": same}
        p = per[rid]
        print(f"{rid:6s} {titles[rid]['title'][:30]:30s} | {p['41'][0]} -> {p['41'][1]} | {p['unseen'][0]} -> {p['unseen'][1]} "
              f"({p['unseen split/deciding'][0]} -> {p['unseen split/deciding'][1]}) | "
              f"{'yes' if same else 'no' if same is False else 'too few'}")
    out["U2 per rule"] = per
    out["U2 same direction"] = f"{agree} of {n2} rules with 3+ deciding module-wordings on both sides"
    print("U2:", out["U2 same direction"])
    s_old = sum(r["P1/P2"] for r in ou.values())
    s_new = sum(r["P1/P2"] for r in nu.values())
    out["U3 P1/P2 stable disagreements, 6 modules"] = f"{s_old} -> {s_new}"
    print("U3: Phase 1 / Phase 2 stable disagreements on the 6 modules, v9 -> latest:", out["U3 P1/P2 stable disagreements, 6 modules"])
    # S1 Slices
    s4 = collect("v10f4", ["P1-09"]).get("P1-09")
    if s4:
        s1 = s4["rate"] < s3["rate"] and s4["P1/P2"] < s3["P1/P2"]
        R4, _ = AB.load("v10f4")
        addr = [A.covered("addr_ff", A.names(R4[k], "barred")) for k in R4 if k[2] == "neorv32_imem"]
        out["S1 Slices on the 41"] = {"v10f3": [s3["rate"], s3["P1/P2"]], "v10f4": [s4["rate"], s4["P1/P2"]], "pass": s1,
                                      "watch: imem addr_ff barred in (runs)": f"{sum(addr)} of {len(addr)}",
                                      "v10f4 P1/P2 list": s4["P1/P2 list"]}
        print(f"S1: Slices on the 41, rate v10f3 {s3['rate']} -> v10f4 {s4['rate']}, P1/P2 {s3['P1/P2']} -> {s4['P1/P2']}: "
              f"{'PASS' if s1 else 'FAIL'}; watch addr_ff barred in {sum(addr)} of {len(addr)} replies")
    su = {v: collect(v + "__unseen6", ["P1-09"]).get("P1-09") for v in ("v9", "v10f3", "v10f4")}
    out["Slices on the 6 (read)"] = {v: ([x["rate"], x["P1/P2"], f"{x['split']}/{x['deciding']}"] if x else None) for v, x in su.items()}
    print("Slices on the 6 unseen modules (rate, P1/P2, split/deciding):", out["Slices on the 6 (read)"])
    (HERE / "clarity_unseen.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nwritten clarity_unseen.json")


if __name__ == "__main__":
    main()
