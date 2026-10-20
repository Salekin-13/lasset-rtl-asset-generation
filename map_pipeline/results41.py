"""Results on the 41 LAsset modules (15 tuning + 26 held-out NEORV32 modules with a manual reference), compared with
LAsset's own published asset lists. Strict scoring (eval_assets.score, strict=True) against the manual reference:
300 reference entries in all (111 tuning, 189 held-out). No model call.

Configurations (CONFIGS, in this order):
  LAsset RTL-only      LAsset's initial list from RTL only. The like-for-like row: our pipeline also reads RTL only.
  LAsset spec+RTL      LAsset's initial list from the specification and the RTL.
  LAsset refined       LAsset's list after its refinement agents.
  final prompt, gpt-5.4     prompt_opt/v1 (sha12 802ee9a90d41) on gpt-5.4. Held-out runs are pending until they exist.
  final prompt, Claude      the same prompt, Claude agent as executor.
  ist2 prompt, Claude       the traced baseline prompt (prompt_opt/v0, sha12 e5fe4918c22b), Claude agent.
  Step-1b gpt-5-mini        the Step-1b winner m7e194es0ism (sha12 0d0def4c6fe3); it does not cite occurrence IDs.

In-sample and out-of-sample. For our four configurations the tuning figures are in-sample: the prompts were chosen on
these 15 modules (prompt_opt v0 -> v1 on the 15 tuning modules, assetgen_meta/prompt_opt/OPTIMIZATION_LOG.md line 3;
the Step-1b winner and the ist2 prompt were also picked on tuning runs, map_pipeline/convergence.csv stages 4 and 6). The
held-out figures are out-of-sample: the 26 modules were not used to choose any prompt. All 41 mixes both. LAsset's lists
were not tuned on this reference by us: they are the published lists, used as they are. score_table carries this as
the column `in_sample` (which split is in-sample: "tuning", or "not tuned by us" for the LAsset lists) and as attrs["in_sample"].

Pooling rule. For a configuration with several runs, TP, FP and FN are averaged per module over the split's complete
runs; precision (P) and recall (R) are computed from the summed means. All 41 adds the two splits' means. This is not the
same as the mean of the per-run precisions that map_pipeline/convergence.csv reports (P_mean): on the final gpt-5.4 tuning runs
the two differ in the third decimal (0.406 pooled, 0.407 mean of the 3 per-run values). score_table gives both: the
pooled P_<split> / R_<split>, and P_runmean_<split> / R_runmean_<split> where a split has more than one complete run.

A run is complete for a split only if both its flat <module>.json and its _nested/<module>.json exist for every module
of the split.

    python map_pipeline/results41.py              # selftest, then the tables
    python map_pipeline/results41.py --write-manifest
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ("tuning", "heldout")
RTL_DIR = {"tuning": "data/RTL_data", "heldout": "data/RTL_heldout"}
MANIFEST = "data/LASSET_41_MODULES.csv"
ENTITY = re.compile(rb"^[ \t]*entity[ \t]+(\w+)[ \t]+is\b", re.I | re.M)


def _runs(stem: str, n: int) -> list[str]:
    return [f"runs/{stem}_r{k}" for k in range(n)]


def _lst(name, which, source, prompt):
    return {"name": name, "executor": "LAsset pipeline (published list)", "prompt": prompt, "tuning": [], "heldout": [],
            "cites_occurrences": False, "kind": "list", "list": which, "source": source,
            "prompt_sha12": None, "prompt_file": None, "in_sample": "not tuned by us"}


IN_SAMPLE_NOTE = {
    "tuning": "in-sample for our configurations: the prompts were chosen on these 15 modules",
    "heldout": "out-of-sample: the 26 modules were not used to choose any prompt",
    "all41": "mixes in-sample (15 tuning modules) and out-of-sample (26 held-out modules)",
    "LAsset": "LAsset's published lists were not tuned on this reference by us (whether LAsset tuned against its own reference is not known)",
}
POOLING_NOTE = ("pooled: mean TP, FP, FN per module over the split's complete runs, then P and R from their sums; "
                "P_runmean / R_runmean: plain mean of the per-run P and R (map_pipeline/convergence.csv), only where runs > 1")


CONFIGS = [
    _lst("LAsset RTL-only", "rtl_only", "data/LAsset_initial_results/asset_list_neorv32_initial.json",
         "LAsset initial list, RTL only (like-for-like with our RTL-only pipeline)"),
    _lst("LAsset spec+RTL", "paper", "data/ground_truth/lasset_initial.json", "LAsset initial list, specification + RTL"),
    _lst("LAsset refined", "paper_refined", "data/ground_truth/lasset_refined.json",
         "LAsset list after refinement (attack scenario, CWE, self-critique)"),
    {"name": "final prompt, gpt-5.4", "executor": "gpt-5.4 (effort high)", "prompt": "final: prompt_opt/v1, sha12 802ee9a90d41",
     "tuning": _runs("assets_tuning18_m7e194es0opt1_g54", 3), "heldout": _runs("assets_heldout26_m7e194es0opt1_g54", 3),
     "cites_occurrences": True, "kind": "runs", "list": None, "source": None,
     "prompt_sha12": "802ee9a90d41", "prompt_file": "assetgen_meta/prompt_opt/v1/exec_prompt.txt", "in_sample": "tuning"},
    {"name": "final prompt, Claude", "executor": "Claude agent (claude-opus-5-5)", "prompt": "final: prompt_opt/v1, sha12 802ee9a90d41",
     "tuning": _runs("assets_opt_v1", 3), "heldout": ["runs/assets_opt_heldout_v1_r0"],
     "cites_occurrences": True, "kind": "runs", "list": None, "source": None,
     "prompt_sha12": "802ee9a90d41", "prompt_file": "assetgen_meta/prompt_opt/v1/exec_prompt.txt", "in_sample": "tuning"},
    {"name": "ist2 prompt, Claude", "executor": "Claude agent (claude-opus-5-5)",
     "prompt": "ist2, the traced baseline: prompt_opt/v0, sha12 e5fe4918c22b",
     "tuning": _runs("assets_opt_v0", 2), "heldout": ["runs/assets_opt_heldout_v0_r0"],
     "cites_occurrences": True, "kind": "runs", "list": None, "source": None,
     "prompt_sha12": "e5fe4918c22b", "prompt_file": "assetgen_meta/prompt_opt/v0/exec_prompt.txt", "in_sample": "tuning"},
    {"name": "Step-1b gpt-5-mini", "executor": "gpt-5-mini (effort high)",
     "prompt": "Step-1b winner m7e194es0ism, sha12 0d0def4c6fe3 (no occurrence citations)",
     "tuning": _runs("assets_tuning18_m7e194es0ism", 3), "heldout": _runs("assets_heldout26_m7e194es0ism", 3),
     "cites_occurrences": False, "kind": "runs", "list": None, "source": None,
     "prompt_sha12": "0d0def4c6fe3", "prompt_file": None, "in_sample": "tuning"},
]

# The run folders whose occurrence citations were counted when this module was written (2026-10-02): the selftest
# asserts 100% citing (or 0% for Step-1b) on these only. A run outside this set, such as a future gpt-5.4 held-out run,
# gets its citing share reported, not asserted.
CITES_CHECKED = frozenset(_runs("assets_tuning18_m7e194es0opt1_g54", 3) + _runs("assets_opt_v1", 3)
                          + ["runs/assets_opt_heldout_v1_r0"] + _runs("assets_opt_v0", 2) + ["runs/assets_opt_heldout_v0_r0"]
                          + _runs("assets_tuning18_m7e194es0ism", 3) + _runs("assets_heldout26_m7e194es0ism", 3))


def _cfg(config) -> dict:
    if isinstance(config, dict):
        return config
    for c in CONFIGS:
        if c["name"] == config:
            return c
    raise KeyError(f"no configuration named {config!r}; names: {[c['name'] for c in CONFIGS]}")


# ------------------------------------------------------------------------------------------------- runs ---
def _has_module(d: str, m: str) -> bool:
    """Both outputs of module m exist in run folder d: the flat <m>.json (scored) and _nested/<m>.json (cited)."""
    return (ROOT / d / f"{m}.json").exists() and (ROOT / d / "_nested" / f"{m}.json").exists()


def complete_runs(config, split: str, mods: dict) -> list[str]:
    """The config's run folders for this split that hold BOTH the flat <module>.json and _nested/<module>.json for every
    module of the split."""
    cfg = _cfg(config)
    return [d for d in cfg[split] if all(_has_module(d, m) for m in mods[split])]


def run_status(config, split: str, mods: dict) -> str:
    """'list'; 'k of n complete' (with the modules present in each incomplete folder when k < n); or why the split is
    pending (folders found, modules present)."""
    cfg = _cfg(config)
    if cfg["kind"] == "list":
        return "list"
    done = complete_runs(cfg, split, mods)
    seen = [d for d in cfg[split] if (ROOT / d).exists()]
    have = lambda d: f"{Path(d).name[-2:]} {sum(_has_module(d, m) for m in mods[split])}/{len(mods[split])} modules"
    if done:
        rest = [(have(d) if d in seen else f"{Path(d).name[-2:]} folder missing") for d in cfg[split] if d not in done]
        return f"{len(done)} of {len(cfg[split])} complete" + (f" ({', '.join(rest)})" if rest else "")
    if not seen:
        return f"pending: 0 of {len(cfg[split])} run folders exist"
    return f"pending: no complete run ({', '.join(have(d) for d in seen)})"


def config_status(config, mods: dict) -> str:
    """'complete' when every run folder of both splits is complete (a list is always complete); otherwise, for each split
    that is short, 'split: k of n complete (...)' or 'split: pending: ...'."""
    cfg = _cfg(config)
    if cfg["kind"] == "list":
        return "complete"
    short = [f"{s}: {run_status(cfg, s, mods)}" for s in SPLITS if len(complete_runs(cfg, s, mods)) < len(cfg[s])]
    return "; ".join(short) or "complete"


def _list_run(ns, cfg: dict, names) -> dict:
    """A LAsset list in run shape, every module of `names` present (an absent module counts as an empty list)."""
    if cfg["list"] == "rtl_only":
        import lasset_layer as LL
        items = LL.load_list("rtl_only")
        return LL.as_run({m: items.get(m, []) for m in names})
    lst = ns.ea.load_refs()[cfg["list"]]
    return {m: lst.get(m, []) for m in names}


def _score(ns, mods: dict, run, split: str) -> dict:
    """ea.score on one split; stops if a module of the split was not scored (its misses would be silently dropped)."""
    only = set(mods[split])
    s = ns.ea.score(run, mods["gt"], strict=True, only=only)
    missing = sorted(only - set(s["per_module"]))
    if missing:
        raise RuntimeError(f"{run}: modules not scored (no flat output file): {missing}")
    return s


def _scores(ns, mods: dict, config, split: str) -> list[dict]:
    cfg = _cfg(config)
    if cfg["kind"] == "list":
        return [_score(ns, mods, _list_run(ns, cfg, mods[split]), split)]
    return [_score(ns, mods, ROOT / d, split) for d in complete_runs(cfg, split, mods)]


def _counts(ss: list[dict], names) -> dict | None:
    """{module: (mean TP, mean FP, mean FN)} over the scored runs `ss`; None if there are none."""
    if not ss:
        return None
    out = {}
    for m in names:
        per = [s["per_module"][m] for s in ss]
        out[m] = (float(np.mean([p["tp"] for p in per])), float(np.mean([len(p["fp"]) for p in per])),
                  float(np.mean([len(p["fn"]) for p in per])))
    return out


def _means(ss: list[dict]) -> dict:
    P = [s["precision"] for s in ss]
    R = [s["recall"] for s in ss]
    return {"runs": len(ss), "P_runs": P, "R_runs": R,
            "P_mean": float(np.mean(P)) if P else math.nan, "R_mean": float(np.mean(R)) if R else math.nan}


def module_counts(ns, mods: dict, config, split: str) -> dict | None:
    """{module: (mean TP, mean FP, mean FN)} over the split's complete runs (a list counts as one run); None if none."""
    return _counts(_scores(ns, mods, config, split), mods[split])


