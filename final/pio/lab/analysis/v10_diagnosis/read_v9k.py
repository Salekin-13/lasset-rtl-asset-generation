"""Readings of the rule-alone test of the v9k drafts (claude_rules.py: Claude Sonnet agents, one rule per agent, two
repeats, the modules of claude_rules.PLAN). Both sides run on the same executor; nothing here is compared with a luna
run. Read-only; writes read_v9k.json.

Readings, set 2026-10-17 before any agent ran (the cuts of decision D13, as read_v11n.py applies them):
  New keep rules N21-N25, per wording (rule, phase):
    ambiguity   mean per-module disagreement on the "spared" list (a record and its fields count as one) <= 0.157, and a
                contradiction (one repeat spares, the other bars) in at most 1 module.
    coverage    intended cases (meta "intended_cases") spared in both repeats: share >= 0.8 on the main wording (P2 where
                the rule has one; P1 reported). N21 is a naming rule: its intended cases are the whole record ports.
    harm        non-reference elements spared in both repeats on the tested modules, no more than the reference entries
                spared in both repeats; and no must-spare case spared in both repeats.
    PASS = ambiguity and harm on every wording, coverage on the main wording.
  Revised bar rules P1-04, P1-14, P1-15, old (v11r3) against new, per wording:
    targets     intended cases barred in both repeats: new must be 0 (an intended case the old text also leaves alone
                tells "no harm", not "fixed": Claude may not show luna's misreading; say so).
    kept bars   non-reference elements the old text bars in both repeats and the new text bars in both repeats: the new
                text loses none of the must-bar cases; the count of lost non-reference bars is reported.
    ambiguity   as above, on the "barred" list; new not worse than old by more than 0.05.
    PASS = targets 0, no must-bar case lost, ambiguity not worse.
Self-test: read_v11n.decide on a planted reply pair (disagreement 0.5, contradiction, consistent decision set).

  python -B read_v9k.py
"""
import json
import os
import re
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, register  # noqa: E402

ISO = register()
sys.path.insert(0, str(ISO.HERE))
import claude_rules as CR  # noqa: E402,F401  (registers v9k / v9k_old and their __claude1 variants)
import read_v11n as RV  # noqa: E402
import rule_breaks as RB  # noqa: E402
import analyze_isolation as AN  # noqa: E402

CUT_DIS, CUT_COV, CUT_DIS_WORSE = 0.157, 0.8, 0.05
META = json.loads((HERE / "new_rules" / "meta_v9k.json").read_text(encoding="utf-8"))
TEXTS = json.loads((HERE / "new_rules" / "rule_texts_v9k.json").read_text(encoding="utf-8"))
# round 2 (V9K_ROUND=2): the revised rules (rule_texts_v9k2.json) are read from the v9k2 run with their round-2 meta and
# modules (claude_rules.PLAN2); every other rule stays as in round 1. Each rule's verdict uses its latest tested text.
ROUND = os.environ.get("V9K_ROUND", "1")
PLAN = dict(CR.PLAN)
NEW_VARIANT = {rid: "v9k__claude1" for rid in TEXTS}
if ROUND == "2":
    T2 = json.loads((HERE / "new_rules" / "rule_texts_v9k2.json").read_text(encoding="utf-8"))
    M2 = json.loads((HERE / "new_rules" / "meta_v9k2.json").read_text(encoding="utf-8"))
    for rid in T2:
        TEXTS[rid], META[rid], PLAN[rid] = T2[rid], M2[rid], CR.PLAN2[rid]
        NEW_VARIANT[rid] = "v9k2__claude1"


def grams(text, n=4):
    w = re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def exception_text(rid, ph):
    """The wording's Exceptions slot plus the exclusions inside its Scope (clauses after 'other than', 'never', 'not')."""
    t = TEXTS[rid][ph] or ""
    exc = re.findall(r"Exceptions:(.*?)(?:\n  Outcome:|\Z)", t, re.S)
    scope = re.findall(r"Scope:(.*?)(?:\n  Criteria|\Z)", t, re.S)
    excl = []
    for s in scope:
        excl += re.findall(r"(?:other than|never|not an? |not covered|\(not )[^;.)]*", s)
    return " ".join(exc + excl)


def rest_text(rid, ph):
    t = TEXTS[rid][ph] or ""
    return " ".join(re.findall(r"(?:Criteria[^:]*:|Outcome:)(.*?)(?:\n  [A-Z][a-z]+:|\Z)", t, re.S))


