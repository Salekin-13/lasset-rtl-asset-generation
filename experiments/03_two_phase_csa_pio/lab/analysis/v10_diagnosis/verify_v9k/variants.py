"""Sensitivity of the 'internal and not anchored' correct/false split to the correctness rule.
Reads walk_found_internal.json (written by walk_found_internal.py) and the reference. No API calls."""
import json, os, sys
from collections import Counter
from pathlib import Path
os.environ["PIO_INPUT_VERSION"] = "v1"
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]; ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
import chain
res = json.loads((HERE / "walk_found_internal.json").read_text(encoding="utf-8"))
gt = json.loads((ROOT / "data/ground_truth/manual_gt_neorv32.json").read_text(encoding="utf-8"))["modules"]
ref = {m: [r["element"] for r in gt[m]["assets"] if r["element"] in {k[1] for k in chain.closed_names(m)}] for m in res["all41"]}
for ver, runs in res["versions"].items():
    pooled = Counter()
    for rep, per_mod in runs.items():
        for m, rec in per_mod.items():
            sel = [r for r in rec["rows"] if r["internal"] is True and not r["anchored"]]
            refset = set(ref[m])
            seen = Counter()
            for r in sel:
                pooled["n"] += 1
                pooled["copies rule correct"] += r["correct"]
                pooled["name-in-reference correct"] += r["name"] in refset
                # duplicate copy of a name already listed in the same module (any earlier row)
            names_all = [r["name"] for r in rec["rows"]]
            first_idx = {}
            for i, n in enumerate(names_all):
                first_idx.setdefault(n, i)
            for i, r in enumerate(rec["rows"]):
                if r["internal"] is True and not r["anchored"]:
                    pooled["later copy of a name"] += first_idx[r["name"]] != i
                    pooled["later copy and name in ref"] += (first_idx[r["name"]] != i) and (r["name"] in refset)
    print(ver, dict(pooled))
