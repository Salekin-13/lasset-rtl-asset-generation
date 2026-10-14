"""Read-only check of the condensed versions against two_phase_v6 (writes nothing).

Per version: words of phase1.md and phase2.md, the Phase 1 and Phase 2 system shas, whether common.md and both user
templates are byte-identical to v6, whether each phase file is byte-identical to v6, and the project prompt checker.

  python verify_versions.py
"""
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
sys.path.insert(0, str(LAB))
import check_lab_prompt as CK  # noqa: E402

VERSIONS = ("two_phase_v6", "two_phase_v6a", "two_phase_v6b", "two_phase_v6c", "two_phase_v6abc")


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    v6 = LAB / "prompts" / "two_phase_v6"
    for ver in VERSIONS:
        d = LAB / "prompts" / ver
        w = {k: len((d / f"{k}.md").read_text(encoding="utf-8").split()) for k in ("phase1", "phase2", "common")}
        same = {f: (d / f).read_bytes() == (v6 / f).read_bytes()
                for f in ("common.md", "phase1_user.md", "phase2_user.md", "phase1.md", "phase2.md")}
        chk = bool(CK.check(ver, log=lambda *a: None))
        print(f"{ver}: words phase1 {w['phase1']}, phase2 {w['phase2']}, common {w['common']}; "
              f"shas {sha(CK.system(ver, 1))} / {sha(CK.system(ver, 2))}; "
              f"same as v6: {', '.join(f for f, s in same.items() if s) or 'none'}; checker {chk}")


if __name__ == "__main__":
    main()
