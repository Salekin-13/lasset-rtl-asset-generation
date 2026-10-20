"""LAsset's published initial lists (RTL-only, spec+RTL) scored with the PIO lab's exact scorer (compare_v8: names
equal, each reference entry used once; findable = reference names in the module's closed set). Read-only."""
import os, sys, json
from collections import Counter, defaultdict
from pathlib import Path


def _root() -> Path:
    """The repository root: the nearest parent holding FINAL_NOTEBOOK.ipynb (works from experiments/03_two_phase_csa_pio/lab/analysis/ or anywhere in the repo)."""
    for p in Path(__file__).resolve().parents:
        if (p / "FINAL_NOTEBOOK.ipynb").exists():
            return p
    raise SystemExit("run this script from inside the repository")


ROOT = _root(); os.chdir(ROOT)
LAB = ROOT / "experiments" / "03_two_phase_csa_pio" / "lab"
for p in (LAB, LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2", ROOT / "final", ROOT / "src", ROOT / "assetgen_meta" / "lasset_layer", ROOT):
    sys.path.insert(0, str(p))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
sys.stdout.reconfigure(encoding="utf-8")
import labkit as K, compare_v8 as C8, lasset_layer as LL
g = K.gt_modules(); ref = C8.refs(sorted(set(g["tuning"]) | set(g["heldout"])))
print("scorer self-test:", "PASS" if C8.selftest(ref) else "FAIL")

def per_module_names(items):
    """Normalise the loader's output to {module: [names]}; print the shape if unknown."""
    if isinstance(items, dict) and all(isinstance(v, list) for v in items.values()):
        out = {}
        for m, v in items.items():
            out[m] = [x if isinstance(x, str) else next(x[k] for k in ("Asset RTL", "asset_rtl", "rtl", "name", "asset") if k in x) for x in v]
        return out
    if isinstance(items, list) and items and isinstance(items[0], dict):
        out = defaultdict(list)
        for x in items:
            m = next(x[k] for k in ("module", "entity", "ip", "Module") if k in x)
            n = next(x[k] for k in ("Asset RTL", "asset_rtl", "rtl", "name", "asset", "structural") if k in x)
            out[m].append(n)
        return dict(out)
    raise SystemExit(f"unknown shape: {type(items)} sample {str(items)[:300]}")

def score(names, m):
    listed, found = Counter(names), 0
    for n in ref[m]:
        if listed[n] > 0:
            listed[n] -= 1; found += 1
    return len(names), found

for key, label in (("rtl_only", "LAsset RTL-only"), ("spec_rtl", "LAsset spec+RTL")):
    try:
        items = LL.load_list(key)
    except Exception as e:
        print(label, "load failed:", e); continue
    pm = per_module_names(items)
    mods_in = set(pm)
    for k, mods in (("tuning", g["tuning"]), ("heldout", g["heldout"]), ("all41", g["tuning"] + g["heldout"])):
        F = sum(len(ref[m]) for m in mods)
        L = T = 0; miss = []
        for m in mods:
            key_m = m if m in pm else (m.replace("neorv32_", "") if m.replace("neorv32_", "") in pm else None)
            if key_m is None:
                miss.append(m); continue
            l, t = score(pm[key_m], m); L += l; T += t
        print(f"{label:16s} {k:8s} listed {L}  correct {T}  findable {F}  P {T/L:.3f}  R {T/F:.3f}" + (f"  (modules missing from the list: {miss})" if miss else ""))
