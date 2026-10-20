"""Re-send the two_phase_v9g held-out modules that have no assets file (connection errors in r1 and r2), with few
workers. Same call path as run_v9g.run (chain.run_many, luna high); stored replies and pending ids are reused, never
re-asked. RERUN_REPS (default "1,2"), RERUN_WORKERS (default 3)."""
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_v9g as T  # noqa: E402

CH, V = T.CH, T.V
REPS = [int(x) for x in os.environ.get("RERUN_REPS", "1,2").split(",")]
jobs = {r: [m for m in T.mods_of("A") if V.assets(T.V9G, m, r) is None] for r in REPS}
mods = sorted({m for v in jobs.values() for m in v})
start = T.run_a.spent(log=lambda *a: None)
W = int(os.environ.get("RERUN_WORKERS", "3"))
print(f"re-sending {sum(len(v) for v in jobs.values())} module-runs ({ {r: [m[8:] for m in v] for r, v in jobs.items()} }) with {W} workers; spent before USD {start:.2f}", flush=True)
if sum(len(v) for v in jobs.values()) > 16:
    sys.exit("more than expected; nothing sent")
for r in REPS:
    if not jobs[r]:
        continue
    res = CH.run_many([(T.V9G, r)], jobs[r], lambda out: CH.openai(T.MODEL, T.EFFORT, out=out, poll=5), T.MODEL, T.EFFORT, executor="openai", workers=W)
    print(f"r{r} not done:", [(x["module"], x["status"]) for x in res[(T.V9G, r)] if x.get("status") != "done"] or "none", flush=True)
print(f"spent this re-send USD {T.run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)
