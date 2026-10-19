"""Compare prompts/two_phase_v9j with prompts/two_phase_v9i file by file.

Expected (from the task):
  common.md, phase1_user.md, phase2_user.md : byte-identical
  phase1.md, phase2.md : differ only by
    (a) one sentence appended to the Outcome line of the "Processor control-unit state." block
    (b) the KEEP blocks (8 titles) moved to the end of their step, order change only
Everything else is reported as a difference.

Run:  python -B verify_v9j.py
No imports from the lab's run scripts; no API calls; reads files only.
"""
import sys, re, io, json
from collections import Counter
from pathlib import Path

LAB = Path(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab")
OLD = LAB / "prompts" / "two_phase_v9i"
NEW = LAB / "prompts" / "two_phase_v9j"

MOVED_TITLES = [
    "- Control record ports.",
    "- Access command ports.",
    "- Entry selects and register addresses.",
    "- Coprocessor progress state.",
    "- Boundary outputs.",
    "- Done and wait inputs.",
    "- Link handshake ports.",
    "- Busy locks.",
]
BAR_TITLES = [
    "- Stored-word arrays.",
    "- Processor control-unit state.",
    "- Forwarded-access stages.",
    "- Transfer records.",
    "- Response merges",
]
CU_TITLE = "- Processor control-unit state."

out = io.StringIO()


def P(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    out.write(s + "\n")


problems = []


def problem(msg):
    problems.append(msg)
    P("  PROBLEM:", msg)


# ---------- helpers ----------
def read_bytes(p):
    return p.read_bytes()


def read_lines(p):
    raw = p.read_bytes().decode("utf-8")
    lines = raw.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]  # trailing newline
    return [l.rstrip("\r") for l in lines]


def blocks_of(lines):
    """Block = a line not starting with whitespace, plus following lines starting with whitespace.
    Blank lines are their own blocks (kind 'blank')."""
    blocks = []
    cur = None
    for i, l in enumerate(lines, 1):
        if l.strip() == "":
            if cur:
                blocks.append(cur)
                cur = None
            blocks.append({"start": i, "lines": [l], "kind": "blank"})
            continue
        if l[0].isspace() and cur is not None and cur["kind"] != "blank":
            cur["lines"].append(l)
            continue
        if cur:
            blocks.append(cur)
        cur = {"start": i, "lines": [l], "kind": "text"}
    if cur:
        blocks.append(cur)
    for b in blocks:
        b["title"] = b["lines"][0]
        b["text"] = "\n".join(b["lines"])
    return blocks


def title_matches(b, prefixes):
    return b["kind"] == "text" and any(b["title"].startswith(p) for p in prefixes)


def short(s, n=90):
    return s if len(s) <= n else s[:n] + "..."


def wc_words(text):
    return len(text.split())


# ---------- self-test against hand-read lines (read by eye from sed/grep output this session) ----------
HAND = {
    ("v9i", "phase1.md"): {"nlines": 212, 158: CU_TITLE, 173: "OUTPUT", 163: "- Control record ports.", 112: "- Stored-word arrays."},
    ("v9i", "phase2.md"): {"nlines": 198, 145: "5. Secondary.", 40: "- Control record ports.", 139: CU_TITLE, 152: "OUTPUT"},
    ("v9j", "phase1.md"): {"nlines": 212},
    ("v9j", "phase2.md"): {"nlines": 198},
}
P("=== SELF-TEST (script line reading vs hand-read lines) ===")
selftest_ok = True
for (ver, fn), facts in HAND.items():
    folder = OLD if ver == "v9i" else NEW
    ls = read_lines(folder / fn)
    for k, v in facts.items():
        if k == "nlines":
            ok = len(ls) == v
            got = len(ls)
        else:
            ok = ls[k - 1].startswith(v)
            got = short(ls[k - 1], 60)
        P(f"  {ver}/{fn} {k}: expect {v!r} got {got!r} -> {'OK' if ok else 'FAIL'}")
        selftest_ok &= ok
if not selftest_ok:
    P("SELF-TEST FAILED: nothing below may be reported.")
    sys.exit(2)
P("  self-test passed\n")

# ---------- 1. file inventory + byte compare ----------
P("=== FILE INVENTORY ===")
old_files = sorted(p.name for p in OLD.iterdir())
new_files = sorted(p.name for p in NEW.iterdir())
P("  v9i:", old_files)
P("  v9j:", new_files)
if old_files != new_files:
    problem(f"file sets differ: only-v9i={set(old_files)-set(new_files)} only-v9j={set(new_files)-set(old_files)}")

P("\n=== BYTE COMPARE ===")
byte_identical = {}
for fn in sorted(set(old_files) | set(new_files)):
    a = read_bytes(OLD / fn) if (OLD / fn).exists() else None
    b = read_bytes(NEW / fn) if (NEW / fn).exists() else None
    same = (a == b)
    byte_identical[fn] = same
    la = len(a) if a is not None else "-"
    lb = len(b) if b is not None else "-"
    P(f"  {fn:16s} v9i={la:>6} bytes  v9j={lb:>6} bytes  identical={same}")
for fn in ["common.md", "phase1_user.md", "phase2_user.md"]:
    if not byte_identical.get(fn):
        problem(f"{fn} expected byte-identical but differs")
if byte_identical.get("README.md"):
    P("  README.md identical (not expected, but not a problem)")
else:
    P("  README.md differs (expected: it names the version).")
    P("    v9i:", repr(read_bytes(OLD / "README.md").decode("utf-8")))
    P("    v9j:", repr(read_bytes(NEW / "README.md").decode("utf-8")))

# ---------- 2. phase1.md / phase2.md ----------
figures = {"byte_identical": byte_identical, "word_counts": {}, "phases": {}}
for fn in ["common.md", "phase1_user.md", "phase2_user.md", "phase1.md", "phase2.md", "README.md"]:
    figures["word_counts"][fn] = {"v9i": wc_words((OLD / fn).read_text(encoding="utf-8")),
                                  "v9j": wc_words((NEW / fn).read_text(encoding="utf-8"))}

for fn, step_end_marker in [("phase1.md", "OUTPUT"), ("phase2.md", "5. Secondary.")]:
    P(f"\n=== {fn} ===")
    ol, nl = read_lines(OLD / fn), read_lines(NEW / fn)
    oraw, nraw = read_bytes(OLD / fn), read_bytes(NEW / fn)
    fig = figures["phases"][fn] = {}
    cr_o, cr_n = oraw.count(b"\r"), nraw.count(b"\r")
    lf_o, lf_n = oraw.count(b"\n"), nraw.count(b"\n")
    P(f"  lines: v9i={len(ol)} v9j={len(nl)}   CR count: v9i={cr_o} v9j={cr_n}   LF count: v9i={lf_o} v9j={lf_n}")
    fig["lines"] = {"v9i": len(ol), "v9j": len(nl)}

    # --- line multiset ---
    co, cn = Counter(ol), Counter(nl)
    only_old = list((co - cn).elements())
    only_new = list((cn - co).elements())
    P(f"  line multiset: lines only in v9i = {len(only_old)}, only in v9j = {len(only_new)}")
    for l in only_old:
        P("    v9i-only:", short(l, 160))
    for l in only_new:
        P("    v9j-only:", short(l, 160))
    fig["lines_only_v9i"] = len(only_old)
    fig["lines_only_v9j"] = len(only_new)

    # --- the one expected changed line: Outcome of control-unit block ---
    ob, nb = blocks_of(ol), blocks_of(nl)
    ocu = [b for b in ob if title_matches(b, [CU_TITLE])]
    ncu = [b for b in nb if title_matches(b, [CU_TITLE])]
    P(f"  control-unit blocks: v9i={len(ocu)} (line {[b['start'] for b in ocu]}), v9j={len(ncu)} (line {[b['start'] for b in ncu]})")
    if len(ocu) != 1 or len(ncu) != 1:
        problem(f"{fn}: expected exactly one control-unit block per version")
    else:
        a, b = ocu[0], ncu[0]
        if len(a["lines"]) != len(b["lines"]):
            problem(f"{fn}: control-unit block line count differs {len(a['lines'])} vs {len(b['lines'])}")
        diffs = [(i, x, y) for i, (x, y) in enumerate(zip(a["lines"], b["lines"])) if x != y]
        P(f"  control-unit block: {len(diffs)} differing line(s) of {len(a['lines'])}")
        for i, x, y in diffs:
            field = x.strip().split(":")[0]
            is_outcome = x.strip().startswith("Outcome:")
            appended = y[len(x):] if y.startswith(x) else None
            P(f"    line {a['start']+i} field={field!r} is_Outcome={is_outcome} v9j_startswith_v9i={y.startswith(x)}")
            if appended is not None:
                n_sent = len(re.findall(r"[.!?](?=\s|$)", appended.strip()))
                P(f"    appended text ({len(appended.split())} words, {n_sent} sentence-ending mark(s)):")
                P(f"      {appended!r}")
                P(f"    v9i Outcome line ends with: {x[-80:]!r}")
                fig["appended_sentence"] = appended.strip()
                fig["appended_words"] = len(appended.split())
                if not is_outcome:
                    problem(f"{fn}: changed line is not the Outcome line")
                if n_sent != 1:
                    problem(f"{fn}: appended text has {n_sent} sentence marks, expected 1")
                if not x.rstrip().endswith("."):
                    P("    note: v9i Outcome line did not end with '.'")
                if not appended.startswith(" "):
                    problem(f"{fn}: appended text does not start with a space (joins the previous sentence)")
            else:
                problem(f"{fn}: control-unit line {a['start']+i} changed but is not an append: v9i={short(x,120)!r} v9j={short(y,120)!r}")
        if len(diffs) != 1:
            problem(f"{fn}: control-unit block has {len(diffs)} changed lines, expected 1")
        exp_old = [x for _, x, _ in diffs]
        exp_new = [y for _, _, y in diffs]
        if sorted(only_old) != sorted(exp_old) or sorted(only_new) != sorted(exp_new):
            problem(f"{fn}: line multiset differs beyond the control-unit Outcome line")
        else:
            P("  line multiset: differs ONLY by that one Outcome line (confirmed)")

    # --- block order: remove moved blocks, compare the rest in order ---
    omoved = [b for b in ob if title_matches(b, MOVED_TITLES)]
    nmoved = [b for b in nb if title_matches(b, MOVED_TITLES)]
    P(f"  moved-title blocks found: v9i={len(omoved)} v9j={len(nmoved)}")
    P("    v9i order:", [(b["start"], short(b["title"], 45)) for b in omoved])
    P("    v9j order:", [(b["start"], short(b["title"], 45)) for b in nmoved])
    fig["moved_blocks_v9i"] = [(b["start"], b["title"]) for b in omoved]
    fig["moved_blocks_v9j"] = [(b["start"], b["title"]) for b in nmoved]
    present = [t for t in MOVED_TITLES if any(b["title"].startswith(t) for b in ob)]
    absent = [t for t in MOVED_TITLES if t not in present]
    P(f"    titles absent from this phase: {absent}")
    fig["moved_titles_absent"] = absent
    if Counter(b["text"] for b in omoved) != Counter(b["text"] for b in nmoved):
        problem(f"{fn}: moved blocks' texts differ between versions")
        for b in omoved:
            if b["text"] not in {x["text"] for x in nmoved}:
                P("     v9i moved block not matched:", short(b["title"], 60))
    else:
        P("  moved blocks: texts identical in both versions (as a multiset)")
    orest = [b for b in ob if not title_matches(b, MOVED_TITLES)]
    nrest = [b for b in nb if not title_matches(b, MOVED_TITLES)]
    orest_t = [b for b in orest if b["kind"] == "text"]
    nrest_t = [b for b in nrest if b["kind"] == "text"]
    P(f"  non-moved text blocks: v9i={len(orest_t)} v9j={len(nrest_t)}")
    if len(orest_t) != len(nrest_t):
        problem(f"{fn}: non-moved block counts differ")
    rest_diffs = [(i, a, b) for i, (a, b) in enumerate(zip(orest_t, nrest_t)) if a["text"] != b["text"]]
    P(f"  non-moved blocks compared position by position: {len(rest_diffs)} differ (1 = only the control-unit append; more = other blocks shifted; see the permutation analysis below)")
    # --- permutation analysis: which blocks REALLY moved (minimal set), using the block texts ---
    # map the control-unit Outcome change away so texts match
    def norm(b):
        return b["text"] if not b["title"].startswith(CU_TITLE) else CU_TITLE
    # residual = text blocks that are NOT one of the 8 keep titles; if their order is unchanged,
    # the 8 titles explain the whole permutation; otherwise find the minimal extra moved set
    ot = [b for b in ob if b["kind"] == "text" and not title_matches(b, MOVED_TITLES)]
    nt = [b for b in nb if b["kind"] == "text" and not title_matches(b, MOVED_TITLES)]
    okeys, nkeys = [norm(b) for b in ot], [norm(b) for b in nt]
    residual_same_order = (okeys == nkeys)
    P(f"  residual (keep titles removed) in the same order in both versions: {residual_same_order}")
    fig["residual_same_order"] = residual_same_order
    dup = [k for k, c in Counter(okeys).items() if c > 1]
    P(f"  residual text blocks: v9i={len(ot)} v9j={len(nt)}; duplicate block texts in v9i: {len(dup)}; multiset equal: {Counter(okeys) == Counter(nkeys)}")
    if Counter(okeys) != Counter(nkeys):
        problem(f"{fn}: the set of text blocks differs between versions (beyond the control-unit Outcome line)")
    elif dup:
        problem(f"{fn}: duplicate block texts, permutation analysis skipped")
    elif residual_same_order:
        P("  => the 8 keep titles explain the whole reordering; no other block changed position")
        fig["minimal_moved_set"] = [(b["start"], None, b["title"]) for b in omoved]
        fig["unexpected_moved_blocks"] = []
        o_order = [b["title"] for b in omoved]
        n_order = [b["title"] for b in nmoved]
        P(f"  keep blocks' order among themselves: {'same' if o_order == n_order else 'changed'}")
        fig["keep_order_same"] = (o_order == n_order)
    else:
        pos_new = {k: i for i, k in enumerate(nkeys)}
        perm = [pos_new[k] for k in okeys]  # v9j index of each v9i block, in v9i order
        # longest increasing subsequence = blocks that kept their relative order
        import bisect
        tails, tails_idx, prev = [], [], [-1] * len(perm)
        for i, v in enumerate(perm):
            j = bisect.bisect_left(tails, v)
            if j == len(tails):
                tails.append(v); tails_idx.append(i)
            else:
                tails[j] = v; tails_idx[j] = i
            prev[i] = tails_idx[j - 1] if j > 0 else -1
        lis = []
        k = tails_idx[-1] if tails_idx else -1
        while k != -1:
            lis.append(k); k = prev[k]
        kept = set(lis)
        really_moved = [ot[i] for i in range(len(ot)) if i not in kept]
        P(f"  minimal moved set (blocks not in the longest order-preserving subsequence): {len(really_moved)}")
        extra = []
        for b in really_moved:
            tag = "expected" if title_matches(b, MOVED_TITLES) else "UNEXPECTED"
            nbk = nt[pos_new[norm(b)]]
            P(f"    {tag:10s} v9i line {b['start']:4d} -> v9j line {nbk['start']:4d}  {short(b['title'], 70)!r}")
            if tag == "UNEXPECTED":
                extra.append(b)
        fig["minimal_moved_set"] = [(b["start"], nt[pos_new[norm(b)]]["start"], b["title"]) for b in really_moved]
        fig["unexpected_moved_blocks"] = [(b["start"], nt[pos_new[norm(b)]]["start"], wc_words(b["text"]), b["title"]) for b in extra]
        fig["unexpected_moved_words_total"] = sum(wc_words(b["text"]) for b in extra)
        if extra:
            problem(f"{fn}: {len(extra)} block(s) outside the 8 titles also changed position (see list)")
            ot_all = [b for b in ob if b["kind"] == "text"]
            nt_all = [b for b in nb if b["kind"] == "text"]
            for b in extra:
                nbk = nt[pos_new[norm(b)]]
                i_old = ot_all.index(b); i_new = nt_all.index(nbk)
                P(f"    UNEXPECTED block, v9i line {b['start']} -> v9j line {nbk['start']}, {len(b['lines'])} line(s), {wc_words(b['text'])} words: {short(b['text'], 230)!r}")
                P(f"       v9i neighbours: before={short(ot_all[i_old-1]['title'],60)!r} (line {ot_all[i_old-1]['start']}), after={short(ot_all[i_old+1]['title'],60)!r} (line {ot_all[i_old+1]['start']})")
                P(f"       v9j neighbours: before={short(nt_all[i_new-1]['title'],60)!r} (line {nt_all[i_new-1]['start']}), after={short(nt_all[i_new+1]['title'],60)!r} (line {nt_all[i_new+1]['start']})")
        # the order of the non-moved (titled) keep blocks among themselves: did it change?
        o_order = [b["title"] for b in omoved]
        n_order = [b["title"] for b in nmoved]
        P(f"  keep blocks' order among themselves: {'same' if o_order == n_order else 'changed'}")
        fig["keep_order_same"] = (o_order == n_order)

    oblank = [i for i, b in enumerate(ob) if b["kind"] == "blank"]
    nblank = [i for i, b in enumerate(nb) if b["kind"] == "blank"]
    P(f"  blank-line blocks: v9i={len(oblank)} v9j={len(nblank)}  positions(block index) v9i={oblank} v9j={nblank}")
    if len(oblank) != len(nblank):
        problem(f"{fn}: blank-line count differs")
    # full block sequence, moved removed, including blanks: same?
    oseq = [b["text"] for b in orest]
    nseq = [b["text"] for b in nrest]
    same_len = len(oseq) == len(nseq)
    n_seq_diff = sum(1 for x, y in zip(oseq, nseq) if x != y) if same_len else None
    P(f"  non-moved sequence incl. blanks: same length={same_len}, differing positions={n_seq_diff} (1 = only the control-unit block)")

    # --- where do the moved blocks sit in v9j? end of step check ---
    nend = [b for b in nb if b["kind"] == "text" and b["title"].startswith(step_end_marker)]
    if len(nend) != 1:
        problem(f"{fn}: step-end marker {step_end_marker!r} found {len(nend)} times in v9j")
    else:
        end_idx = nb.index(nend[0])
        j = end_idx - 1
        while j >= 0 and nb[j]["kind"] == "blank":
            j -= 1
        tail = []
        while j >= 0 and nb[j]["kind"] == "text" and title_matches(nb[j], MOVED_TITLES):
            tail.append(nb[j])
            j -= 1
        tail.reverse()
        P(f"  v9j: blocks immediately before {step_end_marker!r} (line {nend[0]['start']}) that are moved titles: {len(tail)} of {len(nmoved)}")
        P("    tail order:", [(b["start"], short(b["title"], 45)) for b in tail])
        if j >= 0:
            P(f"    block just before the tail: line {nb[j]['start']} {short(nb[j]['title'],70)!r}")
        if len(tail) != len(nmoved):
            problem(f"{fn}: not all moved blocks are contiguous at the end of the step in v9j ({len(tail)} of {len(nmoved)} directly before {step_end_marker!r})")
        fig["tail_order_v9j"] = [b["title"] for b in tail]
        fig["block_before_tail_v9j"] = nb[j]["title"] if j >= 0 else None
        # what sits between the LAST moved block and the step end in v9j?
        if nmoved:
            last_m = nb.index(nmoved[-1])
            between = [b for b in nb[last_m + 1:end_idx] if b["kind"] == "text"]
            P(f"  v9j: text blocks between the last moved block (line {nmoved[-1]['start']}) and {step_end_marker!r}: {len(between)}")
            for b in between:
                P(f"    line {b['start']:4d} {short(b['title'], 70)!r}  ({'BAR' if title_matches(b, BAR_TITLES) else 'other'})")
            fig["blocks_after_last_moved_v9j"] = [(b["start"], b["title"]) for b in between]
            # and inside the moved run: any non-keep text blocks interleaved?
            first_m = nb.index(nmoved[0])
            inter = [b for b in nb[first_m:last_m + 1] if b["kind"] == "text" and not title_matches(b, MOVED_TITLES)]
            P(f"  v9j: non-keep text blocks interleaved inside the moved run (lines {nmoved[0]['start']}-{nmoved[-1]['start']}): {len(inter)}")
            for b in inter:
                P(f"    line {b['start']:4d} {short(b['title'], 90)!r}")
            fig["interleaved_in_moved_run_v9j"] = [(b["start"], b["title"]) for b in inter]
        if fn == "phase2.md":
            s4 = [b for b in nb if b["kind"] == "text" and b["title"].startswith("4. Primary.")]
            if s4 and tail and not (nb.index(s4[0]) < nb.index(tail[0]) < end_idx):
                problem("phase2: tail is not between '4. Primary.' and '5. Secondary.'")
            else:
                P("    phase2: tail lies between '4. Primary.' and '5. Secondary.' (step 4)")
        # same check in v9i: where were they?
        oend = [b for b in ob if b["kind"] == "text" and b["title"].startswith(step_end_marker)]
        if len(oend) == 1:
            oend_idx = ob.index(oend[0])
            P(f"  v9i: moved blocks' block indexes {[ob.index(b) for b in omoved]}, step-end marker at block index {oend_idx}")

    # --- positions relative to the five bar blocks ---
    P("  bar blocks (line numbers):")
    for ver, bl in [("v9i", ob), ("v9j", nb)]:
        bars = [(b["start"], short(b["title"], 40)) for b in bl if title_matches(b, BAR_TITLES)]
        P(f"    {ver}: {bars}")
        fig[f"bar_blocks_{ver}"] = bars
        if len(bars) != 5:
            problem(f"{fn} {ver}: found {len(bars)} bar blocks, expected 5")

    def order_listing(bl, label):
        seq = [b for b in bl if b["kind"] == "text" and (title_matches(b, BAR_TITLES) or title_matches(b, MOVED_TITLES))]
        P(f"  {label}: order of bar (B) and moved (M) blocks, with line numbers:")
        for b in seq:
            tag = "B" if title_matches(b, BAR_TITLES) else "M"
            P(f"    {tag} {b['start']:4d}  {short(b['title'], 50)}")
        return [("B" if title_matches(b, BAR_TITLES) else "M", b["start"], b["title"]) for b in seq]

    fig["bar_moved_order_v9i"] = order_listing(ob, "v9i")
    fig["bar_moved_order_v9j"] = order_listing(nb, "v9j")
    bars_n = [nb.index(b) for b in nb if title_matches(b, BAR_TITLES)]
    moved_n = [nb.index(b) for b in nb if title_matches(b, MOVED_TITLES)]
    if bars_n and moved_n:
        P(f"  v9j: every moved block after every bar block? {min(moved_n) > max(bars_n)}   (last bar block index {max(bars_n)}, first moved index {min(moved_n)})")
        fig["v9j_all_moved_after_all_bars"] = min(moved_n) > max(bars_n)
    bars_o = [ob.index(b) for b in ob if title_matches(b, BAR_TITLES)]
    moved_o = [ob.index(b) for b in ob if title_matches(b, MOVED_TITLES)]
    if bars_o and moved_o:
        before = sum(1 for m in moved_o if m < min(bars_o))
        between = sum(1 for m in moved_o if min(bars_o) < m < max(bars_o))
        after = sum(1 for m in moved_o if m > max(bars_o))
        P(f"  v9i: moved blocks before first bar: {before}, between first and last bar: {between}, after last bar: {after}")
        fig["v9i_moved_vs_bars"] = {"before_first_bar": before, "between": between, "after_last_bar": after}

    # --- OUTPUT sections ---
    def output_section(lines):
        idx = [i for i, l in enumerate(lines) if l == "OUTPUT"]
        return idx, ("\n".join(lines[idx[0]:]) if idx else None)

    oi, osec = output_section(ol)
    ni, nsec = output_section(nl)
    osec_len = len(osec.split("\n")) if osec else None
    P(f"  OUTPUT line(s): v9i at {[i+1 for i in oi]}, v9j at {[i+1 for i in ni]}; OUTPUT section identical = {osec == nsec}; section length = {osec_len} lines")
    if len(oi) != 1 or len(ni) != 1 or osec != nsec:
        problem(f"{fn}: OUTPUT section not identical or not unique")
    fig["output_identical"] = (osec == nsec)
    fig["output_line"] = {"v9i": [i + 1 for i in oi], "v9j": [i + 1 for i in ni]}
    # also: everything before the first moved/changed point identical?
    first_change = next((i for i, (x, y) in enumerate(zip(ol, nl)) if x != y), None)
    last_change = next((i for i, (x, y) in enumerate(zip(ol[::-1], nl[::-1])) if x != y), None)
    P(f"  first differing line (1-based): {first_change+1 if first_change is not None else None}; last differing line: {len(ol)-last_change if last_change is not None else None}")
    fig["first_diff_line"] = first_change + 1 if first_change is not None else None
    fig["last_diff_line"] = len(ol) - last_change if last_change is not None else None

    fig["word_count"] = figures["word_counts"][fn]
    d = figures["word_counts"][fn]["v9j"] - figures["word_counts"][fn]["v9i"]
    P(f"  word count (whitespace tokens): v9i={figures['word_counts'][fn]['v9i']} v9j={figures['word_counts'][fn]['v9j']} (diff {d:+d}; expected = appended words {fig.get('appended_words')})")
    if fig.get("appended_words") is not None and d != fig["appended_words"]:
        problem(f"{fn}: word-count difference does not equal the appended sentence's word count")

P("\n=== WORD COUNTS (whitespace-separated tokens) ===")
for fn, d in figures["word_counts"].items():
    P(f"  {fn:16s} v9i={d['v9i']:6d}  v9j={d['v9j']:6d}  diff={d['v9j']-d['v9i']:+d}")

P("\n=== PROBLEMS ===")
if not problems:
    P("  none: every difference is within the expected set")
for p in problems:
    P("  -", p)
figures["problems"] = problems

here = Path(__file__).resolve().parent
(here / "verify_v9j_report.txt").write_text(out.getvalue(), encoding="utf-8")
(here / "verify_v9j_figures.json").write_text(json.dumps(figures, indent=1), encoding="utf-8")
P(f"\nwrote {here / 'verify_v9j_report.txt'} and verify_v9j_figures.json")
