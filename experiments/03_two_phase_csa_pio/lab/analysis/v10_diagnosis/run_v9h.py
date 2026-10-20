"""Stage C, first cell: two_phase_v9h (v9g + four keep blocks) on the K1 failure modules, r0-r2, two phases chained
(PLAN_ISOLATE_CLUSTER_ORDER.md section 8). NOT sent without the user's go-ahead on the cost.

Cell modules (held-out, so v9g's stored r0-r2 is the free baseline): the prefetch unit, the link, the inter-core unit,
the counters, the control unit, the debug module, the external bus (K11 also claims its acknowledge and error inputs).
Readings (set 2026-10-18 before any call; exact scorer; v9g r0-r2 on the same six modules is the comparison):
  C1 per block: its targets (meta_v9h.json intended cases) found per run, against v9g's 3 runs; "followed" when every
     target is found in at least 2 of 3 runs; each miss with where_lost's stage.
  C2 exact correct, listed, recall and precision on the six modules, per run and pooled, against v9g r0-r2; a change
     counts when it holds in every run and moves at least 3 correct finds pooled.
  C3 watch: the cluster's other lost entries (WATCH_REF: prefetch flags, the inter-core push and flag, the link's data
     and frame-end outputs) found per run, and the non-reference elements the blocks might keep (WATCH_HARM) listed per run.
  C4 reply-format slips: Phase 2 replies with a format problem (chain's checks) per run, against v9g.
Self-test: the readers on v9g r0-r2 as the candidate reproduce v9g's own per-run correct counts on the six modules and
give "no change shown"; targets and watch names are closed-set names with the stated reference status.

  python -B run_v9h.py selftest
  python -B run_v9h.py preview
  <conda python> run_v9h.py run --remaining=<USD>
  python -B run_v9h.py measure          (writes read_v9h.json)
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402

sys.path.insert(0, str(LAB / "analysis" / "heldout_versions__gpt-5.6-luna__high__r0-r2"))
import v11 as V  # noqa: E402
import compare_v11h as C  # noqa: E402
import heldout_recall as HR  # noqa: E402
import transitions as TR  # noqa: E402

CH, run_a = V.CH, V.run_a
V9H, V9G = "two_phase_v9h", "two_phase_v9g"
MODS = ["neorv32_cpu_frontend", "neorv32_slink", "neorv32_cpu_icc", "neorv32_cpu_counters", "neorv32_cpu_control", "neorv32_debug_dm", "neorv32_xbus"]
REPS = (0, 1, 2)
MARGIN = 0.32
META = json.loads((HERE / "new_rules" / "meta_v9h.json").read_text(encoding="utf-8"))
WATCH_REF = ["cpu_frontend:ipb.free", "cpu_frontend:ipb.avail", "cpu_icc:tx_fifo_we", "cpu_icc:tx_fifo_free", "slink:slink_tx_data_o",
             "slink:slink_tx_last_o", "cpu_counters:cnt_en"]
WATCH_HARM = ["slink:rx_fifo.we", "slink:tx_fifo.re", "slink:tx_fifo.avail", "slink:rx_fifo.free", "cpu_frontend:ipb.we", "cpu_frontend:ipb.re",
              "debug_dm:dm_ctrl.state", "cpu_counters:cnt_acc", "cpu_counters:cfg_acc"]


def groups():
    return V.R10.CV.groups_and_ref()


def targets():
    """the blocks' intended cases inside the cell modules (cases in tuning modules are basis cases, not cell targets)."""
    return {rid: [c.replace("neorv32_", "") for c in m["intended_cases"] if c.split(":")[0] in MODS] for rid, m in META.items()}


def found(v, r, c):
    m, e = "neorv32_" + c.split(":")[0], c.split(":", 1)[1]
    ls = HR.names(v, r, m)
    return None if ls is None else bool(HR.found_occ(V.cvref()[m], ls).get((e, 1)))


def listed(v, r, c):
    m, e = "neorv32_" + c.split(":")[0], c.split(":", 1)[1]
    a = V.assets(v, m, r)
    return None if a is None else (e in a)


def rows(v, reps):
    _, refl = groups()
    fd = sum(len(refl[m]) for m in MODS)
    out = []
    for r in reps:
        s = [C.score_dir(CH.run_dir(v, MODEL, r, EFFORT), m) for m in MODS]
        if all(x is None for x in s):
            continue
        tp, ln = sum(x[1] for x in s if x), sum(x[0] for x in s if x)
        out.append({"run": r, "correct": tp, "listed": ln, "findable": fd, "recall": round(tp / fd, 3), "precision": round(tp / ln, 3) if ln else None,
                    "missing": [m[8:] for m, x in zip(MODS, s) if x is None]})
    return out


