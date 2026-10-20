"""How consistently does the model follow the prompt's rules? two_phase_v9 (gpt-5.6-luna, high, r0-r2) on all 41
modules, with v8 for the change. Code only, read-only on runs, prompts and inputs; writes rule_consistency.json.

Measurements
  A. Change v8 -> v9 per split (15 tuning, 26 held-out): finds lost and gained (runs, gross), where each lost find went
     in v9, and the false positives added and removed.
  B. Rule citations: every row of a v9 reply that refers to a closed-set element (Phase 1 Not Kept rows: by name, or by
     citing one of its RTL lines while citing at most 30 lines, attribute.py's link) and invokes a rule (RULES: the Phase 1
     rule titles, which v9 also copies into Phase 2 when paired, and four Phase 2 / common.md bars; keyword match,
     approximate, a lower bound): Phase 1 Not Kept rows ("excluded"), Phase 2 secondary and Not Reported rows
     ("excluded"), Phase 2 primary rows whose justification invokes a rule ("kept, citing"). Per (module, element,
     rule), over the 3 runs:
        consistent      excluded with the rule cited in all 3 runs, primary in none
        stable          excluded with the rule cited in 1-2 runs, primary in none (other runs excluded it otherwise)
        mixed           the rule cited to exclude it in some run, and the element primary in another run (or the same
                        run, see C): the rule applied in one run and not in another
     Per rule: counts per class, tuning vs held-out, and how many cited elements are reference elements (a rule that
     excludes an element the reference lists).
  C. Cross-phase contradictions: in one run, a Phase 1 Not Kept row bars the element under rule R, yet Phase 2 lists it
     primary (through another concept).
  D. Where run-to-run inconsistency starts: every element primary in 1 or 2 of the 3 runs (reference elements and false
     positives); each run where it is not primary is classed by stage (transitions.where_lost): Phase 1 (Not Kept, lines
     only, never named: no kept concept holds it) or Phase 2 (secondary, not reported, anchor only, parent or field
     listed: a concept holds it and Phase 2 labels it otherwise).
  E. Rules cited against each other: for one element, the rules cited when it is excluded and the rules cited when it
     is kept primary, across runs.
  F. Code detectors of bars the model broke (the v7 rules round's checks P1-P4, failure_analysis/rules/*/check_ho.py,
     run on the v9 replies of all 41 modules): listed primaries a bar already excludes, split into reference finds and
     false positives, tuning vs held-out.
Self-tests (nothing is reported if one fails): the citation extractor finds the rule of every hand-read case of
attribute.HAND; the per-element run counts sum to compare_versions.json's v9 TP and FP; the stage classes of the v9
misses sum to its FN; the P1-P4 copies on the v7 tuning replies equal the originals' check_out.json.

  python rule_consistency.py
"""
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
HV = LAB / "analysis" / "heldout_versions__gpt-5.6-luna__high__r0-r2"
for p in (LAB, HV, LAB / "analysis" / "two_phase_v7__gpt-5.6-luna__high__r0-r2" / "heldout"):
    sys.path.insert(0, str(p))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import transitions as T  # noqa: E402
import attribute as A  # noqa: E402
import compare_versions as CV  # noqa: E402

CH, K = T.CH, T.K
V8, V9 = "two_phase_v8", "two_phase_v9"
REPS = (0, 1, 2)
P1_ORIGIN = {"Not Kept", "lines only", "never named"}
P2_ORIGIN = {"secondary", "not reported", "anchor only", "parent or field listed"}
EXTRA = {  # bars stated in phase2.md step 4 or common.md only (no Phase 1 title)
    "2.6 bus record port bar": ["bus request or response record", "bus-record", "bus record", "record-field bar", "record field bar"],
    "Phase 2 synchronizer-stage bar": ["synchronizer"],
    "Phase 2 operand-copy bar": ["holds that operand", "holds the operand", "operand copy", "operand register"],
    "2.6 carrier sentence": ["forwarding wire", "copy kept only", "only passes the value", "mixing it with other values"],
}


def rules_for(v):
    have = A.titles(v)
    out = {}
    for r, keys in A.RULE_KEYS.items():
        base = r.split(" (")[0]
        if base in have:
            out[r] = list(keys) + (["relayed"] if base == "Forwarded transactions" else [])
    out.update(EXTRA)
    return out


