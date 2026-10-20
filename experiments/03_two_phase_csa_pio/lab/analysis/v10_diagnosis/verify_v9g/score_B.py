"""Independent re-score (suffix _B) of two_phase_v9g r0, two_phase_v9f r0 and two_phase_v9 r0-r2 on four module groups.

Written from the file formats alone; imports nothing from the lab. Exact scorer as specified:
  per module: Counter of listed names ("Asset RTL" rows); walk the reference rows in order; a row whose element
  still has a listed copy left consumes one copy and counts as correct. listed = number of asset rows.
  findable = reference rows whose element is a declared name in the module's closed set (port, signal or field name
  of any entity); findable_all = every reference row.
Record-port dotted name: a listed name containing "." whose prefix before the first "." is a port (any entity) with a
non-empty "record type" in the module's closed set.
"""
import json, os, sys
from collections import Counter

ROOT = r"E:\jobs\ff\test\Prepoison_subset"
LAB = os.path.join(ROOT, "experiments", "03_two_phase_csa_pio", "lab")
INPUTS = os.path.join(LAB, "inputs", "v1")
RUNS = os.path.join(LAB, "runs")
MODEL_DIR = "gpt-5.6-luna__high"
GT_PATH = os.path.join(ROOT, "data", "ground_truth", "manual_gt_neorv32.json")
SPLIT_PATH = os.path.join(LAB, "splits", "tuning_v2.json")
OUT_PATH = os.path.join(LAB, "analysis", "v10_diagnosis", "verify_v9g", "score_B_result.json")

VERSIONS_RUNS = [("two_phase_v9g", 0), ("two_phase_v9f", 0), ("two_phase_v9", 0), ("two_phase_v9", 1), ("two_phase_v9", 2)]


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def folders(split):
    return sorted(d for d in os.listdir(os.path.join(INPUTS, split))
                  if d.startswith("neorv32_") and os.path.isdir(os.path.join(INPUTS, split, d)))


def module_split(m):
    for s in ("tuning", "heldout"):
        if os.path.isdir(os.path.join(INPUTS, s, m)):
            return s
    raise FileNotFoundError(m)


def closed_set(m):
    return load(os.path.join(INPUTS, module_split(m), m, "closed_set.json"))


def declared_names(cs):
    """Port, signal and field names of every entity (the names a reply can pick from)."""
    names = set()
    for e in cs["entity list"]:
        for x in e.get("port list", []) + e.get("signal list", []):
            names.add(x.get("port") or x.get("signal"))
            for f in x.get("fields", []):
                names.add(f["field"])
    return names


def any_string_names(cs):
    """Every string value anywhere in the closed set (broader reading of 'appears somewhere')."""
    out = set()

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            out.add(o)
    walk(cs)
    return out


def record_ports(cs):
    out = set()
    for e in cs["entity list"]:
        for x in e.get("port list", []):
            if x.get("record type"):
                out.add(x["port"])
    return out


def assets_path(version, run, m):
    return os.path.join(RUNS, f"{version}__v1", MODEL_DIR, f"r{run}", "assets", m + ".json")


def score_module(ref_rows, listed_names, declared, anystr, recports):
    left = Counter(listed_names)
    correct = 0
    for r in ref_rows:
        el = r["element"]
        if left[el] > 0:
            left[el] -= 1
            correct += 1
    findable = sum(1 for r in ref_rows if r["element"] in declared)
    findable_any = sum(1 for r in ref_rows if r["element"] in anystr)
    dotted = sum(1 for n in listed_names if "." in n and n.split(".", 1)[0] in recports)
    return {"correct": correct, "listed": len(listed_names), "findable": findable, "findable_any_string": findable_any,
            "findable_all": len(ref_rows), "excluded_not_in_closed_set": len(ref_rows) - findable,
            "record_port_dotted": dotted}


