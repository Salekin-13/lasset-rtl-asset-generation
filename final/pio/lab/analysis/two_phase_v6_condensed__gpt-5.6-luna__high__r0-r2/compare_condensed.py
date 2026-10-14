"""Did condensing change v6's results? The condensed versions of two_phase_v6 (v6a phase1.md condensed, v6b phase2.md
condensed, v6c the shared core sentences condensed, v6abc all three; analysis/prompt_builds/condense_v6/CONDENSE_V6.md;
v6d = v6abc with the traced units restored, v6e = v6 with only v6b's Phase 2 condensing minus traced and register-flagged
units; analysis/prompt_builds/condense_v6/trace/) against v6, gpt-5.6-luna, high, inputs v1, runs r0-r2. Read-only on stored files; writes compare_condensed.json.

Each version is compared with v6 only, never pooled with another version. Reported per version:
  0. completeness: an assets file for each of the 15 modules in each run, no pending request. A module whose reply
     failed the format check again after its one retry (its first reply is in _schema_failed/) can never be completed
     by a re-run: it is scored as an empty list and counted as a slip. v6b only: its Phase 1 replies are still byte
     for byte v6's (the paired design held); if not, the reading says so and the paired rows are left out;
  1. per run (exact scorer: names equal, each reference entry used once; 109 findable): listed, correct, precision,
     recall, F1; the pooled figures of the version's own 3 runs;
  2. the readings set in each version's README before the run:
     - recall below 0.761 (v6's lowest run) in 2 or more runs;
     - precision below 0.601 (v6's lowest run) in 2 or more runs;
     - element losses: found in all 3 v6 runs, in at most 1 run of the version;
     - v6b: correct finds lost against v6 on the same Phase 1 replies in 2 or more runs;
     - format: zero slips. A slip can lose finds: a missing walk, assets nested in points, an asset row without a
       name, a module lost to a format failure after its retry. v6's own count is shown beside it (v6 r2 bus missed
       3 walks), and the target is reported on its own line;
     - v6a: Phase 1 concepts and held lines per run, next to v6's;
  3. how far the version is from v6, measured against how far v6 is from itself:
     - correct finds and listed primaries that differ between two runs (symmetric difference, as sets);
     - v6 vs v6: the 3 pairs of different v6 runs (run-to-run spread);
     - version vs v6: the 9 pairs (each version run against each v6 run); for v6b, the 6 pairs with different run
       numbers, since v6b rX and v6 rX share their Phase 1;
     - v6b only, paired: v6b rX vs v6 rX on the same Phase 1 replies. Phase 2's own spread on a fixed Phase 1 has
       never been measured, so this has no yardstick of its own; read it against the unpaired v6 spread, which also
       holds Phase 1's spread (an upper bound);
  4. element gains (in no v6 run, in 2 or more runs of the version), per-module correct/listed, and cost from the
     stored usage: stored replies, replies moved to _schema_failed/ and failed calls (_failed_calls.jsonl). For v6b,
     Phase 2 only: its Phase 1 replies were paid in v6's runs.

Self-test (runs first; --selftest runs only it):
  - v6 r0-r2 give correct 86/83/86 and listed 143/134/134 (re-derived 2026-10-13 with compare_v6.py's scorer);
  - this scorer equals compare_v6.py's score() on every v6 run and module;
  - v6 compared with itself, unpaired and paired, shows no change signal;
  - simulated runs, made from copies of v6's runs in a temporary folder, give the right readings: an element removed
    from every run is a loss and a paired loss; a module failing its retry is scored empty and counted as a slip; an
    altered Phase 1 copy breaks the paired design.

  python compare_condensed.py
  python compare_condensed.py --selftest
"""
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from itertools import combinations, product
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB.parents[2] / "src"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import cost_estimate as CE  # noqa: E402
import labkit as K  # noqa: E402

MODEL, EFF, REPS = "gpt-5.6-luna", "high", (0, 1, 2)
BASE = "two_phase_v6"
VERSIONS = ("two_phase_v6a", "two_phase_v6b", "two_phase_v6c", "two_phase_v6abc", "two_phase_v6d", "two_phase_v6e")
PAIRED = {"two_phase_v6b": BASE, "two_phase_v6e": BASE,      # version -> the version whose Phase 1 replies it reuses
          "two_phase_v6d": "two_phase_v6abc"}                # (copied by prepare_phase1_copy.py)
