"""Build two_phase_v9 = two_phase_v8 + one narrowing of the Forwarded transactions rule (wording proposed by Claude in the
held-out analysis, 2026-10-14; the user: "apply these narrowing to v8", "yes" to building v9, then "do the check & the fix
if needed").

Why (analysis/heldout_versions__gpt-5.6-luna__high__r0-r2, measured): the held-out recall drop at v1 -> v2 is the xbus
module (correct finds 27 -> 9 over r0-r2; the other 25 held-out modules -6, the same as the 15 tuning modules). In every
v2 run Phase 1 put xbus's outgoing request under Not Kept citing the rule, so its separate external-bus ports were never
named. Everything the rule removed on the tuning modules at v1 -> v2 is a record port or record field, and in v8 the
rule's Not Kept rows name no non-record port of any tuning module. v8 still misses xbus_dat_o, xbus_dat_i, xbus_stb_o
(0 of 3 runs) and xbus_cyc_o, xbus_ack_i, xbus_err_i (1 of 3); the "Relayed data" sentences bar the data ports.

Review of the first wording (4 Claude agents, 2026-10-14; analysis/two_phase_v9__gpt-5.6-luna__high__r0-r2/review/):
two blind judges re-judged the 61 v8 Not Kept rows citing forwarding or relayed data (no reference), a scope skeptic
checked every module's ports, a conflict skeptic checked every other rule. Findings acted on: the first wording ("a bus
whose signals are separate non-record ports ... (an address, data, strobe or acknowledge line ...)") named no
direction, so it also reached a register-access port the unit answers (cpu_icc, both judges) and was ambiguous for
operand, read-data, test-access and stream ports; Phase 2's "this sentence" pointed at itself; Phase 1 freed the
information while Phase 2 freed only the port; the Phase 2 sentence split the bar from its "Judged as usual" list and
named a rule Phase 2 cannot see. Fix: the bus is one whose address the unit drives on a non-record output port of its
own and whose acknowledge it takes on a non-record input port of its own (by port name: xbus alone among all entities
of the 41 modules); Phase 2's sentence moves after the relayed-data block, names "the relayed-data sentences above",
labels each port of that bus as usual and keeps those sentences for the concept's other elements.
Re-check of the revised wording (2 Claude agents): a blind judge found the clause changes 7 of the 61 rows, all in xbus,
and no other module's (scope sweep: slink's transmit side a remote "maybe", no row there); a conflict skeptic confirmed
fixes 1, 3, 4 and 5 and found one medium point (keeping "those sentences" for the other elements kept the bar's false
premise "Phase 1 does not keep such a concept, so it has no secondary") and two low ones (an unnamed "them" in "judge
them from port names"; "label each such port"). Applied as the skeptic worded them: the bar "still keeps every other
element from being primary, but each can be a secondary of those ports (2.7)"; "judge from port names which ports are
that bus's address, acknowledge and other lines"; "judge each such port as usual (2.6, 2.7)". These last edits were
checked in code (below), not by another agent round.

Edits:
  phase1.md, v8 line 27 (Forwarded transactions): the first sentence's ending "is not a conceptual asset of this unit."
     gains P1_NEW.
  phase2.md, v8 line 34: after the relayed-data block ("... which a computed result, and say so."), P2_NEW.
Each anchor must occur exactly once on its v8 line, or the build stops.

Checks (as in make_v8.py): the project prompt checker (check_lab_prompt.check: corpus identifiers, numeric hints,
comments, the final-JSON phrase, both user templates); chain.new_format for both phases; the OUTPUT sections
byte-identical to v8; every sentence of 6+ words both phase bodies shared in v8 is still in both, or gone from both;
both new texts present; common.md and the user templates unchanged; words per file and the shas.

  python make_v9.py            (dry run: the plan and the checks; writes nothing)
  python make_v9.py --write
"""
import hashlib
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
sys.path.insert(0, str(LAB))
import check_lab_prompt as CK  # noqa: E402
import chain as CH  # noqa: E402

