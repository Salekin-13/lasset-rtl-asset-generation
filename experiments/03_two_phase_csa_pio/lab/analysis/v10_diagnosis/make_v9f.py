"""two_phase_v9f = two_phase_v9 (the working version) with the five rule fixes written for v9's held-out Phase 1 misses
(user 2026-10-17: "write the rules into the v9 prompt and check if recall rises, especially for the heldout 26").
Builds the prompt folder only; sends nothing. Plan: PLAN_V9F.md.

Rule texts: new_rules/rule_texts_v11r3.json, both phases, for Access command fields (P1-23), Pacing pulses (P1-04),
Port buffers (P1-14), Operation selectors (P1-22) and Sequencing state (P1-15). These are the latest luna-tested
wordings: P1-23 both phases and P1-15 Phase 2 equal v11r2; the other Phase 1 texts are v11r3; the Phase 2 texts of
P1-04, P1-14 and P1-22 are v11r3 and were never run on luna. They are written in the block layout (Scope / Criteria /
Exceptions / Outcome / Evidence) and were tested with the "Reading a rule" procedure, so that procedure sentence goes in
too, as in v10 (make_v10.PROC_P1 after "- Precedence.", make_v10.PROC_P2 before the first block in step 4).

Edits (prompt_builds/v10/make_v10.py's machinery, limited to these five rules):
  phase1.md  each rule's v9 line -> its v11r3 Phase 1 block; the procedure line after "- Precedence.".
  phase2.md  the step-4 sentences each rule owns (make_v10's sentence ids, "P2_replaces") are removed and the rule's
             v11r3 Phase 2 block goes where the first of them stood; Sequencing state's two in-place sentences
             (S004, S012) stay in place with their text (the v11r3 Phase 2 text ends with exactly those two sentences,
             which are cut off the block).
Checks: the v9 step-4 sentences rebuild the v9 line exactly; every other v9 Phase 1 line and Phase 2 sentence is
unchanged and in order; the OUTPUT sections, common.md and the user templates are byte-identical to v9;
check_lab_prompt and chain.new_format pass; line ends as v9.

  python -B make_v9f.py            (dry run)
  python -B make_v9f.py --write
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
SRC, DST = LAB / "prompts" / "two_phase_v9", LAB / "prompts" / "two_phase_v9f"
RULES = ["P1-23", "P1-04", "P1-14", "P1-22", "P1-15"]
FILES = M.FILES


def finals():
    v10 = M.finals()
    t = json.loads((HERE / "new_rules" / "rule_texts_v11r3.json").read_text(encoding="utf-8"))
    out = {}
    for rid in RULES:
        p2 = t[rid]["P2"]
        inplace = v10[rid].get("P2_in_place") or {}
        if inplace:
            tail = [v.strip() for v in inplace.values()]
            for s in reversed(tail):
                cut = p2.rindex(s)
                assert p2[cut:].strip() == s or p2[cut:].strip().startswith(s), (rid, s[:40])
                p2 = p2[:cut]
            p2 = p2.rstrip("\n")
        out[rid] = {"P1_structured": t[rid]["P1"], "P2_structured": p2,
                    "P2_replaces": v10[rid]["P2_replaces"], "P2_in_place": inplace}
    return out


def build(log):
    idx = json.loads((M.ISOD / "pack" / "index.json").read_text(encoding="utf-8"))
    F = finals()
    ok = True
    orig = {f: (SRC / f).read_text(encoding="utf-8").replace("\r\n", "\n") for f in FILES}
    p1 = orig["phase1.md"].split("\n")
    new1 = []
    for i, line in enumerate(p1, 1):
        rid = next((r for r, x in idx["p1"].items() if x["line"] == i and r in F), None)
        if rid:
            if line != idx["p1"][rid]["text"]:
                ok = False
                log.append(f"phase1.md:{i}: v9 line differs from the indexed text of {rid}")
            new1.append(F[rid]["P1_structured"].strip("\n"))
        else:
            new1.append(line)
        if line.startswith("- Precedence."):
            new1.append(M.PROC_P1)
    p2 = orig["phase2.md"].split("\n")
    by_line = {}
    for s in sorted(idx["p2"]):
        by_line.setdefault(idx["p2"][s]["line"], []).append(s)
    owner = {s: rid for rid in F for s in list(F[rid]["P2_replaces"]) + list(F[rid]["P2_in_place"])}
    placed, proc_done = set(), False
    for ln, sids in by_line.items():
        if " ".join(idx["p2"][s]["text"] for s in sids) != p2[ln - 1]:
            ok = False
            log.append(f"phase2.md:{ln}: the indexed sentences do not rebuild the v9 line")
            continue
        if not any(s in owner for s in sids):
            continue
        parts, run = [], []
        for s in sids:
            rid = owner.get(s)
            if rid and s in F[rid]["P2_in_place"]:
                run.append(F[rid]["P2_in_place"][s].strip())
            elif rid and s in F[rid]["P2_replaces"]:
                if rid not in placed:
                    if run:
                        parts.append(" ".join(run))
                        run = []
                    if not proc_done:
                        parts.append(M.PROC_P2)
                        proc_done = True
                    parts.append(F[rid]["P2_structured"].strip("\n"))
                    placed.add(rid)
            else:
                run.append(idx["p2"][s]["text"])
        if run:
            parts.append(" ".join(run))
        p2[ln - 1] = "\n".join(parts)
    if placed != set(F):
        ok = False
        log.append(f"Phase 2 blocks placed for {sorted(placed)}, expected {sorted(F)}")
    new = {"common.md": orig["common.md"], "phase1.md": "\n".join(new1), "phase2.md": "\n".join(p2)}
    kept1 = [l for i, l in enumerate(orig["phase1.md"].split("\n"), 1) if not any(x["line"] == i and r in F for r, x in idx["p1"].items())]
    pos, n1 = 0, new["phase1.md"].split("\n")
    for l in kept1:
        try:
            pos = n1.index(l, pos) + 1
        except ValueError:
            ok = False
            log.append(f"phase1.md: an untouched v9 line is missing or out of order: {l[:80]!r}")
            break
    pos, body2 = 0, new["phase2.md"]
    for s in sorted(idx["p2"]):
        if s in owner and s not in F[owner[s]]["P2_in_place"]:
            continue
        txt = F[owner[s]]["P2_in_place"][s].strip() if s in owner else idx["p2"][s]["text"]
        j = body2.find(txt, pos)
        if j < 0:
            ok = False
            log.append(f"phase2.md: untouched sentence {s} missing or out of order")
            break
        pos = j + len(txt)
    for f in ("phase1.md", "phase2.md"):
        if new[f][new[f].index("\nOUTPUT\n"):] != orig[f][orig[f].index("\nOUTPUT\n"):]:
            ok = False
            log.append(f"{f}: the OUTPUT section changed")
    for rid in F:
        if new["phase1.md"].count(F[rid]["P1_structured"].strip("\n")) != 1 or new["phase2.md"].count(F[rid]["P2_structured"].strip("\n")) != 1:
            ok = False
            log.append(f"{rid}: a new block is not present exactly once")
    return ok, orig, new


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
            "# two_phase_v9f: v9 + the five Phase 1 rule fixes (built 2026-10-17, not run)\n\nv9 (the working version) with "
            "Access command fields, Pacing pulses, Port buffers, Operation selectors and Sequencing state replaced by their "
            "rule-fix texts (analysis/v10_diagnosis/new_rules/rule_texts_v11r3.json, both phases) and the 'Reading a rule' "
            "procedure sentence. Plan and readings: analysis/v10_diagnosis/PLAN_V9F.md. Built by "
            "analysis/v10_diagnosis/make_v9f.py.\n", encoding="utf-8")
        chk = bool(CK.check("two_phase_v9f", log=print))
        nf = CH.new_format("two_phase_v9f", 1) and CH.new_format("two_phase_v9f", 2)
        same = all((SRC / f).read_bytes() == (DST / f).read_bytes() for f in ("common.md", "phase1_user.md", "phase2_user.md"))
        eol = all((b"\r\n" in (SRC / f).read_bytes()) == (b"\r\n" in (DST / f).read_bytes()) for f in FILES)
        ok &= chk and nf and same and eol
        print(f"checker {chk}; new_format {nf}; common.md and user templates identical to v9 {same}; line ends as v9 {eol}; "
              f"sha12 {M.sha(CK.system('two_phase_v9f', 1))[:12]} / {M.sha(CK.system('two_phase_v9f', 2))[:12]}")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
