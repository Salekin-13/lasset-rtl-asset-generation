"""Code checks of the rule-map / Phase-conflict workflow (workflow_result.json, wf_32bef4b5-0ff) before anything is
reported or used. Writes text_conflicts.json and rule_texts_extra.json, then rebuilds rule_texts.json.

1. Phase 1 / Phase 2 divergences: each claimed divergence keeps its skeptic verdict (confirmed / corrected / refuted);
   its two quotes must be verbatim (whitespace and quote marks normalised; a quote may join pieces with "...") in the
   v9 phase1.md (Phase 1 quote; also common.md 2.6-2.7) and phase2.md (Phase 2 quote); a quote may be "-" or
   empty for a "missing in" kind. Kept = not refuted AND quotes verbatim.
2. The revised Operation selectors wording (P1-22R): the reviser's trailing "[Scope of this replacement: ...]" note is
   cut off (it is an annotation, not prompt text); both texts must pass meta_tools.check_prompt (no corpus identifier,
   no numeric emission hint, no comment-reading instruction), the checker that check_lab_prompt uses.
Self-test: a quote taken from the pack passes, the same quote with one word changed fails; a planted identifier in a
copy of the revised text is caught.

  python check_text_results.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
ROOT = LAB.parents[2]
for p in (LAB, ROOT / "src", ROOT / "assetgen_meta", ROOT / "bahavioral_patterns_of_assets"):
    sys.path.insert(0, str(p))
import labkit as K  # noqa: E402
import meta_tools as mt  # noqa: E402
import isolation as ISO  # noqa: E402


def norm(s):
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace("...", " ").replace("…", " ")
    return " ".join(s.split()).strip(" .\"'")


def verbatim(q, hay):
    """True when every quoted piece is in hay. The agents wrote quotes as plain text or as 'S049: "..."' with several
    quoted pieces and their own words around them: when the text has double-quoted segments, only those are checked;
    otherwise sentence labels and [bracketed notes] are dropped. "NONE ..." (no sentence exists) is no quote."""
    raw = (q or "").replace("“", '"').replace("”", '"')
    if not norm(raw) or norm(raw).lower().startswith(("none", "-", "n/a", "(none")):
        return None
    segs = re.findall(r'"([^"]{8,})"', raw)
    if not segs:
        segs = [re.sub(r"\[[^\]]*\]|\bS\d{3}\b:?|\bP1-\d\d\b:?", " ", raw)]
    pieces = [p for s in segs for p in re.split(r"\.\.\.|…", s) if len(norm(p)) >= 6]
    return all(norm(p) in hay for p in pieces) if pieces else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    r = json.loads((HERE / "workflow_result.json").read_text(encoding="utf-8"))
    idx = json.loads((HERE / "pack" / "index.json").read_text(encoding="utf-8"))
    v9 = LAB / "prompts" / "two_phase_v9"
    # the plain prompt text (no S-number labels between sentences), so a quote may span sentences
    p1 = norm((v9 / "phase1.md").read_text(encoding="utf-8"))
    p2 = norm((v9 / "phase2.md").read_text(encoding="utf-8"))
    com = norm((HERE / "pack" / "common_26_27.md").read_text(encoding="utf-8"))
    names = K.corpus_names() | mt.corpus_names(str(ROOT))
    # self-test
    good = "Precedence. A rule's bar is its sentence saying information is not a conceptual asset"
    ok = verbatim(good, p1) is True and verbatim(good.replace("sentence", "clause"), p1) is False
    rv = r["operation_selectors"]["revised"]
    p2_os = re.split(r"\n\s*\[Scope of this replacement", rv["phase2_text"])[0].strip()
    p1_os = rv["phase1_text"].strip()
    plant = mt.check_prompt(p1_os + " Report at most 20 signals such as " + sorted(names)[0], names, "plant")
    ok &= len(plant["problems"]) >= 2
    print("self-test (verbatim check, planted identifier and numeric hint caught):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    kept, tally, by_rule = [], Counter(), defaultdict(Counter)
    for u in r["compared"]:
        ver = {v["id"]: v for v in (u.get("verification") or [])}
        for d in u.get("divergences", []):
            v = ver.get(d["id"], {"verdict": "not verified", "note": ""})
            q1 = verbatim(d["p1_quote"], p1 + " " + com)
            q2 = verbatim(d["p2_quote"], p2)
            quotes_ok = q1 is not False and q2 is not False
            status = "refuted" if v["verdict"] == "refuted" else ("kept" if quotes_ok else "quote not verbatim")
            tally[status] += 1
            by_rule[u["unit"]][status] += 1
            if status == "kept":
                kept.append({"unit": u["unit"], **d, "skeptic": v["verdict"], "skeptic note": v["note"]})
    titles = {k: v["title"] for k, v in json.loads((HERE / "pack" / "index.json").read_text(encoding="utf-8"))["p1"].items()}
    out = {"tally": dict(tally), "per unit": {k: dict(v) for k, v in by_rule.items()}, "kept divergences": kept}
    (HERE / "text_conflicts.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"divergences: {dict(tally)}")
    sev = Counter((d["severity"], d["kind"]) for d in kept)
    print("kept by severity and kind:", dict(sev.most_common()))
    per = Counter(d["unit"] for d in kept)
    print("kept per unit:", {f"{k} {titles.get(k, '')}".strip(): v for k, v in per.most_common()})
    # the revised Operation selectors wording
    probs = {ph: mt.check_prompt(t, names, ph)["problems"] for ph, t in (("P1", p1_os), ("P2", p2_os))}
    print("revised Operation selectors: prompt check", {k: (v or "clean") for k, v in probs.items()},
          f"| words P1 {len(p1_os.split())}, P2 {len(p2_os.split())} (v9: P1 {len(titles and json.loads((HERE / 'pack' / 'index.json').read_text(encoding='utf-8'))['p1']['P1-22']['text'].split())})")
    if any(probs.values()):
        sys.exit("revised wording fails the prompt check: not added to the isolation run")
    (HERE / "rule_texts_extra.json").write_text(json.dumps({"P1-22R": {"title": "Operation selectors (revised scope)",
                                                                        "P1": p1_os, "P2": p2_os}}, indent=1, ensure_ascii=False), encoding="utf-8")
    ISO.build()


if __name__ == "__main__":
    main()
