"""Score a blind boundary test of v6 rule text on two_phase_v5g's stored replies (r0-r2, 15 modules).

Input: JSON list of judge answers {"module": short, "judge": 1|2,
  "concept_changes": [{"run": "r0", "concept_id": "C3", "action": "drop" | "trim", "elements": [names, for trim], "rule_ids"}],
  "changes": [{"row_id", "new_label", "rule_ids"}],                (row ids as in views_blind/ and boundary_key.json)
  "new_primaries": [{"run": "r0", "element", "entity", "rule_ids"}]}.
A dropped concept takes every Phase 2 row of its walk out of the primaries; a trim takes out the rows of the named
elements in that walk; row changes and new primaries apply after. Judges never saw which rows the reference lists.
Per run, for "either judge" and "both judges": listed, correct, false positives, precision, recall (of 109), exact
(names equal, each reference entry used once, one listing per (entity, element)); per rule: correct lost, false
positives removed, correct gained, false positives added. Self-tests: no change reproduces compare_v5g.json; a planted
drop of one concept counts exactly its correct and false elements.

  python score_v6.py <judges.json> [out.json]
"""
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent
LAB = AN.parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB.parents[2] / "src"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402

KEY = json.loads((HERE / "boundary_key.json").read_text(encoding="utf-8"))


def _refs():
    import eval_assets as ea
    with CH.at_root():
        refs = ea.load_refs()["gt"]
    out = {}
    for m in CH.tuning_modules():
        names = {n for (_, n) in CH.closed_names(m)}
        out[m.replace("neorv32_", "")] = [n for n, _ in refs[m] if n in names]
    return out


REFS = _refs()


def primaries(labels, extra):
    out = defaultdict(dict)
    for rid, k in KEY.items():
        if labels.get(rid, k["label"]) == "primary":
            short = rid.split(":")[0]
            for el in k["elements"]:
                if isinstance(el, str) and el:
                    out[(k["run"], short)].setdefault((k["entity"], el), [])
    for run, short, ent, el, rules in extra:
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
    for key, d in prim.items():
        listed = Counter(el for (_, el) in d)
        got = set()
        for n in REFS.get(key[1], []):
            if listed[n] > 0:
                listed[n] -= 1
                got.add(n)
        out[key] = got
    return out


def labels_from(judge):
    """row id -> (new label, rule ids) from one judge's concept and row changes."""
    lab = {}
    m = judge["module"]
    for c in judge.get("concept_changes", []):
        run = int(str(c.get("run")).lstrip("r"))
        for rid, k in KEY.items():
            if rid.startswith(m + ":") and k["run"] == run and k["concept"] == c.get("concept_id"):
                if c.get("action") == "drop" or set(k["elements"]) & set(c.get("elements") or []):
                    lab[rid] = ("not reported", list(c.get("rule_ids") or []))
    for c in judge.get("changes", []):
        if c.get("row_id") in KEY:
            lab[c["row_id"]] = (c.get("new_label"), list(c.get("rule_ids") or []))
    return lab


