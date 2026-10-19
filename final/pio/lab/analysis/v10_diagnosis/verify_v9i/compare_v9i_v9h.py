"""Compare prompt folder two_phase_v9i with two_phase_v9h, file by file.

Self-contained: reads the .md files only. No imports from the lab code, no API calls.

Method
- Every file: byte comparison, byte size, line count, word count (words = whitespace-
  separated tokens, len(text.split())).
- phase1.md / phase2.md: split each file into "segments". A segment is either a rule
  block (a line starting "- " at column 0 plus the following lines that start with two
  spaces) or a single non-block line. Segments are diffed by key (block title or line
  text) with difflib; blocks whose key matches on both sides are then compared line by
  line. Each difference is classified against the expected change list; anything that
  does not fit is reported as UNEXPECTED.
- OUTPUT sections: text from the line "OUTPUT" to end of file, compared for equality.

Self-test: the segment parser is checked against block boundaries read by hand from
v9h (sed output in the session) before any result is printed.
"""
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab\prompts")
OLD = ROOT / "two_phase_v9h"
NEW = ROOT / "two_phase_v9i"
FILES = ["README.md", "common.md", "phase1.md", "phase1_user.md", "phase2.md", "phase2_user.md"]

EXPECTED_INSERT_PREFIXES = [
    "- Stored-word arrays.",
    "control-unit",            # title containing this
    "- Forwarded-access stages.",
    "- Transfer records.",
    "- Response merges",
]
NEW_EXC_PHRASE = "judged as usual, as information crossing the unit's boundary"


def read(path: Path):
    data = path.read_bytes()
    text = data.decode("utf-8")
    return data, text


def segments(lines):
    """Return list of (kind, key, start_line_1based, [lines])."""
    segs = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("- "):
            start = i
            block = [line]
            i += 1
            while i < n and lines[i].startswith("  ") and lines[i].strip() != "":
                block.append(lines[i])
                i += 1
            segs.append(("block", block_key(line), start + 1, block))
        else:
            segs.append(("line", "L:" + line, i + 1, [line]))
            i += 1
    return segs


def block_key(first_line):
    body = first_line[2:]
    if body.startswith("Scope:"):
        return "B:" + body[:80]      # headerless block: use its start as key
    m = re.match(r"([^.]*\.)", body)  # title up to the first period
    return "B:" + (m.group(1) if m else body[:80])


def self_test():
    """Hand-read facts from the session (sed/grep output on v9h):
    phase1.md: '- Count increment inputs.' at line 38, block ends line 43 (44 starts
      '- Forwarded transactions.'); '- Link handshake ports.' at 70, ends 75 (76 starts
      '- Sequencing state.'); 'OUTPUT' at 155; '- Control record ports.' at 149.
    phase2.md: '- Count increment inputs.' at 65, ends 69 (line 70 is a column-0 prose
      line 'A register only recording that a count has started...', 71 starts '- Scope:');
      '- Boundary outputs.' at 120; '5. Secondary.' line at 126; 'OUTPUT' at 133.
    """
    _, p1 = read(OLD / "phase1.md")
    _, p2 = read(OLD / "phase2.md")
    s1 = {k: (st, st + len(b) - 1) for _, k, st, b in segments(p1.splitlines())}
    s2 = {k: (st, st + len(b) - 1) for _, k, st, b in segments(p2.splitlines())}
    checks = [
        (s1.get("B:Count increment inputs."), (38, 43)),
        (s1.get("B:Link handshake ports."), (70, 75)),
        (s1.get("B:Control record ports.")[0], 149),
        (s1.get("L:OUTPUT")[0], 155),
        (s2.get("B:Count increment inputs."), (65, 69)),
        (s2.get("L:" + p2.splitlines()[69])[0] if ("L:" + p2.splitlines()[69]) in s2 else None, 70),
        (s2.get("B:Boundary outputs.")[0], 120),
        (s2.get("L:OUTPUT")[0], 133),
    ]
    sec = [st for _, k, st, _ in segments(p2.splitlines()) if k.startswith("L:5. Secondary.")]
    checks.append((sec[0] if sec else None, 126))
    # synthetic: a block followed by a blank line and a numbered line
    syn = segments(["- A. x", "  Scope: y", "", "5. Z", "- Scope: q", "  Criteria: r"])
    checks.append(([s[0] for s in syn], ["block", "line", "line", "block"]))
    checks.append((len(syn[0][3]), 2))
    bad = [(got, want) for got, want in checks if got != want]
    return bad


