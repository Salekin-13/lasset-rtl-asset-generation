"""Compare two blind boundary tests on the same stored v5g replies, element by element: v6 (long) vs a condensed
version. Both were scored by analysis/two_phase_v5g__.../boundary/score_v6.py. For each list (correct lost, correct
gained, false positives removed, false positives added) and each mode (both judges, either judge): the elements in
both, only in v6, only in the condensed version. Same decisions = same lists; the run-level precision and recall are
printed for both.

  python compare_boundary.py <v6 result.json> <condensed result.json>
"""
import json
import re
import sys
from pathlib import Path


def key(s):
    return re.sub(r"\s*\[.*\]$", "", s)          # "r0 bus:locked ['CX4.TF1']" -> "r0 bus:locked"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a, b = (json.loads(Path(p).read_text(encoding="utf-8")) for p in sys.argv[1:3])
    for mode in ("both", "either"):
        print(f"== {mode} judge(s)")
        for r in ("0", "1", "2"):
            sa, sb = a[mode]["score"][r], b[mode]["score"][r]
            print(f"  r{r}: precision v6 {sa['precision']} vs condensed {sb['precision']}; recall v6 {sa['recall']} vs condensed {sb['recall']}")
        for lst in ("correct lost", "correct gained", "false positives removed", "false positives added"):
            A, Bs = {key(x) for x in a[mode][lst]}, {key(x) for x in b[mode][lst]}
            print(f"  {lst}: v6 {len(A)}, condensed {len(Bs)}, in both {len(A & Bs)}; only v6 {sorted(A - Bs)[:12]}{' ...' if len(A - Bs) > 12 else ''}; "
                  f"only condensed {sorted(Bs - A)[:12]}{' ...' if len(Bs - A) > 12 else ''}")


if __name__ == "__main__":
    main()