def tag(text, rules):
    low = (text or "").lower()
    return {r for r, keys in rules.items() if any(k in low for k in keys)}


def names_in(text, names):
    found = set()
    for n in names:
        if T.has(n, text):
            found.add(n)
        elif "." in n:
            last = n.rsplit(".", 1)[-1]
            if re.search(r"[_\d]", last) and T.has(last, text):
                found.add(n)
    return found


_names = {}
_lines = {}


def closed(m):
    if m not in _names:
        _names[m] = {n for (_, n) in CH.closed_names(m) if len(n) >= 4 or "_" in n or "." in n}
    return _names[m]


def occ(m):
    """name -> RTL occurrence lines (all entities of the module)."""
    if m not in _lines:
        d = defaultdict(set)
        for (e, n), fx in CH.closed_names(m).items():
            d[n] |= set(fx.get("occurrence lines") or [])
        _lines[m] = d
    return _lines[m]


def linked(text, m):
    """Elements a Not Kept row refers to: by name (as names_in), or by citing one of their RTL lines while citing at most
    A.MAX_CITED lines (attribute.py's link; a line-only link does not count for rules in A.LINE_LINK_SKIP)."""
    by_name = names_in(text, closed(m))
    c = A.cited_lines(text)
    by_line = {n for n, ls in occ(m).items() if n not in by_name and ls & c} if c and len(c) <= A.MAX_CITED else set()
    return by_name, by_line


