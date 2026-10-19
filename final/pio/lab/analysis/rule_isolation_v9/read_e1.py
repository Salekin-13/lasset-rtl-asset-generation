"""Rule-alone test of the E1 fix to Buffer and engine status bits (P1-17; user 2026-10-16: "Before building v10, apply
the E1 gloss fix to Buffer and engine status bits and test that rule alone first"). Code only, read-only on the runs;
writes e1_<tag>.json.

Sides: old = the current v10 text (variant v10m), new = the text with the two E1 edits (v10e1); both in v10's context
(merged procedure), old reply format, same executor. Claude run: v10m__claude1 vs v10e1__claude1 (claude_single.py,
one rule per agent, modules claude_single.PART1 / PART2). OpenAI run (notebook cell 19): v10m vs v10e1 on the 41.

Signal classes (fixed before the run; lists from the closed sets, hand-checked against the RTL: uart rtl 201-206 and
214-215 return the FIFO flags, rx_engine.over and tx_engine.busy in bus_rsp_o.data; gptmr rtl 94 returns irq_pnd,
rtl 98 timer.count, rtl 131 sets timer.match):
  MUST_NOT  gptmr timer.count, timer.match, irq_pnd; debug_dm dm_ctrl.cmderr, dm_ctrl.hart_reset; every response
            acknowledge / error line (name matching ACKERR) in the tested modules. Sequencing state leaves out timer
            counts and their compare flags and error and reset records; the scope edit leaves out lines that are not
            read data.
  TARGET    uart, spi, slink FIFO flags (avail, free, half) and engine busy / overrun bits (name matching TARGET).
Barred = covered by a run's barred list (analyze_isolation.covered: a whole record covers its fields).

Readings set before the run (2026-10-16; cuts chosen here, stated as such):
  E1-1 (primary; the diagnosis's falsifier) PASS when both hold, over the tested modules, both wordings, both runs:
       (a) the new text bars no MUST_NOT signal in any run;
       (b) TARGET signals barred in both runs: new >= old (no drop).
       PASS -> the fix may go into current_rules.json (the user decides). FAIL -> not adopted; say which part failed.
  E1-2 (read; what the PASS can mean) MUST_NOT element-runs barred by the OLD text. If 0, the executor does not show
       the misreading the fix targets: a PASS then means "does no harm", not "fixes it".
  E1-3 (read) disagreement rate old -> new, both wordings pooled (ambiguity_by_rule.measure); Phase 1 / Phase 2 stable
       disagreements.
  E1-4 (read) reference signals (exact name) barred by one run only / by both runs, old -> new.
What it does not settle: other modules (neorv32_bus is not in the Claude run: about 300,000 characters per request);
the full prompt.

Self-test (nothing is reported if it fails): the class lists equal the hand-read lists above; the decision logic on
synthetic replies (new bars timer.count -> FAIL; new drops a target -> FAIL; same as old with no MUST_NOT -> PASS).

  python -B read_e1.py claude      (v10m__claude1 vs v10e1__claude1, the modules with replies)
  python -B read_e1.py             (v10m vs v10e1, luna, cell 19)
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402
import analyze_isolation as A  # noqa: E402
import ambiguity_by_rule as AB  # noqa: E402
import compare_v10r as C  # noqa: E402

RID = "P1-17"
ACKERR = re.compile(r"rsp[^.]*\.(ack|err)$")
TARGET = re.compile(r"(fifo[^.]*\.(avail|free|half|full|empty))$|\.(busy|over)$")
TARGET_MODULES = {"neorv32_uart", "neorv32_spi", "neorv32_slink"}
NAMED = {"neorv32_gptmr": {"timer.count", "timer.match", "irq_pnd"}, "neorv32_debug_dm": {"dm_ctrl.cmderr", "dm_ctrl.hart_reset"}}
HAND = {"neorv32_uart": {"rx_engine.over", "rx_fifo.avail", "rx_fifo.free", "rx_fifo.half", "tx_engine.busy",
                         "tx_fifo.avail", "tx_fifo.free", "tx_fifo.half"}}


def classes(m):
    names = {n for (_, n) in ISO.CH.closed_names(m)}
    must = {n for n in names if ACKERR.search(n)} | (NAMED.get(m, set()) & names)
    tgt = {n for n in names if TARGET.search(n)} if m in TARGET_MODULES else set()
    return must, tgt


def load(variant, modules=None):
    ISO.use(variant)
    try:
        R = {k: v for k, v in A.load(lambda r: ISO.run_root(rep=r)).items()
             if k[0] == RID and (modules is None or k[2] in modules)}
    finally:
        ISO.use("v9")
    return R


def counts(R, modules):
    """MUST_NOT element-runs barred; TARGET element-wordings barred in both runs; per (phase, module)."""
    must_runs, tgt_both, must_list = 0, 0, []
    for m in modules:
        must, tgt = classes(m)
        for ph in ("P1", "P2"):
            reps = [R.get((RID, ph, m, r)) for r in (0, 1)]
            if any(x is None for x in reps):
                continue
            B = [A.names(x, "barred") for x in reps]
            for e in sorted(must):
                for r in (0, 1):
                    if A.covered(e, B[r]):
                        must_runs += 1
                        must_list.append(f"{ph} {m.replace('neorv32_', '')}:{e} r{r}")
            tgt_both += sum(1 for e in tgt if A.covered(e, B[0]) and A.covered(e, B[1]))
    return must_runs, tgt_both, must_list


def decide(old, new, modules):
    mo, to, _ = counts(old, modules)
    mn, tn, ln = counts(new, modules)
    return {"(a) MUST_NOT element-runs barred by new": mn, "(a) list": ln, "(b) TARGET both-run bars old -> new": [to, tn],
            "E1-2 MUST_NOT element-runs barred by old": mo, "verdict": "PASS" if mn == 0 and tn >= to else "FAIL"}


def selftest():
    bad = []
    if classes("neorv32_uart")[1] != HAND["neorv32_uart"]:
        bad.append(f"uart targets {sorted(classes('neorv32_uart')[1])}")
    if NAMED["neorv32_gptmr"] - classes("neorv32_gptmr")[0]:
        bad.append("gptmr named signals not in its closed set")
    m = "neorv32_uart"

    def rep(barred):
        return {"applies": "yes", "barred": [{"element": e} for e in barred], "spared": [], "unsure": []}
    tg = sorted(HAND[m])
    old = {(RID, ph, m, r): rep(tg) for ph in ("P1", "P2") for r in (0, 1)}
    g = "neorv32_gptmr"
    old.update({(RID, ph, g, r): rep([]) for ph in ("P1", "P2") for r in (0, 1)})
    same = dict(old)
    drop = dict(old)
    drop[(RID, "P1", m, 1)] = rep(tg[1:])
    wrong = dict(old)
    wrong[(RID, "P2", g, 0)] = rep(["timer.count"])
    mods = [m, g]
    if (decide(old, same, mods)["verdict"], decide(old, drop, mods)["verdict"], decide(old, wrong, mods)["verdict"]) != ("PASS", "FAIL", "FAIL"):
        bad.append("decision logic")
    return bad


def main(old_v="v10m", new_v="v10e1", tag="luna"):
    sys.stdout.reconfigure(encoding="utf-8")
    bad = selftest()
    print(f"self-test (hand-read class lists, decision logic on synthetic replies): {'PASS' if not bad else 'FAIL'} {bad or ''}")
    if bad:
        sys.exit(1)
    RN = load(new_v)
    if not RN:
        print(f"{new_v}: no replies stored yet")
        return
    mods = sorted({k[2] for k in RN} & {k[2] for k in load(old_v)})
    RO, RN = load(old_v, mods), load(new_v, mods)
    common = set(RO) & set(RN)
    RO = {k: v for k, v in RO.items() if k in common}
    RN = {k: v for k, v in RN.items() if k in common}
    print(f"{old_v} vs {new_v}: {len(common)} replies per side on {len(mods)} modules: {[m.replace('neorv32_', '') for m in mods]}")
    out = {"modules": mods, "replies per side": len(common), "E1-1": decide(RO, RN, mods)}
    e = out["E1-1"]
    print(f"\nE1-1 (primary): (a) MUST_NOT element-runs barred by the new text: {e['(a) MUST_NOT element-runs barred by new']} "
          f"{e['(a) list']}; (b) TARGET bars in both runs old -> new: {e['(b) TARGET both-run bars old -> new']} -> {e['verdict']}")
    print(f"E1-2: MUST_NOT element-runs barred by the old text: {e['E1-2 MUST_NOT element-runs barred by old']} "
          f"{counts(RO, mods)[2]}")
    rows = {}
    for name, R in (("old", RO), ("new", RN)):
        rep = A.analyze(R, None, {})
        f = u = 0
        for ph in ("P1", "P2"):
            if ph in rep.get(RID, {}):
                x = AB.measure(R, None, rep, RID, ph)
                f += x["flips"]
                u += x["decided (union)"]
        rows[name] = {"flips": f, "union": u, "rate": round(f / u, 3) if u else None,
                      "P1/P2": len(rep[RID]["Phase 1 / Phase 2 stable disagreements"]) if RID in rep else None}
    out["E1-3"] = rows
    print(f"E1-3: disagreement rate old {rows['old']['rate']} ({rows['old']['flips']}/{rows['old']['union']}) -> new "
          f"{rows['new']['rate']} ({rows['new']['flips']}/{rows['new']['union']}); P1/P2 {rows['old']['P1/P2']} -> {rows['new']['P1/P2']}")
    import read_e3 as E
    ref = E.reference()
    out["E1-4 reference barred (one run, both runs)"] = {"old": E.ref_barred(RO, [RID], ref), "new": E.ref_barred(RN, [RID], ref)}
    print("E1-4 reference signals barred (one run, both runs) old -> new:", out["E1-4 reference barred (one run, both runs)"])
    for name, R in (("old", RO), ("new", RN)):
        print(f"--- {name}: barred per run")
        for (rid, ph, m, r), x in sorted(R.items()):
            print(f"   {ph} {m.replace('neorv32_', '')} r{r}: {sorted(A.names(x, 'barred'))}")
    (HERE / f"e1_{tag}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwritten e1_{tag}.json")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "claude":
        main("v10m__claude1", "v10e1__claude1", "claude")
    else:
        main()
