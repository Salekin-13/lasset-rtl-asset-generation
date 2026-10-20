"""Builds RULES_FROM_V7.md: the v7 failure patterns and the rules round, as for v5/v6. Every table is generated from the
result files of this folder; the prose is the orchestrator's (reasoning is labelled). Run after rules_post.py,
e_post.py and the D conflict check.   python make_rules_report.py
"""
import json
from pathlib import Path

H = Path(__file__).resolve().parent


def J(p):
    p = H / p
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


cat = J("pattern_categories.json")
items = J("rules_items.json")
rs = J("rules_status.json")
blind = J("E/blind_result.json")
proj = J("E/projection_combined.json")
oos = J("rules/oos_codecheck.json")
conf = J("D/conflicts.json")
st = J("c1_status.json")
sc = J("scores.json")
fx_check = J("rules/fixcheck_revised.json")
revised = {k: J(f"rules/{k}/revised.json") for k in ("B1", "R1", "R2", "R3", "R4", "R5", "R6", "P1", "P2", "P3", "P4")}

L = []
w = L.append
w("# Rules and constraints from the v7 failure analysis")
w("")
w("v7 = prompts/two_phase_v7, gpt-5.6-luna, high, runs r0-r2, 15 tuning modules, exact scoring (109 findable elements "
  "per run). Built 2026-10-14 from the v7 failure analysis in this folder (RUN_LOG.md has every step, agent count, cost "
  "and check). **Nothing here has been run on the model.** The effects below are measured on the stored v7 replies "
  "(code filters, exact) or judged blind on them (prompt rules, an upper bound).")
w("")
w("## 1. Where v7 fails")
w("")
w("Counts are element-runs summed over the three runs (missed: 17 + 20 + 23 = 60; false positives: 54 + 69 + 45 = 168). "
  "The categories are my reading of the analysts' revised C1 records; code counted each item once (pattern_categories.py).")
w("")
for name in ("misses", "false positives"):
    w(f"| {name.capitalize()} | Element-runs | In all 3 runs / 2 / 1 |")
    w("|---|---|---|")
    for k, v in cat[name].items():
        c = v["by class"]
        w(f"| {k} | {v['items']} | {c.get('consistent (3 of 3 runs)', 0)} / {c.get('frequent (2 of 3)', 0)} / {c.get('intermittent (1 of 3)', 0)} |")
    w("")
w("- Misses: 42 of 60 start in Phase 1 (categories 1-3), 18 in Phase 2 (4-5). Of the 12 elements missed in all three "
  "runs, 9 are lost in Phase 1 (27 of their 36 element-runs).")
w("- False positives: about half (88) break a rule v7 already has; 71 follow the prompt as written but the reference "
  "does not list them; 9 concern which end of an instance connection to name.")
w("- Over-walking is not a cause: every false positive found at a point reached by an arrow sits at a block that holds "
  "the concept's own lines; the error is the primary label.")
w("- None of the C1 patterns is \"confirmed\" under the run's strict rule (any correction a skeptic asked for counted as "
  "a refutation; 136 of 140 re-check verdicts asked for one). The rules below were drafted from the revised patterns, as "
  "in the v6 rules round, with the skeptics' corrections given to the drafters.")
w("")
w("## 2. The rules, ranked")
w("")
w("How each was checked (as in the v6 rules round): a fresh drafter; two skeptics (A: does it hit its targets; B: what it "
  "risks and the constraints); one revision; the project's prompt checks in code (no corpus names, no numeric hints; "
  "fixcheck.py, planted self-test); one integration check for conflicts (section 5); then the blind test for prompt "
  "rules (2 judges per module, 15 modules, no reference; score_v6.py) or an exact re-score of the stored replies for code "
  "filters. Both first-round skeptics asked for changes to every item; every item was revised. There was no re-check "
  "round.")
w("")
w("Ranking (the task's order): first rules that raise both precision and recall; then rules that raise one without "
  "lowering the other (on the stored replies), by size.")
w("")
w("| Rank | Fix | Kind | What it does | Targets (misses / FPs) | Effect on the stored replies | Words added (phase1 / phase2) | Basis |")
w("|---|---|---|---|---|---|---|---|")
pf = blind["per fix"]


def eff(fx):
    if fx in pf:
        p = pf[fx]
        return (f"blind: +{p['correct gained (both)']} correct, -{p['false positives removed (both)']} FP; "
                f"lost {p['correct lost (either)']}, FP added {p['false positives added (either)']}")
    s = rs[fx]["code-check score"]
    return (f"exact: -{sum(x['false positives removed'] for x in s.values())} FP, "
            f"{sum(len(x['correct lost']) for x in s.values())} correct lost")


