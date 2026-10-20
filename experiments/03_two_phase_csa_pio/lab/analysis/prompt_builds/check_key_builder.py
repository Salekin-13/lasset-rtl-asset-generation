"""Check that the diagram builder (pio_blocks.py, friendly-hopper worktree) and the inputs it feeds agree on the ARROWS key:
- pio_blocks.ARROWS_KEYS["v1"] equals make_inputs_v1k.KEY_V1 and ARROWS_KEYS["v1k"] equals KEY_V1K;
- text(m, lines=False, key="v1") rebuilds every lab/inputs/v1 diagram.txt byte for byte;
- text(m, lines=False, key="v1k") rebuilds every lab/inputs/v1k diagram.txt byte for byte.

  python check_key_builder.py [path to the folder holding pio_blocks.py]
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
BUILDER = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path(r"E:\jobs\ff\test\Prepoison_subset\.claude\worktrees\friendly-hopper-2fb731\final\pio")
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BUILDER))
import make_inputs_v1k as MK  # noqa: E402
import pio_blocks as B  # noqa: E402


def main():
    assert B.ARROWS_KEYS["v1"] == MK.KEY_V1, "builder v1 key differs from make_inputs_v1k.KEY_V1"
    assert B.ARROWS_KEYS["v1k"] == MK.KEY_V1K, "builder v1k key differs from make_inputs_v1k.KEY_V1K"
    bad = []
    for ver in ("v1", "v1k"):
        man = json.loads((LAB / "inputs" / ver / "manifest.json").read_text(encoding="utf-8"))
        n = 0
        for m, d in man["modules"].items():
            want = (LAB / "inputs" / ver / d["split"] / m / "diagram.txt").read_bytes()
            # pio_inputs writes with Path.write_text (text mode), so on Windows each "\n" is stored as os.linesep
            got = B.text(m, lines=False, key=ver).replace("\n", os.linesep).encode("utf-8")
            n += 1
            if got != want:
                bad.append((ver, m))
        print(f"{ver}: {n - sum(1 for b in bad if b[0] == ver)} of {n} diagrams rebuilt byte for byte")
    assert not bad, bad
    print("PASS: builder keys equal make_inputs_v1k's; v1 and v1k diagrams rebuild exactly")


if __name__ == "__main__":
    main()
