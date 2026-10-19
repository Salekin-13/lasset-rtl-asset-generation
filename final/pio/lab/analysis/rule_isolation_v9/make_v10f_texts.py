"""Rule texts and contexts for the facts-first test ("v10f"; user 2026-10-15: "yes" to testing fixes 1-5 on the four
worst over-appliers: Sequencing state, Port options, Clocks and resets, Slices).

Reads prompt_builds/v10f/{A,B}_final.json (the rewrite workflow's final texts) and writes:
  rule_texts_v10f.json   {rule id: {"title", "P1": structured Phase 1 block, "P2": structured Phase 2 block plus the
                          rule's Phase 2 sentences kept in place}}
  context_p1_v10f.md / context_p2_v10f.md   the v9 contexts with the v10f shared procedure (FACTS_SPEC.md): check the
                          scope, then each criterion, writing the RTL fact for each, listing every assignment or use for
                          "only" / "every" / "one element"; the v10 clause "a criterion ... does not show is not met" is gone
Checks: the four rules, each with the phases its v9 wording had; every text passes the project prompt check.

  python -B make_v10f_texts.py
  python -B make_v10f_texts.py v10fo   (2026-10-16, G3: the adopted wordings for the old-reply-format test)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
ROOT = LAB.parents[2]
for p in (LAB, ROOT / "src", ROOT / "assetgen_meta", ROOT / "bahavioral_patterns_of_assets"):
    sys.path.insert(0, str(p))
import labkit as K  # noqa: E402
import meta_tools as mt  # noqa: E402

F = LAB / "analysis" / "prompt_builds" / "v10f"
RULES = ["P1-15", "P1-18", "P1-02", "P1-09"]
PROC = ("Check its scope, then each criterion, in that order, writing the RTL fact for each; where a criterion says "
        "\"only\", \"every\" or \"one element\", list every assignment or use. Its outcome follows only when the scope and "
        "every criterion hold for that element.")
PROC_P1 = "- Reading a rule. " + PROC
PROC_P2 = "Reading a rule below: " + PROC[0].lower() + PROC[1:]
# 2026-10-16 (user "do the g3 test"): "v10fo" = the four adopted wordings (prompt_builds/v10/current_rules.json) in the
# OLD reply format. Each text must equal the one its facts-format test read, so only the reply format differs.
TESTED_IN = {"P1-15": "v10f", "P1-18": "v10f", "P1-02": "v10f2", "P1-09": "v10f3"}


def main(variant="v10f"):
    """variant "v10f2" (2026-10-15, user "apply" G2): Slices and Clocks and resets from prompt_builds/v10f/C_final.json
    -> rule_texts_v10f2.json; the v10f contexts are reused unchanged.
    variant "v10fo" (2026-10-16, G3): the adopted wordings from current_rules.json -> rule_texts_v10fo.json; stops unless
    every text equals the text stored for its facts-format test (TESTED_IN)."""
    sys.stdout.reconfigure(encoding="utf-8")
    v9 = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    fin = {}
    if variant == "v10fo":
        cur_dir = LAB / "analysis" / "prompt_builds" / "v10"
        cur = {k: v for k, v in json.loads((cur_dir / "current_rules.json").read_text(encoding="utf-8")).items()
               if not k.startswith("_")}
        if sorted(cur) != sorted(TESTED_IN):
            print(f"PROBLEM adopted rules {sorted(cur)} are not the four facts-first rules {sorted(TESTED_IN)}")
            sys.exit(1)
        for rid, rel in cur.items():                   # one rule per file: C_final.json also holds an older Slices
            fin[rid] = json.loads((cur_dir / rel).read_text(encoding="utf-8"))[rid]
    for g in {"v10f": ("A", "B"), "v10f2": ("C",), "v10f3": ("D",),    # v10f3: Slices only (2026-10-15, "ok")
              "v10f4": ("E",), "v10fo": ()}[variant]:   # v10f4: v10f3 Slices without "(never the whole element)" (2026-10-15, "implement")
        fin.update(json.loads((F / f"{g}_final.json").read_text(encoding="utf-8")))
    rules = RULES if variant == "v10f" else [r for r in RULES if r in fin]
    names = K.corpus_names() | mt.corpus_names(str(ROOT))
    out, bad = {}, []
    for rid in rules:
        d = fin.get(rid)
        if d is None:
            bad.append(f"{rid}: no final text")
            continue
        t = {"title": v9[rid]["title"], "P1": None, "P2": None}
        if v9[rid].get("P1"):
            t["P1"] = (d.get("P1_structured") or "").strip()
        if v9[rid].get("P2"):                         # sentences kept in place come first (they stand before the
            t["P2"] = "\n".join([s.strip() for s in (d.get("P2_in_place") or {}).values()] +   # block in the prompt;
                                [(d.get("P2_structured") or "").strip()]).strip()            # S012 says "defined below")
        for ph in ("P1", "P2"):
            if bool(v9[rid].get(ph)) != bool(t[ph]):
                bad.append(f"{rid} {ph}: phase missing or extra")
            if t[ph]:
                pr = mt.check_prompt(t[ph], names, f"{rid} {ph}")["problems"]
                if pr:
                    bad.append(f"{rid} {ph}: prompt check {pr}")
        out[rid] = t
    if variant == "v10fo":                             # same words as the facts-format test of each rule
        for rid, v in TESTED_IN.items():
            tested = json.loads((HERE / f"rule_texts_{v}.json").read_text(encoding="utf-8")).get(rid)
            if out.get(rid) != tested:
                bad.append(f"{rid}: adopted text differs from the text the {v} test read")
    for b in bad:
        print("PROBLEM", b)
    if bad:
        sys.exit(1)
    c1 = (HERE / "context_p1.md").read_text(encoding="utf-8").split("\n")
    i = next(k for k, l in enumerate(c1) if l.startswith("- Precedence."))
    c1.insert(i + 1, PROC_P1)
    c2 = (HERE / "context_p2.md").read_text(encoding="utf-8").split("\n")
    j = next(k for k, l in enumerate(c2) if l.startswith("4. Primary."))
    c2[j] = c2[j] + " " + PROC_P2
    (HERE / f"rule_texts_{variant}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    if variant == "v10f":                              # v10f2 reuses the v10f contexts unchanged
        (HERE / "context_p1_v10f.md").write_text("\n".join(c1), encoding="utf-8")
        (HERE / "context_p2_v10f.md").write_text("\n".join(c2), encoding="utf-8")
    t10 = json.loads((HERE / "rule_texts_v10r.json").read_text(encoding="utf-8"))
    for rid in rules:
        print(rid, v9[rid]["title"], {ph: f"v9 {len((v9[rid].get(ph) or '').split())} / v10 {len((t10[rid].get(ph) or '').split())} / "
                                          f"{variant} {len((out[rid].get(ph) or '').split())}" for ph in ("P1", "P2") if out[rid].get(ph)})
    print(f"written: rule_texts_{variant}.json" + (", context_p1_v10f.md, context_p2_v10f.md" if variant == "v10f" else "")
          + f"; procedure {len(PROC_P1.split())} words"
          + ("; each text equals its facts-format test's text" if variant == "v10fo" else ""))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "v10f")
