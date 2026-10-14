"""Assemble the LONG (uncompressed) Phase 2 consistency fix on two_phase_v5f's phase2.md from the audit drafts
(audit_workflow_result.json, wf_5d7fb7b2-d73) with the integration check's resolutions:
  - I16 dropped (duplicates I1-I5, I7 and contradicts itself); I21 has no edit;
  - I8 -> I8r (spare list reordered so "except as the next sentence says" precedes the reset-trigger spare; I10 follows);
  - I11: "2.6's lock-bit example" -> "the lock-bit examples of 2.6 and 2.8";
  - FRAME (new scoping sentence) after I19;
  - I5 moved to the F3A anchor, before I6; one block per shared anchor, in the integration check's reading order;
  - I26 (added here): Phase 2 mapping for common.md's three stale "the reason" pointers (lines 62, 93, 121), left by the
    v5f format change.
common.md and phase1.md are not touched. Writes phase2_long.md (CRLF, like v5f) and blocks.json (texts per block, for
the compression step). Checks: each anchor once in v5f phase2.md and once after the build; the project prompt checker;
words and sha.

  python make_long.py
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
FRAME = ("What one sentence of this step judges as usual is only left out of that sentence: another sentence of this step "
         "can still say that it never qualifies or is not primary, and such a sentence holds even where another would label "
         "the element primary.")
I26 = ('Where sections 1 and 2 ask you to name or say something "in the reason", write it in the point\'s "Answer Reason" '
       'or in the asset\'s "Justification".')
I8_OLD = ("Judged as usual: a decision triggering a reset (such as a timeout), where it is computed, the record of a reset's "
          "cause, and a compare outcome that restarts a counter.")
I8_NEW = ("Judged as usual: the record of a reset's cause, a compare outcome that restarts a counter, and, except as the "
          "next sentence says, a decision triggering a reset (such as a timeout), where it is computed.")
I26_ANCHOR = "the objective 2.7 gives it among the conceptual asset's objectives."
F3A = "even where this step's clause on a decision or setting would make it one."
R1_TAIL = "even when it is the only port the conceptual asset enters or leaves through."
ORDER = {"F3A": ["I8", "I10", "I4", "I7", "I5", "I6", "I15", "I1", "I2", "I12", "I11"],
         "R1": ["I14", "I13", "I9", "I25", "I3"]}


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    d = json.loads((HERE / "audit_workflow_result.json").read_text(encoding="utf-8"))
    D = {v["draft"]["id"]: v["draft"] for v in d["verified"] if v.get("draft")}
    txt = {}
    for k, dr in D.items():
        if k in ("I16", "I21"):
            continue
        assert len(dr["edits"]) >= 1, k
        txt[k] = [dict(e) for e in dr["edits"]]
    # resolutions
    e8 = txt["I8"][0]
    assert e8["new_text"].count(I8_OLD) == 1, "I8 spare list not found"
    e8["new_text"] = e8["new_text"].replace(I8_OLD, I8_NEW)
    e11 = txt["I11"][0]
    assert e11["new_text"].count("2.6's lock-bit example") == 1, "I11 phrase not found"
    e11["new_text"] = e11["new_text"].replace("2.6's lock-bit example", "the lock-bit examples of 2.6 and 2.8")
    p2 = (V5F / "phase2.md").read_text(encoding="utf-8")
    # one insertion block per anchor, in reading order
    blocks = {}
    s1_anchor = txt["I19"][0]["anchor"]
    blocks[s1_anchor] = [("I19", txt["I19"][0]["new_text"]), ("FRAME", FRAME)]
    blocks[R1_TAIL] = [(k, txt[k][0]["new_text"]) for k in ORDER["R1"]]
    blocks[F3A] = [(k, txt[k][0]["new_text"]) for k in ORDER["F3A"]]
    for k in ("I3", "I9", "I13", "I14", "I25"):
        assert txt[k][0]["anchor"] == R1_TAIL and txt[k][0]["mode"] == "insert_after", k
    for k in ORDER["F3A"]:
        if k != "I5":
            assert txt[k][0]["anchor"] == F3A and txt[k][0]["mode"] == "insert_after", k
    blocks[txt["I20"][0]["anchor"]] = [("I20", txt["I20"][0]["new_text"])]
    blocks[I26_ANCHOR] = [("I26", I26)]
    replaces = []
    for e in txt["I22"]:
        if e["mode"] == "replace":
            replaces.append(("I22", e["anchor"], e["new_text"]))
        else:
            blocks.setdefault(e["anchor"], []).append(("I22", e["new_text"]))
    for a in list(blocks) + [r[1] for r in replaces]:
        assert p2.count(a) == 1, f"anchor not unique in v5f phase2.md: {a[:80]}"
    t = p2
    for k, a, new in replaces:
        t = t.replace(a, new)
    for a, items in blocks.items():
        assert t.count(a) == 1, f"anchor lost: {a[:80]}"
        t = t.replace(a, a + " " + " ".join(x.strip() for _, x in items))
    for a in blocks:
        assert t.count(a) == 1, f"anchor no longer unique after the build: {a[:80]}"
    common = (V5F / "common.md").read_text(encoding="utf-8")
    sysp = common.rstrip() + "\n\n" + t
    K, mt = CL.K, CL.mt
    names = K.corpus_names() | mt.corpus_names(str(CL.ROOT))
    plant = mt.check_prompt("Report at most 20 signals such as " + sorted(names)[0], names, "plant")
    r = mt.check_prompt(sysp, names, "long")
    probs = r["problems"] + ([] if "only the final json object" in sysp.lower() else ["no final-JSON phrase"])
    print("checker self-test:", len(plant["problems"]) == 3, "| checker on the long build:", "clean" if not probs else probs)
    wc = lambda s: len(s.split())
    print(f"phase2.md words: v5f {wc(p2)} -> long {wc(t)} ({wc(t) - wc(p2):+d}); Phase 2 system sha {sha(common.rstrip() + chr(10) * 2 + p2)} -> {sha(sysp)}")
    (HERE / "phase2_long.md").write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
    out = {"anchors": {a: [{"id": k, "text": x.strip()} for k, x in items] for a, items in blocks.items()},
           "replaces": [{"id": k, "anchor": a, "new_text": n} for k, a, n in replaces],
           "words": {"v5f": wc(p2), "long": wc(t)}, "sha_long": sha(sysp)}
    (HERE / "blocks.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("written: phase2_long.md, blocks.json; drafts used:", ", ".join(sorted(txt)), "+ FRAME, I26")
    if probs:
        sys.exit(1)


if __name__ == "__main__":
    main()