def classify_phase(name):
    old_b, old_t = read(OLD / name)
    new_b, new_t = read(NEW / name)
    ol, nl = old_t.splitlines(), new_t.splitlines()
    os_, ns_ = segments(ol), segments(nl)
    ok, nk = [s[1] for s in os_], [s[1] for s in ns_]
    sm = difflib.SequenceMatcher(a=ok, b=nk, autojunk=False)

    report = {"file": name, "deleted": [], "inserted": [], "modified": [], "unexpected": []}

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for a, b in zip(os_[i1:i2], ns_[j1:j2]):
                if a[3] != b[3]:
                    report["modified"].append(describe_modified(a, b))
        elif tag == "delete":
            for a in os_[i1:i2]:
                report["deleted"].append({"key": a[1], "old_line": a[2], "n_lines": len(a[3]),
                                          "first_line": a[3][0][:100]})
        elif tag == "insert":
            for idx in range(j1, j2):
                b = ns_[idx]
                prev_seg = ns_[idx - 1] if idx > 0 else None
                # the nearest preceding block (skipping blank/other lines) and next segment
                k = idx - 1
                while k >= 0 and ns_[k][0] != "block":
                    k -= 1
                prev_block = ns_[k] if k >= 0 else None
                nxt = ns_[j2] if j2 < len(ns_) else None
                report["inserted"].append({
                    "key": b[1], "new_line": b[2], "n_lines": len(b[3]),
                    "first_line": b[3][0][:120],
                    "words": sum(len(x.split()) for x in b[3]),
                    "immediately_before": (prev_seg[1], prev_seg[2]) if prev_seg else None,
                    "preceding_block": (prev_block[1], prev_block[2]) if prev_block else None,
                    "next_segment_after_run": (nxt[1], nxt[2]) if nxt else None,
                })
        else:  # replace: a mix the key-diff could not separate
            report["unexpected"].append({
                "tag": "replace",
                "old": [(a[1], a[2]) for a in os_[i1:i2]],
                "new": [(b[1], b[2]) for b in ns_[j1:j2]],
            })

    # --- classify against expectations ---
    exp_del = [d for d in report["deleted"] if d["key"] == "B:Count increment inputs."]
    other_del = [d for d in report["deleted"] if d["key"] != "B:Count increment inputs."]
    if len(exp_del) != 1:
        report["unexpected"].append({"tag": "count-increment-deletion-count", "n": len(exp_del)})
    for d in other_del:
        report["unexpected"].append({"tag": "unexpected-deletion", **d})

    exp_mod, other_mod = [], []
    for m in report["modified"]:
        if m["key"] == "B:Link handshake ports." and m["changed_lines"] == 1 \
                and m["diffs"][0]["old"].lstrip().startswith("Exceptions:") \
                and NEW_EXC_PHRASE in m["diffs"][0]["added_text"] \
                and "Forwarded transactions" in m["diffs"][0]["removed_text"] \
                and "Port buffers" in m["diffs"][0]["removed_text"] \
                and m["diffs"][0]["old"].replace(m["diffs"][0]["removed_text"], m["diffs"][0]["added_text"], 1) == m["diffs"][0]["new"]:
            exp_mod.append(m)
        else:
            other_mod.append(m)
    if len(exp_mod) != 1:
        report["unexpected"].append({"tag": "link-handshake-modification-count", "n": len(exp_mod)})
    for m in other_mod:
        report["unexpected"].append({"tag": "unexpected-modification", **m})

    def matches_expected(first_line):
        for p in EXPECTED_INSERT_PREFIXES:
            if p == "control-unit":
                title = first_line.split(".")[0]
                if "control-unit" in title:
                    return p
            elif first_line.startswith(p):
                return p
        return None

    matched = {}
    for ins in report["inserted"]:
        p = matches_expected(ins["first_line"]) if ins["key"].startswith("B:") else None
        ins["expected_as"] = p
        if p is None:
            report["unexpected"].append({"tag": "unexpected-insertion", **ins})
        else:
            matched.setdefault(p, []).append(ins)
    for p in EXPECTED_INSERT_PREFIXES:
        if len(matched.get(p, [])) != 1:
            report["unexpected"].append({"tag": "expected-insert-count", "prefix": p,
                                         "n": len(matched.get(p, []))})

    # placement check (phase2: after Boundary outputs block, before "5. Secondary.")
    if name == "phase2.md":
        bo = [s for s in ns_ if s[1] == "B:Boundary outputs."]
        sec = [s for s in ns_ if s[1].startswith("L:5. Secondary.")]
        bo_end = bo[0][2] + len(bo[0][3]) - 1 if bo else None
        sec_line = sec[0][2] if sec else None
        report["placement"] = {"boundary_outputs_block": (bo[0][2], bo_end) if bo else None,
                               "secondary_line": sec_line}
        for ins in report["inserted"]:
            if ins.get("expected_as"):
                inside = bo_end is not None and sec_line is not None and bo_end < ins["new_line"] < sec_line
                ins["between_boundary_outputs_and_secondary"] = inside
                if not inside:
                    report["unexpected"].append({"tag": "placement", **ins})
    else:
        # phase1: report what the last pre-existing block is and whether inserts follow it
        old_block_keys = {s[1] for s in os_ if s[0] == "block"}
        last_old_block = [s for s in ns_ if s[0] == "block" and s[1] in old_block_keys][-1]
        out_line = [s for s in ns_ if s[1] == "L:OUTPUT"][0][2]
        report["placement"] = {"last_pre_existing_block": (last_old_block[1], last_old_block[2]),
                               "OUTPUT_line": out_line}
        for ins in report["inserted"]:
            if ins.get("expected_as"):
                prev = ins["immediately_before"]
                after_existing = prev is not None and prev[0] in old_block_keys
                before_output = ins["new_line"] < out_line
                ins["immediately_after_a_pre_existing_block"] = after_existing
                ins["before_OUTPUT"] = before_output
                if not (after_existing and before_output):
                    report["unexpected"].append({"tag": "placement", **ins})

    # cross-references inside inserted blocks to rule titles that do not exist in this phase
    titles_here = {s[1][2:-1] for s in ns_ if s[0] == "block" and not s[1].startswith("B:Scope:")}
    other = "phase2.md" if name == "phase1.md" else "phase1.md"
    _, other_t = read(NEW / other)
    titles_other = {s[1][2:-1] for s in segments(other_t.splitlines()) if s[0] == "block" and not s[1].startswith("B:Scope:")}
    all_titles = titles_here | titles_other | {"Count increment inputs"}
    dangling = []
    for ins in report["inserted"]:
        seg = [s for s in ns_ if s[2] == ins["new_line"]][0]
        body = " ".join(seg[3])
        refs = sorted(t for t in all_titles if t in body and t != ins["key"][2:-1])
        ins["rule_refs"] = refs
        missing = [t for t in refs if t not in titles_here]
        if missing:
            dangling.append((ins["key"], missing))
    report["dangling_refs"] = dangling

    # OUTPUT sections
    def output_section(lines):
        idx = lines.index("OUTPUT")
        return lines[idx:]
    report["output_identical"] = output_section(ol) == output_section(nl)
    report["output_lines"] = (len(output_section(ol)), len(output_section(nl)))

    # mentions that should move with the change
    for term in ["Count increment inputs", "Forwarded transactions", "Port buffers"]:
        report.setdefault("mentions", {})[term] = (old_t.count(term), new_t.count(term))

    # cheap check of the inserted text for numeric emission hints (project constraint)
    hint_re = re.compile(r"\b(at most|at least|no more than|up to) (\d+|half|a third)\b|%", re.I)
    hits = []
    for ins in report["inserted"]:
        seg = [s for s in ns_ if s[2] == ins["new_line"]][0]
        for off, line in enumerate(seg[3]):
            for m in hint_re.finditer(line):
                hits.append((ins["new_line"] + off, m.group(0)))
    report["numeric_hints_in_inserted"] = hits

    # column-0 prose lines that are neither block starts, steps, headings, OUTPUT nor JSON
    orphan_re = re.compile(r'^(- |  |[0-9]+\. |#|OUTPUT$|\{|\}|"| |\]|\[|$)')
    report["orphan_prose_old"] = [(i + 1, l[:90]) for i, l in enumerate(ol) if not orphan_re.match(l)]
    report["orphan_prose_new"] = [(i + 1, l[:90]) for i, l in enumerate(nl) if not orphan_re.match(l)]
    # full text dumps for the reader
    dump = Path(__file__).with_name(f"dump_{name.replace('.md','')}.txt")
    NL = "\n"
    with dump.open("w", encoding="utf-8") as fh:
        for d in report["deleted"]:
            seg = [s for s in os_ if s[2] == d["old_line"]][0]
            fh.write(f"### DELETED (v9h line {d['old_line']}):" + NL + NL.join(seg[3]) + NL + NL)
        for m in report["modified"]:
            for d in m["diffs"]:
                fh.write(f"### MODIFIED line v9h {d['old_line']} / v9i {d['new_line']}:" + NL
                         + "OLD: " + d["old"] + NL + "NEW: " + d["new"] + NL + NL)
        for i in report["inserted"]:
            seg = [s for s in ns_ if s[2] == i["new_line"]][0]
            fh.write(f"### INSERTED (v9i line {i['new_line']}):" + NL + NL.join(seg[3]) + NL + NL)
    report["dump"] = str(dump)
    return report