MODS = CH.tuning_modules()
FINDABLE = 109
R_MIN, P_MIN = 0.761, 0.601                    # v6's lowest run (README readings)
CLEAN = "no pre-set change signal vs v6"
OVERRIDE = {}                                  # version -> folder holding r0..r2 (self-test simulations only)
V6_PAIRS = list(combinations(REPS, 2))                       # the 3 pairs of different v6 runs
ALL_PAIRS = list(product(REPS, REPS))                        # 9 pairs: each version run against each v6 run
CROSS_PAIRS = [(i, j) for i, j in ALL_PAIRS if i != j]       # 6 pairs: for v6b, leave out the runs sharing a Phase 1


def refs():
    import eval_assets as ea
    with CH.at_root():
        r = ea.load_refs()["gt"]
    out = {}
    for m in MODS:
        names = {n for (_, n) in CH.closed_names(m)}
        out[m] = [n for n, _ in r[m] if n in names]
    return out


REF = refs()


def run_dir(v, r):
    return OVERRIDE[v] / f"r{r}" if v in OVERRIDE else CH.run_dir(v, MODEL, r, EFF)


def failed_after_retry(d, m):
    """The module's reply failed the format check after its one retry: no assets file, and a first reply moved to
    _schema_failed/. A re-run leaves such a module as it is (chain._schema_retry)."""
    return not (d / "assets" / f"{m}.json").exists() and any((d / "_schema_failed" / f"phase{p}" / f"{m}.json").exists() for p in (1, 2))


def score(v, r, m):
    """(listed, correct, found elements, listed (module, element) pairs) for one module of one run. A module that
    failed after its retry counts as an empty list."""
    f = run_dir(v, r) / "assets" / f"{m}.json"
    if not f.exists() and failed_after_retry(run_dir(v, r), m):
        return 0, 0, [], set()
    a = json.loads(f.read_text(encoding="utf-8"))
    names = [x["Asset RTL"] for x in a["Assets"]]
    listed = Counter(names)
    T, found, kth = 0, [], Counter()
    for n in REF[m]:
        kth[n] += 1
        if listed[n] > 0:
            listed[n] -= 1
            T += 1
            found.append(f"{m.replace('neorv32_', '')}:{n}#{kth[n]}")
    return len(names), T, found, {f"{m.replace('neorv32_', '')}:{n}" for n in names}


def complete(v):
    """Per run: modules with an assets file, modules lost to a format failure after the retry, modules still missing
    (a re-run collects them), pending requests, failed calls, retried replies."""
    out = {}
    for r in REPS:
        d = run_dir(v, r)
        lost = [m for m in MODS if failed_after_retry(d, m)]
        out[r] = {"assets files": sum((d / "assets" / f"{m}.json").exists() for m in MODS),
                  "format failure after retry": [m.replace("neorv32_", "") for m in lost],
                  "missing": [m.replace("neorv32_", "") for m in MODS
                              if not (d / "assets" / f"{m}.json").exists() and m not in lost],
                  "pending": len(list((d / "_pending").glob("*.json"))) if (d / "_pending").exists() else 0,
                  "failed calls": (len((d / "_failed_calls.jsonl").read_text(encoding="utf-8").splitlines())
                                   if (d / "_failed_calls.jsonl").exists() else 0),
                  "retried replies": (len(list((d / "_schema_failed").rglob("*.json")))
                                      if (d / "_schema_failed").exists() else 0)}
    return out


def _parse(rec):
    try:
        return K.parse_json(rec["raw"])
    except (ValueError, KeyError, TypeError):
        return None


def _usd(u, P):
    if not u or u.get("in") is None:
        return 0.0
    cc = u.get("cached") or 0
    return ((u["in"] - cc) * P["in"] + cc * P["cached"] + (u.get("out") or 0) * P["out"]) / 1e6


