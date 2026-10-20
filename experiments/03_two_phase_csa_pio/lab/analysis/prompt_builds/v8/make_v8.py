"""Build two_phase_v8 = two_phase_v7 (the final prompt) + seven prompt rules from the v7 failure analysis (user request
2026-10-14: "implement"; the code filters P1-P4 are held, "the task at hand is prompt debugging").

Rules (analysis/two_phase_v7__gpt-5.6-luna__high__r0-r2/failure_analysis/RULES_FROM_V7.md; each drafted, challenged by
two skeptics, revised, prompt-checked, conflict-checked and blind-tested on the stored v7 replies):
  B1 (paired)  which end of a connection to an instance of an entity of this file is primary
  R1 (paired)  a switch's requests waiting for a grant, and its strobe
  R2 (paired)  the sequencing-state bar keeps judging a peer's command input as usual
  R3 (phase 1) a FIFO holding data the unit generates: its tested holds-data flag and clear-only command
  R4 (phase 1) the access address of a memory the unit itself stores
  R5 (phase 2) labels: a reduced enable input and a plain-copy output port; from rules/R5/merged.json, which adds B1's
               case as an exception inside R5's main sentence (the stage D conflict; 0 elements in the 41 closed sets
               meet both, rules/conflict_scan.py)
  R6 (paired)  held lines of an accepted compare outcome, a handed-off access address and a decoded operand setting
Each edit is anchored to a v7 line: a replace's old text must occur exactly once on that line (after the earlier
replaces on it), or the build stops; inserts go after their v7 line, in rule order. Replaces are applied first, then
the inserts from the bottom up, so every v7 line number stays valid.

Checks (as in make_v7.py):
  - the project prompt checker (check_lab_prompt.check: corpus identifiers, numeric hints, comments, the final-JSON
    phrase, both user templates);
  - chain.new_format for both phases;
  - the OUTPUT sections byte-identical to v7;
  - every sentence of 6 or more words that both phase bodies shared in v7 is still in both, or gone from both;
  - each paired rule's core sentence is in both phase bodies; every edit's new text is in its file;
  - words per file and the shas.

  python make_v8.py            (dry run: the plan and the checks; writes nothing)
  python make_v8.py --write
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
sys.path.insert(0, str(LAB))
import check_lab_prompt as CK  # noqa: E402
import chain as CH  # noqa: E402

SRC = LAB / "prompts" / "two_phase_v7"
DST = LAB / "prompts" / "two_phase_v8"
RULES = LAB / "analysis" / "two_phase_v7__gpt-5.6-luna__high__r0-r2" / "failure_analysis" / "rules"
FILES = ("common.md", "phase1.md", "phase2.md")
ORDER = ("B1", "R1", "R2", "R3", "R4", "R5", "R6")
SOURCE = {fx: RULES / fx / ("merged.json" if fx == "R5" else "revised.json") for fx in ORDER}
SPL = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\-\[])")
REVIEW = [
    # 1: R2's new clause sits before "It"; "It" must stay the sequencing state, not the port or the command (both files)
    ("1", "phase1.md", "nor those stages. It and its internal busy and done flags", "nor those stages. Sequencing state and its internal busy and done flags"),
    ("1", "phase2.md", "nor those stages. It and its internal busy and done flags", "nor those stages. Sequencing state and its internal busy and done flags"),
    # 2: R1's "them" could mean the lock bits and the previous-grant register R1 just left out
    ("2", "phase1.md", "sequencing state and pacing pulses do not cover them: keep the waiting requests",
     "sequencing state and pacing pulses do not cover such a register or that strobe signal: keep the waiting requests"),
    # 3: Phase 2's trailing list repeated the exception the consistency edit put in the main sentence (Phase 1 removed it)
    ("3", "phase2.md", ", the record of a reset's cause, a flag of a FIFO holding data the unit generates), is not covered",
     ", the record of a reset's cause), is not covered"),
    # 4: R5's exception pointed only at B1's sentence; for a hand-off the hand-off sentences pick the same signal
    ("4", "phase2.md", "by the sentence on a value an instance of this file outputs):",
     "by the sentence on a value an instance of this file outputs, or, for a hand-off, by the sentences on hand-offs):"),
    # 5: B1's held line could clash with the Port buffers bar on citing a FIFO's data signals (not reached in the corpus)
    ("5", "phase1.md", "Hold such a value also at the port-map line wiring that port to that signal, besides any line",
     "Hold such a value also at the port-map line wiring that port to that signal (unless the Port buffers rule bars citing that signal's lines), besides any line"),
    # 7: R3's parse: "with a read-data line" could attach to "wiring", and "it" to the data
    ("7", "phase1.md", "the flag held at the line wiring it out of the FIFO with a read-data line returning it as its exit (step 6) and the register held at the line assigning it",
     "the flag held at the line wiring it out of the FIFO, with the read-data line returning the flag as its exit (step 6), and the register held at the line assigning it"),
]
CONSISTENCY = [("R3", "phase2.md", 34,
                "barred by this call's rule on a FIFO only buffering data between two ports or on sequencing state",
                "barred by this call's rule on a FIFO only buffering data between two ports (never a flag of a FIFO holding data the unit generates itself) or on sequencing state")]


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def body(t):
    return t[:t.index("\nOUTPUT\n")]


def sentences(t):
    return {s.strip() for line in t.split("\n") for s in SPL.split(line) if len(s.split()) >= 6}


def build():
    texts = {f: (SRC / f).read_text(encoding="utf-8") for f in FILES}      # read_text gives "\n" line ends
    lines = {f: texts[f].split("\n") for f in FILES}
    fixes = {fx: json.loads(SOURCE[fx].read_text(encoding="utf-8")) for fx in ORDER}
    ok, log = True, []
    # 1. replaces, in rule order, each on its v7 line
    for fx in ORDER:
        for e in fixes[fx]["wording"]["edits"]:
            if e["action"] != "replace":
                continue
            L, i = lines[e["file"]], e["line"] - 1
            n = L[i].count(e["old_text"]) if e["old_text"] else 0
            if n != 1:
                ok = False
                log.append(f"{fx}: {e['file']}:{e['line']}: old text found {n} times: {e['old_text'][:80]!r}")
                continue
            L[i] = L[i].replace(e["old_text"], e["new_text"])
    # 1b. consistency: a v7 sentence both phases share must stay shared. R3 (a phase 1 rule) edits the main sentence of
    #     the status-bit bar on phase1.md:38; the same sentence is on phase2.md:34, so the same edit goes there too.
    #     Phase 2's own trailing list already spares that flag, so this restates an exception Phase 2 already has.
    for fx, f, ln, old, new_t in CONSISTENCY:
        L, i = lines[f], ln - 1
        n = L[i].count(old)
        if n != 1:
            ok = False
            log.append(f"consistency {fx}: {f}:{ln}: old text found {n} times")
            continue
        L[i] = L[i].replace(old, new_t)
        log.append(f"consistency {fx}: the phase1.md edit of a shared sentence also applied on {f}:{ln}")
    # 2. inserts, bottom up; several after the same line keep rule order
    for f in FILES:
        ins = {}
        for fx in ORDER:
            for e in fixes[fx]["wording"]["edits"]:
                if e["action"] == "insert after" and e["file"] == f:
                    ins.setdefault(e["line"], []).append((fx, e["new_text"]))
        for ln in sorted(ins, reverse=True):
            lines[f][ln:ln] = [t for _, t in ins[ln]]
            log.append(f"{f}: inserted after v7 line {ln}: {', '.join(fx for fx, _ in ins[ln])}")
    new = {f: "\n".join(lines[f]) for f in FILES}
    # 2b. REVIEW: the fixes of the combined read-through of the assembled v8 (one agent, 2026-10-14; every claim checked
    #     against the text before applying). Each old text must occur exactly once in its file.
    r6 = next(e for e in fixes["R6"]["wording"]["edits"] if e["file"] == "phase2.md")
    r6_sentence = r6["new_text"][len(r6["old_text"]):]                 # R6's Phase 2 sentence, appended after its anchor
    review = REVIEW + [
        # 6: R6's Phase 2 sentence split the hand-off sentences; move it after B1's sentence (Phase 1 order: B1, then R6)
        ("6", "phase2.md", r6["old_text"] + r6_sentence, r6["old_text"]),
        ("6", "phase2.md", "can be its secondary (2.7, direction a).", "can be its secondary (2.7, direction a)." + r6_sentence),
    ]
    for no, f, old, new_t in review:
        n = new[f].count(old)
        if n != 1:
            ok = False
            log.append(f"review {no}: {f}: old text found {n} times: {old[:80]!r}")
            continue
        new[f] = new[f].replace(old, new_t)
        log.append(f"review {no}: {f} edited")
    # 3. every edit's new text is in its file (R6's moved sentence and texts the review changed are checked by their
    #    review entry); paired cores in both phase bodies
    changed = {old for _, _, old, _ in review}
    for fx in ORDER:
        for e in fixes[fx]["wording"]["edits"]:
            if e["new_text"] not in new[e["file"]] and not any(c in e["new_text"] or e["new_text"] in c for c in changed):
                ok = False
                log.append(f"{fx}: new text missing from {e['file']}")
        core = (fixes[fx]["wording"].get("core_sentence") or "").strip()
        if fixes[fx]["kind"] == "paired rule":
            for f in ("phase1.md", "phase2.md"):
                if core not in body(new[f]):
                    ok = False
                    log.append(f"{fx}: paired core sentence not in the {f} body")
    return texts, new, fixes, ok, log


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    orig, new, fixes, ok, log = build()
    shared_before = sentences(body(orig["phase1.md"])) & sentences(body(orig["phase2.md"]))
    s1, s2 = sentences(body(new["phase1.md"])), sentences(body(new["phase2.md"]))
    broken = sorted(s for s in shared_before if (s in s1) != (s in s2))
    if broken:
        ok = False
        log += [f"shared sentence now in one phase file only: {s[:100]!r}" for s in broken]
    for f in ("phase1.md", "phase2.md"):
        if new[f][new[f].index("\nOUTPUT\n"):] != orig[f][orig[f].index("\nOUTPUT\n"):]:
            ok = False
            log.append(f"{f}: the OUTPUT section changed")
    if new["common.md"] != orig["common.md"]:
        log.append("common.md changed")
    print("\n".join(log))
    w = {f: (len(orig[f].split()), len(new[f].split())) for f in FILES}
    print("words:", {f: f"{a} -> {b} ({b - a:+d})" for f, (a, b) in w.items()})
    print(f"shared v7 sentences (6+ words) kept in both phase bodies or gone from both: {len(shared_before) - len(broken)} of {len(shared_before)}")
    if write and ok:
        DST.mkdir(exist_ok=True)
        for f in ("phase1_user.md", "phase2_user.md"):
            shutil.copyfile(SRC / f, DST / f)                                # byte for byte (LF, as in v7)
        for f in FILES:
            (DST / f).write_bytes(new[f].replace("\n", "\r\n").encode("utf-8"))   # CRLF, as in v7
        chk = bool(CK.check("two_phase_v8", log=print))
        nf = CH.new_format("two_phase_v8", 1) and CH.new_format("two_phase_v8", 2)
        same_user = all((SRC / f).read_bytes() == (DST / f).read_bytes() for f in ("phase1_user.md", "phase2_user.md"))
        ok &= chk and nf and same_user
        print(f"checker {chk}; new_format {nf}; user templates identical to v7 {same_user}; "
              f"shas {sha(CK.system('two_phase_v8', 1))} / {sha(CK.system('two_phase_v8', 2))} (v7 {sha(CK.system('two_phase_v7', 1))} / {sha(CK.system('two_phase_v7', 2))})")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