def main():
    gt = load(GT_PATH)["modules"]
    split = load(SPLIT_PATH)
    tuning15_folders = folders("tuning")
    heldout26 = folders("heldout")
    # the two tuning folders without reference rows and without any assets file are reported, not scored
    no_ref = [m for m in tuning15_folders if m not in gt]
    tuning15 = [m for m in tuning15_folders if m in gt]
    tuning_v2 = list(split["tuning"])
    heldout_v2_listed = list(split["heldout"]) if "heldout" in split else None
    all41 = sorted(gt)
    heldout_v2_derived = [m for m in all41 if m not in tuning_v2]
    groups = {"tuning 15": tuning15, "held-out 26": heldout26, "tuning_v2": tuning_v2,
              "heldout_v2": heldout_v2_listed if heldout_v2_listed is not None else heldout_v2_derived}

    # per-module static facts
    static = {}
    for m in all41:
        cs = closed_set(m)
        static[m] = (declared_names(cs), any_string_names(cs), record_ports(cs))

    per_module = {}  # (version, run) -> module -> dict
    for version, run in VERSIONS_RUNS:
        per_module[(version, run)] = {}
        for m in all41:
            p = assets_path(version, run, m)
            if not os.path.exists(p):
                per_module[(version, run)][m] = None
                continue
            listed = [row["Asset RTL"] for row in load(p)["Assets"]]
            d, a, rp = static[m]
            per_module[(version, run)][m] = score_module(gt[m]["assets"], listed, d, a, rp)

    figures = {}
    for g, mods in groups.items():
        figures[g] = {"modules": len(mods)}
        for version, run in VERSIONS_RUNS:
            key = f"{version} r{run}"
            tot = Counter()
            missing = []
            for m in mods:
                x = per_module[(version, run)].get(m)
                if x is None:
                    missing.append(m)
                    continue
                tot.update(x)
            row = dict(tot)
            row["recall"] = round(row["correct"] / row["findable"], 4) if row["findable"] else None
            row["precision"] = round(row["correct"] / row["listed"], 4) if row["listed"] else None
            row["recall_all_rows"] = round(row["correct"] / row["findable_all"], 4) if row["findable_all"] else None
            row["missing_assets_files"] = len(missing)
            figures[g][key] = row

    # self-test: hand-readable dump for one module, one run
    st_mod, st_ver, st_run = "neorv32_bus", "two_phase_v9g", 0
    listed = [row["Asset RTL"] for row in load(assets_path(st_ver, st_run, st_mod))["Assets"]]
    refs = [r["element"] for r in gt[st_mod]["assets"]]
    print("SELF-TEST", st_mod, st_ver, "r%d" % st_run)
    print("  listed names (%d):" % len(listed), listed)
    print("  reference elements in order (%d):" % len(refs), refs)
    d, a, rp = static[st_mod]
    print("  reference elements not in declared closed-set names:", [e for e in refs if e not in d])
    print("  record ports:", sorted(rp))
    print("  scorer says:", per_module[(st_ver, st_run)][st_mod])
    # hand re-count with a different method: multiset intersection size
    hand = sum((Counter(refs) & Counter(listed)).values())
    print("  hand re-count via multiset intersection:", hand)
    assert hand == per_module[(st_ver, st_run)][st_mod]["correct"], "self-test failed"
    # second cross-check: order-walk correct == multiset intersection for every module/run
    for (version, run), mm in per_module.items():
        for m, x in mm.items():
            if x is None:
                continue
            listed = [row["Asset RTL"] for row in load(assets_path(version, run, m))["Assets"]]
            refs = [r["element"] for r in gt[m]["assets"]]
            assert x["correct"] == sum((Counter(refs) & Counter(listed)).values()), (version, run, m)
    print("  cross-check passed on every module and run")

    result = {"groups": {g: mods for g, mods in groups.items()},
              "split_keys_used": {"tuning_v2": "tuning", "heldout_v2": "heldout" if heldout_v2_listed else "derived"},
              "heldout_v2_listed_equals_derived": heldout_v2_listed == heldout_v2_derived,
              "tuning_folders_without_reference_rows": no_ref,
              "tuning_folder_count": len(tuning15_folders),
              "figures": figures,
              "per_module": {f"{v} r{r}": mm for (v, r), mm in per_module.items()}}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print()
    print("split keys used:", result["split_keys_used"], "| heldout listed == derived:", result["heldout_v2_listed_equals_derived"])
    print("tuning folders:", len(tuning15_folders), "| without reference rows (and no assets file in any run):", no_ref)
    for g in groups:
        print()
        print(f"== {g} ({len(groups[g])} modules)")
        for version, run in VERSIONS_RUNS:
            r = figures[g][f"{version} r{run}"]
            print(f"  {version} r{run}: correct {r['correct']} listed {r['listed']} findable {r['findable']} "
                  f"(any-string {r['findable_any_string']}, all rows {r['findable_all']}, excluded {r['excluded_not_in_closed_set']}) "
                  f"R {r['recall']} P {r['precision']} R_all {r['recall_all_rows']} dotted {r['record_port_dotted']} "
                  f"missing files {r['missing_assets_files']}")
    print()
    print("wrote", OUT_PATH)


if __name__ == "__main__":
    main()
