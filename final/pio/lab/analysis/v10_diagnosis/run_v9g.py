"""Does recall on the 26 held-out modules rise when the v9k rules that passed alone go into v9f? (user 2026-10-17: "include
it in the v9f to check for recall increase"). Candidate: two_phase_v9g (make_v9g.py). Plan: PLAN_V9K.md.
NOT sent without the user's go-ahead on the option and its cost (the study budget is nearly spent).

Options (luna, high, Phase 1 then Phase 2 per module, chain.run_many, at most 8 requests at a time):
  A  the 26 held-out modules, r0-r2 (156 calls)   B  all 41 modules, r0 (82 calls)   H  the 26 held-out modules, r0 (52)
Readings (set 2026-10-17 before any call; exact scorer; v9 r0-r2 and v9f r0-r2 are the comparisons):
  R1 held-out 26 recall, per run and pooled. v9: 134 / 136 / 130 of 187; v9f: 138 / 130 / 128.
     Rise shown: every v9g run above the best run of both baselines (> 138). Drop shown: every v9g run below the worst
     run of both (< 128). Otherwise: no change shown. One run (option H) can at most show "consistent with a rise".
  R2 held-out 26 precision, per run and pooled; v9: 0.409 / 0.416 / 0.380; v9f: 0.387 / 0.447 / 0.421. Read beside R1.
  R3 the held-out reference entries the rules aim at (v9g_targets.json: 43 distinct entries), found per run, against
     v9's and v9f's per-run counts; each miss with where_lost's stage.
  R4 (option B) tuning 15, tuning_v2 and heldout_v2 recall and precision against v9 r0-r2 and v9f r0.
  R5 watch: elements the rules are expected to list although the reference does not (WATCH), listed per run against
     v9 and v9f; and the number of record-port fields listed per run (every one a false positive), against v9f.
Self-test (7 checks): the readers on v9 r0-r2 as the candidate give R1 = 134 / 136 / 130 and "no change shown"; the
43 targets are held-out reference entries; the watch names are non-reference closed-set names.

  python -B run_v9g.py selftest
  python -B run_v9g.py preview
  <conda python> run_v9g.py run A|B|H --remaining=<USD>
  python -B run_v9g.py measure A|B|H          (writes read_v9g.json)
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
V9G, V9F, V9 = "two_phase_v9g", "two_phase_v9f", "two_phase_v9"
OPTIONS = {"A": ("held-out", (0, 1, 2)), "B": ("all", (0,)), "H": ("held-out", (0,))}
MARGIN = 0.32
WATCH = ["cpu_frontend:ctrl_i", "cpu_cp_muldiv:ctrl_i", "pwm:re", "cpu_counters:cfg_re", "cpu_counters:cfg_acc", "cpu_counters:cnt_acc",
         "xbus:xbus_tag_o", "xbus:xbus_sel_o", "cpu_lsu:mar_o", "cpu_cp_bitmanip:shifter.run", "cpu_cp_bitmanip:clmul.run",
         "cpu_frontend:ibus_req_o", "cpu_lsu:dbus_req_o", "cpu_icc:csr_rdata_o", "cpu_cp_cfu:rtype_i", "cpu_cp_cfu:funct3_i"]


def groups():
    return V.R10.CV.groups_and_ref()


def mods_of(opt):
    g, _ = groups()
    return list(g["held-out"]) if OPTIONS[opt][0] == "held-out" else list(g["held-out"]) + list(g["tuning"])


def targets():
    return sorted({c for _, c in json.loads((HERE / "v9g_targets.json").read_text(encoding="utf-8"))})


def sc(v, r, m):
    return C.score_dir(CH.run_dir(v, MODEL, r, EFFORT), m)


def recall_rows(v, reps, ms):
    _, refl = groups()
    fd = sum(len(refl[m]) for m in ms)
    rows = []
    for r in reps:
        s = [sc(v, r, m) for m in ms]
        if all(x is None for x in s):
            continue
        miss = [m[8:] for m, x in zip(ms, s) if x is None]
        tp, ln = sum(x[1] for x in s if x), sum(x[0] for x in s if x)
        rows.append({"run": r, "correct": tp, "listed": ln, "findable": fd, "recall": round(tp / fd, 3), "precision": round(tp / ln, 3) if ln else None, "missing": miss})
    return rows


def r1_verdict(cand, bases):
    c = [x["correct"] for x in cand]
    b = [x["correct"] for rows in bases for x in rows]
    return "rise shown" if min(c) > max(b) else "drop shown" if max(c) < min(b) else "no change shown"


def found(v, r, c):
    m, e = "neorv32_" + c.split(":")[0], c.split(":", 1)[1]
    ls = HR.names(v, r, m)
    return None if ls is None else bool(HR.found_occ(V.cvref()[m], ls).get((e, 1)))


def record_fields_listed(v, r, ms):
    n = 0
    for m in ms:
        ls = HR.names(v, r, m)
        if ls is None:
            continue
        recs = {x for (_, x), f in CH.closed_names(m).items() if "port" in f and f.get("record type") and "field" not in f}
        n += sum(1 for x in ls if "." in x and x.split(".")[0] in recs)
    return n


def readers(v, reps):
    g, _ = groups()
    ho = list(g["held-out"])
    out = {}
    cand = recall_rows(v, reps, ho)
    b9, b9f = recall_rows(V9, (0, 1, 2), ho), recall_rows(V9F, (0, 1, 2), ho)
    out["R1/R2 held-out 26"] = {"candidate": cand, "v9 r0-r2": b9, "v9f r0-r2": b9f, "R1": r1_verdict(cand, [b9, b9f]),
                                "pooled candidate": f"{sum(x['correct'] for x in cand)}/{sum(x['findable'] for x in cand)} recall, {sum(x['correct'] for x in cand)}/{sum(x['listed'] for x in cand)} precision"}
    tg = targets()
    out["R3 targets found per run (of %d)" % len(tg)] = {
        "candidate": [sum(bool(found(v, r, c)) for c in tg) for r in reps],
        "v9": [sum(bool(found(V9, r, c)) for c in tg) for r in (0, 1, 2)],
        "v9f": [sum(bool(found(V9F, r, c)) for c in tg) for r in (0, 1, 2)]}
    out["R5 watch listed per run (of %d)" % len(WATCH)] = {
        name: [sum(bool(c.split(":", 1)[1] in (V.assets(vv, "neorv32_" + c.split(":")[0], r) or set())) for c in WATCH) for r in rr]
        for name, vv, rr in (("candidate", v, reps), ("v9", V9, (0, 1, 2)), ("v9f", V9F, (0, 1, 2)))}
    out["R5 record-port fields listed per run (held-out 26)"] = {name: [record_fields_listed(vv, r, ho) for r in rr]
                                                                for name, vv, rr in (("candidate", v, reps), ("v9", V9, (0, 1, 2)), ("v9f", V9F, (0, 1, 2)))}
    return out


def measure(opt, v=V9G, path=None):
    reps = OPTIONS[opt][1]
    out = {"option": opt, "candidate": v, "readings": readers(v, reps)}
    lost = {}
    for r in reps:
        for c in targets():
            m, e = "neorv32_" + c.split(":")[0], c.split(":", 1)[1]
            ls = HR.names(v, r, m)
            if ls is not None and not HR.found_occ(V.cvref()[m], ls).get((e, 1)):
                lost.setdefault(c, []).append(f"r{r}: {TR.where_lost(v, r, m, e, ls)[0]}")
    out["R3 where the targets are lost"] = lost
    if OPTIONS[opt][0] == "all":
        g, _ = groups()
        sp = V.splits()
        out["R4"] = {name: {"candidate": recall_rows(v, reps, ms), "v9 r0-r2": recall_rows(V9, (0, 1, 2), ms), "v9f r0": recall_rows(V9F, (0,), ms)}
                     for name, ms in (("tuning 15", list(g["tuning"])), ("tuning_v2", sp["tuning_v2"]), ("heldout_v2", sp["heldout_v2"]))}
    p = path or (HERE / "read_v9g.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    return out


def selftest(log=print):
    c = {}
    c["prompt folder exists"] = (LAB / "prompts" / V9G / "phase1.md").exists()
    c["check_lab_prompt passes v9g"] = c["prompt folder exists"] and V.CK.check(V9G, log=lambda *a: None)
    z = readers(V9, (0, 1, 2))
    c["zero point: v9 r0-r2 as the candidate gives 134 / 136 / 130 and 'no change shown'"] = (
        [x["correct"] for x in z["R1/R2 held-out 26"]["candidate"]] == [134, 136, 130] and z["R1/R2 held-out 26"]["R1"] == "no change shown")
    c["v9f baseline reads 138 / 130 / 128"] = [x["correct"] for x in z["R1/R2 held-out 26"]["v9f r0-r2"]] == [138, 130, 128]
    _, refl = groups()
    c["43 targets, each a held-out reference entry"] = len(targets()) == 43 and all(t.split(":", 1)[1] in refl["neorv32_" + t.split(":")[0]] for t in targets())
    c["watch names are non-reference and in their closed sets"] = all(
        x.split(":", 1)[1] not in refl["neorv32_" + x.split(":")[0]] and x.split(":", 1)[1] in {n for (_, n) in CH.closed_names("neorv32_" + x.split(":")[0])} for x in WATCH)
    try:
        d = measure("A", V9, os.path.join(os.environ.get("TEMP", "."), "dry_v9g_on_v9.json"))
        c["dry run of measure() on v9"] = "R3 where the targets are lost" in d
    except Exception as e:  # noqa: BLE001
        log(f"dry run failed: {e}")
        c["dry run of measure() on v9"] = False
    bad = [k for k, v in c.items() if not v]
    log(f"run_v9g self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def growth():
    """prompt-size ratio v9g / v9f (system prompts, both phases, mean) as the cost multiplier."""
    s = [len(V.CK.system(V9G, ph)) / len(V.CK.system(V9F, ph)) for ph in (1, 2)]
    return sum(s) / len(s)


def estimate(opt):
    ms, reps = mods_of(opt), OPTIONS[opt][1]
    s = 0.0
    for r in reps:
        for m in ms:
            for ph in (1, 2):
                f = CH.run_dir(V9F, MODEL, r if OPTIONS[opt][0] == "held-out" else 0, EFFORT) / f"phase{ph}" / f"{m}.json"
                s += run_a.usd(json.loads(f.read_text(encoding="utf-8"))["usage"])
    return s, s * growth()


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    print(f"prompt growth v9g / v9f (system text): x{growth():.3f}")
    for opt in OPTIONS:
        base, est = estimate(opt)
        n = 2 * len(mods_of(opt)) * len(OPTIONS[opt][1])
        print(f"option {opt}: {n} calls; v9f's stored cost of the same cells USD {base:.2f}; estimate USD {est:.2f}; needs USD {est + MARGIN:.2f} left")
    print(f"spent so far (counter) USD {run_a.spent(log=lambda *a: None):.2f}")


def run(opt):
    rem = [a for a in sys.argv if a.startswith("--remaining=")]
    if not rem:
        sys.exit("refused: give --remaining=<USD> as read on the OpenAI usage page")
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    _, est = estimate(opt)
    if float(rem[0].split("=", 1)[1]) < est + MARGIN:
        sys.exit("refused: not enough budget left")
    ms, reps = mods_of(opt), OPTIONS[opt][1]
    V.track([CH.run_dir(V9G, MODEL, 0, EFFORT).parent])
    start = run_a.spent(log=lambda *a: None)
    print(f"sending option {opt}: {len(ms)} modules x {len(reps)} runs (about USD {est:.2f}); spent before USD {start:.2f}")
    for r in reps:
        res = CH.run_many([(V9G, r)], ms, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RUN_WORKERS", "6")))
        bad = [(x["module"], x["status"]) for x in res[(V9G, r)] if x.get("status") != "done"]
        print(f"r{r} done; not done: {bad or 'none'}; this run so far USD {run_a.spent(log=lambda *a: None) - start:.3f}")
        if run_a.spent(log=lambda *a: None) - start > est * 1.3:
            print("stopped: spend passed 1.3 x the estimate")
            break
    print(f"spent this run USD {run_a.spent(log=lambda *a: None) - start:.3f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "measure":
        if not selftest(log=print):
            sys.exit("self-test FAIL; nothing reported")
        print(json.dumps(measure(sys.argv[2]), indent=1, ensure_ascii=False)[:12000])
    elif cmd == "run":
        run(sys.argv[2])
    else:
        {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview}[cmd]()