def format_and_cost(v, paired):
    P = CE.PRICES[MODEL]
    out = {}
    for r in REPS:
        c = Counter()
        usd = 0.0
        d = run_dir(v, r)
        for m in MODS:
            if failed_after_retry(d, m):
                c["modules lost to a format failure"] += 1
            f1, f2 = d / "phase1" / f"{m}.json", d / "phase2" / f"{m}.json"
            if not f1.exists():
                continue
            rec1 = json.loads(f1.read_text(encoding="utf-8"))
            if not paired:                                       # v6b: its Phase 1 was paid in v6's run
                usd += _usd(rec1.get("usage"), P)
            p1 = _parse(rec1)
            if p1 is None:
                c["unparseable replies"] += 1
                continue
            cons = [x for x in (p1.get("Conceptual Assets") or []) if isinstance(x, dict)]
            ids = [x.get("Concept ID") for x in cons]
            c["concepts"] += len(ids)
            c["held lines"] += sum(len(x["Held Lines"]) if isinstance(x.get("Held Lines"), list) else int(bool(x.get("Held Lines")))
                                   for x in cons)
            _, a = CH.from_format_phase1(p1, rec1["raw"])
            c["other format notes"] += sum(1 for x in a if x.startswith("format:"))
            if f2.exists():
                rec2 = json.loads(f2.read_text(encoding="utf-8"))
                usd += _usd(rec2.get("usage"), P)
                p2 = _parse(rec2)
                if p2 is None:
                    c["unparseable replies"] += 1
                    continue
                _, b = CH.from_format_phase2(p2, rec2["raw"], ids)
                walks = [w for w in (p2.get("Concept Walks", []) or []) if isinstance(w, dict)]
                have = {w.get("Concept ID") for w in walks}
                c["missing walks"] += sum(1 for i in ids if i not in have)
                c["other format notes"] += sum(1 for x in b if x.startswith("format:") and "Concept Walks miss" not in x)
                for w in walks:
                    c["assets nested in points"] += sum(len(p.get("Assets") or []) for p in (w.get("Points") or [])
                                                        if isinstance(p, dict) and isinstance(p.get("Assets"), list))
                    c["asset rows without a name"] += sum(1 for x in (w.get("Assets") or [])
                                                          if isinstance(x, dict) and not x.get("Asset RTL"))
        # paid calls that are not stored replies: first replies moved to _schema_failed/, failed calls
        for f in (d / "_schema_failed").rglob("*.json") if (d / "_schema_failed").exists() else []:
            if paired and f.parent.name == "phase1":
                continue
            usd += _usd(json.loads(f.read_text(encoding="utf-8")).get("usage"), P)
        if (d / "_failed_calls.jsonl").exists():
            phase_of = {}
            if (d / "_keys.jsonl").exists():
                for l in (d / "_keys.jsonl").read_text(encoding="utf-8").splitlines():
                    if l.strip():
                        k = json.loads(l)
                        phase_of[k["key"]] = k.get("phase")
            for l in (d / "_failed_calls.jsonl").read_text(encoding="utf-8").splitlines():
                if l.strip():
                    x = json.loads(l)
                    if paired and phase_of.get(x.get("key")) == 1:
                        continue
                    usd += _usd(x.get("usage"), P)
        c["slips"] = (c["missing walks"] + c["assets nested in points"] + c["asset rows without a name"]
                      + c["modules lost to a format failure"])
        c["usd"] = round(usd, 2)
        out[r] = dict(c)
    return out


def collect(v, paired=None):
    runs, found, listed, correct = {}, Counter(), {}, {}
    for r in REPS:
        L = T = 0
        fs, ls = set(), set()
        per_mod = {}
        for m in MODS:
            l, t, f, s = score(v, r, m)
            L, T = L + l, T + t
            fs |= set(f)
            ls |= s
            per_mod[m] = (t, l)
        found.update(fs)
        correct[r], listed[r] = fs, ls
        runs[r] = {"listed": L, "correct": T, "precision": round(T / L, 3) if L else 0.0, "recall": round(T / FINDABLE, 3),
                   "f1": round(2 * T / (L + FINDABLE), 3), "per module": per_mod}
    return {"runs": runs, "found": found, "correct sets": correct, "listed sets": listed,
            "format": format_and_cost(v, (v in PAIRED) if paired is None else bool(paired))}


def spread(a_sets, b_sets, pairs):
    """Mean size of the symmetric difference between the runs of the given (a run, b run) pairs."""
    return round(sum(len(a_sets[i] ^ b_sets[j]) for i, j in pairs) / len(pairs), 1)


