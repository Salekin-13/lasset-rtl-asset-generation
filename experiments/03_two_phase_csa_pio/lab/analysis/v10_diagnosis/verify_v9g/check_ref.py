"""Which reference rows (26 held-out modules) name an element absent from the closed set?"""
import json, os
import rescore as R

gt = R.load_json(R.GT_PATH)["modules"]
modules = sorted(d for d in os.listdir(R.HELDOUT_DIR) if d.startswith("neorv32_"))

def names_in_closed_set(cs):
    out = set()
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("port", "signal", "element", "field", "name") and isinstance(v, str):
                    out.add(v)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(cs)
    return out

total = 0
absent = []
empty = []
for m in modules:
    cs = names_in_closed_set(R.load_json(os.path.join(R.HELDOUT_DIR, m, "closed_set.json")))
    for row in gt[m]["assets"]:
        total += 1
        el = row["element"]
        if not el.strip():
            empty.append((m, repr(el)))
        elif el not in cs:
            absent.append((m, el))
print("reference rows over 26 modules:", total)
print("empty elements:", empty)
print("elements not found anywhere in closed_set.json:", len(absent))
for a in absent:
    print("  ", a)
