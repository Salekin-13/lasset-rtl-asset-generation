"""Overnight prompt-debugging campaign (user 2026-10-18, before sleeping: test the convention bars, the one-primary-per-place rule,
the confidence split, a Phase 1 bar on configuration concepts, and a fix for v9m's menu effect; "do these tests automatically
while keeping an eye on the api credits"; "keep to prompt debugging"). Design (D92, pre-registered):
  Candidates (make_v9n.py): A two_phase_v9n_place (one primary per place, in step 4's core sentence), B two_phase_v9n_conf
  (a Confidence key on each primary; scored sure-only and all), C two_phase_v9n_cfg (Phase 1 bar on tuning settings, a
  reference-convention bar), D two_phase_v9n_menu (v9m + LOCATED as a bound, one per place, keep blocks decide), E
  two_phase_v9n_dbg (Phase 2 bar on debug-module registers, a reference-convention bar).
  Screen: held-out 26, r0 only, two candidates at a time at 3 workers each. Screen gate (against v9j r0 on the held-out 26,
  162 / 296 of 187: recall 0.866, precision 0.547): recall >= 0.82 and precision >= 0.58. Confirm: r1 and r2 for the
  candidates that pass; final cut (the user's): pooled held-out 26 recall >= 0.848 and precision above v9j's 0.569.
  Budget: remaining = user's balance by subtraction (budget_v9n.json, start 18.9 USD, not read); a send is refused when
  remaining minus its estimate would fall below 4.0.
  python -B run_v9n.py build-check | estimate <cand> <reps> | report ;  <conda python> run_v9n.py send <cand> <reps...> --send
"""
import json
import os
import sys
from collections import Counter

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402
import run_v9g as RG  # noqa: E402

V, CH, run_a = RG.V, RG.CH, RG.run_a
CANDS = {"A": "two_phase_v9n_place", "A2": "two_phase_v9n_place2", "AD": "two_phase_v9n_place_dbg", "F": "two_phase_p1o_first", "B": "two_phase_v9n_conf", "C": "two_phase_v9n_cfg", "D": "two_phase_v9n_menu", "E": "two_phase_v9n_dbg"}
V9J = "two_phase_v9j"
BUDGET = HERE / "budget_v9n.json"
FLOOR = 4.0
START = 18.9
SCREEN_R, SCREEN_P = 0.82, 0.58


def groups():
    g, ref = V.R10.CV.groups_and_ref()
    return list(g["held-out"]), ref


def names(v, m, r, sure_only=False):
    f = CH.run_dir(v, MODEL, r, EFFORT) / "assets" / f"{m}.json"
    if not f.exists():
        return None
    rows = json.loads(f.read_text(encoding="utf-8"))["Assets"]
    if sure_only:
        rows = [x for x in rows if x.get("Confidence") == "sure"]
    return [x["Asset RTL"] for x in rows]


def score(v, r, ms, ref, sure_only=False):
    c = l = f = 0
    done = 0
    for m in ms:
        ns = names(v, m, r, sure_only)
        if ns is None:
            continue
        done += 1
        left = Counter(ns)
        for n in ref[m]:
            if left[n] > 0:
                left[n] -= 1
                c += 1
        l += len(ns)
        f += len(ref[m])
    return {"modules": done, "correct": c, "listed": l, "findable": f, "recall": round(c / f, 3) if f else None, "precision": round(c / l, 3) if l else None}


def actual(v, reps=(0, 1, 2)):
    """USD of the stored records of v on the held-out 26 (exact from each record's usage; a call cut short and not stored is
    not in it: add it by hand from the log)."""
    ms, _ = groups()
    s = 0.0
    for r in reps:
        for m in ms:
            for ph in (1, 2):
                f = CH.run_dir(v, MODEL, r, EFFORT) / f"phase{ph}" / f"{m}.json"
                if f.exists():
                    s += run_a.usd(json.loads(f.read_text(encoding="utf-8"))["usage"])
    return s


def budget():
    if BUDGET.exists():
        return json.loads(BUDGET.read_text(encoding="utf-8"))
    b = {"remaining": 18.9, "note": "user's 55.61 (mid v9g A) minus the session's sends by subtraction; not read", "sends": []}
    BUDGET.write_text(json.dumps(b, indent=1), encoding="utf-8")
    return b


def estimate(v, reps):
    ms, _ = groups()
    base = sum(run_a.usd(json.loads((CH.run_dir(V9J, MODEL, 0, EFFORT) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))["usage"]) for m in ms for ph in (1, 2))
    gr = sum(len(V.CK.system(v, ph)) / len(V.CK.system(V9J, ph)) for ph in (1, 2)) / 2
    return base, base * gr * len(reps)


