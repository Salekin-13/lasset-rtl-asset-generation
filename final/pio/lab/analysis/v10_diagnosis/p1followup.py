"""Phase 1 follow-up on the modules where full v10's Phase 1 breaks four rules (p1_full_breaks.json; user 2026-10-16: "Run
the follow-up: Operation selectors, Build-time values, Access command fields and Forwarded transactions, each alone vs in
its cluster, on the modules where full v10 Phase 1 breaks them").

Cells reuse p1clusters.py's names, so stored replies are reused: alone = P1alone__<rule>__<cluster> (core + the rule),
cluster = P1cluster__<cluster> (core + every rule of the cluster). Access command fields alone on cpu_regfile and cpu_alu
reads the stored cell P123__P1_S1 (the same Phase 1 prompt: core + that rule; system sha checked).
Measure and reading: p1clusters.py's (bar rule: share of its rule-alone signals Phase 1 does not NAME; FAILS WHERE THE
ISOLATED PASS when alone >= 0.8 and cluster <= alone - 0.25 with at least 2 more pairs broken). Full v10 r0-r1 alongside.

  <conda python> p1followup.py run
  python -B p1followup.py measure
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
import rule_breaks as RB  # noqa: E402
import run_a  # noqa: E402

TARGETS = [("P1-22", "K2", ["neorv32_cpu_control", "neorv32_cpu_lsu"]),
           ("P1-05", "K2", ["neorv32_cpu_icc", "neorv32_xbus"]),
           ("P1-03", "K3", ["neorv32_uart", "neorv32_sysinfo"]),
           ("P1-23", "K3", ["neorv32_cpu_regfile", "neorv32_cpu_alu"])]
REUSE = {("P1-23", "neorv32_cpu_regfile"): "P123__P1_S1", ("P1-23", "neorv32_cpu_alu"): "P123__P1_S1"}


def cells():
    pl = json.loads(PC.PLAN.read_text(encoding="utf-8"))
    T = PC.titles()
    jobs = []
    for rid, k, mods in TARGETS:
        clus = sorted([T[r] for r in pl[k]["rules"]], key=P.order().index)
        for m in mods:
            if (rid, m) not in REUSE:
                jobs.append((f"P1alone__{rid.replace('-', '')}__{k}", [T[rid]], m))
            jobs.append((f"P1cluster__{k}", clus, m))
    return jobs


def run():
    from concurrent.futures import ThreadPoolExecutor
    jobs = []
    for name, keep, m in cells():
        for rep in (0, 1):
            if not (L.cell_dir(name, rep) / "phase1" / f"{m}.json").exists():
                jobs.append((name, keep, m, rep))
    spent = run_a.spent(log=lambda *a: None)
    print(f"{len(jobs)} calls to send (about USD {len(jobs) * 0.03:.2f}); spent so far USD {spent:.2f}; cap 26")
    if spent + len(jobs) * 0.03 > 26:
        sys.exit("over the cap; nothing sent")
    # reused cell: same system prompt as the alone cell it stands for
    T = PC.titles()
    a = CH.sha12(CK.system(P.cell_version("P1alone__P123__K3", P.build_keep([T["P1-23"]])), 1))
    b = json.loads((L.cell_dir("P123__P1_S1", 0) / "phase1" / "neorv32_cpu_regfile.json").read_text(encoding="utf-8"))["system sha"]
    assert a == b, "reused cell has another system prompt"
    L.track_folders(sorted({j[0] for j in jobs}))
    stop = CH._new_run_flag()
    vers, calls = {}, {}
    for name, keep, m, rep in jobs:
        if name not in vers:
            vers[name] = P.cell_version(name, P.build_keep(keep))
        if (name, rep) not in calls:
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            calls[(name, rep)] = CH.openai(MODEL, EFFORT, out=out, poll=5)

    def one(j):
        threading.current_thread().lab_stop = stop
        name, keep, m, rep = j
        v, out = vers[name], L.cell_dir(name, rep)
        try:
            return CH._ask(calls[(name, rep)], CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                           lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                           adapt=CH.from_format_phase1).get("problems")
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"[:200]
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        res = list(pool.map(one, jobs))
    bad = [r for r in res if isinstance(r, str)]
    print(f"done {len(res) - len(bad)} of {len(res)}" + (f"; errors {bad[:3]}" if bad else ""))
    print("spent after USD", round(run_a.spent(log=lambda *a: None), 2))


def measure():
    groups, refl = RB.CV.groups_and_ref()
    mods41 = groups["tuning"] + groups["held-out"]
    dec = PC.decisions(mods41)
    T = PC.titles()
    out = {}
    for rid, k, mods in TARGETS:
        row = {}
        for tag in ("alone", "cluster", "full v10"):
            ok = tot = 0
            per = {}
            for m in mods:
                els = sorted(dec[rid].get(m, ()))
                name = (REUSE.get((rid, m)) or f"P1alone__{rid.replace('-', '')}__{k}") if tag == "alone" else \
                       f"P1cluster__{k}" if tag == "cluster" else None
                mo = mt = 0
                for rep in (0, 1):
                    f = (CH.run_dir(V10, MODEL, rep, EFFORT) if name is None else L.cell_dir(name, rep)) / "phase1" / f"{m}.json"
                    if not f.exists():                       # D36: a reply cut at the output limit is left out
                        per.setdefault("_missing", []).append(f"{m[8:]} r{rep}")
                        continue
                    rec = json.loads(f.read_text(encoding="utf-8"))
                    a, b, _ = PC.score(rec, m, els, False)
                    mo, mt = mo + a, mt + b
                per[m[8:]] = [mo, mt]
                ok, tot = ok + mo, tot + mt
            row[tag] = {"followed": ok, "pairs": tot, "share": round(ok / tot, 3) if tot else None, "per module": per}
        al, cu = row["alone"], row["cluster"]
        row["cluster fails where alone passes"] = bool(al["share"] is not None and al["share"] >= 0.8 and cu["share"] <= al["share"] - 0.25
                                                       and al["followed"] - cu["followed"] >= 2)
        out[rid] = row
        print(f"{rid} {T[rid][:28]:28s} ({k}) alone {al['followed']}/{al['pairs']} {al['per module']} | cluster {cu['followed']}/{cu['pairs']} "
              f"{cu['per module']} | full v10 {row['full v10']['followed']}/{row['full v10']['pairs']} {row['full v10']['per module']}"
              + ("  <-- FAILS in the cluster" if row["cluster fails where alone passes"] else ""))
    (HERE / "p1followup.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"run": run, "measure": measure}[sys.argv[1]]()
