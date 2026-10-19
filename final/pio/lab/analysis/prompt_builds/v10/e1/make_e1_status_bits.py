"""E1 fix for Buffer and engine status bits (P1-17), user 2026-10-16: "Before building v10, apply the E1 gloss fix to
Buffer and engine status bits and test that rule alone first."

Source of the fix: the v10r diagnosis (workflow wf_31b2e8b5-c7a, V10R_RETEST_RESULTS.md "Better at the main target,
plus a new narrow misreading"): two edits, the same in both phases.
  1. Scope: "a status bit a bus read returns" -> "a status bit in the data a bus read returns" (response acknowledge and
     error lines are not data; the diagnosis: wrong bars on response ack / err ports, 6/14 element-runs in Phase 1,
     14/14 in Phase 2).
  2. Gloss: "(state register, counter, or busy or done flag derived from them)" -> Sequencing state's own words, so
     that rule's exclusions (timer counts, their compare flags, error and reset records) are not swept in. The
     diagnosis wrote "a state register or bit, phase, word or step counter"; Sequencing state's adopted wording
     (prompt_builds/v10f/A_final.json) now says "a state machine's state register ... or a bit counter, phase counter,
     word counter or step counter" (the short list was split by runs; FACTS_SPEC.md fix 3), so its current words are used.
Falsifier (the diagnosis's, kept): the fix fails if a run bars gptmr irq_pnd, timer.count or timer.match, debug_dm
cmderr or hart_reset, or any response ack / err port, or if the FIFO-flag and busy targets drop.

Reads dossiers/G5_final.json (never edited); writes e1/P1-17_final.json in the shape make_v10.finals() reads. Checks:
each edit matches exactly once in each of the four text fields; the project prompt check (check_rule_draft.py rules:
corpus names, numeric hints, banned words, slots) passes; word counts. The fix is not in current_rules.json: it goes
there only if its rule-alone test passes and the user agrees.

  python -B make_e1_status_bits.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V10 = HERE.parent
RID = "P1-17"
EDITS = [
    ("Scope: a status bit a bus read returns.", "Scope: a status bit in the data a bus read returns."),
    ("A status bit a bus read returns is", "A status bit in the data a bus read returns is"),
    ("(state register, counter, or busy or done flag derived from them)",
     "(a state machine's state register, a bit counter, phase counter, word counter or step counter, or a busy or done "
     "flag decoded from one)"),
]
FIELDS = ("P1_flat", "P1_structured", "P2_flat", "P2_structured")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    src = json.loads((V10 / "dossiers" / "G5_final.json").read_text(encoding="utf-8"))[RID]
    out = dict(src)
    bad = []
    for f in FIELDS:
        t = src[f]
        for old, new in EDITS:
            n = t.count(old)
            if old.startswith("Scope:") and "structured" not in f or old.startswith("A status") and "flat" not in f:
                if n:
                    bad.append(f"{f}: unexpected match of {old[:30]!r}")
                continue
            if n != 1:
                bad.append(f"{f}: {old[:40]!r} matches {n} times")
                continue
            t = t.replace(old, new)
        out[f] = t
    if bad:
        for b in bad:
            print("PROBLEM", b)
        sys.exit(1)
    p = HERE / f"{RID}_final.json"
    p.write_text(json.dumps({RID: out}, indent=1, ensure_ascii=False), encoding="utf-8")
    chk = subprocess.run([sys.executable, "-B", str(V10 / "check_rule_draft.py"), str(p)], capture_output=True, text=True,
                         encoding="utf-8")
    print(chk.stdout[-3000:] or chk.stderr[-3000:])
    for f in FIELDS:
        print(f"{f}: {len(src[f].split())} -> {len(out[f].split())} words")
    if chk.returncode != 0:
        print("PROBLEM: check_rule_draft.py failed")
        sys.exit(1)
    print(f"written {p.name}")


if __name__ == "__main__":
    main()
