"""Pairwise cluster test for Access command fields (user 2026-10-16: "Run K3 paired with each other cluster (K1, K2, K4,
K5, K6, Serial shift registers) on cpu_regfile and cpu_alu, 2 repeats, with the readings you set, and report.").

Purpose (user): clustering and comparing with the isolated runs is a diagnostic for conflicts between rules; the final
Phase 1 prompt runs whole. Access command fields keeps 20/22 of its barred signals alone, 16/22 in its own cluster K3,
8/22 in full v10 (r0-r1, p1followup.json), so most of its loss comes from outside K3. Which other cluster causes it?

Cells (v10's own Phase 1 format; luna, high; r0-r1; cpu_regfile and cpu_alu): P1pair__K3_<X> = v10 phase1.md with only
the rule blocks of K3 and of cluster X (p1_clusters.json; X = K1, K2, K4, K5, K6, or S = Serial shift registers), in v10's
order (p1probe.build_keep). Baseline: the stored cell P1cluster__K3 (the same construction with K3 alone).
Measure (as in D39-D41): the (signal, repeat) pairs in which Phase 1 names one of Access command fields' consistently
barred signals (ladder.bars "P1-23 P2"; p1probe.p1_named == "named"), 22 pairs per cell.
Readings (set 2026-10-16 before the run; K3 alone names 6/22): per partner X: 12/22 or more named -> X conflicts with
  K3; 7/22 or fewer -> no effect; 8-11 -> no answer. If no partner reaches 12/22, the full-prompt loss is load from many
  rules rather than one conflicting cluster. Resolution: cpu_regfile replies break all or none, so a cell is about 4
  replies.
Self-test (nothing is sent if it fails): each pair cell holds every core line, the K3 blocks and the partner's blocks
  verbatim and no other rule; its text minus the partner's blocks equals the stored P1cluster__K3 prompt; the stored K3
  replies carry that prompt's system sha.

  python -B p1pairs.py selftest
  <conda python> p1pairs.py run       (at most 24 new calls)
  python -B p1pairs.py measure        (writes p1pairs.json)
"""
import json
import os
import sys
import threading

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import ladder as L  # noqa: E402
import p1probe as P  # noqa: E402
import p1clusters as PC  # noqa: E402
import run_a  # noqa: E402

T = "P1-23 P2"
MODS = ["neorv32_cpu_regfile", "neorv32_cpu_alu"]
BASE = "P1cluster__K3"


def clusters():
    tl = PC.titles()
    cl = json.loads((HERE / "p1_clusters.json").read_text(encoding="utf-8"))
    out = {f"K{i}": [tl[r] for r in c["rules"] if r in tl] for i, c in enumerate(cl["clusters"], 1)}
    out["S"] = ["Serial shift registers"]
    return out


def cells():
    K = clusters()
    return {f"P1pair__K3_{x}": (K["K3"], K[x]) for x in ("K1", "K2", "K4", "K5", "K6", "S")}


