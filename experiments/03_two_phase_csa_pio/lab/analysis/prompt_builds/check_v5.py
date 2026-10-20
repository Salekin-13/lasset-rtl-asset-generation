"""Code checks for two_phase_v5 against two_phase_v4a.

  python check_v5.py

1. The project prompt checker (check_lab_prompt.check: corpus names, banned words, numeric hints, final-JSON phrase).
2. Which files differ from v4a: common.md, phase1.md and phase2.md may change; the user templates must be identical.
3. phase1.md's OUTPUT block is byte-identical to v4a's (no reply-format change).
4. Every protected phrase of check_v4a_phrases.PHRASES is still in v5's phase1.md; "If so" did not come back.
5. The rule heads are in v4a's order, followed by the new head(s).
6. Every edit of make_v5.py is present in the built files.
Self-test: the checks pass on v4a itself where they apply (phrases, OUTPUT identity).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(HERE))
import check_lab_prompt as CK  # noqa: E402
import check_v4a_phrases as PH  # noqa: E402
import make_v5 as M5  # noqa: E402

V4A, V5 = LAB / "prompts" / "two_phase_v4a", LAB / "prompts" / "two_phase_v5"
FILES = ("common.md", "phase1.md", "phase2.md", "phase1_user.md", "phase2_user.md")


def main():
    ok = True
    p1a = (V4A / "phase1.md").read_text(encoding="utf-8")
    assert all(x in p1a for x in PH.PHRASES), "self-test: a protected phrase is missing in v4a"
    print("== two_phase_v5 vs two_phase_v4a")
    ok &= bool(CK.check("two_phase_v5"))
    for f in FILES:
        a, b = (V4A / f).read_text(encoding="utf-8"), (V5 / f).read_text(encoding="utf-8")
        same = a == b
        allowed = f in ("common.md", "phase1.md", "phase2.md")
        good = same or allowed
        ok &= good
        print(f"  {f}: {'identical' if same else 'changed'} ({'ok' if good else 'UNEXPECTED'}); words {len(a.split())} -> {len(b.split())}")
    p1 = (V5 / "phase1.md").read_text(encoding="utf-8")
    out_same = p1[p1.index("\nOUTPUT"):] == p1a[p1a.index("\nOUTPUT"):]
    ok &= out_same
    print(f"  phase1.md OUTPUT block identical to v4a: {out_same}")
    miss = [x for x in PH.PHRASES if x not in p1]
    ok &= not miss
    print(f"  protected phrases present: {len(PH.PHRASES) - len(miss)} of {len(PH.PHRASES)}" + (f"; MISSING {miss}" if miss else ""))
    ok &= "If so" not in p1
    print(f"  'If so' absent: {'If so' not in p1}")
    rules_part = p1[p1.index("\nRules:"):p1.index("\nOUTPUT")]
    heads = [l[2:].split(".")[0] + "." for l in rules_part.splitlines() if l.startswith("- ") and "." in l[:40]]
    order_ok = heads[:len(PH.HEADS)] == PH.HEADS
    ok &= order_ok
    print(f"  rule heads: {heads} (v4a order kept: {order_ok})")
    T = {f: (V5 / f).read_text(encoding="utf-8") for f in FILES}
    U = json.loads((HERE / "u_rules.json").read_text(encoding="utf-8")) if (HERE / "u_rules.json").exists() else []
    # an A/B edit whose text a later U edit rewrites on purpose (its 'old' lies inside the A/B text) counts as present
    # when every part of it outside the rewritten pieces is still there
    def present(new, f):
        if new in T[f]:
            return True
        rest = new
        for u in U:
            if u.get("old") and u["file"] == f and u["old"] in rest:
                rest = rest.replace(u["old"], "\0")
        return rest != new and all(p.strip() in T[f] for p in rest.split("\0") if p.strip())
    absent = [rid for rid, f, _, new in M5.EDITS if not present(new, f)]
    if M5.K1_LINE not in T["phase1.md"]:
        absent.append("K1")
    FX = json.loads((HERE / "v5_fixes.json").read_text(encoding="utf-8")) if (HERE / "v5_fixes.json").exists() else []
    # a rule text later changed by a conflict fix counts as present when the fix's new text is there
    fixed_old = {x["old"] for x in FX}
    absent += [u["id"] for u in U if u["new"] not in T[u["file"]] and not any(o in u["new"] for o in fixed_old)]
    absent += [x["id"] for x in FX if x["new"] not in T[x["file"]]]
    ok &= not absent
    print(f"  edits present: {len(M5.EDITS) + 1 + len(U) + len(FX) - len(absent)} of {len(M5.EDITS) + 1 + len(U) + len(FX)}" + (f"; ABSENT {absent}" if absent else ""))
    print("PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
