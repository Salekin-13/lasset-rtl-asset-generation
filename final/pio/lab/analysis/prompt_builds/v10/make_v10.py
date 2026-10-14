"""Build two_phase_v10 = two_phase_v9 with the critical rules reworded and restructured (user, 2026-10-15: fix the
wording of rules the isolation test found read two ways; give the critical rules a clear structure and decision order;
do not raise word counts unless necessary). The rule texts come from the rewrite workflow (writer, skeptic, reviser per
group of rules; dossiers/G*_final.json), built from dossiers/G*.md and STRUCTURE_SPEC.md.

Edits:
  phase1.md: each critical rule's line is replaced by its structured block; the shared procedure line ("- Reading a
     rule. ...") goes after the "- Precedence." line.
  phase2.md: in the step-4 line (and any other line holding a rule's sentences), the sentences a block replaces are
     removed and the block is inserted where the first of them stood; sentences kept in place get their final text;
     the shared procedure sentence goes before the first block. Every other sentence keeps its text and order.
Checks: the v9 line-34 sentences rebuild the v9 line exactly (so the S-id split is lossless); every S-id of a critical
rule is replaced or kept in place; every non-critical Phase 1 line and Phase 2 sentence is unchanged and in order;
common.md, the OUTPUT sections and the user templates are byte-identical to v9; the project prompt checker
(check_lab_prompt.check) and chain.new_format pass; line ends as v9; words per file and per rule; the shas.

  python make_v10.py            (dry run: plan and checks; writes nothing)
  python make_v10.py --write
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
ISOD = LAB / "analysis" / "rule_isolation_v9"
sys.path.insert(0, str(LAB))
import check_lab_prompt as CK  # noqa: E402
import chain as CH  # noqa: E402

SRC = LAB / "prompts" / "two_phase_v9"
DST = LAB / "prompts" / "two_phase_v10"
FILES = ("common.md", "phase1.md", "phase2.md")
PROC = ("Check its scope, then each criterion, then each exception, in that order. Its outcome follows only for an element "
        "in scope that meets every criterion (one, where marked \"any of\") and that no exception covers; a criterion that "
        "the RTL, or the evidence the rule names, does not show is not met.")
PROC_P1 = "- Reading a rule. " + PROC
PROC_P2 = "Reading a rule below: " + PROC[0].lower() + PROC[1:]


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def finals():
    out = {}
    for f in sorted((HERE / "dossiers").glob("G*_final.json")):
        for rid, d in json.loads(f.read_text(encoding="utf-8")).items():
            if rid in out:
                raise SystemExit(f"{rid} appears in two final files")
            out[rid] = d
    return out


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    idx = json.loads((ISOD / "pack" / "index.json").read_text(encoding="utf-8"))
    dix = json.loads((HERE / "dossiers" / "index.json").read_text(encoding="utf-8"))
    texts = json.loads((ISOD / "rule_texts.json").read_text(encoding="utf-8"))
    F = finals()
    ok, log = True, []
    missing = sorted(set(dix) - set(F))
    if missing:
        ok = False
        log.append(f"no final text for {missing}")
    orig = {f: (SRC / f).read_text(encoding="utf-8").replace("\r\n", "\n") for f in FILES}
    # Phase 1
    p1 = orig["phase1.md"].split("\n")
    new1 = []
    for i, line in enumerate(p1, 1):
        rid = next((r for r, x in idx["p1"].items() if x["line"] == i and r in F), None)
        if rid:
            if line != idx["p1"][rid]["text"]:
                ok = False
                log.append(f"phase1.md:{i}: v9 line differs from the indexed text of {rid}")
            new1.append(F[rid]["P1_structured"].strip("\n"))
        else:
            new1.append(line)
        if line.startswith("- Precedence."):
            new1.append(PROC_P1)
    # Phase 2
    p2 = orig["phase2.md"].split("\n")
    by_line = {}
    for s in sorted(idx["p2"]):
        by_line.setdefault(idx["p2"][s]["line"], []).append(s)
    owner = {}
    for rid in F:
        for s in dix.get(rid, {}).get("P2 sentence ids", []):
            owner[s] = rid
        got = set(F[rid].get("P2_replaces") or []) | set((F[rid].get("P2_in_place") or {}).keys())
        want = set(dix.get(rid, {}).get("P2 sentence ids", []))
        if got != want:
            ok = False
            log.append(f"{rid}: Phase 2 S-ids replaced or kept {sorted(got)} != the rule's {sorted(want)}")
    placed, proc_done = set(), False
    for ln, sids in by_line.items():
        rebuilt = " ".join(idx["p2"][s]["text"] for s in sids)
        if rebuilt != p2[ln - 1]:
            ok = False
            log.append(f"phase2.md:{ln}: the indexed sentences do not rebuild the v9 line")
            continue
        parts, run = [], []
        for s in sids:
            rid = owner.get(s)
            if rid and s in (F[rid].get("P2_in_place") or {}):
                run.append(F[rid]["P2_in_place"][s].strip())
            elif rid and s in (F[rid].get("P2_replaces") or []):
                if rid not in placed:
                    if run:
                        parts.append(" ".join(run))
                        run = []
                    if not proc_done:
                        parts.append(PROC_P2)
                        proc_done = True
                    parts.append(F[rid]["P2_structured"].strip("\n"))
                    placed.add(rid)
            else:
                run.append(idx["p2"][s]["text"])
        if run:
            parts.append(" ".join(run))
        p2[ln - 1] = "\n".join(parts)
    new = {"common.md": orig["common.md"], "phase1.md": "\n".join(new1), "phase2.md": "\n".join(p2)}
    # unchanged text
    kept1 = [l for i, l in enumerate(orig["phase1.md"].split("\n"), 1) if not any(x["line"] == i and r in F for r, x in idx["p1"].items())]
    pos = 0
    n1 = new["phase1.md"].split("\n")
    for l in kept1:
        try:
            pos = n1.index(l, pos) + 1
        except ValueError:
            ok = False
            log.append(f"phase1.md: an untouched v9 line is missing or out of order: {l[:80]!r}")
            break
    body2 = new["phase2.md"]
    pos = 0
    for s in sorted(idx["p2"]):
        if s in owner:
            continue
        j = body2.find(idx["p2"][s]["text"], pos)
        if j < 0:
            ok = False
            log.append(f"phase2.md: untouched sentence {s} missing or out of order")
            break
        pos = j + len(idx["p2"][s]["text"])
    for f in ("phase1.md", "phase2.md"):
        if new[f][new[f].index("\nOUTPUT\n"):] != orig[f][orig[f].index("\nOUTPUT\n"):]:
            ok = False
            log.append(f"{f}: the OUTPUT section changed")
    print("\n".join(log) if log else "plan: no problems found")
    w = {f: (len(orig[f].split()), len(new[f].split())) for f in FILES}
    print("words per file:", {f: f"{a} -> {b} ({b - a:+d})" for f, (a, b) in w.items()})
    print(f"shared procedure: Phase 1 {len(PROC_P1.split())} words, Phase 2 {len(PROC_P2.split())} words")
    tot = [0, 0, 0, 0]
    for rid in sorted(F):
        a1, b1 = len((texts[rid].get("P1") or "").split()), len((F[rid].get("P1_structured") or "").split())
        a2 = len((texts[rid].get("P2") or "").split())
        b2 = len((F[rid].get("P2_structured") or "").split()) + sum(len(t.split()) for t in (F[rid].get("P2_in_place") or {}).values())
        tot = [tot[0] + a1, tot[1] + b1, tot[2] + a2, tot[3] + b2]
        print(f"  {rid:6s} {texts[rid]['title'][:32]:32s} P1 {a1:4d} -> {b1:4d} ({b1 - a1:+d})   P2 {a2:4d} -> {b2:4d} ({b2 - a2:+d})")
    print(f"  critical rules total: P1 {tot[0]} -> {tot[1]} ({tot[1] - tot[0]:+d}); P2 {tot[2]} -> {tot[3]} ({tot[3] - tot[2]:+d})")
    if write and ok:
        DST.mkdir(exist_ok=True)
        for f in ("phase1_user.md", "phase2_user.md"):
            shutil.copyfile(SRC / f, DST / f)
        crlf = b"\r\n" in (SRC / "phase1.md").read_bytes()
        for f in FILES:
            data = new[f].replace("\n", "\r\n") if crlf else new[f]
            (DST / f).write_bytes(data.encode("utf-8"))
        same_eol = all((b"\r\n" in (SRC / f).read_bytes()) == (b"\r\n" in (DST / f).read_bytes()) for f in FILES)
        same_common = (SRC / "common.md").read_bytes() == (DST / "common.md").read_bytes()
        chk = bool(CK.check("two_phase_v10", log=print))
        nf = CH.new_format("two_phase_v10", 1) and CH.new_format("two_phase_v10", 2)
        same_user = all((SRC / f).read_bytes() == (DST / f).read_bytes() for f in ("phase1_user.md", "phase2_user.md"))
        ok &= chk and nf and same_user and same_eol and same_common
        print(f"checker {chk}; new_format {nf}; user templates identical to v9 {same_user}; common.md byte-identical {same_common}; "
              f"line ends as v9 {same_eol}; shas {sha(CK.system('two_phase_v10', 1))} / {sha(CK.system('two_phase_v10', 2))} "
              f"(v9 {sha(CK.system('two_phase_v9', 1))} / {sha(CK.system('two_phase_v9', 2))})")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
