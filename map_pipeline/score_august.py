"""Every stored August run family (runs/assets_tuning18_<family>_r<k>), strict scorer (src/eval_assets.score) against
the manual reference's 15 tuning modules. Per run and pooled. Read-only."""
import os, re, sys
from collections import defaultdict
from pathlib import Path
def _root() -> Path:
    """The repository root: the nearest parent holding FINAL_NOTEBOOK.ipynb."""
    for q in Path(__file__).resolve().parents:
        if (q / "FINAL_NOTEBOOK.ipynb").exists():
            return q
    raise SystemExit("run this script from inside the repository")


ROOT = _root(); os.chdir(ROOT); sys.path.insert(0, "src"); sys.stdout.reconfigure(encoding="utf-8")
import eval_assets as E
gt = E.load_refs()["gt"]
fams = defaultdict(list)
for d in sorted((ROOT / "runs").iterdir()):
    m = re.match(r"assets_tuning18_(v[0-9a-z_]+?)_r(\d+)$", d.name)
    if m: fams[m.group(1)].append(d)
order = sorted(fams, key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)])
print("| family | runs | per run TP/FP/FN | pooled P | pooled R | mean listed |")
for f in order:
    rows = []
    for d in fams[f]:
        res = E.score(E.load_run(d), gt, strict=True)
        if res["tp"] + res["fp"] + res["fn"] == 0:
            continue  # an empty run folder (for example v01c6p1p2 r3 and r4), not a run
        rows.append((res["tp"], res["fp"], res["fn"]))
    T = sum(r[0] for r in rows); Fp = sum(r[1] for r in rows); Fn = sum(r[2] for r in rows)
    print(f"| {f} | {len(rows)} | {'; '.join(f'{a}/{b}/{c}' for a,b,c in rows)} | {T/(T+Fp):.3f} | {T/(T+Fn):.3f} | {(T+Fp)/len(rows):.0f} |")
