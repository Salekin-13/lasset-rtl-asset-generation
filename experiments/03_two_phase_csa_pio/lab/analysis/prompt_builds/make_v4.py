"""Build prompt version two_phase_v4 = two_phase_v3 + one sentence in common.md section 2.6 (change C10).

C10 (V3_PHASE1_PROPOSAL_APPENDIX.md): a bus request or response record port, or any field of one, is not a primary.
It goes on its own line right after common.md line 99 of v2/v3 (the line that makes forwarding wires and read-back words
candidate secondaries). Asserts that the anchor line is where expected and that every other file equals v3.

  python make_v4.py
"""
import shutil
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
V3, V4 = LAB / "prompts" / "two_phase_v3", LAB / "prompts" / "two_phase_v4"
C10 = ("A bus request record port (one that carries an address, data and a strobe) or bus response record port (one that carries "
       "data, an acknowledge and an error flag), or any field of one, is not a primary. Label primary the element inside the unit "
       "that the access sets, decides or returns.")


def main():
    V4.mkdir(exist_ok=True)
    for f in ("phase1.md", "phase2.md", "phase1_user.md", "phase2_user.md"):
        shutil.copyfile(V3 / f, V4 / f)
    lines = (V3 / "common.md").read_text(encoding="utf-8").split("\n")
    assert lines[98].startswith("An internal element that only passes the value on between two of these carries it"), lines[98][:80]
    assert lines[99].startswith("Examples: the key register"), lines[99][:60]
    new = lines[:99] + [C10] + lines[99:]  # read_text/write_text keep the file's CRLF line ends on Windows
    (V4 / "common.md").write_text("\n".join(new), encoding="utf-8")
    for f in ("phase1.md", "phase2.md", "phase1_user.md", "phase2_user.md"):
        assert (V4 / f).read_bytes() == (V3 / f).read_bytes(), f
    print("two_phase_v4 written: common.md line 100 =", C10[:60], "...")


if __name__ == "__main__":
    main()
