"""Readings of the new rules' rule-alone test (variant v11n, or v11n2 for round 2), with the cuts of decision D13, set
before the run (2026-10-16 07:40). Read-only; writes read_<variant>.json.

Per wording (rule, phase), over the 41 modules with both repeats (luna, high):
  ambiguity    mean per-module disagreement on its decision list (bar / naming: "barred"; keep: "spared"), counting a
               record and its fields as one (analyze_isolation.flips_of), and the modules with a contradiction (one repeat
               bars it, the other keeps it). PASS: mean <= 0.157 and contradictions in <= 1 module.
  coverage     its intended cases (meta "intended_cases", module:element): an intended case the reference lists must be
               kept (spared) in both repeats; one the reference does not list must be barred in both repeats.
               PASS (Phase 2 wording, or the only wording): share >= 0.8. Phase 1 reported.
  harm         bar / naming: reference entries barred in both repeats, any module (PASS: 0); keep: non-reference elements
               kept in both repeats (PASS: no more than the intended cases it recovers). Must-spare entries barred are
               listed.
Overall PASS = every wording passes ambiguity and harm, and the coverage reading passes.
Self-test: analyze_isolation.selftest() (the disagreement and covering code), and a planted reply pair gives the
expected disagreement, contradiction and coverage.

  python -B read_v11n.py [v11n | v11n2]
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, register  # noqa: E402

ISO = register()
import rule_breaks as RB  # noqa: E402
import analyze_isolation as AN  # noqa: E402

CH, CV = RB.CH, RB.CV
CUT_DIS, CUT_COV = 0.157, 0.8


def decide(reps, keep, exact=False):
    """reps: two replies -> (disagreement or None, contradiction?, consistent decision set, consistent opposite set).
    exact (naming rules, revision D18 chosen after the data): names compared exactly, because a naming rule bars a
    record's fields and keeps the record, which the record/field covering would count as a contradiction."""
    dkey, okey = ("spared", "barred") if keep else ("barred", "spared")
    D = [AN.names(x, dkey) for x in reps]
    O = [AN.names(x, okey) for x in reps]
    U = D[0] | D[1]
    if exact:
        f = D[0] ^ D[1]
        c = {e for e in f if e in O[0] | O[1]}
        return (len(f) / len(U) if U else None), bool(c), D[0] & D[1], O[0] & O[1]
    f, c = AN.flips_of(D, O)
    cons = {e for e in D[0] if AN.covered(e, D[1])}
    ocons = {e for e in O[0] if AN.covered(e, O[1])}
    return (len(f) / len(U) if U else None), bool(c), cons, ocons


def selftest():
    ok = AN.selftest(log=lambda *a: None)
    a = {"barred": [{"element": "x"}, {"element": "y"}], "spared": []}
    b = {"barred": [{"element": "x"}], "spared": [{"element": "y"}]}
    dis, con, cons, _ = decide([a, b], keep=False)
    ok2 = abs(dis - 0.5) < 1e-9 and con and cons == {"x"}
    print(f"self-test (analyze_isolation; planted pair: disagreement 0.5, contradiction, consistent bar x): {'PASS' if ok and ok2 else 'FAIL'}")
    return ok and ok2


