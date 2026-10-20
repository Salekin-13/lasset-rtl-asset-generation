"""Reports for two_phase_v4a (gpt-5.6-luna, high, r0-r2): what changed from v4, and the Phase 1 / Phase 2 failure analysis.

Numbers come from code: pack3.json (exact scorer), compare_v4_v4a.json, attribution.json, views_fa/items.json. Diagnoses,
patterns and regression causes come from the failure-analysis workflow (its result file, given as argument); every
pattern's false-positive and miss counts are recomputed here from the member items, never copied from an agent.

Writes V4A_VS_V4.md, V4A_FAILURE_ANALYSIS.md and V4A_FAILURE_ANALYSIS_APPENDIX.md.

  python make_fa_report.py <workflow result file (task output)> <workflow id>
  python make_fa_report.py <path to the workflow's journal.jsonl> <workflow id>     (when the result file is gone, e.g. in a
                                                                                     new session: rebuilds the result from
                                                                                     every agent's journal entry)
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = ("r0", "r1", "r2")
SIDE_NAME = {"P1": "Phase 1", "P2": "Phase 2", "RC": "Reference convention"}


def cell(x):
    return str(x).replace("|", "/").replace("\n", " ")


def table(header, rows):
    return ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"] + \
        ["| " + " | ".join(cell(x) for x in r) + " |" for r in rows] + [""]


def r3(xs):
    return " / ".join(str(x) for x in xs)


def from_journal(path):
    """The workflow's return value, rebuilt from its journal (labels fa-a/fa-a2/fa-c:<chunk>, fa-reg/fa-regc:<module>,
    fa-pat/fa-crit/fa-rev:<side>), the same way the workflow script assembles it."""
    J = {}
    label = {}
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        if d["type"] == "started":
            label[d["agentId"]] = d["label"]
        elif d["type"] == "result" and d.get("agentId") in label:
            r = d["result"]
            J[label[d["agentId"]]] = json.loads(r) if isinstance(r, str) and r[:1] in "{[" else r
    args = json.loads((HERE / "workflow_args_fa_compact.json").read_text(encoding="utf-8"))
    checked = []
    for c, tails in args["chunks"].items():
        want = [f"{c.split('#')[0]}:{t}" for t in tails]
        a = J.get(f"fa-a:{c}")
        if not a:
            continue
        got = {x["id"]: x for x in a["items"] if x["id"] in want}
        for x in (J.get(f"fa-a2:{c}") or {}).get("items", []):
            if x["id"] in want and x["id"] not in got:
                got[x["id"]] = x
        k = J.get(f"fa-c:{c}")
        if k:
            fin = {x["id"]: x for x in k["items"] if x["id"] in want}
            for i, x in got.items():
                fin.setdefault(i, x)
            checked.append({"chunk": c, "items": list(fin.values()), "changes": k["changes"], "notes": a["module_notes"]})
        else:
            checked.append({"chunk": c, "items": list(got.values()), "changes": [], "unchecked": True, "notes": a["module_notes"]})
    regressed = []
    for s in args["regress"]:
        r, k = J.get(f"fa-reg:{s}"), J.get(f"fa-regc:{s}")
        if k:
            regressed.append({"module": s, "elements": k["elements"], "changes": k["changes"], "notes": (r or {}).get("notes", "")})
        elif r:
            regressed.append({"module": s, "elements": r["elements"], "changes": [], "unchecked": True, "notes": r["notes"]})
    take = {"P1": ("Phase 1", "both"), "P2": ("Phase 2", "both"), "RC": ("reference convention",)}
    allitems = [x for c in checked for x in c["items"]]
    sides = []
    for sd in ("P1", "P2", "RC"):
        fin = J.get(f"fa-rev:{sd}") or J.get(f"fa-pat:{sd}")
        if not fin:
            continue
        ids = [x["id"] for x in allitems if x["attribution"] in take[sd]]
        seen = Counter(m for p in fin["patterns"] for m in p["members"])
        cov = {"dup": [m for m, n in seen.items() if n > 1], "miss": [i for i in ids if i not in seen], "stray": [m for m in seen if m not in ids]}
        sides.append({"side": sd, "final": fin, "coverage_final": cov, "from_draft": f"fa-rev:{sd}" not in J})
    return {"checked": checked, "regressed": regressed, "sides": sides}


def main(result_file, wid):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if result_file.endswith("journal.jsonl"):
        R = from_journal(result_file)
    else:
        R = json.loads(Path(result_file).read_text(encoding="utf-8"))
        R = R.get("result", R)
    C = json.loads((HERE / "compare_v4_v4a.json").read_text(encoding="utf-8"))
    A = json.loads((HERE / "attribution.json").read_text(encoding="utf-8"))
    items = {i["id"]: i for i in json.loads((HERE / "views_fa" / "items.json").read_text(encoding="utf-8"))}
    idmap = json.loads((HERE / "fa_id_map.json").read_text(encoding="utf-8"))
    diag = {}
    for c in R["checked"]:
        if not c:
            continue
        s = c["chunk"].split("#")[0]
        for x in c["items"]:
            diag[f"{s}:{x['id'].split(':', 1)[1]}" if not x["id"].startswith(s + ":") else x["id"]] = x
    missing = [k for k in idmap if k not in diag]
    print(f"diagnosed items {len(diag)} of {len(idmap)}; missing {len(missing)}")

    def fp_of(sid, side):
        """false positives (sum over the item's run) that an item contributes to one side, by the item's own split"""
        it, d = items[idmap[sid]], diag[sid]
        k = it["kind"]
        if k == "extra":
            return it["fp_only"] + it["fp_shared"]
        if k == "broader":
            return len(d["extra_part_elements"]) if side == "P1" else len(d["matched_part_elements"]) if side == "P2" else \
                len(d["extra_part_elements"]) + len(d["matched_part_elements"])
        if k == "p2fp":
            return len(d["own_rule_broken_elements"]) if side == "P2" else len(d["prompt_allows_elements"]) if side == "RC" else 0
        return 0

    # ---------------- attribution summary (code + agents)
    att = Counter((items[idmap[k]]["kind"], d["attribution"]) for k, d in diag.items())
    p2 = [(k, d) for k, d in diag.items() if items[idmap[k]]["kind"] == "p2fp"]
    own = sum(len(d["own_rule_broken_elements"]) for _, d in p2)
    allow = sum(len(d["prompt_allows_elements"]) for _, d in p2)
    p2n = sum(len(items[idmap[k]]["fp_elements"]) for k, _ in p2)
    br = [(k, d) for k, d in diag.items() if items[idmap[k]]["kind"] == "broader"]
    bx = sum(len(d["extra_part_elements"]) for _, d in br)
    bm = sum(len(d["matched_part_elements"]) for _, d in br)
    bn = sum(items[idmap[k]]["fp_only"] + items[idmap[k]]["fp_shared"] for k, _ in br)
    fpc = Counter((x["run"], x["phase"]) for x in A["fp"])
    fnc = Counter((x["run"], x["category"]) for x in A["fn"])
    miss_att = Counter(d["attribution"] for k, d in diag.items() if items[idmap[k]]["kind"] == "miss")
    miss_att_run = Counter((items[idmap[k]]["run"], d["attribution"]) for k, d in diag.items() if items[idmap[k]]["kind"] == "miss")
    ext_att = Counter(d["attribution"] for k, d in diag.items() if items[idmap[k]]["kind"] == "extra")
    print("p2fp elements", p2n, "own rule broken", own, "prompt allows", allow, "| broader fps", bn, "extra part", bx, "matched part", bm)
    print("miss attribution", dict(miss_att), "| extra attribution", dict(ext_att))

    # ---------------- every false positive counted once, by the judged cause of the item(s) that cover it
    PRIO = ["Phase 1", "both", "Phase 2", "reference convention", "unclear", "not split"]
    claim = defaultdict(list)
    for sid, d in diag.items():
        it = items[idmap[sid]]
        m, k, kind = "neorv32_" + it["module"], it["run"], it["kind"]
        if kind == "extra":
            for e in it["fp_elements_only"] + it["fp_elements_shared"]:
                claim[(m, k, e)].append(d["attribution"])
        elif kind == "broader":
            xs, ms = set(d["extra_part_elements"]), set(d["matched_part_elements"])
            for e in it["fp_elements_only"] + it["fp_elements_shared"]:
                c = "reference convention" if d["attribution"] == "reference convention" else \
                    "Phase 1" if e in xs else "Phase 2" if e in ms else "not split"
                claim[(m, k, e)].append(c)
        elif kind == "p2fp":
            ob, pa = set(d["own_rule_broken_elements"]), set(d["prompt_allows_elements"])
            for e in it["fp_elements"]:
                claim[(m, k, e)].append("Phase 2" if e in ob else "reference convention" if e in pa else "not split")
    fpcause = Counter()
    for x in A["fp"]:
        cs = claim.get((x["module"], x["run"], x["element"]), [])
        fpcause[(x["run"], min(cs, key=PRIO.index) if cs else "no item")] += 1
    CAUSE_LABEL = {"Phase 1": "Phase 1 made a concept, or a concept part, that the reference does not have",
                   "both": "both phases (judged)", "Phase 2": "Phase 2 broke its own rules under a correct concept",
                   "reference convention": "the prompt's rules ask for it; the reference lists something else",
                   "unclear": "unclear (judged)", "not split": "under a split item but in neither list", "no item": "covered by no item"}
    print("false positives by judged cause:", {c: [fpcause[(k, c)] for k in RUNS] for c in CAUSE_LABEL})

    # ---------------- patterns with recomputed weights
    PAT = {}
    for sd in R["sides"]:
        if not sd or not sd.get("final"):
            continue
        rows = []
        for p in sd["final"]["patterns"]:
            mem = [m for m in p["members"] if m in diag]
            fp = sum(fp_of(m, sd["side"]) for m in mem)
            miss = sum(1 for m in mem if items[idmap[m]]["kind"] == "miss")
            runs = Counter(items[idmap[m]]["run"] for m in mem)
            mods = sorted({items[idmap[m]]["module"] for m in mem})
            rows.append({**p, "fp": fp, "misses": miss, "runs": [runs[k] for k in RUNS], "modules": mods, "n": len(mem),
                         "bad_members": [m for m in p["members"] if m not in diag]})
        rows.sort(key=lambda r: (-r["fp"], -r["misses"]))
        PAT[sd["side"]] = {"rows": rows, "left_out": sd["final"].get("left_out", []), "cov": sd.get("coverage_final")}
    REGR = {r["module"]: r for r in R["regressed"] if r}

    # ---------------- V4A_VS_V4.md
    S = C["structural"]
    g = lambda v, f, fmt="{:.3f}": " / ".join(fmt.format(S[f"{v} {k}"][f]) for k in RUNS)  # noqa: E731
    Cc = C["concepts"]
    cg = lambda v, f: " / ".join(str(Cc[f"{v} {k}"][f]) for k in RUNS)  # noqa: E731
    p1p = lambda v: " / ".join(f"{1 - Cc[f'{v} {k}']['extra'] / Cc[f'{v} {k}']['concepts']:.3f}" for k in RUNS)  # noqa: E731
    cause = Counter()
    reg_rows = []
    for s, r in REGR.items():
        for e in r["elements"]:
            ch = e["change"].strip().lower()
            ch = "gain" if ch.startswith("gain") else "loss" if ch.startswith("loss") else "lone miss"
            cause[(ch, e["cause"])] += 1
            reg_rows.append([f"{s}:{e['element']}", ch, e["cause"], e["mechanism"][:400] + ("..." if len(e["mechanism"]) > 400 else "")])
    wc = [x for x in reg_rows if x[2] == "wording change"]
    L = ["# two_phase_v4a vs two_phase_v4 (gpt-5.6-luna, high, three runs each)", "",
         "v4a is v4's content in v2a's shorter wording (common.md 4,926 -> 4,109 words, phase1.md 1,506 -> 1,448; meaning checked "
         "clause by clause; prompts/two_phase_v4a/README.md). Yardstick: v4's own run-to-run range, as the README set it before the run. "
         "Structural numbers: exact scorer, 109 findable reference elements (compare_v4_v4a.py). Concept numbers: two blind judges per "
         f"module plus adjudication, the same method as for v4 (v4: wf_60ff96f7-019; v4a: {A['judges']}). Causes of element changes: "
         f"one agent per module plus a skeptic ({wid}).", "",
         "## Answer", "",
         f"- **Averages are the same; the runs spread more.** Precision v4 {g('v4', 'P')}, v4a {g('v4a', 'P')}. Recall v4 {g('v4', 'R')}, "
         f"v4a {g('v4a', 'R')}. Correct finds v4 {g('v4', 'tp', '{}')}, v4a {g('v4a', 'tp', '{}')}.",
         f"- **The README's falsification rule is tripped by one run.** v4a r1's recall ({S['v4a r1']['R']:.3f}) and F1 "
         f"({S['v4a r1']['F1']:.3f}) fall below v4's range; r0 and r2 are above it. r1 alone missed {len(C['lone_misses']['r1'])} "
         f"elements that both other v4a runs found ({', '.join(C['lone_misses']['r1'])}), in "
         f"{len({x.split(':')[0] for x in C['lone_misses']['r1']})} different modules.",
         f"- **Element level: no detectable direction.** Found in more v4a runs: {len(C['elements']['more'])}; in fewer: "
         f"{len(C['elements']['fewer'])} (two-sided sign test p = {C['elements']['p']:.2f}). Found in all three runs: v4 "
         f"{C['elements']['dist']['v4']['3']}, v4a {C['elements']['dist']['v4a']['3']} of 109.",
         f"- **Phase 1 made more concepts in r1 and r2.** Concepts v4 {cg('v4', 'concepts')}, v4a {cg('v4a', 'concepts')}; extra "
         f"concepts v4 {cg('v4', 'extra')}, v4a {cg('v4a', 'extra')}; Phase 1 precision v4 {p1p('v4')}, v4a {p1p('v4a')}. Reference "
         f"concepts found (of 77): v4 {cg('v4', 'found')}, v4a {cg('v4a', 'found')}.",
         f"- **Merged bus responses (CX5) came back in one run** (v4a {r3([C['cx']['v4a'].get(f'CX5|{k}', 0) for k in RUNS])}), "
         "not in more than one, so the README's second test is not tripped.",
         f"- **Causes of the changed elements** (after the skeptic): " + "; ".join(f"{a} {b}: {n}" for (a, b), n in sorted(cause.items())) + ".", ""]
    L += ["## Structural results", ""]
    L += table(["version", "run", "listed", "correct", "false pos.", "precision", "recall", "F1", "bus-record FPs", "concepts"],
               [[v, k, S[f"{v} {k}"]["listed"], S[f"{v} {k}"]["tp"], S[f"{v} {k}"]["fp"], f"{S[f'{v} {k}']['P']:.3f}", f"{S[f'{v} {k}']['R']:.3f}",
                 f"{S[f'{v} {k}']['F1']:.3f}", S[f"{v} {k}"]["bus_fp"], S[f"{v} {k}"]["concepts"]] for v in ("v4", "v4a") for k in RUNS])
    L += ["Per module, correct finds and false positives per run (r0/r1/r2):", ""]
    L += table(["module", "findable", "correct v4", "correct v4a", "FP v4", "FP v4a"],
               [[s, d["findable"], r3(d["v4"]["tp"]), r3(d["v4a"]["tp"]), r3(d["v4"]["fp"]), r3(d["v4a"]["fp"])] for s, d in C["modules"].items()])
    L += ["## Elements whose found-run count changed, and why", "",
          "Record: runs r0 r1 r2 that found it (x). Cause after the skeptic: 'wording change' needs a changed prompt line that the model's "
          "text echoes or a behaviour consistent across v4a runs and absent in v4; otherwise 'run-to-run variance' or 'unclear'.", ""]
    L += table(["element", "change", "cause", "mechanism (shortened; full text and evidence in the appendix)"], reg_rows)
    L += ["## Concept level (judges)", ""]
    L += table(["version", "run", "concepts", "extra", "broader", "Phase 1 precision", "reference concepts found of 77", "partly found"],
               [[v, k, Cc[f"{v} {k}"]["concepts"], Cc[f"{v} {k}"]["extra"], Cc[f"{v} {k}"]["broader"],
                 f"{1 - Cc[f'{v} {k}']['extra'] / Cc[f'{v} {k}']['concepts']:.3f}", Cc[f"{v} {k}"]["found"], Cc[f"{v} {k}"]["partly"]]
                for v in ("v4", "v4a") for k in RUNS])
    L += ["Reference concepts found in a different number of runs: " + "; ".join(f"{a} {b}/3 -> {c}/3" for a, b, c in C["rc_changes"]) + ".", ""]
    L += ["## Reasoning, not measured", "",
          "- With three runs per version, a one-run dip like v4a r1 is within what Luna's run-to-run spread can produce; the element-level "
          "test and the found-in-all-runs count show no consistent loss. Brevity is not a lever on scores, the same finding as v2a vs v2.",
          "- Where the skeptic kept a 'wording change' cause, the shortened line is named above; those lines are candidates to restore "
          "word for word in the next version." if wc else
          "- The skeptic kept no 'wording change' cause, so no shortened line is implicated.", ""]
    (HERE / "V4A_VS_V4.md").write_text("\n".join(L), encoding="utf-8")

    # ---------------- V4A_FAILURE_ANALYSIS.md
    tot = {k: S[f"v4a {k}"] for k in RUNS}
    F = ["# Failure analysis of two_phase_v4a, Phase 1 and Phase 2 (gpt-5.6-luna, high, r0-r2)", "",
         "What fails, in which phase, and why, with one fix direction per pattern. Facts from code (exact scorer, self-tested pack builder; "
         "attribution.py); diagnoses by one analyst per module (per run for the 7 largest) and a skeptical checker; patterns grouped "
         f"per side, then criticized and revised ({wid}). Concept verdicts: {A['judges']}. Every count below is recomputed by code "
         "from the member items (make_fa_report.py).", "",
         "## Answer", "",
         f"- **False positives (wrong elements listed as primary), {r3([tot[k]['fp'] for k in RUNS])} per run.** Phase 1 causes "
         f"{r3([fpc[(k, 'Phase 1')] for k in RUNS])}: they sit only under concepts the reference does not have. Phase 2 causes "
         f"{r3([fpc[(k, 'Phase 2')] for k in RUNS])}: they sit under a correct concept.",
         f"- **Of the Phase 2 false positives under concepts that match exactly ({p2n}, sum of 3 runs), {own} break the prompt's own "
         f"Phase 2 rules and {allow} are allowed by them** (the reference simply lists something else). Of the {bn} false positives "
         f"under broader concepts, {bx} belong to the extra part Phase 1 bundled in and {bm} to the matched part.",
         f"- **Misses (reference elements not found), {r3([109 - tot[k]['tp'] for k in RUNS])} per run.** Judged cause: "
         + ", ".join(f"{a} {n}" for a, n in miss_att.most_common()) + " (sum of 3 runs).",
         f"- **Extra concepts with false positives**: judged " + ", ".join(f"{a} {n}" for a, n in ext_att.most_common()) + ".",
         "- **Every false positive counted once, by its judged cause** (r0 / r1 / r2): " +
         "; ".join(f"{CAUSE_LABEL[c]} {r3([fpcause[(k, c)] for k in RUNS])}" for c in CAUSE_LABEL if any(fpcause[(k, c)] for k in RUNS)) + ".", ""]
    F += ["## False positives by judged cause (each counted once)", "",
          "An element under two items takes the first cause in this order: Phase 1, both, Phase 2, reference convention, unclear. "
          "Broader concepts are split element by element (extra part -> Phase 1, matched part -> Phase 2), Phase 2 groups likewise "
          "(own rule broken -> Phase 2, prompt allows -> reference convention).", ""]
    F += table(["cause", "r0", "r1", "r2", "sum"],
               [[CAUSE_LABEL[c]] + [fpcause[(k, c)] for k in RUNS] + [sum(fpcause[(k, c)] for k in RUNS)] for c in CAUSE_LABEL] +
               [["all false positives"] + [tot[k]["fp"] for k in RUNS] + [sum(tot[k]["fp"] for k in RUNS)]])
    F += ["## Numbers by phase (code)", ""]
    F += table(["", "r0", "r1", "r2"],
               [["listed / correct / false positives"] + [f"{tot[k]['listed']} / {tot[k]['tp']} / {tot[k]['fp']}" for k in RUNS],
                ["false positives only under extra concepts (Phase 1)"] + [fpc[(k, "Phase 1")] for k in RUNS],
                ["false positives under a matching concept (Phase 2 or broader)"] + [fpc[(k, "Phase 2")] for k in RUNS]] +
               [[f"misses: {c}"] + [fnc[(k, c)] for k in RUNS] for c in ("P1 concept missed", "P1 concept partly found", "P1 dropped by name",
                                                                           "P1? folded", "P2 secondary", "P2 not listed", "format")] +
               [[f"misses judged {a}"] + [miss_att_run[(k, a)] for k in RUNS] for a in ("Phase 1", "Phase 2", "both", "reference convention", "unclear")])
    for side in ("P1", "P2", "RC"):
        if side not in PAT:
            F += [f"## {SIDE_NAME[side]} patterns", "", "(no result)", ""]
            continue
        rows = PAT[side]["rows"]
        F += [f"## {SIDE_NAME[side]} patterns", "",
              "Items whose judged attribution is " + {"P1": "Phase 1 or both", "P2": "Phase 2 or both", "RC": "reference convention"}[side] +
              ". FPs = false positives these items carry for this side (sum of 3 runs; an extra concept's shared FPs count fully, so "
              "patterns can overlap); items per run. The group label is the pattern agent's; where it says 'reference convention' on "
              "the Phase 1 or Phase 2 side, the pattern stage judged the fix to be an evaluation-layer filter. Full text of every "
              "pattern: appendix.", ""]
        F += table(["id", "group", "pattern", "FPs", "misses", "items r0/r1/r2", "modules"],
                   [[p["id"], p["group"], p["name"], p["fp"], p["misses"], r3(p["runs"]), ", ".join(p["modules"])] for p in rows])
        big = [p for p in rows if p["fp"] >= 10 or p["misses"] >= 3]
        if big:
            F += ["Fix directions of the patterns with at least 10 false positives or 3 misses (agent text, after the critic):", ""]
            for p in big:
                F += [f"- **{p['id']} {p['name']}** ({p['fp']} FPs, {p['misses']} misses). Fix: {p['fix_direction']} Basis: {p['fix_basis']} "
                      f"Could break: {p['could_break']} Falsified if: {p['falsify']}"]
            F += [""]
        if PAT[side]["left_out"]:
            F += ["Left out of this side: " + "; ".join(f"{x['id']} ({x['reason']})" for x in PAT[side]["left_out"]), ""]
        cov = PAT[side]["cov"] or {}
        F += [f"Coverage check (code): duplicates {len(cov.get('dup', []))}, missing {len(cov.get('miss', []))}, stray {len(cov.get('stray', []))}.", ""]
    (HERE / "V4A_FAILURE_ANALYSIS.md").write_text("\n".join(F), encoding="utf-8")

    # ---------------- appendix: every item
    X = ["# Appendix: patterns in full, and every diagnosed item (two_phase_v4a)", "", f"Workflow {wid}. Ids: <module>:<run>:<code>:<rest>; "
         "x extra concept, b broader concept, p Phase 2 false positives under matching concepts, m missed element.", ""]
    for side in ("P1", "P2", "RC"):
        for p in PAT.get(side, {}).get("rows", []):
            X += [f"### {SIDE_NAME[side]} {p['id']} {p['name']} ({p['group']}; {p['fp']} FPs, {p['misses']} misses)", "",
                  f"- What the model did: {p['what_model_did']}", f"- RTL shape: {p['rtl_shape']}", f"- Cause: {p['cause']}",
                  f"- Why the rules did not stop it: {p['why_rules_missed']}", f"- Example: {p['example']}",
                  f"- Fix direction: {p['fix_direction']} Basis: {p['fix_basis']}", f"- Could break: {p['could_break']}",
                  f"- Falsified if: {p['falsify']}", f"- Members ({p['n']}): {', '.join(p['members'])}", ""]
    X += ["## Every diagnosed item", ""]
    for s in sorted({items[idmap[k]]["module"] for k in idmap}):
        X += [f"## {s}", ""]
        rows = []
        for k in sorted((k for k in idmap if items[idmap[k]]["module"] == s), key=lambda k: (k.split(":")[1], k)):
            d = diag.get(k)
            if not d:
                rows.append([k, "NOT DIAGNOSED", "", "", ""])
                continue
            extra = ""
            if d["extra_part_elements"] or d["matched_part_elements"]:
                extra = f" extra part: {', '.join(d['extra_part_elements']) or '-'}; matched part: {', '.join(d['matched_part_elements']) or '-'}."
            if d["own_rule_broken_elements"] or d["prompt_allows_elements"]:
                extra = f" own rule broken: {', '.join(d['own_rule_broken_elements']) or '-'}; prompt allows: {', '.join(d['prompt_allows_elements']) or '-'}."
            rows.append([k, d["attribution"], d["mechanism"] + extra, f"\"{d['quote']}\" ({d['quote_source']}); {d['prompt_lines']}", d["fix_direction"]])
        X += table(["item", "attribution", "mechanism", "evidence", "fix direction"], rows)
    X += ["## Checker changes", ""]
    for c in R["checked"]:
        if c and c.get("changes"):
            X += [f"- {c['chunk']}: " + "; ".join(f"{x['id']}: {x['what']} ({x['why']})" for x in c["changes"])]
    X += ["", "## Regression explanations (after the skeptic)", ""]
    for s, r in REGR.items():
        for e in r["elements"]:
            X += [f"- {s}:{e['element']} ({e['change']}, {e['cause']}): v4: {e['v4_behaviour']} v4a: {e['v4a_behaviour']} "
                  f"Evidence: {e['evidence']} \"{e['quote']}\" ({e['quote_source']})"]
        if r.get("changes"):
            X += [f"  - skeptic changes: " + "; ".join(f"{x['element']}: {x['what']} ({x['why']})" for x in r["changes"])]
    (HERE / "V4A_FAILURE_ANALYSIS_APPENDIX.md").write_text("\n".join(X), encoding="utf-8")
    print("wrote V4A_VS_V4.md, V4A_FAILURE_ANALYSIS.md, V4A_FAILURE_ANALYSIS_APPENDIX.md")


if __name__ == "__main__":
    main(*sys.argv[1:3])
