"""v10's Phase 2 on v11's Phase 1 (PLAN_COMPARE.md; user 2026-10-17: "First run PLAN_COMPARE.md (v10 Phase 2 on v11
Phase 1, 38 calls, about USD 1.05) as planned, then decide on N12 and N14.").

two_phase_v11h = v11's phase1.md + v10's phase2.md (v10 + F1 + F2, without F3 and F4), a diagnostic hybrid. Phase 1 is
not asked again: v11's 41 stored r0 Phase 1 records are copied in, and the 4 Stage A base-cell r0 Phase 2 records
(asked with v10's phase2 on v11's Phase 1) too, each after a sha check. 37 new Phase 2 calls, plus v11's own
cpu_cp_crypto Phase 2 re-send (its key is logged cut short, so retry_incomplete=True, same max_tokens 128,000).
A crypto reply that breaks again (either arm) gets one more re-send; if still missing it is dropped from both arms in
C1 and scored 0 found in C2.

Readings (PLAN_COMPARE.md 2, set before any call; exact scorer compare_v8.score, r0 only):
  C1 (carry F3 and F4 or not), on the 37 new modules, paired (v11 = with F3+F4, v11h = without):
     carry only if BOTH (a) own-target wrong primaries (REPORT.md 3's measure: Operation selectors P1-22 P2 + the bus
     record-port bar, consistent rule-alone bars, non-reference, listed primary) v11 <= v11h - 3, and (b) they do not
     lose 3 or more correct finds (v11h - v11 >= 3) where a difference counts only if it does not come from one module
     alone. Otherwise do not carry them (the user's default).
     "Not from one module alone", set 2026-10-17 before the send (the plan left the exact test open): the loss counts
     only if it stays >= 3 after removing the module with the largest loss (leave-one-out). The looser reading (the loss
     spread over at least 2 modules) is printed beside it, read only.
     Read only: pooled precision; listed per module with cpu_control apart (cpu_control is a Stage A module, so it is
     outside the 37).
  C2 (does v11h clear the r0 gate?), all 41 modules, exact cuts derived here with Fractions (M1 / M2 cut minus the
     largest one-run shortfall in v9 or v10): tuning_v2 >= 144/206 correct and precision >= 0.40395..; heldout_v2
     >= 69/90 and precision >= 0.53042... Pass -> r1-r2 of v11h is the follow-up (not sent here). Fail -> stop for budget.
  C3 (F1 + F2 against v10, read only): v11h r0 vs v10 r0 per group and per module.
  C4 (v11 complete, read only): v11 r0 with crypto.
Cap: USD 1.6 (38 calls, up to 40 with the crypto re-sends; schema retries, chain's usual one-retry rule, count too).

  python -B compare_v11h.py selftest        (builds and copies nothing; checks readers on stored runs)
  python -B compare_v11h.py build           (writes prompts/two_phase_v11h and copies the stored records)
  python -B compare_v11h.py preview
  <conda python> compare_v11h.py run
  python -B compare_v11h.py read            (writes v11h_compare.json)
"""
import json
import os
import sys
import threading
from collections import Counter
from fractions import Fraction as Fr
from pathlib import Path

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT, V10  # noqa: E402
import v11 as V  # noqa: E402

CH, CK, L, RB, AN, R10, run_a = V.CH, V.CK, V.L, V.RB, V.AN, V.R10, V.run_a
V11, V9, V11H = V.V11, V.V9, "two_phase_v11h"
STAGEA = V.OS_MODS + V.BUS_MODS
BASE = V.CELL["base"]
CRYPTO = "neorv32_cpu_cp_crypto"
CAP_USD = 1.6
OWN = [("P1-22", "P2"), (V.BUS_ID, "P2")]
COPY_P1 = "copied from two_phase_v11 r0 (same system and user message; PLAN_COMPARE.md)"
COPY_P2 = f"copied from the Stage A cell {BASE} r0 (same system and user message; PLAN_COMPARE.md)"


# ------------------------------------------------------------------------------------------------ build ---
def text(version, f):
    return (LAB / "prompts" / version / f).read_text(encoding="utf-8").replace("\r\n", "\n")


