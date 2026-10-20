"""Code checks of the failure-cause workflow (v10c_fa_workflow.js, result saved as fa_result.json), then the tallies the
report uses. Read-only on facts.json, the packs and the prompt; writes fa_checked.json.

Checks per item (PLAN.md rules 1-5, set before the data):
  - coverage: every id in workflow_args.json "expected" has exactly one item, and no item has an unknown id;
  - prompt quotes: each quote is found in the named v10 file after collapsing whitespace and dropping markdown '*' and
    backquotes (exact words otherwise); an item with a failed quote is kept but marked, and not counted in a pattern;
  - reply quotes: found in that run's reply (pretty-printed pack file, or the parsed JSON string values joined);
  - rtl lines: each cited line number is one of rtl.txt's own line-number prefixes ("  18 | entity ..."; the file keeps
    the source's line numbers and drops comment and blank lines);
  - "missing" only with a basis: FN_MISSING_KEEP_RULE / FP_MISSING_BAR whose analyst basis is empty or "none" are
    re-labelled as reference convention (rule 1);
  - detector conflicts: FPs a v7 bar detector flags but the final category calls a missing bar (rule 5).
Pattern sizes: element-runs from facts.json (FP: runs listed; FN: runs missed = 3 - runs found); systematic when
element-runs / items >= 2 (rule 3).
Self-test: the quote matcher finds 3 hand-picked v10 sentences (exact, with a line break inside, with markdown) and
rejects an altered one; the line parser finds cpu_alu rtl line 18 ("entity neorv32_cpu_alu is", hand-read) and not 20.

  python -B check_items.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
PROMPT = LAB / "prompts" / "two_phase_v10"
MISSING = {"FN_MISSING_KEEP_RULE": "FN_REFERENCE_CONVENTION", "FP_MISSING_BAR": "FP_REFERENCE_CONVENTION"}


def norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[*`]", "", t)).strip().lower()


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def rtl_numbers(path):
    out = {}
    for l in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*(\d+) \|(.*)$", l)
        if m:
            out[int(m.group(1))] = m.group(2)
    return out


def selftest(ptext):
    p1 = ptext["phase1.md"]
    ok = norm("Reading a rule. Check its scope, then each criterion, then each exception it lists") in p1
    ok &= norm("Check its scope,\n then each   criterion") in p1
    ok &= norm("- **Reading a rule.** Check its scope") in p1 or norm("Reading a rule. Check its scope") in p1
    ok &= norm("Reading a rule. Check its scope, then every exception first") not in p1
    alu = rtl_numbers(LAB / "inputs" / "v1" / "heldout" / "neorv32_cpu_alu" / "rtl.txt")
    ok &= alu.get(18, "").strip() == "entity neorv32_cpu_alu is" and 20 not in alu
    return ok


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ptext = {f: norm((PROMPT / f).read_text(encoding="utf-8")) for f in ("common.md", "phase1.md", "phase2.md")}
    if not selftest(ptext):
        sys.exit("self-test FAILED: nothing reported")
    print("self-test (quote matcher, rtl line parser): PASS")
    F = json.loads((HERE / "facts.json").read_text(encoding="utf-8"))
    A = json.loads((HERE / "workflow_args.json").read_text(encoding="utf-8"))
    R = json.loads((HERE / "fa_result.json").read_text(encoding="utf-8"))
    R = R.get("result", R)
    expected = {i for v in A["expected"].values() for i in v}
    runs = {}
    for o, v in F["occurrences"].items():
        runs[o] = 3 - v["found in"]
    for n, v in F["false positives"].items():
        runs[n] = v["listed in"]
    replies, rtl_len = {}, {}
    for m in A["modules"]:
        d = HERE / "packs" / m
        for r in (0, 1, 2):
            for ph in (1, 2):
                raw = (d / f"r{r}_phase{ph}.json").read_text(encoding="utf-8")
                replies[(m, r, ph)] = norm(raw) + " || " + norm(" ".join(strings(json.loads(raw))))
        el = json.loads((d / "elements.json").read_text(encoding="utf-8"))
        rtl_len[m] = set(rtl_numbers(el["inputs"]["rtl.txt"]))
    analysis = {}
    for mod in R["modules"]:
        fin = {v["id"]: v for v in (mod.get("check") or {}).get("verdicts", [])}
        for it in mod["analysis"]["items"]:
            analysis[it["id"]] = (mod["module"], it, fin.get(it["id"]))
    got = Counter(i["id"] for mod in R["modules"] for i in mod["analysis"]["items"])
    cov = {"missing ids": sorted(expected - set(got)), "unknown ids": sorted(set(got) - expected),
           "duplicate ids": sorted(i for i, c in got.items() if c > 1),
           "items without a skeptic verdict": sorted(i for i, (_, _, v) in analysis.items() if v is None)}
    print("coverage:", {k: len(v) for k, v in cov.items()}, {k: v for k, v in cov.items() if v})
    out = {}
    for i, (m, it, v) in analysis.items():
        cat = (v or {}).get("final_category") or it["category"]
        bad_p = [q for q in it.get("prompt_quotes", []) if norm(q["quote"]) not in ptext.get(q["file"], "")]
        bad_v = [q for q in ((v or {}).get("prompt_quotes") or []) if norm(q["quote"]) not in ptext.get(q["file"], "")]
        bad_r = [q for q in it.get("reply_quotes", []) if norm(q["quote"]) not in replies.get((m, q.get("run"), q.get("phase")), "")]
        bad_l = [l for l in it.get("rtl_lines", []) if l not in rtl_len[m]]
        relabel = None
        if cat in MISSING and str(it.get("basis", "")).strip().lower() in ("", "none", "n/a"):
            relabel, cat = cat, MISSING[cat]
        det = F["false positives"].get(i, {}).get("runs", [])
        det_flag = any(x["v7 bar detectors"] for x in det)
        out[i] = {"module": m, "kind": it["kind"], "analyst category": it["category"],
                  "skeptic": (v or {}).get("verdict"), "final category": cat, "relabelled (no basis)": relabel,
                  "element-runs": runs.get(i, 0), "pattern": it["pattern"], "rule": it["rule"], "cause": it["cause"],
                  "basis": it.get("basis", ""), "level": it.get("level"), "skeptic reason": (v or {}).get("reason", ""),
                  "bad prompt quotes": bad_p, "bad skeptic quotes": bad_v, "bad reply quotes": bad_r,
                  "bad rtl lines": bad_l, "v7 detector flags it": det_flag,
                  "detector conflict": det_flag and cat == "FP_MISSING_BAR"}
    quote_fail = [i for i, x in out.items() if x["bad prompt quotes"] or x["bad reply quotes"] or x["bad rtl lines"]]
    print(f"items {len(out)}; skeptic corrected {sum(1 for x in out.values() if x['skeptic'] == 'corrected')}; "
          f"quote/line failures {len(quote_fail)}; relabelled missing->reference convention (no basis) "
          f"{sum(1 for x in out.values() if x['relabelled (no basis)'])}; detector conflicts "
          f"{[i for i, x in out.items() if x['detector conflict']]}")
    tally = defaultdict(lambda: [0, 0])
    for i, x in out.items():
        if i in quote_fail:
            continue
        tally[x["final category"]][0] += 1
        tally[x["final category"]][1] += x["element-runs"]
    print("final categories (items, element-runs), quote failures excluded:")
    for c, (n, e) in sorted(tally.items(), key=lambda kv: -kv[1][1]):
        print(f"  {c:26s} {n:3d} items  {e:3d} element-runs")
    pats = []
    syn = R.get("synthesis") or {}
    for p in syn.get("patterns", []):
        ids = [i for i in p["item_ids"] if i in out]
        ok_ids = [i for i in ids if i not in quote_fail]
        er = sum(out[i]["element-runs"] for i in ok_ids)
        cats = Counter(out[i]["final category"] for i in ok_ids)
        pats.append({**p, "items": len(ok_ids), "element-runs": er, "systematic": bool(ok_ids) and er / len(ok_ids) >= 2,
                     "final categories": dict(cats), "ids not in items": [i for i in p["item_ids"] if i not in out],
                     "ids with quote failures": [i for i in ids if i in quote_fail]})
    assigned = Counter(i for p in syn.get("patterns", []) for i in p["item_ids"])
    print(f"synthesis: {len(pats)} patterns; items in no pattern {sorted(set(out) - set(assigned))}; "
          f"items in 2+ patterns {sorted(i for i, c in assigned.items() if c > 1)}")
    (HERE / "fa_checked.json").write_text(json.dumps({"coverage": cov, "items": out, "quote failures": quote_fail,
                                                      "tally": dict(tally), "patterns": pats,
                                                      "tp_patterns": syn.get("tp_patterns", []),
                                                      "general": syn.get("general", [])}, indent=1, ensure_ascii=False),
                                          encoding="utf-8")
    print("wrote fa_checked.json")


if __name__ == "__main__":
    main()
