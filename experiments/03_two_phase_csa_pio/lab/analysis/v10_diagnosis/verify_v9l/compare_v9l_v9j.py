"""Compare prompts/two_phase_v9l with prompts/two_phase_v9j file by file.

Self-contained: reads the two folders, compares bytes, locates the one
changed paragraph in phase2.md, and prints what it found. No API calls,
no imports from the run scripts.

Checks (each one PASS/FAIL, printed and written to result.json):
  C1  same set of file names in both folders
  C2  common.md, phase1.md, phase1_user.md, phase2_user.md byte-identical
  C3  phase2.md: same number of lines (paragraphs), so no block was
      inserted or removed
  C4  phase2.md: exactly one line differs, and it starts "4. Primary."
  C5  phase2.md: no line starting "- Walk-found internals." in either
  C6  the changed paragraph: the replacing text contains the expected
      precedence pieces (held line, crossing whole, decision or setting,
      "does not cite", "path", "labels it primary"); the replaced text
      contains none of them
  C7  the changed paragraph: after the replaced sentences, the rest of
      the paragraph is byte-identical in both versions
Self-test: the script's own line splitting is checked against the
byte lengths of the files (sum of line bytes == file bytes), and the
prefix + replaced + suffix split is asserted to rebuild each paragraph.
"""
import difflib
import json
import os
import re
import sys

LAB = r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab"
A = os.path.join(LAB, "prompts", "two_phase_v9j")   # before
B = os.path.join(LAB, "prompts", "two_phase_v9l")   # after
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "result.json")

EXPECT_IDENTICAL = ["common.md", "phase1.md", "phase1_user.md", "phase2_user.md"]
TARGET = "phase2.md"
PARA_START = "4. Primary."
FORBIDDEN_BLOCK = "- Walk-found internals."


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def split_lines_keep(data):
    """Split on newline, keeping the terminator on each piece.
    A paragraph in these prompt files is one line."""
    out = []
    start = 0
    while True:
        i = data.find(b"\n", start)
        if i < 0:
            if start < len(data):
                out.append(data[start:])
            break
        out.append(data[start:i + 1])
        start = i + 1
    return out


def words(s):
    return s.split()


def sentences(s):
    """Split on a period followed by space and an uppercase letter, digit
    or open bracket. Only for the human-readable listing, not for any
    PASS/FAIL."""
    parts = re.split(r"(?<=\.)\s+(?=[A-Z(\d])", s)
    return [p for p in parts if p]


