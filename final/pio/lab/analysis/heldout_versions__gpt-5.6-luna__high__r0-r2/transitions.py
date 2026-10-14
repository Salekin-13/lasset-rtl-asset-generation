"""Element-level change of TPs, FNs and FPs on the held-out modules between prompt versions (v1 -> v2 -> v4a -> v5 -> v7
-> v8; gpt-5.6-luna, high, r0-r2), with the tuning modules beside them for contrast. Read-only; writes transitions.json.

Units:
  - a reference occurrence ("module:name#k", the k-th reference entry with that name) is found in 0-3 runs of a
    version (exact scorer of compare_v8.py);
  - a listed name that is not a reference find ("module:name") is a false positive in 0-3 runs.
Between two versions A -> B:
  - lost find: found in 2+ runs of A and at most 1 of B; gained find: the reverse;
  - removed FP: listed as FP in 2+ runs of A and at most 1 of B; new FP: the reverse.
  (2-of-3 vs 0-1-of-3 is a chosen cut against run-to-run noise.)
Where a miss is lost, per occurrence-run of version B (first that applies):
  - "secondary": a Phase 2 structural-asset row names it (element or same role) with a label other than primary;
  - "not reported": a Phase 2 Not Reported row names it (only versions with that list: v5f on);
  - "Not Kept": a Phase 1 considered-not-kept row mentions the name;
  - "parent or field listed": a listed primary is its record parent or one of its fields (naming granularity);
  - "anchor only": a kept concept lists it under enters/leaves through, but no Phase 2 row names it;
  - "lines only": a kept concept cites one of its RTL occurrence lines, nothing names it;
  - "never named".
Kinds of element (closed set): port, record port, port field, signal, record signal, signal field.
Self-test: the occurrence counts sum to the per-run correct counts of compare_versions.json, and v7's held-out miss stages
on the 12 modules reproduce diagnose_12.json's totals where the categories coincide (secondary, Not Kept, never named
plus lines only, with "parent or field listed" and "anchor only" folded back the way diagnose_12 counted them).

  python transitions.py
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import compare_v8 as C8  # noqa: E402
import compare_versions as CV  # noqa: E402
import labkit as K  # noqa: E402

MODEL, EFF, REPS = "gpt-5.6-luna", "high", (0, 1, 2)
VERS = CV.VERS
PAIRS = list(zip(VERS, VERS[1:]))


def has(name, text):
    return bool(re.search(r"(?<![\w.])" + re.escape(name) + r"(?!\w)(?!\.\w)", text or ""))


def kinds(m):
    """name -> kind, for every closed-set name of the module (any entity; the first entity's kind wins)."""
    out, parent = {}, {}
    for (e, n), x in CH.closed_names(m).items():
        if "field" in x:
            continue
        isport = "port" in x
        rec = "record type" in x
        out.setdefault(n, ("record port" if rec else "port") if isport else ("record signal" if rec else "signal"))
        for f in x.get("fields", []):
            out.setdefault(f["field"], "port field" if isport else "signal field")
            parent.setdefault(f["field"], (n, x.get("record type")))
    return out, parent


def load(v, r, m, ph):
    return json.loads((CH.run_dir(v, MODEL, r, EFF) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))


def where_lost(v, r, m, n, listed_names):
    p1, p2 = load(v, r, m, 1)["reply"] or {}, load(v, r, m, 2)["reply"] or {}
    rows = [a for a in (p2.get("structural assets") or []) if isinstance(a, dict)
            and (a.get("element") == n or n in CH.as_list(a.get("same role")))]
    sec = [a for a in rows if a.get("label") != "primary"]
    if sec:
        return "secondary", [f"{a.get('concept id')} {a.get('label')}: {a.get('justification') or a.get('reason')}" for a in sec]
    nr = [x for x in (p2.get("not reported") or []) if isinstance(x, dict) and x.get("element") == n]
    if nr:
        return "not reported", [f"{x.get('concept id')}: {x.get('reason')}" for x in nr]
    raw1 = K.parse_json(load(v, r, m, 1)["raw"])                # the raw rows: the v5-key mapping drops Why Not Kept
    nkr = raw1.get("Not Kept") if isinstance(raw1, dict) and "Not Kept" in raw1 else p1.get("considered, not kept")
    nk = [x for x in (nkr or []) if isinstance(x, dict) and has(n, json.dumps(x))]   # text when Merged Into is also filled
    if nk:
        return "Not Kept", [" | ".join(str(y) for y in x.values() if y) for x in nk]
    rel = [x for x in listed_names if x.startswith(n + ".") or n.startswith(x + ".")]
    if rel:
        return "parent or field listed", rel
    cons = CH.phase1_concepts(p1) or []
    if any(n in CH.as_list(c.get("enters through")) + CH.as_list(c.get("leaves through")) for c in cons):
        return "anchor only", []
    lines = set()
    for (e, x), fx in CH.closed_names(m).items():
        if x == n:
            lines |= set(fx.get("occurrence lines") or [])
    if any(lines & set(CH.as_list(c.get("held lines")) + CH.as_list(c.get("entry lines")) + CH.as_list(c.get("exit lines"))) for c in cons):
        return "lines only", []
    return "never named", []


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, ref = CV.groups_and_ref()
    the12 = set(groups["held-out: the 12"])
    mods = {"tuning": groups["tuning"], "held-out": groups["held-out"]}
    found = {s: {v: Counter() for v in VERS} for s in mods}      # occurrence -> runs found
    fp = {s: {v: Counter() for v in VERS} for s in mods}         # module:name -> runs listed as FP
    listed = {}                                                  # (v, r, m) -> listed names
    occ = {s: [] for s in mods}
    for s, ms in mods.items():
        for m in ms:
            k = Counter()
            for n in ref[m]:
                k[n] += 1
                occ[s].append(f"{m.replace('neorv32_', '')}:{n}#{k[n]}")
            for v in VERS:
                for r in REPS:
                    L, T, fl, names = C8.score(v, r, m, ref)
                    for f in fl:
                        found[s][v][f] += 1
                    left = Counter(ref[m])
                    names_list = [x["Asset RTL"] for x in json.loads((CH.run_dir(v, MODEL, r, EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]]
                    listed[(v, r, m)] = names_list
                    for x in names_list:
                        if left[x] > 0:
                            left[x] -= 1
                        else:
                            fp[s][v][f"{m.replace('neorv32_', '')}:{x}"] += 1
    # self-test 1: occurrence counts = per-run correct counts
    cvj = json.loads((HERE / "compare_versions.json").read_text(encoding="utf-8"))
    ok = all(sum(found[s][v].values()) == cvj["versions"][CV.short(v)][s]["TP"] for s in mods for v in VERS)
    ok &= all(sum(fp[s][v].values()) == cvj["versions"][CV.short(v)][s]["FP"] for s in mods for v in VERS)
    # miss stages, held-out, every version
    stages = {v: Counter() for v in VERS}
    stages12 = {v: Counter() for v in VERS}
    detail = defaultdict(list)                                   # (v, occurrence) -> [(run, stage, reasons)]
    kind_of = {}
    for m in groups["held-out"]:
        kd, par = kinds(m)
        for n in set(ref[m]):
            kind_of[f"{m.replace('neorv32_', '')}:{n}"] = (kd.get(n, "?"), par.get(n, (None, None))[1])
        for v in VERS:
            for r in REPS:
                names_list = listed[(v, r, m)]
                left = Counter(names_list)
                k = Counter()
                for n in ref[m]:
                    k[n] += 1
                    o = f"{m.replace('neorv32_', '')}:{n}#{k[n]}"
                    if left[n] > 0:
                        left[n] -= 1
                        continue
                    st, why = where_lost(v, r, m, n, names_list)
                    stages[v][st] += 1
                    if m in the12:
                        stages12[v][st] += 1
                    detail[(v, o)].append((f"r{r}", st, why))
    d12 = json.loads((LAB / "analysis" / "two_phase_v7__gpt-5.6-luna__high__r0-r2" / "heldout" / "diagnose_12.json").read_text(encoding="utf-8"))
    want = Counter()
    for mm in d12["modules"].values():
        for x in mm["misses"]:
            want[x["where lost"]] += 1
    mine = stages12["two_phase_v7"]
    fold = {"secondary": mine["secondary"], "Not Kept": mine["Not Kept"],
            "named or lines (rest)": sum(mine.values()) - mine["secondary"] - mine["Not Kept"] - mine["not reported"]}
    theirs = {"secondary": want["secondary"], "Not Kept": want["Not Kept"] + want["Not Kept (merged)"],
              "named or lines (rest)": sum(want.values()) - want["secondary"] - want["Not Kept"] - want["Not Kept (merged)"] - want["not reported"]}
    ok2 = fold == theirs and mine["not reported"] == want["not reported"]
    print("self-test (occurrence and FP counts = compare_versions.json):", "PASS" if ok else "FAIL")
    print(f"self-test (v7 miss stages on the 12 = diagnose_12.json): {'PASS' if ok2 else 'FAIL'} mine {fold} nr {mine['not reported']}, "
          f"diagnose_12 {theirs} nr {want['not reported']}")
    if not (ok and ok2):
        sys.exit(1)
    out = {"miss stages, held-out (occurrence-runs)": {CV.short(v): dict(stages[v]) for v in VERS},
           "miss stages, the 12 (occurrence-runs)": {CV.short(v): dict(stages12[v]) for v in VERS}, "pairs": {}}
    print("\nwhere held-out misses are lost (occurrence-runs; all 26 modules):")
    cats = ["secondary", "not reported", "Not Kept", "parent or field listed", "anchor only", "lines only", "never named"]
    print(f"  {'':5s}" + "".join(f"{c:>23s}" for c in cats) + f"{'total':>7s}")
    for v in VERS:
        print(f"  {CV.short(v):5s}" + "".join(f"{stages[v][c]:23d}" for c in cats) + f"{sum(stages[v].values()):7d}")
    for a, b in PAIRS:
        pr = {}
        for s in mods:
            lost = sorted(o for o in occ[s] if found[s][a][o] >= 2 and found[s][b][o] <= 1)
            gained = sorted(o for o in occ[s] if found[s][a][o] <= 1 and found[s][b][o] >= 2)
            allfp = set(fp[s][a]) | set(fp[s][b])
            removed = sorted(x for x in allfp if fp[s][a][x] >= 2 and fp[s][b][x] <= 1)
            new = sorted(x for x in allfp if fp[s][a][x] <= 1 and fp[s][b][x] >= 2)
            pr[s] = {"lost finds": len(lost), "gained finds": len(gained), "removed FPs": len(removed), "new FPs": len(new)}
            if s == "held-out":
                pr[s]["lost"] = {o: {"runs found": f"{found[s][a][o]} -> {found[s][b][o]}", "kind": kind_of[o.split("#")[0]],
                                     f"where lost in {CV.short(b)}": detail[(b, o)]} for o in lost}
                pr[s]["gained"] = {o: {"runs found": f"{found[s][a][o]} -> {found[s][b][o]}", "kind": kind_of[o.split("#")[0]],
                                       f"where lost in {CV.short(a)}": detail[(a, o)]} for o in gained}
                pr[s]["removed FP list"] = removed
                pr[s]["new FP list"] = new
                pr[s]["lost, stage in B (occurrence-runs)"] = dict(Counter(st for o in lost for _, st, _ in detail[(b, o)]))
                pr[s]["lost, by module"] = dict(Counter(o.split(":")[0] for o in lost))
                pr[s]["gained, by module"] = dict(Counter(o.split(":")[0] for o in gained))
                pr[s]["lost, by kind"] = dict(Counter(kind_of[o.split("#")[0]][0] for o in lost))
        out["pairs"][f"{CV.short(a)} -> {CV.short(b)}"] = pr
    print("\nversion to version (2+ of 3 runs vs at most 1): lost / gained finds, removed / new FPs")
    for k, pr in out["pairs"].items():
        t, h = pr["tuning"], pr["held-out"]
        print(f"  {k:12s} tuning: finds -{t['lost finds']} +{t['gained finds']}, FPs -{t['removed FPs']} +{t['new FPs']}   |   "
              f"held-out: finds -{h['lost finds']} +{h['gained finds']}, FPs -{h['removed FPs']} +{h['new FPs']}")
        print(f"               held-out lost by module {h['lost, by module']}")
        print(f"               held-out lost: stage in B {h['lost, stage in B (occurrence-runs)']}; kind {h['lost, by kind']}")
        print(f"               held-out gained by module {h['gained, by module']}")
    (HERE / "transitions.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("written transitions.json")


if __name__ == "__main__":
    main()
