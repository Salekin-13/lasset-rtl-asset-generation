"""Stage A (code) of the v10 failure analysis: two_phase_v10 on the Claude executor (claude_chain.py), the 14 heldout_v2
modules, runs r0-r2. Read-only on runs, prompts and inputs; writes facts.json and packs/<module>/ for the analysts.
Never compare these numbers with luna runs (another executor).

Units (as in transitions.py):
  - reference occurrence "module:name#k" (the k-th reference entry with that name; findable = its name is in the
    module's closed set): found in 0-3 runs (exact scorer of compare_v8.py: names equal, each entry used once);
  - false-positive name "module:name": a listed primary that is not a reference find, listed in 0-3 runs.
Per run and pooled: TP (correct), FP (listed - correct), FN (findable - correct); precision = TP / listed, recall =
TP / findable.
Per missed occurrence-run: the stage where it is lost (transitions.where_lost: secondary, not reported, Not Kept,
parent or field listed, anchor only, lines only, never named) with the reply's own reasons.
Per false-positive name-run: the concepts it is primary under and the Phase 2 justification; whether the same run's
Phase 1 Not Kept rows name it (a cross-phase contradiction); flags of the v7 code detectors P1-P4 (the testable
condition of a v7 bar holds for it, read from the reply and the RTL only: the prompt already bars it).
Per found occurrence: runs found and the concepts it is primary under.

Self-tests (nothing is written if one fails):
  1. the scorer: compare_v8.selftest on the stored luna v7 runs (92/89/86 of 146/158/131);
  2. the detectors: the P1-P4 copies on the v7 tuning replies equal their check_out.json (as rule_consistency.py);
  3. sums: per run, found occurrence-runs = correct, FP name-runs = listed - correct, miss stages = FN;
  4. hand-read: each run's listed names re-read from the assets files by a separate plain json read equal the scorer's.

  python -B facts_v10c.py
"""
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
for p in (LAB, LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2",
          LAB / "analysis" / "heldout_versions__gpt-5.6-luna__high__r0-r2",
          LAB / "analysis" / "two_phase_v7__gpt-5.6-luna__high__r0-r2" / "heldout"):
    sys.path.insert(0, str(p))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402
import compare_v8 as C8  # noqa: E402
import transitions as T  # noqa: E402
import diagnose_12 as D12  # noqa: E402
import claude_chain as CC  # noqa: E402

V, MODEL, EFF, REPS, MODS = CC.VERSION, CC.MODEL, CC.EFFORT, CC.REPS, CC.MODULES
PACKS = HERE / "packs"


def short(m):
    return m.replace("neorv32_", "")


def rec(r, m, ph):
    return json.loads((CH.run_dir(V, MODEL, r, EFF) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))


