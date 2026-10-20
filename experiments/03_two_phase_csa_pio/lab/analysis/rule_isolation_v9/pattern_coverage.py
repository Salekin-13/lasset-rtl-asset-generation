"""Does each rule, applied alone, catch the whole pattern it was written for? Code only, read-only on runs; nothing is
sent. Writes pattern_coverage.json.

Patterns (independent of the model): the v7 rules round's code detectors (failure_analysis/rules/P1-P4/check_ho.py) state
the testable condition of a bar in closed-set facts and RTL text. Run here over EVERY closed-set element of the 41
modules (not only the elements a reply lists), each match labelled with its test:
  P1 COPY -> Second copies; OPERAND -> Operation selectors (operand-copy sentence); RECORD -> Instance-driven records or
     Forwarded transactions (record only wired); BUSREC -> the bus request/response record port bar; SHIFT -> Serial
     shift registers
  P2 T1, T2 -> Bus handshake copies; T3 -> count-started flag; T4 -> Sequencing state; T5 -> Forwarded transactions
     (merged responses)
  P3 A(...) -> Cached copies; B(...) -> Port buffers
  P4 A -> Register read-back; B1, B2 -> Operation selectors; D -> Per-region checks; E -> Clocks and resets (violation
     reset setting); C (timing flags, a step-3 sentence with no rule of its own) is not mapped
For each match and each wording of its rule: barred in both isolated runs, in one, or in none ("barred" = the element,
its record or one of its fields on the reply's barred list). Also: in the reference (exact name), and listed primary in
how many v9 runs.
Design targets (signals a v8 rule was written to recover, failure_analysis/rules/<R>/item.json "target items"): kept
or not barred by that rule alone, in both runs / one / none.
Self-tests (nothing is written if one fails): each detector's own self-test on its own data; and every element the
detectors flagged on the stored v9 replies (two_phase_v9.../consistency/_flags_P*.json) is found by this scan with the
same entity (and, for P4, the same test).

  python -B pattern_coverage.py
"""
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANA = HERE.parent
RULES = ANA / "two_phase_v7__gpt-5.6-luna__high__r0-r2" / "failure_analysis" / "rules"
ALLIN = ANA / "two_phase_v7__gpt-5.6-luna__high__r0-r2" / "heldout" / "_allinputs"
CONS = ANA / "two_phase_v9__gpt-5.6-luna__high__r0-r2" / "consistency"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ANA / "heldout_versions__gpt-5.6-luna__high__r0-r2"))
import isolation as ISO  # noqa: E402
import analyze_isolation as A  # noqa: E402
import compare_versions as CV  # noqa: E402

CH = ISO.CH
MAP = {("P1", "COPY"): ["P1-06"], ("P1", "OPERAND"): ["P1-22"], ("P1", "RECORD"): ["P1-12", "P1-05"],
       ("P1", "BUSREC"): ["P2X-bus-request-response-record-port"], ("P1", "SHIFT"): ["P1-16"],
       ("P2", "T1"): ["P1-07"], ("P2", "T2"): ["P1-07"], ("P2", "T3"): ["P2X-count-started-flag"], ("P2", "T4"): ["P1-15"],
       ("P2", "T5"): ["P1-05"], ("P3", "A"): ["P1-19"], ("P3", "B"): ["P1-14"],
       ("P4", "A"): ["P1-13"], ("P4", "B1"): ["P1-22"], ("P4", "B2"): ["P1-22"], ("P4", "D"): ["P1-24"], ("P4", "E"): ["P1-02"]}
LABEL = {("P1", "COPY"): "register copying another register", ("P1", "OPERAND"): "register holding one operand",
         ("P1", "RECORD"): "record only wired to an instance", ("P1", "BUSREC"): "bus request/response record port or field",
         ("P1", "SHIFT"): "serial shift register", ("P2", "T1"): "one-bit bus handshake copy", ("P2", "T2"): "re-timed response bit",
         ("P2", "T3"): "count-started flag", ("P2", "T4"): "state register outside a coprocessor",
         ("P2", "T5"): "merged bus responses", ("P3", "A"): "cache data words", ("P3", "B"): "port-buffer FIFO bits",
         ("P4", "A"): "register read-back word", ("P4", "B1"): "operation-selector record field",
         ("P4", "B2"): "operation-selector port", ("P4", "D"): "per-region result", ("P4", "E"): "violation-reset setting"}
