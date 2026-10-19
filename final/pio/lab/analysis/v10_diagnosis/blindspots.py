"""Blind spots of the rule set (user 2026-10-16, 07:05: "Analyze the failure patterns of the v10's isolated rule runs. If
a pattern is visible in the missed TPs or emitted FPs that are left unaddressed by any rule, write rules for them ...
Only do this if isolated v10 rules have a blindspot for any error patterns in the 41. If that happens, pause the testing
and wake me up"). Read-only; writes blindspots.json. Sends nothing.

Unaddressed, per (module, element, run) of v10 (luna, r0-r2, 41 modules):
  FP  listed primary, not in the reference, and no rule wording bars it alone in EITHER repeat (any rule, either phase,
      the element itself or a record it is a field of): no rule even tries to stop it.
  FN  a reference element not listed primary, and no rule wording bars it alone in either repeat (so no rule caused the
      miss) and no primary-making rule keeps it alone in either repeat (so no rule asks for it). Its stage comes from
      transitions.where_lost (secondary / not reported / Not Kept / never named / ...).
Pattern (cut chosen 2026-10-16 before this script ran, decision D8): a group of unaddressed failures of one kind with at
  least 6 (element, run) pairs, where a group is (a) one module and one record or name stem (the part before the first
  '.', or the whole name), or (b) one field or name ending (the part after the last '.', or the last '_' word of a port)
  across at least 2 modules. Blind spot = at least one pattern.
Self-test: the unaddressed FP / FN totals plus the addressed ones equal read_v10.json's v10 FP and FN over the 41.

  python -B blindspots.py
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

CH, T, CV = RB.CH, RB.T, RB.CV
V10 = RB.V10
ADDS = ("P1-HO", "P1-26")


def adds(rid):
    return AN.adds(rid) or rid in ADDS


def stem(n):
    return n.split(".")[0]


def ending(n):
    if "." in n:
        return "." + n.rsplit(".", 1)[1]
    return "_" + n.rsplit("_", 1)[1] if "_" in n else n


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, refl = CV.groups_and_ref()
    mods = groups["tuning"] + groups["held-out"]
    ref = {m: set(v) for m, v in refl.items()}
    R, want, lp = RB.load_latest(mods)
    if lp:
        sys.exit("rule-alone sources incomplete: " + "; ".join(lp[:4]))
    anybar, anykeep = defaultdict(set), defaultdict(set)
    for (rid, ph, m, rep), rp in R.items():
        if adds(rid):
            anykeep[m] |= AN.names(rp, "spared")
        else:
            anybar[m] |= AN.names(rp, "barred")
    lst, _ = RB.primaries(V10, mods)
    fp, fn, n_fp, n_fn = [], [], 0, 0
    for r in RB.REPS:
        for m in mods:
            names = lst[(r, m)]
            left = Counter(names)                      # the exact scorer: each reference entry used once
            missed = []
            for n in refl[m]:
                if left[n] > 0:
                    left[n] -= 1
                else:
                    missed.append(n)
            for n, c in left.items():
                for _ in range(c):
                    n_fp += 1
                    if not RB.down(n, anybar[m]):
                        fp.append((m, n, r))
            for n in missed:
                n_fn += 1
                if not RB.down(n, anybar[m]) and not RB.down(n, anykeep[m]):
                    st, why = T.where_lost(V10, r, m, n, names)
                    fn.append((m, n, r, st))
    rv = json.loads((HERE / "read_v10.json").read_text(encoding="utf-8"))["all 41"]["v10"]
    ok = (n_fp, n_fn) == (rv["FP"], rv["FN"])
    print(f"self-test (FP / FN counted here = read_v10.json's v10 totals {rv['FP']} / {rv['FN']}): {'PASS' if ok else 'FAIL'} ({n_fp} / {n_fn})")
    if not ok:
        sys.exit(1)
    split = {m: ("heldout_v2" if m in groups["held-out: other 14"] else "tuning_v2") for m in mods}
    out = {"FP pairs": n_fp, "FP pairs no rule bars": len(fp), "FN pairs": n_fn, "FN pairs no rule bars or keeps": len(fn),
           "FN unaddressed by stage": dict(Counter(x[3] for x in fn)),
           "by split": {s: {"FP unaddressed": sum(1 for x in fp if split[x[0]] == s), "FN unaddressed": sum(1 for x in fn if split[x[0]] == s)}
                        for s in ("tuning_v2", "heldout_v2")}}
    pats = []
    for kind, items in (("FP", fp), ("FN", fn)):
        a = defaultdict(list)
        for x in items:
            a[(x[0], stem(x[1]))].append(x)
        for (m, s), xs in a.items():
            if len(xs) >= 6:
                pats.append({"kind": kind, "group": f"{m[8:]}: {s}*", "pairs": len(xs), "elements": sorted({x[1] for x in xs}),
                             "in all 3 runs": sorted(n for n, c in Counter(x[1] for x in xs).items() if c == 3),
                             "stages": dict(Counter(x[3] for x in xs)) if kind == "FN" else None, "split": split[m]})
        b = defaultdict(list)
        for x in items:
            b[ending(x[1])].append(x)
        for e, xs in b.items():
            ms = {x[0] for x in xs}
            if len(xs) >= 6 and len(ms) >= 2:
                pats.append({"kind": kind, "group": f"*{e} across {len(ms)} modules", "pairs": len(xs),
                             "elements": sorted({f"{x[0][8:]}:{x[1]}" for x in xs})[:30],
                             "stages": dict(Counter(x[3] for x in xs)) if kind == "FN" else None})
    pats.sort(key=lambda p: (p["kind"], -p["pairs"]))
    out["patterns"] = pats
    out["blind spot"] = bool(pats)
    out["FP unaddressed, per module (pairs)"] = dict(Counter(x[0][8:] for x in fp).most_common())
    out["FN unaddressed, per module (pairs)"] = dict(Counter(x[0][8:] for x in fn).most_common())
    out["FP unaddressed list"] = [f"{m[8:]}:{n} r{r}" for m, n, r in fp]
    out["FN unaddressed list"] = [f"{m[8:]}:{n} r{r} ({st})" for m, n, r, st in fn]
    (HERE / "blindspots.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if not k.endswith("list") and k != "patterns"}, indent=1))
    print(f"patterns: {len(pats)} (FP {sum(p['kind'] == 'FP' for p in pats)}, FN {sum(p['kind'] == 'FN' for p in pats)})")
    for p in pats:
        print(f"  {p['kind']} {p['group']:42s} {p['pairs']:3d} pairs; {len(p['elements'])} elements; e.g. {p['elements'][:5]}"
              + (f"; stages {p['stages']}" if p.get("stages") else ""))
    print(f"BLIND SPOT: {out['blind spot']}")


if __name__ == "__main__":
    main()
