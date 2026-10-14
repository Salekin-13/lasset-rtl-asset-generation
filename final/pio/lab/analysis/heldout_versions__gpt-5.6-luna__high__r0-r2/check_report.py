"""Code checks of the written report (HELDOUT_PROMPT_DIAGNOSIS.md) against the code results.

  1. every check id (u<NN>-<k>) in the report exists in verify/merged.json;
  2. in table rows, the Status cell matches the code status of every check id in the row (kept / contested), and no
     refuted claim appears in a table row;
  3. the Scores table: for each version row, the TP / FP / FN / precision / recall numbers equal compare_versions.json
     (tuning and held-out), whatever the column order (each number must be one of that version's values);
  4. every cited prompt location "<version> <file>.md:<line>" exists and is not empty, and when the same table cell
     names one Phase 1 rule title (attribute.RULE_KEYS) and cites one location, that line starts with "- <title>.".
Self-test: a small made-up report with one right and one wrong item of each kind gives exactly the expected failures.

  python check_report.py [report.md]
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import attribute as A  # noqa: E402

LAB = A.LAB
LOC = re.compile(r"\b(v\d\w*)\s+(common|phase1|phase2)\.md:(\d+)")


def load():
    merged = {m["check id"]: m["status"] for m in json.loads((HERE / "verify" / "merged.json").read_text(encoding="utf-8"))}
    cv = json.loads((HERE / "compare_versions.json").read_text(encoding="utf-8"))
    return merged, cv


def check(text, merged, cv):
    fails = []
    ids = set(re.findall(r"\bu\d\d-\d+\b", text))
    for i in sorted(ids - set(merged)):
        fails.append(f"unknown check id {i}")
    rule_titles = [r for r in A.RULE_KEYS if " (" not in r]
    in_scores = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_scores = line.strip().lower().startswith("## scores")
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rid = re.findall(r"\bu\d\d-\d+\b", line)
        if rid:
            st = {merged[i] for i in rid if i in merged}            # unknown ids are reported above
            if "refuted" in st:
                fails.append(f"refuted claim in a table row: {[i for i in rid if merged.get(i) == 'refuted']}")
            low = line.lower()
            said = "contested" if "contested" in low else ("kept" if re.search(r"\bkept\b", low) else None)
            if said and st - {said, "refuted"}:
                fails.append(f"status cell '{said}' but code status {sorted(x for x in st if x)} for {rid}")
        for c in cells:
            for v, f, n in LOC.findall(c):
                p = LAB / "prompts" / f"two_phase_{v}" / f"{f}.md"
                if not p.exists():
                    fails.append(f"no file for {v} {f}.md:{n}")
                    continue
                L = p.read_text(encoding="utf-8").splitlines()
                n = int(n)
                if not (0 < n <= len(L)) or not L[n - 1].strip():
                    fails.append(f"{v} {f}.md:{n} does not exist or is empty")
                    continue
                if f == "phase1" and len(LOC.findall(c)) == 1:      # unambiguous: one location, one rule named
                    named = [t for t in rule_titles if t.lower() in c.lower()]
                    if len(named) == 1 and not L[n - 1].startswith(f"- {named[0]}."):
                        fails.append(f"{v} phase1.md:{n} is not the '{named[0]}' rule (line starts '{L[n - 1][:40]}')")
        if in_scores and cells and re.fullmatch(r"\**v\d\w*\**", cells[0]):
            v = cells[0].strip("*")
            if v not in cv["versions"]:
                continue
            want = set()
            for s in ("tuning", "held-out"):
                z = cv["versions"][v][s]
                want |= {str(z["TP"]), str(z["FP"]), str(z["FN"]), f"{z['pooled precision'][2]:.3f}", f"{z['pooled recall'][2]:.3f}"}
            nums = re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])", " ".join(cells[1:]))
            bad = [x for x in nums if x not in want and not (x.startswith("0.") and f"{float(x):.3f}" in want)]
            if bad:
                fails.append(f"scores row {v}: numbers not in compare_versions.json: {bad}")
    return fails


def selftest(merged, cv):
    kept = next(i for i, s in merged.items() if s == "kept")
    refd = next(i for i, s in merged.items() if s == "refuted")
    z = cv["versions"]["v7"]["held-out"]
    t = cv["versions"]["v7"]["tuning"]
    good_scores = f"| v7 | {t['TP']} | {t['FP']} | {t['FN']} | {t['pooled precision'][2]:.3f} | {t['pooled recall'][2]:.3f} | {z['TP']} | {z['FP']} | {z['FN']} | {z['pooled precision'][2]:.3f} | {z['pooled recall'][2]:.3f} |"
    rep = "\n".join([
        "## Scores", "| Version | a |", good_scores, f"| v8 | 9999 |",
        "## S1", f"| p | v7 phase1.md:43, Access command fields | kept | {kept} |",
        f"| p | v7 phase1.md:26, Access command fields | kept | {kept} |",
        f"| p | v7 phase1.md:26 Pacing pulses and v7 phase1.md:43 Access command fields | kept | {kept} |",
        f"| p | v7 phase1.md:43 | contested | {kept} |",
        f"| p | v7 phase1.md:43 | kept | {refd} |",
        "| p | v7 phase1.md:9999 | kept | u99-9 |",
    ])
    f = check(rep, merged, cv)
    want = ["unknown check id u99-9", "scores row v8", "is not the 'Access command fields' rule", "status cell 'contested'",
            "refuted claim in a table row", "phase1.md:9999 does not exist"]
    ok = all(any(w in x for x in f) for w in want) and len(f) == len(want)
    print("self-test (each planted error found, nothing else):", "PASS" if ok else f"FAIL {f}")
    return ok


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    merged, cv = load()
    if not selftest(merged, cv):
        sys.exit(1)
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "HELDOUT_PROMPT_DIAGNOSIS.md"
    text = p.read_text(encoding="utf-8")
    fails = check(text, merged, cv)
    ids = set(re.findall(r"\bu\d\d-\d+\b", text))
    print(f"report: {len(ids)} check ids cited; kept claims cited {sum(1 for i in ids if merged.get(i) == 'kept')} of "
          f"{sum(1 for s in merged.values() if s == 'kept')}, contested {sum(1 for i in ids if merged.get(i) == 'contested')} of "
          f"{sum(1 for s in merged.values() if s == 'contested')}, refuted {sum(1 for i in ids if merged.get(i) == 'refuted')} of "
          f"{sum(1 for s in merged.values() if s == 'refuted')}")
    print(f"failures: {len(fails)}")
    for x in fails:
        print("  -", x)


if __name__ == "__main__":
    main()