def run_means(ns, mods: dict, config, split: str) -> dict:
    """Per-run P and R and their plain means (the convention of map_pipeline/convergence.csv), for comparison only."""
    return _means(_scores(ns, mods, config, split))


def _prf(tp: float, fp: float, fn: float) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


# ------------------------------------------------------------------------------------------------ tables ---
def score_table(ns, mods: dict) -> pd.DataFrame:
    """One row per configuration: runs per split, and pooled P, R, F1 (plus mean TP, FP, FN) on tuning (15 modules,
    111 entries), held-out (26, 189) and all 41 (300). A split with no complete run is empty; then all 41 is empty.

    Pooling rule: for each module, TP, FP and FN are averaged over the split's complete runs; P = TP / (TP + FP) and
    R = TP / (TP + FN) are then computed from the sums of those means (all 41: the two splits' sums added). This can
    differ in the third decimal from the mean of the per-run precisions that map_pipeline/convergence.csv reports: gpt-5.4
    tuning is 0.406 pooled and 0.407 as the mean of its 3 per-run P. Both are exposed: P_runmean_<split> and
    R_runmean_<split> hold the plain per-run means, filled only where the split has more than one complete run.

    in_sample: the split on which the configuration's prompt was chosen ("tuning" for our four configurations, "not tuned by us"
    for LAsset's published lists). Tuning figures of our configurations are in-sample, held-out figures out-of-sample,
    all 41 mixes both; attrs["in_sample"] holds the full note, attrs["pooling"] the pooling rule.

    status: 'complete' when every run folder of both splits is complete; otherwise 'k of n complete' or 'pending: ...'
    for each split that is short (config_status)."""
    rows = []
    for cfg in CONFIGS:
        row = {"config": cfg["name"], "executor": cfg["executor"], "cites_occurrences": cfg["cites_occurrences"],
               "in_sample": cfg["in_sample"]}
        tot = {}
        for split in SPLITS:
            ss = _scores(ns, mods, cfg, split)
            c = _counts(ss, mods[split])
            row[f"runs_{split}"] = len(ss)
            rm = _means(ss) if len(ss) > 1 else {"P_mean": math.nan, "R_mean": math.nan}
            row[f"P_runmean_{split}"], row[f"R_runmean_{split}"] = rm["P_mean"], rm["R_mean"]
            if c is None:
                for k in ("P", "R", "F1", "TP", "FP", "FN"):
                    row[f"{k}_{split}"] = math.nan
                continue
            t = tuple(sum(v[i] for v in c.values()) for i in range(3))
            tot[split] = t
            p, r, f = _prf(*t)
            row.update({f"P_{split}": p, f"R_{split}": r, f"F1_{split}": f,
                        f"TP_{split}": t[0], f"FP_{split}": t[1], f"FN_{split}": t[2]})
        if len(tot) == 2:
            t = tuple(tot["tuning"][i] + tot["heldout"][i] for i in range(3))
            p, r, f = _prf(*t)
            row.update({"P_all41": p, "R_all41": r, "F1_all41": f, "TP_all41": t[0], "FP_all41": t[1], "FN_all41": t[2]})
        else:
            row.update({k: math.nan for k in ("P_all41", "R_all41", "F1_all41", "TP_all41", "FP_all41", "FN_all41")})
        row["status"] = config_status(cfg, mods)
        rows.append(row)
    cols = (["config", "executor", "cites_occurrences", "in_sample", "runs_tuning", "runs_heldout"]
            + [f"{k}_{s}" for s in ("tuning", "heldout", "all41") for k in ("P", "R", "F1")]
            + [f"{k}_{s}" for s in ("tuning", "heldout", "all41") for k in ("TP", "FP", "FN")]
            + [f"{k}_runmean_{s}" for s in SPLITS for k in ("P", "R")] + ["status"])
    df = pd.DataFrame(rows)[cols]
    df.attrs["denominators"] = {"tuning": (len(mods["tuning"]), mods["entries"]["tuning"]),
                                "heldout": (len(mods["heldout"]), mods["entries"]["heldout"]),
                                "all41": (len(mods["tuning"]) + len(mods["heldout"]), sum(mods["entries"].values()))}
    df.attrs["in_sample"] = dict(IN_SAMPLE_NOTE)
    df.attrs["pooling"] = POOLING_NOTE
    return df


