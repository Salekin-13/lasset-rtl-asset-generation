"""TP_SEPARABILITY.md: why the v2 prompt asks for the remaining extra concepts, which correct concepts share their words and
RTL shape, and whether a testable criterion keeps only the correct ones. Judged by agents (analyst + skeptic per cluster
group, workflows wf_18c9ed67-578 and wf_0f8752e5-3ff); counts below are lengths of their verified lists, taken by code.
'Basis' is my reading of each wording against the project rule (a prompt rule needs a basis in the prompt or a source).

  python make_tp_report.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent / "two_phase_v2__gpt-5.6-luna__high__r0-r2"
sys.path.insert(0, str(HERE.parent / "two_phase_v1__gpt-5.4__high__r0" / "failure_patterns"))
from make_report_md import table  # noqa: E402

BASIS = {"CX7": "prompt-internal (A4/A5; ASSET_DEFINITION row 60)", "CX2": "prompt-internal (A2; line 14's 'an element holds or carries')",
         "CX6": "prompt-internal (steps 3 and 6)", "CX14": "prompt-internal (same reasoning as C1n, A4)", "CX16": "prompt-internal (step 3)",
         "none": "prompt-internal, but it narrows step 2's decision sentence", "CX10": "your decision: contradicts line 17 (overrides act on it)",
         "CX11": "your decision: extends the clock/reset rule A1", "CX12": "your decision: P3164 p15 says status registers may be assets",
         "CX15": "none: P3164 p17 says a memory array is an asset; evaluation filter only", "CX3": "-", "CX13": "-", "CX8": "-", "CX17": "-"}


def main():
    V = json.loads((HERE / "tp_verified.json").read_text(encoding="utf-8"))
    O = json.loads((AN / "concept_overlap_v1_v2.json").read_text(encoding="utf-8"))
    X, names = O["extra_by_cluster"]["v2"], O["cx_names"]
    rows, detail = [], []
    order = {"separable without losing correct concepts": 0, "separable only by losing correct concepts": 1, "not separable by any RTL-observable criterion": 2}
    cl = [c for v in V.values() for c in v["clusters"]]
    for c in sorted(cl, key=lambda c: (order[c["verdict"]], c["cx"])):
        cr = [x for x in c["criteria"] if x["extras_excluded"]]
        best = min(cr, key=lambda x: (len(x["tps_excluded"]), -len(x["extras_excluded"]))) if cr else None
        n = "/".join(str(X.get(c["cx"], {}).get(k, 0)) for k in ("r0", "r1", "r2"))
        reach = f"{len(best['extras_excluded'])} of {len(best['extras_excluded']) + len(best['extras_kept'])}" if best else "-"
        rows.append([f"{c['cx']} {names.get(c['cx'], 'new in v2')}", n, len(c["tp_siblings"]), c["verdict"], reach,
                     len(best["tps_excluded"]) if best else "-", BASIS.get(c["cx"], "?")])
        detail += [f"### {c['cx']} {names.get(c['cx'], 'new in v2')}", "",
                   f"- **Why the prompt asks for it:** {c['why_asked']}",
                   f"- **Licensing lines:** {'; '.join(x['line'] + ' \"' + x['quote'][:140] + '\"' for x in c['licensing'])}",
                   f"- **Correct concepts with the same words and shape:** {'; '.join(s['concept'] + ' (' + s['reference_concept'] + ')' for s in c['tp_siblings'])}",
                   f"- **Best criterion:** {best['criterion'] if best else '-'}",
                   f"- **Narrowed wording:** {c['narrowed_wording'] or '-'}",
                   f"- **Explanation:** {c['explanation']}", ""]
    L = ["# Why the v2 prompt asks for the remaining extra concepts, and whether wording can keep only the correct ones", "",
         "Judged by agents (an analyst and a skeptic per cluster group); the counts are lengths of their verified lists. "
         "'Extras out' = extra concepts, as the analysts listed them (some lists group a concept across runs), that the best criterion excludes; 'correct lost' = correct concepts of "
         "the same shape it would also exclude. A result here is fitted on the same 15 modules and three runs: before any "
         "wording enters a prompt, it needs a blind boundary check like the one done for v3, and ideally held-out modules.", ""]
    L += table(["cluster", "v2 extras r0/r1/r2", "correct siblings", "verdict", "extras out (of those the analysts listed)", "correct lost", "basis of the wording"], rows)
    L += ["## Detail per cluster", ""] + detail
    (HERE / "TP_SEPARABILITY.md").write_text("\n".join(L), encoding="utf-8")
    for r in rows:
        print(" | ".join(str(x) for x in r))


if __name__ == "__main__":
    main()
