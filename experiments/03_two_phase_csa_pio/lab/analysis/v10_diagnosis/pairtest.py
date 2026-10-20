"""Before / after test of the fixes for the conflicting rule pairs (user 2026-10-16: "pair them together and check if
this solves their conflicts ... Test whether the model can: follow both rules when they are compatible; apply the
precedence rule when they genuinely conflict; preserve requirements unrelated to the conflict").

Cells (luna, high, repeats r0-r1, the pair's modules):
  Phase 2 pair (both rules have a Phase 2 wording in the pair): BEFORE = core + both rules (v10 text); AFTER = BEFORE + the
    fix sentence at the end of step 4 (stages.build_p2 add_after). Phase 1 input: luna's v10 Phase 1 replies.
  Phase 1 pair (both Phase 1 wordings): BEFORE = Phase 1 core + both rules; AFTER = BEFORE + the fix right after the bar
    rule's block (p1probe). Phase 1 only.
  Cross-phase pair (Phase 1 bar vs Phase 2 keep): chain cells, Phase 1 = core + the bar's Phase 1 wording (+ fix when the
    fix is in Phase 1), Phase 2 = core + the keep clause (+ fix when the fix is in Phase 2), fed that Phase 1.
Readings (set here, before the cells run; the expected outcome per group comes from the checked analysis):
  conflict   share of (conflict element, repeat) pairs decided the winner's way (bar: not primary / not named; keep:
             primary / named). FIXED when AFTER >= 0.8 and AFTER - BEFORE >= 0.25 or BEFORE already >= 0.8.
  compatible bar-only elements stay barred, keep-only elements stay kept: share in AFTER at least BEFORE - 0.1.
  unrelated  Phase 2: primaries outside the three groups, AFTER vs BEFORE (shared / union) >= 0.8, and the reference finds
             among them not lower by more than 1 pair; Phase 1: elements named outside the groups, same Jaccard reading.

  python -B pairtest.py plan             (writes the cells from conflict_fixes.json; sends nothing)
  <conda python> pairtest.py run
  python -B pairtest.py measure
"""
import json
import os
import sys
import threading

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import ladder as L  # noqa: E402
import p1probe as P  # noqa: E402
import stages as S  # noqa: E402
import run_a  # noqa: E402

FIX = HERE / "conflict_fixes.json"
PLAN = HERE / "pairtest_plan.json"
TITLES = {"P1-14": "Port buffers", "P1-05": "Forwarded transactions", "P1-15": "Sequencing state",
          "P1-20": "Held addresses", "P1-04": "Pacing pulses", "P1-17": "Buffer and engine status bits",
          "P1-HO": "Held outcomes, addresses and settings", "P1-10": "Hand-offs"}


def mods_for(cid, k=3):
    idx = json.loads((HERE / "conflict_packs" / "index.json").read_text(encoding="utf-8"))[cid]
    cnt = {}
    for s in idx["conflict elements"]:
        cnt["neorv32_" + s.split(":")[0]] = cnt.get("neorv32_" + s.split(":")[0], 0) + 1
    return sorted(cnt, key=lambda m: (-cnt[m], m))[:k], idx


def p1_text(keep_titles, bar_title=None, extra=None):
    """Phase 1 core + the given rule blocks; extra lines inserted right after the bar rule's last block line."""
    base = P.build_keep(keep_titles)
    if not extra:
        return base
    lines = base.split(P.LF)
    blk = [(a, b, t) for a, b, t in P.blocks(lines, lines.index("OUTPUT")) if P.base_title(t) == bar_title]
    at = blk[-1][1]
    return P.LF.join(lines[:at] + extra + lines[at:])