def compare(v, base, paired):
    """paired: False, True (Phase 1 reused from v6) or the name of the version whose Phase 1 replies v reuses."""
    out = {"version": v}
    broken = False
    src = (BASE if paired is True else paired) if paired else None
    short = (src or "").replace("two_phase_", "")
    if src:
        same = all((run_dir(v, r) / "phase1" / f"{m}.json").exists()
                   and (run_dir(v, r) / "phase1" / f"{m}.json").read_bytes() == (run_dir(src, r) / "phase1" / f"{m}.json").read_bytes()
                   for r in REPS for m in MODS)
        out[f"phase 1 replies are {short}'s (paired design held)"] = same
        broken = not same
        paired = same                                        # a broken pairing is read as an ordinary full run
    pb = (base if src == BASE else collect(src)) if paired else None      # the paired control's runs
    x = collect(v, paired)
    out["runs"] = {r: {k: s for k, s in x["runs"][r].items() if k != "per module"} for r in REPS}
    L = sum(x["runs"][r]["listed"] for r in REPS)
    T = sum(x["runs"][r]["correct"] for r in REPS)
    out["pooled"] = {"precision": f"{T}/{L} = {T / L:.3f}" if L else "n/a", "recall": f"{T}/{FINDABLE * len(REPS)} = {T / (FINDABLE * len(REPS)):.3f}"}
    rec_low = [r for r in REPS if x["runs"][r]["recall"] < R_MIN]
    pre_low = [r for r in REPS if x["runs"][r]["precision"] < P_MIN]
    allel = set(base["found"]) | set(x["found"])
    lost = sorted(e for e in allel if base["found"][e] == 3 and x["found"][e] <= 1)
    gained = sorted(e for e in allel if base["found"][e] == 0 and x["found"][e] >= 2)
    fc, fb = x["format"], base["format"]
    slip_keys = ("slips", "missing walks", "assets nested in points", "asset rows without a name", "modules lost to a format failure")
    slips, slips6 = sum(fc[r]["slips"] for r in REPS), sum(fb[r]["slips"] for r in REPS)
    out["readings"] = {
        f"1. recall below {R_MIN} in 2 or more runs": f"runs {rec_low} -> {'FALSIFIED' if len(rec_low) >= 2 else 'held'}",
        f"2. precision below {P_MIN} in 2 or more runs": f"runs {pre_low} -> {'FALSIFIED' if len(pre_low) >= 2 else 'held'}",
        "3. element losses (all 3 v6 runs, at most 1 run here)": lost,
        "format: slips that can lose finds (README target 0)": {f"r{r}": {k: fc[r].get(k, 0) for k in slip_keys} for r in REPS},
        "format: the same in v6": {f"r{r}": {k: fb[r].get(k, 0) for k in slip_keys} for r in REPS},
    }
    out["phase 1 concepts / held lines per run: here | v6"] = {
        f"r{r}": f"{fc[r].get('concepts', 0)} / {fc[r].get('held lines', 0)} | {fb[r].get('concepts', 0)} / {fb[r].get('held lines', 0)}" for r in REPS}
    out["other format notes (missing optional fields, key order) per run: here | v6"] = {
        f"r{r}": f"{fc[r].get('other format notes', 0)} | {fb[r].get('other format notes', 0)}" for r in REPS}
    if any(fc[r].get("unparseable replies") for r in REPS):
        out["unparseable replies"] = {f"r{r}": fc[r].get("unparseable replies", 0) for r in REPS}
    out["element gains (no v6 run, 2 or more runs here)"] = gained
    pairs = CROSS_PAIRS if paired and src == BASE else ALL_PAIRS          # leave out runs sharing v6's Phase 1
    out["distance from v6 (mean symmetric difference between runs)"] = {
        "correct finds: v6 vs v6 (3 pairs of different runs)": spread(base["correct sets"], base["correct sets"], V6_PAIRS),
        f"correct finds: this version vs v6 ({len(pairs)} pairs)": spread(x["correct sets"], base["correct sets"], pairs),
        "listed primaries: v6 vs v6 (3 pairs of different runs)": spread(base["listed sets"], base["listed sets"], V6_PAIRS),
        f"listed primaries: this version vs v6 ({len(pairs)} pairs)": spread(x["listed sets"], base["listed sets"], pairs),
    }
    lost_paired = []
    if paired:
        pr = {}
        for r in REPS:
            pr[f"r{r}"] = {f"correct only in {short}": sorted(pb["correct sets"][r] - x["correct sets"][r]),
                           "correct only here": sorted(x["correct sets"][r] - pb["correct sets"][r]),
                           f"listed only in {short}": len(pb["listed sets"][r] - x["listed sets"][r]),
                           "listed only here": len(x["listed sets"][r] - pb["listed sets"][r])}
        n_lost = Counter(e for r in REPS for e in pr[f"r{r}"][f"correct only in {short}"])
        lost_paired = sorted(e for e, n in n_lost.items() if n >= 2)
        out[f"paired with {short} (same Phase 1 replies)"] = pr
        out["paired: correct finds lost in 2 or more runs"] = lost_paired
        if src != BASE:
            out[f"paired control {short}: correct per run"] = {f"r{r}": pb["runs"][r]["correct"] for r in REPS}
    out["cost USD" + (f" (Phase 2 only; Phase 1 was paid in {short}'s runs)" if paired else "")] = {f"r{r}": fc[r]["usd"] for r in REPS}
    out["per module correct/listed"] = {m.replace("neorv32_", ""): [f"{x['runs'][r]['per module'][m][0]}/{x['runs'][r]['per module'][m][1]}" for r in REPS] for m in MODS}
    flags = []
    if broken:
        flags.append(f"PAIRED DESIGN BROKEN: {v.replace('two_phase_', '')}'s Phase 1 replies are not {short}'s, so it is read as a full run")
    if len(rec_low) >= 2:
        flags.append("recall reading")
    if len(pre_low) >= 2:
        flags.append("precision reading")
    if lost:
        flags.append(f"{len(lost)} element losses")
    if lost_paired:
        flags.append(f"{len(lost_paired)} paired losses")
    out["reading"] = ("CHANGED vs v6: " + "; ".join(flags)) if flags else CLEAN
    out["format target (0 slips)"] = "met" if not slips else f"MISSED: {slips} slips (v6 had {slips6})"
    return out


