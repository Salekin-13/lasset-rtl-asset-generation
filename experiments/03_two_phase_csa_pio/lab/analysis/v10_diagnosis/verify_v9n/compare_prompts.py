"""Compare prompt versions with two_phase_v9j file by file.

Pure file comparison. No imports from the lab, no API calls.

For every version listed in VERSIONS:
  * every *.md file in either folder is compared byte for byte with v9j;
  * every differing file is listed with its differing lines (1-based, as in
    the file; lines are split on the file's own CRLF/LF endings);
  * for phase2.md the script checks whether the only differing line is the
    paragraph that starts "4. Primary." and, if so, prints the word counts of
    that paragraph in both versions and the exact replaced / replacing text.

Run:  python -B compare_prompts.py
"""
import difflib
import os

LAB = r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab"
PROMPTS = os.path.join(LAB, "prompts")
BASE = "two_phase_v9j"
VERSIONS = ["two_phase_v9n_place_dbg", "two_phase_v9n_place"]
EXPECTED_IDENTICAL = ["common.md", "phase1.md", "phase1_user.md", "phase2_user.md"]
PARA_START = "4. Primary."


# ---------------------------------------------------------------- helpers
def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def split_lines(data):
    """Split raw bytes into text lines, keeping the file's line endings.

    Returns a list of str (decoded as UTF-8). Each item keeps its own ending
    so that a CRLF/LF difference would show up as a difference.
    """
    return data.decode("utf-8").splitlines(keepends=True)


def strip_eol(line):
    return line.rstrip("\r\n")


def word_count(text):
    """Number of whitespace-separated tokens."""
    return len(text.split())