def main():
    result = {"checks": {}, "figures": {}, "files": {}}
    ok_all = True

    def check(name, ok, detail):
        nonlocal ok_all
        result["checks"][name] = {"pass": bool(ok), "detail": detail}
        ok_all = ok_all and bool(ok)
        print("[%s] %s: %s" % ("PASS" if ok else "FAIL", name, detail))

    names_a = sorted(os.listdir(A))
    names_b = sorted(os.listdir(B))
    print("v9j files:", names_a)
    print("v9l files:", names_b)
    check("C1_same_file_names", names_a == names_b,
          "v9j=%s v9l=%s" % (names_a, names_b))

    # --- file-level byte comparison for every file
    file_rows = {}
    for n in sorted(set(names_a) | set(names_b)):
        pa, pb = os.path.join(A, n), os.path.join(B, n)
        if not (os.path.isfile(pa) and os.path.isfile(pb)):
            file_rows[n] = {"in_v9j": os.path.isfile(pa), "in_v9l": os.path.isfile(pb)}
            continue
        da, db = read_bytes(pa), read_bytes(pb)
        la, lb = split_lines_keep(da), split_lines_keep(db)
        # self-test of the splitter: bytes must be conserved
        assert sum(len(x) for x in la) == len(da), n
        assert sum(len(x) for x in lb) == len(db), n
        diff_idx = [i for i in range(min(len(la), len(lb))) if la[i] != lb[i]]
        file_rows[n] = {
            "bytes_v9j": len(da), "bytes_v9l": len(db),
            "lines_v9j": len(la), "lines_v9l": len(lb),
            "identical": da == db,
            "crlf_v9j": b"\r\n" in da, "crlf_v9l": b"\r\n" in db,
            "bom_v9j": da.startswith(b"\xef\xbb\xbf"), "bom_v9l": db.startswith(b"\xef\xbb\xbf"),
            "differing_line_numbers_1based": [i + 1 for i in diff_idx],
            "line_count_difference": abs(len(la) - len(lb)),
        }
    result["files"] = file_rows
    for n, r in file_rows.items():
        print(n, json.dumps(r))

    ident = dict((n, file_rows[n].get("identical")) for n in EXPECT_IDENTICAL)
    check("C2_four_files_byte_identical", all(ident.values()), str(ident))

    # --- phase2.md paragraph-level comparison
    da = read_bytes(os.path.join(A, TARGET))
    db = read_bytes(os.path.join(B, TARGET))
    la, lb = split_lines_keep(da), split_lines_keep(db)
    check("C3_phase2_same_line_count", len(la) == len(lb),
          "v9j lines=%d v9l lines=%d" % (len(la), len(lb)))

    sm = difflib.SequenceMatcher(a=la, b=lb, autojunk=False)
    ops = [op for op in sm.get_opcodes() if op[0] != "equal"]
    ops_desc = []
    for tag, i1, i2, j1, j2 in ops:
        ops_desc.append({"op": tag, "v9j_lines_1based": [i1 + 1, i2],
                         "v9l_lines_1based": [j1 + 1, j2],
                         "v9j_starts": [la[k][:40].decode("utf-8", "replace") for k in range(i1, i2)],
                         "v9l_starts": [lb[k][:40].decode("utf-8", "replace") for k in range(j1, j2)]})
    result["phase2_line_ops"] = ops_desc
    print("phase2.md non-equal opcodes:", json.dumps(ops_desc, indent=1))

    one_replace = (len(ops) == 1 and ops[0][0] == "replace"
                   and ops[0][2] - ops[0][1] == 1 and ops[0][4] - ops[0][3] == 1)
    starts_ok = False
    if one_replace:
        i = ops[0][1]
        ta = la[i].decode("utf-8")
        tb = lb[ops[0][3]].decode("utf-8")
        starts_ok = ta.startswith(PARA_START) and tb.startswith(PARA_START)
    check("C4_only_the_primary_paragraph_differs", one_replace and starts_ok,
          "non-equal ops=%d; single 1-line replace=%s; both start with %r=%s"
          % (len(ops), one_replace, PARA_START, starts_ok))

    wf_a = [k + 1 for k, x in enumerate(la) if x.startswith(FORBIDDEN_BLOCK.encode())]
    wf_b = [k + 1 for k, x in enumerate(lb) if x.startswith(FORBIDDEN_BLOCK.encode())]
    sub_a = da.count(FORBIDDEN_BLOCK.encode())
    sub_b = db.count(FORBIDDEN_BLOCK.encode())
    check("C5_no_walk_found_internals_block",
          not wf_a and not wf_b and sub_a == 0 and sub_b == 0,
          "line-start hits v9j=%s v9l=%s; substring count v9j=%d v9l=%d"
          % (wf_a, wf_b, sub_a, sub_b))

    other_diffs = [k + 1 for k in range(min(len(la), len(lb)))
                   if la[k] != lb[k] and not la[k].startswith(PARA_START.encode())]
    result["figures"]["phase2_other_differing_lines_1based"] = other_diffs

    # --- inside the paragraph
    n_para_a = sum(1 for x in la if x.startswith(PARA_START.encode()))
    n_para_b = sum(1 for x in lb if x.startswith(PARA_START.encode()))
    result["figures"]["paragraphs_starting_4_Primary_v9j"] = n_para_a
    result["figures"]["paragraphs_starting_4_Primary_v9l"] = n_para_b
    print("paragraphs starting %r: v9j=%d v9l=%d" % (PARA_START, n_para_a, n_para_b))
    para_a = next(x.decode("utf-8") for x in la if x.startswith(PARA_START.encode()))
    para_b = next(x.decode("utf-8") for x in lb if x.startswith(PARA_START.encode()))
    line_no_a = next(k + 1 for k, x in enumerate(la) if x.startswith(PARA_START.encode()))
    line_no_b = next(k + 1 for k, x in enumerate(lb) if x.startswith(PARA_START.encode()))
    result["figures"]["paragraph_line_number_v9j"] = line_no_a
    result["figures"]["paragraph_line_number_v9l"] = line_no_b
    pa_s, pb_s = para_a.rstrip("\r\n"), para_b.rstrip("\r\n")
    wa, wb = words(pa_s), words(pb_s)
    result["figures"]["paragraph_words_v9j"] = len(wa)
    result["figures"]["paragraph_words_v9l"] = len(wb)
    result["figures"]["paragraph_words_delta"] = len(wb) - len(wa)
    result["figures"]["paragraph_chars_v9j"] = len(pa_s)
    result["figures"]["paragraph_chars_v9l"] = len(pb_s)
    result["figures"]["paragraph_bytes_delta_equals_file_bytes_delta"] = (
        (len(para_b.encode("utf-8")) - len(para_a.encode("utf-8"))) == (len(db) - len(da)))
    print("paragraph words (whitespace-split): v9j=%d v9l=%d delta=%d"
          % (len(wa), len(wb), len(wb) - len(wa)))
    print("paragraph chars: v9j=%d v9l=%d" % (len(pa_s), len(pb_s)))

    # exact replaced / replacing text = strip common prefix and common suffix
    p = 0
    while p < min(len(pa_s), len(pb_s)) and pa_s[p] == pb_s[p]:
        p += 1
    s = 0
    while (s < min(len(pa_s), len(pb_s)) - p
           and pa_s[len(pa_s) - 1 - s] == pb_s[len(pb_s) - 1 - s]):
        s += 1
    # snap both cuts back to a word boundary so the text reads whole
    while p > 0 and pa_s[p - 1] != " ":
        p -= 1
    while s > 0 and pa_s[len(pa_s) - s] != " ":
        s -= 1
    replaced = pa_s[p:len(pa_s) - s]
    replacing = pb_s[p:len(pb_s) - s]
    common_prefix = pa_s[:p]
    common_suffix = pa_s[len(pa_s) - s:]
    assert common_prefix + replaced + common_suffix == pa_s
    assert common_prefix + replacing + common_suffix == pb_s
    result["figures"]["common_prefix"] = common_prefix
    result["figures"]["replaced_text_v9j"] = replaced
    result["figures"]["replacing_text_v9l"] = replacing
    result["figures"]["common_suffix_first_120_chars"] = common_suffix[:120]
    result["figures"]["common_suffix_chars"] = len(common_suffix)
    result["figures"]["replaced_words"] = len(words(replaced))
    result["figures"]["replacing_words"] = len(words(replacing))
    result["figures"]["common_prefix_words"] = len(words(common_prefix))
    result["figures"]["common_suffix_words"] = len(words(common_suffix))
    print("\n--- common prefix ---")
    print(common_prefix)
    print("\n--- REPLACED (v9j) ---")
    print(replaced)
    print("\n--- REPLACING (v9l) ---")
    print(replacing)
    print("\n--- common suffix (first 200 chars) ---")
    print(common_suffix[:200])
    print("\ncommon suffix: %d chars, %d words" % (len(common_suffix), len(words(common_suffix))))
    print("replaced: %d words; replacing: %d words"
          % (len(words(replaced)), len(words(replacing))))

    # word-level diff of the paragraph, as a second view
    wsm = difflib.SequenceMatcher(a=wa, b=wb, autojunk=False)
    wops = [(t, i1, i2, j1, j2) for t, i1, i2, j1, j2 in wsm.get_opcodes() if t != "equal"]
    result["figures"]["paragraph_word_level_nonequal_ops"] = [
        {"op": t, "v9j_words": [i1, i2], "v9l_words": [j1, j2],
         "v9j_text": " ".join(wa[i1:i2]), "v9l_text": " ".join(wb[j1:j2])}
        for t, i1, i2, j1, j2 in wops]
    print("\nword-level non-equal ops in the paragraph:", len(wops))
    for t, i1, i2, j1, j2 in wops:
        print("  %s: v9j words[%d:%d] -> v9l words[%d:%d]" % (t, i1, i2, j1, j2))
    # the last word-level op must end before the first word of the common suffix
    last_op_end_a = max([i2 for _, _, i2, _, _ in wops] or [0])
    result["figures"]["word_ops_all_before_suffix"] = (
        last_op_end_a <= len(wa) - len(words(common_suffix)))

    # C6: new pieces present in the replacing text and absent from the replaced
    # text; kept pieces present in both
    new_pieces = {
        "precedence": "precedence",
        "held_line_of_entry": "held line of its CONCEPTS entry",
        "decision_or_setting_at_held_line": "the element that holds or makes it at such a held line",
        "does_not_cite": "does not cite as held lines",
        "is_a_path": "is a path to the primary",
        "unless_below_labels_primary": "unless a sentence or block below labels it primary",
    }
    kept_pieces = {
        "stored_or_computed": "where its value is stored or computed in this unit",
        "crosses_whole": "where it crosses the unit's boundary whole",
        "decision_or_setting": "for a decision or setting, the element that holds or makes it",
    }
    new_b = dict((k, (v in replacing)) for k, v in new_pieces.items())
    new_a = dict((k, (v in replaced)) for k, v in new_pieces.items())
    kept_b = dict((k, (v in replacing)) for k, v in kept_pieces.items())
    kept_a = dict((k, (v in replaced)) for k, v in kept_pieces.items())
    result["figures"]["new_pieces_in_replacing_v9l"] = new_b
    result["figures"]["new_pieces_in_replaced_v9j"] = new_a
    result["figures"]["kept_pieces_in_replacing_v9l"] = kept_b
    result["figures"]["kept_pieces_in_replaced_v9j"] = kept_a
    check("C6_new_pieces_in_v9l_only_kept_pieces_in_both",
          all(new_b.values()) and not any(new_a.values())
          and all(kept_b.values()) and all(kept_a.values()),
          "new in v9l=%s; new in v9j=%s; kept in v9l=%s; kept in v9j=%s"
          % (new_b, new_a, kept_b, kept_a))

    # C7: common suffix covers the rest of the paragraph from "Outside a coprocessor" on
    check("C7_rest_of_paragraph_identical",
          common_suffix.startswith(" Outside a coprocessor"),
          "suffix starts %r; suffix words=%d" % (common_suffix[:40], len(words(common_suffix))))

    result["figures"]["replaced_sentences"] = sentences(replaced)
    result["figures"]["replacing_sentences"] = sentences(replacing)
    print("\nreplaced sentences:", len(sentences(replaced)))
    for x in sentences(replaced):
        print("  J|", x)
    print("replacing sentences:", len(sentences(replacing)))
    for x in sentences(replacing):
        print("  L|", x)

    rd = file_rows.get("README.md", {})
    result["figures"]["readme_identical"] = rd.get("identical")
    # README.md is expected to differ (it names the version); list its lines
    ra = split_lines_keep(read_bytes(os.path.join(A, "README.md")))
    rb = split_lines_keep(read_bytes(os.path.join(B, "README.md")))
    result["figures"]["readme_lines_v9j"] = [x.decode("utf-8").rstrip("\r\n") for x in ra]
    result["figures"]["readme_lines_v9l"] = [x.decode("utf-8").rstrip("\r\n") for x in rb]
    print("\nREADME.md v9j (%d lines):" % len(ra))
    for k, x in enumerate(ra):
        print("  %d| %s" % (k + 1, x.decode("utf-8").rstrip("\r\n")))
    print("README.md v9l (%d lines):" % len(rb))
    for k, x in enumerate(rb):
        print("  %d| %s" % (k + 1, x.decode("utf-8").rstrip("\r\n")))

    result["all_pass"] = ok_all
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print("\nALL CHECKS PASS" if ok_all else "\nSOME CHECK FAILED")
    print("wrote", OUT)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
