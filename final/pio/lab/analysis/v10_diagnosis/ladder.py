"""Step D of PLAN.md: the staged test. One cell = one Phase 2 prompt (stages.build_p2 with a rule set) asked on luna for
the target's test modules, with luna's stored v10 Phase 1 reply of run rk held fixed as input (repeat k). The full-v10
cell ("full") is v10's own stored Phase 2 reply and costs nothing.

Cells are kept in cells.json: {name: {"target", "stage", "keep", "last", "add_after", "modules", "reps", "why"}}.
Runs: runs/diag_v10/<cell>/gpt-5.6-luna__high/r<k>/phase2/<module>.json (chain._ask records) and assets/<module>.json.

Measure (PLAN.md): for the target wording, its consistent-bar elements in the cell's modules (rule_breaks.down over the
two rule-alone repeats); compliance = share of (element, repeat) pairs where the element is NOT listed primary. Each
pair's state is also kept: primary / secondary / not reported / absent, with the reply's justification text (for the
cause coding B, D, E).

Budget: a cell is sent only if the study's spend so far (run_a.spent, which reads the cell folders too) plus the cell's
estimate (calls x USD 0.030, v9's mean Phase 2 call) stays within CAP (USD 18 = keep USD 32 of 50; user 2026-10-16).

  python ladder.py selftest
  <conda python> ladder.py run <cell> [<cell> ...]
  python ladder.py measure <cell> [...]
"""
import json
import os
import sys
import threading
from pathlib import Path

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import labkit as K  # noqa: E402
import stages as S  # noqa: E402

CAP = 21.5
PER_CALL = 0.030
CELLS = HERE / "cells.json"
EXTRA = HERE / "spent_extra_folders.json"
_bars_cache = {}


def cells():
    return json.loads(CELLS.read_text(encoding="utf-8")) if CELLS.exists() else {}


def save_cell(name, spec):
    c = cells()
    if name in c and c[name] != spec:
        raise RuntimeError(f"cell {name} exists with another spec")
    c[name] = spec
    CELLS.write_text(json.dumps(c, indent=1, ensure_ascii=False), encoding="utf-8")


def version_of(name):
    return f"diag_v10/{name}"


def cell_dir(name, rep):
    return LAB / "runs" / "diag_v10" / name / f"{MODEL}__{EFFORT}" / f"r{rep}"


def build(name, spec):
    """Write the cell's prompt folder (idempotent: an existing folder must hold the same phase2.md)."""
    text = spec["p2_text"] if spec.get("p2_text") else S.build_p2(spec["keep"], last=spec.get("last"), add_after=spec.get("add_after"))
    d = LAB / "prompts" / "diag_v10" / name
    if (d / "phase2.md").exists():
        old = (d / "phase2.md").read_text(encoding="utf-8").replace("\r\n", "\n")
        if old != text:
            raise RuntimeError(f"{d} holds another phase2.md")
        return version_of(name)
    readme = (f"# {name}\n\nStaged-test cell (analysis/v10_diagnosis/ladder.py). Target {spec['target']}, stage "
              f"{spec['stage']}. Phase 2 rules kept: {len(spec['keep'])}; moved to the end: {spec.get('last')}; extra text: "
              f"{'yes' if spec.get('add_after') else 'no'}. Why: {spec.get('why', '')}\n")
    v = S.write_prompt(name, text, readme)
    if not CK.check(v, log=lambda *a: None):
        raise RuntimeError(f"{v}: the project prompt check fails")
    return v


def p1_record(m, rep, p1_from=None):
    """v10's stored Phase 1 reply, or (spec "p1_from": a cell name) that cell's Phase 1 reply (an isolated chain)."""
    d = cell_dir(p1_from, rep) if p1_from else CH.run_dir(V10, MODEL, rep, EFFORT)
    return json.loads((d / "phase1" / f"{m}.json").read_text(encoding="utf-8"))


def ask(call, version, m, rep, out, p1_from=None):
    r1 = p1_record(m, rep, p1_from)
    concepts = CH.phase1_concepts(r1.get("reply"))
    ids = [c.get("id") for c in concepts]
    meta = {"module": m, "prompt version": version, "input version": CH.INPUT_VERSION, "phase": 2,
            "phase 1 from": f"{p1_from or V10} r{rep}"}
    r2 = CH._ask(call, CK.system(version, 2), CH.user_message(version, 2, m, CH.concepts_as_written(r1, V10)),
                 out / "phase2" / f"{m}.json", lambda o: CH.check_phase2(m, o, concepts), meta,
                 adapt=lambda o, t: CH.from_format_phase2(o, t, ids))
    if CH.stopped(r2, 2):
        return "phase 2 schema failure"
    a = CH.to_assets(m, r2["reply"], concepts)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    (out / "assets" / f"{m}.json").write_text(json.dumps(a, indent=1, ensure_ascii=False), encoding="utf-8")
    return "done"


