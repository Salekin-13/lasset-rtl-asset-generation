"""Independent check of the three Tier 1 prompt folders against two_phase_v9n_place (PLAN_P1_ORDER.md Tier 1).

Nothing here imports chain, make_p1_order or any lab script; it only reads the files. No API call.
Expected (stated by the task, verified here, not assumed):
  common.md, phase1_user.md, phase2.md, phase2_user.md   byte-identical to the base;
  phase1.md   every base line kept in order plus ONE contiguous inserted block, five lines long:
              first  "- Debug module registers." right after the "- Reading a rule." block,
              last   same block right after the last rule block, before the blank line that precedes "OUTPUT",
              sham   "- Reading note." right after the "- Processor control-unit state." block.
Everything else that differs is reported. The sham block is screened for instruction-like sentences.

Self-test: facts hand-read from the base file in this session (cat -n / diff output) must match what the code finds,
or the run reports nothing.
  python -B verify_prompts.py
"""
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

LAB = Path(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab")
PROMPTS = LAB / "prompts"
BASE = "two_phase_v9n_place"
DBG = "two_phase_v9n_place_dbg"
ARMS = {
    "two_phase_p1o_first": {"first_line": "- Debug module registers.", "where": "after_block", "block": "- Reading a rule."},
    "two_phase_p1o_last": {"first_line": "- Debug module registers.", "where": "before_output"},
    "two_phase_p1o_sham": {"first_line": "- Reading note.", "where": "after_block", "block": "- Processor control-unit state."},
}
FILES = ["README.md", "common.md", "phase1.md", "phase1_user.md", "phase2.md", "phase2_user.md"]
EXPECT_IDENTICAL = ["common.md", "phase1_user.md", "phase2.md", "phase2_user.md"]
EXPECTED_BLOCK_LINES = 5
TITLE_RE = re.compile(r"^- [A-Z].*?\.(\s|$)")  # column-zero "- Title." line

# ---- hand-read facts (this session, cat -n and diff on the base and arm files) ----
HAND_READ = {
    "base_line_count": 212,           # wc -l
    "base_line_1": "THIS CALL: PHASE 1, CONCEPTUAL ASSETS",
    "base_line_24_prefix": "- Reading a rule.",
    "base_line_163_prefix": "- Processor control-unit state.",
    "base_line_168_prefix": "- Transfer records.",
    "base_line_172": "",
    "base_line_173": "OUTPUT",
    "base_title_count": 46,
    "base_first_title_line": 22,
    "base_last_title_line": 168,
    # diff(1) output: "24a25,29", "171a172,176", "167a168,169"
    "diff_insert": {"two_phase_p1o_first": (25, 29), "two_phase_p1o_last": (172, 176), "two_phase_p1o_sham": (168, 169)},
}


def sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


def endings(b):
    crlf = b.count(b"\r\n")
    lf_only = b.count(b"\n") - crlf
    cr_only = b.count(b"\r") - crlf
    return {"crlf": crlf, "bare_lf": lf_only, "bare_cr": cr_only, "bom": b.startswith(b"\xef\xbb\xbf"),
            "ends_with_newline": b.endswith(b"\n")}


def lines_of(b):
    t = b.decode("utf-8").replace("\r\n", "\n")
    if t.endswith("\n"):
        t = t[:-1]
    return t.split("\n")


def blocks(lines):
    """Rule blocks of the base: a column-zero '- Title.' line and the lines after it up to the next title, a blank line or OUTPUT.
    Returns a list of (title_line_1based, end_line_1based, title_text)."""
    out = []
    idx = [i for i, l in enumerate(lines) if TITLE_RE.match(l)]
    for i in idx:
        j = i + 1
        while j < len(lines) and lines[j].strip() != "" and lines[j] != "OUTPUT" and not TITLE_RE.match(lines[j]):
            j += 1
        out.append((i + 1, j, lines[i]))  # 1-based title line, 1-based last line
    return out


def align(base, arm):
    """('ok', start_1based, inserted_lines) when arm == base with exactly one contiguous block inserted; else ('bad', detail)."""
    sm = difflib.SequenceMatcher(a=base, b=arm, autojunk=False)
    ops = [op for op in sm.get_opcodes() if op[0] != "equal"]
    if len(ops) != 1 or ops[0][0] != "insert":
        return ("bad", [(op[0], op[1] + 1, op[2], op[3] + 1, op[4]) for op in ops])
    _, i1, i2, j1, j2 = ops[0]
    # second, independent check: a two-pointer walk keeps every base line in order
    p = 0
    extra = []
    for k, l in enumerate(arm):
        if p < len(base) and l == base[p]:
            p += 1
        else:
            extra.append(k)
    if p != len(base):
        return ("bad", f"two-pointer walk lost base line {p + 1}")
    if extra != list(range(j1, j2)):
        return ("bad", f"two-pointer extra lines {extra[:3]}.. differ from difflib insert {j1 + 1}-{j2}")
    return ("ok", j1 + 1, arm[j1:j2])


# ---- instruction-like screen for the sham ----
MODALS = re.compile(r"\b(must|should|shall|never|always|do not|don.t|cannot|may not|only|"
                    r"no [a-z]+ (is|are) (kept|cited|named)|is not a (conceptual asset|piece)|not a piece of its own|"
                    r"keep no|cite no|name it in no|judged as usual|as (a )?held lines?)\b", re.I)
IMPERATIVE_START = re.compile(r"^(Check|Cite|Keep|Name|List|Copy|Return|Describe|Assume|Answer|Judge|Treat|Use|Count|Read|"
                              r"Place|Put|Write|Mark|Do|Spell|Match|Report|Give|Include|Omit|Skip|Ignore|Apply|Follow)\b")
PASSIVE_DIRECTIVE = re.compile(r"\b(so|and|then)\s+[a-z ]*?\b(are|is)\s+(copied|cited|written|named|kept|listed|spelled|read)\b", re.I)
SECOND_PERSON = re.compile(r"\b(you|your)\b", re.I)


def screen(text):
    sents = re.split(r"(?<=[.;])\s+(?=[A-Z])", text.strip())
    found = []
    for s in sents:
        hits = []
        if IMPERATIVE_START.match(s):
            hits.append("imperative-start")
        m = MODALS.search(s)
        if m:
            hits.append("modal/bar-word:" + m.group(0))
        m = PASSIVE_DIRECTIVE.search(s)
        if m:
            hits.append("passive-directive:" + m.group(0))
        if SECOND_PERSON.search(s):
            hits.append("second-person")
        if hits:
            found.append({"sentence": s, "cues": hits})
    return {"sentences": len(sents), "flagged": found}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    base_bytes = {f: (PROMPTS / BASE / f).read_bytes() for f in FILES}
    base_lines = lines_of(base_bytes["phase1.md"])
    bl = blocks(base_lines)

    # ---- self-test against hand-read facts ----
    st = {}
    st["base_line_count"] = (len(base_lines), HAND_READ["base_line_count"])
    st["base_line_1"] = (base_lines[0], HAND_READ["base_line_1"])
    st["base_line_24_prefix"] = (base_lines[23].startswith(HAND_READ["base_line_24_prefix"]), True)
    st["base_line_163_prefix"] = (base_lines[162].startswith(HAND_READ["base_line_163_prefix"]), True)
    st["base_line_168_prefix"] = (base_lines[167].startswith(HAND_READ["base_line_168_prefix"]), True)
    st["base_line_172"] = (base_lines[171], HAND_READ["base_line_172"])
    st["base_line_173"] = (base_lines[172], HAND_READ["base_line_173"])
    st["base_title_count"] = (len(bl), HAND_READ["base_title_count"])
    st["base_first_title_line"] = (bl[0][0], HAND_READ["base_first_title_line"])
    st["base_last_title_line"] = (bl[-1][0], HAND_READ["base_last_title_line"])
    arm_lines = {a: lines_of((PROMPTS / a / "phase1.md").read_bytes()) for a in ARMS}
    aligned = {a: align(base_lines, arm_lines[a]) for a in ARMS}
    for a in ARMS:
        r = aligned[a]
        got = (r[1], r[1] + len(r[2]) - 1) if r[0] == "ok" else r
        st[f"diff_insert[{a}]"] = (got, HAND_READ["diff_insert"][a])
    failed = {k: v for k, v in st.items() if v[0] != v[1]}
    if failed:
        print("SELF-TEST FAILED; nothing reported:")
        for k, v in failed.items():
            print(f"  {k}: code found {v[0]!r}, hand-read {v[1]!r}")
        sys.exit(1)
    print(f"SELF-TEST PASSED: {len(st)} hand-read facts match the code's reading.")

    report = {"base": BASE, "self_test_facts": len(st), "arms": {}}
    def base_end_of(prefix):
        """Last line (1-based) of the one base block whose title line starts with prefix."""
        hits = [e for (_, e, t) in bl if t.startswith(prefix)]
        assert len(hits) == 1, (prefix, hits)
        return hits[0]
    base_end = {spec["block"]: base_end_of(spec["block"]) for spec in ARMS.values() if "block" in spec}
    output_idx = base_lines.index("OUTPUT")  # 0-based index of OUTPUT; 1-based line is output_idx + 1
    last_rule_end = max(e for (_, e, _) in bl)
    # convention of the base's multi-line blocks: do non-title lines start with two spaces?
    sub = [l for (s, e, _) in bl for l in base_lines[s:e]]  # lines after each title within its block
    base_sub_indented = sum(1 for l in sub if l.startswith("  "))
    report["base_block_sublines"] = {"count": len(sub), "two_space_indented": base_sub_indented}
    dbg_lines = lines_of((PROMPTS / DBG / "phase1.md").read_bytes())
    dbg_al = align(base_lines, dbg_lines)
    report["dbg_block"] = {"status": dbg_al[0], "start_line": dbg_al[1] if dbg_al[0] == "ok" else None,
                           "lines": len(dbg_al[2]) if dbg_al[0] == "ok" else None,
                           "sha12": sha("\n".join(dbg_al[2]).encode()) if dbg_al[0] == "ok" else None}
    dbg_other = {f: sha(base_bytes[f]) == sha((PROMPTS / DBG / f).read_bytes()) for f in FILES if (PROMPTS / DBG / f).exists()}
    report["dbg_other_files_identical_to_base"] = dbg_other

    for a, spec in ARMS.items():
        d = PROMPTS / a
        arm = {"files": {}, "extra_files": sorted(p.name for p in d.iterdir() if p.name not in FILES),
               "missing_files": [f for f in FILES if not (d / f).exists()]}
        for f in FILES:
            if not (d / f).exists():
                continue
            b = (d / f).read_bytes()
            arm["files"][f] = {"identical": b == base_bytes[f], "size": len(b), "base_size": len(base_bytes[f]),
                               "sha12": sha(b), "base_sha12": sha(base_bytes[f])}
            if f == "README.md" and b != base_bytes[f]:
                arm["files"][f]["arm_text"] = b.decode("utf-8")
                arm["files"][f]["base_text"] = base_bytes[f].decode("utf-8")
        pb = (d / "phase1.md").read_bytes()
        arm["phase1_endings"] = {"arm": endings(pb), "base": endings(base_bytes["phase1.md"])}
        r = aligned[a]
        p1 = {"alignment": r[0]}
        if r[0] != "ok":
            p1["detail"] = r[1]
        else:
            start, blk = r[1], r[2]
            body = "\n".join(blk)
            p1.update({
                "block_start_line": start, "block_end_line": start + len(blk) - 1, "block_lines": len(blk),
                "block_lines_as_expected": len(blk) == EXPECTED_BLOCK_LINES,
                "block_first_line": blk[0], "block_first_line_as_expected": blk[0] == spec["first_line"],
                "block_words": len(body.split()), "block_chars": len(body), "block_sha12": sha(body.encode()),
                "block_sublines_two_space_indented": sum(1 for l in blk[1:] if l.startswith("  ")),
                "block_sublines": len(blk) - 1,
                "line_after_block": arm_lines[a][start - 1 + len(blk)] if start - 1 + len(blk) < len(arm_lines[a]) else None,
                "line_before_block": arm_lines[a][start - 2] if start >= 2 else None,
                "arm_line_count": len(arm_lines[a]), "base_line_count": len(base_lines),
                "arm_titles": sum(1 for l in arm_lines[a] if TITLE_RE.match(l)), "base_titles": len(bl),
            })
            # position check
            if spec["where"] == "after_block":
                exp_start = base_end[spec["block"]] + 1
                p1["expected_start_line"] = exp_start
                p1["position_as_expected"] = (start == exp_start)
                p1["position_note"] = (f"block '{spec['block']}' ends at base line {base_end[spec['block']]}; "
                                       f"inserted block starts at line {start}; the original line now after it is base line {exp_start}")
            else:
                exp_start = last_rule_end + 1
                p1["expected_start_line"] = exp_start
                after = arm_lines[a][start - 1 + len(blk): start + 1 + len(blk)]
                p1["position_as_expected"] = (start == exp_start and after == ["", "OUTPUT"])
                p1["position_note"] = (f"last rule block ends at base line {last_rule_end}; base blank line {output_idx}, "
                                       f"OUTPUT at base line {output_idx + 1}; inserted block starts at line {start}; "
                                       f"two lines after it: {after}")
            p1["block_identical_to_dbg_block"] = (dbg_al[0] == "ok" and blk == dbg_al[2])
            if a == "two_phase_p1o_sham":
                p1["instruction_screen"] = screen(" ".join(l.strip() for l in blk[1:]))
        arm["phase1"] = p1
        report["arms"][a] = arm

    f_blk = aligned["two_phase_p1o_first"][2]
    l_blk = aligned["two_phase_p1o_last"][2]
    s_blk = aligned["two_phase_p1o_sham"][2]
    report["first_and_last_blocks_identical"] = (f_blk == l_blk)
    report["word_counts"] = {"bar_block": len("\n".join(f_blk).split()), "sham_block": len("\n".join(s_blk).split()),
                             "difference": len("\n".join(s_blk).split()) - len("\n".join(f_blk).split())}

    out = Path(__file__).resolve().parent / "verify_prompts.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---- plain print ----
    print(f"\nBase {BASE}: phase1.md {len(base_lines)} lines, {len(bl)} rule blocks (title lines {bl[0][0]}-{bl[-1][0]}), "
          f"last rule block ends line {last_rule_end}, OUTPUT at line {output_idx + 1}; endings {endings(base_bytes['phase1.md'])}")
    print(f"Base block sub-lines: {base_sub_indented}/{len(sub)} start with two spaces.")
    print(f"{DBG}: phase1 block {report['dbg_block']}; other files identical to base: {dbg_other}")
    for a, arm in report["arms"].items():
        print(f"\n== {a}")
        print(f"  extra files: {arm['extra_files']}  missing: {arm['missing_files']}")
        for f, v in arm["files"].items():
            tag = "IDENTICAL" if v["identical"] else f"DIFFERS ({v['base_size']} -> {v['size']} bytes)"
            exp = " (expected identical)" if f in EXPECT_IDENTICAL else ""
            print(f"  {f:16s} {tag}{exp}")
            if f == "README.md" and not v["identical"]:
                print(f"     base: {v['base_text'].strip()}")
                print(f"     arm : {v['arm_text'].strip()}")
        print(f"  phase1 endings arm={arm['phase1_endings']['arm']}")
        p1 = arm["phase1"]
        if p1["alignment"] != "ok":
            print(f"  phase1 alignment BAD: {p1['detail']}")
            continue
        print(f"  phase1: {p1['base_line_count']} -> {p1['arm_line_count']} lines; titles {p1['base_titles']} -> {p1['arm_titles']}; "
              f"one inserted block at lines {p1['block_start_line']}-{p1['block_end_line']} "
              f"({p1['block_lines']} lines, expected {EXPECTED_BLOCK_LINES}: {p1['block_lines_as_expected']}); "
              f"{p1['block_words']} words, {p1['block_chars']} chars, sha12 {p1['block_sha12']}")
        print(f"  first line {p1['block_first_line']!r} as expected: {p1['block_first_line_as_expected']}")
        print(f"  position as expected: {p1['position_as_expected']} -- {p1['position_note']}")
        print(f"  line before block: {p1['line_before_block'][:70]!r}")
        print(f"  line after block : {p1['line_after_block'][:70]!r}")
        print(f"  block sub-lines two-space indented: {p1['block_sublines_two_space_indented']}/{p1['block_sublines']}; "
              f"identical to dbg arm's block: {p1['block_identical_to_dbg_block']}")
        if "instruction_screen" in p1:
            sc = p1["instruction_screen"]
            print(f"  sham screen: {sc['sentences']} sentences, {len(sc['flagged'])} flagged")
            for fl in sc["flagged"]:
                print(f"    cues {fl['cues']}: {fl['sentence'][:170]}")
    print(f"\nfirst and last blocks identical: {report['first_and_last_blocks_identical']}; word counts {report['word_counts']}")
    print(f"written {out}")


if __name__ == "__main__":
    main()
