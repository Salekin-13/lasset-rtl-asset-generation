"""Score a blind boundary test of Phase 2 rule text on two_phase_v5f's stored replies.

Input: a JSON file with the judges' answers, [{"module": short, "judge": 1|2, "changes": [{"row_id", "new_label",
"rule_ids"}], "new_primaries": [{"run", "element", "entity", "rule_ids"}]}] (row ids as in views_blind/ and
boundary_key.json). Judges never saw which rows the reference lists; this script uses the hidden key.

Per run (r0-r2), for "either judge" (union of changes) and "both judges" (changes both made): listed primaries,
correct, false positives, precision, recall (of 109), with the same exact rule as the scorer (names equal, each
reference entry matched once, one listing per (entity, element)). Per rule id: correct finds lost (a correct element
whose every primary row in that run is demoted), false positives removed, correct finds gained, false positives added.
Self-test: with no changes the counts equal compare_v5f.json (206/91, 214/85, 220/92).

  python score_boundary.py <judges.json> [out.json]
"""
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent
LAB = AN.parents[1]
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402

KEY = json.loads((HERE / "boundary_key.json").read_text(encoding="utf-8"))


def refs_by_short():
    import eval_assets as ea
    with CH.at_root():
        refs = ea.load_refs()["gt"]
    out = {}
    for m in CH.tuning_modules():
        names = {n for (_, n) in CH.closed_names(m)}
        out[m.replace("neorv32_", "")] = [n for n, _ in refs[m] if n in names]
    return out


REFS = refs_by_short()


def primaries(labels, extra):
    """(run, short) -> {(entity, element): [rule ids that put it there]} from row labels plus new primaries."""
    out = defaultdict(dict)
    for rid, k in KEY.items():
        if labels.get(rid, k["label"]) == "primary":
            short, run = rid.split(":")[0], k["run"]
            for el in k["elements"]:
                if isinstance(el, str) and el:
                    out[(run, short)].setdefault((k["entity"], el), [])
    for (run, short, ent, el, rules) in extra:
        out[(run, short)].setdefault((ent, el), []).extend(rules)
    return out


def score(prim):
    res = {}
    for run in (0, 1, 2):
        L = T = 0
        for short, ref in REFS.items():
            listed = Counter(el for (_, el) in prim.get((run, short), {}))
            L += sum(listed.values())
            for n in ref:
                if listed[n] > 0:
                    listed[n] -= 1
                    T += 1
        res[run] = {"listed": L, "correct": T, "fp": L - T, "precision": round(T / L, 3) if L else None, "recall": round(T / 109, 3)}
    return res


