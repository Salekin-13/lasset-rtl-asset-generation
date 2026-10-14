"""Barrier and checkpoint 1b (code), after stage C1.

1. Which confirmed patterns get a fix item: a confirmed pattern whose fix_route is not "none: ...", and a confirmed
   pattern with fix_route "none: ..." for which a Skeptic B file (first round or re-check) found a separating condition
   ("the pattern gets a fix after all"). Not confirmed and not checked patterns and the unexplained lists get none.
2. Merge: confirmed patterns that blame the same prompt sentence (the same file and line of common.md, phase1.md or
   phase2.md, or the same non-empty rule id) become one fix item (union-find, so the merge is transitive). The merged
   item keeps every element-run of each pattern. Every merge is printed with the shared sentence.
3. The scope cut test: patterns made only of intermittent items are marked; the cut is applied only when asked
   (--scope-cut) and only to fix items whose every pattern is intermittent-only.
4. Cost: the analysts' (and every role's) measured tokens and tool calls from C1's run record; tokens still to come =
   per fix item 1 drafter + 2 skeptics + 1 reviser + 2 re-check skeptics, plus the conflict check, 30 blind judges, the
   report writer and the report skeptic. Skeptic and reviser tokens: this run's C1 means; drafter, conflict, blind:
   budget_full.py's past means; the report writer as a reviser, the report skeptic as a skeptic.
Writes C2/<FX>/item.json per fix item and merge_1b.json.

  python merge_1b.py <C1 run id> [--scope-cut] [--write]
"""
import glob
import io
import contextlib
import json
import os
import statistics as stx
import sys
from collections import defaultdict

import common_fa as F
import checkpoint as CP


