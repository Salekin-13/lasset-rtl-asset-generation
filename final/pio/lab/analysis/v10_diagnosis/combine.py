"""Combined rule-alone outputs (user 2026-10-16 07:24: "combine the findings of the isolated run outputs & check for any
remaining blind patterns that can be addressed by a softened theory backed rule ... any overlap between TPs & FPs of the
isolated runs combined may indicate a conflict between rules, use the insight for resumed test's analysis").
Read-only; writes combine_<tag>.json. Sends nothing.

Inputs: every v10 rule wording's luna rule-alone run (rule_breaks.load_latest) plus the new rules' runs (variants given,
e.g. v11n), only the rules that passed (read_<variant>.json) unless --all.
  bar decision   a bar or naming rule's "barred" list; keep decision: a primary-making (keep) rule's "spared" list. A bar
                 rule's own "spared" list only says its bar does not cover the element, so it is no decision
                 (analyze_isolation's convention)
  consistent     in both repeats (analyze_isolation.covered, a record and its fields as one)
1. Remaining blind spots: v10's false positives and misses (blindspots.py's lists) that no rule, old or new, decides in
   either repeat; patterns with decision D8's cut.
2. Conflict candidates: an element one rule bars consistently while a primary-making rule keeps it consistently. Per pair of rules: elements, how many the reference lists ("a bar against a correct find") and how many it
   does not ("a keep against a correct bar"), and v10's primary runs on them. These pairs feed the staged test.
3. Isolated verdict vs the reference: an element counts as "kept alone" when some rule keeps it and none bars it, "barred
   alone" when some rule bars it and none keeps it, "both" when it is in 2. Tallied against the reference.
Self-test: with no new variant, part 1 equals blindspots.json's unaddressed totals (366 / 60).

  python -B combine.py <tag> [variant ...] [--all]
"""
import json
import os
import sys
from collections import Counter, defaultdict

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, register  # noqa: E402

ISO = register()
import rule_breaks as RB  # noqa: E402
import analyze_isolation as AN  # noqa: E402
import blindspots as BS  # noqa: E402

CH, CV, T = RB.CH, RB.CV, RB.T


def load_new(variant, only_pass=True):
    meta = json.loads((HERE / "new_rules" / f"meta_{variant}.json").read_text(encoding="utf-8"))
    texts = json.loads((HERE / "new_rules" / f"rule_texts_{variant}.json").read_text(encoding="utf-8"))
    passed = json.loads((HERE / f"read_{variant}.json").read_text(encoding="utf-8")) if only_pass else {}
    ISO.use(variant)
    R = {}
    for rid, t in texts.items():
        if only_pass and not passed.get(rid, {}).get("PASS"):
            continue
        for ph in ("P1", "P2"):
            if not t.get(ph):
                continue
            for rep in (0, 1):
                for f in (ISO.run_root(rep=rep) / ph / rid).glob("*.json"):
                    rec = json.loads(f.read_text(encoding="utf-8"))
                    if isinstance(rec.get("reply"), dict):
                        R[(rid, ph, rec["module"], rep)] = rec["reply"]
    ISO.use("v9")
    return R, {rid: (meta[rid].get("kind") or "") for rid in texts}