def _simulate(tmp):
    """Copies of v6's runs as a fake version, with planted changes; returns failures."""
    fails = []
    base = collect(BASE)
    src = CH.run_dir(BASE, MODEL, 0, EFF).parent
    always = sorted(e for e, n in base["found"].items() if n == 3)
    target = always[0]                                        # e.g. "bus:alu_res#1"
    mod, name = "neorv32_" + target.split(":")[0], target.split(":")[1].split("#")[0]

    def fake(label):
        d = Path(tmp) / label
        for r in REPS:
            shutil.copytree(src / f"r{r}", d / f"r{r}", ignore=shutil.ignore_patterns("_pending"))
        OVERRIDE[f"fake_{label}"] = d
        return d, f"fake_{label}"

    # (a) unchanged copy, unpaired and paired
    d, v = fake("same")
    for paired in (False, True):
        res = compare(v, base, paired)
        if res["reading"] != CLEAN:
            fails.append(f"simulation: an unchanged copy (paired={paired}) reads {res['reading']}")
    # (b) one always-found element removed from every run
    d, v = fake("loss")
    for r in REPS:
        f = d / f"r{r}" / "assets" / f"{mod}.json"
        a = json.loads(f.read_text(encoding="utf-8"))
        a["Assets"] = [x for x in a["Assets"] if x["Asset RTL"] != name]
        f.write_text(json.dumps(a), encoding="utf-8")
    for paired in (False, True):
        res = compare(v, base, paired)
        want = [target] == res["readings"]["3. element losses (all 3 v6 runs, at most 1 run here)"]
        if not want or "element losses" not in res["reading"] or (paired and res["paired: correct finds lost in 2 or more runs"] != [target]):
            fails.append(f"simulation: removing {target} (paired={paired}) reads {res['reading']}")
    # (c) one module fails after its retry in r0: scored empty, counted as a slip, not 'incomplete'
    d, v = fake("retry")
    rr = d / "r0"
    (rr / "_schema_failed" / "phase2").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(rr / "phase2" / "neorv32_wdt.json", rr / "_schema_failed" / "phase2" / "neorv32_wdt.json")
    (rr / "assets" / "neorv32_wdt.json").unlink()
    c = complete(v)
    if c[0]["format failure after retry"] != ["wdt"] or c[0]["missing"]:
        fails.append(f"simulation: a failed retry is not reported as such: {c[0]}")
    res = compare(v, base, False)
    if res["format target (0 slips)"] == "met" or res["runs"][0]["listed"] >= base["runs"][0]["listed"]:
        fails.append(f"simulation: a failed retry is not scored empty and counted as a slip: {res['format target (0 slips)']}")
    # (d) a changed Phase 1 copy breaks the paired design
    d, v = fake("broken")
    f = d / "r1" / "phase1" / "neorv32_wdt.json"
    f.write_text(f.read_text(encoding="utf-8") + " ", encoding="utf-8")
    res = compare(v, base, True)
    if res.get("phase 1 replies are v6's (paired design held)") is not False or "PAIRED DESIGN BROKEN" not in res["reading"] \
            or "paired with v6 (same Phase 1 replies)" in res:
        fails.append(f"simulation: a broken pairing is not reported: {res['reading']}")
    for k in [k for k in OVERRIDE if k.startswith("fake_")]:
        del OVERRIDE[k]
    return fails


