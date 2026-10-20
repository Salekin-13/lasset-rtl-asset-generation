"""Prepare the Phase 2-only test of two_phase_v5g (no model call; copies stored files only).

  arm:     runs/two_phase_v5g__v1/gpt-5.6-luna__high/r0..r2/phase1/  <- v5f r0..r2 phase1 replies
  control: runs/two_phase_v5f__v1/gpt-5.6-luna__high/r3..r5/phase1/  <- v5f r0..r2 phase1 replies (v5f's own Phase 2
           is then rerun on the same Phase 1, to measure Phase 2's run-to-run spread)
chain._ask reuses a stored record only for the exact same system and user message, so each copied record is checked
against today's Phase 1 message of its target version before it is written. Nothing is overwritten.
Never pool r3-r5 with v5f's r0-r2 (different design: Phase 1 reused).

  python prepare_phase2_only.py            (dry run: prints the plan and the checks)
  python prepare_phase2_only.py --apply    (copies)
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402

MODEL, EFF = "gpt-5.6-luna", "high"
PLAN = [("two_phase_v5g", src, src) for src in (0, 1, 2)] + [("two_phase_v5f", src, src + 3) for src in (0, 1, 2)]


def main(apply=False):
    sys.stdout.reconfigure(encoding="utf-8")
    ok, todo = True, []
    for version, src, dst in PLAN:
        s_dir = CH.run_dir("two_phase_v5f", MODEL, src, EFF) / "phase1"
        d_dir = CH.run_dir(version, MODEL, dst, EFF) / "phase1"
        sys1 = CH.sha12(CH.C.system(version, 1))
        for m in CH.tuning_modules():
            rec = json.loads((s_dir / f"{m}.json").read_text(encoding="utf-8"))
            want = (sys1, CH.sha12(CH.user_message(version, 1, m)))
            match = (rec.get("system sha"), rec.get("user sha")) == want
            exists = (d_dir / f"{m}.json").exists()
            ok &= match and not exists
            if not match or exists:
                print(f"  PROBLEM {version} r{dst} {m}: sha match {match}, target exists {exists}")
            todo.append((s_dir / f"{m}.json", d_dir / f"{m}.json"))
        print(f"{version} r{dst} <- v5f r{src}: {len(CH.tuning_modules())} Phase 1 replies, Phase 1 system sha {sys1}")
    print("checks:", "PASS" if ok else "FAIL", f"({len(todo)} files)")
    if apply and ok:
        for s, d in todo:
            d.parent.mkdir(parents=True, exist_ok=True)
            d.write_bytes(s.read_bytes())
        print("copied", len(todo), "files")
    elif apply:
        print("nothing copied")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main("--apply" in sys.argv) else 1)
