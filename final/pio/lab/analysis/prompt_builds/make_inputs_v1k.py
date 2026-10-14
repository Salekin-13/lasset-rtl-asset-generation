"""Inputs v1k = inputs v1 with an exact ARROWS key line in every diagram.txt (nothing else changes).

The v1 key line, written by final/pio/pio_blocks.py _text_labels, is looser than the prompt's own definitions (common.md
1(c) and 2.2): a "-->" arrow can list an index, which carries its value; brackets can list elements that only decide;
a "==>" arrow into an instance block can carry only a clock or reset, which carries no value; a "==>" arrow into an output
port the block also assigns can list only deciding elements. KEY_V1K states those rules in the prompt's own terms.

Writes lab/inputs/v1k/ (tuning/ and heldout/ copied from v1, diagram.txt key line replaced, new manifest.json and README.md)
and lab/kit_data/v1k.json (v1's kit data with the new manifest sha; its facts do not depend on the key line). v1 is not
touched. Checks: every v1 diagram has the old key line exactly once; every non-diagram file is byte-identical; every
diagram differs from v1 in that one line only; manifest shas are recomputed the way v1's were (verified on v1 first).

  python make_inputs_v1k.py
"""
import hashlib
import json
import shutil
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
V1, V1K = LAB / "inputs" / "v1", LAB / "inputs" / "v1k"
KEY_V1 = "  ARROWS (==> a value moves; --> only decides; [the elements the arrow carries])"
# Revised after two skeptics (workflow wf_599c5f7c-0e1) found five gaps in the first version: an index was said to carry
# always (2.2: not when the picked element is only tested) and only in "-->" arrows; "not all of which carry" read as a
# claim about every arrow; arrows without brackets and [inst] brackets naming another IP's port were not covered.
# Round 2 (wf_ad57388c-265): "otherwise ... it only decides" wrongly covered 10 index-tagged elements with an explicit flow
# (9 "==>" arrows), so the clause now limits only the index route; whole-record moves and "directly" (1(c) line 53) added.
KEY_V1K = ("  ARROWS (A ==> B: at least one listed element has an explicit flow into B, or B is an output port that A's own statements also assign; "
           "A --> B: no listed element has an explicit flow into B, and each one decides B or is an index; "
           "in either arrow, a listed element carries its value as an index only when the array element or slice it picks is read or "
           "written in an assignment to B, not when that element is only tested (2.2); "
           "[...]: A's elements the arrow stands for (rec.{a,b} is rec.a and rec.b; if the whole record rec also moves, it is not named "
           "separately), some of which may only decide; "
           "from an [inst] block whose port map writes output port B directly: the instance's own port (under the child entity if the instance "
           "is of this file; in no list if it is another IP's), left out when it has B's name; "
           "no [...] from any other block: A's own statements assign output port B, perhaps with constants only; "
           "a clock or reset wired into an instance block is drawn ==> and carries no value)")


KEYS = [0]


def sha12(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def main():
    man = json.loads((V1 / "manifest.json").read_text(encoding="utf-8"))
    # how v1's file shas were computed: check on every file before writing anything
    for m, d in man["modules"].items():
        for f, s in d["files"].items():
            assert sha12(V1 / d["split"] / m / f) == s, ("v1 sha rule", m, f)
    if V1K.exists():   # delete its files, keep its folders (a shell may have one as its working directory)
        for c in sorted(V1K.rglob("*"), reverse=True):
            if c.is_file():
                c.unlink()
            elif not any(c.iterdir()):
                try:
                    c.rmdir()
                except PermissionError:
                    pass
    new = {**man, "version": "v1k", "built": "2026-10-12", "sources": {**man["sources"], "diagram": man["sources"]["diagram"] +
           " with the ARROWS key line replaced by an exact one (analysis/prompt_builds/make_inputs_v1k.py)"}, "modules": {}}
    for m, d in man["modules"].items():
        src, dst = V1 / d["split"] / m, V1K / d["split"] / m
        dst.mkdir(parents=True, exist_ok=True)
        for f in d["files"]:
            if f != "diagram.txt":
                shutil.copyfile(src / f, dst / f)
                assert (dst / f).read_bytes() == (src / f).read_bytes()
                continue
            raw = (src / f).read_bytes()
            text = raw.decode("utf-8")
            units = sum(1 for l in text.splitlines() if l.startswith("UNIT "))
            assert units >= 1 and text.count(KEY_V1) == units, (m, units, text.count(KEY_V1))   # one key line per unit
            out = text.replace(KEY_V1, KEY_V1K)
            (dst / f).write_bytes(out.encode("utf-8"))
            a, b = text.splitlines(), out.splitlines()
            diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
            assert len(a) == len(b) and len(diff) == units and all(a[i] == KEY_V1 and b[i] == KEY_V1K for i in diff), m
            KEYS[0] += units
        new["modules"][m] = {**d, "files": {f: sha12(dst / f) for f in d["files"]}}
    (V1K / "manifest.json").write_text(json.dumps(new, indent=1), encoding="utf-8")
    (V1K / "README.md").write_text(
        "# Inputs v1k\n\nInputs v1 with one change: the ARROWS key line of every diagram.txt now states the prompt's own arrow "
        "rules (common.md 1(c) and 2.2) instead of the looser shorthand. Built by analysis/prompt_builds/make_inputs_v1k.py, "
        "which checks that nothing else differs from v1. Why, how it was checked, what it breaks and how to test it: "
        "analysis/prompt_builds/DIAGRAM_KEY_FIX.md.\n\nOld key:\n\n    " + KEY_V1.strip() + "\n\nNew key:\n\n    " + KEY_V1K.strip() + "\n",
        encoding="utf-8")
    kd = json.loads((LAB / "kit_data" / "v1.json").read_text(encoding="utf-8"))
    kd["input version"] = "v1k"
    kd["inputs manifest sha"] = hashlib.sha256((V1K / "manifest.json").read_text(encoding="utf-8").encode()).hexdigest()[:12]
    kd["built from"] = f"{kd.get('built from')}; copied for inputs v1k (only the diagram key line differs, which no kit fact uses)"
    (LAB / "kit_data" / "v1k.json").write_text(json.dumps(kd, indent=1, ensure_ascii=False), encoding="utf-8")
    n = len(man["modules"])
    print(f"inputs v1k written: {n} modules, {sum(1 for d in man['modules'].values() if 'diagram.txt' in d['files'])} diagrams changed in "
          f"their key lines only ({KEYS[0]} key lines, one per unit); other files byte-identical; kit_data/v1k.json manifest sha {kd['inputs manifest sha']}")


if __name__ == "__main__":
    main()
