"""Blind per-module views of v4a's concepts for the rule boundary check, and the hidden key the workflow code uses.

views_blind/<module>.md   every concept of r0-r2 (unit, name, information, rubric reason, anchors, Phase 2 primaries and
                          secondaries) and each run's 'considered, not kept' list. No judge verdict, no reference count,
                          no correct/false marks.
boundary_key.json         per concept "<module>:<run>:<Cn>": extra (judges' verdict), and each primary's status:
                          tp_sole (correct, no other concept of the run lists it as primary), tp (correct, also elsewhere),
                          fp_only (false positive listed only here), fp_shared (false positive also under other concepts).
Self-test: no blind view contains the phrases our tooling writes ('in the reference', 'reference element/concept',
'false positive', 'correct find', 'of which', RC ids); the key's fp_only counts equal concepts_all.json's.

  python make_blind_views.py
"""
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = ("r0", "r1", "r2")


def main():
    P = json.loads((HERE / "pack3.json").read_text(encoding="utf-8"))
    CA = {(c["module"], c["run"], c["id"]): c for c in json.loads((HERE / "concepts_all.json").read_text(encoding="utf-8"))}
    out = HERE / "views_blind"
    out.mkdir(exist_ok=True)
    key = {}
    for m, d in P["modules"].items():
        s = m.replace("neorv32_", "")
        L = [f"# {m}: Phase 1 concepts of three independent runs (r0, r1, r2) of the same prompt", "",
             "Each concept: the unit, its name and information, the rubric reason, its anchor ports, and the elements Phase 2 "
             "labelled primary and secondary under it. Then each run's 'considered, not kept' list.", ""]
        for k in RUNS:
            r = d["runs"][k]
            lab = defaultdict(lambda: defaultdict(list))
            for kk, lv in r["labels"].items():
                for l, cs in lv.items():
                    for c in cs:
                        lab[c][l].append(kk.split("|", 1)[1])
            L += [f"## Run {k}", ""]
            for c in r["concepts"]:
                cid = c["id"]
                L += [f"### {k}:{cid} {c['concept']} (unit {c.get('unit')})",
                      f"- information: {c.get('information', '')}",
                      f"- rubric reason: {c.get('rubric reason', '')}",
                      f"- objectives: {', '.join(c.get('objectives', []))}; enters through: {', '.join(c.get('enters through', [])) or '-'}; "
                      f"leaves through: {', '.join(c.get('leaves through', [])) or '-'}",
                      f"- Phase 2 primary: {', '.join(sorted(lab[cid]['primary'])) or '-'}",
                      f"- Phase 2 secondary: {', '.join(sorted(lab[cid]['secondary'])) or '-'}", ""]
                ca = CA[(s, k, cid)]
                st = {}
                for e in ca["primaries"]:
                    if e in ca["correct"]:
                        st[e] = "tp_sole" if e in ca["sole correct"] else "tp"
                    elif e in ca["fp only"]:
                        st[e] = "fp_only"
                    elif e in ca["fp shared"]:
                        st[e] = "fp_shared"
                    else:
                        st[e] = "other"   # listed as primary but neither correct nor a counted false positive (e.g. absent name)
                key[f"{s}:{k}:{cid}"] = {"extra": ca["verdict"] == "no reference counterpart", "verdict": ca["verdict"], "prim": st}
            L += [f"### Run {k}: considered, not kept", ""]
            L += [f"- {x.get('unit', '')}: {x.get('concept', '')}: {x.get('reason', '')}" for x in r["not kept"]] or ["- (none)"]
            L += [""]
        text = "\n".join(L)
        # phrases our own tooling writes (the model's own text may say "correctly" or "timing reference")
        bad = re.findall(r"(?i)in the reference|reference element|reference concept|false positive|correct find|\bRC\d+\b|of which", text)
        assert not bad, (s, bad[:5])
        (out / f"{s}.md").write_text(text, encoding="utf-8")
    # self-test against concepts_all.json
    for kk, v in key.items():
        s, k, cid = kk.split(":")
        assert sum(1 for x in v["prim"].values() if x == "fp_only") == len(CA[(s, k, cid)]["fp only"]), kk
    (HERE / "boundary_key.json").write_text(json.dumps(key, indent=0), encoding="utf-8")
    other = sum(1 for v in key.values() for x in v["prim"].values() if x == "other")
    print(f"blind views for {len(P['modules'])} modules; key for {len(key)} concepts; primaries marked 'other': {other}")


if __name__ == "__main__":
    main()
