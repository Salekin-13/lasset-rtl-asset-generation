"""Phase 1 probe for a target whose Phase 2 bar loses wherever Phase 1 named the element (core_clash.py). Does Phase 1
itself drop the barred information when its prompt holds only the core, or the core plus the target's Phase 1 wording?

Cells (luna, high; the target's 2 test modules; repeats r0-r1; Phase 1 only):
  P1_S0   phase1.md of v10 with every rule block removed (kept: the steps, "Describe a conceptual asset", Precedence,
          Reading a rule, OUTPUT)
  P1_S1   P1_S0 plus the target's own Phase 1 blocks, at their v10 place
  full    v10's stored Phase 1 replies r0-r2 (free)
Measure: of the target's consistently barred elements (its Phase 2 wording alone, ladder.bars), the share Phase 1 names
by name (concept information, Enters / Leaves Through) or by line (a held, entry or exit line; over-counts).
Self-test: the core keeps every non-rule line of v10's phase1.md in order, and S1 adds exactly the target's lines.
Length cells (decision D30): L1b = S1 + neutral VHDL notes of the 17 preceding rules' length, L2b = S1 + those 17 rules
archived, both right before the target. lselftest checks them through run()'s own dispatch (cells P123__P1_L1 / L2 of
2026-10-16 were sent as the bare core by a dispatch bug; see DECISION_LOG D39).

  python -B p1probe.py selftest <title prefix>
  <conda python> p1probe.py run "<target wording>" "<title prefix>"
  python -B p1probe.py measure "<target wording>" "<title prefix>"
  python -B p1probe.py lselftest "P1-23 P2" "Access command fields"
  <conda python> p1probe.py lrun "P1-23 P2" "Access command fields"      (at most 8 new calls)
  python -B p1probe.py lmeasure "P1-23 P2" "Access command fields"       (writes p1probe_P1-23_length.json)
"""
import json
import os
import re
import sys
import threading

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import ladder as L  # noqa: E402
import core_clash as CC  # noqa: E402
import run_a  # noqa: E402

V10D = LAB / "prompts" / "two_phase_v10"
CRLF, LF = chr(13) + chr(10), chr(10)
KEEP_TITLES = ("- Describe a conceptual asset", "- Precedence.", "- Reading a rule.")


def blocks(lines, end):
    """[(start, stop, title line)] of every titled rule block before the OUTPUT line."""
    out, i = [], 0
    while i < end:
        l = lines[i]
        if re.match(r"- [A-Z][^.]*\.", l) and not l.startswith(KEEP_TITLES):
            j = i + 1
            while j < end and lines[j].startswith("  "):
                j += 1
            out.append((i, j, l))
            i = j
        else:
            i += 1
    return out


def base_title(t):
    return re.sub(r" \([a-z]\)$", "", t[2:].split(".")[0])


def order():
    lines = (V10D / "phase1.md").read_text(encoding="utf-8").replace(CRLF, LF).split(LF)
    out = []
    for _, _, t in blocks(lines, lines.index("OUTPUT")):
        if base_title(t) not in out:
            out.append(base_title(t))
    return out


def build_keep(keep):
    """v10 phase1.md keeping only the rule blocks whose base title is in keep (plus the core)."""
    unknown = [t for t in keep if t not in order()]
    if unknown:                                   # 2026-10-16: an unknown title used to return the bare core silently
        raise ValueError(f"not a v10 Phase 1 rule title: {unknown}")
    return _keep_blocks(keep)


def _keep_blocks(keep):
    lines = (V10D / "phase1.md").read_text(encoding="utf-8").replace(CRLF, LF).split(LF)
    end = lines.index("OUTPUT")
    drop = set()
    for a, b, title in blocks(lines, end):
        if base_title(title) not in keep:
            drop |= set(range(a, b))
    return LF.join(l for i, l in enumerate(lines) if i not in drop)


def build_insert(target_title, extra_lines):
    """v10 phase1.md with only the target's rule blocks, and extra_lines inserted right before the target's first block
    (where the rules that precede it in v10's order stand)."""
    lines = (V10D / "phase1.md").read_text(encoding="utf-8").replace(CRLF, LF).split(LF)
    end = lines.index("OUTPUT")
    drop, first = set(), None
    for a, b, title in blocks(lines, end):
        if base_title(title) == target_title:
            first = a if first is None else first
        else:
            drop |= set(range(a, b))
    out = []
    for i, l in enumerate(lines):
        if i == first:
            out += extra_lines
        if i not in drop:
            out.append(l)
    return LF.join(out)


