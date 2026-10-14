"""Evidence packs for attributing v5g-vs-v5f changes (read-only on stored replies; nothing is sent).

Elements included, per module:
  - reference entries whose share of runs found differs (v5g of 3 vs v5f of 6; compare_v5g.json "element shares");
  - false-positive elements (primary, not a findable reference name) whose primary share moved by 0.5 or more
    (v5g share of 3 runs minus v5f share of 6 runs).
For each element and each of the 9 runs (v5g r0-r2, v5f r0-r5): primary in the scorer file or not; every Phase 2 asset
row naming it (concept, label, Functionality, Justification); Not Reported entries; the walk's No Primary Reason;
Phase 1 concepts whose text names it. v5g r0 bus is marked: its Phase 2 reply wrote all rows inside points (format slip).
Writes <short>.md and changes.json. Self-test: shares recomputed here equal compare_v5g.json for the reference entries.

  python make_change_packs.py
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent
LAB = AN.parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB.parents[2] / "src"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402

RUNS = [("v5g", "two_phase_v5g", r) for r in (0, 1, 2)] + [("v5f", "two_phase_v5f", r) for r in range(6)]


def has(name, text):
    return bool(re.search(r"(?<![\w.])" + re.escape(name) + r"(?!\w)(?!\.\w)", text or ""))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import eval_assets as ea
    with CH.at_root():
        refs = ea.load_refs()["gt"]
    cmp = json.loads((AN / "compare_v5g.json").read_text(encoding="utf-8"))["element shares"]
    data = {}
    for m in CH.tuning_modules():
        short = m.replace("neorv32_", "")
        names = {n for (_, n) in CH.closed_names(m)}
        ref = [n for n, _ in refs[m] if n in names]
        per = {}
        for k, v, r in RUNS:
            run = CH.run_dir(v, "gpt-5.6-luna", r, "high")
            assets = json.loads((run / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]
            p1 = K.parse_json(json.loads((run / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
            p2 = K.parse_json(json.loads((run / "phase2" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
            per[(k, r)] = (assets, p1, p2)
        # shares
        prim = defaultdict(Counter)
        for (k, r), (assets, _, _) in per.items():
            for el in {x["Asset RTL"] for x in assets}:
                prim[el][k] += 1
        tp_found = defaultdict(Counter)
        for (k, r), (assets, _, _) in per.items():
            listed = Counter(x["Asset RTL"] for x in assets)
            kth = Counter()
            for n in ref:
                kth[n] += 1
                if listed[n] > 0:
                    listed[n] -= 1
                    tp_found[f"{short}:{n}#{kth[n]}"][k] += 1
        chosen = []
        kth = Counter()
        for n in ref:
            kth[n] += 1
            key = f"{short}:{n}#{kth[n]}"
            g, f = tp_found[key]["v5g"], tp_found[key]["v5f"]
            assert (g, f) == (cmp.get(key, {}).get("v5g of 3", 0), cmp.get(key, {}).get("v5f of 6", 0)), f"self-test {key}"
            if abs(g / 3 - f / 6) > 1e-9:
                chosen.append(("reference", n, g, f))
        for el, c in prim.items():
            if el in ref:
                continue
            if abs(c["v5g"] / 3 - c["v5f"] / 6) >= 0.5:
                chosen.append(("false positive", el, c["v5g"], c["v5f"]))
        if not chosen:
            continue
        out = [f"# {short}: elements whose share changed (v5g 3 runs vs v5f 6 runs)", "",
               "Both versions have the same Phase 1 prompt and the same reply format; v5g adds Phase 2 sentences (see",
               "analysis/two_phase_v5f__gpt-5.6-luna__high__r0-r2/consistency/inserts_compressed.md, ids I1-I26, FRAME).",
               "'primary' = listed in the scorer file for that run." + (" NOTE: v5g r0 bus wrote all Phase 2 asset rows inside its points"
                                                                        " (format slip): the scorer read none." if short == "bus" else ""), ""]
        for kind, el, g, f in chosen:
            out.append(f"## {el} ({kind}): v5g {g}/3, v5f {f}/6")
            for k, v, r in RUNS:
                assets, p1, p2 = per[(k, r)]
                isp = any(x["Asset RTL"] == el for x in assets)
                cname = {c.get("Concept ID"): c.get("Concept Name") for c in p1.get("Conceptual Assets", []) if isinstance(c, dict)}
                rows = []
                for w in p2.get("Concept Walks", []) or []:
                    if not isinstance(w, dict):
                        continue
                    cid = w.get("Concept ID")
                    pools = [("walk", w.get("Assets") or [])] + [("inside point", p.get("Assets") or []) for p in (w.get("Points") or []) if isinstance(p, dict) and isinstance(p.get("Assets"), list)]
                    for where, lst in pools:
                        for a in lst:
                            if isinstance(a, dict) and (a.get("Asset RTL") == el or el in (a.get("Same Role") or [])):
                                rows.append(f"{cid} '{cname.get(cid)}' {a.get('Label')}{' [' + where + ']' if where != 'walk' else ''}: "
                                            f"F: {a.get('Functionality')} | J: {a.get('Justification')}")
                    for x in w.get("Not Reported") or []:
                        if isinstance(x, dict) and x.get("Element RTL") == el:
                            rows.append(f"{cid} NOT REPORTED: {x.get('Why Not Reported')}")
                    if any(el in r_ for r_ in rows[-3:]) and w.get("No Primary Reason"):
                        rows.append(f"{cid} no primary reason: {w.get('No Primary Reason')}")
                p1hits = [f"{c.get('Concept ID')} '{c.get('Concept Name')}'" for c in p1.get("Conceptual Assets", [])
                          if isinstance(c, dict) and has(el, json.dumps(c, ensure_ascii=False))]
                nk = [x.get("Candidate Name") for x in p1.get("Not Kept", []) if isinstance(x, dict) and has(el, json.dumps(x, ensure_ascii=False))]
                out.append(f"- {k} r{r}: {'PRIMARY' if isp else 'not primary'}; Phase 1 concepts naming it: {', '.join(p1hits) or '-'}"
                           + (f"; Not Kept naming it: {nk}" if nk else ""))
                out += [f"    - {x}" for x in rows] or ["    - no Phase 2 row names it"]
            out.append("")
        (HERE / f"{short}.md").write_text("\n".join(out), encoding="utf-8")
        data[short] = [{"kind": k, "element": e, "v5g of 3": g, "v5f of 6": f} for k, e, g, f in chosen]
        print(f"{short}: {sum(1 for c in chosen if c[0] == 'reference')} reference, {sum(1 for c in chosen if c[0] != 'reference')} false-positive elements")
    (HERE / "changes.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    print("self-test (shares = compare_v5g.json): PASS")


if __name__ == "__main__":
    main()
