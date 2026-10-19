"""Final pattern table of the v10 Claude failure analysis, counted by code from fa_checked.json (check_items.py).

The synthesis agent named each pattern's cause ("attributable_to"), but PLAN.md rule 1 makes the skeptic's final
category per item decide. So each synthesis pattern is split by its items' final class, and every count below is
element-runs from facts.json (FN: runs missed; FP: runs listed). Items with a failed quote are listed apart (rule 2).
Writes patterns_final.json.

Self-test: class totals equal the per-category tally of check_items.py, and FN + FP element-runs plus the quote-failure
items equal 68 + 174 (facts.json pooled FN and FP).

  python -B patterns_final.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLASS = {"FP_REFERENCE_CONVENTION": "reference convention", "FN_REFERENCE_CONVENTION": "reference convention",
         "FP_NAMING": "naming granularity", "FN_NAMING": "naming granularity",
         "FP_BAR_UNCLEAR": "unclear bar", "FN_BAR_UNCLEAR": "unclear bar",
         "FN_BAR_TEXT_COVERS": "bar covers a reference element (too broad)",
         "FN_BAR_OVERAPPLIED": "bar applied beyond its text", "FP_BAR_BROKEN": "bar broken (compliance)",
         "FP_MISSING_BAR": "missing bar", "FN_MISSING_KEEP_RULE": "missing rule",
         "FN_MERGED_AWAY": "merged away in Phase 1", "FN_RUN_NOISE": "run noise", "FP_RUN_NOISE": "run noise",
         "FN_OTHER": "other", "FP_OTHER": "other"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    C = json.loads((HERE / "fa_checked.json").read_text(encoding="utf-8"))
    F = json.loads((HERE / "facts.json").read_text(encoding="utf-8"))
    I, bad = C["items"], set(C["quote failures"])
    tot = defaultdict(lambda: Counter())
    for i, x in I.items():
        if i in bad:
            continue
        tot[(x["kind"], CLASS[x["final category"]])]["items"] += 1
        tot[(x["kind"], CLASS[x["final category"]])]["element-runs"] += x["element-runs"]
    # self-test
    ok = all(sum(v["element-runs"] for (k, c), v in tot.items() if c == cl and k == kd)
             == sum(C["tally"][cat][1] for cat in C["tally"] if CLASS[cat] == cl and cat.startswith(kd))
             for (kd, cl) in tot)
    fn = sum(v["element-runs"] for (k, _), v in tot.items() if k == "FN") + sum(I[i]["element-runs"] for i in bad if I[i]["kind"] == "FN")
    fp = sum(v["element-runs"] for (k, _), v in tot.items() if k == "FP") + sum(I[i]["element-runs"] for i in bad if I[i]["kind"] == "FP")
    ok &= fn == F["pooled"]["FN"] and fp == F["pooled"]["FP"]
    print(f"self-test: {'PASS' if ok else 'FAIL'} (FN element-runs {fn} = {F['pooled']['FN']}, FP {fp} = {F['pooled']['FP']})")
    if not ok:
        sys.exit("nothing written")
    print("\nBy final class (element-runs; FN of", F["pooled"]["FN"], "missed runs, FP of", F["pooled"]["FP"], "false-positive runs):")
    for kd in ("FN", "FP"):
        for (k, cl), v in sorted(tot.items(), key=lambda kv: -kv[1]["element-runs"]):
            if k == kd:
                print(f"  {kd} {cl:44s} {v['items']:3d} items {v['element-runs']:4d} element-runs")
    rows = []
    for p in C["patterns"]:
        by = defaultdict(list)
        for i in p["item_ids"]:
            if i in I and i not in bad:
                by[CLASS[I[i]["final category"]]].append(i)
        for cl, ids in by.items():
            er = sum(I[i]["element-runs"] for i in ids)
            rows.append({"pattern": p["name"], "kind": p["kind"], "class (final categories)": cl,
                         "synthesis said": p["attributable_to"], "items": ids, "element-runs": er,
                         "systematic": er / len(ids) >= 2, "rules": p["rules"], "cause": p["cause"], "basis": p["basis"],
                         "fix direction": p["fix_direction"], "risk": p["risk"]})
    rows.sort(key=lambda r: (r["kind"], -r["element-runs"]))
    print("\nPatterns split by final class:")
    for r in rows:
        flag = "" if r["class (final categories)"].split(" (")[0] in r["synthesis said"] or r["synthesis said"] in r["class (final categories)"] else f"   [synthesis said: {r['synthesis said']}]"
        print(f"  [{r['kind']}] {r['element-runs']:3d} er {len(r['items']):2d} it {'SYST' if r['systematic'] else 'int '} "
              f"{r['class (final categories)']:30s} {r['pattern'][:80]}{flag}")
    print("\nQuote failures (not in any count above):", {i: (I[i]["final category"], I[i]["element-runs"]) for i in bad})
    (HERE / "patterns_final.json").write_text(json.dumps({"totals": {f"{k} {c}": dict(v) for (k, c), v in tot.items()},
                                                          "patterns": rows, "quote failures": sorted(bad)},
                                                         indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