def slips(v, reps):
    out = []
    for r in reps:
        n = 0
        for m in MODS:
            f = CH.run_dir(v, MODEL, r, EFFORT) / "phase2" / f"{m}.json"
            if f.exists():
                n += any(str(p).startswith("format:") for p in json.loads(f.read_text(encoding="utf-8")).get("problems") or [])
        out.append(n)
    return out


def readers(v, reps):
    out = {}
    cand, base = rows(v, reps), rows(V9G, REPS)
    pc, pb = sum(x["correct"] for x in cand), sum(x["correct"] for x in base)
    verdict = "no change shown"
    if cand and all(x["correct"] > max(y["correct"] for y in base) for x in cand) and pc - pb >= 3:
        verdict = "rise shown"
    elif cand and all(x["correct"] < min(y["correct"] for y in base) for x in cand) and pb - pc >= 3:
        verdict = "drop shown"
    out["C2 six modules"] = {"candidate": cand, "v9g r0-r2": base, "verdict": verdict,
                             "pooled candidate correct": pc, "pooled v9g correct": pb}
    c1 = {}
    for rid, cases in targets().items():
        fc = [sum(bool(found(v, r, c)) for c in cases) for r in reps]
        fb = [sum(bool(found(V9G, r, c)) for c in cases) for r in REPS]
        per = {c: [found(v, r, c) for r in reps] for c in cases}
        c1[rid] = {"title": META[rid].get("title", rid), "targets": len(cases), "found per run": fc, "v9g": fb,
                   "followed (every target in 2 of 3 runs)": all(sum(bool(x) for x in per[c]) >= 2 for c in cases) if len(reps) == 3 else None,
                   "per target": per}
    out["C1 per block"] = c1
    out["C3 watch reference entries found per run"] = {name: [sum(bool(found(vv, r, c)) for c in WATCH_REF) for r in rr]
                                                     for name, vv, rr in (("candidate", v, reps), ("v9g", V9G, REPS))}
    out["C3 watch non-reference listed per run"] = {name: [sum(bool(listed(vv, r, c)) for c in WATCH_HARM) for r in rr]
                                                   for name, vv, rr in (("candidate", v, reps), ("v9g", V9G, REPS))}
    out["C4 Phase 2 replies with a format problem per run"] = {"candidate": slips(v, reps), "v9g": slips(V9G, REPS)}
    return out