def plan():
    fx = {x["id"]: x for x in json.loads(FIX.read_text(encoding="utf-8"))}
    out = {}
    for cid, x in fx.items():
        if x.get("fix_kind") == "none needed" or not x.get("fix_text"):
            continue
        mods, idx = mods_for(cid)
        bar, keep = idx["bar"], idx["keep"]
        if idx["keep phase"] == "P2" and "P2" in idx["bar phases"]:
            kind = "P2"                                     # both rules have a Phase 2 wording in the pair
        elif idx["keep phase"] == "P1" and "P1" in idx["bar phases"]:
            kind = "P1"                                     # both Phase 1 wordings
        else:
            kind = "chain"                                  # Phase 1 bar against a Phase 2 keep clause
        out[cid] = {"kind": kind, "bar": bar, "keep": keep, "modules": mods, "fix": x["fix_text"].strip(), "fix_phase": x.get("fix_phase"),
                    "winner": x.get("winner"), "groups": x.get("boundary_cases"), "conflict": idx["conflict elements"]}
    PLAN.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for cid, p in out.items():
        print(cid, p["kind"], p["bar"], "vs", p["keep"], [m[8:] for m in p["modules"]], "winner", p["winner"], "| fix:", p["fix"][:120])
    return out


def cells():
    """name -> (kind, phase, version text builder args)"""
    pl = json.loads(PLAN.read_text(encoding="utf-8"))
    c = {}
    for cid, p in pl.items():
        if p["kind"] == "P2":
            for tag, add in (("before", None), ("after", p["fix"])):
                c[f"{cid}__{tag}"] = {"phase": 2, "keep": [p["bar"], p["keep"]], "add_after": add, "modules": p["modules"]}
        elif p["kind"] == "P1":
            for tag, add in (("before", None), ("after", p["fix"])):
                c[f"{cid}__{tag}"] = {"phase": 1, "p1": [TITLES[p["bar"]], TITLES[p["keep"]]], "bar_title": TITLES[p["bar"]],
                                      "extra": ["  " + add] if add else None, "modules": p["modules"]}
        else:                                                   # chain: Phase 1 bar, Phase 2 keep
            for tag in ("before", "after"):
                f1 = p["fix"] if tag == "after" and p["fix_phase"] in ("P1", "both") else None
                f2 = p["fix"] if tag == "after" and p["fix_phase"] in ("P2", "both") else None
                c[f"{cid}__{tag}__p1"] = {"phase": 1, "p1": [TITLES[p["bar"]]], "bar_title": TITLES[p["bar"]],
                                          "extra": ["  " + f1] if f1 else None, "modules": p["modules"]}
                c[f"{cid}__{tag}"] = {"phase": 2, "keep": [p["keep"]], "add_after": f2, "modules": p["modules"],
                                      "p1_from": f"{cid}__{tag}__p1"}
    return c


def run():
    from concurrent.futures import ThreadPoolExecutor
    cs = cells()
    stop = CH._new_run_flag()
    n = sum(len(x["modules"]) * 2 for x in cs.values())
    spent = run_a.spent(log=lambda *a: None)
    print(f"{len(cs)} cells, at most {n} calls (about USD {n * 0.025:.2f}); spent so far USD {spent:.2f}")
    if spent + n * 0.025 > 21.5:
        sys.exit("over the cap 21.5; nothing sent")
    L.track_folders(list(cs))

    def p1_job(name, spec):
        text = p1_text(spec["p1"], spec["bar_title"], spec["extra"])
        v = P.cell_version(name, text)
        return v

    jobs1, jobs2 = [], []
    for name, spec in cs.items():
        if spec["phase"] == 1:
            v = p1_job(name, spec)
            for rep in (0, 1):
                out = L.cell_dir(name, rep)
                out.mkdir(parents=True, exist_ok=True)
                call = CH.openai(MODEL, EFFORT, out=out, poll=5)
                for m in spec["modules"]:
                    jobs1.append((v, m, out, call))
    with ThreadPoolExecutor(max_workers=max(1, len(jobs1))) as pool:
        def one(j):
            threading.current_thread().lab_stop = stop
            v, m, out, call = j
            return CH._ask(call, CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                           lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                           adapt=CH.from_format_phase1).get("problems")
        list(pool.map(one, jobs1)) if jobs1 else None
    c2 = L.cells()
    names2 = []
    for name, spec in cs.items():
        if spec["phase"] == 2:
            c2[name] = {"target": "pair", "stage": "pair", "keep": spec["keep"], "last": None, "add_after": spec["add_after"],
                        "modules": spec["modules"], "reps": [0, 1], "p1_from": spec.get("p1_from"), "why": "conflict pair test"}
            names2.append(name)
    (HERE / "cells.json").write_text(json.dumps(c2, indent=1, ensure_ascii=False), encoding="utf-8")
    if names2:
        L.run(names2)
    print("spent after USD", round(run_a.spent(log=lambda *a: None), 2))