def correct_names(prim):
    out = {}
    for (run, short), d in prim.items():
        listed = Counter(el for (_, el) in d)
        got = set()
        for n in REFS.get(short, []):
            if listed[n] > 0:
                listed[n] -= 1
                got.add(n)
        out[(run, short)] = got
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    base = primaries({}, [])
    s0 = score(base)
    cmp = json.loads((AN / "compare_v5f.json").read_text(encoding="utf-8"))["B"]["runs"]["v5f"]
    ok = all((s0[r]["listed"], s0[r]["correct"]) == (cmp[r]["listed"], cmp[r]["correct"]) for r in (0, 1, 2))
    print("self-test (no change = compare_v5f):", "PASS" if ok else "FAIL", {r: (s0[r]["listed"], s0[r]["correct"]) for r in s0})
    if not ok or len(sys.argv) < 2:
        sys.exit(0 if ok else 1)
    J = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    per_judge = defaultdict(dict)        # (module, judge) -> {row_id: (new_label, rules)}
    newp = defaultdict(list)
    for j in J:
        for c in j.get("changes", []):
            if c.get("row_id") in KEY:
                per_judge[(j["module"], j["judge"])][c["row_id"]] = (c.get("new_label"), c.get("rule_ids", []))
        for n in j.get("new_primaries", []):
            newp[(j["module"], j["judge"])].append((int(str(n.get("run")).lstrip("r")), j["module"], n.get("entity"), n.get("element"), n.get("rule_ids", [])))
    mods = {m for m, _ in per_judge} | {m for m, _ in newp} | {j["module"] for j in J}
    out = {"base": s0}
    for mode in ("either", "both"):
        labels, rules_of = {}, {}
        extra = []
        for m in mods:
            a, b = per_judge.get((m, 1), {}), per_judge.get((m, 2), {})
            ids = (set(a) | set(b)) if mode == "either" else (set(a) & set(b))
            for rid in ids:
                lab = (a.get(rid) or b.get(rid))[0]
                labels[rid] = lab
                rules_of[rid] = sorted(set((a.get(rid, (None, []))[1]) + (b.get(rid, (None, []))[1])))
            na = {(x[0], x[2], x[3]) for x in newp.get((m, 1), [])}
            nb = {(x[0], x[2], x[3]) for x in newp.get((m, 2), [])}
            keep = (na | nb) if mode == "either" else (na & nb)
            for x in newp.get((m, 1), []) + newp.get((m, 2), []):
                if (x[0], x[2], x[3]) in keep and not any(e[:4] == x[:4] for e in extra):
                    extra.append(x)
        after = primaries(labels, extra)
        s1 = score(after)
        cb, ca = correct_names(base), correct_names(after)
        per_rule = defaultdict(Counter)
        lost, removed, gained, added = [], [], [], []
        for key in set(base) | set(after):
            run, short = key
            b_el = {el for (_, el) in base.get(key, {})}
            a_el = {el for (_, el) in after.get(key, {})}
            for el in sorted(b_el - a_el):
                rids = [rid for rid, k in KEY.items() if rid.startswith(short + ":") and k["run"] == run and el in k["elements"]
                        and k["label"] == "primary" and labels.get(rid, "primary") != "primary"]
                rr = sorted({x for rid in rids for x in rules_of.get(rid, [])})
                if el in cb.get(key, set()):
                    lost.append(f"r{run} {short}:{el} {rr}")
                    for x in rr:
                        per_rule[x]["correct lost"] += 1
                else:
                    removed.append(f"r{run} {short}:{el} {rr}")
                    for x in rr:
                        per_rule[x]["false positives removed"] += 1
            for el in sorted(a_el - b_el):
                rr = sorted({r for x in extra if x[0] == run and x[1] == short and x[3] == el for r in x[4]} |
                            {x for rid, k in KEY.items() if rid.startswith(short + ":") and k["run"] == run and el in k["elements"]
                             and labels.get(rid) == "primary" for x in rules_of.get(rid, [])})
                if el in ca.get(key, set()):
                    gained.append(f"r{run} {short}:{el} {rr}")
                    for x in rr:
                        per_rule[x]["correct gained"] += 1
                else:
                    added.append(f"r{run} {short}:{el} {rr}")
                    for x in rr:
                        per_rule[x]["false positives added"] += 1
        out[mode] = {"score": s1, "correct lost": lost, "false positives removed": removed, "correct gained": gained,
                     "false positives added": added, "per rule": {k: dict(v) for k, v in sorted(per_rule.items())}}
        print(f"\n== {mode} judge(s)")
        for r in (0, 1, 2):
            print(f"  r{r}: listed {s0[r]['listed']} -> {s1[r]['listed']}, correct {s0[r]['correct']} -> {s1[r]['correct']}, "
                  f"precision {s0[r]['precision']} -> {s1[r]['precision']}, recall {s0[r]['recall']} -> {s1[r]['recall']}")
        print(f"  correct lost {len(lost)}: {lost}")
        print(f"  correct gained {len(gained)}: {gained}")
        print(f"  false positives removed {len(removed)}, added {len(added)}")
        for k, v in sorted(per_rule.items()):
            print(f"    {k}: {dict(v)}")
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