def selftest(log=print):
    lines = P.V10D.joinpath("phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF).split(P.LF)
    end = lines.index("OUTPUT")
    core = P.build(None).split(P.LF)
    K = clusters()
    base_text = P.build_keep(K["K3"])
    stored = (P.LAB / "prompts" / "diag_v10" / BASE / "phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF)
    sha = CH.sha12(CK.system(f"diag_v10/{BASE}", 1))
    stored_sha = {json.loads(f.read_text(encoding="utf-8"))["system sha"] for r in (0, 1) for m in MODS
                  for f in [L.cell_dir(BASE, r) / "phase1" / f"{m}.json"] if f.exists()}
    checks = {"stored K3 prompt = build_keep(K3)": stored == base_text,
              "stored K3 replies on both modules carry its system sha": stored_sha == {sha},
              "partition: the 7 calls cover the 27 rules once": sorted(t for v in K.values() for t in v) == sorted(P.order())}
    for name, (k3, x) in cells().items():
        tl = P.build_keep(k3 + x).split(P.LF)
        active = {P.base_title(t) for _, _, t in P.blocks(tl, tl.index("OUTPUT"))}
        want = [l for a, b, t in P.blocks(lines, end) if P.base_title(t) in set(k3 + x) for l in lines[a:b]]
        minus_x = [l for i, l in enumerate(tl) if not any(a <= i < b for a, b, t in P.blocks(tl, tl.index("OUTPUT"))
                                                         if P.base_title(t) in set(x))]
        checks[f"{name}: active rules = K3 + partner"] = active == set(k3 + x)
        checks[f"{name}: blocks verbatim, in v10 order"] = [l for l in tl if l in set(want)] == want
        checks[f"{name}: every core line kept"] = [l for l in tl if l in set(core)] == core
        checks[f"{name}: minus the partner = the K3 cell"] = P.LF.join(minus_x) == base_text
    bad = [k for k, v in checks.items() if not v]
    for name, (k3, x) in cells().items():
        log(f"{name}: partner {x} ({len(P.build_keep(k3 + x).split())} words; K3 cell {len(base_text.split())})")
    log(f"p1pairs self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def run():
    from concurrent.futures import ThreadPoolExecutor
    if not selftest():
        sys.exit("self-test FAIL; nothing sent")
    jobs, stop = [], CH._new_run_flag()
    for name, (k3, x) in cells().items():
        v = P.cell_version(name, P.build_keep(k3 + x))
        L.track_folders([name])
        for rep in (0, 1):
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            call = CH.openai(MODEL, EFFORT, out=out, poll=5)
            jobs += [(v, m, out, call) for m in MODS if not (out / "phase1" / f"{m}.json").exists()]
    spent = run_a.spent(log=lambda *a: None)
    print(f"{len(jobs)} calls to send (about USD {len(jobs) * 0.022:.2f}); spent so far USD {spent:.2f}")
    if len(jobs) > 24:
        sys.exit("more than the 24 approved calls; nothing sent")

    def one(j):
        threading.current_thread().lab_stop = stop
        v, m, out, call = j
        return CH._ask(call, CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                       lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                       adapt=CH.from_format_phase1).get("problems")
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        res = list(pool.map(one, jobs))
    print("done", len(res), "; problems", res, "; spent after USD", round(run_a.spent(log=lambda *a: None), 2))


def measure():
    B = L.bars(T, MODS)
    out = {}
    names = [("P123__P1_S1", "rule alone"), (BASE, "K3 alone")] + [(n, "K3 + " + n.split("_")[-1]) for n in cells()] + \
            [("P123__P1_pre17", "17 rules (r0-r1)"), (None, "full v10 (r0-r1)")]
    for name, label in names:
        per, tot, words = {}, 0, None
        for m in MODS:
            for rep in (0, 1):
                d = CH.run_dir(V10, MODEL, rep, EFFORT) if name is None else L.cell_dir(name, rep)
                rec = json.loads((d / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
                k = sum(P.p1_named(rec, m, e) == "named" for e in B[m])
                per[f"{m[12:]} r{rep}"] = f"{k}/{len(B[m])}"
                tot += k
        if name:
            words = len((P.LAB / "prompts" / "diag_v10" / name / "phase1.md").read_text(encoding="utf-8").split())
        reading = None
        if name and name.startswith("P1pair__"):
            reading = "conflicts with K3" if tot >= 12 else "no effect" if tot <= 7 else "no answer"
        out[label] = {"cell": name, "words": words, "named": tot, "pairs": 22, "per reply": per, "reading": reading}
        print(f"{label:18s} {str(words):>5s} words  named {tot:2d}/22  {per}" + (f"  -> {reading}" if reading else ""))
    hits = [k for k, v in out.items() if v["reading"] == "conflicts with K3"]
    out["overall"] = (f"conflicting partner(s): {hits}" if hits else
                      "no single partner reaches 12/22: the full-prompt loss is load from many rules, not one cluster")
    print("overall (set before the run):", out["overall"])
    (HERE / "p1pairs.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


SINGLE = {"P1pair__K3_CR": "Clocks and resets", "P1pair__K3_WV": "Working values", "P1pair__K3_PO": "Port options"}
NARROW_DOC = """Narrowing round (user 2026-10-16: "Run r2-r3 of K3 alone and K3+K6, and K3 plus each K6 rule alone (Clocks and
resets, Working values, Port options) at r0-r1, on cpu_regfile and cpu_alu. Set the readings before sending and report.")
Readings, set before sending (named pairs of Access command fields' barred signals):
  A. Confirmation, K3+K6 over r0-r3 (44 pairs; the 22-pair readings doubled): 24/44 or more -> the conflict is
     confirmed; 14/44 or fewer -> not confirmed; 15-23 -> no answer. Contrast condition: K3 alone over r0-r3 must stay at
     14/44 or fewer, else there is no contrast to confirm. Also reported: r2-r3 alone against the 22-pair readings.
  B. Which K6 rule (K3 + one K6 rule, r0-r1, 22 pairs): 12/22 or more -> that rule carries the conflict; 7/22 or fewer
     -> no effect; 8-11 -> no answer. If no single rule reaches 12/22 while K3+K6 does, the effect needs the rules
     together (or is noise).
Resolution: about 4 replies per 22 pairs; cpu_regfile replies break all or none."""


def narrow_selftest(log=print):
    K = clusters()
    ok = selftest(log=lambda *a: None)
    checks = {"pair self-test (27 checks)": ok}
    lines = P.V10D.joinpath("phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF).split(P.LF)
    end = lines.index("OUTPUT")
    base_text = P.build_keep(K["K3"])
    for name, rule in SINGLE.items():
        checks[f"{name}: {rule} is a K6 rule"] = rule in K["K6"]
        tl = P.build_keep(K["K3"] + [rule]).split(P.LF)
        active = {P.base_title(t) for _, _, t in P.blocks(tl, tl.index("OUTPUT"))}
        checks[f"{name}: active rules = K3 + {rule}"] = active == set(K["K3"] + [rule])
        minus = [l for i, l in enumerate(tl) if not any(a <= i < b for a, b, t in P.blocks(tl, tl.index("OUTPUT"))
                                                       if P.base_title(t) == rule)]
        checks[f"{name}: minus the rule = the K3 cell"] = P.LF.join(minus) == base_text
        blk = [l for a, b, t in P.blocks(lines, end) if P.base_title(t) == rule for l in lines[a:b]]
        checks[f"{name}: rule blocks verbatim"] = all(l in tl for l in blk)
    for name, text in ((BASE, base_text), ("P1pair__K3_K6", P.build_keep(K["K3"] + K["K6"]))):
        disk = (P.LAB / "prompts" / "diag_v10" / name / "phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF)
        sha = CH.sha12(CK.system(f"diag_v10/{name}", 1))
        stored = {json.loads((L.cell_dir(name, r) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["system sha"]
                  for r in (0, 1) for m in MODS}
        checks[f"{name}: prompt on disk = builder, stored r0-r1 sha = today's"] = disk == text and stored == {sha}
    bad = [k for k, v in checks.items() if not v]
    for name, rule in SINGLE.items():
        log(f"{name}: K3 + {rule} ({len(P.build_keep(K['K3'] + [rule]).split())} words)")
    log(f"narrow self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def narrow_run():
    from concurrent.futures import ThreadPoolExecutor
    if not narrow_selftest():
        sys.exit("self-test FAIL; nothing sent")
    K = clusters()
    plan = [(BASE, None, (2, 3)), ("P1pair__K3_K6", None, (2, 3))] + [(n, K["K3"] + [r], (0, 1)) for n, r in SINGLE.items()]
    jobs, stop = [], CH._new_run_flag()
    for name, keep, reps in plan:
        v = P.cell_version(name, P.build_keep(keep)) if keep else f"diag_v10/{name}"
        L.track_folders([name])
        for rep in reps:
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            call = CH.openai(MODEL, EFFORT, out=out, poll=5)
            jobs += [(v, m, out, call) for m in MODS if not (out / "phase1" / f"{m}.json").exists()]
    spent = run_a.spent(log=lambda *a: None)
    print(f"{len(jobs)} calls to send (about USD {len(jobs) * 0.02:.2f}); spent so far USD {spent:.2f}")
    if len(jobs) > 20:
        sys.exit("more than the 20 approved calls; nothing sent")

    def one(j):
        threading.current_thread().lab_stop = stop
        v, m, out, call = j
        return CH._ask(call, CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                       lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                       adapt=CH.from_format_phase1).get("problems")
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        res = list(pool.map(one, jobs))
    print("done", len(res), "; problems", res, "; spent after USD", round(run_a.spent(log=lambda *a: None), 2))


def narrow_measure():
    B = L.bars(T, MODS)

    def count(name, reps):
        per, tot = {}, 0
        for m in MODS:
            for rep in reps:
                rec = json.loads((L.cell_dir(name, rep) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
                k = sum(P.p1_named(rec, m, e) == "named" for e in B[m])
                per[f"{m[12:]} r{rep}"] = f"{k}/{len(B[m])}"
                tot += k
        return tot, per
    out = {}
    for name, label in ((BASE, "K3 alone"), ("P1pair__K3_K6", "K3 + K6")):
        t4, p4 = count(name, (0, 1, 2, 3))
        t2, _ = count(name, (2, 3))
        out[label] = {"named r0-r3": t4, "pairs": 44, "named r2-r3": t2, "per reply": p4}
        print(f"{label:22s} named {t4:2d}/44 (r2-r3 alone {t2}/22)  {p4}")
    k3, k6 = out["K3 alone"]["named r0-r3"], out["K3 + K6"]["named r0-r3"]
    out["A confirmation"] = ("no contrast: K3 alone above 14/44" if k3 > 14 else
                             "conflict confirmed (24/44 or more)" if k6 >= 24 else
                             "not confirmed (14/44 or fewer)" if k6 <= 14 else "no answer (15-23/44)")
    late = out["K3 + K6"]["named r2-r3"]
    out["A replication r2-r3 (22-pair readings)"] = "conflict" if late >= 12 else "no effect" if late <= 7 else "no answer"
    print("A (set before sending):", out["A confirmation"], "| r2-r3 alone:", out["A replication r2-r3 (22-pair readings)"])
    for name, rule in SINGLE.items():
        t, p = count(name, (0, 1))
        rd = "carries the conflict" if t >= 12 else "no effect" if t <= 7 else "no answer"
        words = len((P.LAB / "prompts" / "diag_v10" / name / "phase1.md").read_text(encoding="utf-8").split())
        out["K3 + " + rule] = {"named": t, "pairs": 22, "words": words, "per reply": p, "reading": rd}
        print(f"{'K3 + ' + rule:22s} {words:5d} words  named {t:2d}/22  {p}  -> {rd}")
    carriers = [r for r in SINGLE.values() if out["K3 + " + r]["reading"] == "carries the conflict"]
    out["B which rule"] = (f"carried by: {carriers}" if carriers else
                           "no single K6 rule reaches 12/22" + (" while K3+K6 does: the rules act together, or noise"
                                                                 if out["A confirmation"].startswith("conflict") else ""))
    print("B (set before sending):", out["B which rule"])
    (HERE / "p1pairs_narrow.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


PARTS = {  # cell -> the exact Port options words removed (v10 phase1.md line)
    "P1pair__K3_PO_noalthough": (141, ", although step 2 names each enable, step 3 splits by use and it gates an output port"),
    "P1pair__K3_PO_nocrit2": (140, "; (2) it is none of: an enable giving value to engine state, clearing a buffer or driving a "
                                   "clock-enable output; a rate setting; a lock; a limit compared with a count"),
}
PARTS_DOC = """Parts round (user 2026-10-16: "Test K3 + Port options in two variants on cpu_regfile and cpu_alu, 2 repeats: without
the 'although step 2 names each enable, step 3 splits by use and it gates an output port' clause, and without its
Criteria (2) list. Set the readings before sending and report.")
Diagnostic only: each variant changes what Port options says; only Access command fields is scored.
Readings, set before sending (22 pairs; K3 + Port options 15/22, K3 alone 6/22 at r0-r1):
  per variant: 7/22 or fewer named -> the removed words carry the conflict; 12/22 or more -> they do not (the
  conflict stays); 8-11 -> no answer.
  Both at 7 or fewer -> either part is enough to cause it (removing one removes it). Both at 12 or more -> the cause is
  elsewhere in Port options (its scope, the rest of its outcome, or its evidence line).
Resolution: about 4 replies per cell; cpu_regfile replies break all or none."""


def part_text(name):
    K = clusters()
    full = P.build_keep(K["K3"] + ["Port options"])
    ln, cut = PARTS[name]
    assert full.count(cut) == 1, name
    return full.replace(cut, "", 1)


def parts_selftest(log=print):
    K = clusters()
    v10 = P.V10D.joinpath("phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF).split(P.LF)
    full = P.build_keep(K["K3"] + ["Port options"]).split(P.LF)
    checks = {"narrow self-test": narrow_selftest(log=lambda *a: None)}
    for name, (ln, cut) in PARTS.items():
        checks[f"{name}: words on v10 line {ln}, once"] = v10[ln - 1].count(cut) == 1 and P.LF.join(v10).count(cut) == 1
        t = part_text(name).split(P.LF)
        diff = [i for i, (a, b) in enumerate(zip(full, t)) if a != b]
        checks[f"{name}: only that line differs"] = len(t) == len(full) and len(diff) == 1 and full[diff[0]] == v10[ln - 1]
        checks[f"{name}: the line minus the words"] = t[diff[0]] == v10[ln - 1].replace(cut, "", 1) if diff else False
        active = {P.base_title(x) for _, _, x in P.blocks(t, t.index("OUTPUT"))}
        checks[f"{name}: active rules = K3 + Port options"] = active == set(K["K3"] + ["Port options"])
        log(f"{name}: removes {len(cut.split())} words from line {ln}; cell {len(P.LF.join(t).split())} words "
            f"(K3 + Port options {len(P.LF.join(full).split())})")
    bad = [k for k, v in checks.items() if not v]
    log(f"parts self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def parts_run():
    from concurrent.futures import ThreadPoolExecutor
    if not parts_selftest():
        sys.exit("self-test FAIL; nothing sent")
    jobs, stop = [], CH._new_run_flag()
    for name in PARTS:
        v = P.cell_version(name, part_text(name))
        L.track_folders([name])
        for rep in (0, 1):
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            call = CH.openai(MODEL, EFFORT, out=out, poll=5)
            jobs += [(v, m, out, call) for m in MODS if not (out / "phase1" / f"{m}.json").exists()]
    spent = run_a.spent(log=lambda *a: None)
    print(f"{len(jobs)} calls to send (about USD {len(jobs) * 0.02:.2f}); spent so far USD {spent:.2f}")
    if len(jobs) > 8:
        sys.exit("more than the 8 approved calls; nothing sent")

    def one(j):
        threading.current_thread().lab_stop = stop
        v, m, out, call = j
        return CH._ask(call, CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                       lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                       adapt=CH.from_format_phase1).get("problems")
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        res = list(pool.map(one, jobs))
    print("done", len(res), "; problems", res, "; spent after USD", round(run_a.spent(log=lambda *a: None), 2))


def parts_measure():
    B = L.bars(T, MODS)
    out = {}
    for name, label in ((BASE, "K3 alone"), ("P1pair__K3_PO", "K3 + Port options"),
                        ("P1pair__K3_PO_noalthough", "PO without 'although...'"), ("P1pair__K3_PO_nocrit2", "PO without Criteria (2)")):
        per, tot = {}, 0
        for m in MODS:
            for rep in (0, 1):
                rec = json.loads((L.cell_dir(name, rep) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
                k = sum(P.p1_named(rec, m, e) == "named" for e in B[m])
                per[f"{m[12:]} r{rep}"] = f"{k}/{len(B[m])}"
                tot += k
        rd = None
        if name in PARTS:
            rd = "the removed words carry it" if tot <= 7 else "they do not carry it" if tot >= 12 else "no answer"
        out[label] = {"cell": name, "named": tot, "pairs": 22, "per reply": per, "reading": rd}
        print(f"{label:26s} named {tot:2d}/22  {per}" + (f"  -> {rd}" if rd else ""))
    a, b = out["PO without 'although...'"]["named"], out["PO without Criteria (2)"]["named"]
    out["overall"] = ("either part is enough to cause it" if a <= 7 and b <= 7 else
                      "the cause is elsewhere in Port options" if a >= 12 and b >= 12 else
                      "the 'although' clause" if a <= 7 else "Criteria (2)" if b <= 7 else "no single part identified")
    print("overall (set before sending):", out["overall"])
    (HERE / "p1pairs_parts.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "run": run, "measure": measure,
     "nselftest": lambda: sys.exit(0 if narrow_selftest() else 1), "nrun": narrow_run, "nmeasure": narrow_measure,
     "pselftest": lambda: sys.exit(0 if parts_selftest() else 1), "prun": parts_run, "pmeasure": parts_measure}[sys.argv[1]]()
