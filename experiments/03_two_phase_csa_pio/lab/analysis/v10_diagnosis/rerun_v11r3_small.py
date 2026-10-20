"""Re-send driver used for the v11r3 re-test's runs 3 and 4 (2026-10-17), after connection errors at 50 workers:
the same run_v11r3 jobs, estimate and request path, with fewer workers (run 3: 6, run 4: 1). Logs: logs/v11r3_run3.log, run4.log."""
import os, sys
os.environ["V11R3_OPTION"] = "p1"
sys.path.insert(0, r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab\analysis\v10_diagnosis")
os.chdir(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab\analysis\v10_diagnosis")
import run_v11r3 as T
if not T.selftest(log=lambda *a: None):
    sys.exit("self-test FAIL; nothing sent")
jl, tx, todo = T.jobs()
est, _ = T.estimate(todo)
start = T.run_a.spent(log=lambda *a: None)
WORKERS = int(os.environ.get("RERUN_WORKERS", "1"))
print(f"re-sending {len(todo)} with {WORKERS} workers (about USD {est:.2f}); spent before USD {start:.2f}")
if len(todo) > 20 or est > 0.5:
    sys.exit("more than expected; nothing sent")
T.ISO.use(T.VAR)
T.ISO.run(todo, tx, lambda out: T.CH.openai(T.MODEL, T.EFFORT, out=out, poll=5, max_tokens=64000), T.MODEL, T.EFFORT, workers=WORKERS)
T.ISO.use("v9")
print(f"not stored: {len(T.jobs()[2])}; spent this run USD {T.run_a.spent(log=lambda *a: None) - start:.3f}")
