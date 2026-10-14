"""Rule texts and contexts for the isolation re-test of the rewritten critical rules ("v10r"; user, 2026-10-15: "don't
assemble it into a full prompt yet. I want to check how the individual changed rules perform").

Reads prompt_builds/v10/dossiers/G*_final.json (the rewrite workflow's final texts) and writes:
  rule_texts_v10r.json   {rule id: {"title", "P1": structured Phase 1 block, "P2": structured Phase 2 block plus the
                          rule's Phase 2 sentences kept in place (as the v9 test joined a rule's sentences)}}
  context_p1_v10r.md     context_p1.md with the shared procedure line after "- Precedence."
  context_p2_v10r.md     context_p2.md with the shared procedure sentence ending the step-4 line
Same rule ids as the v9 test, so every v9 measure compares rule by rule. Checks: every rewritten rule has the phases
its v9 wording had; each new text passes the project prompt check (meta_tools.check_prompt); the contexts differ from
v9's by the procedure text only.

  python -B make_v10r_texts.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
ROOT = LAB.parents[2]
V10 = LAB / "analysis" / "prompt_builds" / "v10"
for p in (LAB, ROOT / "src", ROOT / "assetgen_meta", ROOT / "bahavioral_patterns_of_assets", V10):
    sys.path.insert(0, str(p))
import labkit as K  # noqa: E402
import meta_tools as mt  # noqa: E402
import make_v10 as MV  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    v9 = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    F = MV.finals()
    names = K.corpus_names() | mt.corpus_names(str(ROOT))
    out, bad = {}, []
    for rid, d in sorted(F.items()):
        t = {"title": v9[rid]["title"], "P1": None, "P2": None}
        if v9[rid].get("P1"):
            t["P1"] = (d.get("P1_structured") or "").strip()
        if v9[rid].get("P2"):
            t["P2"] = "\n".join([(d.get("P2_structured") or "").strip()] + [s.strip() for s in (d.get("P2_in_place") or {}).values()]).strip()
        for ph in ("P1", "P2"):
            if bool(v9[rid].get(ph)) != bool(t[ph]):
                bad.append(f"{rid} {ph}: v9 has it {bool(v9[rid].get(ph))}, rewrite has it {bool(t[ph])}")
            if t[ph]:
                pr = mt.check_prompt(t[ph], names, f"{rid} {ph}")["problems"]
                if pr:
                    bad.append(f"{rid} {ph}: prompt check {pr}")
        out[rid] = t
    c1 = (HERE / "context_p1.md").read_text(encoding="utf-8").split("\n")
    i = next(k for k, l in enumerate(c1) if l.startswith("- Precedence."))
    c1.insert(i + 1, MV.PROC_P1)
    c2 = (HERE / "context_p2.md").read_text(encoding="utf-8").split("\n")
    j = next(k for k, l in enumerate(c2) if l.startswith("4. Primary."))
    c2[j] = c2[j] + " " + MV.PROC_P2
    print("rewritten rules:", len(out), "| wordings:", sum(bool(t["P1"]) for t in out.values()) + sum(bool(t["P2"]) for t in out.values()))
    for b in bad:
        print("PROBLEM", b)
    if bad:
        sys.exit(1)
    (HERE / "rule_texts_v10r.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "context_p1_v10r.md").write_text("\n".join(c1), encoding="utf-8")
    (HERE / "context_p2_v10r.md").write_text("\n".join(c2), encoding="utf-8")
    print("written: rule_texts_v10r.json, context_p1_v10r.md, context_p2_v10r.md")


if __name__ == "__main__":
    main()
