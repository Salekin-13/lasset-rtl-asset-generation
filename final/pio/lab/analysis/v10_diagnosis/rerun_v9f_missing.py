"""Re-send the two_phase_v9f r0 modules that have no assets file (connection errors), with few workers. Same call path
as run_v9f.run (chain.run_many, luna high); stored replies and pending ids are reused, never re-asked."""
import os, sys
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_v9f as T
CH, V = T.CH, T.V
REPS = [int(x) for x in os.environ.get("RERUN_REPS", "0").split(",")]
OPT = os.environ.get("RERUN_OPTION", "B")
jobs = {r: [m for m in T.mods_of(OPT) if V.assets(T.V9F, m, r) is None] for r in REPS}
mods = sorted({m for v in jobs.values() for m in v})
start = T.run_a.spent(log=lambda *a: None)
W = int(os.environ.get("RERUN_WORKERS", "2"))
print(f"re-sending {len(mods)} modules {[m[8:] for m in mods]} with {W} workers; spent before USD {start:.2f}")
if len(mods) > 10:
    sys.exit("more than expected; nothing sent")
res = CH.run_many([(T.V9F, r) for r in REPS if jobs[r]], mods, lambda out: CH.openai(T.MODEL, T.EFFORT, out=out, poll=5), T.MODEL, T.EFFORT, executor="openai", workers=W)
print("not done:", [(k[1], x["module"], x["status"]) for k, v in res.items() for x in v if x.get("status") != "done"] or "none")
print(f"spent this re-send USD {T.run_a.spent(log=lambda *a: None) - start:.3f}")
