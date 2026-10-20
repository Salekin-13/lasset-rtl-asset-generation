"""Phase 1-only runs for the rule order / position study (PLAN_P1_ORDER.md): sends only the Phase 1 call of a prompt version for a
module set and stores phase1/<module>.json in the version's usual run folder (same guard, _run_meta.json and record format as
chain.run_many, so a later full run can reuse the records and the verifiers can rebuild them). Nothing of Phase 2 is sent.
Readings: read_p1.py. Cost: about USD 0.53 per run on the held-out 26 (v9j r0's Phase 1 records).
  python -B run_p1.py preview <version> <reps>            estimate only
  <conda python> run_p1.py send <version> <reps> --send [--approved]   (budget file budget_v9n.json; floor as run_v9n)
"""
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402
import run_v9g as RG  # noqa: E402
import run_v9n as N  # noqa: E402

V, CH, run_a = RG.V, RG.CH, RG.run_a


def p1_cost(v, reps):
    ms, _ = N.groups()
    base = sum(run_a.usd(json.loads((CH.run_dir("two_phase_v9j", MODEL, 0, EFFORT) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["usage"]) for m in ms)
    gr = len(V.CK.system(v, 1)) / len(V.CK.system("two_phase_v9j", 1))
    return base, base * gr * len(reps)


def send_phase1(version, rep, modules, workers=3):
    out = CH._prepare(version, MODEL, EFFORT, rep, "openai")
    call = CH.openai(MODEL, EFFORT, out=out, poll=5, retry_incomplete=True)
    stop = CH._new_run_flag()
    meta = {"module": None, "prompt version": version, "input version": CH.INPUT_VERSION, "phase": 1}
    adapt = CH.from_format_phase1 if CH.new_format(version, 1) else None

    def one(m):
        threading.current_thread().lab_stop = stop
        try:
            rec = CH._ask(call, CH.C.system(version, 1), CH.user_message(version, 1, m), out / "phase1" / f"{m}.json",
                          lambda o: CH.check_phase1(m, o), {**meta, "module": m}, adapt=adapt)
            return {"module": m, "status": "phase 1 schema failure" if CH.stopped(rec, 1) else "done", "problems": len(rec.get("problems") or [])}
        except Exception as e:  # noqa: BLE001
            return {"module": m, "status": f"ERROR {type(e).__name__}: {e}"}
    pool = ThreadPoolExecutor(max_workers=workers)
    rows = list(pool.map(one, modules))
    pool.shutdown(wait=True)
    bad = [(r["module"], r["status"]) for r in rows if r["status"] != "done"]
    print(f"{version} r{rep} phase 1: {len(rows) - len(bad)} of {len(rows)} done" + (f"; not done: {bad}" if bad else ""), flush=True)
    return rows


def actual_p1(v, reps):
    ms, _ = N.groups()
    s = 0.0
    for r in reps:
        for m in ms:
            f = CH.run_dir(v, MODEL, r, EFFORT) / "phase1" / f"{m}.json"
            if f.exists():
                s += run_a.usd(json.loads(f.read_text(encoding="utf-8"))["usage"])
    return s


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd, v, reps = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")]
    ms, _ = N.groups()
    base, est = p1_cost(v, reps)
    b = N.budget()
    have = [r for r in reps if all((CH.run_dir(v, MODEL, r, EFFORT) / "phase1" / f"{m}.json").exists() for m in ms)]
    print(f"{v} Phase 1 only, reps {reps}: estimate USD {est:.2f} (v9j r0 Phase 1 USD {base:.2f} x growth x {len(reps)}); records already complete for reps {have}; remaining USD {b['remaining']:.2f}")
    if cmd == "send":
        if not V.CK.check(v, log=lambda *a: None):
            sys.exit("checker FAIL")
        if "--send" not in sys.argv:
            sys.exit("not sent (no --send)")
        if b["remaining"] - est < N.FLOOR and "--approved" not in sys.argv:
            sys.exit(f"REFUSED: remaining {b['remaining']:.2f} - estimate {est:.2f} < floor {N.FLOOR}")
        for r in reps:
            if r in have:
                print(f"r{r} already complete; skipped", flush=True)
                continue
            send_phase1(v, r, ms, workers=int(os.environ.get("RUN_WORKERS", "3")))
        spent = actual_p1(v, reps)
        b = N.budget()
        b["remaining"] = round(b["remaining"] - spent, 3)
        b["sends"].append({"version": v, "phase": 1, "reps": reps, "usd": round(spent, 3)})
        N.BUDGET.write_text(json.dumps(b, indent=1), encoding="utf-8")
        print(f"spent USD {spent:.3f} (Phase 1 records of {v}); remaining USD {b['remaining']:.2f}", flush=True)
