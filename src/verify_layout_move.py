"""Check that the layout move kept every pre-registered pin verifiable.

Before any row is read:
  - the tag prereg-layout-before must point at commit TAG_COMMIT, and that commit must be an ancestor of HEAD;
  - HELDOUT_PREREG.md and HELDOUT_CHECK_PREREG.md must be byte-identical to the tag; lasset_layer/PREREG.md may only
    gain an appended amendment that starts with the layout-move marker, and each row of that amendment must equal
    the hash of its file at HEAD;
  - no pinned item may have uncommitted changes (the repo's own verifiers hash the working tree).
Then, for each row of the three pin tables as they stand at the tag:
  1. the pinned bytes at the tag still hash to the registered sha12 (the pin held before the move);
  2. the same item at its new path either hashes to the same sha12 (moved byte for byte), or
  3. is a Python file whose new bytes equal the tagged bytes with some string literals rewritten, where every
     rewritten literal is the old literal with a moved root name prefixed by its new folder (data/, src/, runs/).
     Outside string literals nothing may differ: not code, not comments, not whitespace, not line endings. Inside an
     f-string, the expression tokens must be identical; only its literal text may gain a prefix.
Folders are hashed with each table's own rule (lasset_layer skips __pycache__; the two held-out verifiers do not).
This proves that nothing but the move's prefixes changed. It does not prove that every needed prefix was added: that
was measured by re-running the live notebooks in both layouts (logs/LAYOUT.md).
Prints one line per row and exits 1 on any failure. Run from the repo root:  python src/verify_layout_move.py
Needs Python 3.12 or later (f-string tokens). No file is written."""
from __future__ import annotations

import hashlib, io, re, subprocess, sys, tokenize

TAG = "prereg-layout-before"
TAG_COMMIT = "5ebdfa0693761861f7fa39b7980ef1eeae03ac33"
MARKER = b"<!-- layout-move -->"
TABLES = {"assetgen_meta/lasset_layer/PREREG.md": True,          # value: skip __pycache__ when hashing a folder
          "assetgen_meta/HELDOUT_PREREG.md": False,
          "assetgen_meta/prompt_opt/HELDOUT_CHECK_PREREG.md": False}
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(?:(bytes|text|dir)\s*\|\s*)?`([0-9a-f]{12})`\s*\|", re.M)
DATA = ["RTL_data", "RTL_heldout", "ground_truth", "LAsset_initial_results", "parsed_tuning18", "parsed_heldout26", "parsed_heldout_raw"]
SRC = ["diagnose_step1", "eval_assets", "gt_extract", "icl_asset_examples", "icl_examples_0", "icl_examples_01", "icl_examples_01b",
       "icl_examples_01b_noparse", "icl_examples_01b_nosum", "icl_examples_01b_ot", "icl_examples_02", "parse_audit", "parse_roles",
       "parse_v3", "prompts", "prompts_parse_v2", "prompts_parse_v3", "prompts_v2", "rtl_parse", "stage_a", "stage_ceilings",
       "verify_icl", "vhdl_occurrence_context"]
MOVE = {**{d: "data/" + d for d in DATA}, **{m + ".py": "src/" + m + ".py" for m in SRC}}
START = r"(?<![\w/.\\-])"                       # a name that starts a path, not one inside another folder's path
RUNS_RX = re.compile(START + r"(assets_(?:tuning18|heldout26|opt)\w*|\{stem\}_)")
MOVED_RUNS: set[str] = set()                    # the run folders that moved, read from the tag in main()


def _runs(m):
    """A run name gains runs/ only if it is one of the moved folders, or a template that continues with { or *."""
    name, nxt = m.group(1), m.string[m.end():m.end() + 1]
    return "runs/" + name if name == "{stem}_" or nxt in ("{", "*") or name in MOVED_RUNS else name


REWRITES = [(re.compile(START + r"(" + "|".join(DATA) + r")(?![\w.-])"), r"data/\1"),
            (re.compile(START + r"((?:" + "|".join(SRC) + r")\.py)(?![\w.-])"), r"src/\1"),
            (RUNS_RX, _runs)]


