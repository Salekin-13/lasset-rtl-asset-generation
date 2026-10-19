"""Failure patterns of v11 (user 2026-10-17: "analyze the failure patterns of v11. was any of the FNs & FPs due to missing
rules to address them? If so, draft rules to address them and perform isolated tests of the rules to verify they find
target assets or bar FPs"). Read-only; writes blindspots_v11.json. Sends nothing.

Data: v11 r0 only (the stop gate stopped r1-r2, D62), the 40 modules with a stored reply (cpu_cp_crypto's Phase 2 broke).
Rules: v11's own wordings, each from its luna rule-alone run: rule_breaks.load_latest (v10's wordings) with Access
command fields P1 taken from v12t (the 474-word tightened text; v11 carries it without one part (b) sentence, D60) and
Forwarded transactions P1 from v11p. The drafted rules N01-N10 (not in v11): their passing rule-alone runs (v11n, v11n2,
v11n3; combine.load_new).
Definitions (blindspots.py's, unchanged): an FP is unaddressed when no rule wording bars it alone in EITHER repeat (the
element or a record it is a field of); an FN is unaddressed when no rule bars it and no primary-making rule keeps it in
either repeat. Exact scorer matching (each reference entry used once).
Bins: (1) addressed by a v11 rule (the rule exists; v11 broke it or its bar is unclear); (2) unaddressed by v11 but
covered by a drafted rule N01-N10; (3) unaddressed by anything: a new blind spot.
Pattern cut (set 2026-10-17 before this script ran): decision D8's 6 (element, run) pairs over 3 runs, scaled to one run
= 2 pairs in r0, for (a) one module and one record or name stem, or (b) one name ending across at least 2 modules.
Self-test: the FP / FN totals equal compare_v8.score's for v11 r0 on the same 40 modules.

  python -B blindspots_v11.py
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
import combine as CB  # noqa: E402
import v11 as V  # noqa: E402

CH, T = RB.CH, RB.T
CUT = 2
DRAFT_VARIANTS = ("v11n", "v11n2", "v11n3")


def rule_set(mods):
    R, want, lp = RB.load_latest(mods)
    for (rid, var) in (("P1-23", "v12t"), ("P1-05", "v11p")):
        for k in [k for k in R if k[0] == rid and k[1] == "P1"]:
            del R[k]
        ISO.use(var)
        for m in mods:
            for rep in (0, 1):
                f = ISO.run_root(rep=rep) / "P1" / rid / f"{m}.json"
                if f.exists():
                    rp = json.loads(f.read_text(encoding="utf-8")).get("reply")
                    if isinstance(rp, dict):
                        R[(rid, "P1", m, rep)] = rp
        ISO.use("v9")
    return R, lp


def decisions(R):
    bar, keep = defaultdict(set), defaultdict(set)
    for (rid, ph, m, rep), rp in R.items():
        if BS.adds(rid):
            keep[m] |= AN.names(rp, "spared")
        else:
            bar[m] |= AN.names(rp, "barred")
    return bar, keep


def drafts():
    """{module: (bar set, keep set, {element: [rule ids]})} from the drafted rules' passing WORDINGS (each wording's own
    ambiguity / harm / coverage flags in read_<variant>.json; fixed 2026-10-17 after review: the rule-level PASS dropped
    N04's passing Phase 2 wording). A naming rule's spared list counts as a keep, and its barred list as a bar
    (combine.py's convention; fixed 2026-10-17: the first version read only its barred list)."""
    bar, keep, who = defaultdict(set), defaultdict(set), defaultdict(lambda: defaultdict(set))
    latest = {}                                  # 2026-10-17, after the check: only each wording's LATEST tested text counts
    for var in DRAFT_VARIANTS:                   # (rounds in order); an older text a later round replaced is not mixed in
        t = json.loads((HERE / "new_rules" / f"rule_texts_{var}.json").read_text(encoding="utf-8"))
        for rid, x in t.items():
            for ph in ("P1", "P2"):
                if x.get(ph):
                    latest[(rid, ph)] = var
    for var in DRAFT_VARIANTS:
        R, kinds = CB.load_new(var, only_pass=False)
        rd = json.loads((HERE / f"read_{var}.json").read_text(encoding="utf-8"))
        ok = {k: all(v for a, v in x.items() if a.endswith("PASS")) for k, x in rd.items() if " P" in k}
        for (rid, ph, m, rep), rp in R.items():
            if latest.get((rid, ph)) != var or not ok.get(f"{rid} {ph}"):
                continue
            kind = kinds.get(rid, "")
            lists = (("spared",) if kind.startswith("keep") else ("barred", "spared") if kind.startswith("naming") else ("barred",))
            for k in lists:
                s_ = AN.names(rp, k)
                (keep if k == "spared" else bar)[m] |= s_
                for e in s_:
                    who[m][e].add(f"{rid} {ph} ({var})")
    ISO.use("v9")
    return bar, keep, who


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    mods_all, _ = V.mods_ref()
    refl = V.cvref()
    mods = [m for m in mods_all if V.assets(V.V11, m, 0) is not None]
    R, lp = rule_set(mods_all)
    if lp:
        sys.exit("rule-alone sources incomplete: " + "; ".join(lp[:4]))
    bar, keep = decisions(R)
    dbar, dkeep, who = drafts()
    fp, fn, n_fp, n_fn = [], [], 0, 0
    lp_ = sc_fp = sc_fn = 0
    for m in mods:
        names = [x["Asset RTL"] for x in json.loads((CH.run_dir(V.V11, V.MODEL, 0, V.EFFORT) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]]
        s = V.R10.CV.C8.score(V.V11, 0, m, refl)
        sc_fp += s[0] - s[1]
        sc_fn += len(refl[m]) - s[1]
        left = Counter(names)
        missed = []
        for n in refl[m]:
            if left[n] > 0:
                left[n] -= 1
            else:
                missed.append(n)
        for n, c in left.items():
            for _ in range(c):
                n_fp += 1
                if RB.down(n, bar[m]):
                    b = "v11 rule bars it (broken or unclear)"
                elif RB.down(n, dbar[m]):
                    b = "drafted rule bars it"
                else:
                    b = "no rule"
                fp.append({"module": m, "element": n, "bin": b, "drafts": sorted({r for e in [n] + [".".join(n.split(".")[:i]) for i in range(1, len(n.split(".")))] for r in who[m].get(e, ())})})
        for n in missed:
            n_fn += 1
            st, why = T.where_lost(V.V11, 0, m, n, names)
            if RB.down(n, bar[m]):
                b = "a v11 rule bars it (over-bar)"
            elif RB.down(n, keep[m]):
                b = "v11 keep rule asks for it (broken)"
            elif RB.down(n, dkeep[m]):
                b = "drafted keep rule asks for it"
            elif RB.down(n, dbar[m]):
                b = "drafted rule bars it (would make it worse)"
            else:
                b = "no rule"
            fn.append({"module": m, "element": n, "bin": b, "stage": st,
                       "drafts": sorted(who[m].get(n, ()))})
    ok = (n_fp, n_fn) == (sc_fp, sc_fn)
    print(f"self-test (FP / FN counted here = compare_v8.score's for v11 r0 on {len(mods)} modules, {sc_fp} / {sc_fn}): {'PASS' if ok else 'FAIL'} ({n_fp} / {n_fn})")
    if not ok:
        sys.exit(1)
    sp = V.splits()
    split = {m: g for g, ms in sp.items() for m in ms}
    out = {"modules": len(mods), "left out": [m[8:] for m in mods_all if m not in mods],
           "FP pairs": n_fp, "FP by bin": dict(Counter(x["bin"] for x in fp)),
           "FN pairs": n_fn, "FN by bin": dict(Counter(x["bin"] for x in fn)),
           "FN 'no rule' by stage": dict(Counter(x["stage"] for x in fn if x["bin"] == "no rule")),
           "by split": {g: {"FP no rule": sum(1 for x in fp if split[x["module"]] == g and x["bin"] == "no rule"),
                            "FN no rule": sum(1 for x in fn if split[x["module"]] == g and x["bin"] == "no rule")} for g in sp}}
    pats = []
    for kind, items in (("FP", [x for x in fp if x["bin"] == "no rule"]), ("FN", [x for x in fn if x["bin"] == "no rule"])):
        a = defaultdict(list)
        for x in items:
            a[(x["module"], BS.stem(x["element"]))].append(x)
        for (m, s), xs in a.items():
            if len(xs) >= CUT:
                pats.append({"kind": kind, "group": f"{m[8:]}: {s}*", "pairs": len(xs), "elements": sorted({x['element'] for x in xs}),
                             "stages": dict(Counter(x["stage"] for x in xs)) if kind == "FN" else None, "split": split[m]})
        b = defaultdict(list)
        for x in items:
            b[BS.ending(x["element"])].append(x)
        for e, xs in b.items():
            ms = {x["module"] for x in xs}
            if len(xs) >= CUT and len(ms) >= 2:
                pats.append({"kind": kind, "group": f"*{e} across {len(ms)} modules", "pairs": len(xs),
                             "elements": sorted({f"{x['module'][8:]}:{x['element']}" for x in xs}),
                             "stages": dict(Counter(x["stage"] for x in xs)) if kind == "FN" else None})
    pats.sort(key=lambda p: (p["kind"], -p["pairs"]))
    out["patterns (no rule)"] = pats
    out["FP list"] = [{**x, "module": x["module"][8:]} for x in fp]
    out["FN list"] = [{**x, "module": x["module"][8:]} for x in fn]
    (HERE / "blindspots_v11.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if not k.endswith("list") and not k.startswith("patterns")}, indent=1))
    print(f"patterns (no rule): {len(pats)}")
    for p in pats:
        print(f"  {p['kind']} {p['group']:42s} {p['pairs']:3d} pairs; {p['elements'][:6]}" + (f"; stages {p['stages']}" if p.get("stages") else ""))


if __name__ == "__main__":
    main()
