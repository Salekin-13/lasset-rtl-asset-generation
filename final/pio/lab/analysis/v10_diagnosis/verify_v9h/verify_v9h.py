"""Independent file-by-file comparison of two_phase_v9g and two_phase_v9h.

Does not import any lab code. Reads the six prompt files of each version as bytes.

Checks:
  1. Which files are byte-identical.
  2. For phase1.md and phase2.md: v9h must be v9g plus inserted lines only
     (no deleted or changed line). Inserted lines must form whole blocks
     (a block = a column-zero "- Name." line plus its indented lines), each
     block's first line must start with one of four expected prefixes, and
     each insertion must sit at a block boundary (the next original line
     starts at column zero).
  3. Word counts (whitespace-separated tokens), line counts, byte counts.
  4. The OUTPUT section (from the column-zero line "OUTPUT" to end of file)
     must be byte-identical between the versions.

Self-tests run first; if any fails the script exits non-zero and prints
nothing else.
"""
import difflib
import json
import os
import sys

PROMPTS = r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab\prompts"
OLD = os.path.join(PROMPTS, "two_phase_v9g")
NEW = os.path.join(PROMPTS, "two_phase_v9h")
FILES = ["README.md", "common.md", "phase1.md", "phase1_user.md",
         "phase2.md", "phase2_user.md"]
EXPECTED_IDENTICAL = ["common.md", "phase1_user.md", "phase2_user.md"]
EXPECTED_INSERT_ONLY = ["phase1.md", "phase2.md"]
EXPECTED_PREFIXES = ["- Done and wait inputs.", "- Count increment inputs.",
                     "- Link handshake ports.", "- Busy locks."]
HERE = os.path.dirname(os.path.abspath(__file__))


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def to_lines(data):
    """Decode UTF-8 and split keeping line ends, so ''.join(lines) == text."""
    text = data.decode("utf-8")
    return text, text.splitlines(keepends=True)


def is_block_start(line):
    """A line that is not indented starts a new block (or is a header/blank)."""
    return not line.startswith((" ", "\t"))


def insert_only_opcodes(old_lines, new_lines):
    """Return (ok, inserts, bad_ops).

    inserts: list of (old_index, new_start, new_end): the inserted new lines
             new_lines[new_start:new_end] sit just before old_lines[old_index].
    bad_ops: opcodes that are not 'equal' or 'insert'.
    """
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    inserts, bad = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            inserts.append((i1, j1, j2))
        else:
            bad.append({"op": tag, "old_lines": (i1 + 1, i2),
                        "new_lines": (j1 + 1, j2),
                        "old_text": old_lines[i1:i2],
                        "new_text": new_lines[j1:j2]})
    return (not bad), inserts, bad


def reconstruct(new_lines, inserts):
    """Drop the inserted ranges from new_lines; must give back the old text."""
    drop = set()
    for _, j1, j2 in inserts:
        drop.update(range(j1, j2))
    return "".join(l for k, l in enumerate(new_lines) if k not in drop)


def split_blocks(lines, offset):
    """Split a run of lines into blocks. Returns list of dicts with the
    first line, the number of lines and the 1-based line number (offset is
    the 1-based number of the first line of the run)."""
    blocks = []
    for k, line in enumerate(lines):
        if is_block_start(line):
            blocks.append({"first_line": line.rstrip("\r\n"),
                           "n_lines": 1, "line_no": offset + k,
                           "leading_continuation": False})
        elif blocks:
            blocks[-1]["n_lines"] += 1
        else:
            # run begins with an indented line: a partial block
            blocks.append({"first_line": line.rstrip("\r\n"), "n_lines": 1,
                           "line_no": offset + k,
                           "leading_continuation": True})
    return blocks


def previous_block_start(lines, idx):
    """1-based line number and text of the nearest column-zero '- ' line at or
    above lines[idx-1]; None if none."""
    k = idx - 1
    while k >= 0:
        if lines[k].startswith("- "):
            return k + 1, lines[k].rstrip("\r\n")
        k -= 1
    return None, None


def word_count(text):
    return len(text.split())


def output_section(lines):
    """Lines from the column-zero line 'OUTPUT' to the end. Returns
    (start_line_no_1based, text, n_hits)."""
    hits = [k for k, l in enumerate(lines) if l.rstrip("\r\n") == "OUTPUT"]
    if len(hits) != 1:
        return None, None, len(hits)
    k = hits[0]
    return k + 1, "".join(lines[k:]), 1


