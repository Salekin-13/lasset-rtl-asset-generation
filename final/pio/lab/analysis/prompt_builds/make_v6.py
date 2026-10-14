"""Build prompt version two_phase_v6 = two_phase_v5g + the v6 rules (user request 2026-10-13: from the v5g failure
analysis, consistent Phase 1 + Phase 2 rules against FP-causing extra concepts without losing correct finds, and narrow
recall rules plus a Phase 2 diagram-walk instruction).

Source text: analysis/two_phase_v5g__gpt-5.6-luna__high__r0-r2/rules/v6_candidate/ (make_candidate.py: the rules
workflow wf_ce0308e1-806's integrated text, rebuilt by re-running its integrator's own build code; system shas matched
its report). 24 rules; NC.SCR, NC.FIFOb and NC.K2SW held for the user's decision; W2 left for a separate arm.
Blind boundary test (wf_b1d6d6cc-c10, score_v6.py): 0 correct finds lost by either judge.
Checks: the files equal the candidate; system shas e815598c3dda / 773926fea6fb; the OUTPUT sections (reply format)
are byte-identical to v5g's; the project prompt checker; the runner reads the format (chain.new_format); words.

  python make_v6.py            (refuses to overwrite an existing two_phase_v6 unless --force)
"""
import hashlib
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
import check_lab_prompt as CK  # noqa: E402

P = LAB / "prompts"
V5G, V6 = P / "two_phase_v5g", P / "two_phase_v6"
CAND = LAB / "analysis" / "two_phase_v5g__gpt-5.6-luna__high__r0-r2" / "rules" / "v6_candidate"
WANT = {1: "e815598c3dda", 2: "773926fea6fb"}


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def output_block(t):
    i = t.rfind("\nOUTPUT")
    return t[i:] if i >= 0 else None


def main(force=False):
    sys.stdout.reconfigure(encoding="utf-8")
    if V6.exists() and not force:
        raise SystemExit(f"{V6} exists; use --force to rebuild")
    V6.mkdir(exist_ok=True)
    for f in ("common.md", "phase1.md", "phase2.md"):
        shutil.copyfile(CAND / f, V6 / f)
    for f in ("phase1_user.md", "phase2_user.md"):
        shutil.copyfile(V5G / f, V6 / f)
    ok = True
    for ph in (1, 2):
        s = sha(CK.system("two_phase_v6", ph))
        print(f"Phase {ph} system sha12 {s} (want {WANT[ph]}): {'ok' if s == WANT[ph] else 'DIFFERENT'}")
        ok &= s == WANT[ph]
        a = output_block((V6 / f"phase{ph}.md").read_text(encoding="utf-8"))
        b = output_block((V5G / f"phase{ph}.md").read_text(encoding="utf-8"))
        print(f"  phase{ph}.md OUTPUT section identical to v5g: {a == b}")
        ok &= a == b
    for f in ("phase1_user.md", "phase2_user.md"):
        same = (V6 / f).read_bytes() == (V5G / f).read_bytes()
        print(f"  {f} byte-identical to v5g: {same}")
        ok &= same
    ok &= bool(CK.check("two_phase_v6"))
    import chain as CH
    nf = CH.new_format("two_phase_v6", 1) and CH.new_format("two_phase_v6", 2)
    print("runner reads the reply format (chain.new_format):", nf)
    ok &= nf
    for f in ("common.md", "phase1.md", "phase2.md"):
        print(f"  words {f}: v5g {len((V5G / f).read_text(encoding='utf-8').split())} -> v6 {len((V6 / f).read_text(encoding='utf-8').split())}")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main("--force" in sys.argv) else 1)