def assets(r, m):
    return json.loads((CH.run_dir(V, MODEL, r, EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]


def concept_names(r, m):
    return {c.get("id"): c.get("concept") for c in (CH.phase1_concepts(rec(r, m, 1)["reply"]) or [])}


def primary_rows(r, m, n):
    p2 = rec(r, m, 2)["reply"] or {}
    return [a for a in (p2.get("structural assets") or []) if isinstance(a, dict) and a.get("label") == "primary"
            and (a.get("element") == n or n in CH.as_list(a.get("same role")))]


def not_kept_mentions(r, m, n):
    raw1 = K.parse_json(rec(r, m, 1)["raw"])
    rows = raw1.get("Not Kept") if isinstance(raw1, dict) else None
    return [" | ".join(str(y) for y in x.values() if y) for x in (rows or []) if isinstance(x, dict) and T.has(n, json.dumps(x))]


def detectors(log):
    """P1-P4 on the v10 Claude Phase 2 replies; first the self-test on the v7 tuning replies."""
    fa = D12.FA
    raw = HERE / "_raw_v10c"
    for r in REPS:
        for m in MODS:
            for ph in (1, 2):
                p = raw / f"r{r}" / f"phase{ph}" / f"{m}.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(rec(r, m, ph)["raw"], encoding="utf-8", newline="")
    # The detectors' built-in self-tests read hand-checked lines of tuning modules (bus, cache, wdt, imem, cpu, ...) from
    # the scanned folder: copy the stored luna v7 replies of the 15 tuning modules in for them. None is a held-out
    # module, and their flags are never read (only MODS are looked up).
    assert not {p.stem for p in (fa / "raw").glob("r0/phase2/*.json")} & set(MODS)
    for p in (fa / "raw").glob("r*/phase*/*.json"):
        q = raw / p.relative_to(fa / "raw")
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_bytes(p.read_bytes())
    ok, flags = True, defaultdict(set)                   # (r, m, element) -> {P1, ...}
    for fx in ("P1", "P2", "P3", "P4"):
        sc = fa / "rules" / fx / "check_ho.py"
        a = D12.run_check(fx, sc, fa / "raw", HERE / f"_selftest_{fx}.json")
        b = json.loads((fa / "rules" / fx / "check_out.json").read_text(encoding="utf-8"))
        ok &= D12.norm(a) == D12.norm(b)
        (HERE / f"_selftest_{fx}.json").unlink()
        o = D12.run_check(fx, sc, raw, HERE / f"_flags_{fx}.json")
        (HERE / f"_flags_{fx}.json").unlink()
        for rk, mm, e, el in D12.norm(o):
            m = mm if mm.startswith("neorv32_") else "neorv32_" + mm
            flags[(int(rk[1]), m, el)].add(fx)
    shutil.rmtree(raw, ignore_errors=True)
    log(f"self-test 2 (P1-P4 copies on the v7 tuning replies = check_out.json): {'PASS' if ok else 'FAIL'}")
    return ok, flags


def main(log=print):
    sys.stdout.reconfigure(encoding="utf-8")
    ref = C8.refs(MODS)
    ok1 = C8.selftest(C8.refs(sorted(set(K.gt_modules()["tuning"]))))
    log(f"self-test 1 (scorer on the luna v7 runs): {'PASS' if ok1 else 'FAIL'}")
    C8.MODEL, C8.EFF = MODEL, EFF                        # from here on the scorer reads the Claude runs
    T.MODEL, T.EFF = MODEL, EFF
    ok2, flags = detectors(log)
    per_run, found, fpn, listed_all = {}, defaultdict(list), defaultdict(list), {}
    miss = defaultdict(list)
    ok3 = ok4 = True
    for r in REPS:
        tot = Counter()
        for m in MODS:
            L, Tn, fl, _ = C8.score(V, r, m, ref)
            names = [x["Asset RTL"] for x in assets(r, m)]
            raw_names = [x["Asset RTL"] for x in json.loads(
                (CH.run_dir(V, MODEL, r, EFF) / "assets" / f"{m}.json").read_bytes().decode("utf-8"))["Assets"]]
            ok4 &= names == raw_names and L == len(names)
            listed_all[(r, m)] = names
            cn = concept_names(r, m)
            for f in fl:
                n = f.split(":", 1)[1].rsplit("#", 1)[0]
                found[f].append({"run": r, "concepts": [f"{c} {cn.get(c, '')}" for c in
                                                         next((x["Concepts"] for x in assets(r, m) if x["Asset RTL"] == n), [])]})
            left = Counter(ref[m])
            fp_here = 0
            for x in assets(r, m):
                n = x["Asset RTL"]
                if left[n] > 0:
                    left[n] -= 1
                    continue
                fp_here += 1
                rows = primary_rows(r, m, n)
                fpn[f"{short(m)}:{n}"].append({
                    "run": r, "concepts": [f"{c} {cn.get(c, '')}" for c in x["Concepts"]],
                    "justification": [f"{a.get('concept id')}: {a.get('reason') or a.get('justification')}" for a in rows][:3],
                    "phase 1 Not Kept names it": not_kept_mentions(r, m, n)[:2],
                    "v7 bar detectors": sorted(flags.get((r, m, n), set()))})
            k, missed_here = Counter(), 0
            for n in ref[m]:
                k[n] += 1
                occ = f"{short(m)}:{n}#{k[n]}"
                if occ in fl:
                    continue
                missed_here += 1
                stage, why = T.where_lost(V, r, m, n, names)
                miss[occ].append({"run": r, "stage": stage, "reasons": [str(w)[:400] for w in why][:3]})
            ok3 &= fp_here == L - Tn and missed_here == len(ref[m]) - Tn
            tot.update({"listed": L, "TP": Tn, "FP": L - Tn, "FN": len(ref[m]) - Tn, "findable": len(ref[m])})
        per_run[r] = dict(tot)
    ok3 &= sum(len(v) for v in found.values()) == sum(per_run[r]["TP"] for r in REPS)
    ok3 &= sum(len(v) for v in fpn.values()) == sum(per_run[r]["FP"] for r in REPS)
    ok3 &= sum(len(v) for v in miss.values()) == sum(per_run[r]["FN"] for r in REPS)
    log(f"self-test 3 (sums): {'PASS' if ok3 else 'FAIL'}; self-test 4 (hand-read listings): {'PASS' if ok4 else 'FAIL'}")
    if not (ok1 and ok2 and ok3 and ok4):
        sys.exit("a self-test failed: nothing written")
    pooled = {k: sum(per_run[r][k] for r in REPS) for k in ("listed", "TP", "FP", "FN", "findable")}
    log("per run: " + "; ".join(f"r{r} TP {d['TP']} / listed {d['listed']} (P {d['TP'] / d['listed']:.3f}), "
                                f"recall {d['TP']}/{d['findable']} = {d['TP'] / d['findable']:.3f}" for r, d in per_run.items()))
    log(f"pooled: precision {pooled['TP']}/{pooled['listed']} = {pooled['TP'] / pooled['listed']:.3f}; "
        f"recall {pooled['TP']}/{pooled['findable']} = {pooled['TP'] / pooled['findable']:.3f}")
    # occurrences never found count too: every reference occurrence gets an entry
    occs = []
    for m in MODS:
        k = Counter()
        for n in ref[m]:
            k[n] += 1
            occs.append(f"{short(m)}:{n}#{k[n]}")
    stage_runs = Counter(x["stage"] for v in miss.values() for x in v)
    cons = lambda c: {3: "all 3", 2: "2 of 3", 1: "1 of 3", 0: "none"}[c]  # noqa: E731
    out = {"version": V, "executor": f"Claude Code subagent, model sonnet ({MODEL}__{EFF})", "modules": MODS,
           "per run": per_run, "pooled": pooled, "miss stages (occurrence-runs)": dict(stage_runs),
           "occurrences": {o: {"found in": len(found.get(o, [])), "found": found.get(o, []), "missed": miss.get(o, [])}
                           for o in occs},
           "false positives": {n: {"listed in": len(v), "runs": v} for n, v in sorted(fpn.items())}}
    out["summary"] = {
        "found occurrences by runs": dict(Counter(cons(len(found.get(o, []))) for o in occs)),
        "false-positive names by runs": dict(Counter(cons(len(v)) for v in fpn.values())),
        "FP name-runs a v7 bar detector flags": sum(1 for v in fpn.values() for x in v if x["v7 bar detectors"]),
        "FP name-runs Phase 1 Not Kept also names": sum(1 for v in fpn.values() for x in v if x["phase 1 Not Kept names it"])}
    (HERE / "facts.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"miss stages: {dict(stage_runs)}")
    log(f"summary: {out['summary']}")
    # packs: one folder per module for the analysts
    for m in MODS:
        d = PACKS / short(m)
        d.mkdir(parents=True, exist_ok=True)
        for r in REPS:
            for ph in (1, 2):
                (d / f"r{r}_phase{ph}.json").write_text(json.dumps(K.parse_json(rec(r, m, ph)["raw"]), indent=1,
                                                                   ensure_ascii=False), encoding="utf-8")
        mo = {o: v for o, v in out["occurrences"].items() if o.startswith(short(m) + ":")}
        mf = {n: v for n, v in out["false positives"].items() if n.startswith(short(m) + ":")}
        pm = {"module": m, "runs": list(REPS),
              "per run": {r: {"listed": len(listed_all[(r, m)]),
                              "TP": sum(1 for o in mo.values() for x in o["found"] if x["run"] == r)} for r in REPS},
              "reference occurrences (findable)": mo, "false positives": mf,
              "inputs": {f: str(CH.module_dir(m) / f) for f in ("rtl.txt", "closed_set.json", "diagram.txt")},
              "prompt": {f: str(LAB / "prompts" / V / f) for f in ("common.md", "phase1.md", "phase2.md")}}
        (d / "elements.json").write_text(json.dumps(pm, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"wrote facts.json and packs/ for {len(MODS)} modules")


if __name__ == "__main__":
    main()