def score_key(fx):
    if fx in pf:
        p = pf[fx]
        both = p["correct gained (both)"] > 0 and p["false positives removed (both)"] > 0
        return (0 if both else 1, -(p["correct gained (both)"] + p["false positives removed (both)"]))
    s = rs[fx]["code-check score"]
    return (1, -sum(x["false positives removed"] for x in s.values()))


plain = {
    "B1": "Names the parent signal, not the child port, when a sub-unit's output reaches this unit's decisions",
    "R1": "Keeps a switch's waiting-request flags and its downstream strobe as information of their own",
    "R2": "Narrows the sequencing-state bar: a peer's command input through synchronizers stays its own piece",
    "R3": "Keeps the 'holds data' flag and clear command of a FIFO holding generated data",
    "R4": "Keeps the access address of a memory the unit itself stores",
    "R5": "Labels primary a reduced enable input and an output port that copies a primary unchanged",
    "R6": "Holds the line of an accepted compare outcome, a handed-off access address and a decoded operand setting",
    "P1": "Code filter: drops copies, operand copies, pass-through record fields, serial shift registers",
    "P2": "Code filter: drops one-bit handshake copies, started flags, AMO state, merged responses",
    "P3": "Code filter: drops cache data words and port-buffer FIFO bits",
    "P4": "Code filter: drops CSR read-back words, operation selectors, timing flags, per-region results",
}
order = sorted(revised, key=score_key)
for n, fx in enumerate(order, 1):
    it = items[fx]
    wd = fx_check[f"{fx} revised"]["words added"]
    w(f"| {n} | {fx} | {revised[fx]['kind']} | {plain[fx]} | {it['misses']} / {it['false positives']} | {eff(fx)} | "
      f"{wd['phase1.md']} / {wd['phase2.md']} | {revised[fx]['basis']['label']} |")
w("")
w("## 3. Projection on the stored replies (upper bound, not a run)")
w("")
w("| | Correct per run | Listed per run | Pooled precision | Pooled recall |")
w("|---|---|---|---|---|")
for k, lab in (("base", "v7 as run"), ("filters", "+ code filters P1-P4"), ("blind", "+ prompt rules B1, R1-R6 (blind)"), ("blind+filters", "both")):
    v = proj["either"][k]
    w(f"| {lab} | {' / '.join(str(x[0]) for x in v['per run'].values())} | {' / '.join(str(x[1]) for x in v['per run'].values())} | {v['pooled precision']} | {v['pooled recall']} |")
w("")
w("The code filters on other stored runs of the same 15 modules (oos_codecheck.py), which the drafters did not target:")
w("")
w("| Runs | Pooled precision before -> after | Correct finds lost |")
w("|---|---|---|")
for k, v in oos.items():
    b, a = v["base"], v["all four"]
    T0, L0 = sum(x["correct"] for x in b.values()), sum(x["listed"] for x in b.values())
    T1, L1 = sum(x["correct"] for x in a.values()), sum(x["listed"] for x in a.values())
    w(f"| {k} | {T0}/{L0} = {T0 / L0:.3f} -> {T1}/{L1} = {T1 / L1:.3f} | {sum(len(x['correct lost']) for x in a.values())} |")
w("")
w("**Why these are upper bounds (reasoning, with the measured history):**")
w("- Blind tests have been too optimistic before (inherited from experiments/03_two_phase_csa_pio/lab/HANDOVER.md and "
  "analysis/two_phase_v6__gpt-5.6-luna__high__r0-r2/V6_RESULTS.md, not re-derived here): v5g's blind test predicted "
  "precision 0.50-0.55 and the run gave 0.43; v6's predicted 0 lost correct finds and the run lost 10 elements. Judges apply a rule as written; the model skips exceptions "
  "and applies bars beyond their text, and a new Phase 1 can drop concepts the stored replies still have.")
w("- The two blind judges made the same changes on every module. The rules are written close to their targets: R1 and "
  "R4 each fit one unit of this corpus (the drafters say so). That is an overfitting risk the 15 tuning modules cannot "
  "measure; the 26 held-out modules can.")
w("- The code filters were written by agents who saw these false positives. They lost nothing on 15 other runs of the "
  "same modules, which is encouraging, but those modules are not held out. A filter fixes the score, not the model.")
w("- Length: the 7 prompt rules together add 998 words to phase1.md (v7: 5,963) and 838 to phase2.md (v7: 7,573). "
  "v6's growth in length came with rules applied beyond their text.")
