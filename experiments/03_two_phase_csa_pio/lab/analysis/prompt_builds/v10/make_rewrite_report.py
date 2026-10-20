"""REWRITTEN_RULES.md: the 17 rewritten critical rules for review (not assembled into a prompt). Code only.

Per rule: the job, the word changes of the reworded flat text against v9 (word-level diff, so every change is shown
exactly), words v9 -> structured, and the structured Phase 1 and Phase 2 texts as the re-test sends them
(rule_isolation_v9/rule_texts_v10r.json).

  python -B make_rewrite_report.py
"""
import difflib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISOD = HERE.parents[0].parent / "rule_isolation_v9"
sys.path.insert(0, str(HERE))
import make_v10 as MV  # noqa: E402
import make_dossiers as MD  # noqa: E402


def changes(old, new):
    a, b = (old or "").split(), (new or "").split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        ctx = " ".join(a[max(0, i1 - 4):i1])
        out.append(f"…{ctx} **[{' '.join(a[i1:i2]) or '+'}]** → **[{' '.join(b[j1:j2]) or 'removed'}]**")
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    v9 = json.loads((ISOD / "rule_texts.json").read_text(encoding="utf-8"))
    v10 = json.loads((ISOD / "rule_texts_v10r.json").read_text(encoding="utf-8"))
    F = MV.finals()
    L = ["# Rewritten critical rules (v10 drafts, not assembled into a prompt)\n",
         "Built 2026-10-15 by the rewrite workflow (writer, skeptic, reviser per group of rules; evidence in dossiers/), then",
         "trimmed in code: \"Criteria:\" means all criteria must hold, \"Criteria (any of):\" marks alternatives, and an empty",
         "\"Exceptions\" slot is left out. Every text passes the project prompt check (check_rule_draft.py, 0 blockers).\n",
         "Shared procedure (once per phase, in the test context; " + str(len(MV.PROC_V10R_P1.split())) + " words):\n",
         "> " + MV.PROC_V10R_P1 + "\n"]
    tot = [0, 0, 0, 0]
    rows = []
    for g, rules in MD.GROUPS.items():
        for rid in rules:
            t9, t10 = v9[rid], v10[rid]
            w = [len((t9.get(p) or "").split()) for p in ("P1", "P2")] + [len((t10.get(p) or "").split()) for p in ("P1", "P2")]
            tot = [x + y for x, y in zip(tot, w)]
            rows.append(f"| {rid} | {t9['title']} | {'structure only' if rid in MD.STRUCTURE_ONLY else 'reworded + structure'} | "
                        f"{w[0]} → {w[2]} | {w[1]} → {w[3]} |")
    L += ["## Word counts\n", "| Rule | Title | Job | Phase 1 words v9 → v10 | Phase 2 words v9 → v10 |", "|---|---|---|---|---|"] + rows
    L.append(f"| | **All 17** | | **{tot[0]} → {tot[2]} ({tot[2] - tot[0]:+d})** | **{tot[1]} → {tot[3]} ({tot[3] - tot[1]:+d})** |\n")
    for g, rules in MD.GROUPS.items():
        for rid in rules:
            t9, t10, d = v9[rid], v10[rid], F[rid]
            L.append(f"\n---\n\n## {rid} {t9['title']}")
            L.append(f"Why it was rewritten: {MD.WHY[rid]}.\n")
            if rid not in MD.STRUCTURE_ONLY:
                for ph in ("P1", "P2"):
                    if t9.get(ph):
                        old = t9[ph]
                        new = d.get(f"{ph}_flat") or ""
                        if ph == "P2" and d.get("P2_in_place"):
                            new = new + " " + " ".join(d["P2_in_place"].values())
                        ch = changes(old, new)
                        L.append(f"**Word changes, {'Phase 1' if ph == 'P1' else 'Phase 2'} wording** ({len(ch)}):\n")
                        L += [f"- {c}" for c in ch] or ["- none"]
                        L.append("")
            for ph in ("P1", "P2"):
                if t10.get(ph):
                    L.append(f"**{'Phase 1' if ph == 'P1' else 'Phase 2'} wording, as tested:**\n")
                    L.append("```\n" + t10[ph] + "\n```\n")
    (HERE / "REWRITTEN_RULES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("written REWRITTEN_RULES.md;", f"P1 {tot[0]} -> {tot[2]}, P2 {tot[1]} -> {tot[3]}")


if __name__ == "__main__":
    main()