SRC = LAB / "prompts" / "two_phase_v8"
DST = LAB / "prompts" / "two_phase_v9"
FILES = ("common.md", "phase1.md", "phase2.md")
SPL = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\-\[])")
P1_NEW = ("; this rule, its sentences on relayed data included, never covers a bus whose address this unit drives on a "
          "non-record output port of its own and whose acknowledge it takes on a non-record input port of its own (judge "
          "from port names which ports are that bus's address, acknowledge and other lines, and say so): the request it "
          "drives onto that bus's ports and the response it takes from them are judged as usual, as information leaving and "
          "entering the unit there.")
P2_NEW = (" The relayed-data sentences above never bar a port of a bus whose address this unit drives on a non-record output "
          "port of its own and whose acknowledge it takes on a non-record input port of its own (judge from port names "
          "which ports are that bus's address, acknowledge and other lines, and say so): judge each such port as usual "
          "(2.6, 2.7); under a conceptual asset about what crosses that bus, the relayed-data bar still keeps every other "
          "element from being primary, but each can be a secondary of those ports (2.7).")
EDITS = [  # (file, v8 line, old text, new text)
    ("phase1.md", 27, "without storing, computing or deciding it, is not a conceptual asset of this unit. Also forwarding:",
     "without storing, computing or deciding it, is not a conceptual asset of this unit" + P1_NEW + " Also forwarding:"),
    ("phase2.md", 34, "Judge from port names which instance ports carry relayed data and which a computed result, and say so.",
     "Judge from port names which instance ports carry relayed data and which a computed result, and say so." + P2_NEW),
]


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def body(t):
    return t[:t.index("\nOUTPUT\n")]


def sentences(t):
    return {s.strip() for line in t.split("\n") for s in SPL.split(line) if len(s.split()) >= 6}


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    orig = {f: (SRC / f).read_text(encoding="utf-8") for f in FILES}
    lines = {f: orig[f].split("\n") for f in FILES}
    ok, log = True, []
    for f, ln, old, new_t in EDITS:
        L, i = lines[f], ln - 1
        n = L[i].count(old)
        if n != 1:
            ok = False
            log.append(f"{f}:{ln}: anchor found {n} times: {old[:80]!r}")
            continue
        L[i] = L[i].replace(old, new_t)
        log.append(f"{f}:{ln}: edited")
    new = {f: "\n".join(lines[f]) for f in FILES}
    for txt, f in ((P1_NEW.lstrip("; "), "phase1.md"), (P2_NEW.strip(), "phase2.md")):
        if txt not in body(new[f]):
            ok = False
            log.append(f"new text missing from the {f} body")
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
        ok = False
        log.append("common.md changed")
    print("\n".join(log))
    w = {f: (len(orig[f].split()), len(new[f].split())) for f in FILES}
    print("words:", {f: f"{a} -> {b} ({b - a:+d})" for f, (a, b) in w.items()})
    print(f"shared v8 sentences (6+ words) kept in both phase bodies or gone from both: {len(shared_before) - len(broken)} of {len(shared_before)}")
    if write and ok:
        DST.mkdir(exist_ok=True)
        for f in ("phase1_user.md", "phase2_user.md"):
            shutil.copyfile(SRC / f, DST / f)                                # byte for byte, as in v8
        crlf = b"\r\n" in (SRC / "phase1.md").read_bytes()
        for f in FILES:
            data = new[f].replace("\n", "\r\n") if crlf else new[f]
            (DST / f).write_bytes(data.encode("utf-8"))                     # same line ends as v8
        same_eol = all((b"\r\n" in (SRC / f).read_bytes()) == (b"\r\n" in (DST / f).read_bytes()) for f in FILES)
        same_common = (SRC / "common.md").read_bytes() == (DST / "common.md").read_bytes()
        chk = bool(CK.check("two_phase_v9", log=print))
        nf = CH.new_format("two_phase_v9", 1) and CH.new_format("two_phase_v9", 2)
        same_user = all((SRC / f).read_bytes() == (DST / f).read_bytes() for f in ("phase1_user.md", "phase2_user.md"))
        ok &= chk and nf and same_user and same_eol and same_common
        print(f"checker {chk}; new_format {nf}; user templates identical to v8 {same_user}; common.md byte-identical {same_common}; "
              f"line ends as v8 {same_eol}; shas {sha(CK.system('two_phase_v9', 1))} / {sha(CK.system('two_phase_v9', 2))} "
              f"(v8 {sha(CK.system('two_phase_v8', 1))} / {sha(CK.system('two_phase_v8', 2))})")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
