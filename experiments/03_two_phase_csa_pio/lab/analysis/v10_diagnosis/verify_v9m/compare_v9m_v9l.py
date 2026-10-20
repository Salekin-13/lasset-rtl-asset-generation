"""Compare prompts/two_phase_v9m with prompts/two_phase_v9l file by file.

Expected (from the task):
  common.md, phase1.md, phase1_user.md : byte-identical
  phase2_user.md : only an added section between CONCEPTS and the final
                   "Do Phase 2" line, headed "=== LOCATED", holding "{located}"
  phase2.md      : (a) one added paragraph before "Steps, for each conceptual
                   asset in CONCEPTS:" starting "A second input, LOCATED:"
                   (b) a change inside the one paragraph starting "4. Primary."
Everything else is reported as "outside expected".
No API calls, no imports from the lab; standard library only.
"""
import difflib
import hashlib
import os
import sys

ROOT = r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab\prompts"
OLD = os.path.join(ROOT, "two_phase_v9l")
NEW = os.path.join(ROOT, "two_phase_v9m")
EXPECT_IDENTICAL = ["common.md", "phase1.md", "phase1_user.md"]
FILES = ["README.md", "common.md", "phase1.md", "phase1_user.md", "phase2.md", "phase2_user.md"]


def read_bytes(folder, name):
    with open(os.path.join(folder, name), "rb") as f:
        return f.read()


def lines_of(b):
    # line endings are compared separately; here CRLF and LF are the same
    return b.decode("utf-8").replace("\r\n", "\n").split("\n")


def md5(b):
    return hashlib.md5(b).hexdigest()


def common_affix(a, b):
    """Character-level common prefix and suffix lengths of two strings."""
    p = 0
    while p < min(len(a), len(b)) and a[p] == b[p]:
        p += 1
    s = 0
    while s < min(len(a), len(b)) - p and a[-1 - s] == b[-1 - s]:
        s += 1
    return p, s


def sentence_bounds(text, start, end):
    """Widen [start, end) to the enclosing sentence(s): back to the previous
    '. ' (or the line start) and forward to the next '. ' (or the line end)."""
    s = text.rfind(". ", 0, start)
    s = 0 if s < 0 else s + 2
    e = text.find(". ", end)
    e = len(text) if e < 0 else e + 1
    return s, e


