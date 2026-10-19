"""Sensitivity of the 'internal and not anchored' split to the anchoring rule. Re-walks the rows with
walk_found_internal's own functions under three anchoring variants. No API calls."""
import json, os, sys
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import walk_found_internal as W

ref = W.reference(); grp = W.groups(ref); all41 = sorted(set(grp["tuning 15"]) | set(grp["held-out 26"]))

def anchored_variant(row, concepts, cn, keys, use_held, use_io):
    name = row["Asset RTL"]; al = None
    for cid in row.get("Concepts", []):
        c = concepts.get(cid)
        if c is None: continue
        if use_io and (name in W.chain.as_list(c.get("enters through")) or name in W.chain.as_list(c.get("leaves through"))):
            return True
        if use_held:
            if al is None:
                al = set()
                for rec in W._records(cn, row["Entity"], name):
                    for k in keys:
                        for cp in rec.get("counterparts", {}).get(k, []):
                            al |= {int(x) for x in cp.get("lines", [])}
            if al & {int(x) for x in W.chain.as_list(c.get("held lines"))}:
                return True
    return False

VARIANTS = {
    "as defined (gets/decided/reset/clocked + enters/leaves)": (W.ASSIGN_KEYS, True, True),
    "assignment = gets value from + decided by only": (("gets value from", "decided by"), True, True),
    "assignment = gets value from only": (("gets value from",), True, True),
    "enters/leaves only (no held-line test)": ((), False, True),
    "held-line test only (no enters/leaves)": (W.ASSIGN_KEYS, True, False),
}
for label, (keys, use_held, use_io) in VARIANTS.items():
    print("\n==", label)
    for ver in W.VERSIONS:
        pooled = Counter()
        for rep in W.REPS:
            d = W.RUNS / f"{ver}__v1" / W.MODEL / f"r{rep}"
            for m in all41:
                rows = json.loads((d / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]
                concepts = {c["id"]: c for c in json.loads((d / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["reply"]["conceptual assets"]}
                cn = W.closed(m)
                _, _, _, ok = W.score([x["Asset RTL"] for x in rows], ref[m])
                for x, k in zip(rows, ok):
                    if W.is_internal(cn, x["Entity"], x["Asset RTL"]) is True and not anchored_variant(x, concepts, cn, keys, use_held, use_io):
                        pooled["n"] += 1; pooled["correct"] += k; pooled["false"] += (not k)
        print(f"  {ver}: internal&not-anchored {pooled['n']}  correct {pooled['correct']}  false {pooled['false']}")
