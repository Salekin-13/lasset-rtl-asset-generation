"""Staged prompt edit that goes with inputs v1k (exact diagram key line): in a NEW prompt version's common.md, replace the
1(c) stopgap sentence that calls the key line shorthand. Run it only on a new version folder that will be run with
PIO_INPUT_VERSION=v1k; versions run on inputs v1 keep the stopgap.

  python apply_key_fix.py <new prompt version>          (for example two_phase_v5)

Recognizes the v2 wording and the shorter v2a/v4a wording; refuses anything else, and refuses v1-era folders that runs
already used (two_phase_v1, v2, v2a, v3, v4, v4a).
"""
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
OLD = ["The diagram writes a one-line key after the word ARROWS; the key is shorthand, and where it differs, this section and 2.2 decide.",
       "The one-line key after the word ARROWS is shorthand; where it differs, this section and 2.2 decide."]
# Keeps a tie-breaker (skeptic check wf_599c5f7c-0e1): a one-line key cannot carry every detail of 1(c) and 2.2.
NEW = "The one-line key after the word ARROWS summarizes this section and 2.2; they decide anything the key leaves out or states differently."
USED = {"two_phase_v1", "two_phase_v2", "two_phase_v2a", "two_phase_v3", "two_phase_v4", "two_phase_v4a"}


def main(version):
    if version in USED:
        raise SystemExit(f"{version} already has runs on inputs v1; make a new version folder first")
    p = LAB / "prompts" / version / "common.md"
    t = p.read_text(encoding="utf-8")
    hits = [o for o in OLD if o in t]
    if len(hits) != 1 or t.count(hits[0]) != 1:
        raise SystemExit(f"expected exactly one known stopgap sentence in {p}; found {len(hits)}")
    p.write_text(t.replace(hits[0], NEW), encoding="utf-8")
    print(f"{p}: replaced\n  {hits[0]}\nwith\n  {NEW}")


if __name__ == "__main__":
    main(sys.argv[1])