def norm_rule(x):
    x = (x or "").strip()
    return "" if x.lower() in ("", "none", "n/a", "-", "not applicable") else x


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    run_id = sys.argv[1]
    st = json.loads((F.HERE / "c1_status.json").read_text(encoding="utf-8"))
    recs = {}
    for g in json.loads((F.HERE / "c1_args.json").read_text(encoding="utf-8"))["groups"]:
        f = F.HERE / "C1" / g / "revised.json"
        if f.exists():
            for p in json.loads(f.read_text(encoding="utf-8"))["patterns"]:
                recs[p["id"]] = (g, p)
    elig, why = [], {}
    for pid, s in st["patterns"].items():
        if s["status"] != "confirmed":
            continue
        route = s["fix_route"]
        if not route.startswith("none"):
            elig.append(pid)
            why[pid] = f"fix route: {route}"
        elif s["separating conditions found by Skeptic B"]:
            elig.append(pid)
            why[pid] = f"no prompt fix ({route}), but Skeptic B found a separating condition: gets a fix after all"
    # union-find on shared sentences
    parent = {p: p for p in elig}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    keys = defaultdict(list)
    for pid in elig:
        for b in recs[pid][1]["blamed_sentences"]:
            keys[("line", b["file"], b["line"])].append(pid)
            if norm_rule(b.get("rule_id")):
                keys[("rule", norm_rule(b["rule_id"]))].append(pid)
    merges = []
    for k, ps in keys.items():
        for p in ps[1:]:
            if find(p) != find(ps[0]):
                merges.append({"shared": k, "patterns": [ps[0], p]})
                parent[find(p)] = find(ps[0])
    comp = defaultdict(list)
    for p in elig:
        comp[find(p)].append(p)
    items = []
    lines_of = {}
    for f in ("common.md", "phase1.md", "phase2.md"):
        lines_of[f] = (F.PROMPTS / f).read_text(encoding="utf-8").splitlines()
    for n, (root, ps) in enumerate(sorted(comp.items(), key=lambda kv: -sum(len(st["patterns"][p]["items"]) for p in kv[1])), 1):
        fxid = f"FX{n:02d}"
        tgt = sorted({i for p in ps for i in st["patterns"][p]["items"]})
        shared = sorted({(b["file"], b["line"]) for p in ps for b in recs[p][1]["blamed_sentences"]})
        items.append({
            "id": fxid,
            "title": " + ".join(recs[p][1]["name"] for p in ps),
            "findings": [{"id": p, "group": recs[p][0], "record file": F.rel(F.HERE / "C1" / recs[p][0] / "revised.json"),
                          "step answers": F.rel(F.HERE / "C1" / recs[p][0] / "analysis.md"),
                          "evidence pack": F.rel(F.HERE / "packs" / "group" / (json.loads((F.HERE / "c1_args.json").read_text(encoding="utf-8"))["groups"][recs[p][0]]["pack"].split("\\")[-1])),
                          "name": recs[p][1]["name"], "fix_route": recs[p][1]["fix_route"], "why it gets a fix": why[p],
                          "separating conditions found by Skeptic B": st["patterns"][p]["separating conditions found by Skeptic B"]} for p in ps],
            "blamed sentences (v7 file:line, quoted)": [f"{F.rel(F.PROMPTS / f)}:{l}: {lines_of[f][l - 1] if 0 < l <= len(lines_of[f]) else '(line does not exist)'}" for f, l in shared],
            "target items": tgt,
            "target counts per run": {r: sum(1 for i in tgt if i.endswith(":" + r)) for r in F.RUNS},
            "target kinds": {"misses": sum(1 for i in tgt if i.startswith("M:")), "false positives": sum(1 for i in tgt if i.startswith("F:"))},
            "same-shape correct finds to keep (from the finding records)": sorted({s["key"] for p in ps for s in recs[p][1]["same_shape_correct"]}),
            "only intermittent items": all(st["patterns"][p]["only intermittent"] for p in ps),
            "stage B verdict files": sorted({F.rel((F.HERE / "stageB" / f"final_{i.split(':')[1]}.json") if (F.HERE / "stageB" / f"final_{i.split(':')[1]}.json").exists()
                                                   else (F.HERE / "stageB" / f"judge1_{i.split(':')[1]}.json")) for i in tgt}),
            "correct finds file": F.rel(F.HERE / "correct_finds.json"),
        })
    cut = "--scope-cut" in sys.argv
    kept = [x for x in items if not (cut and x["only intermittent items"])]
    dropped = [x for x in items if cut and x["only intermittent items"]]
    # cost
    f = glob.glob(os.path.expanduser(f"~/.claude/projects/*/*/workflows/{run_id}.json"))
    rec = json.loads(open(f[0], encoding="utf-8").read())
    ag = [a for a in rec["workflowProgress"] if a.get("type") == "workflow_agent" and a.get("tokens") is not None]
    roles = defaultdict(list)
    for a in ag:
        lab = (a.get("label") or "").split(":")[0]
        roles[lab].append(a)
    meas = {k: {"n": len(v), "tokens mean": round(stx.mean(a["tokens"] for a in v)), "tool calls median": stx.median(a.get("toolCalls") or 0 for a in v)}
            for k, v in roles.items()}
    hi, _ = CP.budget()
    with contextlib.redirect_stdout(io.StringIO()):
        g = {"__name__": "bf"}
        exec(compile(CP.BF.read_text(encoding="utf-8"), str(CP.BF), "exec"), g)
    R = g["R"]
    sk = stx.mean([a["tokens"] for k in ("skepticA", "skepticB", "recheckA", "recheckB") for a in roles.get(k, [])] or [R["skeptic"]["tok"]])
    rv = stx.mean([a["tokens"] for a in roles.get("revise", [])] or [R["reviser"]["tok"]])
    per_fix = R["drafter"]["tok"] + 2 * sk + rv + 2 * sk
    rest = R["conflict"]["tok"] + 30 * R["blind"]["tok"] + rv + sk
    left = (len(kept) * per_fix + rest) / 1e6
    out = {"eligible patterns": {p: why[p] for p in elig}, "merges": [{"shared": list(m["shared"]), "patterns": m["patterns"]} for m in merges],
           "fix items": [{k: x[k] for k in ("id", "title", "target counts per run", "target kinds", "only intermittent items")} | {"findings": [y["id"] for y in x["findings"]]} for x in items],
           "scope cut applied": cut, "dropped by the scope cut": [x["id"] for x in dropped],
           "C1 measured per role": meas, "C1 totalTokens": rec.get("totalTokens"), "C1 durationMs": rec.get("durationMs"),
           "per fix item tokens (M)": round(per_fix / 1e6, 2), "after C2 (D, E, F) tokens (M)": round(rest / 1e6, 2),
           "tokens still to come (M)": round(left, 1)}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    if "--write" in sys.argv:
        for x in kept:
            d = F.HERE / "C2" / x["id"]
            d.mkdir(parents=True, exist_ok=True)
            (d / "item.json").write_text(json.dumps(x, indent=1, ensure_ascii=False), encoding="utf-8")
        (F.HERE / "merge_1b.json").write_text(json.dumps(out | {"items": items}, indent=1, ensure_ascii=False), encoding="utf-8")
        print("written:", [x["id"] for x in kept])


if __name__ == "__main__":
    main()
