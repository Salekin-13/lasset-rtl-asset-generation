"""Re-send the two_phase_v12 r0 modules that have no assets file (connection errors), with few workers. Same call path as
run_v12.run (chain.run_many, luna high); stored replies are reused, never re-asked. Estimate from v11h r0's stored cost."""
import os, sys
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_v12 as T
CH, V = T.CH, T.V
mods = [m for m in T.all_mods() if V.assets(T.V12, m, 0) is None]
_, est = T.estimate(mods)
start = T.run_a.spent(log=lambda *a: None)
W = int(os.environ.get("RERUN_WORKERS", "2"))
print(f"re-sending {len(mods)} modules {[m[8:] for m in mods]} with {W} workers (about USD {est:.2f}); spent before USD {start:.2f}")
if len(mods) > 6 or est > 0.6:
    sys.exit("more than expected; nothing sent")
res = CH.run_many([(T.V12, 0)], mods, lambda out: CH.openai(T.MODEL, T.EFFORT, out=out, poll=5), T.MODEL, T.EFFORT, executor="openai", workers=W)
print("not done:", [(x["module"], x["status"]) for x in res[(T.V12, 0)] if x.get("status") != "done"] or "none")
print(f"spent this re-send USD {T.run_a.spent(log=lambda *a: None) - start:.3f}")
