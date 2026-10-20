"""V5_RESULTS.md: two_phase_v5 against v4a (and v4). Numbers come from compare_v5.json, parser_repair.json and
concepts_v5.json (all computed by code this session); causes and per-rule verdicts are copied from the diagnosis workflow
(v5_diagnosis_result.json, wf_1aa19284-7f0: per-module analysts with skeptics, compliance per rule, new false positives,
verdicts with critic and revision).

  python make_v5_report.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = ("r0", "r1", "r2")


def cell(x):
    return str(x).replace("|", "/").replace("\n", " ")


def table(h, rows):
    return ["| " + " | ".join(h) + " |", "|" + "|".join("---" for _ in h) + "|"] + ["| " + " | ".join(cell(x) for x in r) + " |" for r in rows] + [""]


def r3(xs):
    return " / ".join(str(x) for x in xs)


def main():
    C = json.loads((HERE / "compare_v5.json").read_text(encoding="utf-8"))
    PR = json.loads((HERE / "parser_repair.json").read_text(encoding="utf-8"))
    K = json.loads((HERE / "concepts_v5.json").read_text(encoding="utf-8"))
    D = json.loads((HERE / "v5_diagnosis_result.json").read_text(encoding="utf-8"))
    D = D.get("result", D)
    S = C["structural"]
    f = lambda v, x: r3([f"{S[f'{v} {k}'][x]:.3f}" for k in RUNS])  # noqa: E731
    rp = lambda v, x: r3([f"{PR[v]['repaired'][k][x]:.3f}" for k in RUNS])  # noqa: E731
    kc = lambda v, x: r3([K["runs"][f"{v} {k}"][x] if isinstance(K["runs"][f"{v} {k}"][x], int) else f"{K['runs'][f'{v} {k}'][x]:.3f}" for k in RUNS])  # noqa: E731
    L = ["# two_phase_v5 results (gpt-5.6-luna, high, r0-r2, inputs v1)", "",
         "Exact scorer, 109 findable reference elements. Numbers: compare_v5.py, parser_repair.py, concepts_v5.py (this folder). "
         "Causes and verdicts: diagnosis workflow wf_1aa19284-7f0 (v5_diagnosis_result.json); judges wf_ec4c65b4-268.", "",
         "## Answer", "",
         f"- **Precision went up in every run**: {f('v5', 'P')} (v4a {f('v4a', 'P')}); F1 {f('v5', 'F1')} (v4a {f('v4a', 'F1')}).",
         f"- **Recall went down**: {f('v5', 'R')} (v4a {f('v4a', 'R')}). Most of r1's drop is a Phase 2 output-format slip in the bus "
         f"module (rows with the element name in 'concept id'); read with a parser repair, recall is {rp('v5', 'R')} and precision "
         f"{rp('v5', 'P')}. The repair changes no v4 or v4a score.",
         "- **Pre-set tests (v5 README):** precision above v4a's range in all 3 runs: pass. Recall below v4a's range: fails strictly "
         "(r1), passes with the repair. Elements found in every v4a run but in fewer than 2 v5 runs: 6 strictly, 3 with the repair "
         "(cpu lsu_err, lsu_wait, dbi_i): **fails**.",
         f"- **Extra concepts halved**: {kc('v5', 'extra')} (v4a {kc('v4a', 'extra')}); Phase 1 precision {kc('v5', 'P1')} "
         f"(v4a {kc('v4a', 'P1')}); reference concepts found {kc('v5', 'found')} of 77 (v4a {kc('v4a', 'found')}).",
         "- **The blind test was optimistic**: it predicted precision 0.519 / 0.503 / 0.540 and no loss. About half the predicted "
         "false-positive removal happened; Phase 1-only rules leak through Phase 2 (their elements come back as primaries under other "
         "concepts), and some rules were followed partly.", ""]
    L += ["## Structural", ""]
    L += table(["version", "run", "listed", "correct", "false pos.", "precision", "recall", "F1", "bus-record FPs", "concepts"],
               [[v, k, S[f"{v} {k}"]["listed"], S[f"{v} {k}"]["tp"], S[f"{v} {k}"]["fp"], f"{S[f'{v} {k}']['P']:.3f}", f"{S[f'{v} {k}']['R']:.3f}",
                 f"{S[f'{v} {k}']['F1']:.3f}", S[f"{v} {k}"]["bus_fp"], S[f"{v} {k}"]["concepts"]] for v in ("v4", "v4a", "v5") for k in RUNS])
    L += ["With the parser repair (rows whose 'concept id' names a closed-set element are read as that element; each reference entry "
          "matched once): v5 r1 gains bus port_sel, keeper.cnt, keeper.err, keeper.halt, alu_res and state (correct) and 7 false "
          "positives. v3 r2 changes by 1 correct and 3 false positives; v4 and v4a do not change.", ""]
    L += ["## Elements found in a different number of runs (v4a -> v5, strict)", ""]
    L += table(["element", "v4a", "v5"], [[n, a, b] for n, a, b in C["elements"]["fewer"] + C["elements"]["more"]])
    L += ["## Causes (diagnosis, after a skeptic per module)", ""]
    rows = []
    for m in D["loss"]:
        if not m:
            continue
        for e in m["elements"]:
            rows.append([f"{m['module']}:{e['element'].split(' ')[0]}", e["change"][:40], e["cause"], ", ".join(e["rules"])[:120], e["mechanism"][:300]])
    L += table(["element", "change", "cause", "rules", "mechanism (shortened)"], rows)
    L += ["## Per-rule verdicts for the next version (synthesis, critic, revision)", ""]
    L += table(["rule", "verdict", "losses caused", "gains caused", "change"],
               [[r["rule"][:60], r["verdict"], "; ".join(r["losses_caused"])[:200], "; ".join(r["gains_caused"])[:160], r["change"][:300]] for r in D["final"]["rules"]])
    L += ["## General findings (diagnosis)", ""] + [f"- {g}" for g in D["final"]["general"]] + ["", "## Summary (diagnosis)", "", D["final"]["summary"], ""]
    L += ["## Not re-derived here", "",
          "- The code-row precision figures quoted in the verdicts and general findings (for example v5 0.444 / 0.479 / 0.453 with five "
          "code checks) come from the diagnosis agents' scripts in the session scratchpad (revise/). They are not recomputed in this "
          "folder; treat them as leads until a code row is built and self-tested here.", ""]
    (HERE / "V5_RESULTS.md").write_text("\n".join(L), encoding="utf-8")
    print("wrote V5_RESULTS.md")


if __name__ == "__main__":
    main()
