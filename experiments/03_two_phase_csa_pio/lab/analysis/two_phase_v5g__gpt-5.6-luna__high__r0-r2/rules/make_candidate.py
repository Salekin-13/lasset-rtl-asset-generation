"""Save the integrated v6 candidate (rules workflow wf_ce0308e1-806; its integrator's own build code, recovered from
its transcript, was re-run unchanged: scratchpad v6build/build_phase1_call20.py and build_phase2_call18.py) as
v6_candidate/{common,phase1,phase2}.md (CRLF, like v5g), and write diff_v5g_to_v6.md: every changed passage, file by
file, as REMOVED / ADDED blocks with the sentence before it, and the draft rule id(s) whose text it matches.
Checks: the system shas equal the integrator's reported ones (Phase 1 e815598c3dda, Phase 2 773926fea6fb); the
project prompt checker on both assembled prompts; words per file.

  python make_candidate.py <folder with the built phase1.md, phase2.md, common_from_18.md>
"""
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
sys.path.insert(0, str(LAB))
import check_lab_prompt as CL  # noqa: E402

V5G = LAB / "prompts" / "two_phase_v5g"
WANT = {1: "e815598c3dda", 2: "773926fea6fb"}


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def sents(t):
    return [s for s in re.split(r"(?<=[.:;])\s+(?=[\"'(A-Z-])|\n+", t) if s.strip()]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    src = Path(sys.argv[1])
    new = {"common.md": (src / "common_from_18.md").read_bytes().decode("utf-8"),
           "phase1.md": (src / "phase1.md").read_bytes().decode("utf-8"),
           "phase2.md": (src / "phase2.md").read_bytes().decode("utf-8")}
    old = {f: (V5G / f).read_text(encoding="utf-8") for f in new}
    ok = True
    for ph in (1, 2):
        s = sha(new["common.md"].rstrip() + "\n\n" + new[f"phase{ph}.md"])
        print(f"Phase {ph} system sha12 {s} (integrator: {WANT[ph]}): {'MATCH' if s == WANT[ph] else 'DIFFERENT'}")
        ok &= s == WANT[ph]
    K, mt = CL.K, CL.mt
    names = K.corpus_names() | mt.corpus_names(str(CL.ROOT))
    for ph in (1, 2):
        sp = new["common.md"].rstrip() + "\n\n" + new[f"phase{ph}.md"]
        pr = mt.check_prompt(sp, names, f"v6 phase {ph}")["problems"] + ([] if "only the final json object" in sp.lower() else ["no final-JSON phrase"])
        print(f"checker phase {ph}:", "clean" if not pr else pr)
        ok &= not pr
    for f in new:
        print(f"words {f}: v5g {len(old[f].split())} -> v6 candidate {len(new[f].split())}")
    out = HERE / "v6_candidate"
    out.mkdir(exist_ok=True)
    for f, t in new.items():
        (out / f).write_bytes(t.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
    # readable diff with draft ids
    fin = json.loads((HERE / "rules_workflow_result.json").read_text(encoding="utf-8"))
    texts = []
    for it in fin["items"]:
        for r in (it.get("final") or {}).get("rules", []):
            for e in r["edits"]:
                texts.append((r["id"], " ".join(e["text"].split())))
    def ids_for(block):
        b = " ".join(block.split())
        hits = []
        for rid, t in texts:
            for s in sents(b):
                s = s.strip()
                if len(s) > 40 and s[:60] in t:
                    hits.append(rid)
                    break
        return sorted(set(hits))
    md = ["# What v6 changes against v5g (for the blind judges)", "",
          "Every changed passage per file. REMOVED = v5g text that v6 deletes or replaces; ADDED = new v6 text. 'after:' is the",
          "sentence just before the change. Draft ids (where the text matches a draft of the rules workflow) are given to cite.", ""]
    for f in ("common.md", "phase1.md", "phase2.md"):
        a, b = sents(old[f]), sents(new[f])
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        md.append(f"## {f}")
        n = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            n += 1
            before = a[i1 - 1].strip() if i1 > 0 else "(start)"
            md.append(f"### change {f}#{n} (after: \"{before[-120:]}\")")
            if i2 > i1:
                md.append("- REMOVED: " + " ".join(s.strip() for s in a[i1:i2]))
            if j2 > j1:
                blk = " ".join(s.strip() for s in b[j1:j2])
                md.append(f"- ADDED {ids_for(blk) or ''}: " + blk)
            md.append("")
    (HERE / "diff_v5g_to_v6.md").write_text("\n".join(md), encoding="utf-8")
    print("written: v6_candidate/, diff_v5g_to_v6.md;", "ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