def git(*a, binary=False):
    r = subprocess.run(["git", *a], capture_output=True)
    if r.returncode:
        raise SystemExit(f"git {' '.join(a)}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout if binary else r.stdout.decode("utf-8")


def new_path(p):
    for old, new in MOVE.items():
        if p == old or p.startswith(old + "/"):
            return new + p[len(old):]
    if re.fullmatch(r"assets_\w+(/.*)?", p) and p.split("/")[0] in MOVED_RUNS:
        return "runs/" + p
    return p


def blobs(rev, p):
    """{relative path: bytes} of every tracked file at rev under p (a file gives {'': bytes})."""
    out = {}
    for line in git("ls-tree", "-r", "-z", rev, "--", p).split("\0"):
        if line:
            meta, path = line.split("\t", 1)
            out[path[len(p):].lstrip("/")] = git("cat-file", "blob", meta.split()[2], binary=True)
    return out


def sha12(files, kind, skip_pycache):
    if kind == "text":
        b = files[""].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        return hashlib.sha256(b).hexdigest()[:12]
    if list(files) == [""]:
        return hashlib.sha256(files[""]).hexdigest()[:12]
    h = hashlib.sha256()
    for rel in sorted(files):
        if skip_pycache and "__pycache__" in rel.split("/"):
            continue
        h.update(rel.encode("utf-8") + b"\0" + files[rel] + b"\0")
    return h.hexdigest()[:12]


def rewrite(lit):
    for rx, rep in REWRITES:
        lit = rx.sub(rep, lit)
    return lit


def units(src: str):
    """Tokens; each f-string becomes one unit (its whole source span) carrying its non-literal sub-tokens."""
    toks = list(tokenize.generate_tokens(io.StringIO(src, newline="").readline))
    lines = src.splitlines(keepends=True)
    FS, FE, FM = tokenize.FSTRING_START, tokenize.FSTRING_END, tokenize.FSTRING_MIDDLE
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t.type == FS:
            depth, j = 0, i
            while True:
                depth += toks[j].type == FS
                depth -= toks[j].type == FE
                if depth == 0:
                    break
                j += 1
            e = toks[j]
            text = lines[t.start[0] - 1][t.start[1]:e.end[1]] if t.start[0] == e.end[0] else "".join(x.string for x in toks[i:j + 1])
            code = tuple((x.type, x.string) for x in toks[i + 1:j] if x.type != FM)
            out.append(("LIT", text, t.start, e.end, code))
            i = j + 1
            continue
        out.append(("LIT" if t.type == tokenize.STRING else tokenize.tok_name[t.type], t.string, t.start, t.end, ()))
        i += 1
    return out


def literal_only(old: bytes, new: bytes):
    """-> (ok, [(line, old literal, new literal)], reason). ok only if new == old with allowed literal rewrites."""
    try:
        o, n = old.decode("utf-8"), new.decode("utf-8")
        to, tn = units(o), units(n)
    except (tokenize.TokenError, SyntaxError, UnicodeDecodeError) as e:
        return False, [], f"cannot tokenize ({e})"
    if len(to) != len(tn):
        return False, [], f"token count {len(to)} -> {len(tn)}"
    lines, edits, rebuilt = o.splitlines(keepends=True), [], {}
    for a, b in zip(to, tn):
        if a[:2] == b[:2]:
            continue
        if a[0] != b[0] or a[0] != "LIT":
            return False, edits, f"line {a[2][0]}: non-literal token changed ({a[1]!r} -> {b[1]!r})"
        if a[4] != b[4]:
            return False, edits, f"line {a[2][0]}: code inside an f-string changed ({a[1]!r} -> {b[1]!r})"
        if b[1] != rewrite(a[1]):
            return False, edits, f"line {a[2][0]}: literal {a[1]!r} -> {b[1]!r} is not a move rewrite"
        if a[2][0] != a[3][0]:
            return False, edits, f"line {a[2][0]}: multi-line literal changed"
        edits.append((a[2][0], a[1], b[1]))
        rebuilt.setdefault(a[2][0], []).append((a[2][1], a[3][1], b[1]))
    for ln, subs in rebuilt.items():           # old text with only these literals replaced must equal the new text
        s = lines[ln - 1]
        for c0, c1, txt in sorted(subs, reverse=True):
            s = s[:c0] + txt + s[c1:]
        lines[ln - 1] = s
    if "".join(lines) != n:
        return False, edits, "bytes outside the rewritten literals differ"
    return True, edits, ""


def selftest():
    cases = [(b'x = ROOT / "RTL_data"\n', b'x = ROOT / "data/RTL_data"\n', True),
             (b'p = ROOT / f"{stem}_{v}_r{k}"\n', b'p = ROOT / f"runs/{stem}_{v}_r{k}"\n', True),
             (b'a, b = ROOT / "RTL_data", BPA / "data/RTL_data"\n', b'a, b = ROOT / "data/RTL_data", BPA / "data/RTL_data"\n', True),
             (b'r = "assets_opt_v1_r0"\n', b'r = "runs/assets_opt_v1_r0"\n', True),                    # a moved run folder
             (b'g = f"assets_tuning18_{v}_r*"\n', b'g = f"runs/assets_tuning18_{v}_r*"\n', True),        # a run template
             (b'n = 3\n', b'n = 4\n', False),                                                         # code changed
             (b'x = ROOT / "RTL_data"\n', b'x = ROOT / "data/RTL_heldout"\n', False),                 # wrong target
             (b'x = 1  # RTL_data\n', b'x = 1  # data/RTL_data\n', False),                            # comment changed
             (b'x = ROOT / "RTL_data"\n', b'x = ROOT  /  "data/RTL_data"\n', False),                  # spacing changed
             (b'x = ROOT / "RTL_data"\r\n', b'x = ROOT / "data/RTL_data"\n', False),                  # line ending changed
             (b'x = str(ROOT)\n', b'x = str(ROOT / "src")\n', False),                                 # path expression, not literal
             (b'p = f"{RTL_data}/x.vhd"\n', b'p = f"{data/RTL_data}/x.vhd"\n', False),                # code inside an f-string
             (b"p = f\"{d['RTL_data']}\"\n", b"p = f\"{d['data/RTL_data']}\"\n", False),              # a key inside an f-string
             (b'x = "RTL_data.bak"\n', b'x = "data/RTL_data.bak"\n', False),                          # not the moved folder
             (b'r = "assets_tuning18_m55eea9s0_r0"\n', b'r = "runs/assets_tuning18_m55eea9s0_r0"\n', False)]  # a run that did not move
    ok = all(literal_only(a, b)[0] is want for a, b, want in cases)
    # hand-read line: eval_assets.py line 25 at the tag
    tagged = blobs(TAG_COMMIT, "eval_assets.py")[""].decode("utf-8").splitlines()[24]
    ok &= tagged == 'GT_DIR = Path("ground_truth")' and rewrite('"ground_truth"') == '"data/ground_truth"'
    return ok, len(cases)


def preflight() -> list[str]:
    """The tag, the pre-registration files at HEAD, and a clean working tree under every pinned item."""
    bad = []
    if git("rev-parse", f"{TAG}^{{commit}}").strip() != TAG_COMMIT:
        bad.append(f"tag {TAG} does not point at {TAG_COMMIT}")
    if subprocess.run(["git", "merge-base", "--is-ancestor", TAG_COMMIT, "HEAD"]).returncode:
        bad.append(f"{TAG_COMMIT} is not an ancestor of HEAD")
    for table in TABLES:
        old, new = blobs(TAG_COMMIT, table)[""], blobs("HEAD", table).get("")
        if new is None:
            bad.append(f"{table} is missing at HEAD")
        elif table.endswith("lasset_layer/PREREG.md"):
            tail = new[len(old):]
            if not new.startswith(old) or (tail and not tail.lstrip(b"\r\n").startswith(MARKER)):
                bad.append(f"{table}: HEAD is not the tagged file plus an appended amendment")
            for p, _kind, want in ROW.findall(tail.decode("utf-8")):
                if sha12(blobs("HEAD", p), "bytes", True) != want:
                    bad.append(f"{table} amendment row {p}: {want} is not its hash at HEAD")
        elif new != old:
            bad.append(f"{table} differs from the tag")
    pinned = sorted({new_path(r[0]) for t in TABLES for r in ROW.findall(git("show", f"{TAG_COMMIT}:{t}"))})
    dirty = git("status", "--porcelain", "--untracked-files=all", "--ignored", "--", *pinned).strip()
    if dirty:
        bad.append("uncommitted or untracked files under pinned items:\n  " + dirty.replace("\n", "\n  "))
    return bad


def main():
    MOVED_RUNS.update(p for p in git("ls-tree", "-d", "--name-only", TAG_COMMIT).split("\n") if p.startswith("assets_"))
    ok, n_cases = selftest()
    if not ok:
        print("self-test FAIL: nothing below is reported")
        return 1
    print(f"self-test PASS ({n_cases} planted cases, 1 hand-read line); {len(MOVED_RUNS)} moved run folders")
    pre = preflight()
    if pre:
        print("preflight FAIL: nothing below is reported\n" + "\n".join(pre))
        return 1
    print(f"preflight PASS: tag at {TAG_COMMIT[:12]} and an ancestor of HEAD; pre-registrations at HEAD as registered; "
          "no uncommitted changes under pinned items")
    fails, n = 0, 0
    for table, skip_pycache in TABLES.items():
        for path, kind, want in ROW.findall(git("show", f"{TAG_COMMIT}:{table}")):
            n += 1
            kind = kind or "bytes"
            old = blobs(TAG_COMMIT, path)
            new_p = new_path(path)
            new = blobs("HEAD", new_p)
            before = sha12(old, kind, skip_pycache) if old else "missing"
            after = sha12(new, kind, skip_pycache) if new else "missing"
            if before != want:
                status, fails = f"FAIL: the pin did not hold at {TAG}", fails + 1
            elif after == want:
                status = "moved, bytes unchanged" if new_p != path else "unchanged"
            elif list(old) == [""] and list(new) == [""] and path.endswith(".py"):
                ok, edits, why = literal_only(old[""], new[""])
                status = f"path literals only: {len(edits)} rewritten on lines {sorted({e[0] for e in edits})}" if ok else f"FAIL: {why}"
                fails += not ok
            else:
                status, fails = "FAIL: changed and not a Python file", fails + 1
            print(f"{table.split('/')[-1]:24s} {path[:62]:62s} -> {new_p[:67]:67s} {want} {after} {status}")
    print(f"{n} rows, {fails} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
