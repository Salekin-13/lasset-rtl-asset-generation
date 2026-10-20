"""Copy a version's stored Phase 1 replies (v6's by default) into another version's run folders, for a Phase 2-only run (no model call; copies
stored files only). For a version whose Phase 1 system and user messages are exactly v6's (v6b, v6e): its run then
makes only Phase 2 calls, and v6's own Phase 2 on the same replies is the paired control.

chain._ask reuses a stored record only for the exact same system and user message, so each copied record is checked
against today's Phase 1 message of the target version before it is written. Nothing is overwritten.
(Generalises prepare_v6b_phase2_only.py.)

  python prepare_phase1_copy.py two_phase_v6e                              (dry run: prints the plan and the checks)
  python prepare_phase1_copy.py two_phase_v6e --apply                      (copies v6's replies)
  python prepare_phase1_copy.py two_phase_v6d --from=two_phase_v6abc --apply   (copies v6abc's replies)
  python prepare_phase1_copy.py two_phase_v6abc --from=two_phase_v6abc --to-reps=3,4,5 --apply
      (a Phase 2 rerun of the same version: r0, r1, r2 -> r3, r4, r5, to measure Phase 2's own spread on fixed concepts)
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


def main(version, apply=False, source="two_phase_v6", to_reps=(0, 1, 2)):
    sys.stdout.reconfigure(encoding="utf-8")
    ok, todo = True, []
    for r, t_r in zip((0, 1, 2), to_reps):
        s_dir = CH.run_dir(source, MODEL, r, EFF) / "phase1"
        d_dir = CH.run_dir(version, MODEL, t_r, EFF) / "phase1"
        sys1 = CH.sha12(CH.C.system(version, 1))
        for m in CH.tuning_modules():
            rec = json.loads((s_dir / f"{m}.json").read_text(encoding="utf-8"))
            want = (sys1, CH.sha12(CH.user_message(version, 1, m)))
            match = (rec.get("system sha"), rec.get("user sha")) == want
            exists = (d_dir / f"{m}.json").exists()
            ok &= match and not exists
            if not match or exists:
                print(f"  PROBLEM {version} r{r} {m}: sha match {match}, target exists {exists}")
            todo.append((s_dir / f"{m}.json", d_dir / f"{m}.json"))
        print(f"{version} r{t_r} <- {source} r{r}: {len(CH.tuning_modules())} Phase 1 replies, Phase 1 system sha {sys1}")
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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit("usage: python prepare_phase1_copy.py <version> [--apply]")
    src = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--from=")), "two_phase_v6")
    to = next((tuple(int(x) for x in a.split("=", 1)[1].split(",")) for a in sys.argv[1:] if a.startswith("--to-reps=")), (0, 1, 2))
    if len(to) != 3 or (src == args[0] and set(to) & {0, 1, 2}):
        raise SystemExit("--to-reps needs 3 reps, and a copy within one version must not write into r0-r2")
    sys.exit(0 if main(args[0], "--apply" in sys.argv, src, to) else 1)
