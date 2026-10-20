"""Does fewer rule words help? (user 2026-10-16: "Build the cell with the same 17 rules cut to about half their words
(keep scope and outcome), show me the word count and the exact cut before sending, then run 4 luna calls and read it
against the readings you set.")

Cell P123__P1_pre17half = cell P123__P1_pre17 (v10 Phase 1 core + Access command fields + the 17 rules before it in v10's
order, all in force) with each of the 17 rules cut to its scope and outcome. Access command fields and the core are
unchanged. Only the target is scored, so the cut need not keep the 17 rules' meaning.
Cut (mechanical):
  - rules written in labelled parts: keep the title line and every "Scope:" / "- Scope:" / "Outcome:" line; drop every
    "Criteria", "Exceptions" and "Evidence" line (any other line stops the build);
  - the 5 rules written as one paragraph: keep the sentences listed in PROSE_KEEP (scope and outcome sentences, read by
    hand; the dropped ones are further cases, exceptions or evidence). Held outcomes is one sentence: its clauses
    (split at "; ") stand in for sentences, and its scope is the text before the first colon.
Measure (p1probe.measure's): of Access command fields' consistently barred signals in cpu_regfile and cpu_alu (ladder.bars
  "P1-23 P2"), the (signal, repeat) pairs Phase 1 names (p1probe.p1_named == "named"), r0-r1, 22 pairs.
Readings (set 2026-10-16 before this cell was built; pre17 = 11/22 named): at most 5/22 named -> word count matters,
  shortening is worth the work; 9/22 or more -> words are not the lever (rule count or content is); 6-8/22 -> no answer.
  Resolution: in cpu_regfile a reply breaks all or none of its 6 signals (stored cells), so the 22 pairs behave like
  about 4 replies.
Self-test (nothing is sent if it fails): every kept piece is verbatim v10 text, in v10's order; the target's blocks and
  every core line are unchanged; the active rules are exactly the target and the 17; each of the 17 keeps its title, a
  scope and an outcome; negative control: the uncut pre17 text fails the length check.

  python -B p1half.py show           (writes p1half_cut.md: kept and dropped text per rule; sends nothing)
  <conda python> p1half.py run       (at most 4 new calls)
  python -B p1half.py measure        (writes p1half.json)
  <conda python> p1half.py repeats   (r2-r3 of pre17 and pre17half; at most 8 new calls)
  python -B p1half.py measure4       (both cells over r0-r3; writes p1half_4reps.json)
"""
import json
import os
import re
import sys
import threading

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import ladder as L  # noqa: E402
import p1probe as P  # noqa: E402
import run_a  # noqa: E402

T, TARGET, CELL = "P1-23 P2", "Access command fields", "P123__P1_pre17half"
SPL = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"(])")
# sentence numbers (1-based) kept for the paragraph rules; Held outcomes: 0 = its scope (before the first colon), then clauses
PROSE_KEEP = {
    "Build-time values": [1, 3],                 # 1 scope + outcome; 3 what to name instead. Dropped: 2 (a second case)
    "Decided-on instance outputs": [1],          # 1 scope + outcome. Dropped: 2 (where to hold it: evidence)
    "Held outcomes, addresses and settings": [0, 4],   # scope; clause 4 the outcome. Dropped: the three cases (clauses 1-3)
    "Instance-driven records": [1, 2],           # 1 scope + outcome; 2 outcome. Dropped: 3 (a port case), 4, 5 (evidence), 6 (judged as usual)
    "Register read-back": [1, 3, 4],             # 1 case 1 scope + outcome; 3 case 2 scope; 4 case 2 outcome. Dropped: 2, 5 (evidence), 6 (judged as usual)
}
KEEP_LABELS = ("Scope:", "- Scope:", "Outcome:")
DROP_LABELS = ("Criteria", "Exceptions", "Evidence")


