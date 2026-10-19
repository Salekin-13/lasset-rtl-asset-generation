"""two_phase_v9g = two_phase_v9f + the v9k rules that pass their rule-alone test (user 2026-10-17: "include it in the v9f
to check for recall increase"). Builds the prompt folder only; sends nothing. Plan: PLAN_V9K.md.

Rule texts: new_rules/rule_texts_v9k.json (make_v9k_texts.py). Which rules go in is given on the command line (the
passing set, decided from read_v9k.json); by default all eight.
  New rules, inserted as whole blocks (each anchor must occur exactly once in v9f's text):
    phase1.md  N22 Access command ports, N23 Entry selects: after the "Access command fields (b)" block;
               N25 Coprocessor progress state: after the Sequencing state block (its last sub-rule);
               N21 Control record ports: after the last rule ("Processor context fields"), before OUTPUT.
    phase2.md  N21, N22, N23: after the Access command fields block (step 4's first block);
               N25: after the Sequencing state block (its last sub-rule);
               N24 Boundary outputs: at the end of step 4, after the "Requests waiting for a grant" paragraph.
  Revised rules P1-04, P1-14, P1-15: the v9f block (the v11r3 text) is replaced by the v9k text in both phases; the
  Phase 2 Sequencing state block keeps v9f's two in-place sentences after it (the v9k text ends with them; they are cut
  off, as make_v9f.py does).
Checks: every untouched v9f line and sentence is still present and in order; OUTPUT sections, common.md and the user
templates byte-identical to v9f; every inserted block present exactly once; check_lab_prompt and chain.new_format pass;
line ends as v9f.

  python -B make_v9g.py [N21,N22,...]            (dry run)
  python -B make_v9g.py [N21,N22,...] --write
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
sys.path.insert(0, str(HERE))
import make_v10 as M  # noqa: E402
import make_v9f as MK  # noqa: E402

CK, CH = M.CK, M.CH
SRC, DST = LAB / "prompts" / "two_phase_v9f", LAB / "prompts" / "two_phase_v9g"
TEXTS = json.loads((HERE / "new_rules" / "rule_texts_v9k.json").read_text(encoding="utf-8"))
_T2 = HERE / "new_rules" / "rule_texts_v9k2.json"          # the revision round: each rule's latest tested text wins
if _T2.exists():
    TEXTS.update(json.loads(_T2.read_text(encoding="utf-8")))
FILES = M.FILES
ALL = ["N21", "N22", "N23", "N24", "N25", "P1-04", "P1-14", "P1-15"]
P1_LAST_RULE_TAIL = "Judge what a field tells from port field names and their uses; say so."          # Processor context fields
P2_GRANT_TAIL = ("for the grant's conceptual asset, label the state register naming the holder primary, as it holds that "
                 "decision (2.6), not secondary to the select or the strobe signal.")                  # end of step 4


def v9f_blocks():
    """The v9f texts of the three revised rules as they stand in the prompt (Phase 2 without the in-place tail)."""
    F = MK.finals()
    return {rid: {"P1": F[rid]["P1_structured"].strip("\n"), "P2": F[rid]["P2_structured"].strip("\n")} for rid in ("P1-04", "P1-14", "P1-15")}


def v9k_p2(rid):
    """The v9k Phase 2 text of a revised rule with the in-place sentences cut off, as make_v9f does for v9f."""
    F = MK.finals()
    p2 = TEXTS[rid]["P2"]
    for s in reversed([v.strip() for v in (F[rid].get("P2_in_place") or {}).values()]):
        cut = p2.rindex(s)
        assert p2[cut:].strip() == s or p2[cut:].strip().startswith(s), (rid, s[:40])
        p2 = p2[:cut]
    return p2.rstrip("\n")


def insert_after(text, anchor, block, log, what):
    if text.count(anchor) != 1:
        log.append(f"{what}: anchor occurs {text.count(anchor)} times")
        return text
    i = text.index(anchor) + len(anchor)
    return text[:i] + "\n" + block + text[i:]


def replace_once(text, old, new, log, what):
    if text.count(old) != 1:
        log.append(f"{what}: the v9f block occurs {text.count(old)} times")
        return text
    return text.replace(old, new)


def build(rules, log):
    orig = {f: (SRC / f).read_text(encoding="utf-8").replace("\r\n", "\n") for f in FILES}
    p1, p2 = orig["phase1.md"], orig["phase2.md"]
    old = v9f_blocks()
    acf_p1 = old_acf_p1()
    acf_p2 = old_acf_p2()
    # revisions first (they replace anchors the insertions below do not use)
    for rid in ("P1-04", "P1-14", "P1-15"):
        if rid in rules:
            p1 = replace_once(p1, old[rid]["P1"], TEXTS[rid]["P1"].strip("\n"), log, f"{rid} P1")
            p2 = replace_once(p2, old[rid]["P2"], v9k_p2(rid), log, f"{rid} P2")
    seq_p1_tail = (TEXTS["P1-15"]["P1"] if "P1-15" in rules else old["P1-15"]["P1"]).strip("\n").split("\n")[-1]
    seq_p2_tail = (v9k_p2("P1-15") if "P1-15" in rules else old["P1-15"]["P2"]).split("\n")[-1]
    # Phase 1 insertions
    after_acf1 = "\n".join(TEXTS[r]["P1"].strip("\n") for r in ("N22", "N23") if r in rules)
    if after_acf1:
        p1 = insert_after(p1, acf_p1, after_acf1, log, "N22/N23 P1 after Access command fields (b)")
    if "N25" in rules:
        p1 = insert_after(p1, seq_p1_tail, TEXTS["N25"]["P1"].strip("\n"), log, "N25 P1 after Sequencing state")
    if "N21" in rules:
        p1 = insert_after(p1, P1_LAST_RULE_TAIL, TEXTS["N21"]["P1"].strip("\n"), log, "N21 P1 after Processor context fields")
    # Phase 2 insertions
    after_acf2 = "\n".join(TEXTS[r]["P2"].strip("\n") for r in ("N21", "N22", "N23") if r in rules)
    if after_acf2:
        p2 = insert_after(p2, acf_p2, after_acf2, log, "N21/N22/N23 P2 after Access command fields")
    if "N25" in rules:
        p2 = insert_after(p2, seq_p2_tail, TEXTS["N25"]["P2"].strip("\n"), log, "N25 P2 after Sequencing state")
    if "N24" in rules:
        p2 = insert_after(p2, P2_GRANT_TAIL, TEXTS["N24"]["P2"].strip("\n"), log, "N24 P2 at the end of step 4")
    new = {"common.md": orig["common.md"], "phase1.md": p1, "phase2.md": p2}
    # checks
    for f in ("phase1.md", "phase2.md"):
        if new[f][new[f].index("\nOUTPUT\n"):] != orig[f][orig[f].index("\nOUTPUT\n"):]:
            log.append(f"{f}: the OUTPUT section changed")
    for rid in rules:
        if rid.startswith("N"):
            for ph, body in (("P1", p1), ("P2", p2)):
                if TEXTS[rid].get(ph) and body.count(TEXTS[rid][ph].strip("\n")) != 1:
                    log.append(f"{rid} {ph}: inserted block not present exactly once")
        else:
            if p1.count(TEXTS[rid]["P1"].strip("\n")) != 1 or p2.count(v9k_p2(rid)) != 1:
                log.append(f"{rid}: revised block not present exactly once")
            if p1.count(old[rid]["P1"]) or p2.count(old[rid]["P2"]):
                log.append(f"{rid}: the v9f block is still present")
    # every untouched v9f line (Phase 1) and sentence (Phase 2) still present, in order
    kept1 = [l for l in orig["phase1.md"].split("\n") if not any(l in old[r]["P1"] for r in old if r in rules)]
    pos, n1 = 0, p1.split("\n")
    for l in kept1:
        try:
            pos = n1.index(l, pos) + 1
        except ValueError:
            log.append(f"phase1.md: an untouched v9f line is missing or out of order: {l[:80]!r}")
            break
    pos = 0
    for l in orig["phase2.md"].split("\n"):
        if any(l in old[r]["P2"] for r in old if r in rules):
            continue
        j = p2.find(l, pos)
        if j < 0:
            log.append(f"phase2.md: an untouched v9f line is missing or out of order: {l[:80]!r}")
            break
        pos = j + len(l)
    return not log, orig, new


def old_acf_p1():
    t = json.loads((HERE / "new_rules" / "rule_texts_v11r3.json").read_text(encoding="utf-8"))["P1-23"]["P1"].strip("\n")
    return t


def old_acf_p2():
    F = MK.finals()
    return F["P1-23"]["P2_structured"].strip("\n")


def main(rules, write):
    sys.stdout.reconfigure(encoding="utf-8")
    log = []
    ok, orig, new = build(rules, log)
    print("\n".join(log) if log else f"plan ({', '.join(rules)}): no problems found")
    print("words per file:", {f: f"{len(orig[f].split())} -> {len(new[f].split())}" for f in FILES})
    if write and ok:
        DST.mkdir(exist_ok=True)
        for f in ("phase1_user.md", "phase2_user.md"):
            shutil.copyfile(SRC / f, DST / f)
        crlf = b"\r\n" in (SRC / "phase1.md").read_bytes()
        for f in FILES:
            (DST / f).write_bytes((new[f].replace("\n", "\r\n") if crlf else new[f]).encode("utf-8"))
        (DST / "README.md").write_text(
            "# two_phase_v9g: v9f + the v9k rules that passed their rule-alone test (built 2026-10-17)\n\nv9f with these rules "
            f"from analysis/v10_diagnosis/new_rules/rule_texts_v9k.json: {', '.join(rules)}. Plan, readings and the test "
            "results: analysis/v10_diagnosis/PLAN_V9K.md and read_v9k.json. Built by analysis/v10_diagnosis/make_v9g.py.\n",
            encoding="utf-8")
        chk = bool(CK.check("two_phase_v9g", log=print))
        nf = CH.new_format("two_phase_v9g", 1) and CH.new_format("two_phase_v9g", 2)
        same = all((SRC / f).read_bytes() == (DST / f).read_bytes() for f in ("common.md", "phase1_user.md", "phase2_user.md"))
        eol = all((b"\r\n" in (SRC / f).read_bytes()) == (b"\r\n" in (DST / f).read_bytes()) for f in FILES)
        ok &= chk and nf and same and eol
        print(f"checker {chk}; new_format {nf}; common.md and user templates identical to v9f {same}; line ends as v9f {eol}; "
              f"sha12 {M.sha(CK.system('two_phase_v9g', 1))[:12]} / {M.sha(CK.system('two_phase_v9g', 2))[:12]}")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0].split(",") if args else ALL, "--write" in sys.argv)