def per_module(ns, mods: dict, config_name: str) -> pd.DataFrame:
    """The 41 modules: split, reference entries, the config's mean TP and FP, and LAsset's RTL-only and spec+RTL TP and
    FP. The config's cells are empty for a split with no complete run."""
    cfg = _cfg(config_name)
    rows = []
    for split in SPLITS:
        mine = module_counts(ns, mods, cfg, split)
        la_rtl = module_counts(ns, mods, "LAsset RTL-only", split)
        la_spec = module_counts(ns, mods, "LAsset spec+RTL", split)
        runs = 1 if cfg["kind"] == "list" else len(complete_runs(cfg, split, mods))
        for m in mods[split]:
            rows.append({"module": m, "split": split, "entries": len(mods["gt"][m]), "runs": runs,
                         "TP": mine[m][0] if mine else math.nan, "FP": mine[m][1] if mine else math.nan,
                         "LAsset_RTL_TP": la_rtl[m][0], "LAsset_RTL_FP": la_rtl[m][1],
                         "LAsset_specRTL_TP": la_spec[m][0], "LAsset_specRTL_FP": la_spec[m][1]})
    df = pd.DataFrame(rows)
    df.attrs["config"] = cfg["name"]
    return df


def bootstrap_vs(ns, mods: dict, config_name: str, against: str, draws: int = 2000, seed: int = 0) -> dict:
    """Config minus `against`: difference in pooled P and in pooled R, with a module-bootstrap 95% interval (resample
    modules with replacement, the same draw for both, recompute P and R from the per-module mean counts). Scopes: all 41
    (plain resampling over the 41 modules), tuning and held-out. A scope with a pending split is reported as pending.
    Only module-to-module variation is in the interval; run-to-run variation of the executor is not."""
    out = {}
    for scope, splits in (("all41", SPLITS), ("tuning", ("tuning",)), ("heldout", ("heldout",))):
        A, B, names = [], [], []
        pending = []
        for s in splits:
            a, b = module_counts(ns, mods, config_name, s), module_counts(ns, mods, against, s)
            if a is None or b is None:
                pending.append(s)
                continue
            for m in mods[s]:
                A.append(a[m]); B.append(b[m]); names.append(m)
        if pending:
            out[scope] = {"status": "pending: no complete run on " + ", ".join(pending)}
            continue
        A, B = np.array(A), np.array(B)
        pa, ra, _ = _prf(*A.sum(0))
        pb, rb, _ = _prf(*B.sum(0))
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, len(names), size=(draws, len(names)))
        SA, SB = A[idx].sum(1), B[idx].sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            dP = SA[:, 0] / (SA[:, 0] + SA[:, 1]) - SB[:, 0] / (SB[:, 0] + SB[:, 1])
            dR = SA[:, 0] / (SA[:, 0] + SA[:, 2]) - SB[:, 0] / (SB[:, 0] + SB[:, 2])
        qP, qR = np.nanquantile(dP, [0.025, 0.975]), np.nanquantile(dR, [0.025, 0.975])
        out[scope] = {"status": "complete", "modules": len(names), "entries": int(round(float(A[:, 0].sum() + A[:, 2].sum()))),
                      "P": pa, "P_against": pb, "dP": pa - pb, "dP_lo": float(qP[0]), "dP_hi": float(qP[1]),
                      "R": ra, "R_against": rb, "dR": ra - rb, "dR_lo": float(qR[0]), "dR_hi": float(qR[1]),
                      "draws": draws, "seed": seed, "undefined_draws": int(np.isnan(dP).sum())}
    return {"config": _cfg(config_name)["name"], "against": _cfg(against)["name"], **out}


