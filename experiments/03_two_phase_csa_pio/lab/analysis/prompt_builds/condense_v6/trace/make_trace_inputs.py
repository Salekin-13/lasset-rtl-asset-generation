"""Inputs for tracing the elements the condensed versions lost (user request 2026-10-13) to the condensed text.

units.md: every condensed unit, with an id, its v6 wording and its condensed wording, and the versions that hold it.
  A unit is one segment of a chunk (a whole rule line, or a sentence part of a very long line) or one core sentence.
  v6a holds the phase1 chunk units, v6b the phase2 chunk units, v6c the core units, v6abc all of them.
evidence/<element>.md: for one lost element, per run of v6 and of each version that lost it: the Phase 1 concepts that
  mention it (as written) and its Phase 2 rows and Not Reported entries (as written), marked found / not found.
targets.json: the elements, why each is traced, the runs, and the units each losing version holds.

Elements traced: the README losses (in all 3 v6 runs, in at most 1 run of the version) and every element found in 2 or
more fewer runs than in v6. Read-only on runs; writes only into this folder.

  python make_trace_inputs.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CV = HERE.parent
LAB = CV.parents[2]
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v6_condensed__gpt-5.6-luna__high__r0-r2"))
import compare_condensed as CC  # noqa: E402
import labkit as K  # noqa: E402


def units():
    M = json.loads((CV / "manifest.json").read_text(encoding="utf-8"))
    acc = json.loads((CV / "accepted_pieces.json").read_text(encoding="utf-8"))
    out = []
    for k, g in (("phase1", "p1"), ("phase2", "p2")):
        for c in M["chunks"][k]:
            new = acc[g].get(c["id"])
            if new is None:
                continue
            for i, (a, b, lay) in enumerate(zip(c["text"].split("\n"), new.split("\n"), c["layout"])):
                if a != b:
                    out.append({"id": f"{c['id']}.{i}", "piece": c["id"], "segment": i, "file": f"{k}.md",
                                "file line": lay[0] + 1, "v6": a, "condensed": b,
                                "versions": ["v6a" if g == "p1" else "v6b", "v6abc"]})
    core = {e["id"]: e["text"] for e in M["core"]}
    for sid, new in acc["core"].items():
        if new != core[sid]:
            out.append({"id": sid, "piece": sid, "file": "phase1.md and phase2.md", "v6": core[sid], "condensed": new,
                        "versions": ["v6c", "v6abc"]})
    return out


def mentions(v, r, mod, name):
    d = CC.run_dir(v, r)
    p1 = K.parse_json(json.loads((d / "phase1" / f"neorv32_{mod}.json").read_text(encoding="utf-8"))["raw"])
    cons = [c for c in (p1.get("Conceptual Assets") or []) if isinstance(c, dict) and name in json.dumps(c)]
    notkept = [c for c in (p1.get("Not Kept") or []) if name in json.dumps(c)]
    rows, notrep = [], []
    f2 = d / "phase2" / f"neorv32_{mod}.json"
    if f2.exists():
        p2 = K.parse_json(json.loads(f2.read_text(encoding="utf-8"))["raw"])
        for w in p2.get("Concept Walks", []) or []:
            if not isinstance(w, dict):
                continue
            rows += [{"walk": w.get("Concept ID"), **a} for a in (w.get("Assets") or []) if isinstance(a, dict) and a.get("Asset RTL") == name]
            notrep += [{"walk": w.get("Concept ID"), "entry": n} for n in (w.get("Not Reported") or []) if name in json.dumps(n)]
    return cons, notkept, rows, notrep


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    U = units()
    md = ["# Condensed units (v6 wording -> condensed wording)", "",
          "Cite a unit by its id. Restoring a unit puts back its v6 wording exactly.", ""]
    for u in U:
        md += [f"## {u['id']} ({u['file']}" + (f", line {u['file line']}" if "file line" in u else "") + f"; in {', '.join(u['versions'])})",
               "- v6: " + u["v6"], "- condensed: " + u["condensed"], ""]
    (HERE / "units.md").write_text("\n".join(md), encoding="utf-8")
    base = CC.collect(CC.BASE)
    X = {v: CC.collect(v) for v in CC.VERSIONS}
    targets = {}
    for v, x in X.items():
        for e in set(base["found"]) | set(x["found"]):
            if (base["found"][e] == 3 and x["found"][e] <= 1) or base["found"][e] - x["found"][e] >= 2:
                targets.setdefault(e, []).append({"version": v.replace("two_phase_", ""), "v6 runs": base["found"][e],
                                                  "version runs": x["found"][e],
                                                  "missed in": [r for r in CC.REPS if e not in x["correct sets"][r]]})
    (HERE / "evidence").mkdir(exist_ok=True)
    for e, losses in sorted(targets.items()):
        mod, name = e.split(":")[0], e.split(":")[1].split("#")[0]
        md = [f"# {e}: element `{name}` of module {mod}", "",
              "Lost: " + "; ".join(f"{l['version']} found it in {l['version runs']} of 3 runs (v6: {l['v6 runs']} of 3), "
                                   f"missed in r{', r'.join(map(str, l['missed in']))}" for l in losses), ""]
        for v in ["two_phase_v6"] + ["two_phase_" + l["version"] for l in losses]:
            sets = base["correct sets"] if v == CC.BASE else X[v]["correct sets"]
            for r in CC.REPS:
                cons, notkept, rows, notrep = mentions(v, r, mod, name)
                md += [f"## {v.replace('two_phase_', '')} r{r}: {'FOUND (primary)' if e in sets[r] else 'NOT FOUND'}", ""]
                md += ["Phase 1 concepts that mention it:", "```json", json.dumps(cons, indent=1, ensure_ascii=False)[:6000], "```"]
                if notkept:
                    md += ["Phase 1 Not Kept entries that mention it:", "```json", json.dumps(notkept, indent=1, ensure_ascii=False)[:2000], "```"]
                md += ["Phase 2 rows for it:", "```json", json.dumps(rows, indent=1, ensure_ascii=False)[:6000], "```"]
                if notrep:
                    md += ["Phase 2 Not Reported entries that mention it:", "```json", json.dumps(notrep, indent=1, ensure_ascii=False)[:2000], "```"]
                md.append("")
        (HERE / "evidence" / f"{e.replace(':', '__').replace('#', '_')}.md").write_text("\n".join(md), encoding="utf-8")
    (HERE / "targets.json").write_text(json.dumps(targets, indent=1), encoding="utf-8")
    n = {v: sum(v in u["versions"] for u in U) for v in ("v6a", "v6b", "v6c", "v6abc")}
    print(f"units: {len(U)} changed units ({n}); elements: {len(targets)}; evidence files written")
    # self-test: the units of v6abc rebuild its phase files from v6's (every changed segment, nothing else)
    M = json.loads((CV / "manifest.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(CV))
    import assemble_condensed as A
    acc = json.loads((CV / "accepted_pieces.json").read_text(encoding="utf-8"))
    full = A.build(M, acc["p1"], acc["p2"], acc["core"])
    disk = {k: (LAB / "prompts" / "two_phase_v6abc" / f"{k}.md").read_text(encoding="utf-8") for k in ("phase1", "phase2")}
    print("self-test: accepted pieces rebuild v6abc on disk:", full == disk)


if __name__ == "__main__":
    main()