def measure(v=V9H, path=None):
    out = {"candidate": v, "readings": readers(v, REPS)}
    lost = {}
    for rid, cases in targets().items():
        for c in cases:
            m, e = "neorv32_" + c.split(":")[0], c.split(":", 1)[1]
            for r in REPS:
                ls = HR.names(v, r, m)
                if ls is not None and not HR.found_occ(V.cvref()[m], ls).get((e, 1)):
                    lost.setdefault(c, []).append(f"r{r}: {TR.where_lost(v, r, m, e, ls)[0]}")
    out["C1 where the targets are lost"] = lost
    p = path or (HERE / "read_v9h.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    return out


def selftest(log=print):
    c = {}
    _, refl = groups()
    c["prompt folder exists and passes check_lab_prompt"] = (LAB / "prompts" / V9H / "phase1.md").exists() and V.CK.check(V9H, log=lambda *a: None)
    z = readers(V9G, REPS)
    c["zero point: v9g as the candidate gives its own counts and 'no change shown'"] = (
        [x["correct"] for x in z["C2 six modules"]["candidate"]] == [x["correct"] for x in z["C2 six modules"]["v9g r0-r2"]] and z["C2 six modules"]["verdict"] == "no change shown")
    tg = [c_ for cases in targets().values() for c_ in cases]
    c["targets are held-out reference entries of the cell modules"] = all("neorv32_" + t.split(":")[0] in MODS and t.split(":", 1)[1] in refl["neorv32_" + t.split(":")[0]] for t in tg)
    c["watch reference names are reference entries"] = all(x.split(":", 1)[1] in refl["neorv32_" + x.split(":")[0]] for x in WATCH_REF)
    c["watch harm names are non-reference closed-set names"] = all(
        x.split(":", 1)[1] not in refl["neorv32_" + x.split(":")[0]] and x.split(":", 1)[1] in {n for (_, n) in CH.closed_names("neorv32_" + x.split(":")[0])} for x in WATCH_HARM)
    c["six cell modules are held-out modules"] = all(m in groups()[0]["held-out"] for m in MODS)
    bad = [k for k, v in c.items() if not v]
    log(f"run_v9h self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def growth():
    s = [len(V.CK.system(V9H, ph)) / len(V.CK.system(V9G, ph)) for ph in (1, 2)]
    return sum(s) / len(s)


def estimate():
    s = 0.0
    for r in REPS:
        for m in MODS:
            for ph in (1, 2):
                f = CH.run_dir(V9G, MODEL, r, EFFORT) / f"phase{ph}" / f"{m}.json"
                s += run_a.usd(json.loads(f.read_text(encoding="utf-8"))["usage"])
    return s, s * growth()


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    base, est = estimate()
    print(f"prompt growth v9h / v9g (system text): x{growth():.3f}")
    print(f"cell: {len(MODS)} modules x 3 runs x 2 phases = {len(MODS) * 6} calls; v9g's stored cost of the same cells USD {base:.2f}; estimate USD {est:.2f}; needs USD {est + MARGIN:.2f} left")
    print(f"spent so far (counter) USD {run_a.spent(log=lambda *a: None):.2f}")


def run():
    rem = [a for a in sys.argv if a.startswith("--remaining=")]
    if not rem:
        sys.exit("refused: give --remaining=<USD> as read on the OpenAI usage page")
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    _, est = estimate()
    if float(rem[0].split("=", 1)[1]) < est + MARGIN:
        sys.exit("refused: not enough budget left")
    V.track([CH.run_dir(V9H, MODEL, 0, EFFORT).parent])
    start = run_a.spent(log=lambda *a: None)
    print(f"sending the Stage C cell: {len(MODS)} modules x 3 runs (about USD {est:.2f}); spent before USD {start:.2f}", flush=True)
    for r in REPS:
        res = CH.run_many([(V9H, r)], MODS, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RUN_WORKERS", "4")))
        bad = [(x["module"], x["status"]) for x in res[(V9H, r)] if x.get("status") != "done"]
        print(f"r{r} done; not done: {bad or 'none'}; this run so far USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)
    print(f"spent this run USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)


def run_all():
    """Stage after the cell (user 2026-10-18: "analyze the failure patterns of v9h prompt on the 41 modules"): v9h on the
    34 modules outside the cell, runs RUN_ALL_REPS (default "0,1"); the cell modules already hold r0-r2. The cost is v9g's
    stored r0 cost of the same modules times the growth, per run. Refuses without --remaining=<USD>."""
    rem = [a for a in sys.argv if a.startswith("--remaining=")]
    if not rem:
        sys.exit("refused: give --remaining=<USD>")
    g, _ = groups()
    others = [m for m in list(g["tuning"]) + list(g["held-out"]) if m not in MODS]
    reps = [int(x) for x in os.environ.get("RUN_ALL_REPS", "0,1").split(",")]
    base = sum(run_a.usd(json.loads((CH.run_dir(V9G, MODEL, 0, EFFORT) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))["usage"])
               for m in others for ph in (1, 2))
    est = base * growth() * len(reps)
    print(f"v9h on {len(others)} modules x {len(reps)} runs = {2 * len(others) * len(reps)} calls; v9g r0 cost of the modules USD {base:.2f} x growth x runs = USD {est:.2f}; needs {est + MARGIN:.2f}", flush=True)
    if "--send" not in sys.argv:
        return
    if float(rem[0].split("=", 1)[1]) < est + MARGIN:
        sys.exit("refused: not enough budget left")
    V.track([CH.run_dir(V9H, MODEL, 0, EFFORT).parent])
    start = run_a.spent(log=lambda *a: None)
    for r in reps:
        res = CH.run_many([(V9H, r)], others, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RUN_WORKERS", "4")))
        bad = [(x["module"], x["status"]) for x in res[(V9H, r)] if x.get("status") != "done"]
        print(f"r{r} done; not done: {bad or 'none'}; so far USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)
    print(f"spent USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)


def rerun_missing():
    """re-send module-runs of v9h that have no assets file (connection errors), few workers, stored replies reused."""
    g, _ = groups()
    allm = list(g["tuning"]) + list(g["held-out"])
    reps = [int(x) for x in os.environ.get("RERUN_REPS", "0,1,2").split(",")]
    jobs = {r: [m for m in allm if (r in REPS and m in MODS or r in [int(x) for x in os.environ.get("RUN_ALL_REPS", "0,1").split(",")] and m not in MODS)
                and V.assets(V9H, m, r) is None] for r in reps}
    print({r: [m[8:] for m in v] for r, v in jobs.items()}, flush=True)
    start = run_a.spent(log=lambda *a: None)
    for r in reps:
        if jobs[r]:
            res = CH.run_many([(V9H, r)], jobs[r], lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RERUN_WORKERS", "3")))
            print(f"r{r} not done:", [(x["module"], x["status"]) for x in res[(V9H, r)] if x.get("status") != "done"] or "none", flush=True)
    print(f"spent this re-send USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "measure":
        if not selftest(log=print):
            sys.exit("self-test FAIL; nothing reported")
        print(json.dumps(measure(), indent=1, ensure_ascii=False)[:9000])
    elif cmd == "run":
        run()
    elif cmd == "run-all":
        run_all()
    elif cmd == "rerun-missing":
        rerun_missing()
    else:
        {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview}[cmd]()
