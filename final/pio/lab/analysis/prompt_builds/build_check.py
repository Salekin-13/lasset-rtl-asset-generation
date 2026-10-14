"""Code checks for a new two-phase prompt version against two_phase_v2.

  python build_check.py <version> [--common-changed] [--phase1-changed]

Checks: the project prompt checker (check_lab_prompt.check: corpus names, numeric hints, final-JSON phrase; self-test
inside); which files differ from v2 (must match the flags); phase1.md OUTPUT block (from the line 'OUTPUT') identical to
v2 except the 'merged into Cn' placeholder; every JSON key of v2's OUTPUT block present; common.md section heads 1-4 and
2.1-2.9, 4.1-4.4 and 1(a)-(c) present; phase1.md step numbers 1-6 and the rule bullet heads present; word counts.
"""
import re
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB))
import check_lab_prompt as CK  # noqa: E402

FILES = ("common.md", "phase1.md", "phase2.md", "phase1_user.md", "phase2_user.md")
HEADS_COMMON = ["1. WHAT YOU ARE GIVEN", "(a) RTL", "(b) CLOSED SET", "(c) DIAGRAM", "2. DEFINITIONS", "2.1 ", "2.2 ", "2.3 ", "2.4 ", "2.5 ",
                "2.6 ", "2.7 ", "2.8 ", "2.9 ", "3. ", "4. ", "4.1 ", "4.2 ", "4.3 ", "4.4 "]
BULLETS = ["Clocks and resets.", "Build-time values.", "Pacing pulses.", "Forwarded transactions.", "Bus handshake copies.", "Working values."]


def words(t):
    return len(t.split())


def main(version, common_changed=False, phase1_changed=False):
    ok = True
    d, v2 = LAB / "prompts" / version, LAB / "prompts" / "two_phase_v2"
    print(f"== {version}")
    ok &= CK.check(version)
    for f in FILES:
        same = (d / f).read_text(encoding="utf-8") == (v2 / f).read_text(encoding="utf-8")
        want_same = not ((f == "common.md" and common_changed) or (f == "phase1.md" and phase1_changed))
        flag = "ok" if same == want_same else "UNEXPECTED"
        ok &= same == want_same
        print(f"  {f}: {'identical to v2' if same else 'changed'} ({flag}); words v2 {words((v2 / f).read_text(encoding='utf-8'))} -> {words((d / f).read_text(encoding='utf-8'))}")
    p1, p1v2 = (d / "phase1.md").read_text(encoding="utf-8"), (v2 / "phase1.md").read_text(encoding="utf-8")
    out, outv2 = p1[p1.index("\nOUTPUT"):], p1v2[p1v2.index("\nOUTPUT"):]
    norm = lambda t: re.sub(r"'merged into Cn'[^>]*>", "'merged into Cn'>", t)  # noqa: E731
    o_same = norm(out) == norm(outv2)
    keys = set(re.findall(r'"([a-z][a-z ,]*)":', outv2))
    missing = sorted(k for k in keys if f'"{k}":' not in out)
    print(f"  OUTPUT block identical to v2 (placeholder aside): {o_same}; JSON keys missing: {missing or 'none'}")
    ok &= not missing
    if not o_same:
        import difflib
        for l in difflib.unified_diff(outv2.splitlines(), out.splitlines(), lineterm="", n=0):
            if l.startswith(("+", "-")) and not l.startswith(("+++", "---")):
                print("    " + l[:200])
    com = (d / "common.md").read_text(encoding="utf-8")
    mh = [h for h in HEADS_COMMON if h not in com]
    steps = [s for s in range(1, 7) if not re.search(rf"^\s*{s}\. ", p1, re.M)]
    mb = [b for b in BULLETS if b not in p1]
    print(f"  common.md heads missing: {mh or 'none'}; phase1 steps missing: {steps or 'none'}; rule bullet heads missing: {mb or 'none'}")
    ok &= not mh and not steps and not mb
    print(f"  RESULT: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    sys.exit(0 if main(a[0], "--common-changed" in a, "--phase1-changed" in a) else 1)
