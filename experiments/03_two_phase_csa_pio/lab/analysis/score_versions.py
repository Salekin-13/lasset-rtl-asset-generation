"""Every stored two-phase version, scored with the lab's exact scorer (compare_v8.score) on the tuning 15 and the held-out
26, per complete run; pooled over the complete runs; all 41 = both splits pooled when both have the same runs. Read-only. Writes score_all_versions.json beside this script."""
import os, sys, json, re
from pathlib import Path


def _root() -> Path:
    """The repository root: the nearest parent holding FINAL_NOTEBOOK.ipynb (works from experiments/03_two_phase_csa_pio/lab/analysis/ or anywhere in the repo)."""
    for p in Path(__file__).resolve().parents:
        if (p / "FINAL_NOTEBOOK.ipynb").exists():
            return p
    raise SystemExit("run this script from inside the repository")


ROOT = _root(); LAB = ROOT / "experiments" / "03_two_phase_csa_pio" / "lab"
sys.path.insert(0, str(LAB)); sys.path.insert(0, str(LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1"); os.chdir(ROOT); sys.stdout.reconfigure(encoding="utf-8")
import labkit as K, compare_v8 as C8, chain as CH
MODEL, EFF = "gpt-5.6-luna", "high"
g = K.gt_modules(); ref = C8.refs(sorted(set(g["tuning"]) | set(g["heldout"])))
print("scorer self-test:", "PASS" if C8.selftest(ref) else "FAIL")
vers = sorted({d.name[:-4] for d in (LAB / "runs").iterdir() if d.name.startswith("two_phase_") and d.name.endswith("__v1")},
              key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)])
out = {}
for v in vers:
    row = {}
    for k, mods in (("tuning", g["tuning"]), ("heldout", g["heldout"])):
        F = sum(len(ref[m]) for m in mods); reps = []
        for r in range(0, 6):
            if not CH.run_dir(v, MODEL, r, EFF).exists(): continue
            sc = [C8.score(v, r, m, ref) for m in mods]
            if all(s is not None for s in sc):
                reps.append((r, sum(s[1] for s in sc), sum(s[0] for s in sc)))
        if reps:
            T = sum(x[1] for x in reps); L = sum(x[2] for x in reps); n = len(reps)
            row[k] = {"runs": [x[0] for x in reps], "per_run": [(x[1], x[2]) for x in reps], "P": round(T / L, 3), "R": round(T / (n * F), 3), "findable": F}
    if "tuning" in row and "heldout" in row and row["tuning"]["runs"] == row["heldout"]["runs"]:
        T = sum(c for c, l in row["tuning"]["per_run"]) + sum(c for c, l in row["heldout"]["per_run"])
        L = sum(l for c, l in row["tuning"]["per_run"]) + sum(l for c, l in row["heldout"]["per_run"])
        n = len(row["tuning"]["runs"]); Fa = row["tuning"]["findable"] + row["heldout"]["findable"]
        row["all41"] = {"runs": row["tuning"]["runs"], "per_run": [(a + c, b + d) for (a, b), (c, d) in zip(row["tuning"]["per_run"], row["heldout"]["per_run"])],
                        "P": round(T / L, 3), "R": round(T / (n * Fa), 3), "findable": Fa}
    out[v] = row
    def fmt(k):
        if k not in row: return "-"
        z = row[k]; return f"{z['P']:.3f} / {z['R']:.3f} ({len(z['runs'])} run{'s' if len(z['runs'])>1 else ''}: {', '.join(f'{c}/{l}' for c,l in z['per_run'])})"
    print(f"| {v.replace('two_phase_','')} | {fmt('tuning')} | {fmt('heldout')} | {fmt('all41')} |")
Path(__file__).with_suffix(".json").write_text(json.dumps(out, indent=1), encoding="utf-8")