def measure():
    pl = json.loads(PLAN.read_text(encoding="utf-8"))
    cs = cells()
    groups, refl = RB_groups()
    out = {}
    for cid, p in pl.items():
        g = p["groups"] or {}
        sets = {k: {s for s in (g.get(k) or []) if ":" in s} for k in ("conflict", "bar_only", "keep_only")}
        sets["conflict"] |= set(p["conflict"])
        res = {}
        for tag in ("before", "after"):
            name = f"{cid}__{tag}"
            spec = cs[name]
            prim, named = {}, {}
            for m in p["modules"]:
                for rep in (0, 1):
                    if spec["phase"] == 2:
                        f = L.cell_dir(name, rep) / "assets" / f"{m}.json"
                        if f.exists():
                            prim[(m, rep)] = {x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]}
                    else:
                        f = L.cell_dir(name, rep) / "phase1" / f"{m}.json"
                        if f.exists():
                            rec = json.loads(f.read_text(encoding="utf-8"))
                            named[(m, rep)] = rec
            def decided(item, want_keep):
                mod, e = item.split(":", 1)
                m = "neorv32_" + mod
                if m not in p["modules"]:
                    return []
                vals = []
                for rep in (0, 1):
                    if spec["phase"] == 2 and (m, rep) in prim:
                        vals.append((e in prim[(m, rep)]) == want_keep)
                    elif spec["phase"] == 1 and (m, rep) in named:      # kept = named or its lines held (over-counts)
                        vals.append((P.p1_named(named[(m, rep)], m, e) != "not in Phase 1") == want_keep)
                return vals
            win_keep = p["winner"] == "keep"
            r = {}
            for k, want in (("conflict", win_keep), ("bar_only", False), ("keep_only", True)):
                v = [x for it in sorted(sets[k]) for x in decided(it, want)]
                r[k] = [sum(v), len(v)]
            if spec["phase"] == 2:
                outside = {(m, rep): {e for e in s if f"{m[8:]}:{e}" not in set().union(*sets.values())} for (m, rep), s in prim.items()}
                r["_outside"] = {f"{m}|{rep}": sorted(s) for (m, rep), s in outside.items()}
                r["_ref outside"] = sum(len(s & set(refl[m])) for (m, rep), s in outside.items())
            res[tag] = r
        if "_outside" in res["before"]:
            a, b = res["before"]["_outside"], res["after"]["_outside"]
            sh = sum(len(set(a[k]) & set(b.get(k, []))) for k in a)
            un = sum(len(set(a[k]) | set(b.get(k, []))) for k in a)
            res["unrelated agreement (shared / union)"] = [sh, un, round(sh / un, 3) if un else None]
            res["reference finds outside, before -> after"] = [res["before"]["_ref outside"], res["after"]["_ref outside"]]
            for t in ("before", "after"):
                res[t].pop("_outside")
        out[cid] = res
        cb, ca = res["before"]["conflict"], res["after"]["conflict"]
        rb_, ra = (cb[0] / cb[1] if cb[1] else None), (ca[0] / ca[1] if ca[1] else None)
        res["conflict FIXED"] = bool(ra is not None and ra >= 0.8 and (rb_ is None or ra - rb_ >= 0.25 or rb_ >= 0.8))
        print(f"{cid} ({p['kind']}, winner {p['winner']}): conflict {cb} -> {ca}; bar-only {res['before']['bar_only']} -> {res['after']['bar_only']}; "
              f"keep-only {res['before']['keep_only']} -> {res['after']['keep_only']}; unrelated {res.get('unrelated agreement (shared / union)')}, "
              f"reference outside {res.get('reference finds outside, before -> after')}; FIXED {res['conflict FIXED']}")
    (HERE / "pairtest.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


def RB_groups():
    import rule_breaks as RB
    return RB.CV.groups_and_ref()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"plan": plan, "run": run, "measure": measure}[sys.argv[1]]()