def describe_modified(a, b):
    diffs = []
    for off, (x, y) in enumerate(zip(a[3], b[3])):
        if x != y:
            sm = difflib.SequenceMatcher(a=x, b=y, autojunk=False)
            removed, added = [], []
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag in ("delete", "replace"):
                    removed.append(x[i1:i2])
                if tag in ("insert", "replace"):
                    added.append(y[j1:j2])
            # widen to the sentence containing the change
            i1 = min(op[1] for op in sm.get_opcodes() if op[0] != "equal")
            i2 = max(op[2] for op in sm.get_opcodes() if op[0] != "equal")
            j1 = min(op[3] for op in sm.get_opcodes() if op[0] != "equal")
            j2 = max(op[4] for op in sm.get_opcodes() if op[0] != "equal")
            diffs.append({
                "old_line": a[2] + off, "new_line": b[2] + off,
                "old": x, "new": y,
                "removed_text": x[i1:i2], "added_text": y[j1:j2],
                "old_sentence": sentence_around(x, i1, i2),
                "new_sentence": sentence_around(y, j1, j2),
            })
    extra = len(a[3]) - len(b[3])
    return {"key": a[1], "old_line": a[2], "new_line": b[2],
            "changed_lines": len(diffs) + abs(extra), "line_count_delta": -extra, "diffs": diffs}