def excepted(rid, ph, rule_words):
    """Reading rule for keep rules (added after the first read of the v9k replies, because of the reply format: the
    format has one 'spared' list for elements an exception keeps and for elements the rule keeps as its own piece,
    and some agents file a keep rule's covered elements under 'barred'). An entry is 'excepted' when its quoted rule
    words share more 4-word phrases with the Exceptions and Scope exclusions than with the Criteria and Outcome, or
    begin with 'not covered' / 'Exceptions' / 'other than'."""
    rw = (rule_words or "").strip().lower()
    if rw.startswith(("not covered", "exceptions", "other than", "never ")):
        return True
    g = grams(rw)
    if not g:
        return False
    e, r = len(g & grams(exception_text(rid, ph))), len(g & grams(rest_text(rid, ph)))
    return e > r


def normalize_keep(rid, ph, reply):
    """A keep rule's reply re-filed by the reading rule above: kept = covered by the rule (whichever list the agent used)
    unless excepted; barred = excepted entries and, for the naming rule N21, its fields (the Outcome bars them)."""
    if reply is None:
        return None
    kept, barred, unsure = [], [], list(reply.get("unsure") or [])
    for k in ("spared", "barred"):
        for x in reply.get(k) or []:
            if not isinstance(x, dict) or not x.get("element"):
                continue
            if excepted(rid, ph, x.get("rule words")) or (rid == "N21" and "." in x["element"]):
                barred.append(x)
            else:
                kept.append(x)
    return {"applies": reply.get("applies"), "spared": kept, "barred": barred, "unsure": unsure}


def replies(variant, rid, ph, m, keep=False):
    ISO.use(variant)
    try:
        out = []
        for rep in (0, 1):
            f = ISO.run_root(rep=rep) / ph / rid / f"{m}.json"
            rec = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
            r = rec["reply"] if rec and isinstance(rec.get("reply"), dict) else None
            out.append(normalize_keep(rid, ph, r) if keep else r)
    finally:
        ISO.use("v9")
    return out


def parse(lst):
    return [(s.split(":")[0], s.split(":", 1)[1]) for s in lst or []]


