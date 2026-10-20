"""Module splits for later prompt versions, separate from the input version's own split (kit_data/<version>.json, which
K.gt_modules() reads and which the old compare scripts and running jobs depend on).

  import splits
  S = splits.load("tuning_v2")        # {"tuning": [...], "heldout": [...]}

In the notebook (cell 1), to run on the new tuning set:  ALL = splits.load("tuning_v2")["tuning"]
Checks on load: the two lists are disjoint, cover exactly the modules of K.gt_modules(), and every module has its three
input files.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name: str = "tuning_v2") -> dict:
    s = json.loads((HERE / f"{name}.json").read_text(encoding="utf-8"))
    tun, held = list(s["tuning"]), list(s["heldout"])
    import labkit as K
    import chain as CH
    old = K.gt_modules()
    if set(tun) & set(held) or sorted(tun + held) != sorted(old["tuning"] + old["heldout"]):
        raise RuntimeError(f"split {name}: lists overlap or do not cover the reference modules")
    for m in tun + held:
        for f in ("rtl.txt", "closed_set.json", "diagram.txt"):
            if not (CH.module_dir(m) / f).exists():
                raise RuntimeError(f"split {name}: {m} has no {f}")
    return {"tuning": tun, "heldout": held}
