"""Format problems on the replies as written (chain.from_format_phase1/2 on "raw"), v5g r0-r2 vs v5f r0-r5, by kind:
replies with it / count. Also: walks whose "Assets" list is empty while points carry their own "Assets" (the nesting
slip), and how many asset rows sit inside points. Hand check: v5g r0 bus has 10 walks, all with empty walk-level Assets
and point-level Assets present."""
import json, os, re, sys
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB)); os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH, labkit as K
sys.stdout.reconfigure(encoding="utf-8")
RUNS = [("v5g", "two_phase_v5g", r) for r in (0, 1, 2)] + [("v5f", "two_phase_v5f", r) for r in range(6)]
def norm(x):
    x = re.sub(r"(walk|conceptual asset|not-kept entry) \S+( (point|asset|not-reported entry) (?:'[^']*'|\d+))?", lambda m: m.group(1) + (" " + m.group(3) if m.group(3) else ""), x)
    return re.sub(r"\[.*?\]|'.*?'|\(.*?\)", "…", x)
kinds = {}; nest = {}
for k, v, r in RUNS:
    c, reps = Counter(), Counter(); ns = Counter()
    for m in CH.tuning_modules():
        run = CH.run_dir(v, "gpt-5.6-luna", r, "high")
        rec1 = json.loads((run / "phase1" / f"{m}.json").read_text(encoding="utf-8")); rec2 = json.loads((run / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
        p1, p2 = K.parse_json(rec1["raw"]), K.parse_json(rec2["raw"])
        _, a = CH.from_format_phase1(p1, rec1["raw"])
        ids = [c0.get("Concept ID") for c0 in p1.get("Conceptual Assets", []) if isinstance(c0, dict)]
        _, b = CH.from_format_phase2(p2, rec2["raw"], ids)
        seen = set()
        for ph, pr in ((1, a), (2, b)):
            for x in pr:
                kk = f"p{ph} " + norm(x); c[kk] += 1
                if kk not in seen: reps[kk] += 1; seen.add(kk)
        hit = False
        for w in p2.get("Concept Walks", []):
            if not isinstance(w, dict): continue
            inner = sum(len(p.get("Assets") or []) for p in (w.get("Points") or []) if isinstance(p, dict) and isinstance(p.get("Assets"), list))
            if inner:
                ns["walks with Assets inside points"] += 1; ns["asset rows inside points"] += inner
                ns["  of them with an empty walk-level Assets"] += not (w.get("Assets") or []); hit = True
        ns["replies with the nesting slip"] += hit
        if k == "v5g" and r == 0 and m == "neorv32_bus":
            assert sum(1 for w in p2["Concept Walks"] if not w.get("Assets")) == 10, "hand check failed"
    kinds[f"{k} r{r}"] = (c, reps); nest[f"{k} r{r}"] = ns
allk = sorted(set().union(*[c for c, _ in kinds.values()]), key=lambda x: -sum(kinds[r][0][x] for r in kinds))
print("format and consistency problems (replies/count) per run:", "  ".join(kinds))
for x in allk:
    print(f"  {x[:95]:95s} " + "  ".join(f"{kinds[r][1][x]}/{kinds[r][0][x]}".ljust(6) for r in kinds))
print("\nnesting slip (Assets written inside points):")
for key in ("replies with the nesting slip", "walks with Assets inside points", "  of them with an empty walk-level Assets", "asset rows inside points"):
    print(f"  {key:45s} " + "  ".join(f"{r}: {nest[r][key]}" for r in nest))