def build():
    readme = ("# two_phase_v11h: diagnostic hybrid (built 2026-10-17)\n\nNot a prompt version to use. phase1.md = two_phase_v11's "
              "(v10 + F1 Access command fields + F2 Forwarded transactions P1); phase2.md, common.md and the user templates = "
              "two_phase_v10's (so F3 and F4 are absent). It separates v11's Phase 1 fixes from its Phase 2 moves "
              "(analysis/v10_diagnosis/PLAN_COMPARE.md). Its r0 Phase 1 records are copies of two_phase_v11 r0's. Built by "
              "analysis/v10_diagnosis/compare_v11h.py.\n")
    V.write_version(V11H, text(V11, "phase1.md"), text(V10, "phase2.md"), readme)
    out = CH.run_dir(V11H, MODEL, 0, EFFORT)
    copied = Counter()
    for m in V.mods_ref()[0]:
        src = CH.run_dir(V11, MODEL, 0, EFFORT) / "phase1" / f"{m}.json"
        rec = json.loads(src.read_text(encoding="utf-8"))
        if (rec["system sha"], rec["user sha"]) != (CH.sha12(CK.system(V11H, 1)), CH.sha12(CH.user_message(V11H, 1, m))):
            sys.exit(f"phase 1 sha differs: {m}; stopped")
        dst = out / "phase1" / f"{m}.json"
        if not dst.exists():
            rec["note"] = COPY_P1 + (f"; its own note: {rec['note']}" if rec.get("note") else "")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        copied["phase1"] += 1
    for m in STAGEA:
        src = L.cell_dir(BASE, 0) / "phase2" / f"{m}.json"
        rec = json.loads(src.read_text(encoding="utf-8"))
        r1 = json.loads((out / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
        us = CH.sha12(CH.user_message(V11H, 2, m, CH.concepts_as_written(r1, V11H)))
        if (rec["system sha"], rec["user sha"]) != (CH.sha12(CK.system(V11H, 2)), us):
            sys.exit(f"phase 2 sha differs: {m}; stopped")
        dst = out / "phase2" / f"{m}.json"
        if not dst.exists():
            rec["note"] = COPY_P2
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        copied["phase2"] += 1
        # the assets file, as chain.run_module writes it from the stored replies (no call); added after the run, where
        # it had been done by hand (check of 2026-10-17): it must equal the base cell's own assets file
        concepts = CH.phase1_concepts(r1.get("reply"))
        a = CH.to_assets(m, json.loads(dst.read_text(encoding="utf-8"))["reply"], concepts)
        if a != json.loads((L.cell_dir(BASE, 0) / "assets" / f"{m}.json").read_text(encoding="utf-8")):
            sys.exit(f"assets differ from the base cell's: {m}; stopped")
        (out / "assets").mkdir(parents=True, exist_ok=True)
        (out / "assets" / f"{m}.json").write_text(json.dumps(a, indent=1, ensure_ascii=False), encoding="utf-8")
        copied["assets"] += 1
    print("built", V11H, "; copied", dict(copied))


def build_check(log=print):
    c = {}
    c["v11h phase 1 system = v11's"] = CK.system(V11H, 1) == CK.system(V11, 1)
    c["v11h phase 2 system = v10's"] = CK.system(V11H, 2) == CK.system(V10, 2)
    c["v11h user templates = v10's (= v11's)"] = all((LAB / "prompts" / V11H / f).read_bytes() == (LAB / "prompts" / V10 / f).read_bytes() == (LAB / "prompts" / V11 / f).read_bytes()
                                                    for f in ("phase1_user.md", "phase2_user.md", "common.md"))
    c["check_lab_prompt passes v11h"] = CK.check(V11H, log=lambda *a: None)
    out = CH.run_dir(V11H, MODEL, 0, EFFORT)
    mods = V.mods_ref()[0]
    c["41 phase 1 copies, each noted"] = sum(COPY_P1 in str(json.loads((out / "phase1" / f"{m}.json").read_text(encoding="utf-8")).get("note"))
                                             for m in mods if (out / "phase1" / f"{m}.json").exists()) == 41
    c["4 phase 2 copies (the Stage A modules) and no other phase 2 record yet, or later ones not noted"] = all(
        COPY_P2 in str(json.loads((out / "phase2" / f"{m}.json").read_text(encoding="utf-8")).get("note")) for m in STAGEA)
    c["the 4 Stage A modules' assets equal the base cell's"] = all(
        (out / "assets" / f"{m}.json").exists() and json.loads((out / "assets" / f"{m}.json").read_text(encoding="utf-8"))
        == json.loads((L.cell_dir(BASE, 0) / "assets" / f"{m}.json").read_text(encoding="utf-8")) for m in STAGEA)
    c["no _run_meta / _keys / _failed_calls copied (only what this run writes)"] = not (out / "_failed_calls.jsonl").exists() or \
        all(json.loads(x).get("key") != "a464af9b642a" for x in (out / "_failed_calls.jsonl").read_text(encoding="utf-8").splitlines() if x.strip())
    bad = [k for k, ok in c.items() if not ok]
    log(f"build check ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


# ------------------------------------------------------------------------------------------------ readers ---
def score_dir(d, m):
    """compare_v8.score on a run folder (for the Stage A base cell, which is not a run_dir)."""
    f = Path(d) / "assets" / f"{m}.json"
    if not f.exists():
        return None
    names = [x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]]
    listed, found = Counter(names), 0
    for n in V.cvref()[m]:
        if listed[n] > 0:
            listed[n] -= 1
            found += 1
    return len(names), found


def sc(v, m):
    return score_dir(CH.run_dir(v, MODEL, 0, EFFORT), m)


def own_target(assets_of, mods):
    """REPORT.md 3's measure for F3's and F4's targets: closed-set elements the rule-alone Phase 2 wording bars in both
    repeats (rule_breaks.load_latest), listed primary. {rule: {"non-reference": n, "reference": n, "pairs": [...]}}."""
    R, _, _ = V.latest()
    _, ref = V.mods_ref()
    out = {}
    for rid, ph in OWN:
        row = {"non-reference": 0, "reference": 0, "pairs": [], "per module": Counter()}
        for m in mods:
            if (rid, ph, m, 0) not in R or (rid, ph, m, 1) not in R:
                continue
            a = assets_of(m)
            if a is None:
                continue
            b = [AN.names(R[(rid, ph, m, r)], "barred") for r in (0, 1)]
            for e in sorted({n for (_, n) in CH.closed_names(m)} & {n for (_, n) in CH.closed_names(m) if RB.down(n, b[0]) and RB.down(n, b[1])}):   # each name once (v11.read_r0's set)
                if e in a:
                    k = "reference" if e in ref[m] else "non-reference"
                    row[k] += 1
                    if k == "non-reference":
                        row["per module"][m[8:]] += 1
                    row["pairs"].append(f"{m[8:]}:{e}" + (" (reference)" if k == "reference" else ""))
        row["per module"] = dict(row["per module"])
        out[f"{rid} {ph}"] = row
    return out


def gate_cuts():
    """Exact cuts (Fractions): M1 / M2 cut (v9 pooled r0-r2 minus 0.02 / 0.03) minus the largest one-run shortfall
    (pooled minus one run) in v9 or v10, for recall and precision separately (PLAN_MERGED.md 6, re-derived D63)."""
    sp = V.splits()
    out = {}
    for g, ms in sp.items():
        fd = V.findable(ms)
        rows = {v: [V.score_run(v, r, ms)[:2] for r in (0, 1, 2)] for v in (V9, V10)}
        pool = lambda v: (Fr(sum(t for t, _ in rows[v]), 3 * fd), Fr(sum(t for t, _ in rows[v]), sum(l for _, l in rows[v])))  # noqa: E731
        d = Fr(2, 100) if g == "tuning_v2" else Fr(3, 100)
        sr = max(pool(v)[0] - Fr(t, fd) for v in rows for t, _ in rows[v])
        spp = max(pool(v)[1] - Fr(t, l) for v in rows for t, l in rows[v])
        out[g] = {"findable": fd, "recall cut": pool(V9)[0] - d - sr, "precision cut": pool(V9)[1] - d - spp}
    return out


def gate_of(score, mods, cuts):
    """score(m) -> (listed, correct) or None; a missing module scores 0 found and 0 listed (PLAN_COMPARE 1)."""
    T = Ls = 0
    miss = []
    for m in mods:
        s = score(m)
        if s is None:
            miss.append(m[8:])
            continue
        Ls, T = Ls + s[0], T + s[1]
    fd = cuts["findable"]
    need = -(-cuts["recall cut"].numerator * fd // cuts["recall cut"].denominator)    # smallest count >= the cut
    ok_r = Fr(T, fd) >= cuts["recall cut"]
    ok_p = Ls > 0 and Fr(T, Ls) >= cuts["precision cut"]
    return {"correct": T, "listed": Ls, "findable": fd, "correct needed": need, "recall": round(T / fd, 5),
            "precision": round(T / Ls, 5) if Ls else None, "recall cut": float(round(cuts["recall cut"], 5)),
            "precision cut": float(round(cuts["precision cut"], 5)), "missing (scored 0)": miss,
            "recall pass": ok_r, "precision pass": ok_p, "pass": ok_r and ok_p}


def readers_selftest(log=print):
    c = {}
    mods, _ = V.mods_ref()
    sp = V.splits()
    c["score_dir = compare_v8.score on v10 r0, all 41"] = all(score_dir(CH.run_dir(V10, MODEL, 0, EFFORT), m) == (lambda s: (s[0], s[1]))(R10.CV.C8.score(V10, 0, m, V.cvref())) for m in mods)
    cuts = gate_cuts()
    c["cuts = 0.69521 / 0.40395 / 0.76630 / 0.53042 (D63)"] = [round(float(cuts[g][k]), 5) for g in ("tuning_v2", "heldout_v2") for k in ("recall cut", "precision cut")] == [0.69521, 0.40395, 0.7663, 0.53042]
    g10 = {g: gate_of(lambda m: sc(V10, m), sp[g], cuts[g]) for g in sp}
    c["gate: v10 r0 tuning fails at 141 (needs 144)"] = (g10["tuning_v2"]["correct"], g10["tuning_v2"]["correct needed"], g10["tuning_v2"]["pass"]) == (141, 144, False)
    c["gate: v10 r0 heldout passes at 69/90, 69/128"] = (g10["heldout_v2"]["correct"], g10["heldout_v2"]["listed"], g10["heldout_v2"]["pass"]) == (69, 128, True)
    c["gate: v9 r0 passes both"] = all(gate_of(lambda m: sc(V9, m), sp[g], cuts[g])["pass"] for g in sp)
    k11 = [sc(V11, m) for m in STAGEA]
    kb = [score_dir(L.cell_dir(BASE, 0), m) for m in STAGEA]
    c["already known row: v11 (O1) vs base cell r0 on the 4 Stage A modules = 17/81 vs 20/124"] = (
        (sum(x[1] for x in k11), sum(x[0] for x in k11), sum(x[1] for x in kb), sum(x[0] for x in kb)) == (17, 81, 20, 124))
    stored = json.loads((HERE / "v11_r0.json").read_text(encoding="utf-8"))["M4 r0 (Phase 2 breaks)"]
    for v in (V10, V11):
        o = own_target(lambda m, v=v: V.assets(v, m, 0), [m for m in mods if v != V11 or m != CRYPTO])   # v11_r0.json predates v11's crypto reply
        c[f"own-target measure = v11_r0.json's M4 r0 for {v}"] = all(
            (o[f"{r} {p}"]["non-reference"], o[f"{r} {p}"]["reference"]) == (stored[f"{r} {p}"][v]["non-reference"], stored[f"{r} {p}"][v]["reference"]) for r, p in OWN)
    c["v11 r0 has assets for the 40 modules other than crypto"] = all(sc(V11, m) is not None for m in mods if m != CRYPTO)
    bad = [k for k, ok in c.items() if not ok]
    log(f"readers self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


# ------------------------------------------------------------------------------------------------ sending ---
def jobs():
    mods, _ = V.mods_ref()
    out = CH.run_dir(V11H, MODEL, 0, EFFORT)
    j = [(V11H, m) for m in mods if not (out / "phase2" / f"{m}.json").exists()]
    if not (CH.run_dir(V11, MODEL, 0, EFFORT) / "phase2" / f"{CRYPTO}.json").exists():
        j.append((V11, CRYPTO))
    return j


def estimate(j):
    """Per job: v10 r0's own Phase 2 cost on the same module (same phase2.md; v11's Phase 1 inputs differ a little)."""
    usd = 0.0
    for _, m in j:
        rec = json.loads((CH.run_dir(V10, MODEL, 0, EFFORT) / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
        usd += run_a.usd(rec["usage"])
    return usd


def preview():
    j = jobs()
    est = estimate(j)
    print(f"{len(j)} Phase 2 calls ({sum(v == V11H for v, _ in j)} v11h, {sum(v == V11 for v, _ in j)} v11 crypto re-send); "
          f"about USD {est:.3f} (v10 r0's own Phase 2 cost on the same modules); cap USD {CAP_USD}; up to 2 crypto re-sends "
          f"after a break at about USD 0.158 each")
    print(f"spent so far USD {run_a.spent(log=lambda *a: None):.2f}")


def run():
    if not (V.builder_selftest(log=lambda *a: None) and build_check(log=print) and readers_selftest(log=print)):
        sys.exit("self-test FAIL; nothing sent")
    j = jobs()
    est = estimate(j)
    if len(j) > 38 or est + 2 * 0.158 > CAP_USD:
        sys.exit(f"{len(j)} jobs, about USD {est:.3f}: over the plan or the cap; nothing sent")
    V.track([LAB / "runs" / f"{V11H}__v1" / f"{MODEL}__{EFFORT}"])
    start = run_a.spent(log=lambda *a: None)
    print(f"sending {len(j)} (about USD {est:.3f}); spent before USD {start:.2f}")
    from concurrent.futures import ThreadPoolExecutor
    stop = CH._new_run_flag()
    outs = {v: CH._prepare(v, MODEL, EFFORT, 0, "openai") for v in (V11H, V11)}

    def make(v, retry):
        return CH.openai(MODEL, EFFORT, out=outs[v], poll=5, retry_incomplete=retry)

    def one(job, retry):
        threading.current_thread().lab_stop = stop
        v, m = job
        call = make(v, retry)
        row = CH._one(v, m, call, outs[v])
        return job, CH._schema_retry(v, m, call, outs[v], row)
    with ThreadPoolExecutor(max_workers=len(j)) as pool:
        res = list(pool.map(lambda x: one(x, x[0] == V11), j))       # v11's crypto key is logged cut short: retry it
    again = [job for job, row in res if job[1] == CRYPTO and "incomplete" in str(row.get("status"))]
    for job in again:                                                  # PLAN_COMPARE 1: one more re-send after a break
        print("crypto broke again:", job[0], "- one more re-send")
        res = [x for x in res if x[0] != job] + [one(job, True)]
    bad = [(job, row.get("status")) for job, row in res if row.get("status") != "done"]
    print("not done:", bad or "none")
    print(f"spent this run USD {run_a.spent(log=lambda *a: None) - start:.3f}")


# ------------------------------------------------------------------------------------------------ readings ---
def read():
    if not readers_selftest(log=print):
        sys.exit("readers self-test FAIL; nothing reported")
    mods, _ = V.mods_ref()
    sp = V.splits()
    grp = {m: g for g, ms in sp.items() for m in ms}
    new37 = [m for m in mods if m not in STAGEA]
    out = {"note": "r0 only; v11 = v10 + F1 + F2 + F3 + F4 (order O1); v11h = v10 + F1 + F2; both on the same stored Phase 1 replies"}
    known = {v: [sc(v, m) for m in STAGEA] for v in (V11, V11H)}
    out["already known (4 Stage A modules; not used in C1): correct / listed"] = {v: [sum(x[1] for x in k), sum(x[0] for x in k)] for v, k in known.items()}
    both = [m for m in new37 if sc(V11, m) is not None and sc(V11H, m) is not None]
    dropped = [m[8:] for m in new37 if m not in both]
    a, b = own_target(lambda m: V.assets(V11, m, 0), both), own_target(lambda m: V.assets(V11H, m, 0), both)
    w11 = sum(a[k]["non-reference"] for k in a)
    w11h = sum(b[k]["non-reference"] for k in b)
    d = {m[8:]: sc(V11H, m)[1] - sc(V11, m)[1] for m in both}
    D = sum(d.values())
    top = max(d.values()) if d else 0
    loo = D - max(top, 0)
    c1a = w11 <= w11h - 3
    lost = D >= 3 and loo >= 3
    out["C1"] = {
        "modules": len(both), "dropped from both arms": dropped,
        "own-target wrong primaries, non-reference (v11 / v11h)": [w11, w11h],
        "per rule (v11 / v11h)": {k: {"v11": a[k], "v11h": b[k]} for k in a},
        "(a) cut by >= 3": c1a,
        "correct finds (v11 / v11h)": [sum(sc(V11, m)[1] for m in both), sum(sc(V11H, m)[1] for m in both)],
        "listed (v11 / v11h)": [sum(sc(V11, m)[0] for m in both), sum(sc(V11H, m)[0] for m in both)],
        "per module correct difference v11h - v11 (non-zero)": {k: x for k, x in sorted(d.items(), key=lambda t: -abs(t[1])) if x},
        "loss (v11h - v11)": D, "largest one-module loss": top, "loss without that module (leave-one-out)": loo,
        "(b) loses >= 3 not from one module alone (leave-one-out, set before the send)": lost,
        "read only: loss >= 3 spread over >= 2 modules": D >= 3 and sum(1 for x in d.values() if x > 0) >= 2,
        "decision": "carry F3 and F4" if (c1a and not lost) else "do not carry F3 and F4 (default)",
    }
    pr = lambda v, ms: (sum(sc(v, m)[1] for m in ms), sum(sc(v, m)[0] for m in ms))  # noqa: E731
    out["C1 read only: pooled precision on the paired modules (correct / listed)"] = {v: pr(v, both) for v in (V11, V11H)}
    out["C1 read only: listed per module (v11 / v11h), largest differences"] = {
        m[8:]: [sc(V11, m)[0], sc(V11H, m)[0]] for m in sorted(both, key=lambda m: -abs(sc(V11H, m)[0] - sc(V11, m)[0]))[:10]}
    out["C1 read only: cpu_control (Stage A) correct / listed (v11 / v11h)"] = [[sc(v, "neorv32_cpu_control")[1], sc(v, "neorv32_cpu_control")[0]] for v in (V11, V11H)]
    out["read only: all 41 modules correct / listed (v11 / v11h)"] = [list(pr(v, mods)) for v in (V11, V11H)]
    cuts = gate_cuts()
    out["C2 gate v11h r0 (all 41)"] = {g: gate_of(lambda m: sc(V11H, m), sp[g], cuts[g]) for g in sp}
    out["C2 pass (go to r1-r2 of v11h)"] = all(x["pass"] for x in out["C2 gate v11h r0 (all 41)"].values())
    out["C2 crypto (correct of its 6 reference entries, listed): v11h, v11"] = [[(sc(v, CRYPTO) or (0, 0))[1], (sc(v, CRYPTO) or (0, 0))[0]] for v in (V11H, V11)]
    c3 = {}
    for g, ms in sp.items():
        rows = {v: (sum((sc(v, m) or (0, 0))[1] for m in ms), sum((sc(v, m) or (0, 0))[0] for m in ms)) for v in (V10, V11H, V11)}
        gained = {m[8:]: (sc(V11H, m) or (0, 0))[1] - sc(V10, m)[1] for m in ms if (sc(V11H, m) or (0, 0))[1] != sc(V10, m)[1]}
        c3[g] = {"correct / listed (v10, v11h, v11)": rows, "per module correct v11h - v10 (non-zero)": gained}
    out["C3 (read only)"] = c3
    out["C4 v11 r0 with crypto (read only)"] = {g: gate_of(lambda m: sc(V11, m), sp[g], cuts[g]) for g in sp}
    (HERE / "v11h_compare.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=list), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False, default=list))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    {"selftest": lambda: sys.exit(0 if readers_selftest() else 1), "build": build,
     "build-check": lambda: sys.exit(0 if build_check() else 1), "preview": preview, "run": run, "read": read}[cmd]()
