"""Write ERROR_ANALYSIS.md from the workflow output (fp_analysis_workflow.json) and the code check (rule_check.py)."""
import io
import json
import sys
from collections import defaultdict
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rule_check as RC  # noqa: E402

d = json.loads((HERE / "fp_analysis_workflow.json").read_text(encoding="utf-8"))
buf = io.StringIO()
with redirect_stdout(buf):
    RC.main()
code_check = buf.getvalue()

over = [defaultdict(set), defaultdict(set)]
for i, o in enumerate(d["overlap"]):
    for x in (o or {}).get("tp_in_bucket", []):
        over[i][x["bucket_id"]].add(x["tp_id"])
sup = [defaultdict(set), defaultdict(set)]
for i, s in enumerate(d["suppression_tp"]):
    for j in (s or {}).get("judgements", []):
        for r in j["suppressed_by"]:
            sup[i][r].add(j["id"])
supfp = defaultdict(set)
for s in d["suppression_fp"]:
    for j in (s or {}).get("judgements", []):
        for r in j["suppressed_by"]:
            supfp[r].add(j["id"])
rules = d["rules"]["rules"]
rule_of = defaultdict(list)
for r in rules:
    for b in r["bucket_ids"]:
        rule_of[b].append(r["rule_id"])

L = ["# Error analysis: two-phase PIO prompt, gpt-5.4, full run on the 15 test modules (2026-10-11)", "",
     "Run: `experiments/03_two_phase_csa_pio/lab/runs/two_phase_v1__v1/gpt-5.4__high/r0`. Strict scorer, 111 reference entries (exact).",
     "Listed 449: 85 TP, 364 FP; 26 FN. P 0.189, R 0.766. Same modules, final prompt on gpt-5.4: P 0.385-0.418,",
     "R 0.784-0.847 (208-239 listed). Cost of this run: USD 27.35 (pilot included).", "",
     "Method: 7 agents read every FP with the model's own reasons (open coding), one agent clustered the codes and a",
     "critic corrected the clusters (every FP in exactly one bucket), two independent judges checked every TP against",
     "each bucket, one agent drafted the rules, then two judges applied the rules to every TP and two to every FP.",
     "A separate code check (rule_check.py, self-tested) applied the mechanical version of each rule to the stored",
     "rows and to every reference entry of the 15 tuning and 26 held-out modules.", "",
     "## 1. FP buckets", "",
     "| Bucket | FPs | Cause | TPs meeting the definition (both judges / either) | Rule |", "|---|---|---|---|---|"]
for b in d["clustering"]["buckets"]:
    bi = b["bucket_id"]
    L.append(f"| {bi} {b['name']} | {len(b['member_ids'])} | {b['cause']} | {len(over[0][bi] & over[1][bi])} / "
             f"{len(over[0][bi] | over[1][bi])} | {', '.join(rule_of[bi]) or '-'} |")
L += ["", "Per bucket: definition, mechanical test, why the model flags these rows.", ""]
for b in d["clustering"]["buckets"]:
    L += [f"### {b['bucket_id']} {b['name']} ({len(b['member_ids'])} FPs, {b['cause']})", "",
          f"- Definition: {b['definition']}", f"- Mechanical test: {b['mechanical_test']}",
          f"- Why the model flags them: {b['why_the_model_flags_these']}",
          f"- Examples: {', '.join(b['example_ids'][:6])}", ""]
L += ["## 2. Drafted negative constraints", "",
      "`where it belongs`: a rule with a published basis can go in the prompt; a rule whose only basis is that the",
      "reference leaves something out is a reference convention and belongs in the evaluation layer as a code filter",
      "(standing project rule).", ""]
for r in rules:
    L += [f"### {r['rule_id']} (buckets {', '.join(r['bucket_ids'])}) -> {r['where_it_belongs']}", "",
          f"**Prompt text.** {r['prompt_text']}", "", f"**Carve-outs.** {r['carve_outs']}", "",
          f"**Placement.** {r['placement']}", "", f"**Basis.** {r['basis']}", "",
          f"**Mechanical version.** {r['mechanical_version']}", "",
          f"**Expected effect (drafting agent).** FP: {r['expected_fp_removed']} TP risk: {r['tp_at_risk']}", ""]
L += ["## 3. Check that the rules do not suppress TPs", "",
      "### 3a. Agent judges applying the wording (with carve-outs) to every TP and FP", "",
      "| Rule | TPs suppressed (both judges / either) | FPs suppressed |", "|---|---|---|"]
for r in rules:
    k = r["rule_id"]
    L.append(f"| {k} | {len(sup[0][k] & sup[1][k])} / {len(sup[0][k] | sup[1][k])} {sorted(sup[0][k] | sup[1][k])} | {len(supfp[k])} |")
L += ["", "### 3b. Code check of the mechanical versions (rule_check.py)", "", "```", code_check.rstrip(), "```", "",
      "## 4. Limits", "",
      "- The post-hoc score filters the stored replies; it is not a re-run. With the rules in the prompt the model may",
      "  list other elements in place of the removed ones, or apply a rule loosely. Only a re-run measures the change.",
      "- The rules were found on the same 15 modules they are checked on. The reference-exposure check covers the 26",
      "  held-out modules too, but the held-out precision and recall are only measured by a held-out run.",
      "- The verdicts follow one reference list; buckets marked 'reference convention' are mismatches with its choices,",
      "  not proven mistakes."]
(HERE / "ERROR_ANALYSIS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print(HERE / "ERROR_ANALYSIS.md", len(L), "lines")
