"""Check 1 of the v10 diagnosis (user 2026-10-16): "verify that the latest isolated rule has the same rules in the
current v10, if v10 is missing any rules, add them."

For every rule wording of the rule-alone inventory, take the text of its LATEST ADOPTED rule-alone test and check that
v10's prompt files carry it word for word (whitespace collapsed; each line of a block, and each sentence of an
unchanged v9 rule, checked on its own, so the check does not depend on where a block sits in the step-4 line).
Latest adopted test per rule:
  P1-17 Buffer and engine status bits    rule_texts_v10e1.json   (E1 fix; tested on Claude only)
  the other 16 re-tested rules           rule_texts_v10m.json    (13 as v10r, 4 as v10fo; v10m adds the merged procedure)
  every other rule                       rule_texts.json (v9)    plus pack/index.json for its Phase 2 sentence ids
  P1-22R                                 rejected wording (not adopted): reported, not required
Reverse check: every titled Phase 1 bullet of v10 and every Phase 2 step-4/5 sentence of v10 is covered by an inventory
text, by the context the rule-alone tests keep ("general" sentences), or by the shared procedure. Anything left over is
a rule in v10 that no rule-alone test read.

Self-test (hand-read, 2026-10-16): phase1.md line 24 is the merged procedure; line 95 starts "- Held outcomes,
addresses and settings."; line 144 starts "- Held addresses."; phase2.md's Hand-offs block has the line
"  Evidence: if the RTL cannot show which kind it is, judge from the port names at either end and say so.".
Sends nothing to any API; writes verify_v10_rules.json.

  python -B verify_v10_rules.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
ISO = LAB / "analysis" / "rule_isolation_v9"
V10 = LAB / "prompts" / "two_phase_v10"
V9 = LAB / "prompts" / "two_phase_v9"
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
sys.path.insert(0, str(LAB))
import make_v10 as MV  # noqa: E402

RULES17 = ["P1-02", "P1-04", "P1-05", "P1-06", "P1-07", "P1-08", "P1-09", "P1-10", "P1-14", "P1-15", "P1-16", "P1-17",
           "P1-18", "P1-22", "P1-23", "P1-24", "P1-27"]


def norm(t):
    return re.sub(r"\s+", " ", t.replace("\r\n", "\n")).strip()


def load(f):
    return json.loads((ISO / f).read_text(encoding="utf-8"))


def selftest(p1, p2):
    l1 = p1.split("\n")
    ok = (l1[23].startswith("- Reading a rule. ") and norm(l1[23]) == norm(MV.PROC_P1)
          and l1[94].startswith("- Held outcomes, addresses and settings.") and l1[143].startswith("- Held addresses.")
          and "  Evidence: if the RTL cannot show which kind it is, judge from the port names at either end and say so." in p2)
    print(f"self-test (hand-read lines of v10 phase1.md / phase2.md): {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p1 = (V10 / "phase1.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    p2 = (V10 / "phase2.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    if not selftest(p1, p2):
        sys.exit(1)
    body = {"P1": norm(p1[:p1.index("\nOUTPUT\n")]), "P2": norm(p2[:p2.index("\nOUTPUT\n")])}
    v9t, v10m, e1 = load("rule_texts.json"), load("rule_texts_v10m.json"), load("rule_texts_v10e1.json")
    idx, rmap = load("pack/index.json"), load("rule_map.json")
    latest, src = {}, {}
    for rid, t in v9t.items():
        if rid == "P1-22R":
            continue
        if rid == "P1-17":
            latest[rid], src[rid] = e1[rid], "v10e1"
        elif rid in RULES17:
            latest[rid], src[rid] = v10m[rid], "v10m"
        else:
            latest[rid], src[rid] = t, "v9"
    rows, missing = [], []
    for rid, t in latest.items():
        for ph in ("P1", "P2"):
            if not t.get(ph):
                continue
            if src[rid] == "v9" and ph == "P2":            # unchanged rule: its Phase 2 sentences one by one
                pieces = [idx["p2"][s]["text"] for s in sorted(idx["p2"]) if rmap[s]["unit"].startswith(rid)
                          or (rid.startswith("P2X-") and rmap[s]["unit"].startswith("P2-only")
                              and "P2X-" + re.sub(r"[^a-z0-9]+", "-", rmap[s]["unit"].split(":", 1)[1].strip().lower()).strip("-") == rid)]
            else:
                pieces = [l for l in t[ph].split("\n") if l.strip()]
            absent = [x for x in pieces if norm(x) not in body[ph]]
            whole = norm(t[ph]) in body[ph]
            rows.append({"rule": rid, "title": t["title"], "phase": ph, "tested text": src[rid], "pieces": len(pieces),
                         "pieces absent from v10": absent, "whole text verbatim": whole})
            if absent:
                missing.append((rid, ph, absent))
    # reverse: v10 Phase 1 titled bullets not covered by any inventory P1 text or the procedure
    inv1 = {norm(t["P1"]) for t in latest.values() if t.get("P1")}
    bullets, cur = [], None
    for line in p1[:p1.index("\nOUTPUT\n")].split("\n"):
        if re.match(r"- [A-Z][^.]*\.", line):
            cur = [line]
            bullets.append(cur)
        elif cur is not None and line.startswith("  "):
            cur.append(line)
        else:
            cur = None
    uncovered1 = []
    for b in bullets:
        txt = norm("\n".join(b))
        if txt == norm(MV.PROC_P1) or b[0].startswith("- Precedence.") or b[0].startswith("- Describe a conceptual asset"):
            continue
        if not any(txt == x or txt in x or x in txt for x in inv1):
            uncovered1.append(b[0][:120])
    # reverse, Phase 2: every sentence of v9's step-4/5 lines is mapped (index) -> its unit; v10 sentences that are not
    # in v9 must come from an inventory text or the procedure
    inv2 = " ".join(norm(t["P2"]) for t in latest.values() if t.get("P2")) + " " + norm(MV.PROC_P2)
    gen = " ".join(norm(idx["p2"][s]["text"]) for s in idx["p2"] if rmap[s]["unit"].startswith("general"))
    lines2 = sorted({x["line"] for x in idx["p2"].values()})
    v10_lines = p2.split("\n")
    # the v10 counterparts of v9's indexed lines: v10 inserted block lines, so take the step-4 region by its header
    start = next(i for i, l in enumerate(v10_lines) if l.startswith("4. Primary."))
    end = next(i for i, l in enumerate(v10_lines) if i > start and l.startswith("Rules:"))
    region = norm("\n".join(v10_lines[start:end]))
    sents = [s for s in re.split(r"(?<=[.;:])\s+(?=[A-Z(\"-])", region) if len(s) > 3]
    uncovered2 = [s[:160] for s in sents if norm(s) not in inv2 and norm(s) not in gen]
    out = {"latest tested text per rule": src, "rows": rows, "missing from v10": missing,
           "v10 Phase 1 bullets no rule-alone test read": uncovered1,
           "v10 Phase 2 step 4-5 sentences not in any inventory text or kept context (candidates; read by hand)": uncovered2,
           "v9 indexed Phase 2 lines": lines2}
    (HERE / "verify_v10_rules.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    n = len(rows)
    print(f"rule wordings checked: {n} ({sum(1 for r in rows if r['phase'] == 'P1')} Phase 1, "
          f"{sum(1 for r in rows if r['phase'] == 'P2')} Phase 2); every piece present: {n - len(missing)} of {n}; "
          f"whole text verbatim: {sum(r['whole text verbatim'] for r in rows)} of {n}")
    for rid, ph, absent in missing:
        print(f"  MISSING {rid} {ph}: {len(absent)} piece(s), first: {absent[0][:140]!r}")
    print(f"v10 Phase 1 bullets that no rule-alone test read: {len(uncovered1)}")
    for b in uncovered1:
        print("   ", b)
    print(f"v10 Phase 2 step-4/5 sentence candidates outside the inventory and the kept context: {len(uncovered2)}")
    for s in uncovered2[:40]:
        print("   ", s)


if __name__ == "__main__":
    main()