def selftest():
    fails = []
    base = collect(BASE)
    got = ([base["runs"][r]["correct"] for r in REPS], [base["runs"][r]["listed"] for r in REPS])
    if got != ([86, 83, 86], [143, 134, 134]):
        fails.append(f"v6 per run correct/listed {got}, expected [86, 83, 86] / [143, 134, 134]")
    sys.path.insert(0, str(LAB / "analysis" / "two_phase_v6__gpt-5.6-luna__high__r0-r2"))
    import compare_v6 as C6
    for r in REPS:
        for m in MODS:
            if score(BASE, r, m)[:3] != C6.score(BASE, r, m):
                fails.append(f"score() differs from compare_v6.score() on v6 r{r} {m}")
    for paired in (False, True):
        res = compare(BASE, base, paired)
        if res["reading"] != CLEAN or res["readings"]["3. element losses (all 3 v6 runs, at most 1 run here)"] \
                or res["element gains (no v6 run, 2 or more runs here)"]:
            fails.append(f"v6 against itself (paired={paired}) reads {res['reading']}")
        if paired and any(p["correct only in v6"] or p["correct only here"] or p["listed only in v6"] or p["listed only here"]
                          for p in res["paired with v6 (same Phase 1 replies)"].values()):
            fails.append("v6 against itself on the paired path shows differences")
    if compare(BASE, base, False)["distance from v6 (mean symmetric difference between runs)"]["correct finds: v6 vs v6 (3 pairs of different runs)"] == 0:
        fails.append("v6 runs show no spread at all (unexpected)")
    with tempfile.TemporaryDirectory() as tmp:
        fails += _simulate(tmp)
    return fails


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    fails = selftest()
    print("self-test (v6 86/83/86 of 143/134/134; same scorer as compare_v6.py; v6 vs itself clean; simulated runs read right):",
          "PASS" if not fails else "FAIL")
    for f in fails:
        print("  " + f)
    if fails:
        sys.exit(1)
    if "--selftest" in sys.argv:
        return
    base = collect(BASE)
    report = {"v6": {r: {k: s for k, s in base["runs"][r].items() if k != "per module"} for r in REPS}}
    for v in VERSIONS:
        c = complete(v)
        whole = all(not c[r]["missing"] and c[r]["pending"] == 0 for r in REPS)
        print(f"\n=== {v}")
        started = any(c[r]["assets files"] or c[r]["format failure after retry"] or c[r]["pending"] for r in REPS)
        if started:
            print("  completeness:", json.dumps(c))
        if not whole:
            print("  " + ("INCOMPLETE: modules still missing or pending; re-run notebook cell 9 to collect them; nothing is read"
                         if started else "not run yet"))
            report[v] = {"completeness": c, "reading": "incomplete" if started else "not run yet"}
            continue
        res = compare(v, base, PAIRED.get(v, False))
        res["completeness"] = c
        report[v] = res
        for k, val in res.items():
            if k in ("version", "per module correct/listed"):
                continue
            print(f"  {k}: {json.dumps(val, default=str)}")
    (HERE / "compare_condensed.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print("\nwritten:", HERE / "compare_condensed.json")


if __name__ == "__main__":
    main()
