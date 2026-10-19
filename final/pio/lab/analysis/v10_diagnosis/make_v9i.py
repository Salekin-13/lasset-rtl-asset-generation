"""two_phase_v9i = two_phase_v9h minus Count increment inputs (K14, the one-case block that was never followed), with the
Link handshake ports exception reworded (never name another bar as the judge of what a keep block excludes), plus the
false-positive bars of new_rules/rule_texts_v9i.json placed by new_rules/placement_v9i.json (user 2026-10-18: "place the
bars / constraints in the prompt where they are least likely to be ignored by the model"):
  Phase 2 bars go at the END of step 4, after the Boundary outputs block (the last block): the diagnosis found a rule
  moved last in its step was followed best (salience), and Phase 2 bars held in every cluster test.
  Phase 1 copies go right after the existing bar they extend (the anchor named in placement_v9i.json), where the
  v9k/v9h keep blocks were followed; a bar with no related Phase 1 bar goes after the last rule, before OUTPUT.
Builds the prompt folder only; sends nothing.

  python -B make_v9i.py            (dry run)
  python -B make_v9i.py --write
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
import make_v10 as M  # noqa: E402

CK, CH = M.CK, M.CH
SRC, DST = LAB / "prompts" / "two_phase_v9h", LAB / "prompts" / "two_phase_v9i"
K = json.loads((HERE / "new_rules" / "rule_texts_v9h.json").read_text(encoding="utf-8"))
BARS_FILE, PLACE_FILE = HERE / "new_rules" / "rule_texts_v9i.json", HERE / "new_rules" / "placement_v9i.json"
BARS = json.loads(BARS_FILE.read_text(encoding="utf-8")) if BARS_FILE.exists() else {}
PLACE = json.loads(PLACE_FILE.read_text(encoding="utf-8")) if PLACE_FILE.exists() else {}
FILES = M.FILES
K12_OLD = ("the link's data ports (Forwarded transactions and Port buffers judge them); the link's clock line (Clocks "
           "and resets).")
K12_NEW = ("the link's data ports, which are judged as usual, as information crossing the unit's boundary; the link's clock "
           "line (Clocks and resets).")
# anchors: the last line of the block a Phase 1 copy follows; "END" = after the last rule line (before OUTPUT);
# Phase 2 bars all go after the Boundary outputs block (the end of step 4)
P1_ANCHORS = {
    "Working values": "- Working values. Partial results inside a computation (a partial sum, product or round value, a synchronizer stage, a debiasing step) are part of the result they produce (step 3), not concepts of their own. So are the state and flag made inside a debiasing step to choose which raw bits it accepts: although step 2 would call them a decision, they only shape that result, like a compare picking a minimum (step 3). Do not name a synchronizer stage in any concept's information or cite its lines as held lines.",
    "Cached copies": "- Cached copies. In a cache (a unit answering a read from its own copy when a stored tag matches the address, else fetching the words over a backing bus), the copied words copy backing-memory data, and the tag and valid bits only record which words are copied: none is a piece of this unit, although steps 1 and 2 would name them and 4.4 names caches. Judged as usual: its decisions (the hit, the bytes a write changes, the address, its fill, clear and invalidate commands, a pending fence or flush), and a memory that is itself the store.",
    "Bus handshake copies": "Judged as usual: that state, where held; a register set only from the unit's input ports (a read enable from a strobe and a read or write bit); and a flag that a condition sets to a constant (a timeout error raised at a count's limit).",
    "Control record ports": None,     # filled from K: the N21 P1 block's last line (looked up at build time)
    "Forwarded transactions": "Judge from port names which instance ports carry relayed data and which a computed result, and say so.",
    "END": "Judge what a field tells from port field names and their uses; say so.",
}
P2_END_ANCHOR_HEAD = "- Boundary outputs."


def last_line_of(text, head):
    """the last line of the block starting with head: the block ends at the next rule bullet or the next blank line."""
    i = text.index(head)
    ends = [x for x in (text.find("\n- ", i + 1), text.find("\n\n", i + 1)) if x > 0]
    block = text[i:min(ends) if ends else len(text)].rstrip("\n")
    return block.split("\n")[-1]


def insert_after(text, anchor, block, log, what):
    if text.count(anchor) != 1:
        log.append(f"{what}: anchor occurs {text.count(anchor)} times")
        return text
    i = text.index(anchor) + len(anchor)
    return text[:i] + "\n" + block + text[i:]


def remove_once(text, block, log, what):
    if text.count(block + "\n") != 1:
        log.append(f"{what}: block to remove occurs {text.count(block)} times")
        return text
    return text.replace(block + "\n", "", 1)


def build(log):
    orig = {f: (SRC / f).read_text(encoding="utf-8").replace("\r\n", "\n") for f in FILES}
    new = {"common.md": orig["common.md"]}
    for f, ph in (("phase1.md", "P1"), ("phase2.md", "P2")):
        body = orig[f]
        body = remove_once(body, K["K14"][ph].strip("\n"), log, f"{f} K14")
        if body.count(K12_OLD) != 1:
            log.append(f"{f}: the K12 exception sentence occurs {body.count(K12_OLD)} times")
        body = body.replace(K12_OLD, K12_NEW)
        if ph == "P2":
            anchor = last_line_of(body, P2_END_ANCHOR_HEAD)
            blocks = [BARS[r]["P2"].strip("\n") for r in PLACE if BARS.get(r, {}).get("P2")]
            if blocks:
                body = insert_after(body, anchor, "\n".join(blocks), log, "P2 bars after Boundary outputs")
        else:
            groups = {}
            for r, p in PLACE.items():
                if BARS.get(r, {}).get("P1"):
                    groups.setdefault(p.get("P1", "END"), []).append(BARS[r]["P1"].strip("\n"))
            for key, blocks in groups.items():
                anchor = P1_ANCHORS.get(key)
                if key == "Control record ports":
                    anchor = last_line_of(body, "- Control record ports.")
                if anchor is None:
                    log.append(f"P1: no anchor for {key}")
                    continue
                body = insert_after(body, anchor, "\n".join(blocks), log, f"P1 bars after {key}")
        if body[body.index("\nOUTPUT\n"):] != orig[f][orig[f].index("\nOUTPUT\n"):]:
            log.append(f"{f}: the OUTPUT section changed")
        for r in PLACE:
            if BARS.get(r, {}).get(ph) and body.count(BARS[r][ph].strip("\n")) != 1:
                log.append(f"{r} {ph}: bar not present exactly once")
        pos = 0
        for l in orig[f].split("\n"):
            if l in K["K14"][ph] or K12_OLD in l:
                continue
            j = body.find(l, pos)
            if j < 0:
                log.append(f"{f}: a v9h line is missing or out of order: {l[:80]!r}")
                break
            pos = j + len(l)
        new[f] = body
    return not log, orig, new


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    log = []
    ok, orig, new = build(log)
    print("\n".join(log) if log else f"plan: no problems found (bars: {list(PLACE)})")
    print("words per file:", {f: f"{len(orig[f].split())} -> {len(new[f].split())}" for f in FILES})
    if write and ok:
        DST.mkdir(exist_ok=True)
        for f in ("phase1_user.md", "phase2_user.md"):
            shutil.copyfile(SRC / f, DST / f)
        crlf = b"\r\n" in (SRC / "phase1.md").read_bytes()
        for f in FILES:
            (DST / f).write_bytes((new[f].replace("\n", "\r\n") if crlf else new[f]).encode("utf-8"))
        (DST / "README.md").write_text(
            "# two_phase_v9i: v9h minus Count increment inputs, Link handshake ports exception reworded, + false-positive bars "
            f"(built 2026-10-18)\n\nBars: {', '.join(PLACE)} (analysis/v10_diagnosis/new_rules/rule_texts_v9i.json, placement_v9i.json). "
            "Phase 2 bars at the end of step 4; Phase 1 copies after the bar they extend. Plan: analysis/v10_diagnosis/"
            "PLAN_ISOLATE_CLUSTER_ORDER.md section 11. Built by analysis/v10_diagnosis/make_v9i.py.\n", encoding="utf-8")
        chk = bool(CK.check("two_phase_v9i", log=print))
        nf = CH.new_format("two_phase_v9i", 1) and CH.new_format("two_phase_v9i", 2)
        same = all((SRC / f).read_bytes() == (DST / f).read_bytes() for f in ("common.md", "phase1_user.md", "phase2_user.md"))
        ok &= chk and nf and same
        print(f"checker {chk}; new_format {nf}; common.md and user templates identical to v9h {same}; "
              f"sha12 {M.sha(CK.system('two_phase_v9i', 1))[:12]} / {M.sha(CK.system('two_phase_v9i', 2))[:12]}")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