def wording(variant, rid, ph, keep, ref):
    dis, contra, cons_by_m, ocons_by_m, missing = [], [], {}, {}, []
    # round 2 tests the revised text on PLAN2's modules; a round-1 module left out of PLAN2 is read from round 1 (its text
    # differs only in the clause the revision added; the output names these modules under "modules read from round 1")
    r1_mods = [m for m in CR.PLAN[rid]["modules"] if m not in PLAN[rid]["modules"]] if ROUND == "2" and variant.startswith("v9k2") else []
    for m in PLAN[rid]["modules"] + r1_mods:
        reps = replies("v9k__claude1" if m in r1_mods else variant, rid, ph, m, keep=keep)
        if any(r is None for r in reps):
            missing += [f"{m[8:]} r{i}" for i, r in enumerate(reps) if r is None]
            continue
        d, c, cons, ocons = RV.decide(reps, keep, exact=(META[rid]["kind"].startswith("keep (naming)")))
        if d is not None:
            dis.append(d)
        if c:
            contra.append(m[8:])
        cons_by_m[m], ocons_by_m[m] = cons, ocons
    mean = round(sum(dis) / len(dis), 3) if dis else 0.0
    return {"mean disagreement": mean, "contradiction modules": contra, "modules decided": len(dis),
            "ambiguity PASS": mean <= CUT_DIS and len(contra) <= 1, "missing": missing,
            "modules read from round 1": [m[8:] for m in r1_mods]}, cons_by_m, ocons_by_m


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if not RV.selftest():
        sys.exit(1)
    _, refl = RB.CV.groups_and_ref()
    ref = {m: set(v) for m, v in refl.items()}
    out = {}
    for rid, t in TEXTS.items():
        meta = META[rid]
        keep = meta["kind"].startswith("keep")
        rows = {}
        for ph in PLAN[rid]["phases"]:
            if not t.get(ph):
                continue
            if keep:
                amb, cons, ocons = wording(NEW_VARIANT[rid], rid, ph, True, ref)
                cases = parse(meta["intended_cases"])
                hit, miss = 0, []
                for m, e in cases:
                    if m not in cons:
                        miss.append(f"{m[8:]}:{e} (no replies)")
                    elif e in cons[m]:
                        hit += 1
                    else:
                        miss.append(f"{m[8:]}:{e}")
                harm = sorted(f"{m[8:]}:{e}" for m, s in cons.items() for e in s if e not in ref[m])
                rec = sorted(f"{m[8:]}:{e}" for m, s in cons.items() for e in s if e in ref[m])
                ms = [f"{m[8:]}:{e}" for m, e in parse(meta["must_spare"]) if m in cons and (e in cons[m] or RB.down(e, cons[m]))]
                exp = [f"{m[8:]}:{e}" for m, e in parse(meta.get("expected_harm")) if m in cons and e in cons[m]]
                rows[ph] = {**amb, "intended": len(cases), "spared in both repeats": hit, "coverage": round(hit / len(cases), 3) if cases else None,
                            "not covered": miss, "non-reference spared (both repeats)": harm, "reference spared (both repeats)": rec,
                            "must-spare spared": ms, "expected harm seen": exp, "harm PASS": len(harm) <= len(rec) and not ms}
            else:
                old_amb, old_b, old_s = wording("v9k_old__claude1", rid, ph, False, ref)
                new_amb, new_b, new_s = wording("v9k__claude1", rid, ph, False, ref)
                cases = parse(meta["intended_cases"])
                tgt_old = [f"{m[8:]}:{e}" for m, e in cases if m in old_b and RB.down(e, old_b[m])]
                tgt_new = [f"{m[8:]}:{e}" for m, e in cases if m in new_b and RB.down(e, new_b[m])]
                lost_mb = [f"{m[8:]}:{e}" for m, e in parse(meta["must_bar"]) if m in old_b and m in new_b and RB.down(e, old_b[m]) and not RB.down(e, new_b[m])]
                lost_nonref = sorted(f"{m[8:]}:{e}" for m in old_b if m in new_b for e in old_b[m] if e not in ref[m] and not RB.down(e, new_b[m]))
                gained_nonref = sorted(f"{m[8:]}:{e}" for m in new_b if m in old_b for e in new_b[m] if e not in ref[m] and not RB.down(e, old_b[m]))
                ref_old = sorted(f"{m[8:]}:{e}" for m in old_b for e in old_b[m] if e in ref[m])
                ref_new = sorted(f"{m[8:]}:{e}" for m in new_b for e in new_b[m] if e in ref[m])
                worse = new_amb["mean disagreement"] - old_amb["mean disagreement"] > CUT_DIS_WORSE
                rows[ph] = {"old": old_amb, "new": new_amb, "targets barred by old (both repeats)": tgt_old,
                            "targets barred by new (both repeats)": tgt_new, "must-bar lost by new": lost_mb,
                            "non-reference bars lost old -> new": lost_nonref, "non-reference bars gained old -> new": gained_nonref,
                            "reference entries barred by old": ref_old, "reference entries barred by new": ref_new,
                            "no-harm only (old also left every target alone)": not tgt_old,
                            "PASS": not tgt_new and not lost_mb and not worse and new_amb["ambiguity PASS"]}
        if keep:
            main_ph = "P2" if "P2" in rows else "P1"
            cov_ok = rows[main_ph]["coverage"] is not None and rows[main_ph]["coverage"] >= CUT_COV
            rows["PASS"] = all(r["ambiguity PASS"] and r["harm PASS"] for k, r in rows.items() if k != "PASS") and cov_ok
            rows["main wording"] = main_ph
        else:
            rows["PASS"] = all(r["PASS"] for k, r in rows.items() if k != "PASS")
        rows["title"], rows["kind"], rows["basis kind"] = t["title"], meta["kind"], meta["basis_kind"]
        out[rid] = rows
    (HERE / f"read_v9k_round{ROUND}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for rid, r in out.items():
        print(f"\n== {rid} {r['title']} [{r['kind']}]: {'PASS' if r['PASS'] else 'FAIL'}")
        for ph in ("P1", "P2"):
            if ph in r:
                x = r[ph]
                if "coverage" in x:
                    print(f"  {ph}: disagreement {x['mean disagreement']} contradictions {x['contradiction modules']} | coverage {x['spared in both repeats']}/{x['intended']} "
                          f"not covered {x['not covered']} | non-ref spared {len(x['non-reference spared (both repeats)'])} {x['non-reference spared (both repeats)'][:12]} | "
                          f"ref spared {len(x['reference spared (both repeats)'])} | must-spare spared {x['must-spare spared']} | missing {x['missing']}")
                else:
                    print(f"  {ph}: targets barred old {x['targets barred by old (both repeats)']} -> new {x['targets barred by new (both repeats)']} | must-bar lost {x['must-bar lost by new']} | "
                          f"non-ref bars lost {len(x['non-reference bars lost old -> new'])} {x['non-reference bars lost old -> new'][:10]} gained {len(x['non-reference bars gained old -> new'])} | "
                          f"disagreement old {x['old']['mean disagreement']} -> new {x['new']['mean disagreement']} | ref barred old {len(x['reference entries barred by old'])} -> new {len(x['reference entries barred by new'])} "
                          f"{x['reference entries barred by new']} | missing old {x['old']['missing']} new {x['new']['missing']} | {'PASS' if x['PASS'] else 'FAIL'}")
    print("\nwritten read_v9k.json")


if __name__ == "__main__":
    main()
