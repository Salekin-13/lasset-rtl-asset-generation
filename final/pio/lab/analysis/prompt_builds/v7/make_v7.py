"""Build two_phase_v7 = two_phase_v6d (the final condensed prompt) + five narrowings of rules the v6 run showed the
model applying beyond their text (user request 2026-10-13; recommendations in
analysis/two_phase_v6__gpt-5.6-luna__high__r0-r2/V6_RESULTS.md): CX2.U3b, CX4.TF1, CX1-ACF, P11.5, LS1.

The edits come from the workflow wf_88588443-cb4 (one drafter and one checker per rule; saved as edits.json). Each
edit is applied as an exact replacement, in rule order: its "old" text must occur exactly once in the current file
(after the edits before it), or the build stops.

Checks:
  - the project prompt checker (corpus identifiers, banned words, numeric hints);
  - chain.new_format;
  - the OUTPUT sections byte-identical to v6d;
  - every sentence of 6 or more words that both phase bodies shared in v6d is still in both, or gone from both;
  - per rule, the words added;
  - the shas.

  python make_v7.py            (dry run: prints the plan and the checks, writes nothing)
  python make_v7.py --write
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
sys.path.insert(0, str(LAB))
import check_lab_prompt as CK  # noqa: E402
import chain as CH  # noqa: E402

SRC = LAB / "prompts" / "two_phase_v6d"
DST = LAB / "prompts" / "two_phase_v7"
FILES = ("common.md", "phase1.md", "phase2.md")
ORDER = ("CX2.U3b", "CX4.TF1", "CX1-ACF", "P11.5", "LS1", "REVIEW")   # REVIEW: fixes from the combined read-through
SPL = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\-\[])")


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def body(t):
    return t[:t.index("\nOUTPUT\n")]


def sentences(t):
    return {s.strip() for line in t.split("\n") for s in SPL.split(line) if len(s.split()) >= 6}


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    E = json.loads((HERE / "edits.json").read_text(encoding="utf-8"))
    by_rule = {x["rule"]: x["edits"] for x in E}
    texts = {f: (SRC / f).read_text(encoding="utf-8") for f in FILES}
    orig = dict(texts)
    ok, log = True, []
    for rule in ORDER:
        before = sum(len(texts[f].split()) for f in FILES)
        for e in by_rule.get(rule, []):
            f, old, new = e["file"], e["old"].replace("\r\n", "\n"), e["new"].replace("\r\n", "\n")
            n = texts[f].count(old)
            if n != 1:
                log.append(f"{rule}: {f}: old text found {n} times: {old[:80]!r}")
                ok = False
                continue
            texts[f] = texts[f].replace(old, new)
        log.append(f"{rule}: {len(by_rule.get(rule, []))} edits, words {sum(len(texts[f].split()) for f in FILES) - before:+d}")
    shared_before = sentences(body(orig["phase1.md"])) & sentences(body(orig["phase2.md"]))
    s1, s2 = sentences(body(texts["phase1.md"])), sentences(body(texts["phase2.md"]))
    broken = sorted(s for s in shared_before if (s in s1) != (s in s2))
    if broken:
        ok = False
        log += [f"shared sentence now in one phase file only: {s[:100]!r}" for s in broken]
    for f in ("phase1.md", "phase2.md"):
        if texts[f][texts[f].index("\nOUTPUT\n"):] != orig[f][orig[f].index("\nOUTPUT\n"):]:
            ok = False
            log.append(f"{f}: the OUTPUT section changed")
    print("\n".join(log))
    w = {f: (len(orig[f].split()), len(texts[f].split())) for f in FILES}
    print("words:", {f: f"{a} -> {b} ({b - a:+d})" for f, (a, b) in w.items()})
    if write and ok:
        DST.mkdir(exist_ok=True)
        for f in ("phase1_user.md", "phase2_user.md"):
            shutil.copyfile(SRC / f, DST / f)
        for f in FILES:
            (DST / f).write_bytes(texts[f].replace("\n", "\r\n").encode("utf-8"))
        chk = bool(CK.check("two_phase_v7", log=lambda *a: None))
        nf = CH.new_format("two_phase_v7", 1) and CH.new_format("two_phase_v7", 2)
        ok &= chk and nf
        print(f"checker {chk}; new_format {nf}; shas {sha(CK.system('two_phase_v7', 1))} / {sha(CK.system('two_phase_v7', 2))}")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
