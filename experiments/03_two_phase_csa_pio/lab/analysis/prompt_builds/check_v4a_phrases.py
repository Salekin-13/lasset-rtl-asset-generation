"""Code check for two_phase_v4a/phase1.md: every protected phrase of v4 is still there word for word, the OUTPUT block
is byte-identical to v4's, "If so" did not come back, and the rule bullet heads are in v4's order. Self-test: every
phrase is first required to be present in v4's own phase1.md.

  python check_v4a_phrases.py
"""
import re
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
V4, V4A = LAB / "prompts" / "two_phase_v4" / "phase1.md", LAB / "prompts" / "two_phase_v4a" / "phase1.md"
PHRASES = [
    "Merging the bus responses of several ports into one (an OR or a multiplexer) is still forwarding",
    "with no statement of this unit reading or writing it",
    "this does not cover the instructions it executes or the data it loads and stores",
    "Do not name it in any concept's information or cite its lines as held lines",
    "A request held until it is served, a start pulse decoded from a received command, and a step counter are not pacing pulses",
    "Do not name a synchronizer stage in any concept's information or cite its lines as held lines",
    "stored state with a request, a count with a stored limit, or a written value with a fixed value",
    "even when it lasts one cycle",
    "never merge it into its inputs or the action it triggers",
    "A wait or fault flag, a write-enable flag, or an access address",
    "No step-3 clause or other rule folds it",
    "Phase 2 sees only kept concepts and starts from their held lines",
    "Assume the IP is to be integrated into an IC where confidentiality protections are required",
    "Assume the IP is to be integrated into an IC where integrity protections are required",
]
HEADS = ["Clocks and resets.", "Build-time values.", "Pacing pulses.", "Forwarded transactions.", "Bus handshake copies.",
         "Working values.", "Hand-offs."]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    old, new = V4.read_text(encoding="utf-8"), V4A.read_text(encoding="utf-8")
    norm = lambda t: " ".join(t.split())  # noqa: E731
    ok = True
    for p in PHRASES:
        assert p in norm(old), f"self-test: phrase not in v4: {p}"
    for p in PHRASES:
        if p not in norm(new):
            ok = False
            print("MISSING:", p)
    n_old, n_new = old.count("If the first part holds"), new.count("If the first part holds")
    print(f"'If the first part holds': v4 {n_old}, v4a {n_new}; 'If so': v4a {len(re.findall(r'If so\b', new))}")
    ok &= n_new == n_old and not re.search(r"If so\b", new)
    out_old, out_new = old[old.index("\nOUTPUT"):], new[new.index("\nOUTPUT"):]
    print("OUTPUT block identical to v4:", norm(out_old) == norm(out_new))
    ok &= norm(out_old) == norm(out_new)
    pos = [new.find("- " + h) for h in HEADS]
    print("rule bullet heads in order:", all(p >= 0 for p in pos) and pos == sorted(pos))
    ok &= all(p >= 0 for p in pos) and pos == sorted(pos)
    before = lambda t: t[: t.index("\nOUTPUT")]  # noqa: E731
    wo, wn = len(before(old).split()), len(before(new).split())
    print(f"words before OUTPUT: v4 {wo}, v4a {wn} ({(wo - wn) / wo:.1%} fewer); whole file v4 {len(old.split())}, v4a {len(new.split())}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