def main():
    out = []
    problems = []
    pr = out.append

    # --- 0. folder contents -------------------------------------------------
    old_names = sorted(os.listdir(OLD))
    new_names = sorted(os.listdir(NEW))
    pr("v9l files: " + repr(old_names))
    pr("v9m files: " + repr(new_names))
    if old_names != new_names:
        problems.append("file sets differ: only in v9l %r, only in v9m %r" % (
            sorted(set(old_names) - set(new_names)), sorted(set(new_names) - set(old_names))))

    data = {}
    for name in FILES:
        data[name] = (read_bytes(OLD, name), read_bytes(NEW, name))

    # self-test against a hand-read fact: md5sum in this session printed
    # 7f2433dc358330d190cb5ecb829e68cd for common.md in both folders, and
    # phase2.md sizes 74370 (v9l) / 74724 (v9m) from ls -la.
    assert md5(data["common.md"][0]) == "7f2433dc358330d190cb5ecb829e68cd", "self-test failed: common.md md5 v9l"
    assert md5(data["common.md"][1]) == "7f2433dc358330d190cb5ecb829e68cd", "self-test failed: common.md md5 v9m"
    assert len(data["phase2.md"][0]) == 74370 and len(data["phase2.md"][1]) == 74724, "self-test failed: phase2.md sizes"
    pr("self-test PASS (common.md md5 and phase2.md byte sizes match the hand-read md5sum / ls output)")

    # --- 1. byte identity ---------------------------------------------------
    pr("")
    pr("== byte identity ==")
    for name in FILES:
        a, b = data[name]
        same = a == b
        pr("%-16s v9l %6d B  v9m %6d B  identical=%s" % (name, len(a), len(b), same))
        if name in EXPECT_IDENTICAL and not same:
            problems.append(name + " expected byte-identical but differs")
    if data["README.md"][0] != data["README.md"][1]:
        pr("README.md differs (not a prompt file; not in the expected list, so reported as outside expected):")
        for l in difflib.unified_diff(lines_of(data["README.md"][0]), lines_of(data["README.md"][1]),
                                      "v9l/README.md", "v9m/README.md", lineterm="", n=0):
            pr("   " + l)
        problems.append("README.md differs (outside the expected list; it is the note file, not a prompt file)")

    # --- 2. phase2_user.md --------------------------------------------------
    pr("")
    pr("== phase2_user.md ==")
    a, b = (lines_of(x) for x in data["phase2_user.md"])
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    ops = [op for op in sm.get_opcodes() if op[0] != "equal"]
    pr("non-equal opcodes: %d" % len(ops))
    ok_user = False
    for tag, i1, i2, j1, j2 in ops:
        pr("  %s: v9l lines %d-%d -> v9m lines %d-%d" % (tag, i1 + 1, i2, j1 + 1, j2))
        for l in a[i1:i2]:
            pr("    - " + repr(l))
        for l in b[j1:j2]:
            pr("    + " + repr(l))
    if len(ops) == 1 and ops[0][0] == "insert":
        tag, i1, i2, j1, j2 = ops[0]
        ins = b[j1:j2]
        before = a[:i1]
        after = a[i1:]
        concepts_idx = max([k for k, l in enumerate(before) if l.startswith("=== CONCEPTS")] or [-1])
        do_idx = min([k for k, l in enumerate(after) if l.startswith("Do Phase 2")] or [-1])
        headed = any(l.startswith("=== LOCATED") for l in ins)
        placeholder = any("{located}" in l for l in ins)
        only_concepts_between = (concepts_idx >= 0
                                 and all(l.strip() == "" or l == "{concepts}" for l in before[concepts_idx + 1:])
                                 and do_idx >= 0 and all(l.strip() == "" for l in after[:do_idx]))
        pr("  inserted block after the CONCEPTS section: %s; before the 'Do Phase 2' line: %s; "
           "headed '=== LOCATED': %s; holds '{located}': %s; only the {concepts} line and blanks around it: %s"
           % (concepts_idx >= 0, do_idx >= 0, headed, placeholder, only_concepts_between))
        ok_user = concepts_idx >= 0 and do_idx >= 0 and headed and placeholder and only_concepts_between
    pr("phase2_user.md matches expectation: %s" % ok_user)
    if not ok_user:
        problems.append("phase2_user.md differs from v9l in a way other than the expected LOCATED insert")

    # --- 3. phase2.md -------------------------------------------------------
    pr("")
    pr("== phase2.md ==")
    a, b = (lines_of(x) for x in data["phase2.md"])
    pr("line counts (CRLF->LF, split on newline): v9l %d  v9m %d" % (len(a), len(b)))
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    ops = [op for op in sm.get_opcodes() if op[0] != "equal"]
    pr("non-equal opcodes: %d" % len(ops))
    seen_a = seen_b = False
    other = []
    for tag, i1, i2, j1, j2 in ops:
        old_block, new_block = a[i1:i2], b[j1:j2]
        desc = "%s: v9l lines %d-%d -> v9m lines %d-%d" % (tag, i1 + 1, i2, j1 + 1, j2)
        # (a) inserted paragraph before "Steps, for each conceptual asset in CONCEPTS:".
        # difflib may align the insert as [paragraph, blank] before the "Steps" line or as
        # [blank, paragraph] before the blank line that precedes "Steps"; both are the same bytes.
        nonblank = [l for l in new_block if l.strip() != ""]
        nxt = next((l for l in a[i1:] if l.strip() != ""), "")
        if (tag == "insert" and not seen_a
                and len(nonblank) == 1 and nonblank[0].startswith("A second input, LOCATED:")
                and nxt.startswith("Steps, for each conceptual asset in CONCEPTS:")
                and j2 < len(b) and b[j2:j2 + 2] in ([ "Steps, for each conceptual asset in CONCEPTS:"], ["", "Steps, for each conceptual asset in CONCEPTS:"])):
            seen_a = True
            pr("(a) %s: inserted %d line(s) (the paragraph + %d blank); the next non-blank v9l line is the 'Steps, ...' line"
               % (desc, len(new_block), len(new_block) - 1))
            pr("    v9m line %d: %s" % (j1 + 1 + new_block.index(nonblank[0]), repr(nonblank[0])))
            pr("    words (whitespace-split): %d" % len(nonblank[0].split()))
            continue
        # (b) one changed line, the "4. Primary." paragraph
        if (tag == "replace" and not seen_b and len(old_block) == 1 and len(new_block) == 1
                and old_block[0].startswith("4. Primary.") and new_block[0].startswith("4. Primary.")):
            seen_b = True
            o, n = old_block[0], new_block[0]
            p, s = common_affix(o, n)
            replaced, replacing = o[p:len(o) - s], n[p:len(n) - s]
            pr("(b) %s: the '4. Primary.' paragraph (one line) changed" % desc)
            pr("    v9l paragraph: %d chars, %d words (whitespace-split)" % (len(o), len(o.split())))
            pr("    v9m paragraph: %d chars, %d words (whitespace-split)" % (len(n), len(n.split())))
            pr("    char-level common prefix %d, common suffix %d" % (p, s))
            pr("    REPLACED  (v9l): " + repr(replaced))
            pr("    REPLACING (v9m): " + repr(replacing))
            so, eo = sentence_bounds(o, p, len(o) - s)
            sn, en = sentence_bounds(n, p, len(n) - s)
            pr("    v9l sentence(s) holding the change [chars %d-%d]: %s" % (so, eo, repr(o[so:eo])))
            pr("    v9m sentence(s) holding the change [chars %d-%d]: %s" % (sn, en, repr(n[sn:en])))
            pr("    'held lines' (case-insensitive) in the v9l paragraph: %d; in v9m: %d"
               % (o.lower().count("held lines"), n.lower().count("held lines")))
            pr("    'LOCATED' in the v9l paragraph: %d; in v9m: %d" % (o.count("LOCATED"), n.count("LOCATED")))
            # word-level diff of the changed region, for a second view
            ow, nw = o.split(), n.split()
            wsm = difflib.SequenceMatcher(None, ow, nw, autojunk=False)
            for wtag, wi1, wi2, wj1, wj2 in wsm.get_opcodes():
                if wtag != "equal":
                    pr("    word-level %s: v9l words %d-%d %r -> v9m words %d-%d %r"
                       % (wtag, wi1 + 1, wi2, " ".join(ow[wi1:wi2]), wj1 + 1, wj2, " ".join(nw[wj1:wj2])))
            continue
        other.append((desc, old_block, new_block))
    for desc, ob, nb in other:
        pr("OUTSIDE EXPECTED: " + desc)
        for l in ob:
            pr("    - " + repr(l))
        for l in nb:
            pr("    + " + repr(l))
        problems.append("phase2.md unexpected change: " + desc)
    if not seen_a:
        problems.append("phase2.md: expected insert (a) 'A second input, LOCATED:' before 'Steps, ...' not found")
    if not seen_b:
        problems.append("phase2.md: expected change (b) inside the '4. Primary.' paragraph not found")
    pr("phase2.md: (a) found=%s, (b) found=%s, other diffs=%d" % (seen_a, seen_b, len(other)))

    # show that "4. Primary." is one line, and the indented lines after it are unchanged
    k = next(i for i, l in enumerate(a) if l.startswith("4. Primary."))
    j = k + 1
    while j < len(a) and a[j].strip() != "":
        j += 1
    kb = next(i for i, l in enumerate(b) if l.startswith("4. Primary."))
    pr("v9l: '4. Primary.' is line %d (v9m line %d); the %d non-blank lines after it (v9l %d-%d) start with %r; "
       "they are identical in v9m: %s"
       % (k + 1, kb + 1, j - k - 1, k + 2, j, a[k + 1][:40], a[k + 1:j] == b[kb + 1:kb + 1 + (j - k - 1)]))

    pr("")
    pr("== problems ==")
    if problems:
        for p_ in problems:
            pr(" - " + p_)
    else:
        pr(" none")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