# ---------------------------------------------------------------------------------------------- manifest ---
def manifest(mods: dict) -> pd.DataFrame:
    """The 41 modules: module, split, RTL path, reference entries, sha12 of the RTL file bytes, line count, and the
    entities the file declares (a multi-entity file such as neorv32_bus has no entity named after the module)."""
    rows = []
    for split in SPLITS:
        for m in sorted(mods[split]):
            rel = f"{RTL_DIR[split]}/{m}.vhd"
            b = (ROOT / rel).read_bytes()
            rows.append({"module": m, "split": split, "rtl_path": rel, "entries": len(mods["gt"][m]),
                         "sha12": hashlib.sha256(b).hexdigest()[:12], "lines": b.count(b"\n"),
                         "entities": ";".join(x.decode() for x in ENTITY.findall(b))})
    extra = sorted(set(mods["gt"]) - set(mods["tuning"]) - set(mods["heldout"]))
    if extra:
        raise RuntimeError(f"reference modules with no RTL file: {extra}")
    return pd.DataFrame(rows)


def manifest_checks(M: pd.DataFrame) -> list[tuple[str, bool, object]]:
    """The manifest's own checks: 41 rows and 300 entries, hand-read RTL lines, hashes from sha256sum (an independent
    tool), line counts from wc -l, entity lines read by hand. `M` is manifest(mods) indexed by module.
    Returns (name, ok, detail) per check."""
    checks = []
    add = lambda name, ok, detail="": checks.append((name, bool(ok), detail))
    add("manifest 41 rows, 300 entries (15 / 111 tuning, 26 / 189 held-out)",
        (len(M), int(M["entries"].sum()), int((M["split"] == "tuning").sum()), int(M.loc[M["split"] == "tuning", "entries"].sum()),
         int((M["split"] == "heldout").sum()), int(M.loc[M["split"] == "heldout", "entries"].sum())) == (41, 300, 15, 111, 26, 189))
    add("manifest: every module has at least 1 entry", int(M["entries"].min()) >= 1)
    read = lambda rel, n: (ROOT / rel).read_bytes().split(b"\n")[n - 1].decode()
    add("hand: data/RTL_data/neorv32_wdt.vhd line 18 'entity neorv32_wdt is'", read(M.loc["neorv32_wdt", "rtl_path"], 18) == "entity neorv32_wdt is")
    add("hand: wdt line 144 assigns cnt_timeout", read(M.loc["neorv32_wdt", "rtl_path"], 144)
        == "  cnt_timeout <= '1' when (cnt_started = '1') and (cnt = ctrl.timeout) else '0';")
    add("hand: data/RTL_heldout/neorv32_gpio.vhd line 17 'entity neorv32_gpio is'", read(M.loc["neorv32_gpio", "rtl_path"], 17) == "entity neorv32_gpio is")
    add("sha12 = sha256sum (wdt b63f4c72f6e1, gpio 50b3e3983803)",
        (M.loc["neorv32_wdt", "sha12"], M.loc["neorv32_gpio", "sha12"]) == ("b63f4c72f6e1", "50b3e3983803"))
    add("hand: line counts wdt 182, gpio 147, bus 967, sys 150 (wc -l)",
        tuple(int(M.loc[m, "lines"]) for m in ("neorv32_wdt", "neorv32_gpio", "neorv32_bus", "neorv32_sys")) == (182, 147, 967, 150))
    at = lambda m: [(ROOT / M.loc[m, "rtl_path"]).read_bytes()[:x.start()].count(b"\n") + 1
                    for x in ENTITY.finditer((ROOT / M.loc[m, "rtl_path"]).read_bytes())]
    add("hand: entity lines bus 17, 191, 284, 457, 716, 878; sys 17, 101; wdt 18; gpio 17",
        M.loc["neorv32_bus", "entities"] == "neorv32_bus_switch;neorv32_bus_reg;neorv32_bus_gateway;neorv32_bus_io_switch;neorv32_bus_amo_rmw;neorv32_bus_amo_rvs"
        and M.loc["neorv32_sys", "entities"] == "neorv32_sys_reset;neorv32_sys_clock"
        and [at(m) for m in ("neorv32_bus", "neorv32_sys", "neorv32_wdt", "neorv32_gpio")]
        == [[17, 191, 284, 457, 716, 878], [17, 101], [18], [17]])
    own = [m for m in M.index if m not in M.loc[m, "entities"].split(";")]
    add("every other module declares an entity of its own name", own == ["neorv32_bus", "neorv32_sys"], own)
    return checks