def send(cand, reps):
    v = CANDS[cand]
    ms, _ = groups()
    if not V.CK.check(v, log=lambda *a: None):
        sys.exit("checker FAIL")
    b = budget()
    base, est = estimate(v, reps)
    print(f"{cand} {v} reps {reps}: estimate USD {est:.2f} (v9j held-out r0 USD {base:.2f} x growth x {len(reps)}); remaining USD {b['remaining']:.2f}", flush=True)
    if "--send" not in sys.argv:
        sys.exit("not sent (no --send)")
    if b["remaining"] - est < FLOOR and "--approved" not in sys.argv:
        sys.exit(f"REFUSED: remaining {b['remaining']:.2f} - estimate {est:.2f} < floor {FLOOR} (pass --approved only for a send the user approved after reading the balance)")
    V.track([CH.run_dir(v, MODEL, 0, EFFORT).parent])
    start = run_a.spent(log=lambda *a: None)
    for r in reps:
        res = CH.run_many([(v, r)], ms, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5, retry_incomplete=True), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RUN_WORKERS", "3")))
        bad = [(x["module"], x["status"]) for x in res[(v, r)] if x.get("status") != "done"]
        print(f"{cand} r{r} done; not done: {bad or 'none'}; so far USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)
    spent = actual(v, reps)
    b = budget()
    b["remaining"] = round(b["remaining"] - spent, 3)
    b["sends"].append({"cand": cand, "version": v, "reps": list(reps), "spent": round(spent, 3)})
    BUDGET.write_text(json.dumps(b, indent=1), encoding="utf-8")
    print(f"{cand} spent USD {spent:.3f}; remaining USD {b['remaining']:.2f}", flush=True)


def report():
    ms, ref = groups()
    out = {"v9j": {f"r{r}": score(V9J, r, ms, ref) for r in (0, 1, 2)}}
    v9j_pooled = {k: sum(out["v9j"][f"r{r}"][k] for r in (0, 1, 2)) for k in ("correct", "listed", "findable")}
    out["v9j"]["pooled"] = {**v9j_pooled, "recall": round(v9j_pooled["correct"] / v9j_pooled["findable"], 3), "precision": round(v9j_pooled["correct"] / v9j_pooled["listed"], 3)}
    for cand, v in CANDS.items():
        rows = {}
        for r in (0, 1, 2):
            s = score(v, r, ms, ref)
            if s["modules"]:
                rows[f"r{r}"] = s
                if cand == "B":
                    rows[f"r{r} sure-only"] = score(v, r, ms, ref, sure_only=True)
        if rows:
            full = [rows[f"r{r}"] for r in (0, 1, 2) if f"r{r}" in rows and rows[f"r{r}"]["modules"] == len(ms)]
            if full:
                p = {k: sum(x[k] for x in full) for k in ("correct", "listed", "findable")}
                rows["pooled"] = {"runs": len(full), **p, "recall": round(p["correct"] / p["findable"], 3), "precision": round(p["correct"] / p["listed"], 3)}
                if cand == "B":
                    fs = [rows[f"r{r} sure-only"] for r in (0, 1, 2) if f"r{r} sure-only" in rows]
                    p = {k: sum(x[k] for x in fs) for k in ("correct", "listed", "findable")}
                    rows["pooled sure-only"] = {"runs": len(fs), **p, "recall": round(p["correct"] / p["findable"], 3), "precision": round(p["correct"] / p["listed"], 3) if p["listed"] else None}
            r0 = rows.get("r0")
            if r0 and r0["modules"] == len(ms):
                rows["screen gate (r0: recall >= 0.82, precision >= 0.58)"] = bool(r0["recall"] >= SCREEN_R and r0["precision"] >= SCREEN_P)
            if "pooled" in rows and rows["pooled"]["runs"] == 3:
                rows["final cut (3 runs: recall >= 0.848, precision > 0.569)"] = bool(rows["pooled"]["recall"] >= 0.848 and rows["pooled"]["precision"] > 0.569)
            out[cand] = rows
    b = budget()
    total = sum(actual(v) for v in CANDS.values())
    b["remaining"] = round(START - total - b.get("unstored", 0.0), 3)
    b["sends"] = [{"version": v, "usd": round(actual(v), 3)} for v in CANDS.values() if actual(v) > 0]
    BUDGET.write_text(json.dumps(b, indent=1), encoding="utf-8")
    out["budget"] = b
    (HERE / "read_v9n.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def selftest():
    ms, ref = groups()
    s = score(V9J, 0, ms, ref)
    ok = (s["correct"], s["listed"], s["findable"]) == (162, 296, 187)
    print(f"run_v9n self-test (v9j r0 held-out 26 = 162 / 296 / 187): {'PASS' if ok else 'FAIL ' + str(s)}")
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "selftest":
        sys.exit(0 if selftest() else 1)
    if cmd == "estimate":
        base, est = estimate(CANDS[sys.argv[2]], [int(x) for x in sys.argv[3].split(",")])
        print(f"estimate USD {est:.2f}; remaining {budget()['remaining']:.2f}")
    elif cmd == "send":
        if not selftest():
            sys.exit("self-test FAIL")
        send(sys.argv[2], [int(x) for x in sys.argv[3].split(",")])
    elif cmd == "report":
        if not selftest():
            sys.exit("self-test FAIL")
        out = report()
        for k, v in out.items():
            print(k, json.dumps(v, ensure_ascii=False)[:900])
