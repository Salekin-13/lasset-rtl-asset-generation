"""Views of the structural verdicts (exact matching) for the clustering agents, from pack.json.

  views/structural_fp.md   every false positive (365), one block per element
  views/structural_tp.md   every correct find (84), same fields, for comparison
  views/structural_fn.md   every missed reference entry (27), with the reference 'why' and where the model mentioned it
  concept_yield.json       per model concept: how many listed primaries were correct finds / false positives

  python make_structural_views.py
"""
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CP_KEYS = ("gets value from", "gives value to", "decided by", "decides", "set by instance", "sets instance input")


def short(t, n=260):
    t = " ".join(str(t or "").split())
    return t if len(t) <= n else t[: n - 3] + "..."


def facts_lines(fx):
    if not fx:
        return ["  - (not in the closed set)"]
    cp = "; ".join(f"{k}: {', '.join(v[:6])}{' ...' if len(v) > 6 else ''}" for k, v in fx["counterparts"].items() if k in CP_KEYS)
    return [f"  - kind: {fx['kind']}, {fx['direction'] or fx['type'] or ''}{', record ' + fx['record type'] if fx['record type'] else ''}"
            f"{' (whole record)' if fx['whole record'] else ''}; tags: {', '.join(fx['tags']) or '-'}",
            f"  - counterparts: {cp or '-'}",
            f"  - diagram: member of {', '.join(fx['member of']) or '-'}; arrows: {' | '.join(fx['arrows'][:3]) or '-'}",
            f"  - RTL: {' | '.join(fx['rtl'][:3])}"]


def main():
    pack = json.loads((HERE / "pack.json").read_text(encoding="utf-8"))
    fp, tp, fn = ["# False positives (exact matching): listed as primary, not in the reference", ""], \
        ["# Correct finds (exact matching)", ""], ["# Missed reference entries (exact matching)", ""]
    yield_ = defaultdict(lambda: {"TP": 0, "FP": 0})
    blocks = {}
    for m, d in pack["modules"].items():
        mm = m.replace("neorv32_", "")
        cname = {c["id"]: c["concept"] for c in d["model concepts"]}
        groups = defaultdict(list)       # elements that differ only by an index, listed for the same concepts: one block
        for x in d["FP"]:
            groups[(x["entity"], re.sub(r"\d+", "N", x["element"]), tuple(x["concepts"]))].append(x)
            for c in x["concepts"]:
                yield_[f"{m}:{c}"]["FP"] += 1
        for (ent, pat, _), xs in groups.items():
            x = xs[0]
            s = x["signature"]
            bid = f"F{len(blocks) + 1:03d}"
            blocks[bid] = [y["id"] for y in xs]
            head = (f"## {bid} | {mm} | {ent} | {x['element']} | rows {x['id']}" if len(xs) == 1 else
                    f"## {bid} | {mm} | {ent} | {pat} ({len(xs)} elements: {', '.join(y['element'] for y in xs[:4])}"
                    f"{' ...' if len(xs) > 4 else ''}) | rows {', '.join(y['id'] for y in xs)}")
            fp += [head + (" | 'same role' copies" if any(y["same role copy"] for y in xs) else ""),
                   f"  - where: {s['where']}; role: {s['role']}; record: {s['record']}; influence: {s['influence']}",
                   f"  - listed for: " + "; ".join(f"{c} {cname.get(c, '')}" for c in x["concepts"]),
                   f"  - model's reason: {short(x['model reason'])}"] + facts_lines(x["facts"]) + [""]
        for x in d["TP"]:
            s = x["signature"]
            tp += [f"## {x['id']} | {mm} | {x['entity']} | {x['element']}",
                   f"  - where: {s['where']}; role: {s['role']}; record: {s['record']}; influence: {s['influence']}",
                   f"  - listed for: " + "; ".join(f"{c} {cname.get(c, '')}" for c in x["concepts"])] + facts_lines(x["facts"]) + [""]
            for c in x["concepts"]:
                yield_[f"{m}:{c}"]["TP"] += 1
        rows = {r["row"]: r for r in d["reference rows"]}
        for x in d["FN"]:
            s = x["signature"]
            fn += [f"## {x['entry']} | {mm} | {x['name']}" + (" | ABSENT from this RTL" if x["absent"] else ""),
                   f"  - reference objective: {x['objective']}; reference why: " + " / ".join(short(rows[r]["why"], 300) for r in x["rows"]),
                   f"  - where: {s['where']}; role: {s['role']}; record: {s['record']}; influence: {s['influence']}",
                   f"  - where the model mentioned it: {'; '.join(x['seen in model output']) or 'nowhere'}"]
            for fx in x["facts"]:
                fn += [f"  - entity {fx['entity']}:"] + facts_lines(fx)
            fn.append("")
    (HERE / "views" / "structural_fp.md").write_text("\n".join(fp), encoding="utf-8")
    (HERE / "views" / "structural_tp.md").write_text("\n".join(tp), encoding="utf-8")
    (HERE / "views" / "structural_fn.md").write_text("\n".join(fn), encoding="utf-8")
    (HERE / "fp_blocks.json").write_text(json.dumps(blocks, indent=1), encoding="utf-8")
    assert sum(len(v) for v in blocks.values()) == sum(len(d["FP"]) for d in pack["modules"].values())
    (HERE / "concept_yield.json").write_text(json.dumps(yield_, indent=1), encoding="utf-8")
    # add the yield to each model view
    for m, d in pack["modules"].items():
        p = HERE / "views" / f"model_{m.replace('neorv32_', '')}.md"
        t = p.read_text(encoding="utf-8")
        if "## Phase 2 yield per concept" not in t:
            t += "\n\n## Phase 2 yield per concept (listed primaries, exact matching)\n\n" + "\n".join(
                f"- {c['id']}: {yield_[m + ':' + c['id']]['TP']} correct finds, {yield_[m + ':' + c['id']]['FP']} false positives"
                for c in d["model concepts"])
            p.write_text(t, encoding="utf-8")
    n = sum(len(d["FP"]) for d in pack["modules"].values()), sum(len(d["TP"]) for d in pack["modules"].values()), \
        sum(len(d["FN"]) for d in pack["modules"].values())
    print(f"views written: {n[0]} FP in {len(blocks)} blocks, {n[1]} TP, {n[2]} FN")


if __name__ == "__main__":
    main()
