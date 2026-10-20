"""Rule text for the rule-alone test of the E1 fix to Buffer and engine status bits ("v10e1"; user 2026-10-16: "Before
building v10, apply the E1 gloss fix to Buffer and engine status bits and test that rule alone first").

Writes rule_texts_v10e1.json with P1-17 only, built from prompt_builds/v10/e1/P1-17_final.json the way
make_v10r_texts.py builds a rule (Phase 1: the structured block; Phase 2: the structured block plus the sentences kept in
place). The context is v10's (context_p1_v10m.md / context_p2_v10m.md, the merged procedure), so the old side of the
test is "v10m" (the current v10 text) and only the rule's words differ. Checks: the old text equals rule_texts_v10m.json's
P1-17; old and new differ exactly by the two E1 edits (re-applied here); the new text passes the project prompt check.

  python -B make_v10e1_texts.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
ROOT = LAB.parents[2]
V10 = LAB / "analysis" / "prompt_builds" / "v10"
for p in (LAB, ROOT / "src", ROOT / "assetgen_meta", ROOT / "bahavioral_patterns_of_assets", V10 / "e1"):
    sys.path.insert(0, str(p))
import labkit as K  # noqa: E402
import meta_tools as mt  # noqa: E402
import make_e1_status_bits as E1  # noqa: E402

RID = "P1-17"


def build(d, title):
    return {"title": title, "P1": (d.get("P1_structured") or "").strip(),
            "P2": "\n".join([(d.get("P2_structured") or "").strip()] + [s.strip() for s in (d.get("P2_in_place") or {}).values()]).strip()}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    old = json.loads((HERE / "rule_texts_v10m.json").read_text(encoding="utf-8"))[RID]
    src = json.loads((V10 / "dossiers" / "G5_final.json").read_text(encoding="utf-8"))[RID]
    fix = json.loads((V10 / "e1" / f"{RID}_final.json").read_text(encoding="utf-8"))[RID]
    bad = []
    if build(src, old["title"]) != old:
        bad.append("the v10 source no longer builds the text the E3 test read")
    new = build(fix, old["title"])
    for ph in ("P1", "P2"):
        t = old[ph]
        for a, b in E1.EDITS:
            t = t.replace(a, b)
        if t != new[ph]:
            bad.append(f"{ph}: old and new differ by more than the E1 edits")
        if t == old[ph]:
            bad.append(f"{ph}: no edit applied")
    names = K.corpus_names() | mt.corpus_names(str(ROOT))
    for ph in ("P1", "P2"):
        pr = mt.check_prompt(new[ph], names, f"{RID} {ph}")["problems"]
        if pr:
            bad.append(f"{ph}: prompt check {pr}")
    for b in bad:
        print("PROBLEM", b)
    if bad:
        sys.exit(1)
    (HERE / "rule_texts_v10e1.json").write_text(json.dumps({RID: new}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written rule_texts_v10e1.json ({RID}: P1 {len(old['P1'].split())} -> {len(new['P1'].split())} words, "
          f"P2 {len(old['P2'].split())} -> {len(new['P2'].split())}); differs from v10m's text by the two E1 edits only")


if __name__ == "__main__":
    main()
