"""Facts-first test (v10f, notebook cell 13) against the v10 re-test (v10r, cell 12), for the four rules rewritten
facts-first: Sequencing state, Port options, Clocks and resets, Slices. Code only; writes compare_v10f.json.

The v10f replies use the facts format (isolation.SYSTEM_HEAD_FACTS); isolation.from_facts maps them to the barred /
spared lists, so compare_v10r.measures runs unchanged on both (two readings, format, one-sided, applied once, unsure,
stable, stable on reference by exact name).
Instrument (measures, changes nothing): decisions whose verdict contradicts the reply's own facts (isolation.against_facts).

Readings set before the run (2026-10-15; cuts chosen, stated as such):
  F1 (primary; needs the reader round: python -B make_onesided_pack.py v10f, readers, tally_onesided.py <journal>
     onesided_v10f) over-applied share of the sampled one-sided cases at most half of v10r's on the same 8 wordings
     (v10r: 27 of 38 = 71%; pass at 36% or less), and the missed share not above v10r's (7 of 38 = 18%).
  F2 two readings, one-sided differences and applied-once modules fall, summed over the four rules.
  F3 stable decisions on reference elements (exact name) do not rise for any rule.
  F4 (read, not gated) verdicts against own facts, as a share of all decisions.

  python -B compare_v10f.py                 (v10r -> v10f, the four rules)
  python -B compare_v10f.py v10f v10f2      (2026-10-15, user "apply" G2: Slices and Clocks and resets re-tested; writes
                                            compare_v10f2.json). Readings set before that run: Slices misses in a reader
                                            sample fall from 10 of 10 to at most 3, and over-application stays at most 2;
                                            Clocks and resets (c): cpu_lsu err_o, bus sc_fail and the bus_rsp_o.ack the
                                            readers named are barred in neither run; the wdt targets (reset_force,
                                            ctrl.strict, hw_rst_access) stay barred in both. Known before the run (skeptic,
                                            wf_0ad7a376-977): Slices' stable bars on reference elements may rise to about
                                            6, because the rule's words cover bus keeper.halt, gpio port_in and
                                            cpu_cp_shifter bs_result (judge F3 on the other reference elements); the
                                            "two readings" count is not comparable, since v10f2's format removes "an
                                            exception applies" (read one-sided counts and the reader sample instead).
  python -B compare_v10f.py v10f2 v10f3     (2026-10-15, user "ok": Slices alone with "never the whole element" and
                                            "concatenated (side by side, with no constant, not combined by a logic or
                                            arithmetic operator)"). Readings set before the run (skeptic wf_01405c28-4ea):
                                            imem addr_ff, sdi sync.sck, twd smp.scl, cpu_control opcode and sys sreg_ext
                                            barred in no run; debug_dm dci.req_res barred in no run (a whole copy, bit by
                                            bit: outside Slices by design, moved off the must-bar list) and Slices' stable
                                            P1/P2 disagreements 1 -> 0; the 9 must-not-bar signals stay unbarred; the
                                            other 8 earlier misses stay barred where v10f2 barred them. If gpio port_in
                                            drops, the cause is the generic-width reading (GPIO_NUM can be 32), not a
                                            regression. Known reading slips the fix does not touch: cy_q, keeper.halt,
                                            acc_adr, rtx_engine.cs_ctrl.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402
import compare_v10r as C  # noqa: E402

RULES = ["P1-15", "P1-18", "P1-02", "P1-09"]


def main(old="v10r", new="v10f"):
    sys.stdout.reconfigure(encoding="utf-8")
    _, refl = C.CV.groups_and_ref()
    ref = {m: set(v) for m, v in refl.items()}
    prim = Counter()
    for m in ref:
        for r in (0, 1, 2):
            f = ISO.CH.run_dir(ISO.V9, "gpt-5.6-luna", r, "high") / "assets" / f"{m}.json"
            for n in {x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]}:
                prim[(m, n)] += 1
    Rf, Tf = C.load(new, RULES)
    rules = [r for r in RULES if r in Tf]
    Rr, Tr = C.load(old, rules)
    print(f"replies: {old} {len(Rr)}, {new} {len(Rf)} ({', '.join(rules)})")
    if not Rf:
        return
    mr, _ = C.measures(Rr, Tr, rules, ref, prim)
    mf, _ = C.measures(Rf, Tf, rules, ref, prim)
    keys = ("two readings", "format", "applied once", "unsure modules", "stable", "stable on reference (exact)")
    print(f"\n{'rule':6s} {'title':24s} ph | two readings | one-sided left/empty | applied once | unsure | stable(ref) | {old} -> {new}")
    tot = Counter()
    for rid in rules:
        for ph in ("P1", "P2"):
            if ph not in mr.get(rid, {}) or ph not in mf.get(rid, {}):
                continue
            a, b = mr[rid][ph], mf[rid][ph]
            for tag, x in (("old", a), ("new", b)):
                tot[(tag, "two readings")] += x["two readings"]
                tot[(tag, "one-sided")] += sum(x["one-sided (left out / other run empty)"])
                tot[(tag, "applied once")] += x["applied once"]
            print(f"{rid:6s} {Tr[rid]['title'][:24]:24s} {ph} | {a['two readings']} -> {b['two readings']} | "
                  f"{a['one-sided (left out / other run empty)']} -> {b['one-sided (left out / other run empty)']} | "
                  f"{a['applied once']} -> {b['applied once']} | {a['unsure modules']} -> {b['unsure modules']} | "
                  f"{a['stable']}({a['stable on reference (exact)']}) -> {b['stable']}({b['stable on reference (exact)']})")
    F2 = {k: f"{tot[('old', k)]} -> {tot[('new', k)]}" for k in ("two readings", "one-sided", "applied once")}
    F2["pass"] = all(tot[("new", k)] < tot[("old", k)] for k in ("two readings", "one-sided", "applied once"))
    F3 = {}
    for rid in rules:
        r10 = sum(mr[rid][ph]["stable on reference (exact)"] for ph in ("P1", "P2") if ph in mr[rid])
        r10f = sum(mf[rid][ph]["stable on reference (exact)"] for ph in ("P1", "P2") if ph in mf.get(rid, {}))
        F3[rid] = {f"{old} -> {new}": f"{r10} -> {r10f}", "pass": r10f <= r10}
    # instrument: verdicts against own facts
    ISO.use(new)
    dec = against = 0
    by = Counter()
    for r in (0, 1):
        for f in ISO.run_root(rep=r).glob("P*/*/*.json"):
            rec = json.loads(f.read_text(encoding="utf-8"))
            n = len([d for d in ((rec.get("facts reply") or {}).get("decisions") or []) if isinstance(d, dict)])
            a = ISO.against_facts(rec.get("facts reply"))      # recomputed: "any of" parts need only one to hold
            dec += n
            against += a
            by[rec["rule"]] += a
    ISO.use("v9")
    F4 = {"decisions": dec, "against own facts": against, "share": round(against / dec, 4) if dec else None, "by rule": dict(by)}
    out = {old: mr, new: mf, "F2": F2, "F3": F3, "F4": F4}
    (HERE / f"compare_{new}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nF2 (summed over the four rules):", F2)
    print("F3 stable on reference (exact):", F3)
    print("F4 verdicts against own facts:", F4)
    print(f"F1 needs the reader round: python -B make_onesided_pack.py {new}, then the readers, then "
          f"python -B tally_onesided.py <journal> onesided_{new}")


if __name__ == "__main__":
    main(*(sys.argv[1:3] if len(sys.argv) > 2 else ()))