def write_manifest(path: str = MANIFEST, mods: dict | None = None) -> Path:
    """Write the manifest as CSV (LF line ends), after its own hand-read checks (manifest_checks) pass; if any fails,
    nothing is written and RuntimeError names the failures. Sets up the pipeline itself when `mods` is not given."""
    if mods is None:
        sys.path.insert(0, str(ROOT / "map_pipeline"))
        import final_pipeline as FPL
        mods = FPL.modules(FPL.setup().ea)
    M = manifest(mods)
    failed = [name for name, ok, _ in manifest_checks(M.set_index("module")) if not ok]
    if failed:
        raise RuntimeError(f"manifest checks failed, {path} not written: {failed}")
    p = ROOT / path
    p.write_text(M.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline="")
    return p


# -------------------------------------------------------------------------------------------- self-test ---
def _flatten_nested(path: Path) -> list[str]:
    """Element names of a _nested output, first appearance wins (as meta_tools.flatten). Written independently here."""
    o = json.loads(path.read_text(encoding="utf-8"))
    seen = []
    for c in o.get("conceptual assets", []) or []:
        for s in (c.get("related structural assets", []) or []) if isinstance(c, dict) else []:
            if isinstance(s, dict) and s.get("asset rtl") and (s.get("entity", ""), s["asset rtl"]) not in seen:
                seen.append((s.get("entity", ""), s["asset rtl"]))
    return [n for _, n in seen]


def cites_share(config, split: str, mods: dict, dirs: list[str] | None = None) -> tuple[int, int]:
    """(structural assets listed, those carrying an occurrence ID) over `dirs` (default: the split's complete runs)."""
    n = c = 0
    for d in complete_runs(config, split, mods) if dirs is None else dirs:
        for m in mods[split]:
            o = json.loads((ROOT / d / "_nested" / f"{m}.json").read_text(encoding="utf-8"))
            for ca in o.get("conceptual assets", []) or []:
                for s in (ca.get("related structural assets", []) or []) if isinstance(ca, dict) else []:
                    if isinstance(s, dict) and s.get("asset rtl"):
                        n += 1
                        c += s.get("occurrence") not in (None, "")
    return n, c


def cites_checks(config, mods: dict) -> tuple[list[tuple[str, bool, str]], list[str]]:
    """Occurrence citations as declared. On the complete runs in CITES_CHECKED: a check that every structural asset cites
    an occurrence (cites_occurrences True) or none does (False). On any other complete run (one that did not exist when
    the module was written): an info line with the citing share, not a check. Returns (checks, info lines)."""
    cfg = _cfg(config)
    checks, info = [], []
    if cfg["kind"] != "runs":
        return checks, info
    for s in SPLITS:
        done = complete_runs(cfg, s, mods)
        old = [d for d in done if d in CITES_CHECKED]
        new = [d for d in done if d not in CITES_CHECKED]
        if old:
            n, c = cites_share(cfg, s, mods, old)
            ok = (c == n) if cfg["cites_occurrences"] else (c == 0)
            checks.append((f"cites_occurrences={cfg['cites_occurrences']}: {cfg['name']} {s} ({len(old)} checked runs)",
                           ok and n > 0, f"{c}/{n} structural assets cite an occurrence"))
        if new:
            n, c = cites_share(cfg, s, mods, new)
            share = f"{100 * c / n:.1f}%" if n else "no structural assets"
            info.append(f"{cfg['name']} {s}: {len(new)} run(s) outside CITES_CHECKED, {c}/{n} structural assets cite an "
                        f"occurrence ({share}); reported, not asserted")
    return checks, info


def _plant_run(base: Path, names, skip_flat=(), skip_nested=(), uncited=()) -> str:
    """A throwaway run folder under `base`: flat and _nested files for `names`, minus the skipped ones; each _nested file
    lists two structural assets, both citing an occurrence unless the module is in `uncited` (then one does not)."""
    (base / "_nested").mkdir(parents=True)
    for m in names:
        if m not in skip_flat:
            (base / f"{m}.json").write_text("{}", encoding="utf-8")
        if m not in skip_nested:
            sa = [{"entity": m, "asset rtl": "a", "occurrence": "O1"},
                  {"entity": m, "asset rtl": "b", **({} if m in uncited else {"occurrence": "O2"})}]
            (base / "_nested" / f"{m}.json").write_text(json.dumps({"conceptual assets": [{"related structural assets": sa}]}),
                                                        encoding="utf-8")
    return str(base)


