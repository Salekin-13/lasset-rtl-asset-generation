"""two_phase_v9h = two_phase_v9g + the four Stage C keep blocks (new_rules/rule_texts_v9h.json), each placed right after
the bar it overrides, in both phases (PLAN_ISOLATE_CLUSTER_ORDER.md section 8, Stage C first cell). Builds the prompt
folder only; sends nothing.
  Phase 1: K11 then K14 after the Pacing pulses block; K12 after the Port buffers (c) block; K13 after the Sequencing
           state block (so before N25, which v9g placed there).
  Phase 2: the same, after the corresponding step-4 blocks.
Checks: every v9g line still present and in order; OUTPUT sections, common.md and the user templates byte-identical to
v9g; each block present exactly once; check_lab_prompt and chain.new_format pass; line ends as v9g.

  python -B make_v9h.py            (dry run)
  python -B make_v9h.py --write
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
import make_v10 as M  # noqa: E402

CK, CH = M.CK, M.CH
SRC, DST = LAB / "prompts" / "two_phase_v9g", LAB / "prompts" / "two_phase_v9h"
TEXTS = json.loads((HERE / "new_rules" / "rule_texts_v9h.json").read_text(encoding="utf-8"))
FILES = M.FILES
ANCHORS = {
    "phase1.md": {
        "pacing": "  Outcome: part of that step or its rate setting (step 3). Do not name it in any concept's information or cite its lines as held lines.",
        "portbuf": "  Evidence: cite no line assigning or wiring those two signals as a held line; leave \"Held Lines\" empty if no other line holds the data.",
        "seq": "    Outcome: a step counter: information of its own, one piece with that state. Keep that state as a concept and hold the count in it, not in the operation's result or its pacing.",
    },
    "phase2.md": {
        "pacing": "  Outcome: not primary for any conceptual asset. It can be a secondary only of a primary whose update it gates (2.7, direction b).",
        "portbuf": "they can be secondaries (2.7, direction a). The buffered data is judged where the unit generates it (random bits) or where it crosses the unit's boundary at a port.",
        "seq": "    Outcome: a step counter, one piece of information with that state. Label the count primary for that state's conceptual asset, not secondary as a transition input.",
    },
}
PLACE = [("pacing", ["K11", "K14"]), ("portbuf", ["K12"]), ("seq", ["K13"])]


def insert_after(text, anchor, block, log, what):
    if text.count(anchor) != 1:
        log.append(f"{what}: anchor occurs {text.count(anchor)} times")
        return text
    i = text.index(anchor) + len(anchor)
    return text[:i] + "\n" + block + text[i:]


def build(log):
    orig = {f: (SRC / f).read_text(encoding="utf-8").replace("\r\n", "\n") for f in FILES}
    new = {"common.md": orig["common.md"]}
    for f, ph in (("phase1.md", "P1"), ("phase2.md", "P2")):
        body = orig[f]
        for key, rids in PLACE:
            block = "\n".join(TEXTS[r][ph].strip("\n") for r in rids)
            body = insert_after(body, ANCHORS[f][key], block, log, f"{f} {key} {rids}")
        if body[body.index("\nOUTPUT\n"):] != orig[f][orig[f].index("\nOUTPUT\n"):]:
            log.append(f"{f}: the OUTPUT section changed")
        for rid in TEXTS:
            if body.count(TEXTS[rid][ph].strip("\n")) != 1:
                log.append(f"{rid} {ph}: block not present exactly once")
        pos = 0
        for l in orig[f].split("\n"):
            j = body.find(l, pos)
            if j < 0:
                log.append(f"{f}: a v9g line is missing or out of order: {l[:80]!r}")
                break
            pos = j + len(l)
        new[f] = body
    return not log, orig, new


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    log = []
    ok, orig, new = build(log)
    print("\n".join(log) if log else "plan: no problems found")
    print("words per file:", {f: f"{len(orig[f].split())} -> {len(new[f].split())}" for f in FILES})
    if write and ok:
        DST.mkdir(exist_ok=True)
        for f in ("phase1_user.md", "phase2_user.md"):
            shutil.copyfile(SRC / f, DST / f)
        crlf = b"\r\n" in (SRC / "phase1.md").read_bytes()
        for f in FILES:
            (DST / f).write_bytes((new[f].replace("\n", "\r\n") if crlf else new[f]).encode("utf-8"))
        (DST / "README.md").write_text(
            "# two_phase_v9h: v9g + the four Stage C keep blocks (built 2026-10-18)\n\nv9g with Done and wait inputs, Link handshake "
            "ports, Busy locks and Count increment inputs (analysis/v10_diagnosis/new_rules/rule_texts_v9h.json), each placed right "
            "after the bar it overrides. Plan: analysis/v10_diagnosis/PLAN_ISOLATE_CLUSTER_ORDER.md section 8 (Stage C, first "
            "cell). Built by analysis/v10_diagnosis/make_v9h.py.\n", encoding="utf-8")
        chk = bool(CK.check("two_phase_v9h", log=print))
        nf = CH.new_format("two_phase_v9h", 1) and CH.new_format("two_phase_v9h", 2)
        same = all((SRC / f).read_bytes() == (DST / f).read_bytes() for f in ("common.md", "phase1_user.md", "phase2_user.md"))
        eol = all((b"\r\n" in (SRC / f).read_bytes()) == (b"\r\n" in (DST / f).read_bytes()) for f in FILES)
        ok &= chk and nf and same and eol
        print(f"checker {chk}; new_format {nf}; common.md and user templates identical to v9g {same}; line ends as v9g {eol}; "
              f"sha12 {M.sha(CK.system('two_phase_v9h', 1))[:12]} / {M.sha(CK.system('two_phase_v9h', 2))[:12]}")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