w("")
w("## 4. The rules in detail")
w("")
for fx in order:
    r = revised[fx]
    w(f"### {fx}: {r['title']}")
    w("")
    w(f"- **Kind / basis:** {r['kind']}; {r['basis']['label']}: {r['basis']['citation'][:400]}{' ...' if len(r['basis']['citation']) > 400 else ''}")
    w(f"- **Targets:** {r['targets']['description'][:500]}{' ...' if len(r['targets']['description']) > 500 else ''}")
    if r["kind"] == "code check":
        w(f"- **The filter:** {r['wording']['code_check']['sentence']}")
        w(f"- **Script:** rules/{fx}/check.py (reads only the stored replies and the inputs; self-test inside).")
    else:
        core = r["wording"]["core_sentence"] or (r["wording"]["edits"][0]["new_text"] if r["wording"]["edits"] else "")
        w(f"- **Core sentence:** {core}")
        w(f"- **Edits:** " + "; ".join(f"{e['file']} line {e['line']} ({e['action']})" for e in r["wording"]["edits"]) + f". Full text: rules/{fx}/revised.json; as a diff: blind/diffs/{fx}.diff.")
    w(f"- **Expected precision ({r['expected_precision_effect']['direction']}):** {r['expected_precision_effect']['reasoning'][:450]}{' ...' if len(r['expected_precision_effect']['reasoning']) > 450 else ''}")
    w(f"- **Expected recall ({r['expected_recall_effect']['direction']}):** {r['expected_recall_effect']['reasoning'][:450]}{' ...' if len(r['expected_recall_effect']['reasoning']) > 450 else ''}")
    w(f"- **Trade-off:** {r['trade_off'][:450]}{' ...' if len(r['trade_off']) > 450 else ''}")
    if r["kind"] in ("phase 1 rule", "paired rule"):
        w(f"- **Recall risk in a new run (Phase 1):** {r['recall_risk'][:450]}{' ...' if len(r['recall_risk']) > 450 else ''}")
    w(f"- **What would show it is wrong:** {r['falsifier'][:500]}{' ...' if len(r['falsifier']) > 500 else ''}")
    w(f"- **Skeptics (round 1):** A {rs[fx]['skeptic A (fix / finding)'][0]}, B {rs[fx]['skeptic B (fix / finding)'][0]} (both asked for changes; answered in the revision, rules/{fx}/revised.json replies_to_reviewers). Prompt checks: {fx_check[fx + ' revised']['ok'] and 'pass' or 'FAIL'}.")
    w("")
w("## 5. Conflicts between the fixes (integration check)")
w("")
if conf:
    w(f"One agent read all 11 fix files by path ({conf.get('pairs_checked')} pairs). Its notes say the conflicts below are "
      "textual: by its own scan of the 17 tuning closed sets, no element meets both rules (the agent's measurement, not "
      "re-derived here). It also reports that no element the prompt rules require as primary is dropped by a code filter. "
      "Following the plan, conflicting fixes went to the blind test unchanged as alternatives; no merged wording was drafted. "
      "Before both go into one version, one of them needs the other's case named inside its main sentence.")
    w("")
    if not conf.get("conflicts"):
        w(f"None found ({conf.get('pairs_checked')} pairs checked). {conf.get('notes', '')[:600]}")
    for c in conf.get("conflicts", []):
        w(f"- **{' / '.join(c['fixes'])}:** {c['clash']}")
        w(f"  - {c['text_a'][:300]}")
        w(f"  - {c['text_b'][:300]}")
else:
    w("Not available: the integration check had not returned when this report was built.")
w("")
w("## 6. Held for your decision: reference conventions without a basis")
w("")
w("These follow the prompt or theory but not the reference. Under your rule (a prompt rule needs a theory basis; a "
  "convention needs your decision and goes to a code filter), no rule was drafted.")
w("")
w("| Item | What the reference does | Misses / FPs it would address |")
w("|---|---|---|")
for k in ("D1", "D2", "D3", "D4", "D5"):
    it = items[k]
    w(f"| {k} | {it['title']} | {it['misses']} / {it['false positives']} |")
w("")
w("## 7. Recommendation (reasoning)")
w("")
w("Apply the four code filters to v7's outputs as a separately reported row (\"code filter, not a prompt change\"): on the "
  "stored replies they raise precision from 0.614 to 0.767 at no measured recall cost, and they need no new model run. "
  "Build the seven prompt rules as a new version in its own folder (v8, own output directory) and run it, reading each "
  "rule's falsifier; expect much less than the blind projection. Check both on the 26 held-out modules before relying "
  "on them.")
(H / "RULES_FROM_V7.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("written RULES_FROM_V7.md:", len("\n".join(L).split()), "words")
