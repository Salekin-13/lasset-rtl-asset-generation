"""Build prompt version two_phase_v5 = two_phase_v4a + the rules of RULES_PROPOSAL.md the user accepted (2026-10-12):
  A (published or design-principle basis): R1, R3, R4, R5, K1, K2
  B (no published basis, user decision): R2b, R7b
  U (user decision 2026-10-12: restrictions against extra concepts the reference does not list and that contribute no
     correct find, to raise precision): the restriction rules that passed the blind test (u_rules.json, written from the
     restriction workflow; see analysis/two_phase_v4a__gpt-5.6-luna__high__r0-r2/U_RULES.md)
Every edit is an exact string replacement that must match once; the texts are copied from the rule workflows' outputs.
After the rules, the fixes of the v5 conflict check (v5_fixes.json) are applied in order.
Inputs stay v1 (user decision: the v1k key stays out).

  python make_v5.py            (refuses to overwrite an existing two_phase_v5 unless --force)
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
P = LAB / "prompts"
V4A, V5 = P / "two_phase_v4a", P / "two_phase_v5"
AN = LAB / "analysis" / "two_phase_v4a__gpt-5.6-luna__high__r0-r2"

# (rule id, file, old, new): A and B rules, texts verbatim from rules_workflow_result.json (wf_9c7700ae-02e)
R7B_LINE = ("- Clocks and resets. Clock and reset inputs, a reset request that the unit only combines, gates, registers or passes on "
            "to a reset chain or reset output port (its copies and that output port included), and chains only synchronizing or "
            "releasing a reset (a reset shift register, a registered copy of a reset), are not conceptual assets under any question. "
            "Settings or requests controlling a clock (an enable, a rate) are judged as usual, and so is a decision triggering a reset "
            "(a timeout, a violation), where it is computed.")
R2B_LINE = ("- Pacing pulses. A tick, edge pulse or divider count made inside the unit only to pace another step, or an input port "
            "whose only use is a condition letting such a tick or count advance, is part of that step or its rate setting (step 3), "
            "unless an output port carries that pulse itself (2.2); an output port that such pulses only decide or time does not "
            "count. Do not name it in any concept's information or cite its lines as held lines. A request held until it is served, "
            "a start pulse decoded from a received command, and a step counter are not pacing pulses.")
K1_LINE = ("- Register read-back. In a unit executing instructions, the word an instance outputs for reads of its control and status "
           "registers, when a statement of this unit merges it directly into the value written back to a register, is its own "
           "piece: those registers' contents as software reads them. Judge which output that is from port names (section 1's "
           "second exception) and say so. Hold it at that instance output. No step-3 clause or other rule folds it, and the read "
           "words other instances pass into that instance are not part of it.")
HANDOFF_OLD = "No step-3 clause or other rule folds it, even when it travels with the data it qualifies."
EDITS = [
    ("R1", "phase2.md",
     'the element that holds or makes it. If none qualifies for a conceptual asset, say why in "notes".',
     'the element that holds or makes it. A bus request or response record port, or any field of one, never qualifies (2.6), '
     'even when it is the only port the conceptual asset enters or leaves through. If none qualifies for a conceptual asset, say why in "notes".'),
    ("R4", "common.md", "(a forwarding wire, a copy kept only while the value moves,",
     "(a forwarding wire, a synchronizer stage re-sampling an input port's value, a copy kept only while the value moves,"),
    ("R7b", "phase1.md",
     "- Clocks and resets. Clock and reset inputs, and chains only synchronizing or releasing a reset (a reset shift register, a "
     "registered copy of a reset), are not conceptual assets under any question. Settings or requests controlling a clock (an "
     "enable, a rate), and decisions triggering a reset (a timeout, a violation), are judged as usual.", R7B_LINE),
    ("R2b", "phase1.md",
     "- Pacing pulses. A tick, edge pulse or divider count made inside the unit only to pace another step is part of that step or "
     "its rate setting (step 3), unless the unit outputs it. Do not name it in any concept's information or cite its lines as held "
     "lines. A request held until it is served, a start pulse decoded from a received command, and a step counter are not pacing pulses.",
     R2B_LINE),
    ("R5", "phase1.md", "with no statement of this unit reading or writing it; in a unit executing instructions",
     "with no statement of this unit reading or writing it (a constant tied to it in a generate branch where the instance is absent "
     "is no such statement), even though the black-box rule lets the instance change it; in a unit executing instructions"),
    ("R3", "phase1.md", "not concepts of their own. Do not name a synchronizer stage",
     "not concepts of their own. So are the state and flag made inside a debiasing step to choose which raw bits it accepts: although "
     "step 2 would call them a decision, they only shape that result, like a compare picking a minimum (step 3). Do not name a synchronizer stage"),
    ("K2", "phase1.md", HANDOFF_OLD,
     "No step-3 clause or other rule folds it, even when it travels with the data it qualifies, or when it is only one bit of a count: "
     "then hold it at the line assigning that bit to the instance output, and a count kept only to make it belongs to this piece."),
]
K1_ANCHOR = "and a count kept only to make it belongs to this piece."   # end of the Hand-offs line after K2; K1 goes on the next line


def apply(text, old, new, rid):
    n = text.count(old)
    assert n == 1, f"{rid}: expected the old text once, found {n}: {old[:80]}"
    return text.replace(old, new)


def main(force=False):
    if V5.exists() and not force:
        raise SystemExit(f"{V5} exists; use --force to rebuild")
    V5.mkdir(exist_ok=True)   # files are overwritten below; the folder is kept (a shell may have it as its working directory)
    for f in ("common.md", "phase1.md", "phase2.md", "phase1_user.md", "phase2_user.md"):
        shutil.copyfile(V4A / f, V5 / f)
    T = {f: (V5 / f).read_text(encoding="utf-8") for f in ("common.md", "phase1.md", "phase2.md")}
    log = []
    for rid, f, old, new in EDITS:
        T[f] = apply(T[f], old, new, rid)
        log.append((rid, f))
    # K1: a new rule bullet right after the Hand-offs line
    i = T["phase1.md"].index(K1_ANCHOR) + len(K1_ANCHOR)
    assert T["phase1.md"][i] == "\n"
    T["phase1.md"] = T["phase1.md"][:i] + "\n" + K1_LINE + T["phase1.md"][i:]
    log.append(("K1", "phase1.md"))
    # U rules (restrictions), from u_rules.json: [{id, file, old, new | insert_after}]
    U = json.loads((HERE / "u_rules.json").read_text(encoding="utf-8")) if (HERE / "u_rules.json").exists() else []
    for u in U:
        f = u["file"]
        if "insert_after" in u:
            a = u["insert_after"]
            assert T[f].count(a) == 1, f"{u['id']}: anchor not found once"
            j = T[f].index(a) + len(a)
            assert T[f][j] == "\n", f"{u['id']}: anchor must end a line"
            T[f] = T[f][:j] + "\n" + u["new"] + T[f][j:]
        else:
            T[f] = apply(T[f], u["old"], u["new"], u["id"])
        log.append((u["id"], f))
    # conflict fixes (v5_fixes.json, from the v5 conflict check), applied in order after all rules
    FX = json.loads((HERE / "v5_fixes.json").read_text(encoding="utf-8")) if (HERE / "v5_fixes.json").exists() else []
    for x in FX:
        T[x["file"]] = apply(T[x["file"]], x["old"], x["new"], x["id"])
        log.append((x["id"], x["file"]))
    for f, t in T.items():
        (V5 / f).write_text(t, encoding="utf-8")
    print("two_phase_v5 written; edits applied:", ", ".join(f"{r} ({f})" for r, f in log))


if __name__ == "__main__":
    main("--force" in sys.argv)
