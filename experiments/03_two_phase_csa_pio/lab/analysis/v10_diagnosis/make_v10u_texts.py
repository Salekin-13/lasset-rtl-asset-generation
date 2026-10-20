"""Rule texts and contexts for variant "v10u" (diag_common.py): the two v10 wordings that no rule-alone test read.

  P1-HO  Phase 1 "Held outcomes, addresses and settings" = v10 phase1.md line 95, verbatim
  P1-26  Phase 2 wording of "Requests waiting for a grant" = v10 phase2.md line 157 without its 3-space indent
Contexts: v10's rule-alone contexts (context_p1_v10m.md / context_p2_v10m.md, the merged procedure) with exactly that
line removed (each removed line is checked to be the only difference).
Self-test (hand-read 2026-10-16): context_p1_v10m.md line 25 starts "- Held outcomes, addresses and settings.";
context_p2_v10m.md line 35 starts "   Requests waiting for a grant."; v10 phase2.md line 157 is that line, 1,299
characters with its indent.

  python -B make_v10u_texts.py
"""
import json
import sys

from diag_common import HERE, ISOD, LAB, ROOT

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "assetgen_meta"))
sys.path.insert(0, str(ROOT / "bahavioral_patterns_of_assets"))
import labkit as K  # noqa: E402
import meta_tools as mt  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p1 = (LAB / "prompts" / "two_phase_v10" / "phase1.md").read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    p2 = (LAB / "prompts" / "two_phase_v10" / "phase2.md").read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    c1 = (ISOD / "context_p1_v10m.md").read_text(encoding="utf-8").split("\n")
    c2 = (ISOD / "context_p2_v10m.md").read_text(encoding="utf-8").split("\n")
    ok = (c1[24].startswith("- Held outcomes, addresses and settings.") and c2[34].startswith("   Requests waiting for a grant.")
          and p2[156] == c2[34] and len(p2[156]) == 1299 and p1[94] == c1[24])
    print(f"self-test (hand-read lines): {'PASS' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)
    texts = {"P1-HO": {"title": "Held outcomes, addresses and settings", "P1": p1[94], "P2": None},
             "P1-26": {"title": "Requests waiting for a grant", "P1": None, "P2": p2[156].strip()}}
    n1 = c1[:24] + c1[25:]
    n2 = c2[:34] + c2[35:]
    assert sum(1 for l in n1 if l.startswith("- Held outcomes")) == 0 and sum(1 for l in n2 if "Requests waiting for a grant" in l) == 0
    names = K.corpus_names() | mt.corpus_names(str(ROOT))
    for rid, t in texts.items():
        for ph in ("P1", "P2"):
            if t[ph]:
                pr = mt.check_prompt(t[ph], names, f"{rid} {ph}")["problems"]
                if pr:
                    print("PROBLEM", rid, ph, pr)
                    sys.exit(1)
    (HERE / "rule_texts_v10u.json").write_text(json.dumps(texts, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "context_p1_v10u.md").write_text("\n".join(n1), encoding="utf-8")
    (HERE / "context_p2_v10u.md").write_text("\n".join(n2), encoding="utf-8")
    print("wrote rule_texts_v10u.json (P1-HO P1, P1-26 P2), context_p1_v10u.md, context_p2_v10u.md")


if __name__ == "__main__":
    main()
