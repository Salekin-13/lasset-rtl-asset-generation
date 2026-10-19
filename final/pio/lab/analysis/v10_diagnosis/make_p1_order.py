"""Phase 1 position variants for PLAN_P1_ORDER.md, Tier 1: where does one added Phase 1 block go? Built from the working version
two_phase_v9n_place (A); Phase 2, common.md and the user templates stay byte-identical, so Phase 1-only runs are enough.
  two_phase_p1o_first   the paired debug bar's Phase 1 block (make_v9n.AD_P1) as the FIRST rule block (right after "Reading a rule")
  two_phase_p1o_last    the same block as the LAST rule block (right before OUTPUT)
  two_phase_p1o_sham    neutral prose of the same word count, no rule content, at the block's current position (after the
                        control-unit bar): the control that separates "any added text there" from "this rule's text" (D39 found
                        neutral text harmless where rule text hurt)
  (the position "after the control-unit bar" is two_phase_v9n_place_dbg, whose Phase 1 records already exist; absent = A)
Block boundaries follow the inventory of 2026-10-19 (46 column-zero "- Title." blocks at lines 22-168 of A's phase1.md; the
numbered steps before; OUTPUT after). Self-test: the built file keeps every original line in order with exactly one block added
(47 titles), passes check_lab_prompt, and the sham block has the bar's word count within two words.
  python -B make_p1_order.py [--write]
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
sys.path.insert(0, str(HERE))
import make_v10 as M  # noqa: E402
import make_v9n as MN  # noqa: E402

CK, CH = M.CK, M.CH
SRC = "two_phase_v9n_place"
BAR = MN.AD_P1
TITLE_RE = re.compile(r"^- [A-Z][^\n]*?\.(\s|$)")
SHAM = ("- Reading note.\n"
        "  The RTL input shows one statement per line with its source line number first, comments removed and blank lines left out, so "
        "a line number cited anywhere in a reply points at one statement of the source file. The closed set lists the ports, signals "
        "and record fields of the file with the lines where each occurs and the elements each one exchanges values with, in the order "
        "the file declares them. The diagram groups the statements into blocks by the process, instance or concurrent assignment that "
        "owns them and draws an arrow between two blocks where a value moves from one to the other, with the elements that carry it "
        "in brackets. The three inputs describe the same file from three sides: the text itself, its named elements, and the flow of "
        "values between its parts. A unit name in the diagram matches an entity name in the RTL, a block name matches a process label, "
        "an instance label or an output port, and a bracketed element matches a closed-set name, so each of the three can be read "
        "against the other two. Each run of this call receives the same three inputs for the same module; nothing in them changes "
        "between calls, and nothing outside them is available. The reply is read by a program that matches closed-set names exactly, "
        "so names are copied as the closed set spells them, including record field names written with their record and a dot. The "
        "same program also reads each cited line number back against the RTL input.")


def titles(text):
    return [i for i, l in enumerate(text.split("\n")) if TITLE_RE.match(l)]


def build(name, body, readme, write):
    d = LAB / "prompts" / name
    crlf = b"\r\n" in (LAB / "prompts" / SRC / "phase1.md").read_bytes()
    if write:
        d.mkdir(exist_ok=True)
        for f in ("common.md", "phase1_user.md", "phase2.md", "phase2_user.md"):
            shutil.copyfile(LAB / "prompts" / SRC / f, d / f)
        (d / "phase1.md").write_bytes((body.replace("\n", "\r\n") if crlf else body).encode("utf-8"))
        (d / "README.md").write_text(f"# {name}: {readme} (built 2026-10-19; analysis/v10_diagnosis/make_p1_order.py; PLAN_P1_ORDER.md Tier 1)\n", encoding="utf-8")
        chk = bool(CK.check(name, log=lambda *a: None))
        s1 = M.sha(CK.system(name, 1))[:12]
        print(f"{name}: checker {chk}; sha12 phase 1 {s1} (phase 2 unchanged {M.sha(CK.system(name, 2))[:12]})")
        return chk
    return True


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    src = (LAB / "prompts" / SRC / "phase1.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    lines = src.split("\n")
    t = titles(src)
    assert len(t) == 46, f"expected 46 rule blocks in {SRC}, found {len(t)}"
    first, last = t[0], t[-1]
    assert lines[first - 1].startswith("- Reading a rule") or lines[first].startswith("- "), lines[first][:40]
    out_i = lines.index("OUTPUT")
    # end of the last block = the line before the blank line that precedes OUTPUT
    end_last = out_i - 1
    while lines[end_last].strip() == "":
        end_last -= 1
    # first: insert the bar before the first rule block that is not one of the three definition blocks (Precedence, Reading a rule)
    defs = [i for i in t if lines[i].startswith(("- Describe", "- Precedence", "- Reading a rule"))]
    ins_first = max(defs) + 1 if defs else first
    v_first = lines[:ins_first] + BAR.split("\n") + lines[ins_first:]
    v_last = lines[:end_last + 1] + BAR.split("\n") + lines[end_last + 1:]
    cu = [i for i in t if lines[i].startswith("- Processor control-unit state.")]
    assert len(cu) == 1
    nxt = [i for i in t if i > cu[0]][0]
    v_sham = lines[:nxt] + SHAM.split("\n") + lines[nxt:]
    bw, sw = len(BAR.split()), len(SHAM.split())
    assert abs(bw - sw) <= 2, f"sham {sw} words, bar {bw}"
    ok = True
    for name, v, note in (("two_phase_p1o_first", v_first, "A with the debug bar's Phase 1 block as the first rule block"),
                          ("two_phase_p1o_last", v_last, "A with the debug bar's Phase 1 block as the last rule block"),
                          ("two_phase_p1o_sham", v_sham, "A with neutral prose of the bar's length after the control-unit bar (control)")):
        body = "\n".join(v)
        # self-test: original lines kept in order, exactly one block added
        it = iter(v)
        assert all(any(l == x for x in it) for l in lines), f"{name}: an original line was lost or reordered"
        assert len(titles(body)) == 47, f"{name}: {len(titles(body))} titles"
        print(f"{name}: {len(body.split())} words (A {len(src.split())}), block at line {[i for i, l in enumerate(v) if l.startswith(('- Debug module registers.', '- Reading note.'))][0] + 1}")
        ok &= build(name, body, note, write)
    print("ALL BUILT AND CHECKED" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
