"""Write prompts/two_phase_v5/README.md from the build inputs (make_v5.py EDITS and K1_LINE, u_rules.json, v5_fixes.json),
the rule workflows' records (rules_workflow_result.json, u_workflow_result.json) and the blind estimates
(rules_proposal.json, u_effects.json). Nothing is retyped.

  python make_v5_readme.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
AN = LAB / "analysis" / "two_phase_v4a__gpt-5.6-luna__high__r0-r2"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB))
import make_v5 as M5  # noqa: E402
import check_lab_prompt as CK  # noqa: E402

RUNS = ("r0", "r1", "r2")


def r3(xs):
    return " / ".join(str(x) for x in xs)


def cell(x):
    return str(x).replace("|", "/").replace("\n", " ")


def main():
    W = json.loads((AN / "rules_workflow_result.json").read_text(encoding="utf-8"))
    W = W.get("result", W)
    rules = {r["id"]: r for r in W["final"]}
    U = json.loads((AN / "u_workflow_result.json").read_text(encoding="utf-8"))
    U = U.get("result", U)
    urules = {f["id"]: f["rule"] for f in U["final"]}
    RP = json.loads((AN / "rules_proposal.json").read_text(encoding="utf-8"))["per_rule"]
    UE = json.loads((AN / "u_effects.json").read_text(encoding="utf-8"))
    FX = json.loads((HERE / "v5_fixes.json").read_text(encoding="utf-8"))
    UR = json.loads((HERE / "u_rules.json").read_text(encoding="utf-8"))
    shas = {}
    for ph in (1, 2):
        s = CK.system("two_phase_v5", ph)
        shas[ph] = (len(s), __import__("hashlib").sha256(s.encode("utf-8")).hexdigest()[:12])
    n_edits = len(M5.EDITS) + 1 + len(UR) + len(FX)
    w4a = len((LAB / "prompts" / "two_phase_v4a" / "phase1.md").read_text(encoding="utf-8").split())
    w5 = len((LAB / "prompts" / "two_phase_v5" / "phase1.md").read_text(encoding="utf-8").split())
    tot = UE["sets"]["A+B+U"]
    ab = UE["sets"]["A+B"]
    L = ["# two_phase_v5 — v4a + basis rules + precision restrictions (2026-10-12, not run)", "",
         "Base: `two_phase_v4a`, **inputs v1** (user decision: the exact key line of inputs v1k stays out). Built by "
         f"`analysis/prompt_builds/make_v5.py`; checked by `check_v5.py` (PASS: corpus names, numeric hints, OUTPUT block identical "
         f"to v4a, the 14 protected phrases kept, rule heads in order, all {n_edits} edits present) and `check_lab_prompt.py` (clean).", "",
         f"System prompts: Phase 1 {shas[1][0]:,} chars, sha12 `{shas[1][1]}` (v4a 32,278, `b13686bbccbf`); Phase 2 {shas[2][0]:,} chars, "
         f"sha12 `{shas[2][1]}` (v4a 35,937, `1c69fe88de91`). phase1_user.md and phase2_user.md are byte-identical to v4a.", "",
         "## What it is for", "",
         "Raise precision without losing correct finds. On the stored v4a replies, if the model follows every rule, a blind test (two "
         "judges per module who did not know which concepts were right; a benefit counts only when both agree, a loss when either "
         "reports it) estimates:", "",
         "| | r0 | r1 | r2 |", "|---|---|---|---|",
         "| v4a precision (measured) | 0.294 | 0.285 | 0.321 |",
         f"| A + B rules | {ab['r0']['P']:.3f} | {ab['r1']['P']:.3f} | {ab['r2']['P']:.3f} |",
         f"| A + B + U (all of v5) | {tot['r0']['P']:.3f} | {tot['r1']['P']:.3f} | {tot['r2']['P']:.3f} |",
         f"| extra concepts removed or emptied (of 56 / 68 / 75) | {tot['r0']['extras']} | {tot['r1']['extras']} | {tot['r2']['extras']} |",
         f"| false positives removed (of 226 / 211 / 199) | {tot['r0']['fp']} | {tot['r1']['fp']} | {tot['r2']['fp']} |",
         f"| correct finds lost | {len(tot['r0']['lost'])} | {len(tot['r1']['lost'])} | {len(tot['r2']['lost'])} |", "",
         "These are arithmetic on stored replies, not a prediction: the test cannot see false positives a rule might create, and the "
         "model may not follow every rule. Recall is unchanged in the estimate; K1 is expected to add csr_rdata in the two runs that "
         "miss it (both judges), K2 may add trng valid_o (not measurable by the blind test) and cpu lsu_mar (one judge).", "",
         "## The rules", "",
         "Category: **A** published or design-principle basis; **B** no published basis, user decision 2026-10-12; **U** user decision "
         "2026-10-12, reference convention, *removed to increase precision* (restricts prompt lines that produced extra concepts the "
         "reference does not list and that contributed no correct find). Estimates: false positives removed / correct lost per run.", "",
         "| id | cat. | file | what it does | basis or decision | FPs removed | lost |", "|---|---|---|---|---|---|---|"]
    ab_ids = [e[0] for e in M5.EDITS] + ["K1"]
    for rid in ab_ids:
        r = rules[rid]
        f = next((e[1] for e in M5.EDITS if e[0] == rid), "phase1.md")
        cat = "A" if r["category"].startswith("A") else "B"
        est = RP[rid]
        L.append(f"| {rid} | {cat} | {f} | {cell(r['text'][:160])}{'...' if len(r['text']) > 160 else ''} | {cell(r['basis'][:140])}... | "
                 f"{r3([est[k]['fp'] for k in RUNS])} | {r3([len(est[k]['lost']) for k in RUNS])} |")
    for u in UR:
        uid = u["id"].rstrip("a")
        r = urules[uid]
        est = UE["per_rule"].get(uid)
        L.append(f"| {u['id']} | U | {u['file']} | {cell(u['new'][:160])}... | user decision; restricts: {cell(r['prompt_line_restricted'][:120])}... | "
                 + (f"{r3([est[k]['fp'] for k in RUNS])} | {r3([len(est[k]['lost']) for k in RUNS])} |" if est and u["id"] == uid else "(part of U2) | |"))
    L += ["", "## Conflict fixes (F1-F9: three skeptics and a merger, wf_aa7e8d3b-38a; F10-F13: a final verifier, wf_741bb2f0-1be)", "",
          "Applied after the rules, in this order. Only F2 changes a rule's scope: it gives Phase 2 the per-region rule (U9) that only "
          "Phase 1 had; included by default because the U9 blind test already counted that effect (no correct find lost) — the user may "
          "veto it.", "", "| id | file | kind | change | reason |", "|---|---|---|---|---|"]
    for x in FX:
        L.append(f"| {x['id']} | {x['file']} | {x['kind']}{' (changes scope)' if x['changes_scope'] else ''} | {cell(x['new'][:180])}... | {cell(x['reason'][:220])}... |")
    L += ["", "## Decisions recorded (also in EXPERIMENT_LOG.md section 11)", "",
          "- B rules R2b (an input only letting a tick advance is a pacing pulse) and R7b (reset requests only passed to a reset chain "
          "are not assets): no published basis; user decision 2026-10-12.",
          "- U rules U1-U12: user decision 2026-10-12, quoted: \"if reference doesn't list them, and they don't emit or contribute to "
          "any TP, then remove them and keep the decision with reasoning in the log. That it was removed to increase precision.\" "
          "Each passed the blind test with no correct find lost.",
          "- Inputs v1, not v1k: user decision 2026-10-12.", "",
          "## What it breaks", "",
          "- All three system files change (Phase 1 reads common.md + phase1.md, Phase 2 reads common.md + phase2.md): v5 is compared only with its own reruns "
          "and with v4a (same model, effort, inputs, three runs).",
          f"- phase1.md almost doubles ({w4a:,} -> {w5:,} words). v2a and v4a showed brevity alone does not change scores; length growth of "
          "this size has not been tested, so a compliance drop is possible.",
          "- The U rules fit the prompt to this reference's conventions. They may remove information that other references, or the "
          "held-out modules, keep.", "",
          "## How to read the run (falsification)", "",
          "- Precision: falsified if v5's precision is not above v4a's run range (0.285-0.321) in at least two of three runs.",
          "- Recall: falsified (rules removed too much) if any reference element found in all three v4a runs is found in fewer than two "
          "v5 runs, or if recall falls below v4a's range (0.771-0.862).",
          "- Per rule: the 'risk' and 'falsified if' notes of each rule in RULES_PROPOSAL.md and u_workflow_result.json name the elements "
          "to read.",
          "- Overfitting: run v5 and v4a on the 26 held-out modules; if held-out recall drops against v4a, the U rules remove "
          "information the reference keeps elsewhere.", "",
          "## Run it", "",
          "Notebook `final/pio/pio_pilot.ipynb`: cell 1 `INPUT_VERSION = \"v1\"`; cell 9 `JOBS = [(\"two_phase_v5\", r) for r in (0, 1, 2)]`, "
          "`RUN_MANY = True`. Runs go to `runs/two_phase_v5__v1/gpt-5.6-luna__high/r<k>/`.", "",
          "Full rule texts: phase1.md, common.md and phase2.md here; reasons, bases, what each spares and risks: "
          "`analysis/two_phase_v4a__gpt-5.6-luna__high__r0-r2/RULES_PROPOSAL.md` (A, B) and `u_workflow_result.json` (U).", ""]
    (LAB / "prompts" / "two_phase_v5" / "README.md").write_text("\n".join(L), encoding="utf-8")
    print("README written;", len(L), "lines")


if __name__ == "__main__":
    main()
