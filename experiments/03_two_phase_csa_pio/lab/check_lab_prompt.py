"""Assemble and check a two-phase lab prompt version: common.md + phase<k>.md = the system prompt of call k.

  python experiments/03_two_phase_csa_pio/lab/check_lab_prompt.py two_phase_v1

Checks (meta_tools.check_prompt, the same as every asset prompt of this project): no corpus identifier, no numeric
emission hint, no instruction to read comments; plus the "only the final JSON object" phrase. A self-test first
plants an identifier and a numeric hint and requires both to be caught.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[2]
for p in (LAB, ROOT / "src", ROOT / "assetgen_meta", ROOT / "bahavioral_patterns_of_assets"):
    sys.path.insert(0, str(p))
import labkit as K  # noqa: E402
import meta_tools as mt  # noqa: E402


def system(version: str, phase: int) -> str:
    d = LAB / "prompts" / version
    return (d / "common.md").read_text(encoding="utf-8").rstrip() + "\n\n" + (d / f"phase{phase}.md").read_text(encoding="utf-8")


def check(version: str, log=print) -> bool:
    # labkit: the reference and closed-set names (pio_run.corpus_names, precomputed) plus meta_tools' own list
    names = K.corpus_names() | mt.corpus_names(str(ROOT))
    plant = mt.check_prompt("Report at most 20 signals such as " + sorted(names)[0], names, "plant")
    ok = len(plant["problems"]) == 3
    log(f"checker self-test (3 planted problems caught): {ok}")
    for k in (1, 2):
        s = system(version, k)
        r = mt.check_prompt(s, names, f"phase {k}")
        if "only the final json object" not in s.lower():
            r["problems"].append("no instruction to return only the final JSON object")
        ok &= not r["problems"]
        log(f"phase {k}: {len(s):,} chars, sha12 {hashlib.sha256(s.encode()).hexdigest()[:12]}, "
            f"{'clean' if not r['problems'] else r['problems']}")
        u = (LAB / "prompts" / version / f"phase{k}_user.md").read_text(encoding="utf-8")
        ru = mt.check_prompt(u, names, f"phase {k} user")
        ok &= not ru["problems"]
        log(f"phase {k} user template: {'clean' if not ru['problems'] else ru['problems']}")
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if check(sys.argv[1] if len(sys.argv) > 1 else "two_phase_v1") else 1)
