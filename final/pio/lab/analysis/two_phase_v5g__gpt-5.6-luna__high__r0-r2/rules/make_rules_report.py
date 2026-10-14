"""RULES_V6.md (concise) and RULES_V6_APPENDIX.md (every rule's exact texts) from the rules workflow (wf_ce0308e1-806,
rules_workflow_result.json) and the code-computed evidence (extra_groups.json, misses.json). Counts computed here are
marked as such; texts from agents are marked '(agent)' and numbers inside them were not re-derived (Unverified).
Optional second argument: the boundary-test result (score_v6.py output JSON) to add the blind estimate.

  python make_rules_report.py [boundary_result.json]
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
HELD = {"NC.K2SW", "NC.SCR", "NC.FIFOb"}
MERGED = {"NC.TMS": "R-M5-modeselect", "NC.STEP": "CX2.U3b", "NC.FIFOa": "dropped (covered by CX1-ACF)", "W2": "not in this change (separate arm)"}


def clip(t, n=400):
    t = " ".join(str(t or "").split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " ..."


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    R = json.loads((HERE / "rules_workflow_result.json").read_text(encoding="utf-8"))
    G = json.loads((HERE / "extra_groups.json").read_text(encoding="utf-8"))
    M = json.loads((HERE / "misses.json").read_text(encoding="utf-8"))
    BR = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")) if len(sys.argv) > 1 else None
    items = R["items"]
    st = Counter(x["stage"] for x in M)
    fp_extra = sum(len(g["fp_rows"]) for g in G)
    L = ["# v6 rules from the v5g failure analysis", "",
         "Source: the v5g three-run failure analysis (THREE_RUN_FAILURES.md), code-computed evidence (`extra_groups.json`, "
         "`misses.json`, `rules_prep.py`, self-tested), and the rules workflow wf_ce0308e1-806 (61 agents: 15 items, each drafted, "
         "checked by two skeptics and revised; then one integration check). Built 2026-10-13. Texts marked (agent) are the agents' "
         "words; numbers inside them were not re-derived here.", "",
         "## Evidence (computed)", "",
         f"- Extra concepts (no reference counterpart): {len(G)} groups across the three runs; {sum(1 for g in G if not g['tp_any'])} carry no "
         f"correct find; they hold {fp_extra} of the 352 false-positive rows (90 + 133 + 129). No correct find depends only on an extra concept "
         f"(tp_only empty for all groups).",
         f"- Misses: {len(M)} over the three runs ({sum(x['run'] == 'r0' for x in M)} / {sum(x['run'] == 'r1' for x in M)} / {sum(x['run'] == 'r2' for x in M)}), "
         f"by where they were lost: " + ", ".join(f"{k} {v}" for k, v in st.most_common()) + ".", ""]
    L += ["## Causes and rules per item", ""]
    rows = []
    for it in items:
        f = it.get("final") or {}
        L.append(f"### {it['key']}: {it['title']}")
        for r in f.get("reasons", [])[:6]:
            L.append(f"- **Cause (agent):** {clip(r['pattern'], 220)} — {clip(r['cause'], 420)}")
        for r in f.get("rules", []):
            status = "held (needs your decision)" if r["id"] in HELD else (f"merged/dropped: {MERGED[r['id']]}" if r["id"] in MERGED else "in the v6 candidate")
            rows.append([r["id"], it["key"], r["kind"], clip(r["label"], 90), len(r["targets"]), len(r["spares"]), status])
        for x in f.get("not_prompt_fixable", [])[:5]:
            L.append(f"- **Not prompt-fixable (agent):** {clip(x['pattern'], 160)} — {clip(x['why'], 260)}")
        L.append("")
    L += ["## All rules", "", "| Rule | Item | Kind | Label (agent) | Targets | Spares | Status |", "|---|---|---|---|---|---|---|"]
    L += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    L += ["", f"Counted here: {len(rows)} rules; in the candidate {sum(1 for r in rows if r[6] == 'in the v6 candidate')}; held "
          f"{sum(1 for r in rows if r[6].startswith('held'))}; merged or dropped {sum(1 for r in rows if r[6].startswith('merged'))}.", ""]
    it = R["integ"]
    L += ["## Integration (agent)", "", "- " + clip(it["words"], 1200), "",
          "- Conflicts resolved: " + str(len(it["conflicts"])) + ". Main ones: " + "; ".join(clip(c["problem"], 160) for c in it["conflicts"][:5]), ""]
    if BR:
        L += ["## Blind boundary test of the candidate (score_v6.py)", ""]
        for mode in ("both", "either"):
            s0, s1 = BR["base"], BR[mode]["score"]
            L.append(f"- {mode} judge(s): " + "; ".join(f"r{r}: precision {s0[str(r)]['precision']} -> {s1[str(r)]['precision']}, recall "
                                                    f"{s0[str(r)]['recall']} -> {s1[str(r)]['recall']}" for r in (0, 1, 2)))
            L.append(f"  - correct lost {len(BR[mode]['correct lost'])}, correct gained {len(BR[mode]['correct gained'])}, false positives removed "
                     f"{len(BR[mode]['false positives removed'])}, added {len(BR[mode]['false positives added'])}")
        L.append("")
    (HERE / "RULES_V6.md").write_text("\n".join(L), encoding="utf-8")
    A = ["# v6 rules: exact texts (appendix to RULES_V6.md)", ""]
    for it in items:
        for r in (it.get("final") or {}).get("rules", []):
            A += [f"## {r['id']} ({r['kind']}) — {r['title']}", f"- label (agent): {r['label']}", f"- basis (agent): {r['basis']}",
                  f"- core sentence: {r['core_sentence']}", f"- breaks (agent): {r['breaks']}", f"- falsifier (agent): {r['falsifier']}",
                  f"- false-positive risk (agent): {r['fp_risk']}", f"- replaces existing: {r['replaces_existing']}"]
            for e in r["edits"]:
                A += [f"- EDIT {e['file']} {e['mode']} at: `{clip(e['anchor'], 200)}`", f"  - {e['text'].strip()}"]
            A.append("")
    (HERE / "RULES_V6_APPENDIX.md").write_text("\n".join(A), encoding="utf-8")
    print("written RULES_V6.md, RULES_V6_APPENDIX.md;", len(rows), "rules")


if __name__ == "__main__":
    main()
