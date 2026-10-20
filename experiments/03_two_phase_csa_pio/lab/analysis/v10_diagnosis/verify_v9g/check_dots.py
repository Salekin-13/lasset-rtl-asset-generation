"""Transparency check: list the dotted names whose prefix is a record port, and duplicate rows."""
import json, os
from collections import Counter
import rescore as R

gt = R.load_json(R.GT_PATH)["modules"]
modules = sorted(d for d in os.listdir(R.HELDOUT_DIR) if d.startswith("neorv32_"))
rec = {m: R.record_ports(R.load_json(os.path.join(R.HELDOUT_DIR, m, "closed_set.json"))) for m in modules}
print("record ports per module:")
for m in modules:
    print(" ", m, sorted(rec[m]))

print("\nreference duplicate rows (same element more than once) over 26 modules:")
dups = 0
for m in modules:
    c = Counter(r["element"] for r in gt[m]["assets"])
    d = {k: v for k, v in c.items() if v > 1}
    if d:
        print(" ", m, d)
        dups += sum(v - 1 for v in d.values())
print("  extra rows from duplicates:", dups)

for ver in R.VERSIONS:
    for run in R.RUNS:
        hits = []
        listed_dups = 0
        for m in modules:
            p = os.path.join(R.RUNS_DIR, f"{ver}__v1", R.MODEL_DIR, run, "assets", m + ".json")
            names = [r["Asset RTL"] for r in R.load_json(p)["Assets"]]
            listed_dups += sum(v - 1 for v in Counter(names).values() if v > 1)
            for n in names:
                if "." in n and n.split(".", 1)[0] in rec[m]:
                    hits.append(f"{m}:{n}")
        print(f"\n{ver} {run}: record-port dotted = {len(hits)}; duplicate listed names = {listed_dups}")
        print("  ", hits[:70])
