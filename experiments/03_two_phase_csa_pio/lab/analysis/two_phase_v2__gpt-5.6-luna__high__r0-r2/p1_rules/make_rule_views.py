"""Blind concept views for the v3 rule-effect judges (two_phase_v2, gpt-5.6-luna, high, r0-r2).

One file per module, rule_views/<module>.md: every kept Phase 1 concept of r0-r2 with its text, rubric answers and reason,
anchors, cited lines, and the Phase 2 primary and secondary elements. No verdict, no reference hit, no false-positive count.
Self-test: every concept id of pack3.json appears once per run, and no line mentions the reference.

  python make_rule_views.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
RUNS = ("r0", "r1", "r2")


def main():
    P = json.loads((V2 / "pack3.json").read_text(encoding="utf-8"))
    out = HERE / "rule_views"
    out.mkdir(exist_ok=True)
    ids = {}
    for m, d in P["modules"].items():
        s = m.replace("neorv32_", "")
        L = [f"# Three runs of a model on {m}: kept conceptual assets", ""]
        ids[s] = {}
        for k in RUNS:
            r = d["runs"][k]
            L += [f"## Run {k}", ""]
            ids[s][k] = [c["id"] for c in r["concepts"]]
            for c in r["concepts"]:
                prim = [key.split("|", 1)[1] for key, lv in r["labels"].items() if c["id"] in lv.get("primary", [])]
                sec = [key.split("|", 1)[1] for key, lv in r["labels"].items() if c["id"] in lv.get("secondary", [])]
                L += [f"### {k}:{c['id']} {c['concept']} (unit {c['unit']})",
                      f"- information: {c['information']}",
                      f"- rubric yes: {', '.join(q for q, a in c['rubric'].items() if a == 'yes') or '-'}; reason: {c['rubric reason']}",
                      f"- objectives: {', '.join(c.get('objectives', [])) or '-'}; enters through: {', '.join(c.get('enters through', [])) or '-'}; "
                      f"leaves through: {', '.join(c.get('leaves through', [])) or '-'}",
                      f"- entry lines: {c.get('entry lines', [])}; held lines: {c.get('held lines', [])}; exit lines: {c.get('exit lines', [])}",
                      f"- Phase 2 primary: {', '.join(prim) or '-'}",
                      f"- Phase 2 secondary: {', '.join(sec) or '-'}", ""]
        t = "\n".join(L)
        for k in RUNS:
            for cid in ids[s][k]:
                assert t.count(f"### {k}:{cid} ") == 1, (s, k, cid)
        for leak in ("in the reference", "reference concept", "no reference counterpart", "false positive", "verdict"):
            assert leak not in t.lower(), (s, leak)
        (out / f"{s}.md").write_text(t, encoding="utf-8")
    (HERE / "rule_view_ids.json").write_text(json.dumps(ids), encoding="utf-8")
    print({s: sum(len(v) for v in r.values()) for s, r in ids.items()}, "total", sum(len(v) for r in ids.values() for v in r.values()))


if __name__ == "__main__":
    main()