def selftest(ns, mods: dict, log=print) -> bool:
    """Known figures at 3 decimals, one module counted by hand, the manifest against hand-read RTL lines, and the
    internal consistency of the tables. Prints one line per check; True only if all pass. Info lines (the citing share
    of runs outside CITES_CHECKED) are printed but are not checks."""
    import tempfile
    f3 = lambda x: f"{x:.3f}"
    checks, info = [], []
    add = lambda name, ok, detail="": checks.append((name, bool(ok), detail))

    names = [c["name"] for c in CONFIGS]
    add("CONFIGS order", names == ["LAsset RTL-only", "LAsset spec+RTL", "LAsset refined", "final prompt, gpt-5.4",
                                   "final prompt, Claude", "ist2 prompt, Claude", "Step-1b gpt-5-mini"], names)
    add("denominators 15 / 111 and 26 / 189",
        (len(mods["tuning"]), mods["entries"]["tuning"], len(mods["heldout"]), mods["entries"]["heldout"]) == (15, 111, 26, 189))

    T = score_table(ns, mods).set_index("config")
    known = [("LAsset RTL-only", "tuning", "0.680", "0.748"), ("LAsset RTL-only", "heldout", "0.730", "0.757"),
             ("LAsset spec+RTL", "tuning", "0.737", "0.910"), ("LAsset spec+RTL", "heldout", "0.734", "0.862"),
             ("Step-1b gpt-5-mini", "heldout", "0.352", "0.852"), ("final prompt, Claude", "heldout", "0.329", "0.931")]
    for name, s, p, r in known:
        got = (f3(T.loc[name, f"P_{s}"]), f3(T.loc[name, f"R_{s}"]))
        add(f"{name} {s} P/R = {p}/{r}", got == (p, r), f"got {got[0]}/{got[1]}")
    add("final prompt, Claude: held-out has exactly 1 run", T.loc["final prompt, Claude", "runs_heldout"] == 1)

    # in-sample note: our four configurations chose their prompt on tuning; LAsset's lists are used as published
    add("in_sample: LAsset rows 'not tuned by us', our four rows 'tuning'; attrs note for tuning / heldout / all41 / LAsset",
        list(T["in_sample"]) == ["not tuned by us"] * 3 + ["tuning"] * 4 and set(T.attrs["in_sample"]) == {"tuning", "heldout", "all41", "LAsset"},
        list(T["in_sample"]))

    # final gpt-5.4 tuning: the known 0.407/0.820 is the mean of per-run P and R (map_pipeline/convergence.csv P_mean, R_mean)
    g = run_means(ns, mods, "final prompt, gpt-5.4", "tuning")
    add("final gpt-5.4 tuning, mean of 3 per-run P/R = 0.407/0.820", (g["runs"], f3(g["P_mean"]), f3(g["R_mean"])) == (3, "0.407", "0.820"),
        f"got {g['runs']} runs {f3(g['P_mean'])}/{f3(g['R_mean'])}")
    ss = _scores(ns, mods, "final prompt, gpt-5.4", "tuning")
    tp, fp, fn = (sum(s[k] for s in ss) / 3 for k in ("tp", "fp", "fn"))
    pooled = (f3(tp / (tp + fp)), f3(tp / (tp + fn)))
    add("final gpt-5.4 tuning, table = pooled means of TP/FP/FN", (f3(T.loc["final prompt, gpt-5.4", "P_tuning"]),
        f3(T.loc["final prompt, gpt-5.4", "R_tuning"])) == pooled,
        f"pooled {pooled[0]}/{pooled[1]} from mean TP {tp:.2f}, FP {fp:.2f}, FN {fn:.2f}")
    add("final gpt-5.4 tuning: table P pooled 0.406, P_runmean 0.407 (the documented third-decimal difference)",
        (f3(T.loc["final prompt, gpt-5.4", "P_tuning"]), f3(T.loc["final prompt, gpt-5.4", "P_runmean_tuning"])) == ("0.406", "0.407"))

    # P_runmean / R_runmean = P_mean / R_mean of map_pipeline/convergence.csv (tuning) and map_pipeline/heldout.csv, where runs > 1
    conv = {"tuning": pd.read_csv(ROOT / "map_pipeline/convergence.csv", dtype=str, keep_default_na=False).set_index("version"),
            "heldout": pd.read_csv(ROOT / "map_pipeline/heldout.csv", dtype=str, keep_default_na=False).set_index("version")}
    for name, s, ver in (("final prompt, gpt-5.4", "tuning", "m7e194es0opt1_g54"), ("final prompt, Claude", "tuning", "opt_v1"),
                         ("ist2 prompt, Claude", "tuning", "opt_v0"), ("Step-1b gpt-5-mini", "tuning", "m7e194es0ism"),
                         ("Step-1b gpt-5-mini", "heldout", "m7e194es0ism")):
        row = conv[s].loc[ver]
        got = (str(int(T.loc[name, f"runs_{s}"])), f3(T.loc[name, f"P_runmean_{s}"]), f3(T.loc[name, f"R_runmean_{s}"]))
        add(f"P/R_runmean_{s} = map_pipeline/{'convergence' if s == 'tuning' else 'heldout'}.csv {ver} ({name})",
            got == (row["runs_complete"], row["P_mean"], row["R_mean"]), f"got {got}, csv {row['runs_complete']} {row['P_mean']}/{row['R_mean']}")
    one = [(n, s) for n in T.index for s in SPLITS if T.loc[n, f"runs_{s}"] <= 1]
    add(f"P/R_runmean empty wherever a split has at most 1 run ({len(one)} cells)",
        all(math.isnan(T.loc[n, f"P_runmean_{s}"]) and math.isnan(T.loc[n, f"R_runmean_{s}"]) for n, s in one))

    # pending logic: the gpt-5.4 held-out folders are the ones final_pipeline writes; a tuning run asked for held-out is incomplete
    import final_pipeline as FPL
    add("gpt-5.4 held-out folders = final_pipeline.run_dirs('heldout')",
        [ROOT / d for d in _cfg("final prompt, gpt-5.4")["heldout"]] == FPL.run_dirs("heldout"))
    planted = dict(_cfg("final prompt, Claude"), heldout=["runs/assets_opt_v1_r0"])
    add("planted: a tuning run listed as held-out is not complete", complete_runs(planted, "heldout", mods) == [])
    st = T.loc["final prompt, gpt-5.4"]
    if not complete_runs("final prompt, gpt-5.4", "heldout", mods):
        add("gpt-5.4 held-out pending -> all-41 cells empty", math.isnan(st["P_all41"]) and math.isnan(st["P_heldout"])
            and st["status"].startswith("heldout: pending"), st["status"])
    add("status of fully complete configurations is 'complete' (Claude v1, ist2, Step-1b, the 3 lists)",
        all(T.loc[n, "status"] == "complete" for n in names if n != "final prompt, gpt-5.4"))
    partial = dict(_cfg("final prompt, Claude"), tuning=["runs/assets_opt_v1_r0", "runs/assets_opt_v1_r9"])
    add("planted: 1 of 2 tuning folders complete -> status 'tuning: 1 of 2 complete (r9 folder missing)'",
        config_status(partial, mods) == "tuning: 1 of 2 complete (r9 folder missing)", config_status(partial, mods))

    # planted run folders (system temp, removed afterwards): completeness needs both files; uncited runs are reported
    with tempfile.TemporaryDirectory() as tmp:
        tune = mods["tuning"]
        full = _plant_run(Path(tmp) / "full_r0", tune, uncited=tune[:1])
        no_flat = _plant_run(Path(tmp) / "noflat_r1", tune, skip_flat=tune[-1:])
        no_nest = _plant_run(Path(tmp) / "nonest_r2", tune, skip_nested=tune[-1:])
        pc = dict(_cfg("final prompt, Claude"), tuning=[full, no_flat, no_nest], heldout=[])
        add("planted: complete only with flat AND _nested for every module (1 of 3 planted folders)",
            complete_runs(pc, "tuning", mods) == [full], [Path(d).name for d in complete_runs(pc, "tuning", mods)])
        add("planted: status 'tuning: 1 of 3 complete (r1 14/15 modules, r2 14/15 modules)'",
            config_status(pc, mods) == "tuning: 1 of 3 complete (r1 14/15 modules, r2 14/15 modules)", config_status(pc, mods))
        pck, pinf = cites_checks(pc, mods)
        add("planted: a run outside CITES_CHECKED with an uncited entry is reported (29/30), not asserted",
            pck == [] and len(pinf) == 1 and "29/30 structural assets" in pinf[0], pinf)

    # hand check: neorv32_wdt in runs/assets_tuning18_m7e194es0opt1_g54_r0 (read the _nested file and the reference)
    run0 = "runs/assets_tuning18_m7e194es0opt1_g54_r0"
    listed = ["ctrl.enable", "clkgen_en_o", "ctrl.lock", "ctrl.strict", "ctrl.timeout", "cnt_started", "cnt", "reset_wdt",
              "reset_force", "hw_rst_timeout", "rstn_o", "hw_rst_access", "reset_cause"]      # rstn_o is cited twice
    ref = ["ctrl.enable", "ctrl.lock", "ctrl.timeout", "cnt", "cnt_timeout", "reset_cause", "reset_wdt", "clkgen_en_o"]
    hand_fp = sorted(["ctrl.strict", "cnt_started", "reset_force", "hw_rst_timeout", "rstn_o", "hw_rst_access"])
    add("hand: wdt _nested lists 13 distinct elements", _flatten_nested(ROOT / run0 / "_nested" / "neorv32_wdt.json") == listed)
    add("hand: wdt reference has 8 entries", [e for e, _ in mods["gt"]["neorv32_wdt"]] == ref)
    pm = _score(ns, mods, ROOT / run0, "tuning")["per_module"]["neorv32_wdt"]
    add("hand: wdt r0 TP 7, FP 6 (names), FN 1 (cnt_timeout)",
        (pm["tp"], pm["fp"], pm["fn"]) == (7, hand_fp, ["cnt_timeout"]), f"got {pm['tp']} / {pm['fp']} / {pm['fn']}")
    # LAsset RTL-only on wdt: the 9 listed items are on lines 4853..4960 of the published list; 3 FP read there by hand
    la = _scores(ns, mods, "LAsset RTL-only", "tuning")[0]["per_module"]["neorv32_wdt"]
    raw = (ROOT / CONFIGS[0]["source"]).read_bytes().split(b"\n")
    add("hand: wdt LAsset RTL-only TP 6, FP ['ctrl.strict', 'hw_rst_timeout', 'prsc_tick'] (names), FN ['cnt', 'cnt_timeout']",
        (la["tp"], la["fp"], la["fn"]) == (6, ["ctrl.strict", "hw_rst_timeout", "prsc_tick"], ["cnt", "cnt_timeout"]),
        f"got {la['tp']} / {la['fp']} / {la['fn']}")
    add("hand: those 3 FP on lines 4879, 4906, 4947 of the LAsset RTL-only list (wdt block from line 4849)",
        raw[4848].strip() == b'"IP": "neorv32_wdt",'
        and [raw[n - 1].strip() for n in (4879, 4906, 4947)]
        == [b'"Asset RTL": "ctrl.strict",', b'"Asset RTL": "hw_rst_timeout",', b'"Asset RTL": "prsc_tick",'])
    pmod = per_module(ns, mods, "final prompt, gpt-5.4").set_index("module")
    add("per_module: wdt LAsset RTL-only TP 6, FP 3 (the same counts)",
        (pmod.loc["neorv32_wdt", "LAsset_RTL_TP"], pmod.loc["neorv32_wdt", "LAsset_RTL_FP"]) == (6, 3))

    # per-module rows add up to the table
    for name in ("final prompt, Claude", "Step-1b gpt-5-mini"):
        pmn = per_module(ns, mods, name)
        add(f"per_module sums = table all-41 TP/FP ({name})",
            abs(pmn["TP"].sum() - T.loc[name, "TP_all41"]) < 1e-9 and abs(pmn["FP"].sum() - T.loc[name, "FP_all41"]) < 1e-9)
    add("per_module LAsset sums = table all-41 TP/FP", pmod["LAsset_RTL_TP"].sum() == T.loc["LAsset RTL-only", "TP_all41"]
        and pmod["LAsset_specRTL_FP"].sum() == T.loc["LAsset spec+RTL", "FP_all41"])

    # bootstrap: deterministic, zero against itself, point estimate = table difference
    b1 = bootstrap_vs(ns, mods, "final prompt, Claude", "LAsset RTL-only", draws=300, seed=0)
    b2 = bootstrap_vs(ns, mods, "final prompt, Claude", "LAsset RTL-only", draws=300, seed=0)
    b0 = bootstrap_vs(ns, mods, "Step-1b gpt-5-mini", "Step-1b gpt-5-mini", draws=300, seed=0)
    add("bootstrap deterministic (same seed, same result)", b1 == b2)
    add("bootstrap of a config against itself = 0 [0, 0]", all(b0[s]["dP"] == 0 and b0[s]["dP_lo"] == 0 and b0[s]["dR_hi"] == 0
                                                               for s in ("all41", "tuning", "heldout")))
    add("bootstrap point dP = table difference (all 41)",
        abs(b1["all41"]["dP"] - (T.loc["final prompt, Claude", "P_all41"] - T.loc["LAsset RTL-only", "P_all41"])) < 1e-12)

    # occurrence citations (asserted on CITES_CHECKED, reported elsewhere) and prompt hashes as declared
    in_cfg = {d for c in CONFIGS for s in SPLITS for d in c[s]}
    add(f"CITES_CHECKED: all {len(CITES_CHECKED)} folders belong to a configuration and are complete runs",
        CITES_CHECKED <= in_cfg and all(d in complete_runs(c, s, mods) for c in CONFIGS for s in SPLITS for d in c[s] if d in CITES_CHECKED))
    for cfg in CONFIGS:
        if cfg["kind"] != "runs":
            continue
        ck, inf = cites_checks(cfg, mods)
        checks.extend(ck)
        info.extend(inf)
        if cfg["prompt_file"]:
            add(f"prompt sha12 {cfg['prompt_sha12']} ({cfg['name']})", ns.mt.sha12((ROOT / cfg["prompt_file"]).read_text(encoding="utf-8")) == cfg["prompt_sha12"])
        metas = [ROOT / d / "_run_meta.json" for s in SPLITS for d in complete_runs(cfg, s, mods) if (ROOT / d / "_run_meta.json").exists()]
        if metas:
            add(f"run meta system_sha12 = {cfg['prompt_sha12']} ({cfg['name']}, {len(metas)} runs)",
                all(json.loads(p.read_text(encoding="utf-8")).get("system_sha12") == cfg["prompt_sha12"] for p in metas))

    # manifest: the same checks write_manifest runs before writing
    checks.extend(manifest_checks(manifest(mods).set_index("module")))

    for name, ok, detail in checks:
        log(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and (not ok or isinstance(detail, str)) else ""))
    for line in info:
        log(f"  [info] {line}")
    passed = sum(ok for _, ok, _ in checks)
    log(f"selftest: {passed}/{len(checks)} checks pass" + (f"; {len(info)} info line(s), not checks" if info else ""))
    return passed == len(checks)