def main(tag, variants, only_pass=True):
    sys.stdout.reconfigure(encoding="utf-8")
    groups, refl = CV.groups_and_ref()
    mods = groups["tuning"] + groups["held-out"]
    ref = {m: set(v) for m, v in refl.items()}
    R, _, lp = RB.load_latest(mods)
    kinds = {}
    for v in variants:
        Rn, kn = load_new(v, only_pass)
        R.update(Rn)
        kinds.update(kn)

    def is_keep(rid):
        return BS.adds(rid) or kinds.get(rid, "").startswith("keep")
    anybar, anykeep = defaultdict(set), defaultdict(set)
    cbar, ckeep = defaultdict(lambda: defaultdict(set)), defaultdict(lambda: defaultdict(set))   # m -> rule -> elements
    byk = defaultdict(dict)
    for (rid, ph, m, rep), rp in R.items():
        byk[(rid, ph, m)][rep] = rp
    def is_naming(rid):
        return kinds.get(rid, "").startswith("naming")    # bars a record's fields AND keeps the whole record
    for (rid, ph, m), reps in byk.items():
        keep = is_keep(rid)
        for rep, rp in reps.items():
            if keep:
                anykeep[m] |= AN.names(rp, "spared")
            else:
                anybar[m] |= AN.names(rp, "barred")      # a bar rule's "spared" list is not a keep (analyze_isolation)
                if is_naming(rid):
                    anykeep[m] |= AN.names(rp, "spared")
        if len(reps) == 2:
            a, b = reps[0], reps[1]
            if keep:
                ckeep[m][f"{rid} {ph}"] |= {e for e in AN.names(a, "spared") if AN.covered(e, AN.names(b, "spared"))}
            else:
                cbar[m][f"{rid} {ph}"] |= {e for e in AN.names(a, "barred") if e in AN.names(b, "barred")} if is_naming(rid) else                     {e for e in AN.names(a, "barred") if AN.covered(e, AN.names(b, "barred"))}
                if is_naming(rid):
                    ckeep[m][f"{rid} {ph}"] |= AN.names(a, "spared") & AN.names(b, "spared")
    bs = json.loads((HERE / "blindspots.json").read_text(encoding="utf-8"))
    fp = [(("neorv32_" + s.split(":")[0]), s.split(":")[1].rsplit(" r", 1)[0], int(s.rsplit(" r", 1)[1])) for s in bs["FP unaddressed list"]]
    fn = []
    for s in bs["FN unaddressed list"]:
        a, st = s.rsplit(" (", 1)
        fn.append(("neorv32_" + a.split(":")[0], a.split(":")[1].rsplit(" r", 1)[0], int(a.rsplit(" r", 1)[1]), st.rstrip(")")))
    fp_left = [x for x in fp if not RB.down(x[1], anybar[x[0]])]
    fn_left = [x for x in fn if not RB.down(x[1], anybar[x[0]]) and not RB.down(x[1], anykeep[x[0]])]
    if not variants:
        ok = (len(fp_left), len(fn_left)) == (bs["FP pairs no rule bars"], bs["FN pairs no rule bars or keeps"])
        print(f"self-test (no new rules: remaining = blindspots.json {bs['FP pairs no rule bars']} / {bs['FN pairs no rule bars or keeps']}): "
              f"{'PASS' if ok else 'FAIL'} ({len(fp_left)} / {len(fn_left)})")
        if not ok:
            sys.exit(1)
    pats = []
    for kind, items in (("FP", fp_left), ("FN", fn_left)):
        a = defaultdict(list)
        for x in items:
            a[(x[0], BS.stem(x[1]))].append(x)
        pats += [{"kind": kind, "group": f"{m[8:]}: {s}*", "pairs": len(xs), "elements": sorted({x[1] for x in xs})}
                 for (m, s), xs in a.items() if len(xs) >= 6]
        b = defaultdict(list)
        for x in items:
            b[BS.ending(x[1])].append(x)
        pats += [{"kind": kind, "group": f"*{e} across {len({x[0] for x in xs})} modules", "pairs": len(xs),
                  "elements": sorted({f'{x[0][8:]}:{x[1]}' for x in xs})[:20]}
                 for e, xs in b.items() if len(xs) >= 6 and len({x[0] for x in xs}) >= 2]
    lst, _ = RB.primaries(RB.V10, mods)
    pairs = defaultdict(lambda: {"elements": [], "reference": 0, "not reference": 0, "v10 primary runs": 0})
    verdict = Counter()
    for m in mods:
        cl = {n for (_, n) in CH.closed_names(m)}
        for e in cl:
            bars = [r for r, s in cbar[m].items() if RB.down(e, s)]
            keeps = [r for r, s in ckeep[m].items() if e in s]
            if bars and keeps:
                for a in bars:
                    for k in keeps:
                        if a.split(" ")[0] == k.split(" ")[0]:
                            continue                    # a rule's own exception against its own bar is not a conflict
                        x = pairs[(a, k)]
                        x["elements"].append(f"{m[8:]}:{e}")
                        x["reference" if e in ref[m] else "not reference"] += 1
                        x["v10 primary runs"] += sum(e in lst[(r, m)] for r in (0, 1, 2))
            v = "both" if bars and keeps else "barred alone" if bars else "kept alone" if keeps else "undecided"
            verdict[(v, e in ref[m])] += 1
    conf = sorted(({"bar": a, "keep": k, **x} for (a, k), x in pairs.items()), key=lambda y: -len(y["elements"]))
    out = {"variants": variants, "remaining FP pairs": len(fp_left), "remaining FN pairs": len(fn_left),
           "of": {"FP": len(fp), "FN": len(fn)}, "remaining patterns": pats,
           "conflict candidates (bar vs keep, consistent)": conf,
           "isolated verdict vs reference": {f"{v} | {'reference' if r else 'not reference'}": n for (v, r), n in sorted(verdict.items())},
           "remaining FP list": [f"{m[8:]}:{n} r{r}" for m, n, r in fp_left], "remaining FN list": [f"{m[8:]}:{n} r{r} ({st})" for m, n, r, st in fn_left]}
    (HERE / f"combine_{tag}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"remaining unaddressed: FP {len(fp_left)} of {len(fp)}, FN {len(fn_left)} of {len(fn)}; patterns {len(pats)}")
    for p in pats:
        print(f"  {p['kind']} {p['group']} {p['pairs']} pairs: {p['elements'][:6]}")
    print(f"conflict candidates: {len(conf)} rule pairs; top:")
    for c in conf[:15]:
        print(f"  {c['bar']:40s} vs {c['keep']:44s} {len(c['elements']):3d} el (ref {c['reference']}, not {c['not reference']}; v10 primary runs {c['v10 primary runs']}) e.g. {c['elements'][:3]}")
    print("isolated verdict vs reference:", json.dumps(out["isolated verdict vs reference"]))


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(a[0], a[1:], only_pass="--all" not in sys.argv)