def to_send(names):
    n = 0
    for name in names:
        spec = cells()[name]
        for rep in spec["reps"]:
            for m in spec["modules"]:
                n += not (cell_dir(name, rep) / "phase2" / f"{m}.json").exists()
    return n


def track_folders(names):
    ex = json.loads(EXTRA.read_text(encoding="utf-8")) if EXTRA.exists() else []
    for name in names:
        p = str(LAB / "runs" / "diag_v10" / name / f"{MODEL}__{EFFORT}")
        if p not in ex:
            ex.append(p)
    EXTRA.write_text(json.dumps(ex, indent=1), encoding="utf-8")


def run(names, make_call=None, log=print):
    import run_a
    from concurrent.futures import ThreadPoolExecutor, wait
    names = [n for n in names if n != "full"]
    track_folders(names)
    n = to_send(names)
    spent = run_a.spent(log=lambda *a: None)
    log(f"cells {names}: {n} calls to send, estimate USD {n * PER_CALL:.2f}; spent so far USD {spent:.2f}; cap {CAP}")
    if spent + n * PER_CALL > CAP:
        raise SystemExit(f"over the cap: USD {spent:.2f} + {n * PER_CALL:.2f} > {CAP}; nothing sent")
    make_call = make_call or (lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5))
    stop = CH._new_run_flag()
    jobs, calls = [], {}
    for name in names:
        spec = cells()[name]
        v = build(name, spec)
        for rep in spec["reps"]:
            out = cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            calls[(name, rep)] = make_call(out)
            for m in spec["modules"]:
                jobs.append((name, v, m, rep, out, spec.get("p1_from")))

    def one(j):
        threading.current_thread().lab_stop = stop
        try:
            return ask(calls[(j[0], j[3])], j[1], j[2], j[3], j[4], j[5])
        except Exception as e:  # noqa: BLE001
            return f"error: {type(e).__name__}: {e}"[:300]
    pool = ThreadPoolExecutor(max_workers=max(1, len(jobs)))
    futs = {}
    try:
        for j in jobs:
            futs[j] = pool.submit(one, j)
        pending = set(futs.values())
        while pending:
            _, pending = wait(pending, timeout=1)
    except BaseException:
        CH._stop_pool(stop, pool, list(futs.values()), log)
        raise
    pool.shutdown(wait=True)
    res = {(j[0], j[2], j[3]): f.result() for j, f in futs.items()}
    bad = {k: v for k, v in res.items() if v != "done"}
    log(f"done {len(res) - len(bad)} of {len(res)}" + (f"; problems: {bad}" if bad else ""))
    log(f"spent after: USD {run_a.spent(log=lambda *a: None):.2f}")
    return res


def bars(target, modules):
    """{module: consistent-bar elements} of the target wording ('P1-16 P2')."""
    key = (target, tuple(modules))
    if key in _bars_cache:
        return _bars_cache[key]
    import rule_breaks as RB
    rid, ph = target.split()
    ISO.use(RB.source(rid, ph))
    out = {}
    for m in modules:
        b = []
        for rep in (0, 1):
            rec = json.loads((ISO.run_root(rep=rep) / ph / rid / f"{m}.json").read_text(encoding="utf-8"))
            b.append({x.get("element") for x in (rec["reply"] or {}).get("barred") or [] if isinstance(x, dict)})
        out[m] = sorted(e for (_, e) in CH.closed_names(m) if RB.down(e, b[0]) and RB.down(e, b[1]))
    ISO.use("v9")
    _bars_cache[key] = out
    return out


def states(rec, m, e, assets):
    """primary / secondary / not reported / absent for element e in one Phase 2 record, with the reply's texts."""
    rep = rec.get("reply") or {}
    if e in {x["Asset RTL"] for x in assets["Assets"]}:
        st = "primary"
    else:
        st = None
    txt = []
    for a in rep.get("structural assets") or []:
        if isinstance(a, dict) and (a.get("element") == e or e in CH.as_list(a.get("same role"))):
            txt.append(f"[{a.get('label')} {a.get('concept id')}] {a.get('justification') or ''} | {a.get('functionality') or ''}")
            st = st or ("secondary" if a.get("label") != "primary" else "primary")
    for x in rep.get("not reported") or []:
        if isinstance(x, dict) and x.get("element") == e:
            txt.append(f"[not reported {x.get('concept id')}] {x.get('reason') or ''}")
            st = st or "not reported"
    return st or "absent", txt