def main(variant="v11n"):
    sys.stdout.reconfigure(encoding="utf-8")
    if not selftest():
        sys.exit(1)
    meta = json.loads((HERE / "new_rules" / f"meta_{variant}.json").read_text(encoding="utf-8"))
    texts = json.loads((HERE / "new_rules" / f"rule_texts_{variant}.json").read_text(encoding="utf-8"))
    groups, refl = CV.groups_and_ref()
    mods = groups["tuning"] + groups["held-out"]
    ref = {m: set(v) for m, v in refl.items()}
    ISO.use(variant)
    out = {}
    for rid, t in texts.items():
        keep = (meta[rid].get("kind") or "").startswith("keep")
        for ph in ("P1", "P2"):
            if not t.get(ph):
                continue
            dis, contra_m, missing = [], [], []
            cons_by_m, ocons_by_m = {}, {}
            for m in mods:
                reps = []
                for rep in (0, 1):
                    f = ISO.run_root(rep=rep) / ph / rid / f"{m}.json"
                    rec = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
                    if rec is None or not isinstance(rec.get("reply"), dict):
                        missing.append(f"{m[8:]} r{rep}")
                    else:
                        reps.append(rec["reply"])
                if len(reps) < 2:
                    continue
                d, c, cons, ocons = decide(reps, keep, exact=(meta[rid].get("kind") or "").startswith("naming"))
                if d is not None:
                    dis.append(d)
                if c:
                    contra_m.append(m[8:])
                cons_by_m[m], ocons_by_m[m] = cons, ocons
            def parse(lst):
                return [(("neorv32_" + s.split(":")[0]) if not s.startswith("neorv32_") else s.split(":")[0], s.split(":", 1)[1].strip())
                        for s in lst or [] if ":" in s]
            cases = parse(meta[rid].get("intended_cases"))
            wcases = set(parse(meta[rid].get("writer's intended cases")))
            if wcases:                                  # D18 (after the data): a rule whose writer left pack cases out on
                cases = [c for c in cases if c in wcases] or cases   # purpose is read on the cases it was written for
            hit, detail = 0, []
            for m, e in cases:
                if m not in cons_by_m:
                    detail.append(f"{m[8:]}:{e} (no replies)")
                    continue
                if e in ref.get(m, set()):
                    good = (e in cons_by_m[m]) if keep else (e in ocons_by_m[m])     # a reference entry: kept
                else:
                    good = RB.down(e, cons_by_m[m]) if not keep else False
                hit += good
                if not good:
                    detail.append(f"{m[8:]}:{e}")
            if keep:
                harm = sorted(f"{m[8:]}:{e}" for m, s in cons_by_m.items() for e in s if e not in ref[m])
                recovered = sorted(f"{m[8:]}:{e}" for m, s in cons_by_m.items() for e in s if e in ref[m])
                harm_ok = len(harm) <= len(recovered)
            else:
                harm = sorted(f"{m[8:]}:{e}" for m, s in cons_by_m.items() for e in ref[m] if RB.down(e, s))
                recovered = []
                harm_ok = not harm
            mean = round(sum(dis) / len(dis), 3) if dis else 0.0
            row = {"title": t["title"], "kind": meta[rid].get("kind"), "basis kind": meta[rid].get("basis_kind"),
                   "modules deciding something": len(dis), "mean disagreement": mean, "contradiction modules": contra_m,
                   "ambiguity PASS": mean <= CUT_DIS and len(contra_m) <= 1,
                   "intended cases": len(cases), "intended decided as meant (both repeats)": hit,
                   "coverage": round(hit / len(cases), 3) if cases else None, "not covered": detail,
                   "harm list": harm[:40], "harm count": len(harm), "recovered reference entries": recovered[:40],
                   "harm PASS": harm_ok, "missing replies": missing}
            out[f"{rid} {ph}"] = row
    for rid in texts:
        main_ph = "P2" if texts[rid].get("P2") else "P1"
        r = out[f"{rid} {main_ph}"]
        cov_ok = r["coverage"] is None or r["coverage"] >= CUT_COV
        out[f"{rid} {main_ph}"]["coverage PASS"] = cov_ok
        out[rid] = {"PASS": all(out[k]["ambiguity PASS"] and out[k]["harm PASS"] for k in out if k.startswith(rid + " ")) and cov_ok}
    ISO.use("v9")
    (HERE / f"read_{variant}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k, r in out.items():
        if " " in k:
            print(f"{k:8s} {r['title'][:34]:34s} {r['kind'] or '':8s} dis {r['mean disagreement']:.3f} ({r['modules deciding something']} mods) "
                  f"contra {len(r['contradiction modules'])} | coverage {r['intended decided as meant (both repeats)']}/{r['intended cases']} "
                  f"| harm {r['harm count']} (recovered {len(r['recovered reference entries'])}) | amb {'ok' if r['ambiguity PASS'] else 'FAIL'} "
                  f"harm {'ok' if r['harm PASS'] else 'FAIL'}" + (f" cov {'ok' if r.get('coverage PASS') else 'FAIL'}" if 'coverage PASS' in r else ""))
    print("PASS per rule:", {k: v["PASS"] for k, v in out.items() if " " not in k})


if __name__ == "__main__":
    main(*(sys.argv[1:2] or ["v11n"]))