KEEPS = {  # v8 rules written to recover signals -> (isolated rule, how "kept" is read)
    "B1": ["P1-11"], "R1": ["P1-26"], "R2": ["P1-15"], "R3": ["P1-17"], "R4": ["P1-21"],
    "R5": ["P2X-input-port-setting-the-value", "P2X-unmixed-copy-output-port", "P1-04", "P1-22"]}
NINE = {"P1-05", "P1-10", "P1-22", "P1-23", "P1-07", "P1-04", "P1-08", "P1-27", "P1-17"}


def load(fx):
    spec = importlib.util.spec_from_file_location(f"det_{fx}", RULES / fx / "check_ho.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(RULES / fx))
    spec.loader.exec_module(mod)
    return mod


def scan():
    """[(detector, test, module, entity, element)] over every closed-set element of the 41 modules; self-tests first."""
    out, ok = [], True
    mods = sorted(p.name for p in ALLIN.iterdir() if (p / "closed_set.json").exists())
    P1 = load("P1")
    f1 = P1.selftest(P1.index_all())
    ok &= not f1
    P1.INPUTS, P1.RAW = ALLIN, HERE / "_no_raw"
    for m in mods:
        rt = P1.load_rtl(m)
        for en, E in P1.load_cs(m).items():
            for n in sorted(E.names()):
                for t in P1.which(E, n, rt):
                    out.append(("P1", t, m, en, n))
    P2 = load("P2")
    ok2, f2, _ = P2.selftest()
    ok &= ok2
    P2.INPUTS = ALLIN
    for m in mods:
        M = P2.Module(m)
        for en in M.ents:
            E = P2.Entity(M, en)
            for n in M.ents[en]:
                for t in P2.verdict(E, n):
                    out.append(("P2", t, m, en, n))
    P3 = load("P3")
    f3 = P3.self_test()
    ok &= not f3
    for m in P3.module_dirs(ALLIN):
        for (en, n), v in P3.module_flags(m, ALLIN).items():
            out.append(("P3", v[0], m, en, n))
    P4 = load("P4")
    ok4, f4 = P4.selftest()
    ok &= ok4
    P4.INPUTS = ALLIN
    for m in mods:
        for (en, n), t in P4.flagged(P4.Unit(m)).items():
            out.append(("P4", t, m, en, n))
    return out, ok, {"P1": f1, "P2": f2, "P3": f3, "P4": f4}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    hits, ok, fails = scan()
    print("detector self-tests:", "PASS" if ok else f"FAIL {fails}")
    if not ok:
        sys.exit(1)
    # self-test: the v9 flags are a subset of this scan
    have = {(fx, m.replace("neorv32_", ""), en, n): t for fx, t, m, en, n in hits}
    miss = []
    for fx in ("P1", "P2", "P3", "P4"):
        fl = json.loads((CONS / f"_flags_{fx}.json").read_text(encoding="utf-8"))
        for r, mods in fl.items():
            for m, rows in mods.items():
                for x in rows:
                    k = (fx, m.replace("neorv32_", ""), x["entity"], x["element"])
                    if k not in have or (fx == "P4" and have[k] != x.get("test")):
                        miss.append((r, *k))
    print(f"self-test (every element the detectors flagged on the v9 replies is in this scan): {'PASS' if not miss else 'FAIL'}",
          f"| scan matches: {len(hits)}")
    if miss:
        print("  ", miss[:10])
        sys.exit(1)
    _, refl = CV.groups_and_ref()
    ref = {m: set(v) for m, v in refl.items()}
    R = A.load(lambda r: ISO.run_root(rep=r))
    texts = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    prim = Counter()
    for m in ref:
        for r in (0, 1, 2):
            f = CH.run_dir(ISO.V9, "gpt-5.6-luna", r, "high") / "assets" / f"{m}.json"
            for n in {x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]}:
                prim[(m, n)] += 1

    def barred_runs(rid, ph, m, n, key="barred"):
        if (rid, ph, m, 0) not in R or (rid, ph, m, 1) not in R:
            return None
        return sum(A.covered(n, A.names(R[(rid, ph, m, r)], key)) for r in (0, 1))

    pats = defaultdict(set)
    for fx, t, m, en, n in hits:
        key = (fx, t[0] if fx == "P3" else t)
        if key in MAP:
            pats[key].add((m, n))
    rows, out = [], {}
    for key, inst in sorted(pats.items(), key=lambda kv: -len(kv[1])):
        rids = MAP[key]
        res = {}
        for ph in ("P1", "P2"):
            c = Counter()
            for m, n in inst:
                b = [barred_runs(rid, ph, m, n) for rid in rids if texts.get(rid, {}).get(ph)]
                b = [x for x in b if x is not None]
                if not b:
                    continue
                c[{2: "both runs", 1: "one run", 0: "never"}[max(b)]] += 1
            if c:
                res[ph] = dict(c)
        inref = sum(n in ref.get(m, set()) for m, n in inst)
        fp9 = sum(1 for m, n in inst if prim[(m, n)] and n not in ref.get(m, set()))
        out[f"{key[0]} {key[1]}"] = {"pattern": LABEL[key], "rules": [texts[r]["title"] for r in rids], "instances": len(inst),
                                     "modules": len({m for m, _ in inst}), "in the reference (exact)": inref,
                                     "v9 false positives among them (listed primary in some run)": fp9, "barred alone": res,
                                     "never barred, examples": sorted(f"{m[8:]}:{n}" for m, n in inst
                                                                      if all((barred_runs(rid, ph, m, n) or 0) == 0 for rid in rids for ph in ("P1", "P2")))[:8]}
        rows.append((key, rids, len(inst), inref, fp9, res))
    print(f"\n{'pattern':40s} {'rule':30s} inst ref v9FP | P1 both/one/never | P2 both/one/never")
    for key, rids, ni, inref, fp9, res in rows:
        f = lambda ph: "/".join(str(res.get(ph, {}).get(k, 0)) for k in ("both runs", "one run", "never")) if ph in res else "-"  # noqa: E731
        nm = texts[rids[0]]["title"][:30] + (" *" if any(r in NINE for r in rids) else "")
        print(f"{LABEL[key][:40]:40s} {nm:30s} {ni:4d} {inref:3d} {fp9:4d} | {f('P1'):17s} | {f('P2')}")
    # design targets of the v8 keep rules
    tgt = {}
    print("\nv8 design targets (signals a rule was written to recover): kept by the rule alone")
    for rk, rids in KEEPS.items():
        item = json.loads((RULES / rk / "item.json").read_text(encoding="utf-8"))
        els = sorted({(f"neorv32_{x.split(':')[1]}", x.split(':')[2].split('#')[0]) for x in item["target items"] if x.startswith("M:")})
        rows = []
        for m, n in els:
            for rid in rids:
                for ph in ("P1", "P2"):
                    if not texts.get(rid, {}).get(ph):
                        continue
                    k = barred_runs(rid, ph, m, n, "spared")
                    b = barred_runs(rid, ph, m, n, "barred")
                    if k is None:
                        continue
                    if k or b or rid in ("P1-11", "P1-26", "P1-21") or rid.startswith("P2X"):
                        rows.append({"signal": f"{m[8:]}:{n}", "rule": texts[rid]["title"], "wording": ph,
                                     "kept in runs": k, "barred in runs": b, "in the reference": n in ref.get(m, set())})
        tgt[rk] = {"title": item["title"], "targets": rows}
        for x in rows:
            print(f"  {rk} {x['rule'][:34]:34s} {x['wording']} {x['signal']:32s} kept {x['kept in runs']}/2 barred {x['barred in runs']}/2 ref {x['in the reference']}")
    (HERE / "pattern_coverage.json").write_text(json.dumps({"patterns": out, "v8 design targets": tgt}, indent=1, ensure_ascii=False),
                                                encoding="utf-8")


if __name__ == "__main__":
    main()