def measure(name, target=None, modules=None, reps=None):
    if name == "full":
        spec = {"target": target, "modules": modules, "reps": reps or [0, 1, 2]}
        rec_of = lambda m, r: CH.run_dir(V10, MODEL, r, EFFORT)  # noqa: E731
    else:
        spec = cells()[name]
        rec_of = lambda m, r: cell_dir(name, r)  # noqa: E731
    B = bars(spec["target"], spec["modules"])
    pairs, rows = 0, []
    ok = 0
    missing = []
    for m in spec["modules"]:
        for r in spec["reps"]:
            d = rec_of(m, r)
            f2, fa = d / "phase2" / f"{m}.json", d / "assets" / f"{m}.json"
            if not (f2.exists() and fa.exists()):
                missing.append(f"{m} r{r}")
                continue
            rec, assets = json.loads(f2.read_text(encoding="utf-8")), json.loads(fa.read_text(encoding="utf-8"))
            for e in B[m]:
                st, txt = states(rec, m, e, assets)
                pairs += 1
                ok += st != "primary"
                rows.append({"module": m, "rep": r, "element": e, "state": st, "texts": txt})
    return {"cell": name, "target": spec["target"], "pairs": pairs, "complied": ok,
            "compliance": round(ok / pairs, 3) if pairs else None, "missing": missing, "rows": rows,
            "words in phase 2": len((spec.get("p2_text") or S.build_p2(spec["keep"], spec.get("last"), spec.get("add_after"))).split()) if name != "full" else
            len((LAB / "prompts" / V10 / "phase2.md").read_text(encoding="utf-8").split())}


def selftest(log=print):
    """(1) Stub executor in a scratch cell: one Phase 2 call stored once, resumed without sending, assets written.
    (2) measure('full') on stored v10 equals the M2 count of rule_breaks.json for one target-like wording."""
    import shutil
    name = "_selftest"
    spec = {"target": "P1-16 P2", "stage": "test", "keep": ["P1-16"], "last": None, "add_after": None,
            "modules": ["neorv32_wdt"], "reps": [0], "why": "self-test"}
    c = cells()
    c[name] = spec
    CELLS.write_text(json.dumps(c, indent=1, ensure_ascii=False), encoding="utf-8")
    sent = []
    good = json.loads((CH.run_dir(V10, MODEL, 0, EFFORT) / "phase2" / "neorv32_wdt.json").read_text(encoding="utf-8"))["raw"]

    def stub(s, u):
        sent.append(1)
        return good, {"in": 1, "out": 1}
    try:
        shutil.rmtree(LAB / "runs" / "diag_v10" / name, ignore_errors=True)
        shutil.rmtree(LAB / "prompts" / "diag_v10" / name, ignore_errors=True)
        import run_a
        cap = run_a.spent
        run_a.spent = lambda log=print: 0.0
        try:
            r1 = run([name], make_call=lambda out: stub, log=lambda *a: None)
            r2 = run([name], make_call=lambda out: stub, log=lambda *a: None)
        finally:
            run_a.spent = cap
        a = json.loads((cell_dir(name, 0) / "assets" / "neorv32_wdt.json").read_text(encoding="utf-8"))
        b = json.loads((CH.run_dir(V10, MODEL, 0, EFFORT) / "assets" / "neorv32_wdt.json").read_text(encoding="utf-8"))
        ok1 = (len(sent) == 1 and set(r1.values()) == {"done"} and set(r2.values()) == {"done"}
               and sorted(x["Asset RTL"] for x in a["Assets"]) == sorted(x["Asset RTL"] for x in b["Assets"]))
    finally:
        shutil.rmtree(LAB / "runs" / "diag_v10" / name, ignore_errors=True)
        shutil.rmtree(LAB / "prompts" / "diag_v10" / name, ignore_errors=True)
        c = cells()
        c.pop(name, None)
        CELLS.write_text(json.dumps(c, indent=1, ensure_ascii=False), encoding="utf-8")
        ex = json.loads(EXTRA.read_text(encoding="utf-8")) if EXTRA.exists() else []
        EXTRA.write_text(json.dumps([p for p in ex if "_selftest" not in p], indent=1), encoding="utf-8")
    log(f"ladder self-test 1 (stub: stored once, resumed, assets equal v10's from the same reply): {'PASS' if ok1 else 'FAIL'}")
    ok2 = True
    rb = HERE / "rule_breaks.json"
    if rb.exists():
        x = json.loads(rb.read_text(encoding="utf-8"))
        for t in x.get("targets", [])[:5]:
            mods = sorted({"neorv32_" + s.split(":")[0] for s in x["M2"][t]["broken"]})
            mm = measure("full", target=t, modules=mods)
            want_broken = sum(int(s.split(" v10 ")[1].split("/")[0]) for s in x["M2"][t]["broken"])
            ok2 &= mm["pairs"] - mm["complied"] == want_broken
            log(f"  {t}: measure('full') broken {mm['pairs'] - mm['complied']} vs rule_breaks {want_broken}")
        log(f"ladder self-test 2 (measure on stored v10 = rule_breaks M2): {'PASS' if ok2 else 'FAIL'}")
    return ok1 and ok2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        sys.exit(0 if selftest() else 1)
    elif cmd == "run":
        run(sys.argv[2:])
    elif cmd == "measure":
        for n in sys.argv[2:]:
            x = measure(n)
            print(json.dumps({k: v for k, v in x.items() if k != "rows"}, ensure_ascii=False))
