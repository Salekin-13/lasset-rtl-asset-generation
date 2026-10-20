"""two_phase_v9k = two_phase_v9j + the "Walk-found internals" bar (new_rules/rule_texts_v9k_walk.json, W1, Phase 2 only) inserted
in Phase 2 step 4 as the last bar block, right before the first keep block ("- Control record ports."). Phase 1, common.md and
the user templates are byte-identical to v9j. User 2026-10-18: "Build the Walk-found internals rule as two_phase_v9k (Phase 2
step 4, last bar before the keep blocks)". Builds the prompt folder only; sends nothing.

  python -B make_v9k.py [--write]
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
sys.path.insert(0, str(HERE))
import make_v10 as M  # noqa: E402

CK, CH = M.CK, M.CH
SRC, DST = "two_phase_v9j", "two_phase_v9k"
FIRST_KEEP = "- Control record ports."
LAST_BAR = "- Processor control-unit state."


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    texts = json.loads((HERE / "new_rules" / "rule_texts_v9k_walk.json").read_text(encoding="utf-8"))
    r = subprocess.run([sys.executable, "-B", str(HERE / "check_new_rules.py"), str(HERE / "new_rules" / "rule_texts_v9k_walk.json")], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout[-300:].strip())
    if r.returncode:
        sys.exit("checker BLOCKERS")
    w1 = texts["W1"]["P2"].strip("\n")
    body = (LAB / "prompts" / SRC / "phase2.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    i4, i5 = body.index("\n4. Primary."), body.index("\n5. Secondary.")
    step4 = body[i4:i5]
    assert step4.count("\n" + FIRST_KEEP) == 1, "first keep block not found once in step 4"
    k = step4.index("\n" + FIRST_KEEP)
    before = step4[:k].rstrip("\n")
    last_block_head = [l for l in before.split("\n") if l.startswith("- ")][-1]
    assert last_block_head.startswith(LAST_BAR), f"the block before the keep blocks is {last_block_head[:40]!r}, not {LAST_BAR!r}"
    new_step4 = before + "\n" + w1 + step4[k:]
    new_body = body[:i4] + new_step4 + body[i5:]
    assert new_body.count(w1) == 1 and new_body.index(w1) < new_body.index("\n" + FIRST_KEEP) and new_body.index(w1) > new_body.index(LAST_BAR)
    print(f"W1 {len(w1.split())} words inserted after {LAST_BAR!r} and before {FIRST_KEEP!r}; phase2.md words {len(body.split())} -> {len(new_body.split())}")
    if not write:
        return
    crlf = b"\r\n" in (LAB / "prompts" / SRC / "phase2.md").read_bytes()
    d = LAB / "prompts" / DST
    d.mkdir(exist_ok=True)
    for f in ("common.md", "phase1.md", "phase1_user.md", "phase2_user.md"):
        shutil.copyfile(LAB / "prompts" / SRC / f, d / f)
    (d / "phase2.md").write_bytes((new_body.replace("\n", "\r\n") if crlf else new_body).encode("utf-8"))
    (d / "README.md").write_text("# two_phase_v9k: v9j + the Walk-found internals bar (Phase 2 step 4, last bar before the keep blocks); Phase 1 unchanged "
                                 "(built 2026-10-18; analysis/v10_diagnosis/make_v9k.py; FP_V9J_ANALYSIS.md section 2; PLAN_ISOLATE_CLUSTER_ORDER.md section 16)\n", encoding="utf-8")
    chk = bool(CK.check(DST, log=print))
    nf = CH.new_format(DST, 1) and CH.new_format(DST, 2)
    same = all((LAB / "prompts" / SRC / f).read_bytes() == (d / f).read_bytes() for f in ("common.md", "phase1.md", "phase1_user.md", "phase2_user.md"))
    sha1, sha2 = M.sha(CK.system(DST, 1))[:12], M.sha(CK.system(DST, 2))[:12]
    print(f"checker {chk}; new_format {nf}; common.md, phase1.md and user templates identical to v9j {same}; sha12 {sha1} / {sha2} (v9j {M.sha(CK.system(SRC, 1))[:12]} / {M.sha(CK.system(SRC, 2))[:12]})")
    print("ALL CHECKS PASS" if chk and nf and same and sha1 == M.sha(CK.system(SRC, 1))[:12] and sha2 != M.sha(CK.system(SRC, 2))[:12] else "CHECKS FAILED")
    if not (chk and nf and same):
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