def v10_lines():
    return (P.V10D / "phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF).split(P.LF)


def rest17():
    return [t for t in P.order() if t != TARGET][:17]


def units(title, line):
    """The paragraph rule's sentences (Held outcomes: scope, then its '; ' clauses), without the '- Title.' head."""
    body = line[len("- " + title + "."):].strip()
    if title.startswith("Held outcomes"):
        head, tail = body.split(":", 1)
        return [head + ":"] + [c.strip() for c in tail.split("; ")]          # unit 0 = scope, then clauses 1..4
    return [None] + SPL.split(body)                                         # 1-based


def cut_block(title, blines):
    """-> (kept lines, dropped pieces) for one rule block."""
    if len(blines) == 1 and not re.match(r"- [^.]*\.\s*$", blines[0]):      # a paragraph rule
        u = units(title, blines[0])
        keep = PROSE_KEEP[title]
        if title.startswith("Held outcomes"):
            kept = u[0] + " " + "; ".join(u[k] for k in keep if k)
            dropped = [u[k] for k in range(1, len(u)) if k not in keep]
        else:
            kept = " ".join(u[k] for k in keep)
            dropped = [u[k] for k in range(1, len(u)) if k not in keep]
        return ["- " + title + ". " + kept], dropped
    kept, dropped = [blines[0]], []
    for l in blines[1:]:
        s = l.strip()
        if s.startswith(KEEP_LABELS):
            kept.append(l)
        elif s.startswith(DROP_LABELS):
            dropped.append(s)
        else:
            raise ValueError(f"{title}: unclassified line {s[:60]!r}")
    return kept, dropped


def build():
    lines = v10_lines()
    end = lines.index("OUTPUT")
    rest = rest17()
    out, report, i = [], {}, 0
    bl = {a: (b, t) for a, b, t in P.blocks(lines, end)}
    while i < len(lines):
        if i in bl:
            b, t = bl[i]
            bt = P.base_title(t)
            if bt == TARGET:
                out += lines[i:b]
            elif bt in rest:
                k, d = cut_block(bt, lines[i:b])
                out += k
                r = report.setdefault(bt, {"kept": [], "dropped": [], "words before": 0})
                r["kept"] += k
                r["dropped"] += d
                r["words before"] += len(" ".join(lines[i:b]).split())
            i = b
            continue
        out.append(lines[i])
        i += 1
    for r in report.values():
        r["words after"] = len(" ".join(r["kept"]).split())
    return P.LF.join(out), report


def selftest(text, report, log=print):
    lines = v10_lines()
    end = lines.index("OUTPUT")
    v10 = P.LF.join(lines)
    core = P.build(None).split(P.LF)
    tl = text.split(P.LF)
    rest = rest17()
    tgt = [l for a, b, t in P.blocks(lines, end) if P.base_title(t) == TARGET for l in lines[a:b]]
    flat = re.sub(r"\s+", " ", v10)
    pieces = [p for r in report.values() for k in r["kept"] for p in re.split(r"(?<=[.:;])\s+", k.strip()) if p]
    active = [P.base_title(t) for _, _, t in P.blocks(tl, tl.index("OUTPUT"))]
    order17 = [t for t in dict.fromkeys(active) if t != TARGET]
    w17b = sum(r["words before"] for r in report.values())
    w17a = sum(r["words after"] for r in report.values())
    pre17 = P.build_keep([TARGET] + rest)
    checks = {
        "every kept piece is v10 text": all(re.sub(r"\s+", " ", p) in flat for p in pieces),
        "the 17 rules in v10 order": order17 == rest,
        "target blocks unchanged and contiguous": any(tl[i:i + len(tgt)] == tgt for i in range(len(tl))),
        "every core line kept, in order": [l for l in tl if l in set(core)] == core,
        "active rules = target + the 17": set(active) == set(rest) | {TARGET},
        "each of the 17 keeps a scope and an outcome": all(
            len(r["kept"]) >= 1 and (any(x.strip().startswith(("Scope:", "- Scope:")) for x in r["kept"])
                                     or bt in PROSE_KEEP) for bt, r in report.items()),
        "the 17 rules cut to 35-60% of their words": 0.35 <= w17a / w17b <= 0.60,
        "no Criteria / Exceptions / Evidence line left in the 17": not any(
            l.strip().startswith(DROP_LABELS) for a, b, t in P.blocks(tl, tl.index("OUTPUT")) if P.base_title(t) != TARGET
            for l in tl[a:b]),
        "negative control: uncut pre17 is longer than this cell": len(pre17.split()) > len(text.split()),
    }
    bad = [k for k, v in checks.items() if not v]
    log(f"p1half self-test: 17 rules {w17b} -> {w17a} words ({w17a / w17b:.0%}); cell {len(text.split())} words "
        f"(pre17 {len(pre17.split())}); {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def show():
    text, report = build()
    ok = selftest(text, report)
    md = ["# The half-length cut of the 17 rules (cell P123__P1_pre17half)", "",
          "Made by p1half.py. Kept text is verbatim v10 phase1.md; dropped pieces are listed under each rule.", "",
          "| Rule | Words before | Words after | Kept |", "|---|---|---|---|"]
    for bt in rest17():
        r = report[bt]
        md.append(f"| {bt} | {r['words before']} | {r['words after']} | {r['words after'] / r['words before']:.0%} |")
    tb = sum(r["words before"] for r in report.values())
    ta = sum(r["words after"] for r in report.values())
    md += [f"| **all 17** | **{tb}** | **{ta}** | **{ta / tb:.0%}** |", ""]
    for bt in rest17():
        r = report[bt]
        md += [f"## {bt}", "", "Kept:", "", "```"] + r["kept"] + ["```", "", "Dropped:", ""]
        md += [f"- {d}" for d in r["dropped"]] + [""]
    (HERE / "p1half_cut.md").write_text(P.LF.join(md), encoding="utf-8")
    print("wrote p1half_cut.md")
    return ok, text


def run():
    from concurrent.futures import ThreadPoolExecutor
    ok, text = show()
    if not ok:
        sys.exit("self-test FAIL; nothing sent")
    mods = json.loads((HERE / "plan_round1.json").read_text(encoding="utf-8"))[T]["modules"]
    v = P.cell_version(CELL, text)
    L.track_folders([CELL])
    stop = CH._new_run_flag()
    jobs = []
    for rep in (0, 1):
        out = L.cell_dir(CELL, rep)
        out.mkdir(parents=True, exist_ok=True)
        call = CH.openai(MODEL, EFFORT, out=out, poll=5)
        jobs += [(m, out, call) for m in mods if not (out / "phase1" / f"{m}.json").exists()]
    spent = run_a.spent(log=lambda *a: None)
    print(f"{len(jobs)} calls to send (about USD {len(jobs) * 0.022:.2f}); spent so far USD {spent:.2f}")
    if len(jobs) > 4:
        sys.exit("more than the 4 approved calls; nothing sent")

    def one(j):
        threading.current_thread().lab_stop = stop
        m, out, call = j
        return CH._ask(call, CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                       lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                       adapt=CH.from_format_phase1).get("problems")
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        res = list(pool.map(one, jobs))
    print("done", len(res), "; problems", res, "; spent after USD", round(run_a.spent(log=lambda *a: None), 2))


PRE17 = "P123__P1_pre17"


def run_repeats(reps=(2, 3), cap=8):
    """User 2026-10-16: repeats r2 and r3 of P123__P1_pre17 and P123__P1_pre17half (8 calls). Each cell's prompt folder
    must equal its builder and its stored r0-r1 replies must carry today's system sha; nothing is sent otherwise."""
    from concurrent.futures import ThreadPoolExecutor
    ok, _ = show()
    if not ok:
        sys.exit("self-test FAIL; nothing sent")
    mods = json.loads((HERE / "plan_round1.json").read_text(encoding="utf-8"))[T]["modules"]
    built = {PRE17: P.build_keep([TARGET] + rest17()), CELL: build()[0]}
    jobs, stop = [], CH._new_run_flag()
    for name, text in built.items():
        v = f"diag_v10/{name}"
        disk = (P.LAB / "prompts" / v / "phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF)
        sha = CH.sha12(CK.system(v, 1))
        stored = {json.loads(f.read_text(encoding="utf-8"))["system sha"] for r in (0, 1)
                  for f in (L.cell_dir(name, r) / "phase1").glob("*.json")}
        if disk != text or stored != {sha}:
            sys.exit(f"{name}: prompt differs from its builder or from the stored replies; nothing sent")
        L.track_folders([name])
        for rep in reps:
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            call = CH.openai(MODEL, EFFORT, out=out, poll=5)
            jobs += [(v, m, out, call) for m in mods if not (out / "phase1" / f"{m}.json").exists()]
    spent = run_a.spent(log=lambda *a: None)
    print(f"{len(jobs)} calls to send (about USD {len(jobs) * 0.018:.2f}); spent so far USD {spent:.2f}")
    if len(jobs) > cap:
        sys.exit(f"more than the {cap} approved calls; nothing sent")

    def one(j):
        threading.current_thread().lab_stop = stop
        v, m, out, call = j
        return CH._ask(call, CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                       lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                       adapt=CH.from_format_phase1).get("problems")
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        res = list(pool.map(one, jobs))
    print("done", len(res), "; problems", res, "; spent after USD", round(run_a.spent(log=lambda *a: None), 2))


def measure4():
    """Both cells over r0-r3. Readings (set before r2-r3 were sent, the 22-pair readings scaled to 44): the cut cell at
    most 10/44 named -> word count matters; 18/44 or more -> not the lever; 11-17 -> no answer. If pre17 itself is at most
    10/44 there is no contrast left. Also: r2-r3 alone against the 22-pair readings (replication), and per module the
    replies where at least half the barred signals are named (descriptive)."""
    mods = json.loads((HERE / "plan_round1.json").read_text(encoding="utf-8"))[T]["modules"]
    B = L.bars(T, mods)
    out = {}
    for name in (PRE17, CELL):
        rows = {}
        for rep in (0, 1, 2, 3):
            for m in mods:
                rec = json.loads((L.cell_dir(name, rep) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
                rows[(m, rep)] = sum(P.p1_named(rec, m, e) == "named" for e in B[m])
        tot = sum(rows.values())
        late = sum(v for (m, r), v in rows.items() if r >= 2)
        broke = {m[8:]: sum(1 for r in range(4) if rows[(m, r)] * 2 >= len(B[m])) for m in mods}
        out[name] = {"named r0-r3": tot, "pairs": 4 * sum(len(B[m]) for m in mods), "named r2-r3": late,
                     "replies breaking at least half (of 4)": broke,
                     "per reply": {f"{m[8:]} r{r}": f"{v}/{len(B[m])}" for (m, r), v in sorted(rows.items(), key=lambda x: (x[0][0], x[0][1]))}}
        print(f"{name:20s} named {tot:2d}/{out[name]['pairs']} (r2-r3 alone {late}/22); replies breaking half or more: {broke}")
        print("    ", out[name]["per reply"])
    n, p = out[CELL]["named r0-r3"], out[PRE17]["named r0-r3"]
    out["reading"] = ("no contrast: pre17 itself at most 10/44" if p <= 10 else
                      "word count matters (cut cell at most 10/44)" if n <= 10 else
                      "words are not the lever (cut cell 18/44 or more)" if n >= 18 else "no answer (11-17/44)")
    late = out[CELL]["named r2-r3"]
    out["replication r2-r3 (22-pair readings)"] = ("word count matters" if late <= 5 else
                                                  "not the lever" if late >= 9 else "no answer")
    print("reading (set before r2-r3):", out["reading"], "| r2-r3 alone:", out["replication r2-r3 (22-pair readings)"])
    (HERE / "p1half_4reps.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


def measure():
    mods = json.loads((HERE / "plan_round1.json").read_text(encoding="utf-8"))[T]["modules"]
    B = L.bars(T, mods)
    out = {}
    for name in ("P123__P1_S1", "P123__P1_pre9", "P123__P1_pre17", CELL):
        per, named = {}, 0
        for m in mods:
            for rep in (0, 1):
                f = L.cell_dir(name, rep) / "phase1" / f"{m}.json"
                rec = json.loads(f.read_text(encoding="utf-8"))
                k = sum(P.p1_named(rec, m, e) == "named" for e in B[m])
                per[f"{m[8:]} r{rep}"] = f"{k}/{len(B[m])}"
                named += k
        words = len((P.LAB / "prompts" / "diag_v10" / name / "phase1.md").read_text(encoding="utf-8").split())
        out[name] = {"words": words, "named": named, "pairs": sum(len(B[m]) for m in mods) * 2, "per reply": per}
        print(f"{name:20s} {words:5d} words  named {named:2d}/{out[name]['pairs']}  {per}")
    n = out[CELL]["named"]
    out["reading"] = ("word count matters (at most 5/22)" if n <= 5 else
                      "words are not the lever (9/22 or more)" if n >= 9 else "no answer (6-8/22)")
    print("reading (set before the run):", out["reading"])
    (HERE / "p1half.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"show": lambda: show(), "run": run, "measure": measure, "repeats": run_repeats, "measure4": measure4}[sys.argv[1]]()