# ------------------------------------------------------------------------------------------------- main ---
def _fmt_boot(b: dict) -> list[str]:
    out = [f"{b['config']} minus {b['against']}"]
    for s in ("all41", "tuning", "heldout"):
        x = b[s]
        if x["status"] != "complete":
            out.append(f"  {s:8s} {x['status']}")
            continue
        out.append(f"  {s:8s} {x['modules']} modules, {x['entries']} entries: precision {x['P']:.3f} vs {x['P_against']:.3f}, "
                   f"dP {x['dP']:+.3f} [{x['dP_lo']:+.3f}, {x['dP_hi']:+.3f}]; recall {x['R']:.3f} vs {x['R_against']:.3f}, "
                   f"dR {x['dR']:+.3f} [{x['dR_lo']:+.3f}, {x['dR_hi']:+.3f}]")
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    sys.path.insert(0, str(ROOT / "map_pipeline"))
    import final_pipeline as FPL
    ns = FPL.setup()
    mods = FPL.modules(ns.ea)
    if "--write-manifest" in argv:
        print("wrote", write_manifest(mods=mods).relative_to(ROOT))
        return 0
    print("selftest")
    if not selftest(ns, mods):
        print("selftest FAILED: nothing below is reported")
        return 1
    T = score_table(ns, mods)
    d = T.attrs["denominators"]
    print(f"\nStrict scoring. P = precision, R = recall. Denominators: tuning {d['tuning'][0]} modules / {d['tuning'][1]} entries, "
          f"held-out {d['heldout'][0]} / {d['heldout'][1]}, all {d['all41'][0]} / {d['all41'][1]}. Several runs: mean TP, FP, FN, then P and R.")
    print("In-sample: for our configurations (in_sample = tuning) the tuning figures are in-sample, because the prompts were "
          "chosen on these 15 modules;\nheld-out is out-of-sample; all 41 mixes both. LAsset's lists (not tuned by us) were "
          "not tuned on this reference by us.")
    show = T[["config", "in_sample", "runs_tuning", "runs_heldout"] + [f"{k}_{s}" for s in ("tuning", "heldout", "all41") for k in ("P", "R", "F1")] + ["status"]]
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 70):
        print(show.round(3).to_string(index=False, na_rep="-"))
        print("\nmean TP / FP / FN")
        print(T[["config"] + [f"{k}_{s}" for s in ("tuning", "heldout", "all41") for k in ("TP", "FP", "FN")]].round(1).to_string(index=False, na_rep="-"))
        print("\npooled P / R (table above) next to the mean of the per-run P / R (map_pipeline/convergence.csv convention); "
              "the run means are shown only where a split has more than 1 run")
        print(T[["config", "runs_tuning", "P_tuning", "P_runmean_tuning", "R_tuning", "R_runmean_tuning",
                 "runs_heldout", "P_heldout", "P_runmean_heldout", "R_heldout", "R_runmean_heldout"]]
              .round(3).to_string(index=False, na_rep="-"))
    print("\nmodule bootstrap, 95% interval, 2000 draws, seed 0")
    for a in ("final prompt, gpt-5.4", "final prompt, Claude", "Step-1b gpt-5-mini"):
        for b in ("LAsset RTL-only", "LAsset spec+RTL"):
            print("\n".join(_fmt_boot(bootstrap_vs(ns, mods, a, b))))
    P = per_module(ns, mods, "final prompt, Claude")
    print(f"\nper module, {P.attrs['config']} (mean over complete runs)")
    with pd.option_context("display.width", 200):
        print(P.round(2).to_string(index=False))
    M = manifest(mods)
    csv = ROOT / MANIFEST
    same = csv.exists() and csv.read_text(encoding="utf-8") == M.to_csv(index=False, lineterminator="\n")
    print(f"\nmanifest: {len(M)} modules, {int(M['entries'].sum())} entries; {MANIFEST} "
          + ("matches" if same else "is missing or differs: run with --write-manifest"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
