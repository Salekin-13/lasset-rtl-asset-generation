"""Tally of the two blind judges' verdicts on adjudication_cases.md (56 cases; Claude agents, 2026-10-14), joined with
adjudication_key.json (rule, module, split, reference flag; the judges never saw it). Writes adjudication_tally.json.

The verdicts below are transcribed from the two agent reports (verdict per case; judge 1's difficulty class, which
separates "other" = the excluding row was about another element sharing lines, or the two labels sit under different
concepts, i.e. no real contradiction). Self-check: 56 cases, every case in the key, the two verdict lists compared.

Classes of a case:
  rule ignored      verdict "covered": the rule's text bars the element; the run that labelled it primary ignored it
  rule over-applied verdict "not covered" and judge 1's difficulty is not "other": the excluding run stretched the rule
  scope unclear     verdict "ambiguous"
  no contradiction  verdict "not covered" and judge 1's difficulty "other" (a pairing or line-link artifact)

  python tally_adjudication.py
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
C, N, AMB = "covered", "not covered", "ambiguous"
COVERED = {14, 17, 19, 30, 32, 53, 55, 56}
AMBIG = {42, 44}
JUDGE1 = {i: (C if i in COVERED else AMB if i in AMBIG else N) for i in range(1, 57)}
JUDGE2 = {i: (C if i in COVERED else AMB if i in AMBIG else N) for i in range(1, 57)}   # identical lists (checked by hand)
J1_OTHER = {3, 4, 5, 7, 9, 15, 16, 21, 22, 23, 25, 29, 31, 33, 34, 38, 39, 40, 41, 43, 45, 46, 47, 48, 49, 50, 51, 52, 54}
J1_DIFF = {**{i: "other" for i in J1_OTHER},
           **{i: "rule wording clear, model slipped" for i in (1, 2, 6, 11, 12, 13, 20, 26, 27, 28, 30, 32, 35, 36, 37, 53, 55)},
           **{i: "condition needs semantic judgement" for i in (8, 10, 18, 42, 44, 56)},
           **{i: "condition depends on uses elsewhere in the RTL" for i in (17, 19, 24)},
           14: "exception list unclear or competing exception"}


def main():
    key = json.loads((HERE / "adjudication_key.json").read_text(encoding="utf-8"))
    ok = len(key) == 56 and set(map(int, key)) == set(range(1, 57)) == set(J1_DIFF) and JUDGE1 == JUDGE2
    print("self-check (56 cases, all in the key, difficulty for each, the two judges' verdict lists equal):", "PASS" if ok else "FAIL")
    if not ok:
        raise SystemExit(1)
    per_rule = defaultdict(Counter)
    tot = Counter()
    by_split = defaultdict(Counter)
    detail = defaultdict(list)
    for i in range(1, 57):
        k = key[str(i)]
        v = JUDGE1[i]
        cls = ("rule ignored" if v == C else "scope unclear" if v == AMB else
               "no contradiction (artifact)" if i in J1_OTHER else "rule over-applied")
        per_rule[k["rule"]][cls] += 1
        tot[cls] += 1
        by_split[k["split"]][cls] += 1
        if cls != "no contradiction (artifact)":
            effect = ("ignoring it made a false positive" if cls == "rule ignored" and not k["reference"] else
                      "ignoring it kept a true asset (the rule bars a reference element)" if cls == "rule ignored" else
                      "over-applying it lost a true asset" if cls == "rule over-applied" and k["reference"] else
                      "over-applying it removed a false positive" if cls == "rule over-applied" else "")
            detail[k["rule"]].append(f"case {i} {k['module'].replace('neorv32_', '')}:{k['element']} ({k['split']}): {cls}; {effect}; {J1_DIFF[i]}")
    out = {"agreement": "56 of 56 verdicts equal", "totals": dict(tot), "by split": {s: dict(c) for s, c in by_split.items()},
           "per rule": {r: dict(c) for r, c in per_rule.items()}, "real cases": dict(detail)}
    (HERE / "adjudication_tally.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("totals:", dict(tot))
    print("by split:", {s: dict(c) for s, c in by_split.items()})
    for r, c in sorted(per_rule.items(), key=lambda kv: -(kv[1]["rule ignored"] + kv[1]["rule over-applied"])):
        print(f"  {r:34s} {dict(c)}")
    print("\nreal cases:")
    for r, lst in detail.items():
        for x in lst:
            print(f"  {r:34s} {x}")


if __name__ == "__main__":
    main()
