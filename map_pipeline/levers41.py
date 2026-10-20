"""Code levers after generation on the final gpt-5.4 runs: a separately labelled evaluation-layer row
(assetgen_meta/ASSET_DEFINITION.md section 4). No model call; nothing is written.

The levers are the frozen ones in assetgen_meta/post_levers.py (pinned by HELDOUT_PREREG.md, sha12 30b563e562a3), used
unchanged:
  MV    majority vote over the 3 runs: keep an element listed in at least 2 of 3.
  NONE  drop an element whose trace path is "none": its concept's reasoning quotes none of its lines AND the code-built
        relation map does not confirm its realization label (stores / sets / computes / exit port).
  BF    back-fill: add a whole input port the run did not list when its value reaches, within 2 CARRIES / SOURCES steps
        of the map, an element the same run labelled stores or computes (never clock / reset / record ports).
"MV+NONE+BF" = NONE then BF on each run, then the vote. It was pre-registered and adopted on 2026-10-01 for the gpt-5-mini
winner m7e194es0ism (held-out R1: precision gain over MV alone with a 95% module-bootstrap interval above 0, recall >= 0.83).
Here it is applied after the fact to a different prompt and model: not pre-registered, reported as its own row.

Two things matter for reading NONE on gpt-5.4.
  - The gpt-5-mini winner wrote RTL statements out in its reasoning, so most of its elements were "quoted". gpt-5.4
    mostly cites line numbers instead, so on gpt-5.4 NONE rests mostly on the map's confirmation of the label.
    path_shares() returns the shares for one set of runs; the notebook prints them for both models.
  - The confirmation rule for "stores" is the map's storage class "edge" (asset_trace.RULES). A clocked register that
    also has a constant assignment somewhere is "mixed" and is not confirmed: for example the hard-wired x0 register,
    `reg_file(0) <= (others => '0');` (data/RTL_heldout/neorv32_cpu_regfile.vhd:117), beside its clocked writes at
    lines 84-86. none_drops() counts NONE's drops by label and storage class.

post_levers.py still names the pre-2026-10-02 layout in two places, and it is pinned, so it is not edited. This module
passes the new folders as arguments (runs/ stem, data/RTL_*) and replaces post_levers.references at run time with the same
function reading data/ground_truth and data/parsed_tuning18.

Self-test (all must hold, or nothing is reported):
  1. the 17 recorded tuning stacks of post_levers.TUNING_RECORDED and the LAsset initial row reproduce to 3 decimals
     (gpt-5-mini winner, 15 tuning modules, 111 entries);
  2. the stored held-out reading reproduces (assetgen_meta/heldout_readings.json: base, MV and MV+NONE+BF precision and
     recall, and the R1 bootstrap interval, to 3 decimals; 26 modules, 189 entries);
  3. the gpt-5.4 base rows equal map_pipeline/results41.py's per-run means (run_means: P_mean, R_mean) for both splits.

    python map_pipeline/levers41.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in ("src", "assetgen_meta", "step1", "map_pipeline"):
    if str(ROOT / _p) not in sys.path:
        sys.path.insert(0, str(ROOT / _p))

import eval_assets as ea          # noqa: E402
import gt_overlay                 # noqa: E402
import post_levers as PL          # noqa: E402

G54 = "m7e194es0opt1_g54"
STEM = {"tuning": "runs/assets_tuning18", "heldout": "runs/assets_heldout26"}
MAP_DIR = {"tuning": PL.TUNING_MAP_DIR, "heldout": PL.HELDOUT_MAP_DIR}
RTL_DIR = {"tuning": ROOT / "data/RTL_data", "heldout": ROOT / "data/RTL_heldout"}
STACKS = ("base", "MV", "MV+NONE+BF")
BOOT_N, BOOT_SEED = 10000, 0
HELDOUT_READING = ROOT / "assetgen_meta/heldout_readings.json"


def _references(root: Path = ROOT) -> dict:
    """post_levers.references with the 2026-10-02 folders (data/ground_truth, data/parsed_tuning18)."""
    refs = ea.load_refs(gt_dir=Path(root) / "data/ground_truth", parsed_dir=Path(root) / "data/parsed_tuning18")
    return {"original": refs["gt"], "corrected": gt_overlay.corrected(refs["gt"]), "lasset_initial": refs["paper"]}


PL.references = _references


def modules(split: str) -> list[str]:
    if split == "tuning":
        import lasset_step1 as S
        return sorted(S.test_modules())
    import build_heldout_code_map as CM
    return sorted(CM.heldout_modules())


def levers(version: str, split: str) -> PL.Levers:
    return PL.Levers(version, STEM[split], modules(split), MAP_DIR[split], RTL_DIR[split], cond="codetags")


def _r3(x):
    return round(x + 0.0, 3)


def selftest(log=print) -> bool:
    bad = []
    # 1. the recorded tuning stacks of the gpt-5-mini winner
    L = levers(PL.WINNER, "tuning")
    for name, want in PL.TUNING_RECORDED.items():
        s = L.score(name)
        if (_r3(s["precision"]), _r3(s["recall"])) != want:
            bad.append(("tuning " + name, want, (_r3(s["precision"]), _r3(s["recall"]))))
    la = L.lasset()
    if (_r3(la["precision"]), _r3(la["recall"]), la["emit"]) != PL.LASSET_TUNING_RECORDED:
        bad.append(("LAsset initial", PL.LASSET_TUNING_RECORDED, (_r3(la["precision"]), _r3(la["recall"]), la["emit"])))
    if L.score("base")["ref"] != 111 or len(L.modules) != 15:
        bad.append(("tuning denominator", (15, 111), (len(L.modules), L.score("base")["ref"])))
    log(f"  1. post_levers tuning stacks: {len(PL.TUNING_RECORDED)} stacks + LAsset row, "
        f"{'all reproduce' if not bad else 'MISMATCH'}")
    # 2. the stored held-out reading (pre-registered, read once on 2026-10-01)
    rec = json.loads(HELDOUT_READING.read_text(encoding="utf-8"))
    H = levers(PL.WINNER, "heldout")
    n1 = len(bad)
    for name in STACKS:
        s, w = H.score(name), rec["stacks"][name]["original"]
        if (_r3(s["precision"]), _r3(s["recall"])) != (_r3(w["precision"]), _r3(w["recall"])):
            bad.append(("heldout " + name, (_r3(w["precision"]), _r3(w["recall"])), (_r3(s["precision"]), _r3(s["recall"]))))
    bs, wb = H.bootstrap("MV+NONE+BF", "MV", n=BOOT_N, seed=BOOT_SEED), rec["R1"]["bootstrap"]
    got, want = tuple(_r3(bs[k]) for k in ("dP", "dP_lo", "dP_hi")), tuple(_r3(wb[k]) for k in ("dP", "dP_lo", "dP_hi"))
    if got != want:
        bad.append(("heldout R1 bootstrap", want, got))
    if H.score("base")["ref"] != 189 or len(H.modules) != 26:
        bad.append(("heldout denominator", (26, 189), (len(H.modules), H.score("base")["ref"])))
    log(f"  2. stored held-out reading (base, MV, MV+NONE+BF; R1 interval {want}): "
        f"{'reproduces' if len(bad) == n1 else 'MISMATCH'}")
    # 3. the gpt-5.4 base rows against results41
    import final_pipeline as FPL
    import results41 as R41
    ns = FPL.setup()
    mods = FPL.modules(ns.ea)
    n2 = len(bad)
    for split in ("tuning", "heldout"):
        s = levers(G54, split).score("base")
        rm = R41.run_means(ns, mods, "final prompt, gpt-5.4", split)
        want = (_r3(rm["P_mean"]), _r3(rm["R_mean"]))
        if (_r3(s["precision"]), _r3(s["recall"])) != want:
            bad.append((f"gpt-5.4 base {split}", want, (_r3(s["precision"]), _r3(s["recall"]))))
    log(f"  3. gpt-5.4 base rows vs results41 per-run means: {'equal' if len(bad) == n2 else 'MISMATCH'}")
    if bad:
        log(f"levers41 self-test FAIL: {bad}\nnothing is reported")
        return False
    log("levers41 self-test PASS")
    return True


def path_shares(L: PL.Levers) -> dict:
    """Share of listed elements (all runs, before any filter) by best trace path; 'quoted' = full or quoted elsewhere
    or quoted-not-confirmed."""
    from collections import Counter
    c, n = Counter(), 0
    for i, run in enumerate(L.runs):
        for m in L.modules:
            for x in run.get(m, []):
                p = L.trace_of(i, m, x[0], x[1])["paths"]
                best = min(p, key=lambda s: PL.AT.RANK[s]) if p else "none"
                c[best] += 1
                n += 1
    quoted = sum(v for k, v in c.items() if "quoted" in k and "not quoted" not in k or k == "full")
    return {"listed": n, "none": c["none"] / n, "quoted": quoted / n, "confirmed, not quoted": c["confirmed, not quoted"] / n}


def none_drops(L: PL.Levers, gt: str = "original") -> dict:
    """What NONE removes from the unfiltered runs, summed over the runs: {label: {"n", "hits", "mixed"}}, where "mixed"
    counts drops whose map storage class is "mixed" and "hits" those the strict scorer credits (scoring the dropped
    elements alone, per run)."""
    from collections import defaultdict
    out = defaultdict(lambda: {"n": 0, "hits": 0, "mixed": 0})
    for i, run in enumerate(L.runs):
        kept = L.f_none(i, run)
        for m in L.modules:
            keep = {(x[0], x[1]) for x in kept.get(m, [])}
            for x in run.get(m, []):
                if (x[0], x[1]) in keep:
                    continue
                labels = L.trace_of(i, m, x[0], x[1])["labels"] or {"(none)"}
                lab = "/".join(sorted(labels))
                e = L.mentry(m, x[0], x[1])
                hit = ea.score({m: [x]}, L.refs[gt], strict=True, only={m})["tp"]
                out[lab]["n"] += 1
                out[lab]["hits"] += hit
                out[lab]["mixed"] += int(bool(e) and e.get("storage") == "mixed")
    return dict(out)


def lever_table(version: str = G54, log=print) -> dict:
    """base, MV and MV+NONE+BF per split and on all 41 modules, with the MV+NONE+BF minus MV module-bootstrap interval
    per split. base: mean of the 3 runs' P and R; MV stacks: the one voted list."""
    out = {}
    for split in ("tuning", "heldout"):
        L = levers(version, split)
        out[split] = {name: L.score(name) for name in STACKS}
        out[split]["boot"] = L.bootstrap("MV+NONE+BF", "MV", n=BOOT_N, seed=BOOT_SEED)
        out[split]["paths"] = path_shares(L)
        out[split]["none_drops"] = none_drops(L)
    ref = out["tuning"]["base"]["ref"] + out["heldout"]["base"]["ref"]
    out["all41"] = {}
    for name in STACKS:
        a, b = out["tuning"][name]["per_list"], out["heldout"][name]["per_list"]
        ps = [(x[3] + y[3]) / max(x[2] + y[2], 1) for x, y in zip(a, b)]
        rs = [(x[3] + y[3]) / ref for x, y in zip(a, b)]
        out["all41"][name] = {"precision": sum(ps) / len(ps), "recall": sum(rs) / len(rs),
                              "emit": sum(x[2] + y[2] for x, y in zip(a, b)) / len(a), "ref": ref, "lists": len(a)}
    return out


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    sys.stdout.reconfigure(encoding="utf-8")
    if not selftest():
        sys.exit(1)
    res = lever_table()
    for split in ("tuning", "heldout", "all41"):
        for name in STACKS:
            s = res[split][name]
            print(f"{split:8s} {name:11s} P {s['precision']:.3f} R {s['recall']:.3f} emitted {s['emit']:.1f} / {s['ref']}")
        if split != "all41":
            b = res[split]["boot"]
            print(f"{split:8s} MV+NONE+BF - MV: dP {b['dP']:+.3f} [{b['dP_lo']:+.3f}, {b['dP_hi']:+.3f}]; "
                  f"dR {b['dR']:+.3f} [{b['dR_lo']:+.3f}, {b['dR_hi']:+.3f}]  paths {res[split]['paths']}")