def length_cells(target_title):
    """L1: neutral filler of the 17 preceding rules' length; L2: those 17 rules, archived (decision D30)."""
    lines = (V10D / "phase1.md").read_text(encoding="utf-8").replace(CRLF, LF).split(LF)
    rest = [t for t in order() if t != target_title][:17]
    rule_lines = [l for a, b, t in blocks(lines, lines.index("OUTPUT")) if base_title(t) in rest for l in lines[a:b]]
    filler = (HERE / "filler_vhdl.txt").read_text(encoding="utf-8").strip().split(LF)
    filler = [("  " + l) if l.strip() else "" for l in filler]
    l1 = ["- Background on the language (general notes; they decide nothing in this task)."] + [l for l in filler if l]
    l2 = ["- Archived notes from an earlier version (not in force: they decide nothing in this task)."] + ["  " + l for l in rule_lines]
    # New cell names (2026-10-16): P123__P1_L1 / L2 were sent as the bare core (names_of wrapped these INSERT cells as
    # KEEP), so their stored replies are core-only repeats; they stay on disk as the record of that bug.
    return {"P123__P1_L1b": ("INSERT", l1), "P123__P1_L2b": ("INSERT", l2)}, len(" ".join(rule_lines).split())


def lselftest(t, target_title):
    """The length cells as run() builds them (names_of + cell_text, the same path): each holds the core, the target's
    blocks at their v10 place and its own extra lines right before them, and no other active rule. Negative control:
    the pre-fix dispatch (every stage cell wrapped as KEEP) gives the bare core, which this test rejects."""
    cells, n = length_cells(target_title)
    STAGE_CELLS.update(cells)
    lines = (V10D / "phase1.md").read_text(encoding="utf-8").replace(CRLF, LF).split(LF)
    tgt = [l for a, b, t in blocks(lines, lines.index("OUTPUT")) if base_title(t) == target_title for l in lines[a:b]]
    core, s1 = build(None), build(target_title)
    rest = [t for t in order() if t != target_title][:17]
    rule_lines = [l for a, b, t in blocks(lines, lines.index("OUTPUT")) if base_title(t) in rest for l in lines[a:b]]
    filler = [l for l in (HERE / "filler_vhdl.txt").read_text(encoding="utf-8").strip().split(LF) if l.strip()]
    ok, cases = True, names_of(t, target_title)
    for name, (_, extra) in cells.items():
        pf = cases[name]
        text = cell_text(target_title, pf).split(LF)
        old = _keep_blocks(pf)                          # the pre-fix path: build_keep(("INSERT", lines)), no title -> core
        active = {base_title(t) for _, _, t in blocks(text, text.index("OUTPUT"))} & set(order())
        i = text.index(tgt[0]) if tgt[0] in text else None
        checks = {
            "not the bare core": LF.join(text) != core,
            "target blocks present, in order, at the end of the insert": i is not None and text[i:i + len(tgt)] == tgt,
            "extra lines right before the target": i is not None and text[i - len(extra):i] == extra,
            "only the target is an active rule": active == {target_title},
            "every core line kept, in order": [l for l in text if l in set(core.split(LF))] == core.split(LF),
            "length = S1 + the extra lines": len(text) == len(s1.split(LF)) + len(extra),
            "negative control: pre-fix text is the core": old == core and old != LF.join(text),
        }
        if name.endswith("L1b"):
            checks["L1: every filler line, indented"] = extra[1:] == ["  " + l for l in filler]
        else:
            checks["L2: the 17 rules' lines, indented once more"] = extra[1:] == ["  " + l for l in rule_lines]
        bad = [k for k, v in checks.items() if not v]
        ok &= not bad
        print(f"lselftest {name}: {len(LF.join(text).split())} words (core {len(core.split())}, S1 {len(s1.split())}), "
              f"extra {len(extra)} lines; {'PASS' if not bad else 'FAIL ' + str(bad)}")
    print(f"17 rules' words {n}")
    return ok