def short(s, n=70):
    s = s.rstrip("\r\n")
    return s if len(s) <= n else s[:n] + "..."


# --------------------------------------------------------------------------
# Self-tests
# --------------------------------------------------------------------------
def self_test():
    # (a) synthetic: base + one inserted two-line block at a boundary
    base = ["Rules:\n", "- A.\n", "  Scope: a\n", "- B.\n", "  Scope: b\n",
            "OUTPUT\n", "{}\n"]
    ins = ["- X.\n", "  Scope: x\n"]
    new = base[:3] + ins + base[3:]
    ok, inserts, bad = insert_only_opcodes(base, new)
    assert ok and not bad, "self-test a1: expected insert-only"
    assert inserts == [(3, 3, 5)], "self-test a2: %r" % (inserts,)
    assert reconstruct(new, inserts) == "".join(base), "self-test a3"
    blocks = split_blocks(new[3:5], 4)
    assert len(blocks) == 1 and blocks[0]["first_line"] == "- X." \
        and blocks[0]["n_lines"] == 2 and blocks[0]["line_no"] == 4, blocks
    assert previous_block_start(base, 3) == (2, "- A."), \
        previous_block_start(base, 3)
    assert is_block_start(base[3]) and not is_block_start(base[2])
    # (b) synthetic: a changed line must be reported, not hidden
    changed = list(base)
    changed[2] = "  Scope: a changed\n"
    ok, _, bad = insert_only_opcodes(base, changed)
    assert not ok and bad[0]["op"] == "replace", "self-test b"
    # (c) synthetic: a deleted line must be reported
    ok, _, bad = insert_only_opcodes(base, base[:2] + base[3:])
    assert not ok and bad[0]["op"] == "delete", "self-test c"
    # (d) word count and OUTPUT section on synthetic text
    assert word_count("a  b\n c\td ") == 4
    s, txt, n = output_section(base)
    assert (s, txt, n) == (6, "OUTPUT\n{}\n", 1), (s, txt, n)
    # (e) hand-read lines of v9g/phase1.md (read in this session with awk):
    #     line 27 is "- Pacing pulses.", line 32 starts "- Forwarded transactions.",
    #     line 58 is "- Sequencing state.", line 74 is "- Coprocessor progress state."
    _, g1 = to_lines(read_bytes(os.path.join(OLD, "phase1.md")))
    assert g1[26].rstrip("\r\n") == "- Pacing pulses.", g1[26]
    assert g1[31].startswith("- Forwarded transactions."), g1[31]
    assert g1[57].rstrip("\r\n") == "- Sequencing state.", g1[57]
    assert g1[73].rstrip("\r\n") == "- Coprocessor progress state.", g1[73]
    # (f) hand-read: v9h/phase1.md line 32 is "- Done and wait inputs."
    #     (from the diff output "31a32,43" read in this session)
    _, h1 = to_lines(read_bytes(os.path.join(NEW, "phase1.md")))
    assert h1[31].rstrip("\r\n") == "- Done and wait inputs.", h1[31]
    return True


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    try:
        self_test()
    except AssertionError as e:
        print("SELF-TEST FAILED:", e)
        sys.exit(2)
    print("self-tests: PASS (a-f)")

    result = {"files": {}, "insertions": {}, "output_sections": {},
              "unexpected": []}

    for name in FILES:
        po, pn = os.path.join(OLD, name), os.path.join(NEW, name)
        bo, bn = read_bytes(po), read_bytes(pn)
        to, lo = to_lines(bo)
        tn, ln = to_lines(bn)
        entry = {
            "identical": bo == bn,
            "v9g": {"bytes": len(bo), "lines": len(lo), "words": word_count(to),
                    "bom": bo.startswith(b"\xef\xbb\xbf"),
                    "crlf_lines": sum(l.endswith("\r\n") for l in lo),
                    "ends_with_newline": to.endswith("\n")},
            "v9h": {"bytes": len(bn), "lines": len(ln), "words": word_count(tn),
                    "bom": bn.startswith(b"\xef\xbb\xbf"),
                    "crlf_lines": sum(l.endswith("\r\n") for l in ln),
                    "ends_with_newline": tn.endswith("\n")},
        }
        entry["word_delta"] = entry["v9h"]["words"] - entry["v9g"]["words"]
        result["files"][name] = entry

        if name in EXPECTED_IDENTICAL and not entry["identical"]:
            result["unexpected"].append(name + ": expected byte-identical, differs")
        if name not in EXPECTED_IDENTICAL + EXPECTED_INSERT_ONLY and not entry["identical"]:
            result["unexpected"].append(
                "%s: not in the expected list and differs (v9g %d bytes, v9h %d bytes)"
                % (name, len(bo), len(bn)))
            # show the line-level diff for the record
            entry["line_diff"] = [l.rstrip("\n") for l in difflib.unified_diff(
                lo, ln, fromfile="v9g/" + name, tofile="v9h/" + name, n=0)]

        if name in EXPECTED_INSERT_ONLY:
            ok, inserts, bad = insert_only_opcodes(lo, ln)
            recon_ok = reconstruct(ln, inserts) == to if ok else False
            ins_report = []
            for (i_old, j1, j2) in inserts:
                run = ln[j1:j2]
                blocks = split_blocks(run, j1 + 1)
                # boundary: next original line (if any) starts at column 0
                next_old = lo[i_old] if i_old < len(lo) else None
                prev_old = lo[i_old - 1] if i_old > 0 else None
                at_boundary = (next_old is None) or is_block_start(next_old)
                # the run must end with a complete block: the v9h line after
                # the run must start at column 0 (same check, in v9h)
                next_new = ln[j2] if j2 < len(ln) else None
                run_ends_block = (next_new is None) or is_block_start(next_new)
                pb_no, pb_txt = previous_block_start(lo, i_old)
                for b in blocks:
                    b["expected_prefix"] = any(
                        b["first_line"].startswith(p) for p in EXPECTED_PREFIXES)
                    b["words"] = word_count("".join(
                        ln[b["line_no"] - 1: b["line_no"] - 1 + b["n_lines"]]))
                    # the block just before it, in v9h (immediate neighbour)
                    pn_no, pn_txt = previous_block_start(ln, b["line_no"] - 1)
                    b["block_before_in_v9h"] = {"line": pn_no, "text": short(pn_txt or "")}
                    if not b["expected_prefix"]:
                        result["unexpected"].append(
                            "%s: inserted block at v9h line %d has unexpected first line: %s"
                            % (name, b["line_no"], b["first_line"][:80]))
                    if b["leading_continuation"]:
                        result["unexpected"].append(
                            "%s: inserted run at v9h line %d starts mid-block (indented first line)"
                            % (name, b["line_no"]))
                if not at_boundary:
                    result["unexpected"].append(
                        "%s: insertion before v9g line %d is not at a block boundary "
                        "(next original line is indented)" % (name, i_old + 1))
                if not run_ends_block:
                    result["unexpected"].append(
                        "%s: inserted run ending at v9h line %d is followed by an "
                        "indented line (block split)" % (name, j2))
                ins_report.append({
                    "v9g_insert_point": {
                        "after_line": i_old, "after_text": short(prev_old or "<start of file>"),
                        "before_line": i_old + 1 if next_old is not None else None,
                        "before_text": short(next_old or "<end of file>")},
                    "v9h_lines": [j1 + 1, j2],
                    "n_inserted_lines": j2 - j1,
                    "at_block_boundary": at_boundary,
                    "run_ends_with_complete_block": run_ends_block,
                    "previous_original_block": {"v9g_line": pb_no, "text": short(pb_txt or "")},
                    "blocks": blocks,
                })
            result["insertions"][name] = {
                "insert_only": ok,
                "reconstruction_matches_v9g": recon_ok,
                "non_insert_ops": bad,
                "n_inserted_lines_total": sum(j2 - j1 for _, j1, j2 in inserts),
                "runs": ins_report,
            }
            if not ok:
                result["unexpected"].append(
                    "%s: %d non-insert diff op(s) (see non_insert_ops)" % (name, len(bad)))
            if ok and not recon_ok:
                result["unexpected"].append(
                    name + ": removing inserted lines does not give back v9g")

            # OUTPUT section
            so, txo, no = output_section(lo)
            sn, txn, nn = output_section(ln)
            result["output_sections"][name] = {
                "v9g": {"n_OUTPUT_lines": no, "start_line": so,
                        "lines": (len(lo) - so + 1) if so else None,
                        "words": word_count(txo) if txo else None},
                "v9h": {"n_OUTPUT_lines": nn, "start_line": sn,
                        "lines": (len(ln) - sn + 1) if sn else None,
                        "words": word_count(txn) if txn else None},
                "identical": (txo is not None) and (txo == txn),
                "inserted_lines_below_OUTPUT": [
                    j1 + 1 for _, j1, _ in inserts if sn and j1 + 1 >= sn],
            }
            if not result["output_sections"][name]["identical"]:
                result["unexpected"].append(name + ": OUTPUT sections differ")

    # Expected prefixes: each must appear exactly once per phase file in v9h
    for name in EXPECTED_INSERT_ONLY:
        found = [b["first_line"] for r in result["insertions"][name]["runs"]
                 for b in r["blocks"]]
        for p in EXPECTED_PREFIXES:
            n = sum(f.startswith(p) for f in found)
            if n != 1:
                result["unexpected"].append(
                    "%s: prefix %r found %d times among inserted blocks" % (name, p, n))

    out_path = os.path.join(HERE, "result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)

    # ------------------------------------------------------------------
    # Readable report
    # ------------------------------------------------------------------
    print("\nFILES (bytes / lines / words; words = whitespace-separated tokens)")
    for name in FILES:
        e = result["files"][name]
        g, h = e["v9g"], e["v9h"]
        print("  %-16s v9g %6d B %4d L %6d W | v9h %6d B %4d L %6d W | dW %+d | %s%s crlf=%d/%d"
              % (name, g["bytes"], g["lines"], g["words"], h["bytes"], h["lines"], h["words"],
                 e["word_delta"], "IDENTICAL" if e["identical"] else "differs",
                 " BOM" if g["bom"] or h["bom"] else "", g["crlf_lines"], h["crlf_lines"]))
    for name in EXPECTED_INSERT_ONLY:
        r = result["insertions"][name]
        print("\n%s: insert_only=%s reconstruction_matches_v9g=%s inserted_lines=%d"
              % (name, r["insert_only"], r["reconstruction_matches_v9g"], r["n_inserted_lines_total"]))
        for k, run in enumerate(r["runs"], 1):
            ip = run["v9g_insert_point"]
            print("  run %d: v9h lines %d-%d (%d lines), inserted after v9g line %s and before v9g line %s; boundary=%s complete=%s"
                  % (k, run["v9h_lines"][0], run["v9h_lines"][1], run["n_inserted_lines"],
                     ip["after_line"], ip["before_line"], run["at_block_boundary"],
                     run["run_ends_with_complete_block"]))
            print("     v9g line before : " + ip["after_text"])
            print("     v9g line after  : " + ip["before_text"])
            pb = run["previous_original_block"]
            print("     previous v9g block: line %s: %s" % (pb["v9g_line"], pb["text"]))
            for b in run["blocks"]:
                print("     block @v9h %d: %r (%d lines, %d words, expected=%s); block just before in v9h: line %s: %s"
                      % (b["line_no"], b["first_line"], b["n_lines"], b["words"], b["expected_prefix"],
                         b["block_before_in_v9h"]["line"], b["block_before_in_v9h"]["text"]))
        o = result["output_sections"][name]
        print("  OUTPUT section: identical=%s | v9g from line %s (%s lines, %s words) | v9h from line %s (%s lines, %s words) | OUTPUT lines found: %s/%s | insertions below OUTPUT: %s"
              % (o["identical"], o["v9g"]["start_line"], o["v9g"]["lines"], o["v9g"]["words"],
                 o["v9h"]["start_line"], o["v9h"]["lines"], o["v9h"]["words"],
                 o["v9g"]["n_OUTPUT_lines"], o["v9h"]["n_OUTPUT_lines"], o["inserted_lines_below_OUTPUT"]))
    print("\nUNEXPECTED DIFFERENCES:" if result["unexpected"] else "\nUNEXPECTED DIFFERENCES: none")
    for u in result["unexpected"]:
        print("  - " + u)
    if "line_diff" in result["files"].get("README.md", {}):
        print("\nREADME.md line diff (not in the expected list):")
        for l in result["files"]["README.md"]["line_diff"]:
            print("   " + l[:160])
    print("\nwrote " + out_path)


if __name__ == "__main__":
    main()