def evaluate(J, mode):
    per_judge = {(j["module"], j["judge"]): labels_from(j) for j in J}
    newp = {(j["module"], j["judge"]): [(int(str(n.get("run")).lstrip("r")), j["module"], n.get("entity"), n.get("element"), list(n.get("rule_ids") or []))
                                         for n in j.get("new_primaries", [])] for j in J}
    mods = {j["module"] for j in J}
    labels, rules_of, extra = {}, {}, []
    for m in mods:
        a, b = per_judge.get((m, 1), {}), per_judge.get((m, 2), {})
        ids = (set(a) | set(b)) if mode == "either" else (set(a) & set(b))
        for rid in ids:
            labels[rid] = (a.get(rid) or b.get(rid))[0]
            rules_of[rid] = sorted(set(a.get(rid, (None, []))[1]) | set(b.get(rid, (None, []))[1]))
        na = {x[:4] for x in newp.get((m, 1), [])}
        nb = {x[:4] for x in newp.get((m, 2), [])}
        keep = (na | nb) if mode == "either" else (na & nb)
        for x in newp.get((m, 1), []) + newp.get((m, 2), []):
            if x[:4] in keep and not any(e[:4] == x[:4] for e in extra):
                extra.append(x)
    base, after = primaries({}, []), primaries(labels, extra)
    cb, ca = correct_names(base), correct_names(after)
    per_rule = defaultdict(Counter)
    lists = {"correct lost": [], "false positives removed": [], "correct gained": [], "false positives added": []}
    for key in set(base) | set(after):
        run, short = key
        b_el = {el for (_, el) in base.get(key, {})}
        a_el = {el for (_, el) in after.get(key, {})}
        for el in sorted(b_el - a_el):
            rr = sorted({x for rid, k in KEY.items() if rid.startswith(short + ":") and k["run"] == run and el in k["elements"]
                         and labels.get(rid, k["label"]) != "primary" and k["label"] == "primary" for x in rules_of.get(rid, [])})
            kind = "correct lost" if el in cb.get(key, set()) else "false positives removed"
            lists[kind].append(f"r{run} {short}:{el} {rr}")
            for x in rr:
                per_rule[x][kind] += 1
        for el in sorted(a_el - b_el):
            rr = sorted({r for x in extra if x[0] == run and x[1] == short and x[3] == el for r in x[4]} |
                        {x for rid, k in KEY.items() if rid.startswith(short + ":") and k["run"] == run and el in k["elements"]
                         and labels.get(rid) == "primary" for x in rules_of.get(rid, [])})
            kind = "correct gained" if el in ca.get(key, set()) else "false positives added"
            lists[kind].append(f"r{run} {short}:{el} {rr}")
            for x in rr:
                per_rule[x][kind] += 1
    return {"score": score(after), **lists, "per rule": {k: dict(v) for k, v in sorted(per_rule.items())}}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    s0 = score(primaries({}, []))
    cmp = json.loads((AN / "compare_v5g.json").read_text(encoding="utf-8"))["runs"]
    ok = all((s0[r]["listed"], s0[r]["correct"]) == (cmp[f"v5g r{r}"]["listed"], cmp[f"v5g r{r}"]["correct"]) for r in (0, 1, 2))
    # planted: drop one concept of wdt r1 (both judges) and check the counts by hand from the key
    rid0 = next(r for r, k in KEY.items() if r.startswith("wdt:r1:") and k["label"] == "primary")
    cid = KEY[rid0]["concept"]
    J = [{"module": "wdt", "judge": j, "concept_changes": [{"run": "r1", "concept_id": cid, "action": "drop", "rule_ids": ["T"]}]} for j in (1, 2)]
    res = evaluate(J, "both")
    els_in = {e for r, k in KEY.items() if r.startswith("wdt:r1:") and k["concept"] == cid and k["label"] == "primary" for e in k["elements"]}
    els_else = {e for r, k in KEY.items() if r.startswith("wdt:r1:") and k["concept"] != cid and k["label"] == "primary" for e in k["elements"]}
    gone = els_in - els_else
    corr = correct_names(primaries({}, [])).get((1, "wdt"), set())
    ok2 = (len(res["correct lost"]), len(res["false positives removed"])) == (len(gone & corr), len(gone - corr))
    print("self-test (no change = compare_v5g):", "PASS" if ok else "FAIL", {r: (s0[r]["listed"], s0[r]["correct"]) for r in s0},
          "| planted concept drop:", "PASS" if ok2 else "FAIL", f"(wdt r1 {cid}: {len(gone & corr)} correct, {len(gone - corr)} false)")
    if not (ok and ok2):
        sys.exit(1)
    if len(sys.argv) < 2:
        return
    J = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = {"base": s0}
    for mode in ("either", "both"):
        res = evaluate(J, mode)
        out[mode] = res
        print(f"\n== {mode} judge(s)")
        for r in (0, 1, 2):
            s1 = res["score"][r]
            print(f"  r{r}: listed {s0[r]['listed']} -> {s1['listed']}, correct {s0[r]['correct']} -> {s1['correct']}, "
                  f"precision {s0[r]['precision']} -> {s1['precision']}, recall {s0[r]['recall']} -> {s1['recall']}")
        for k in ("correct lost", "correct gained"):
            print(f"  {k} {len(res[k])}: {res[k]}")
        print(f"  false positives removed {len(res['false positives removed'])}, added {len(res['false positives added'])}")
        for k, v in res["per rule"].items():
            print(f"    {k}: {v}")
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
