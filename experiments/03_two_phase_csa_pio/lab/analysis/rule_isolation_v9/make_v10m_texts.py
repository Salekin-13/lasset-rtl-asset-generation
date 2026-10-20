"""Rule texts and contexts for the E3 re-test ("v10m"; user 2026-10-16: "Use the merged procedure. Build the E3 re-test of
all 17 rules (old reply format, send switch off) with readings set before the run").

Only the shared "Reading a rule" procedure changes: every rule keeps the exact text of its last old-format test.
  rule_texts_v10m.json   the 13 rules of the v10 rewrite as rule_texts_v10r.json has them, and the 4 adopted
                         facts-first rules as rule_texts_v10fo.json has them
  context_p1_v10m.md / context_p2_v10m.md   context_p1.md / context_p2.md with the merged procedure
                         (prompt_builds/v10/make_v10.py PROC, the text v10 will carry) placed as in every earlier test:
                         Phase 1 after "- Precedence.", Phase 2 ending the step-4 line
Checks (stops on any failure, writes nothing):
  - the 17 rules are isolation.RULES17, each with the phases its v9 wording had;
  - each of the 13 texts equals the text make_v10.finals() gives now (the text v10 will assemble), built the way
    make_v10r_texts.py builds it; each of the 4 equals the adopted text (make_v10f_texts.py v10fo checked that);
  - the new contexts differ from the v10r and v10f contexts only by the procedure text;
  - the procedure passes the project prompt check.

  python -B make_v10m_texts.py
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
import isolation as ISO  # noqa: E402


def contexts(p1_line, p2_sentence):
    c1 = (HERE / "context_p1.md").read_text(encoding="utf-8").split("\n")
    i = next(k for k, l in enumerate(c1) if l.startswith("- Precedence."))
    c1.insert(i + 1, p1_line)
    c2 = (HERE / "context_p2.md").read_text(encoding="utf-8").split("\n")
    j = next(k for k, l in enumerate(c2) if l.startswith("4. Primary."))
    c2[j] = c2[j] + " " + p2_sentence
    return "\n".join(c1), "\n".join(c2)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    v9 = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    t10r = json.loads((HERE / "rule_texts_v10r.json").read_text(encoding="utf-8"))
    t10fo = json.loads((HERE / "rule_texts_v10fo.json").read_text(encoding="utf-8"))
    bad = []
    out = {}
    F = MV.finals()
    for rid in ISO.RULES17:
        src = t10fo if rid in ISO.G3_RULES else t10r
        if rid not in src:
            bad.append(f"{rid}: missing from its last test's texts")
            continue
        out[rid] = src[rid]
        for ph in ("P1", "P2"):
            if bool(v9[rid].get(ph)) != bool(out[rid].get(ph)):
                bad.append(f"{rid} {ph}: phase missing or extra")
        if rid not in ISO.G3_RULES:                  # the text v10 will assemble, built as make_v10r_texts.py does
            d = F[rid]
            want = {"P1": (d.get("P1_structured") or "").strip() if v9[rid].get("P1") else None,
                    "P2": "\n".join([(d.get("P2_structured") or "").strip()] + [s.strip() for s in (d.get("P2_in_place") or {}).values()]).strip()
                    if v9[rid].get("P2") else None}
            for ph in ("P1", "P2"):
                if (out[rid].get(ph) or None) != want[ph]:
                    bad.append(f"{rid} {ph}: differs from the text make_v10 assembles")
    names = K.corpus_names() | mt.corpus_names(str(ROOT))
    for line in (MV.PROC_P1, MV.PROC_P2):
        pr = mt.check_prompt(line, names, "procedure")["problems"]
        if pr:
            bad.append(f"procedure: prompt check {pr}")
    c1, c2 = contexts(MV.PROC_P1, MV.PROC_P2)
    for v, (p1, p2) in (("v10r", (MV.PROC_V10R_P1, MV.PROC_V10R_P2)),):
        o1 = (HERE / f"context_p1_{v}.md").read_text(encoding="utf-8")
        o2 = (HERE / f"context_p2_{v}.md").read_text(encoding="utf-8")
        if (o1.replace(p1, MV.PROC_P1), o2.replace(p2, MV.PROC_P2)) != (c1, c2):
            bad.append(f"contexts differ from {v}'s beyond the procedure")
    f1 = (HERE / "context_p1_v10f.md").read_text(encoding="utf-8").split("\n")
    f2 = (HERE / "context_p2_v10f.md").read_text(encoding="utf-8").split("\n")
    n1 = c1.split("\n")
    n2 = c2.split("\n")
    d1 = [k for k in range(max(len(f1), len(n1))) if (f1[k] if k < len(f1) else None) != (n1[k] if k < len(n1) else None)]
    d2 = [k for k in range(max(len(f2), len(n2))) if (f2[k] if k < len(f2) else None) != (n2[k] if k < len(n2) else None)]
    if len(d1) != 1 or n1[d1[0]] != MV.PROC_P1 or len(d2) != 1 or not n2[d2[0]].endswith(MV.PROC_P2):
        bad.append(f"contexts differ from v10f's beyond the procedure line (lines {d1}, {d2})")
    for b in bad:
        print("PROBLEM", b)
    if bad:
        sys.exit(1)
    (HERE / "rule_texts_v10m.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "context_p1_v10m.md").write_text(c1, encoding="utf-8")
    (HERE / "context_p2_v10m.md").write_text(c2, encoding="utf-8")
    n = sum(bool(t.get("P1")) for t in out.values()) + sum(bool(t.get("P2")) for t in out.values())
    print(f"written: rule_texts_v10m.json ({len(out)} rules, {n} wordings; 13 as v10r, 4 as v10fo), context_p1_v10m.md, "
          f"context_p2_v10m.md; procedure {len(MV.PROC_P1.split())} words; contexts differ from v10r and v10f by the procedure only")


if __name__ == "__main__":
    main()