def sentence_around(s, i1, i2):
    start = s.rfind(". ", 0, i1)
    start = 0 if start < 0 else start + 2
    end = s.find(". ", i2)
    end = len(s) if end < 0 else end + 1
    return s[start:end]


def main():
    bad = self_test()
    if bad:
        print("SELF-TEST FAILED:", bad)
        sys.exit(1)
    print("SELF-TEST PASS (parser matches hand-read block boundaries in v9h)")
    print()

    print("== Per-file: bytes / lines / words (words = whitespace-separated tokens) ==")
    for f in FILES:
        ob, ot = read(OLD / f)
        nb, nt = read(NEW / f)
        ident = ob == nb
        print(f"{f:16s} v9h: {len(ob):6d} B {len(ot.splitlines()):4d} lines {len(ot.split()):6d} words | "
              f"v9i: {len(nb):6d} B {len(nt.splitlines()):4d} lines {len(nt.split()):6d} words | "
              f"byte-identical: {ident} | CRLF old/new: {b'\\r\\n' in ob}/{b'\\r\\n' in nb}")
    print()

    # README diff (not in the expected list, so shown in full)
    _, ot = read(OLD / "README.md")
    _, nt = read(NEW / "README.md")
    if ot != nt:
        print("== README.md differs; unified diff ==")
        for line in difflib.unified_diff(ot.splitlines(), nt.splitlines(), "v9h/README.md", "v9i/README.md", lineterm=""):
            print(line)
        print()

    for name in ["phase1.md", "phase2.md"]:
        r = classify_phase(name)
        print(f"==================== {name} ====================")
        print("Deleted segments:")
        for d in r["deleted"]:
            print(f"  {d['key']}  (v9h line {d['old_line']}, {d['n_lines']} lines)")
        print("Modified blocks (same key, different text):")
        for m in r["modified"]:
            print(f"  {m['key']}  v9h line {m['old_line']} -> v9i line {m['new_line']}; changed lines: {m['changed_lines']}")
            for d in m["diffs"]:
                print(f"    line v9h {d['old_line']} / v9i {d['new_line']} (starts '{d['old'].strip()[:12]}...')")
                print(f"    OLD sentence: {d['old_sentence']}")
                print(f"    NEW sentence: {d['new_sentence']}")
                print(f"    removed text: {d['removed_text']!r}")
                print(f"    added text:   {d['added_text']!r}")
        print("Inserted segments:")
        for i in r["inserted"]:
            print(f"  {i['key']}  v9i line {i['new_line']}, {i['n_lines']} lines, {i['words']} words; expected_as={i['expected_as']}")
            print(f"    first line: {i['first_line']}")
            print(f"    immediately before it: {i['immediately_before']}")
            print(f"    preceding block:       {i['preceding_block']}")
            print(f"    next segment after insert run: {i['next_segment_after_run']}")
            for k in ("between_boundary_outputs_and_secondary", "immediately_after_a_pre_existing_block", "before_OUTPUT", "rule_refs"):
                if k in i:
                    print(f"    {k}: {i[k]}")
        print("Placement anchors:", r["placement"])
        print("Inserted blocks naming a rule absent from this phase:", r["dangling_refs"])
        ob, ot = read(OLD / name); nb, nt = read(NEW / name)
        print(f"Word delta v9i-v9h: {len(nt.split()) - len(ot.split()):+d} words; line delta: {len(nt.splitlines()) - len(ot.splitlines()):+d}; "
              f"inserted words total: {sum(i['words'] for i in r['inserted'])}")
        print("OUTPUT section identical:", r["output_identical"], "lines (old,new):", r["output_lines"])
        print("Mentions (old,new):", r["mentions"])
        print("Numeric emission hints in inserted text:", r["numeric_hints_in_inserted"])
        print("Column-0 prose lines outside blocks, v9h:", r["orphan_prose_old"])
        print("Column-0 prose lines outside blocks, v9i:", r["orphan_prose_new"])
        print("Full text dump:", r["dump"])
        print("UNEXPECTED differences:", len(r["unexpected"]))
        for u in r["unexpected"]:
            print("  ", u)
        print()


if __name__ == "__main__":
    main()