def citations(v, r, m, rules):
    """[(element, rule, kind)] for one reply; kind: 'P1 Not Kept', 'P2 secondary', 'P2 not reported', 'P2 primary'."""
    out = []
    raw = K.parse_json(T.load(v, r, m, 1)["raw"])
    rows = raw.get("Not Kept") if isinstance(raw, dict) and "Not Kept" in raw else (T.load(v, r, m, 1)["reply"] or {}).get("considered, not kept")
    for x in rows or []:
        if not isinstance(x, dict):
            continue
        t = json.dumps(x, ensure_ascii=False)
        rs = tag(t, rules)
        if rs:
            by_name, by_line = linked(t, m)
            for n in by_name:
                out += [(n, rr, "P1 Not Kept") for rr in rs]
            for n in by_line:
                out += [(n, rr, "P1 Not Kept (line link)") for rr in rs if rr not in A.LINE_LINK_SKIP]
    p2 = T.load(v, r, m, 2)["reply"] or {}
    for a in p2.get("structural assets") or []:
        if not isinstance(a, dict):
            continue
        rs = tag(str(a.get("justification") or a.get("reason") or ""), rules)
        if not rs:
            continue
        kind = "P2 primary" if a.get("label") == "primary" else "P2 secondary"
        for n in [a.get("element")] + CH.as_list(a.get("same role")):
            if isinstance(n, str) and n:
                out += [(n, rr, kind) for rr in rs]
    for x in p2.get("not reported") or []:
        if isinstance(x, dict) and isinstance(x.get("element"), str):
            out += [(x["element"], rr, "P2 not reported") for rr in tag(str(x.get("reason") or ""), rules)]
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, ref = CV.groups_and_ref()
    split = {m: "tuning" for m in groups["tuning"]} | {m: "held-out" for m in groups["held-out"]}
    mods = groups["tuning"] + groups["held-out"]
    listed = {(v, r, m): [x["Asset RTL"] for x in json.loads((CH.run_dir(v, T.MODEL, r, T.EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]]
              for v in (V8, V9) for r in REPS for m in mods}
    ok = True
    # self-test 1: the extractor finds every hand-read case
    for v, r, m, n, rule in A.HAND:
        rules = rules_for(v)
        got = {rr for (e, rr, k) in citations(v, r, m, rules) if e == n}
        st, why = T.where_lost(v, r, m, n, listed.get((v, r, m)) or [x["Asset RTL"] for x in json.loads((CH.run_dir(v, T.MODEL, r, T.EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]])
        got |= {rr for w in why for rr in tag(w, rules)}
        hit = rule in got or (rule.split(" (")[0] in got)
        ok &= hit
        if not hit:
            print(f"  self-test miss: {v[10:]} r{r} {m[8:]}:{n} -> {rule}; got {sorted(got)}")
    print("self-test 1 (extractor finds the hand-read rule of every attribute.HAND case):", "PASS" if ok else "FAIL")
    cvj = json.loads((HV / "compare_versions.json").read_text(encoding="utf-8"))
    # per-element run counts (v9)
    prim = defaultdict(Counter)                     # (m) -> name -> runs listed primary (each run counts once)
    tp_runs = Counter()
    fp_runs = Counter()
    for m in mods:
        for r in REPS:
            names = listed[(V9, r, m)]
            for n in set(names):
                prim[m][n] += 1
            left = Counter(ref[m])
            for x in names:
                if left[x] > 0:
                    left[x] -= 1
                    tp_runs[split[m]] += 1
                else:
                    fp_runs[split[m]] += 1
    ok2 = all(tp_runs[s] == cvj["versions"]["v9"][s]["TP"] and fp_runs[s] == cvj["versions"]["v9"][s]["FP"] for s in ("tuning", "held-out"))
    print("self-test 2 (v9 TP and FP runs = compare_versions.json):", "PASS" if ok2 else f"FAIL {tp_runs} {fp_runs}")
    ok &= ok2
    out = {}
    # A. change v8 -> v9
    A_ = {}
    for s in ("tuning", "held-out"):
        lost = gained = 0
        st = Counter()
        per_mod = Counter()
        for m in groups[s]:
            k = Counter()
            for n in ref[m]:
                k[n] += 1
                f8 = [r for r in REPS if Counter(listed[(V8, r, m)])[n] >= k[n]]
                f9 = [r for r in REPS if Counter(listed[(V9, r, m)])[n] >= k[n]]
                d = len(f9) - len(f8)
                per_mod[m[8:]] += d
                if d > 0:
                    gained += d
                elif d < 0:
                    lost += -d
                    for r in [r for r in REPS if r not in f9][:-d]:
                        st[T.where_lost(V9, r, m, n, listed[(V9, r, m)])[0]] += 1
        fp8 = cvj["versions"]["v8"][s]["FP"]
        fp9 = cvj["versions"]["v9"][s]["FP"]
        A_[s] = {"finds lost (runs)": lost, "finds gained (runs)": gained, "lost finds went to (v9)": dict(st.most_common()),
                 "FP runs v8 -> v9": f"{fp8} -> {fp9}", "net TP change per module": {k: v for k, v in per_mod.items() if v}}
    out["A change v8 -> v9"] = A_
    # D. where inconsistency starts, and the v9 miss stages
    D_ = {s: {"TP elements": Counter(), "FP elements": Counter()} for s in ("tuning", "held-out")}
    flips = {s: {"TP elements": 0, "FP elements": 0} for s in ("tuning", "held-out")}
    steady = {s: Counter() for s in ("tuning", "held-out")}
    miss_st = {s: Counter() for s in ("tuning", "held-out")}
    for m in mods:
        s = split[m]
        refset = set(ref[m])
        for n in sorted(set(prim[m]) | refset):
            c = prim[m][n]
            cls = "TP elements" if n in refset else "FP elements"
            if c in (0, 3):
                steady[s][f"{cls}: primary in {c} of 3 runs"] += 1
            if n in refset:
                for r in REPS:
                    if n not in listed[(V9, r, m)]:
                        miss_st[s][T.where_lost(V9, r, m, n, listed[(V9, r, m)])[0]] += 1 * Counter(ref[m])[n]
            if c not in (1, 2):
                continue
            flips[s][cls] += 1
            for r in REPS:
                if n in listed[(V9, r, m)]:
                    continue
                stg = T.where_lost(V9, r, m, n, listed[(V9, r, m)])[0]
                D_[s][cls]["Phase 1 (" + stg + ")" if stg in P1_ORIGIN else "Phase 2 (" + stg + ")"] += 1
    # the miss-stage self-test counts reference entries, so recount exactly with multiplicity
    fn = {s: 0 for s in ("tuning", "held-out")}
    for m in mods:
        k = Counter()
        for n in ref[m]:
            k[n] += 1
            fn[split[m]] += sum(1 for r in REPS if Counter(listed[(V9, r, m)])[n] < k[n])
    ok3 = all(fn[s] == cvj["versions"]["v9"][s]["FN"] for s in fn)
    print("self-test 3 (v9 misses counted with multiplicity = compare_versions.json FN):", "PASS" if ok3 else f"FAIL {fn}")
    ok &= ok3
    out["D where run-to-run inconsistency starts (non-primary runs of elements primary in 1-2 runs)"] = {
        s: {"elements primary in 1-2 of 3 runs": flips[s], "elements primary in 0 or 3 runs": dict(steady[s]),
            **{cls: {"Phase 1 share": round(sum(v for k, v in D_[s][cls].items() if k.startswith("Phase 1")) / max(1, sum(D_[s][cls].values())), 3),
                     "by stage": dict(D_[s][cls].most_common())} for cls in ("TP elements", "FP elements")}} for s in D_}
    out["v9 misses by stage (element names, not multiplicity)"] = {s: dict(miss_st[s].most_common()) for s in miss_st}
    # B, C, E. rule citations
    rules = rules_for(V9)
    cite_all = defaultdict(lambda: defaultdict(set))     # (m, n, rule) -> kind -> runs (line links folded in)
    cite_name = defaultdict(lambda: defaultdict(set))    # the same, name links only
    for m in mods:
        for r in REPS:
            for n, rr, kind in citations(V9, r, m, rules):
                cite_all[(m, n, rr)][kind.replace(" (line link)", "")].add(r)
                if "line link" not in kind:
                    cite_name[(m, n, rr)][kind].add(r)
    robust = {}
    for label, cmap in (("name links only", cite_name),):
        mix = defaultdict(lambda: [0, 0])
        cph = Counter()
        for (m, n, rr), kinds in cmap.items():
            excl = set().union(*(kinds.get(k, set()) for k in ("P1 Not Kept", "P2 secondary", "P2 not reported")))
            pr = {r for r in REPS if n in listed[(V9, r, m)]}
            if excl:
                mix[rr][1] += 1
                mix[rr][0] += bool(pr)
            cph[rr] += len(kinds.get("P1 Not Kept", set()) & pr)
        robust[label] = {"mixed / cited": {rr: f"{a}/{b}" for rr, (a, b) in sorted(mix.items(), key=lambda kv: -kv[1][1]) if b >= 4},
                         "barred in Phase 1 yet primary in Phase 2 (element-runs)": {rr: c for rr, c in cph.most_common() if c}}
    cite = cite_all
    B_ = defaultdict(lambda: {s: Counter() for s in ("tuning", "held-out")})
    C_ = defaultdict(lambda: {s: Counter() for s in ("tuning", "held-out")})
    examples = defaultdict(list)
    mixed_cases = []
    for (m, n, rr), kinds in cite.items():
        s = split[m]
        excl = set().union(*(kinds[k] for k in ("P1 Not Kept", "P2 secondary", "P2 not reported") if k in kinds)) if any(
            k in kinds for k in ("P1 Not Kept", "P2 secondary", "P2 not reported")) else set()
        pr = {r for r in REPS if n in listed[(V9, r, m)]}
        isref = n in ref[m]
        if excl:
            cls = "mixed" if pr else ("consistent" if len(excl) == 3 else "stable")
            B_[rr][s][cls] += 1
            B_[rr][s]["cited elements in the reference"] += isref
            if cls == "mixed":
                B_[rr][s]["mixed, reference element (rule cited against a true asset)" if isref else "mixed, not reference (rule ignored -> FP)"] += 1
                mixed_cases.append({"rule": rr, "module": m, "element": n, "split": s, "reference": isref,
                                    "excluded in runs": sorted(excl), "primary in runs": sorted(pr),
                                    "kinds": {k: sorted(v) for k, v in kinds.items()}})
            if cls == "mixed" and len(examples[rr]) < 4:
                examples[rr].append(f"{m[8:]}:{n} ({'reference' if isref else 'not reference'}) excluded in r{sorted(excl)}, primary in r{sorted(pr)}")
        if "P2 primary" in kinds:
            B_[rr][s]["kept primary while citing it"] += 1
        p1 = kinds.get("P1 Not Kept", set())
        same = p1 & pr
        if same:
            C_[rr][s]["element-runs barred in Phase 1 yet primary in Phase 2"] += len(same)
            C_[rr][s]["of these, reference elements"] += len(same) * isref
    rank = []
    for rr, d in B_.items():
        tot = {s: d[s]["consistent"] + d[s]["stable"] + d[s]["mixed"] for s in d}
        mixed = {s: d[s]["mixed"] for s in d}
        allt = sum(tot.values())
        if allt:
            rank.append((rr, allt, sum(mixed.values()) / allt, {s: (mixed[s], tot[s]) for s in d}))
    rank.sort(key=lambda x: (-x[2], -x[1]))
    out["B rule citations per (module, element, rule)"] = {rr: {"tuning": dict(B_[rr]["tuning"]), "held-out": dict(B_[rr]["held-out"]),
                                                               "mixed examples": examples[rr]} for rr in B_}
    out["B ranking (rules cited for 4+ elements, by mixed share)"] = [
        {"rule": rr, "cited elements": n, "mixed share": round(sh, 3), "mixed / cited (tuning, held-out)": d} for rr, n, sh, d in rank if n >= 4]
    out["B robustness"] = robust
    out["B mixed cases"] = mixed_cases
    out["C cross-phase contradictions"] = {rr: {s: dict(v) for s, v in d.items()} for rr, d in C_.items()}
    # E. rules cited against each other for one element
    by_el = defaultdict(lambda: {"excluded under": set(), "kept citing": set()})
    for (m, n, rr), kinds in cite.items():
        if any(k in kinds for k in ("P1 Not Kept", "P2 secondary", "P2 not reported")):
            by_el[(m, n)]["excluded under"].add(rr)
        if "P2 primary" in kinds:
            by_el[(m, n)]["kept citing"].add(rr)
    pairs = Counter()
    for (m, n), d in by_el.items():
        for a in d["excluded under"]:
            for b in d["kept citing"]:
                if a != b:
                    pairs[(a, b)] += 1
    out["E rule pairs: excluded under A in one run, kept citing B in another (elements)"] = [
        {"excluded under": a, "kept citing": b, "elements": c} for (a, b), c in pairs.most_common(15)]
    # F. code detectors P1-P4 on the v9 replies
    import diagnose_12 as D12
    raw9 = HERE / "_raw_v9"
    for r in REPS:
        for m in mods:
            for ph in (1, 2):
                rec = json.loads((CH.run_dir(V9, T.MODEL, r, T.EFF) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))
                p = raw9 / f"r{r}" / f"phase{ph}" / f"{m}.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(rec["raw"], encoding="utf-8", newline="")
    fa = D12.FA
    ok4 = True
    F_ = {}
    for fx in ("P1", "P2", "P3", "P4"):
        sc = fa / "rules" / fx / "check_ho.py"
        a = D12.run_check(fx, sc, fa / "raw", HERE / f"_selftest_{fx}.json")
        b = json.loads((fa / "rules" / fx / "check_out.json").read_text(encoding="utf-8"))
        ok4 &= D12.norm(a) == D12.norm(b)
        (HERE / f"_selftest_{fx}.json").unlink()
        o = D12.run_check(fx, sc, raw9, HERE / f"_flags_{fx}.json")
        cnt = {s: Counter() for s in ("tuning", "held-out")}
        seen = set()
        for rk, mm, e, el in D12.norm(o):
            m = mm if mm.startswith("neorv32_") else "neorv32_" + mm
            r = int(rk[1])
            if m not in split or (r, m, el) in seen or el not in listed[(V9, r, m)]:
                continue
            seen.add((r, m, el))
            cnt[split[m]]["reference finds flagged" if el in ref[m] else "false positives flagged"] += 1
            cnt[split[m]]["modules"] += 0
        F_[fx] = {s: dict(c) for s, c in cnt.items()}
    print("self-test 4 (P1-P4 copies on the v7 tuning replies = check_out.json):", "PASS" if ok4 else "FAIL")
    ok &= ok4
    shutil.rmtree(raw9, ignore_errors=True)
    if not ok:
        sys.exit("a self-test failed: nothing reported")
    out["F code detectors of broken v7 bars, on v9 (element-runs)"] = F_
    (HERE / "rule_consistency.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    # print
    print("\nA. change v8 -> v9")
    for s, d in A_.items():
        print(f"  {s}: finds lost {d['finds lost (runs)']}, gained {d['finds gained (runs)']}; FP runs {d['FP runs v8 -> v9']}; lost went to {d['lost finds went to (v9)']}")
        print(f"     net TP per module: {d['net TP change per module']}")
    print("\nD. where run-to-run inconsistency starts (non-primary runs of elements primary in 1-2 of 3 runs)")
    for s, d in out["D where run-to-run inconsistency starts (non-primary runs of elements primary in 1-2 runs)"].items():
        print(f"  {s}: flipping elements {d['elements primary in 1-2 of 3 runs']}; steady {d['elements primary in 0 or 3 runs']}")
        for cls in ("TP elements", "FP elements"):
            print(f"     {cls}: Phase 1 share {d[cls]['Phase 1 share']}; {d[cls]['by stage']}")
    print("\nv9 misses by stage:", out["v9 misses by stage (element names, not multiplicity)"])
    print("\nB. rules by mixed share (applied in one run, element primary in another); cited elements >= 4")
    for x in out["B ranking (rules cited for 4+ elements, by mixed share)"]:
        rr = x["rule"]
        bt, bh = B_[rr]["tuning"], B_[rr]["held-out"]
        print(f"  {rr:40s} cited {x['cited elements']:3d}  mixed {x['mixed share']:.2f}  (tuning mixed/cited {x['mixed / cited (tuning, held-out)']['tuning']}, "
              f"held-out {x['mixed / cited (tuning, held-out)']['held-out']}); consistent t/h {bt['consistent']}/{bh['consistent']}; "
              f"reference elements cited t/h {bt['cited elements in the reference']}/{bh['cited elements in the reference']}; kept-citing t/h {bt['kept primary while citing it']}/{bh['kept primary while citing it']}")
    print("\nB split of mixed cases (tuning / held-out): rule ignored -> FP | rule cited against a reference element")
    ka, kb = "mixed, not reference (rule ignored -> FP)", "mixed, reference element (rule cited against a true asset)"
    for x in out["B ranking (rules cited for 4+ elements, by mixed share)"]:
        rr = x["rule"]
        print(f"  {rr:40s} ignored->FP {B_[rr]['tuning'].get(ka, 0)}/{B_[rr]['held-out'].get(ka, 0)} | "
              f"against a true asset {B_[rr]['tuning'].get(kb, 0)}/{B_[rr]['held-out'].get(kb, 0)}")
    tot = {s: (sum(B_[rr][s]["mixed"] for rr in B_), sum(B_[rr][s]["mixed"] + B_[rr][s]["stable"] + B_[rr][s]["consistent"] for rr in B_))
           for s in ("tuning", "held-out")}
    print(f"  all rules: mixed / cited tuning {tot['tuning'][0]}/{tot['tuning'][1]}, held-out {tot['held-out'][0]}/{tot['held-out'][1]}")
    print("\nB robustness (name links only):", json.dumps(robust, indent=1))
    print("\nC. barred in Phase 1 yet primary in Phase 2, same run (element-runs):")
    for rr, d in sorted(C_.items(), key=lambda kv: -sum(v.get("element-runs barred in Phase 1 yet primary in Phase 2", 0) for v in kv[1].values())):
        print(f"  {rr:40s} tuning {dict(d['tuning'])} | held-out {dict(d['held-out'])}")
    print("\nE. rule pairs (excluded under A in one run, kept citing B in another):")
    for x in out["E rule pairs: excluded under A in one run, kept citing B in another (elements)"]:
        print(f"  {x['excluded under']:36s} vs kept citing {x['kept citing']:36s} {x['elements']}")
    print("\nF. P1-P4 detectors on v9 (listed primaries a v7 bar already excludes):")
    for fx, d in F_.items():
        print(f"  {fx}: tuning {d['tuning']} | held-out {d['held-out']}")


if __name__ == "__main__":
    main()
