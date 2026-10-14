"""Apply the compressed Phase 2 consistency fix (compression workflow wf_0b540b62-d24, final text after 2 clause-check
rounds: 'equivalent' by both checkers) to two_phase_v5f's phase2.md. Writes phase2_compressed.md (CRLF) and
inserts_compressed.md (each inserted text with its draft ids, for the boundary judges).
Checks: anchors once before and after; undoing the inserts and the I22 replace gives v5f phase2.md exactly; the
project prompt checker on the assembled Phase 2 system prompt; words and sha.

  python make_compressed.py
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
sys.path.insert(0, str(LAB))
import check_lab_prompt as CL  # noqa: E402

V5F = LAB / "prompts" / "two_phase_v5f"


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    fin = json.loads((HERE / "compression_workflow_result.json").read_text(encoding="utf-8"))["final"]
    blocks = json.loads((HERE / "blocks.json").read_text(encoding="utf-8"))
    p2 = (V5F / "phase2.md").read_text(encoding="utf-8")
    assert len(blocks["replaces"]) == 1
    rep = blocks["replaces"][0]
    assert p2.count(rep["anchor"]) == 1, "I22 replace anchor"
    t = p2.replace(rep["anchor"], fin["i22_replace_new_text"])
    inserted = []
    for a in fin["anchors"]:
        assert a["anchor"] in blocks["anchors"], f"unknown anchor {a['anchor'][:60]}"
        assert t.count(a["anchor"]) == 1, f"anchor not once: {a['anchor'][:60]}"
        new = " " + a["text"].strip()
        t = t.replace(a["anchor"], a["anchor"] + new)
        inserted.append((a["anchor"], new, a["draft_ids"]))
    for a, _, _ in inserted:
        assert t.count(a) == 1, f"anchor not unique after build: {a[:60]}"
    # undo check
    u = t
    for a, new, _ in inserted:
        u = u.replace(a + new, a)
    u = u.replace(fin["i22_replace_new_text"], rep["anchor"])
    print("undoing the inserts and the I22 replace gives v5f phase2.md exactly:", u == p2)
    common = (V5F / "common.md").read_text(encoding="utf-8")
    sysp = common.rstrip() + "\n\n" + t
    K, mt = CL.K, CL.mt
    names = K.corpus_names() | mt.corpus_names(str(CL.ROOT))
    plant = mt.check_prompt("Report at most 20 signals such as " + sorted(names)[0], names, "plant")
    r = mt.check_prompt(sysp, names, "compressed")
    probs = r["problems"] + ([] if "only the final json object" in sysp.lower() else ["no final-JSON phrase"])
    print("checker self-test:", len(plant["problems"]) == 3, "| checker:", "clean" if not probs else probs)
    wc = lambda s: len(s.split())
    long_words = blocks["words"]["long"]
    print(f"phase2.md words: v5f {wc(p2)} -> compressed {wc(t)} ({wc(t) - wc(p2):+d}); long version {long_words}")
    print(f"Phase 2 system sha: v5f {sha(common.rstrip() + chr(10) * 2 + p2)} -> compressed {sha(sysp)}")
    (HERE / "phase2_compressed.md").write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
    md = ["# Inserted Phase 2 texts (compressed), with the audit draft ids", "",
          "Each block is inserted right after its anchor sentence of v5f phase2.md. I22 also replaces one phrase in the",
          "CONCEPTS paragraph. Draft ids refer to AUDIT_FINDINGS.md (FRAME = scoping sentence; I26 = stale 'reason' pointer).", "",
          f"## I22 replace (CONCEPTS paragraph)", f"- old: {rep['anchor']}", f"- new: {fin['i22_replace_new_text']}", ""]
    for a, new, ids in inserted:
        md += [f"## After: \"{a}\"", f"- drafts: {', '.join(ids)}", "", new.strip(), ""]
    (HERE / "inserts_compressed.md").write_text("\n".join(md), encoding="utf-8")
    print("written: phase2_compressed.md, inserts_compressed.md")
    if probs or u != p2:
        sys.exit(1)


if __name__ == "__main__":
    main()
