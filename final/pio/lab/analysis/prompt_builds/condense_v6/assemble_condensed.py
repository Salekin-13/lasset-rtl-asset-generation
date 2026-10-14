"""Assemble the condensed versions of two_phase_v6 from the condensing workflow (wf_965ed976-a65; result saved as
condense_result.json) and the pieces of make_condense_inputs.py (manifest.json). No merge agent: the three tracks
edit disjoint text, so each version is a plain replacement.

  two_phase_v6a    phase1.md non-core text condensed            (Phase 2 = v6's)
  two_phase_v6b    phase2.md non-core text condensed            (Phase 1 = v6's: v6's stored Phase 1 replies reusable)
  two_phase_v6c    the core sentences condensed, the same text in both phase files
  two_phase_v6abc  all three together (for the one blind boundary test)

A piece is used only if the workflow judged it "equivalent" (both clause checkers, no problem) AND it passes the code
checks. For a chunk:
  - no carriage return (CRLF line ends are first turned into LF);
  - the same line count, with blank lines at the same positions;
  - the same leading and trailing whitespace on every line (indents; segment edges, which build() joins with one space);
  - on every line, the same placeholders in the same order (a core sentence cannot move to another rule's line);
  - every line head kept;
  - every quoted string, step/section reference and rule name of the original still present.
  (The check that the chunk's placeholder list is unchanged is kept for its message. Given the per-line check, it is
  redundant.)
For a core sentence: it stays on one line, no placeholder inside, the same tokens.
Otherwise the original text is used and the reason is printed. Then per version: the project prompt checker, the OUTPUT
sections byte-identical to v6, chain.new_format, each core sentence once in each phase file, words, shas.

Lines of a chunk. A chunk's text is its segments joined by "\n": whole file lines, or sentence parts of a very long
line (manifest "layout"). A blank file line is an empty segment, so a chunk whose last segment is a blank line ENDS
with "\n". The line check must compare like with like: the condensed text is first given exactly the original's
leading and trailing blank lines (restore_blank_lines), never stripped alone. (The first version called
check_chunk(orig, text.rstrip("\n")), so p1_09, p2_04, p2_11 and p2_12, whose last segment is blank, failed
"line count N -> N-1" even when unchanged.) build() refuses a chunk whose segment count differs from its layout, in
either direction, instead of letting zip() drop a line.

Self-test (selftest(); run first in every mode; writes nothing). Every case goes through accept(), the path main()
uses:
  - each unchanged chunk and its edge variants (newlines stripped or added at either end, CRLF) are taken and stored
    byte for byte;
  - planted faults are rejected:
    - merged lines, a moved blank line, an emptied line;
    - a lone CR, a changed indent or trailing space;
    - swapped, deleted or moved placeholders;
    - a lost quoted string, reference or name, a damaged head;
    - for core sentences, a split line, a placeholder inside or a lost token;
  - tokens() equals the manifest's own record;
  - synthetic chunks cover the first version's bug and leading blank lines;
  - unchanged pieces rebuild v6 exactly, and build() refuses a segment too few or too many.
A mutation run (each check broken in turn) is caught by this self-test, except for the redundant placeholder-list
check.

  python assemble_condensed.py              self-test, then build and write the four version folders
  python assemble_condensed.py --selftest   self-test only (writes nothing)
  python assemble_condensed.py --verify     self-test, then build in memory and compare the four version folders and
                                            accepted_pieces.json with the files on disk (writes nothing)
Any other argument is refused (exit 2): only the no-flag mode writes.
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
sys.path.insert(0, str(LAB))
import check_lab_prompt as CK  # noqa: E402

V6 = LAB / "prompts" / "two_phase_v6"
HEAD = re.compile(r"^(\s*\d\. [A-Z][\w -]*\.|- [A-Z][^.\n]{2,40}\.|\s+[A-Z][A-Za-z -]{2,40}[.:](?=\s)|Rules:)")
VERSIONS = ("two_phase_v6a", "two_phase_v6b", "two_phase_v6c", "two_phase_v6abc")
COPIED = ("common.md", "phase1_user.md", "phase2_user.md")


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def tokens(text, names):
    return {
        "quoted": set(re.findall(r'"[^"\n]{1,80}"', text)),
        "refs": set(re.findall(r"\b(?:\d\.\d(?:\.\d)?|\d\([a-c]\)|step \d|steps \d(?: and \d)?|section \d|Phase [12])\b", text)),
        "names": {n for n in names if n in text},
        "placeholders": re.findall(r"\[\[S\d\d\]\]", text),
    }


def restore_blank_lines(orig, new):
    """Blank lines are layout only: when the condensed text lost leading or trailing empty lines that the original
    chunk has (or gained some it does not have), give it exactly the original's leading and trailing blank lines, so
    the line layout matches. Lines with text are never touched."""
    ol, nl = orig.split("\n"), new.split("\n")
    while nl and not nl[-1].strip():
        nl.pop()
    while nl and not nl[0].strip():
        nl.pop(0)
    lead = 0
    while lead < len(ol) and not ol[lead].strip():
        lead += 1
    trail = 0
    while trail < len(ol) - lead and not ol[len(ol) - 1 - trail].strip():
        trail += 1
    return "\n".join(ol[:lead] + nl + ol[len(ol) - trail:])


def blank_positions(lines):
    return [i for i, s in enumerate(lines) if not s.strip()]


def edges(s):
    """The leading and trailing whitespace of a line: layout, like blank lines (indent of sub-items; the edges of a
    long line's sentence segments, which build() joins with one space)."""
    return s[:len(s) - len(s.lstrip())], s[len(s.rstrip()):]


def check_chunk(orig, new, names):
    """new must already have gone through accept()'s preprocessing: CRLF to LF, then restore_blank_lines(orig, new)."""
    probs = []
    if "\r" in new:
        probs.append("carriage return in text")
    ol, nl = orig.split("\n"), new.split("\n")
    if len(ol) != len(nl):
        probs.append(f"line count {len(ol)} -> {len(nl)}")
    else:
        if blank_positions(ol) != blank_positions(nl):
            probs.append(f"blank lines at {blank_positions(ol)} -> {blank_positions(nl)}")
        for i, (a, b) in enumerate(zip(ol, nl)):
            m = HEAD.match(a)
            if m and not b.startswith(m.group(1)):
                probs.append(f"line head lost: {m.group(1)!r}")
            if edges(a) != edges(b) or (not a.strip() and a != b):
                probs.append(f"line {i}: leading or trailing whitespace changed")
            if re.findall(r"\[\[S\d\d\]\]", a) != re.findall(r"\[\[S\d\d\]\]", b):
                probs.append(f"line {i}: placeholders moved between lines")
    to, tn = tokens(orig, names), tokens(new, names)
    if to["placeholders"] != tn["placeholders"]:
        probs.append(f"placeholders {to['placeholders']} -> {tn['placeholders']}")
    for k in ("quoted", "refs", "names"):
        lost = to[k] - tn[k]
        if lost:
            probs.append(f"{k} lost: {sorted(lost)}")
    return probs


def check_core(orig, new, names):
    probs = []
    if "\n" in new.strip():
        probs.append("core sentence spans lines")
    if "[[" in new:
        probs.append("placeholder inside a core sentence")
    to, tn = tokens(orig, names), tokens(new, names)
    for k in ("quoted", "refs", "names"):
        lost = to[k] - tn[k]
        if lost:
            probs.append(f"{k} lost: {sorted(lost)}")
    return probs


def build(manifest, use_p1, use_p2, use_core):
    out = {}
    core = {e["id"]: (use_core.get(e["id"]) or e["text"]) for e in manifest["core"]}
    for k, use in (("phase1", use_p1), ("phase2", use_p2)):
        lines = [[] for _ in range(manifest["lines"][k])]
        for c in manifest["chunks"][k]:
            segs = (use.get(c["id"]) or c["text"]).split("\n")
            if len(segs) != len(c["layout"]):
                raise ValueError(f"{c['id']}: {len(segs)} segments for {len(c['layout'])} layout entries")
            for (li, si, ns), seg in zip(c["layout"], segs):
                lines[li].append(seg)
        b = "\n".join(" ".join(x) for x in lines)
        for sid, s in core.items():
            b = b.replace(f"[[S{sid[1:]}]]", s.strip())
        out[k] = b + manifest["output_sections"][k]
    return out


def accept(M, R):
    """The pieces to use: workflow verdict "equivalent" and the code checks pass. Returns (accepted, log)."""
    names = M["names"]
    orig_chunk = {c["id"]: c["text"] for k in ("phase1", "phase2") for c in M["chunks"][k]}
    orig_core = {e["id"]: e["text"] for e in M["core"]}
    acc = {"p1": {}, "p2": {}, "core": {}}
    log = []
    for r in R:
        if r["status"] != "equivalent" or not r.get("texts"):
            log.append(f"{r['id']}: FALLBACK to original ({r['status']}; {len(r['rounds'])} check rounds)")
            continue
        for t in r["texts"]:
            pid, text = t["id"], t["text"]
            if pid in orig_chunk:
                text = restore_blank_lines(orig_chunk[pid], text.replace("\r\n", "\n"))
                probs = check_chunk(orig_chunk[pid], text, names)
                if probs:
                    log.append(f"{pid}: FALLBACK (code check: {probs})")
                    continue
                acc["p1" if pid.startswith("p1") else "p2"][pid] = text
            elif pid in orig_core:
                probs = check_core(orig_core[pid], text, names)
                if probs:
                    log.append(f"{pid}: FALLBACK (code check: {probs})")
                    continue
                acc["core"][pid] = " ".join(text.split())
            else:
                log.append(f"{pid}: unknown piece id, ignored")
    return acc, log


def plan(acc):
    return {"two_phase_v6a": (acc["p1"], {}, {}), "two_phase_v6b": ({}, acc["p2"], {}),
            "two_phase_v6c": ({}, {}, acc["core"]), "two_phase_v6abc": (acc["p1"], acc["p2"], acc["core"])}


def _fake(pid, text):
    return {"id": pid, "status": "equivalent", "rounds": [], "texts": [{"id": pid, "text": text}]}


def _stored(acc, pid):
    return acc["core"].get(pid) if pid.startswith("S") else acc["p1" if pid.startswith("p1") else "p2"].get(pid)


def selftest(M):
    """Writes nothing. Returns a list of failures (empty = PASS). Every case goes through accept(), the path main()
    uses, so its preprocessing (CRLF to LF, restore_blank_lines) is tested together with the checks."""
    names = M["names"]
    fails = []
    chunks = [c for k in ("phase1", "phase2") for c in M["chunks"][k]]

    def must_accept(pid, orig, text, label):
        acc, log = accept(M, [_fake(pid, text)])
        if _stored(acc, pid) != orig:
            fails.append(f"{pid} {label}: accept() rejects or changes it ({[x for x in log if x.startswith(pid)]})")

    def must_reject(pid, text, label):
        acc, log = accept(M, [_fake(pid, text)])
        if _stored(acc, pid) is not None:
            fails.append(f"{pid} {label}: accept() takes this planted fault")

    for c in chunks:
        o, pid = c["text"], c["id"]
        segs = o.split("\n")
        # 1. the chip's self-test: the unchanged chunk passes check_chunk; accept() takes it and its edge variants
        #    and stores exactly the original
        if check_chunk(o, o, names):
            fails.append(f"{pid}: check_chunk(original, original) reports {check_chunk(o, o, names)}")
        for label, variant in (("as is", o), ("trailing newlines stripped", o.rstrip("\n")),
                               ("extra trailing newline", o + "\n"), ("extra leading newline", "\n" + o),
                               ("edge blank lines stripped", o.strip("\n")), ("CRLF line ends", o.replace("\n", "\r\n"))):
            must_accept(pid, o, variant, label)
        if len(segs) != len(c["layout"]):
            fails.append(f"{pid}: manifest text has {len(segs)} segments for {len(c['layout'])} layout entries")
        # 2. the code's tokens equal the manifest's own record (make_condense_inputs.py computes it separately)
        t = tokens(o, names)
        req = c.get("required", {})
        if {k: (v if k == "placeholders" else sorted(v)) for k, v in t.items()} != {k: req.get(k) for k in t}:
            fails.append(f"{pid}: tokens() differs from the manifest's required tokens")
        # 3. planted faults: each must be rejected by accept()
        text_lines = [i for i, s in enumerate(segs) if s.strip()]

        def put(i, s):
            return "\n".join(segs[:i] + [s] + segs[i + 1:])

        pairs = [i for i in range(len(segs) - 1) if segs[i].strip() and segs[i + 1].strip()]
        if pairs:
            i = pairs[0]
            must_reject(pid, "\n".join(segs[:i] + [segs[i] + " " + segs[i + 1]] + segs[i + 2:]), f"text lines {i} and {i + 1} merged")
        inner = [i for i in range(1, len(segs) - 1) if not segs[i].strip() and segs[i + 1].strip()]
        if inner:
            i = inner[0]
            must_reject(pid, "\n".join(segs[:i] + [segs[i + 1], ""] + segs[i + 2:]), f"blank line moved from {i} to {i + 1}")
        if text_lines:
            i = text_lines[0]
            # inside the line: a "\r" right before "\n" is just a CRLF line end, which accept() turns into LF
            lone_cr = segs[i].replace(" ", "\r", 1) if " " in segs[i].strip() else segs[i] + "\r" + segs[i]
            must_reject(pid, put(i, lone_cr), "lone carriage return inside a line")
            must_reject(pid, put(i, " " + segs[i]), "indent added")
            must_reject(pid, put(i, segs[i] + " "), "trailing space added")
        # a text line emptied: only the blank-position check sees it when the line has no head, placeholder or token
        plain = [i for i in text_lines if not HEAD.match(segs[i]) and not re.search(r"\[\[S\d\d\]\]|\"", segs[i])
                 and not any(x in segs[i] for k in ("refs", "names") for x in t[k])]
        if len(text_lines) >= 2 and plain:
            must_reject(pid, put(plain[0], ""), f"text line {plain[0]} emptied")
        ind = [i for i in text_lines if segs[i] != segs[i].lstrip()]
        if ind:
            must_reject(pid, put(ind[0], segs[ind[0]].lstrip()), "indent removed")
        ph = t["placeholders"]
        if len(ph) >= 2 and ph[0] != ph[1]:
            must_reject(pid, o.replace(ph[0], "@@").replace(ph[1], ph[0]).replace("@@", ph[1]), "two placeholders swapped")
        if ph:
            must_reject(pid, o.replace(" " + ph[0], "", 1) if " " + ph[0] in o else o.replace(ph[0], "", 1), "placeholder deleted")
            src = next(i for i in text_lines if ph[0] in segs[i])
            dst = [i for i in text_lines if i != src]
            if dst and segs[src].strip() != ph[0]:
                lead = segs[src][:len(segs[src]) - len(segs[src].lstrip())]
                moved = segs[:]
                moved[src] = lead + " ".join(segs[src].replace(ph[0], "", 1).split())
                moved[dst[0]] = segs[dst[0]] + " " + ph[0]
                must_reject(pid, "\n".join(moved), f"placeholder moved from line {src} to line {dst[0]}")
        for k in ("quoted", "refs", "names"):
            if t[k]:
                must_reject(pid, o.replace(sorted(t[k])[0], "it"), f"{k} token removed")
        heads = [i for i in text_lines if HEAD.match(segs[i])]
        if heads:
            must_reject(pid, put(heads[0], "X" + segs[heads[0]]), "line head damaged")
    # 4. core sentences: the unchanged sentence is taken as is; planted faults are rejected
    for e in M["core"]:
        s, pid = e["text"], e["id"]
        if check_core(s, s, names):
            fails.append(f"{pid}: check_core(original, original) reports {check_core(s, s, names)}")
        must_accept(pid, s, s, "as is")
        must_accept(pid, s, "\n" + s.replace(" ", "  ", 1) + "  \n", "edge newlines and a double space")
        must_reject(pid, s.replace(" ", "\n", 1), "split over two lines")
        must_reject(pid, s + " [[S01]]", "placeholder inside")
        t = tokens(s, names)
        tok = sorted(t["quoted"] | t["refs"] | t["names"])
        if tok:
            must_reject(pid, s.replace(tok[0], "it"), "token removed")
    # 5. the first version's bug, on synthetic chunks (independent of the data): when only the condensed side is
    #    stripped, a chunk whose last segment is blank fails the line check; restore_blank_lines puts back exactly
    #    the original's edge blank lines
    if not check_chunk("A\n", "A", names):
        fails.append("synthetic: the old rstrip comparison is not reported as a line-count change")
    for o, new, want in (("A\n", "A", "A\n"), ("\n\nA\n\n", "A", "\n\nA\n\n"), ("\n\nA\n\n", "\nA\n\n\n", "\n\nA\n\n"),
                         ("A", "\n\nA\n", "A"), ("A\n\nB", "A\n\nB\n", "A\n\nB")):
        if restore_blank_lines(o, new) != want:
            fails.append(f"synthetic: restore_blank_lines({o!r}, {new!r}) gives {restore_blank_lines(o, new)!r}, not {want!r}")
    # 6. unchanged pieces rebuild v6 exactly; build() refuses one segment too few and one too many
    same = build(M, {}, {}, {})
    for k in ("phase1", "phase2"):
        if same[k] != (V6 / f"{k}.md").read_text(encoding="utf-8"):
            fails.append(f"{k}: build with no accepted piece differs from v6")
    c1 = next((c for c in chunks if len(c["text"].split("\n")) >= 2), None)
    if c1 is None:
        fails.append("no chunk with 2 or more segments to test build()'s count check")
    else:
        p1 = c1["id"].startswith("p1")
        for label, txt in (("one segment too few", "\n".join(c1["text"].split("\n")[:-1])), ("one segment too many", c1["text"] + "\nX")):
            try:
                build(M, {c1["id"]: txt} if p1 else {}, {} if p1 else {c1["id"]: txt}, {})
                fails.append(f"build() accepted {c1['id']} with {label}")
            except ValueError:
                pass
    return fails


def main(mode):
    sys.stdout.reconfigure(encoding="utf-8")
    M = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    fails = selftest(M)
    n = sum(len(M["chunks"][k]) for k in ("phase1", "phase2"))
    print(f"self-test ({n} chunks, {len(M['core'])} core sentences):", "PASS" if not fails else "FAIL")
    for f in fails:
        print("  " + f)
    if fails:
        sys.exit(1)
    if mode == "selftest":
        return
    R = json.loads((HERE / "condense_result.json").read_text(encoding="utf-8"))
    acc, log = accept(M, R)
    print("\n".join(log) or "no fallbacks")
    v6 = {k: (V6 / f"{k}.md").read_text(encoding="utf-8") for k in ("phase1", "phase2")}
    ok_all = True
    import chain as CH
    for ver, (u1, u2, uc) in plan(acc).items():
        texts = build(M, u1, u2, uc)
        d = LAB / "prompts" / ver
        files = {f"{k}.md": texts[k].replace("\n", "\r\n").encode("utf-8") for k in ("phase1", "phase2")}
        if mode == "verify":
            for f in COPIED:
                files[f] = (V6 / f).read_bytes()
            same = {f: (d / f).exists() and (d / f).read_bytes() == b for f, b in files.items()}
            ok = all(same.values())
            print(f"{ver}: built in memory; byte-identical to the files on disk: "
                  + ", ".join(f"{f} {s}" for f, s in same.items()) + f" -> {'OK' if ok else 'DIFFERS'}")
            ok_all &= ok
            continue
        d.mkdir(exist_ok=True)
        for f in COPIED:
            shutil.copyfile(V6 / f, d / f)
        for f, b in files.items():
            (d / f).write_bytes(b)
        ok = True
        for k in ("phase1", "phase2"):
            same_out = texts[k][texts[k].index("\nOUTPUT\n"):] == v6[k][v6[k].index("\nOUTPUT\n"):]
            ok &= same_out
        cores = {e["id"]: (uc.get(e["id"]) or e["text"]) for e in M["core"]}
        core_ok = all(texts["phase1"].count(s) == 1 and texts["phase2"].count(s) == 1 for s in cores.values())
        ok &= core_ok
        chk = bool(CK.check(ver, log=lambda *a: None))
        nf = CH.new_format(ver, 1) and CH.new_format(ver, 2)
        ok &= chk and nf
        w = {k: len(texts[k].split()) for k in texts}
        w6 = {k: len(v6[k].split()) for k in v6}
        s1, s2 = sha(CK.system(ver, 1)), sha(CK.system(ver, 2))
        print(f"{ver}: phase1 {w6['phase1']} -> {w['phase1']} words ({w['phase1'] - w6['phase1']:+d}), phase2 {w6['phase2']} -> {w['phase2']} "
              f"({w['phase2'] - w6['phase2']:+d}); shas {s1} / {s2}; OUTPUT unchanged {same_out}; core sentences once per file {core_ok}; "
              f"checker {chk}; new_format {nf} -> {'OK' if ok else 'FAILED'}")
        ok_all &= ok
    print("pieces used: phase1", len(acc["p1"]), "of", len(M["chunks"]["phase1"]), "| phase2", len(acc["p2"]), "of", len(M["chunks"]["phase2"]),
          "| core", len(acc["core"]), "of", len(M["core"]))
    if mode == "verify":
        ap = HERE / "accepted_pieces.json"
        same_acc = ap.exists() and json.loads(ap.read_text(encoding="utf-8")) == acc
        print(f"accepted_pieces.json matches a fresh accept(): {same_acc}")
        ok_all &= same_acc
        print("VERIFY: all four versions and accepted_pieces.json on disk match a fresh build" if ok_all
              else "VERIFY: DIFFERENCES FOUND")
    else:
        print("ALL CHECKS PASS" if ok_all else "CHECKS FAILED")
        json.dump({k: v for k, v in acc.items()}, open(HERE / "accepted_pieces.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if not ok_all:
        sys.exit(1)


if __name__ == "__main__":
    MODES = {(): "build", ("--selftest",): "selftest", ("--verify",): "verify"}
    if tuple(sys.argv[1:]) not in MODES:
        print("usage: python assemble_condensed.py [--selftest | --verify]   (no flag = build and write)", file=sys.stderr)
        sys.exit(2)
    main(MODES[tuple(sys.argv[1:])])