def common_prefix_len(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def common_suffix_len(a, b, limit):
    """Longest common suffix, not overlapping the first `limit` chars."""
    i = 0
    while (i < len(a) - limit and i < len(b) - limit
           and a[len(a) - 1 - i] == b[len(b) - 1 - i]):
        i += 1
    return i


def changed_span(old, new):
    """Return (prefix, old_mid, new_mid, suffix) with the mid parts extended
    to sentence boundaries ('. ' or start/end) so the replaced text reads as
    whole sentences."""
    p = common_prefix_len(old, new)
    s = common_suffix_len(old, new, p)
    # extend the start back to the previous sentence end ". " (or 0)
    start = old.rfind(". ", 0, p)
    start = 0 if start < 0 else start + 2
    # extend the end forward to the next sentence end ". " (or the end)
    old_end = len(old) - s
    new_end = len(new) - s
    e_old = old.find(". ", old_end)
    e_old = len(old) if e_old < 0 else e_old + 1
    # the suffix is shared, so the same extension applies to new
    ext = e_old - old_end
    e_new = new_end + ext
    assert old[e_old:] == new[e_new:], "suffix alignment broke"
    assert old[:start] == new[:start], "prefix alignment broke"
    return old[:start], old[start:e_old], new[start:e_new], old[e_old:]


def line_diff(old_lines, new_lines):
    """Return (tag, old_idx, old_line, new_idx, new_line) for differing lines.

    Indices are 1-based line numbers in each file. Uses difflib opcodes.
    """
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            # pair them up as far as they go, then the rest as delete/insert
            k = min(i2 - i1, j2 - j1)
            for n in range(k):
                out.append(("changed", i1 + n + 1, old_lines[i1 + n],
                            j1 + n + 1, new_lines[j1 + n]))
            for n in range(k, i2 - i1):
                out.append(("removed", i1 + n + 1, old_lines[i1 + n], None, None))
            for n in range(k, j2 - j1):
                out.append(("added", None, None, j1 + n + 1, new_lines[j1 + n]))
        elif tag == "delete":
            for n in range(i1, i2):
                out.append(("removed", n + 1, old_lines[n], None, None))
        elif tag == "insert":
            for n in range(j1, j2):
                out.append(("added", None, None, n + 1, new_lines[n]))
    return out


# ---------------------------------------------------------------- self-test
def self_test():
    # word_count
    assert word_count("a b  c\r\n") == 3
    assert word_count("") == 0
    # changed_span on a hand-made pair: only the second sentence changes
    old = "4. Primary. Old one. Old two. Same tail. End."
    new = "4. Primary. New one and more. Same tail. End."
    pre, om, nm, suf = changed_span(old, new)
    assert pre == "4. Primary. ", repr(pre)
    assert om == "Old one. Old two.", repr(om)
    assert nm == "New one and more.", repr(nm)
    assert suf == " Same tail. End.", repr(suf)
    assert pre + om + suf == old and pre + nm + suf == new
    # line_diff: one changed line, one added line, one changed last line
    a = ["x\r\n", "y\r\n", "z\r\n", "q\r\n"]
    b = ["x\r\n", "Y\r\n", "z\r\n", "z2\r\n", "q2\r\n"]
    d = line_diff(a, b)
    tags = [(t, i, j) for t, i, _, j, _ in d]
    assert ("changed", 2, 2) in tags, tags
    # every differing line on each side must be reported exactly once
    old_side = sorted(i for _, i, _ in tags if i is not None)
    new_side = sorted(j for _, _, j in tags if j is not None)
    assert old_side == [2, 4], old_side
    assert new_side == [2, 4, 5], new_side
    # and unchanged lines must not be reported
    assert 1 not in old_side and 3 not in old_side
    # split_lines keeps endings and counts lines as the newline count
    data = b"a\r\nb\r\nc\r\n"
    ls = split_lines(data)
    assert len(ls) == data.count(b"\n") == 3
    assert ls[0] == "a\r\n"
    return True


# ---------------------------------------------------------------- main
def compare_version(version, log):
    base_dir = os.path.join(PROMPTS, BASE)
    ver_dir = os.path.join(PROMPTS, version)
    log("\n" + "=" * 78 + "\nVERSION " + version + "  vs  " + BASE + "\n" + "=" * 78)
    base_files = sorted(f for f in os.listdir(base_dir) if f.endswith(".md"))
    ver_files = sorted(f for f in os.listdir(ver_dir) if f.endswith(".md"))
    log("files in %s: %s" % (BASE, base_files))
    log("files in %s: %s" % (version, ver_files))
    only_base = [f for f in base_files if f not in ver_files]
    only_ver = [f for f in ver_files if f not in base_files]
    if only_base:
        log("MISSING in %s: %s" % (version, only_base))
    if only_ver:
        log("EXTRA in %s: %s" % (version, only_ver))

    result = {"identical": [], "differing": {}, "missing": only_base,
              "extra": only_ver}
    for fname in base_files:
        if fname not in ver_files:
            continue
        b = read_bytes(os.path.join(base_dir, fname))
        v = read_bytes(os.path.join(ver_dir, fname))
        if b == v:
            result["identical"].append(fname)
            log("  %-16s byte-identical (%d bytes)" % (fname, len(b)))
            continue
        bl, vl = split_lines(b), split_lines(v)
        # sanity: line count equals newline count (+1 if no final newline)
        assert len(bl) == b.count(b"\n") + (0 if b.endswith(b"\n") else 1)
        assert len(vl) == v.count(b"\n") + (0 if v.endswith(b"\n") else 1)
        diffs = line_diff(bl, vl)
        result["differing"][fname] = diffs
        log("  %-16s DIFFERS: %d -> %d bytes, %d -> %d lines, %d differing line(s)"
            % (fname, len(b), len(v), len(bl), len(vl), len(diffs)))
        for tag, i, ol, j, nl in diffs:
            if tag == "changed":
                log("    line %s (%s) -> line %s (%s): changed" % (i, BASE, j, version))
                log("      OLD [%d words, %d chars]: %s"
                    % (word_count(ol), len(strip_eol(ol)), strip_eol(ol)))
                log("      NEW [%d words, %d chars]: %s"
                    % (word_count(nl), len(strip_eol(nl)), strip_eol(nl)))
            elif tag == "removed":
                log("    line %s (%s): removed" % (i, BASE))
                log("      OLD [%d words]: %s" % (word_count(ol), strip_eol(ol)))
            else:
                log("    line %s (%s): added" % (j, version))
                log("      NEW [%d words]: %s" % (word_count(nl), strip_eol(nl)))

    # expected-identical check
    for fname in EXPECTED_IDENTICAL:
        ok = fname in result["identical"]
        log("  expected identical: %-16s %s" % (fname, "PASS" if ok else "FAIL"))

    # phase2.md: is the only change inside the "4. Primary." paragraph?
    if "phase2.md" in result["differing"]:
        diffs = result["differing"]["phase2.md"]
        bl = split_lines(read_bytes(os.path.join(base_dir, "phase2.md")))
        vl = split_lines(read_bytes(os.path.join(ver_dir, "phase2.md")))
        para_base = [k + 1 for k, l in enumerate(bl) if l.startswith(PARA_START)]
        para_ver = [k + 1 for k, l in enumerate(vl) if l.startswith(PARA_START)]
        log("  phase2.md: lines starting %r: %s %s, %s %s"
            % (PARA_START, BASE, para_base, version, para_ver))
        in_para = [d for d in diffs if d[0] == "changed" and d[1] in para_base]
        other = [d for d in diffs if d not in in_para]
        log("  phase2.md: differing lines inside that paragraph: %d; outside it: %d"
            % (len(in_para), len(other)))
        if other:
            log("  phase2.md: OTHER differences (outside the paragraph):")
            for tag, i, ol, j, nl in other:
                log("    %s: %s line %s, %s line %s" % (tag, BASE, i, version, j))
        if len(para_base) == 1 and len(in_para) == 1:
            _, i, ol, j, nl = in_para[0]
            o, n = strip_eol(ol), strip_eol(nl)

            # blank-line-delimited block around the paragraph line (Markdown
            # paragraph = run of non-blank lines)
            def block(lines, idx1):
                k = idx1 - 1
                s = k
                while s > 0 and strip_eol(lines[s - 1]) != "":
                    s -= 1
                e = k
                while e + 1 < len(lines) and strip_eol(lines[e + 1]) != "":
                    e += 1
                return s + 1, e + 1, "".join(lines[s:e + 1])

            bs, be, btxt = block(bl, i)
            vs, ve, vtxt = block(vl, j)
            log("  paragraph line %d: word count %s = %d, %s = %d "
                "(whitespace-split tokens); chars %d -> %d"
                % (i, BASE, word_count(o), version, word_count(n), len(o), len(n)))
            log("  blank-line-delimited block: %s lines %d-%d = %d words; "
                "%s lines %d-%d = %d words"
                % (BASE, bs, be, word_count(btxt), version, vs, ve, word_count(vtxt)))
            pre, om, nm, suf = changed_span(o, n)
            assert pre + om + suf == o and pre + nm + suf == n
            log("  unchanged prefix (%d chars): %r" % (len(pre), pre))
            log("  REPLACED text (%d words, %d chars):\n    %s"
                % (word_count(om), len(om), om))
            log("  REPLACING text (%d words, %d chars):\n    %s"
                % (word_count(nm), len(nm), nm))
            log("  unchanged suffix: %d chars, %d words (starts %r)"
                % (len(suf), word_count(suf), suf[:60]))
            # also a word-level opcode view, to show nothing else moved
            ow, nw = o.split(), n.split()
            sm = difflib.SequenceMatcher(None, ow, nw, autojunk=False)
            ops = [op for op in sm.get_opcodes() if op[0] != "equal"]
            log("  word-level non-equal opcodes: %d" % len(ops))
            for tag, i1, i2, j1, j2 in ops:
                log("    %s: old words %d-%d -> new words %d-%d" % (tag, i1, i2, j1, j2))
    return result


def main():
    assert self_test(), "self-test failed"
    lines = []

    def log(s):
        print(s)
        lines.append(s)

    log("self-test: PASS")
    log("prompts root: " + PROMPTS)
    results = {}
    for v in VERSIONS:
        results[v] = compare_version(v, log)

    log("\n" + "=" * 78 + "\nSUMMARY\n" + "=" * 78)
    for v, r in results.items():
        log("%s: identical=%s; differing=%s; missing=%s; extra=%s"
            % (v, r["identical"], {k: len(d) for k, d in r["differing"].items()},
               r["missing"], r["extra"]))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "compare_output.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n[written] " + out)


if __name__ == "__main__":
    main()
