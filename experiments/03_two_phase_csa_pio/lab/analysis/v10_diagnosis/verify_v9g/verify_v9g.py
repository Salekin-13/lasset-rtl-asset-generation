"""Independent re-derivation: two_phase_v9g vs two_phase_v9f, file by file.

Method 1 (line level): difflib.SequenceMatcher over the line lists, autojunk off.
Method 2 (block level): parse each file into blocks (a block = one line with no
leading space plus the indented lines after it); compare block sequences.
Both methods must agree on the same set of changes or the run is reported as failed.
Sentence level: changed lines are split into sentences and diffed as sentence lists.
Nothing here imports or calls any other lab script.
"""
import difflib, re, sys, json
from pathlib import Path

PROMPTS = Path(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab\prompts")
OLD, NEW = PROMPTS / "two_phase_v9f", PROMPTS / "two_phase_v9g"
FILES = ["common.md", "phase1.md", "phase2.md", "phase1_user.md", "phase2_user.md"]
EXPECTED_INSERTS = ("- Control record ports.", "- Access command ports.",
                    "- Entry selects and register addresses.", "- Boundary outputs.",
                    "- Coprocessor progress state.")
PB_HEAD = {"phase1.md": "- Port buffers (a).",
           "phase2.md": "- Scope: a FIFO instance's push and pop strobes"}
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def read(p): return p.read_text(encoding="utf-8")
def lines(t): return t.split("\n")
def wc_ws(t): return len(t.split())
def wc_re(t): return len(WORD_RE.findall(t))
def sentences(s): return [x for x in SENT_RE.split(s.strip()) if x]


def blocks(ls):
    """[(start_index, [lines])]; a block starts at a non-indented, non-empty line."""
    out = []
    for i, l in enumerate(ls):
        if l == "":
            out.append((i, [l]))
        elif l[0] in " \t" and out and out[-1][1][0] != "":
            out[-1][1].append(l)
        else:
            out.append((i, [l]))
    return out


def output_section(ls):
    idx = [i for i, l in enumerate(ls) if l == "OUTPUT"]
    return idx, ("\n".join(ls[idx[0]:]) if len(idx) == 1 else None)


# ---------------- self-test against hand-read facts ----------------
def self_test():
    assert sentences("A b. C d (x). Never in scope: e. 2.6: f.") == \
        ["A b.", "C d (x).", "Never in scope: e. 2.6: f."]
    p1 = lines(read(OLD / "phase1.md")); p2 = lines(read(OLD / "phase2.md"))
    g1 = lines(read(NEW / "phase1.md")); g2 = lines(read(NEW / "phase2.md"))
    # hand-read on 2026-10-18 from sed/grep output (1-based there, 0-based here)
    assert p1[41].startswith("- Port buffers (a)."), p1[41][:40]
    assert p1[42].startswith("  Scope: a FIFO instance's push and pop strobes")
    assert p1[44].startswith("  Exceptions: judged as usual")
    assert p1[47].startswith("- Port buffers (b).")
    assert p2[46].startswith("- Scope: a FIFO instance's push and pop strobes")
    assert p2[48].startswith("  Exceptions: judged as usual")
    assert output_section(p1)[0] == [107] and output_section(g1)[0] == [130]
    assert output_section(p2)[0] == [88] and output_section(g2)[0] == [112]
    b = blocks(p1); pb = [x for x in b if x[1][0].startswith("- Port buffers (a).")]
    assert len(pb) == 1 and pb[0][0] == 41 and len(pb[0][1]) == 6
    return "self-test PASS (sentence splitter, block parser, hand-read line numbers)"


# ---------------- method 1: line-level ----------------
def line_level(name, a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    res = {"inserts": [], "replaces": [], "deletes": [], "unexpected": []}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            ins = b[j1:j2]
            for st, bl in blocks(ins):
                head = bl[0]
                ok_head = any(head.startswith(p) for p in EXPECTED_INSERTS)
                ok_body = all(l.startswith("  ") for l in bl[1:])
                at_boundary = (i1 >= len(a)) or (a[i1][:1] not in (" ", "\t"))
                rec = {"new_lines": f"{j1+st+1}-{j1+st+len(bl)}", "head": head[:60],
                       "n_lines": len(bl), "words": wc_ws("\n".join(bl))}
                res["inserts"].append(rec)
                if not (ok_head and ok_body and at_boundary):
                    res["unexpected"].append({"kind": "insert", **rec,
                        "why": f"head ok={ok_head}, body indented={ok_body}, at block boundary={at_boundary}"})
        elif tag == "delete":
            for k in range(i1, i2):
                res["deletes"].append({"old_line": k+1, "text": a[k][:80]})
                res["unexpected"].append({"kind": "delete", "old_line": k+1, "text": a[k][:80]})
        else:  # replace
            if (i2 - i1) != (j2 - j1):
                res["unexpected"].append({"kind": "replace-unequal", "old": f"{i1+1}-{i2}", "new": f"{j1+1}-{j2}"})
            for k in range(max(i2 - i1, j2 - j1)):
                o = a[i1+k] if i1+k < i2 else None
                n = b[j1+k] if j1+k < j2 else None
                rec = sentence_diff(name, a, i1+k, o, j1+k, n)
                res["replaces"].append(rec)
                if not rec["expected"]:
                    res["unexpected"].append({"kind": "replace", "old_line": i1+k+1, "new_line": j1+k+1,
                                              "field": rec["field"], "block_head": rec["block_head"]})
    return res


def enclosing_block(ls, idx):
    for st, bl in blocks(ls):
        if st <= idx < st + len(bl):
            return st, bl
    return None, None


def sentence_diff(name, a, i, o, j, n):
    so, sn = sentences(o or ""), sentences(n or "")
    sm = difflib.SequenceMatcher(None, so, sn, autojunk=False)
    removed, added = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("delete", "replace"): removed += so[i1:i2]
        if tag in ("insert", "replace"): added += sn[j1:j2]
    st, bl = enclosing_block(a, i)
    in_pb = bl is not None and bl[0].startswith(PB_HEAD[name])
    label = (o or "").strip().split(":")[0].lstrip("- ")
    rec = {"old_line": i+1, "new_line": j+1, "field": label,
           "block_head": (bl[0][:50] if bl else None), "in_port_buffers_a_block": in_pb,
           "sentences_old": len(so), "sentences_new": len(sn),
           "sentences_removed": removed, "sentences_added": added,
           "new_extends_old": (o is not None and n is not None and n.startswith(o) and n != o),
           "new_truncates_old": (o is not None and n is not None and o.startswith(n) and n != o)}
    expected = in_pb and ((label == "Scope" and rec["new_extends_old"] and not removed) or
                          (label == "Exceptions" and rec["new_truncates_old"] and not added))
    rec["expected"] = expected
    return rec


# ---------------- method 2: block-level ----------------
def block_level(name, a, b):
    ba, bb = blocks(a), blocks(b)
    ta, tb = ["\n".join(x[1]) for x in ba], ["\n".join(x[1]) for x in bb]
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    added, removed, replaced = [], [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert": added += [bb[k] for k in range(j1, j2)]
        elif tag == "delete": removed += [ba[k] for k in range(i1, i2)]
        elif tag == "replace": replaced.append(([ba[k] for k in range(i1, i2)], [bb[k] for k in range(j1, j2)]))
    out = []
    for o, n in replaced:
        rec = {"old_head": o[0][1][0][:50], "n_old": len(o), "n_new": len(n), "changed_old_lines": None}
        if len(o) == 1 and len(n) == 1 and len(o[0][1]) == len(n[0][1]):
            rec["changed_old_lines"] = [o[0][0] + k + 1 for k, (x, y) in enumerate(zip(o[0][1], n[0][1])) if x != y]
        out.append(rec)
    return {"blocks_old": len(ba), "blocks_new": len(bb),
            "added_heads": [x[1][0][:60] for x in added],
            "removed_heads": [x[1][0][:60] for x in removed],
            "replaced": out}


# ---------------- moved-sentence check for Port buffers ----------------
def move_check(name, a, b):
    """Compare the text dropped from Exceptions with the text added to Scope."""
    ba = [x for x in blocks(a) if x[1][0].startswith(PB_HEAD[name])]
    bb = [x for x in blocks(b) if x[1][0].startswith(PB_HEAD[name])]
    assert len(ba) == 1 and len(bb) == 1
    oa, ob = ba[0][1], bb[0][1]
    assert len(oa) == len(ob)
    sc = [k for k, l in enumerate(oa) if l.lstrip("- ").startswith("Scope:")][0]
    ex = [k for k, l in enumerate(oa) if l.lstrip().startswith("Exceptions:")][0]
    added = ob[sc][len(oa[sc]):].strip() if ob[sc].startswith(oa[sc]) else None
    dropped = oa[ex][len(ob[ex]):].strip() if oa[ex].startswith(ob[ex]) else None
    other_changed = [k+1 for k in range(len(oa)) if k not in (sc, ex) and oa[k] != ob[k]]
    wa, wd = WORD_RE.findall(added or ""), WORD_RE.findall(dropped or "")
    wsm = difflib.SequenceMatcher(None, wd, wa, autojunk=False)
    wdiff = [(t, " ".join(wd[i1:i2]), " ".join(wa[j1:j2])) for t, i1, i2, j1, j2 in wsm.get_opcodes() if t != "equal"]
    return {"block_lines_old": f"{ba[0][0]+1}-{ba[0][0]+len(oa)}", "block_lines_new": f"{bb[0][0]+1}-{bb[0][0]+len(ob)}",
            "scope_added_text": added, "exceptions_dropped_text": dropped,
            "other_lines_changed_in_block": other_changed,
            "words_dropped": len(wd), "words_added": len(wa),
            "word_level_edits_dropped_to_added": wdiff,
            "pure_move": (added == dropped)}


# ---------------- main ----------------
def main():
    print(self_test())
    report = {}
    for f in FILES:
        ta, tb = read(OLD / f), read(NEW / f)
        la, lb = lines(ta), lines(tb)
        rec = {"byte_identical": (OLD / f).read_bytes() == (NEW / f).read_bytes(),
               "bytes": [len((OLD / f).read_bytes()), len((NEW / f).read_bytes())],
               "lines": [len(la), len(lb)],
               "words_whitespace": [wc_ws(ta), wc_ws(tb)],
               "words_regex": [wc_re(ta), wc_re(tb)],
               "crlf_present": ["\r" in ta, "\r" in tb]}
        if f in ("phase1.md", "phase2.md"):
            rec["line_level"] = line_level(f, la, lb)
            rec["block_level"] = block_level(f, la, lb)
            rec["port_buffers_move"] = move_check(f, la, lb)
            ia, oa = output_section(la); ib, ob = output_section(lb)
            rec["output_section"] = {"OUTPUT_line_old": [i+1 for i in ia], "OUTPUT_line_new": [i+1 for i in ib],
                                     "identical": (oa is not None and oa == ob),
                                     "lines": [len(lines(oa)) if oa else None, len(lines(ob)) if ob else None],
                                     "words_whitespace": [wc_ws(oa or ""), wc_ws(ob or "")]}
            rec["body_before_OUTPUT_words"] = [wc_ws("\n".join(la[:ia[0]])), wc_ws("\n".join(lb[:ib[0]]))]
            # cross-check method 1 vs method 2
            m1_ins = sorted(x["head"] for x in rec["line_level"]["inserts"])
            m2_ins = sorted(rec["block_level"]["added_heads"])
            m1_rep_old = sorted(x["old_line"] for x in rec["line_level"]["replaces"])
            m2_rep_old = sorted(k for r in rec["block_level"]["replaced"] for k in (r["changed_old_lines"] or []))
            rec["methods_agree"] = (m1_ins == m2_ins and m1_rep_old == m2_rep_old
                                    and not rec["block_level"]["removed_heads"] and not rec["line_level"]["deletes"])
            ins_words = sum(x["words"] for x in rec["line_level"]["inserts"])
            mv = rec["port_buffers_move"]
            pb_delta = wc_ws(mv["scope_added_text"] or "") - wc_ws(mv["exceptions_dropped_text"] or "")
            rec["word_delta_accounting"] = {
                "file_delta": rec["words_whitespace"][1] - rec["words_whitespace"][0],
                "inserted_block_words": ins_words,
                "port_buffers_delta": pb_delta,
                "sum": ins_words + pb_delta}
        report[f] = rec
    out = Path(__file__).with_name("verify_v9g_report.json")
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    # ---- human summary ----
    print("\n== per-file ==")
    for f, r in report.items():
        print(f"{f:16s} identical={r['byte_identical']!s:5s} bytes={r['bytes']} lines={r['lines']} "
              f"words(ws)={r['words_whitespace']} words(re)={r['words_regex']} crlf={r['crlf_present']}")
    for f in ("phase1.md", "phase2.md"):
        r = report[f]
        print(f"\n== {f} ==")
        print("inserted blocks (new line range, head, lines, words):")
        for x in r["line_level"]["inserts"]:
            print(f"  {x['new_lines']:9s} {x['head']:45s} {x['n_lines']:2d} {x['words']:4d}")
        print("deleted lines:", r["line_level"]["deletes"])
        print("changed lines (sentence level):")
        for x in r["line_level"]["replaces"]:
            print(f"  old {x['old_line']} -> new {x['new_line']} field={x['field']} block={x['block_head']!r} "
                  f"in_PB_block={x['in_port_buffers_a_block']} sent {x['sentences_old']}->{x['sentences_new']} "
                  f"extends={x['new_extends_old']} truncates={x['new_truncates_old']} expected={x['expected']}")
            for s in x["sentences_removed"]: print("     - ", s)
            for s in x["sentences_added"]:   print("     + ", s)
        mv = r["port_buffers_move"]
        print("Port buffers move check: block old", mv["block_lines_old"], "new", mv["block_lines_new"],
              "| other lines changed in block:", mv["other_lines_changed_in_block"], "| pure move:", mv["pure_move"])
        print("  dropped from Exceptions:", mv["exceptions_dropped_text"])
        print("  added to Scope         :", mv["scope_added_text"])
        print("  words dropped/added:", mv["words_dropped"], mv["words_added"])
        print("  word-level edits dropped->added:", mv["word_level_edits_dropped_to_added"])
        print("block level: blocks", r["block_level"]["blocks_old"], "->", r["block_level"]["blocks_new"],
              "| added:", r["block_level"]["added_heads"], "| removed:", r["block_level"]["removed_heads"],
              "| replaced:", r["block_level"]["replaced"])
        print("methods agree:", r["methods_agree"])
        print("OUTPUT section:", r["output_section"])
        print("body words before OUTPUT:", r["body_before_OUTPUT_words"], "| word delta accounting:", r["word_delta_accounting"])
        print("UNEXPECTED:", r["line_level"]["unexpected"] or "none")
    print("\nreport:", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