STAGE_CELLS = {}          # name -> keep list (filled by plan_stages)


def plan_stages(target_title, compatible):
    rest = [t for t in order() if t != target_title]
    k1, k2 = round(len(rest) / 3), round(2 * len(rest) / 3)
    base = "P123"
    STAGE_CELLS.update({f"{base}__P1_S2": [target_title] + compatible,
                        f"{base}__P1_pre{k1}": [target_title] + rest[:k1],
                        f"{base}__P1_pre{k2}": [target_title] + rest[:k2]})
    return STAGE_CELLS


def build(prefix=None):
    lines = (V10D / "phase1.md").read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    end = lines.index("OUTPUT")
    drop = set()
    for a, b, title in blocks(lines, end):
        if prefix and title.startswith("- " + prefix):
            continue
        drop |= set(range(a, b))
    return "\n".join(l for i, l in enumerate(lines) if i not in drop)


def selftest(prefix):
    v10 = (V10D / "phase1.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    core, s1 = build(None), build(prefix)
    lines = v10.split("\n")
    rule_lines = {i for a, b, _ in blocks(lines, lines.index("OUTPUT")) for i in range(a, b)}
    kept = [l for i, l in enumerate(lines) if i not in rule_lines]
    ok = core.split("\n") == kept and len(s1) > len(core) and all(l in s1 for l in core.split("\n"))
    tgt = [l for a, b, t in blocks(lines, lines.index("OUTPUT")) if t.startswith("- " + prefix) for l in lines[a:b]]
    ok &= bool(tgt) and all(l in s1.split("\n") for l in tgt) and len(s1.split("\n")) == len(core.split("\n")) + len(tgt)
    print(f"p1probe self-test ({prefix}): core {len(core.split())} words, S1 +{len(s1.split()) - len(core.split())} words; {'PASS' if ok else 'FAIL'}")
    return ok


def cell_version(name, text):
    d = LAB / "prompts" / "diag_v10" / name
    d.mkdir(parents=True, exist_ok=True)
    crlf = b"\r\n" in (V10D / "phase1.md").read_bytes()
    for f in ("common.md", "phase2.md", "phase1_user.md", "phase2_user.md"):
        (d / f).write_bytes((V10D / f).read_bytes())
    data = (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
    if (d / "phase1.md").exists() and (d / "phase1.md").read_bytes() != data:
        raise RuntimeError(f"{d} holds another phase1.md")
    (d / "phase1.md").write_bytes(data)
    v = f"diag_v10/{name}"
    if not CK.check(v, log=lambda *a: None):
        raise RuntimeError("prompt check failed")
    return v


def names_of(t, prefix):
    base = t.split()[0].replace("-", "")
    out = {f"{base}__P1_S0": None, f"{base}__P1_S1": prefix}
    # a keep list becomes ("KEEP", titles); a cell already tagged ("INSERT", lines) stays as it is (2026-10-16 fix:
    # wrapping it as KEEP sent the length cells as the bare core)
    out.update({k: (v if isinstance(v, tuple) else ("KEEP", v)) for k, v in STAGE_CELLS.items()})
    return out


def cell_text(prefix, pf):
    """phase1.md text of one cell, as run() sends it: None -> the core; a title prefix -> core + that target's blocks;
    ("KEEP", titles) -> core + those rule blocks; ("INSERT", lines) -> core + the target, the lines right before it."""
    if pf is None or isinstance(pf, str):
        return build(pf)
    if pf[0] == "INSERT":
        return build_insert(prefix, pf[1])
    if pf[0] == "KEEP":
        return build_keep(pf[1])
    raise ValueError(f"unknown cell kind {pf[0]!r}")


def run(t, prefix, max_new=None):
    from concurrent.futures import ThreadPoolExecutor
    plan = json.loads((HERE / "plan_round1.json").read_text(encoding="utf-8"))
    mods = plan[t]["modules"]
    jobs = []
    stop = CH._new_run_flag()
    for name, pf in names_of(t, prefix).items():
        v = cell_version(name, cell_text(prefix, pf))
        L.track_folders([name])
        for rep in (0, 1):
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            call = CH.openai(MODEL, EFFORT, out=out, poll=5)
            for m in mods:
                jobs.append((v, m, out, call))
    spent = run_a.spent(log=lambda *a: None)
    new = sum(1 for _, m, out, _ in jobs if not (out / "phase1" / f"{m}.json").exists())
    print(f"{len(jobs)} Phase 1 cells x modules, {new} to send (about USD {new * 0.02:.2f}); spent so far USD {spent:.2f}")
    if max_new is not None and new > max_new:
        sys.exit(f"{new} calls to send, more than the {max_new} approved; nothing sent")

    def one(j):
        threading.current_thread().lab_stop = stop
        v, m, out, call = j
        r = CH._ask(call, CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                    lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                    adapt=CH.from_format_phase1)
        return r.get("problems")
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        res = list(pool.map(one, jobs))
    print("done", len(res), "; spent after USD", round(run_a.spent(log=lambda *a: None), 2))


def p1_named(rec, m, e):
    cons = CH.phase1_concepts(rec.get("reply")) or []
    named, lines = set(), set()
    txt = " ".join(str(c.get("information") or "") + " " + str(c.get("concept") or "") for c in cons)
    for c in cons:
        named |= {x for x in CH.as_list(c.get("enters through")) + CH.as_list(c.get("leaves through")) if isinstance(x, str)}
        lines |= set(CH.as_list(c.get("held lines")) + CH.as_list(c.get("entry lines")) + CH.as_list(c.get("exit lines")))
    if e in named or re.search(r"(?<![\w.])" + re.escape(e) + r"(?!\w)", txt):
        return "named"
    return "line-linked" if CC.occ(m, e) & lines else "not in Phase 1"


def measure(t, prefix, out_name=None):
    from collections import Counter
    plan = json.loads((HERE / "plan_round1.json").read_text(encoding="utf-8"))
    mods = plan[t]["modules"]
    B = L.bars(t, mods)
    out = {}
    cells = [("full v10", None)] + list(names_of(t, prefix).items())
    for name, _ in cells:
        c = Counter()
        for m in mods:
            for rep in ((0, 1, 2) if name == "full v10" else (0, 1)):
                f = (CH.run_dir(V10, MODEL, rep, EFFORT) if name == "full v10" else L.cell_dir(name, rep)) / "phase1" / f"{m}.json"
                if not f.exists():
                    c["missing"] += 1
                    continue
                rec = json.loads(f.read_text(encoding="utf-8"))
                for e in B[m]:
                    c[p1_named(rec, m, e)] += 1
        out[name] = dict(c)
        n = sum(v for k, v in c.items() if k != "missing")
        print(f"{name:22s} of {n} (element, repeat) pairs: named {c['named']}, line-linked {c['line-linked']}, not in Phase 1 {c['not in Phase 1']}"
              + (f"; missing {c['missing']}" if c['missing'] else ""))
    (HERE / (out_name or f"p1probe_{t.split()[0]}.json")).write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "selftest":
        sys.exit(0 if selftest(sys.argv[2]) else 1)
    elif cmd == "lselftest":
        sys.exit(0 if lselftest(sys.argv[2], sys.argv[3]) else 1)
    elif cmd in ("lrun", "lmeasure"):
        if not lselftest(sys.argv[2], sys.argv[3]):  # nothing is sent or measured if the length cells are wrong
            sys.exit("length-cell self-test FAIL")
        if cmd == "lrun":
            run(sys.argv[2], sys.argv[3], max_new=8)
        else:                                        # the 2026-10-16 L1/L2 result stays in p1probe_P1-23.json
            measure(sys.argv[2], sys.argv[3], out_name=f"p1probe_{sys.argv[2].split()[0]}_length.json")
    elif cmd in ("run", "measure", "stages"):
        if len(sys.argv) > 4:                     # stage cells: compatible titles, comma separated
            plan_stages(sys.argv[3], [x for x in sys.argv[4].split(",") if x])
        if cmd == "stages":
            for k, v in STAGE_CELLS.items():
                print(k, len(build_keep(v).split()), "words", v)
        elif cmd == "run":
            run(sys.argv[2], sys.argv[3])
        else:
            measure(sys.argv[2], sys.argv[3])
