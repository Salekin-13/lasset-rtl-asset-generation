"""Why the final prompt's false positives do not go down, traced through occurrence IDs and the relationship map, on
all 41 modules (15 tuning + 26 held-out). No model call.

Each listed asset is followed from the run's output to its cited occurrence ID, the RTL line behind that ID, the
cited relationship record (edge), the citation check (trace_check) and the element's relationship profile (the same
tokens as assetgen_meta/fault_reporter.profile, for example "kind: signal", "storage: stored", "controlled <- input
port"). TP = listed and in the reference; FP = listed and not in it (strict scoring, eval_assets.score).

Readings
  citations       FP citations against hit citations: are FPs misreadings of the RTL?
  cited_types     which record type the model cited, for hits and for FPs
  overlap         profile tokens carried by hits and FPs, split into relationship classes (from the element's
                  relationship records and port-map connections) and element attributes (kind, storage, record
                  field, constant driver); FPs whose whole profile also belongs to a hit
  separability    how well the profile tells a hit from an FP (AUC), in-sample, leave one module out, tuning -> held-out
  transfer        code rules found on tuning (fault_reporter), applied unchanged to held-out; random-removal control;
                  LAsset RTL-only on held-out for scale
  minimal_pairs   a hit and an FP with the same profile and the same cited record type, side by side
  unreferenced_concepts  FPs listed only under concepts that list no reference element. A concept is one run's concept
                  in one module; it is referenced when any hit is listed under it, in any position. Two counts: FPs
                  whose first concept is unreferenced, and FPs none of whose concepts is referenced (the stricter
                  one, used in the summary). fp_diagnosis D5 (first concept only, for hits too) is kept for comparison.

"Pooled" readings cover every complete run present: "all 41 modules" when both splits have a complete run, else
"pooled (N modules, tuning only)". The label is computed from the ledger (pooled_label).

Runs: the final prompt (prompt_opt/v1). The Claude-agent runs cover all 41 modules. The gpt-5.4 held-out runs are
included automatically once they exist and are complete; until then gpt-5.4 is tuning only and reported as pending.

    python map_pipeline/fp_trace41.py              (self-test, then everything; writes map_pipeline/fp_trace41/)
    python map_pipeline/fp_trace41.py --selftest
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "map_pipeline" / "fp_trace41"
CONFIGS = {
    "final prompt, Claude": {"slug": "claude",
                             "tuning": [f"runs/assets_opt_v1_r{k}" for k in range(3)],
                             "heldout": ["runs/assets_opt_heldout_v1_r0"]},
    "final prompt, gpt-5.4": {"slug": "gpt54",
                              "tuning": [f"runs/assets_tuning18_m7e194es0opt1_g54_r{k}" for k in range(3)],
                              "heldout": [f"runs/assets_heldout26_m7e194es0opt1_g54_r{k}" for k in range(3)]},
}
SPLITS = ("tuning", "heldout")
RTL_DIR = {"tuning": ROOT / "data/RTL_data", "heldout": ROOT / "data/RTL_heldout"}
SEED = 0


# ------------------------------------------------------------------------------------------------- runs ---
def run_status(ns, mods: dict, config: str) -> dict:
    """Per split: the complete runs (every module of the split has a readable output) and the pending ones."""
    out = {}
    for split in SPLITS:
        comp, pend = [], []
        for r in CONFIGS[config][split]:
            (comp if ns.fd.complete(ROOT / r, split) else pend).append(r)
        have = {r: f"{sum((ROOT / r / '_nested' / f'{m}.json').exists() for m in mods[split])}/{len(mods[split])} modules on disk"
                for r in pend}
        out[split] = {"complete": comp, "pending": pend, "pending on disk": have}
    return out


def _quiet(*_a, **_k):
    return None


# ----------------------------------------------------------------------------------------------- ledger ---
def concepts_of(obj) -> dict:
    """{(entity, asset rtl): every concept the asset is listed under, in order, each once}, read from one run's
    _nested/<module>.json the way fp_diagnosis.rows_for_run reads it (so the first entry is its 'concept')."""
    out: dict = {}
    for c in (obj or {}).get("conceptual assets", []) or []:
        if not isinstance(c, dict):
            continue
        for s in c.get("related structural assets", []) or []:
            if not isinstance(s, dict) or not s.get("asset rtl"):
                continue
            lst = out.setdefault((s.get("entity", ""), s.get("asset rtl", "")), [])
            if c.get("concept") not in lst:
                lst.append(c.get("concept"))
    return out


def pooled_label(led) -> str:
    """The name of the pooled readings, from the data: "all N modules" only when both splits are present."""
    present = [sp for sp in SPLITS if (led["split"] == sp).any()]
    n = int(led["module"].nunique()) if len(led) else 0
    if len(present) == len(SPLITS):
        return f"all {n} modules"
    return f"pooled ({n} modules, {present[0] if present else 'no split'} only)"


def ledger(ns, mods: dict, config: str = "final prompt, Claude"):
    """One row per listed asset of every complete run of both splits, with its label, citation trail, profile and
    every concept it is listed under (column 'concepts'; 'concept' is the first of them)."""
    import pandas as pd
    st = run_status(ns, mods, config)
    recs = []
    for split in SPLITS:
        cache: dict = {}
        for r in st[split]["complete"]:
            rows, _s = ns.fd.rows_for_run(ROOT / r, split, cache)
            nested: dict = {}
            for x in rows:
                if x["module"] not in nested:
                    nested[x["module"]] = concepts_of(ns.fd._nested(ROOT / r, x["module"]))
                cs = tuple(nested[x["module"]].get((x["entity"], x["element"]), ()))
                assert cs and cs[0] == x["concept"], f"{r}/{x['module']}/{x['element']}: first concept differs from rows_for_run"
                mod = cache[x["module"]]
                e = mod["els"].get((x["entity"], x["element"])) or next(
                    (v for k, v in mod["els"].items() if k[1] == x["element"]), None)
                pc = tuple(sorted(ns.fr.profile(e, mod, "class"))) if e else ()
                pt = tuple(sorted(ns.fr.profile(e, mod, "type"))) if e else ()
                recs.append({"config": config, "split": split, "run": Path(r).name, "module": x["module"],
                             "entity": x["entity"], "element": x["element"], "concept": x["concept"], "concepts": cs,
                             "label": x["label"],
                             "role": x["role"], "occurrence": x["occurrence"], "line": x["line"], "rtl": x["rtl"],
                             "cited_edge": x["edge"] or "", "cited_type": (x["edge"] or "none").split(" ")[0],
                             "citation": x["status"], "family": x["family"], "in_map": bool(x["in_map"]),
                             "profile": pc, "profile_text": "; ".join(pc) if pc else "not in map", "profile_type": pt})
    cols = ["config", "split", "run", "module", "entity", "element", "concept", "concepts", "label", "role", "occurrence",
            "line", "rtl", "cited_edge", "cited_type", "citation", "family", "in_map", "profile", "profile_text",
            "profile_type"]
    return pd.DataFrame(recs, columns=cols)


# ------------------------------------------------------------------------------------------- citations ---
def citations(led):
    """Citation status by split and label, and pooled (pooled_label): counts, and shares of the label's listed assets."""
    import pandas as pd
    pooled = pooled_label(led)
    parts = [led.assign(split_=led["split"]), led.assign(split_=pooled)]
    d = pd.concat(parts, ignore_index=True)
    statuses = sorted(d["citation"].unique(), key=lambda s: (s != "verified", s))
    rows = []
    for (sp, lab), g in d.groupby(["split_", "label"], sort=False):
        c = Counter(g["citation"])
        row = {"split": sp, "label": lab, "listed": len(g)}
        row.update({s: c.get(s, 0) for s in statuses})
        row.update({f"{s} share": round(c.get(s, 0) / len(g), 3) for s in statuses})
        rows.append(row)
    order = {"tuning": 0, "heldout": 1, pooled: 2}
    return pd.DataFrame(rows).sort_values(["split", "label"], key=lambda s: s.map(order) if s.name == "split" else s,
                                          ignore_index=True)


def cited_types(led):
    """The cited record type (or none) by label, pooled over every run and module: counts, share of the label's
    assets, and the FP share among the assets citing that type. Rows are sorted by FP count (then hits), so the
    first row is the record type cited by the most FPs."""
    import pandas as pd
    n = Counter(led["label"])
    rows = []
    for t, g in led.groupby("cited_type"):
        c = Counter(g["label"])
        rows.append({"cited type": t, "hits": c.get("TP", 0), "share of hits": round(c.get("TP", 0) / max(n["TP"], 1), 3),
                     "FPs": c.get("FP", 0), "share of FPs": round(c.get("FP", 0) / max(n["FP"], 1), 3),
                     "FP share among assets citing it": round(c.get("FP", 0) / len(g), 3)})
    return pd.DataFrame(rows).sort_values(["FPs", "hits", "cited type"], ascending=[False, False, True], ignore_index=True)


# --------------------------------------------------------------------------------------------- overlap ---
ATTRIBUTE_TOKENS = ("record field", "constant driver")
ATTRIBUTE_PREFIXES = ("kind:", "storage:")


def token_kind(tok: str) -> str:
    """'element attribute' for the tokens fault_reporter.profile takes from the element itself (fd.features kind,
    storage and field; e['constant_drivers']); 'relationship class' for the tokens it takes from the element's
    relationship records and port-map connections."""
    return "element attribute" if tok.startswith(ATTRIBUTE_PREFIXES) or tok in ATTRIBUTE_TOKENS else "relationship class"


def overlap(ns, mods: dict, led) -> dict:
    """Profile tokens of hits and FPs (pooled over every run and module), split into relationship classes and element
    attributes (token_kind), and exact-profile overlap: FPs whose whole profile is also the profile of some hit (any
    hit; a hit in another module; a hit in the other split)."""
    import pandas as pd
    d = led[led["in_map"]]
    rows = [{"label": r.label, "prof_class": frozenset(r.profile)} for r in d.itertuples()]
    tok = ns.fr.token_table(rows, "prof_class")
    for t in tok:
        t["token kind"] = token_kind(t["token"])
    rel = [t for t in tok if t["token kind"] == "relationship class"]
    att = [t for t in tok if t["token kind"] == "element attribute"]
    hit_prof = {}
    for r in d[d["label"] == "TP"].itertuples():
        hit_prof.setdefault(r.profile, set()).add((r.split, r.module))
    fps = d[d["label"] == "FP"]
    any_hit = sum(1 for r in fps.itertuples() if r.profile in hit_prof)
    other_mod = sum(1 for r in fps.itertuples() if any(m != r.module for _s, m in hit_prof.get(r.profile, ())))
    other_split = sum(1 for r in fps.itertuples() if any(s != r.split for s, _m in hit_prof.get(r.profile, ())))
    per_split = {}
    for sp in SPLITS:
        hp = set(d[(d["label"] == "TP") & (d["split"] == sp)]["profile"])
        f = fps[fps["split"] == sp]
        if len(f):
            k = int(f["profile"].isin(hp).sum())
            per_split[sp] = {"FPs": len(f), "FPs whose exact profile a hit has (same split)": k, "share": round(k / len(f), 3)}
    nf = max(len(fps), 1)
    return {"modules": int(d["module"].nunique()), "listed": len(d), "hits": int((d["label"] == "TP").sum()),
            "FPs": len(fps), "not in map (left out)": int((~led["in_map"]).sum()),
            "profile tokens": len(tok), "profile tokens on both hits and FPs": sum(t["both"] for t in tok),
            "relationship classes": len(rel), "relationship classes on both hits and FPs": sum(t["both"] for t in rel),
            "element attributes": len(att), "element attributes on both hits and FPs": sum(t["both"] for t in att),
            "class table": pd.DataFrame(tok)[["token", "token kind", "hits_with", "hits_share", "fp_with", "fp_share",
                                              "both"]],
            "distinct profiles": int(d["profile"].nunique()),
            "exact profile": {"FPs whose exact profile a hit has": any_hit, "share": round(any_hit / nf, 3),
                              "... of a hit in another module": other_mod, "share (other module)": round(other_mod / nf, 3),
                              "... of a hit in the other split": other_split, "share (other split)": round(other_split / nf, 3),
                              "per split": per_split}}


# ---------------------------------------------------------------------------------------- separability ---
def _features(d, which: str):
    import numpy as np
    def toks(r):
        t = set(r.profile)
        if which == "profile + cited type + role":
            t |= {f"cited: {r.cited_type}", f"role: {r.role}"}
        elif which == "exact record types":
            t = set(r.profile_type)
        return t
    T = [toks(r) for r in d.itertuples()]
    vocab = sorted(set().union(*T)) if T else []
    ix = {t: i for i, t in enumerate(vocab)}
    X = np.zeros((len(T), len(vocab)))
    for i, s in enumerate(T):
        for t in s:
            X[i, ix[t]] = 1.0
    return X


def separability(led, seed: int = SEED) -> dict:
    """Hit-vs-FP AUC from the profile (logistic regression, fixed seed): in-sample; leave one module out over every
    module present; trained on tuning and tested on held-out (when both are present). 0.5 = chance, 1 = perfect."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    d = led[led["in_map"]].reset_index(drop=True)
    y = (d["label"] == "TP").to_numpy()
    g = d["module"].to_numpy()
    sp = d["split"].to_numpy()
    lr = lambda: LogisticRegression(max_iter=2000, random_state=seed)

    def lomo(X, yy, gg):
        p = np.zeros(len(yy))
        for m in sorted(set(gg)):
            te = gg == m
            p[te] = lr().fit(X[~te], yy[~te]).predict_proba(X[te])[:, 1] if len(set(yy[~te])) == 2 else yy[~te].mean()
        return round(float(roc_auc_score(yy, p)), 3)
    out = {"listed": len(d), "hits": int(y.sum()), "FPs": int((~y).sum()), "modules": int(len(set(g))),
           "splits": sorted(set(sp)), "features": {}}
    if len(set(y)) < 2:
        return out
    first = ~d.sort_values(["split", "module", "entity", "element", "run"]).duplicated(["split", "module", "entity", "element"])
    first = first.sort_index().to_numpy()
    for which in ("profile", "profile + cited type + role", "exact record types"):
        X = _features(d, which)
        o = {"in-sample": round(float(roc_auc_score(y, lr().fit(X, y).predict_proba(X)[:, 1])), 3),
             "leave one module out": lomo(X, y, g),
             "leave one module out, one row per element": lomo(X[first], y[first], g[first])}
        tr, te = sp == "tuning", sp == "heldout"
        if tr.any() and te.any() and len(set(y[tr])) == 2 and len(set(y[te])) == 2:
            o["train tuning, test held-out"] = round(float(roc_auc_score(y[te], lr().fit(X[tr], y[tr]).predict_proba(X[te])[:, 1])), 3)
        else:
            o["train tuning, test held-out"] = "pending (no complete held-out run)"
        out["features"][which] = o
    return out


# -------------------------------------------------------------------------------------------- transfer ---
def _point_outputs(ns, out: Path):
    old = (ns.fd.OUT, ns.fr.OUT)
    ns.fd.OUT, ns.fr.OUT = out / "fp_diagnosis", out / "fault_report"
    return old


def _prf(tp, fp, ref):
    return (round(tp / (tp + fp), 3) if tp + fp else 0.0), (round(tp / ref, 3) if ref else 0.0)


def _frac(num: int, den: int) -> Fraction:
    return Fraction(num, den) if den else Fraction(0)


def _ftxt(num: int, den: int) -> str:
    """An exact value as 'numerator/denominator' (not reduced, so the denominator stays the count it is)."""
    return f"{int(num)}/{int(den)}"


def lasset_scores(ns, mods: dict, split: str) -> dict:
    """LAsset's published lists on one split, strict: spec+RTL initial, refined, RTL-only initial.
    Each: P and R (rounded), TP, FP, FN."""
    import lasset_layer as LL
    gt, only = mods["gt"], set(mods[split])
    refs = ns.ea.load_refs()
    out = {}
    for name, run in (("LAsset spec+RTL initial", {m: refs["paper"].get(m, []) for m in mods[split]}),
                      ("LAsset spec+RTL refined", {m: refs["paper_refined"].get(m, []) for m in mods[split]}),
                      ("LAsset RTL-only initial", LL.as_run({m: LL.load_list("rtl_only").get(m, []) for m in mods[split]}))):
        s = ns.ea.score(run, gt, strict=True, only=only)
        out[name] = {"P": round(s["precision"], 3), "R": round(s["recall"], 3), "TP": s["tp"], "FP": s["fp"], "FN": s["fn"]}
    return out


def transfer(ns, mods: dict, config: str = "final prompt, Claude", led=None, draws: int = 2000, seed: int = SEED,
             out: Path = OUT) -> dict:
    """Code rules found by fault_reporter on the tuning runs, applied unchanged to the held-out runs: FPs removed, hits
    lost, P and R before and after. Control: remove the same number of held-out assets uniformly at random (draws,
    seed). Scale: LAsset RTL-only on held-out. Recall counts every reference entry of the held-out runs.
    Every P and R is given rounded and exact ('hits/listed', 'hits/reference entries'). A draw 'reaches the rules P'
    when its exact P is at least the rules' exact P (both have the same denominator, the assets kept)."""
    import numpy as np
    st = run_status(ns, mods, config)
    if not st["tuning"]["complete"] or not st["heldout"]["complete"]:
        return {"status": "pending", "config": config,
                "why": "no complete held-out run" if st["tuning"]["complete"] else "no complete tuning run",
                "pending runs": st["heldout"]["pending"] + st["tuning"]["pending"]}
    led = ledger(ns, mods, config) if led is None else led
    slug = CONFIGS[config]["slug"]
    old = _point_outputs(ns, out)
    try:
        facts = ns.fr.analyse({config: list(st["tuning"]["complete"])}, config,          # repo-relative: reports stay portable
                              f"{slug}_tuning_to_heldout", split="tuning", llm=False, log=_quiet,
                              transfer_runs=list(st["heldout"]["complete"]), transfer_split="heldout")
    finally:
        ns.fd.OUT, ns.fr.OUT = old
    rules = [c["code_best_rule"]["rule"] for c in facts["clusters"] if c["code_best_rule"]]
    h = led[led["split"] == "heldout"].reset_index(drop=True)
    y = (h["label"] == "TP").to_numpy()
    drop = np.array([any(ns.fr._apply_rule(u, set(p)) for u in rules) for p in h["profile"]])
    def refs(split):                         # reference entries summed over the split's complete runs (recall denominator)
        tot = 0
        for r in st[split]["complete"]:
            s = ns.ea.score(ROOT / r, mods["gt"], strict=True, only=set(mods[split]))
            tot += s["tp"] + s["fn"]
        return tot
    ref, ref_t = refs("heldout"), refs("tuning")
    TP, FP, k = int(y.sum()), int((~y).sum()), int(drop.sum())
    lost, removed = int((drop & y).sum()), int((drop & ~y).sum())
    kept_n = len(y) - k                      # assets kept, the P denominator after removal (rules and every draw)
    pb, rb = _prf(TP, FP, ref)
    pa, ra = _prf(TP - lost, FP - removed, ref)
    Pb, Rb, Pa, Ra = _frac(TP, TP + FP), _frac(TP, ref), _frac(TP - lost, kept_n), _frac(TP - lost, ref)
    rng = np.random.default_rng(seed)
    kept_hits = np.empty(draws, dtype=np.int64)                  # hits left after each random removal
    for i in range(draws):
        idx = rng.choice(len(y), size=k, replace=False)
        kept_hits[i] = TP - int(y[idx].sum())
    rp = kept_hits / kept_n if kept_n else np.zeros(draws)
    rr = kept_hits / ref
    reach = int(sum(_frac(int(h), kept_n) >= Pa for h in kept_hits))
    q_lo, q_hi = (int(np.quantile(kept_hits, q, method="inverted_cdf")) for q in (.025, .975))
    tog = facts["code_rules_together"]
    fr_t = tog["transfer"]
    al = tog["all_listed"]
    t_hits, t_fp = al["hits_total"], al["fp_total"]
    t_hits_a, t_fp_a = al["hits_total"] - al["hits_lost"], al["fp_total"] - al["fp_removed"]
    ls = lasset_scores(ns, mods, "heldout")["LAsset RTL-only initial"]
    LP, LR = _frac(ls["TP"], ls["TP"] + ls["FP"]), _frac(ls["TP"], ls["TP"] + ls["FN"])
    return {"status": "done", "config": config, "tuning runs": st["tuning"]["complete"], "held-out runs": st["heldout"]["complete"],
            "clusters": len(facts["clusters"]), "rule count": len(rules),
            "in-sample (tuning)": {"FPs removed": al["fp_removed"], "FP total": al["fp_total"],
                                   "hits lost": al["hits_lost"], "hit total": al["hits_total"],
                                   "P before": al["before"]["P"], "P after": al["after"]["P"],
                                   "R before": al["before"]["R"], "R after": al["after"]["R"],
                                   "reference entries": ref_t,
                                   "exact": {"P before": _ftxt(t_hits, t_hits + t_fp), "P after": _ftxt(t_hits_a, t_hits_a + t_fp_a),
                                             "R before": _ftxt(t_hits, ref_t), "R after": _ftxt(t_hits_a, ref_t)}},
            "held-out": {"listed": len(y), "reference entries": ref, "assets removed": k,
                         "FPs removed": removed, "FP total": FP, "hits lost": lost, "hit total": TP,
                         "P before": pb, "P after": pa, "R before": rb, "R after": ra,
                         "exact": {"P before": _ftxt(TP, TP + FP), "P after": _ftxt(TP - lost, kept_n),
                                   "R before": _ftxt(TP, ref), "R after": _ftxt(TP - lost, ref)}},
            "fault_reporter agrees": (fr_t["fp_removed"], fr_t["hits_lost"], fr_t["fp_total"], fr_t["hits_total"]) == (removed, lost, FP, TP),
            "random removal": {"draws": draws, "seed": seed, "assets removed per draw": k, "assets kept per draw": kept_n,
                               "mean P after": round(float(rp.mean()), 3), "mean R after": round(float(rr.mean()), 3),
                               "P 2.5-97.5%": [round(float(np.quantile(rp, .025)), 3), round(float(np.quantile(rp, .975)), 3)],
                               "share of draws with P >= the rules P": round(reach / draws, 4),
                               "exact": {"mean P after": _ftxt(int(kept_hits.sum()), draws * kept_n),
                                         "mean R after": _ftxt(int(kept_hits.sum()), draws * ref),
                                         "P 2.5-97.5% (sample values, inverted CDF)": [_ftxt(q_lo, kept_n), _ftxt(q_hi, kept_n)],
                                         "rules P compared against": _ftxt(TP - lost, kept_n),
                                         "draws with P >= the rules P": _ftxt(reach, draws),
                                         "most hits kept in any draw": _ftxt(int(kept_hits.max()), kept_n)}},
            "LAsset RTL-only, held-out": {"P": ls["P"], "R": ls["R"], "TP": ls["TP"], "FP": ls["FP"], "FN": ls["FN"],
                                          "P gap before rules": round(float(Pb - LP), 3), "P gap after rules": round(float(Pa - LP), 3),
                                          "R gap before rules": round(float(Rb - LR), 3), "R gap after rules": round(float(Ra - LR), 3),
                                          "how": "gaps from exact values, then rounded",
                                          "exact": {"P": _ftxt(ls["TP"], ls["TP"] + ls["FP"]), "R": _ftxt(ls["TP"], ls["TP"] + ls["FN"])}},
            "report": _rel(out / "fault_report" / f"{slug}_tuning_to_heldout" / "report.md")}


def _rel(p: Path) -> str:
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


# --------------------------------------------------------------------------------------- minimal pairs ---
def minimal_pairs(led, k: int = 6):
    """Pairs of one hit and one FP with the same exact profile and the same cited record type. Groups with the most
    FPs first, a cited record before none; within a group, prefer different modules, then both citations verified,
    then the same role. An element is used once. Two rows per pair (TP, then FP)."""
    import pandas as pd
    d = led[led["in_map"]].sort_values(["module", "element", "run"]).reset_index(drop=True)
    groups = []
    for (p, t), g in d.groupby(["profile", "cited_type"], sort=True):
        c = Counter(g["label"])
        if c.get("TP") and c.get("FP"):
            groups.append((t == "none", -c["FP"], -c["TP"], "; ".join(p), t, g))
    groups.sort(key=lambda x: x[:5])
    used, out = set(), []
    for _n, nfp, ntp, ptxt, t, g in groups:
        if len(out) >= 2 * k:
            break
        best = None
        tps = [r for r in g.itertuples() if r.label == "TP" and (r.split, r.module, r.element) not in used]
        fps = [r for r in g.itertuples() if r.label == "FP" and (r.split, r.module, r.element) not in used]
        for f in fps:
            for h in tps:
                s = (h.module != f.module, h.citation == "verified" and f.citation == "verified", h.role == f.role)
                if best is None or s > best[0]:
                    best = (s, h, f)
        if best is None:
            continue
        pair = len(out) // 2 + 1
        for side, r in (("TP", best[1]), ("FP", best[2])):
            used.add((r.split, r.module, r.element))
            out.append({"pair": pair, "side": side, "profile": ptxt, "cited type": t, "group hits": -ntp, "group FPs": -nfp,
                        "split": r.split, "run": r.run, "module": r.module, "element": r.element, "role": r.role,
                        "occurrence": r.occurrence, "line": r.line, "rtl": r.rtl, "cited edge": r.cited_edge,
                        "citation": r.citation})
    return pd.DataFrame(out)


# -------------------------------------------------------------------------------- unreferenced concepts ---
def concept_counts(d) -> dict:
    """On ledger rows d: a concept is (split, run, module, concept name); it is referenced when any TP row lists it in
    any position of 'concepts'. Counts FPs whose first concept is unreferenced, and FPs none of whose concepts is."""
    key = lambda r, c: (r.split, r.run, r.module, c)
    listed = {key(r, c) for r in d.itertuples() for c in r.concepts}
    ref = {key(r, c) for r in d[d["label"] == "TP"].itertuples() for c in r.concepts}
    fps = list(d[d["label"] == "FP"].itertuples())
    first = sum(key(r, r.concepts[0]) not in ref for r in fps)
    none_ = sum(all(key(r, c) not in ref for c in r.concepts) for r in fps)
    nfp = len(fps)
    return {"concepts listed": len(listed), "concepts with no reference element": len(listed - ref), "FP total": nfp,
            "FPs whose first concept lists no reference element": first,
            "share (first concept)": round(first / nfp, 3) if nfp else 0.0,
            "FPs none of whose concepts lists one": none_,
            "share (none of its concepts)": round(none_ / nfp, 3) if nfp else 0.0,
            "FPs listed under more than one concept": sum(len(r.concepts) > 1 for r in fps)}


def unreferenced_concepts(ns, led) -> dict:
    """FPs listed under concepts that list no reference element (concept_counts), pooled (pooled_label) and per split.
    'FPs none of whose concepts lists one' is the stricter count and the one the summary reports. The old reading,
    fp_diagnosis D5 (every asset, hits too, counted under its first concept only), is kept under 'fp_diagnosis D5' for
    comparison with earlier outputs of this module."""
    out = {}
    for name, d in ((pooled_label(led), led), *((sp, led[led["split"] == sp]) for sp in SPLITS)):
        if not len(d):
            out[name] = "no complete run"
            continue
        o = concept_counts(d)
        r = ns.fd.d5_concepts(d[["run", "module", "concept", "label"]].to_dict("records"))
        nfp = o["FP total"]
        o["fp_diagnosis D5"] = {"concepts": r["concepts"], "concepts with no reference element": r["concepts_without_TP"],
                                "FPs in them": r["fp_in_concepts_without_TP"], "FP total": nfp,
                                "share": round(r["fp_in_concepts_without_TP"] / nfp, 3) if nfp else 0.0}
        out[name] = o
    return out


# --------------------------------------------------------------------------------------------- summary ---
def run_scores(ns, mods: dict, config: str) -> dict:
    """Strict P and R per complete run, per split; and the 41-module figure from the per-run mean counts of each split
    (only when both splits have a complete run). LAsset's lists on the same modules."""
    st = run_status(ns, mods, config)
    out, mean = {}, {}
    for split in SPLITS:
        rows = []
        for r in st[split]["complete"]:
            s = ns.ea.score(ROOT / r, mods["gt"], strict=True, only=set(mods[split]))
            rows.append({"run": Path(r).name, "P": round(s["precision"], 3), "R": round(s["recall"], 3),
                         "TP": s["tp"], "FP": s["fp"], "FN": s["fn"]})
        if rows:
            mean[split] = {k: sum(x[k] for x in rows) / len(rows) for k in ("TP", "FP", "FN")}
        out[split] = {"modules": len(mods[split]), "reference entries": mods["entries"][split], "runs": rows,
                      "pending": st[split]["pending"], "LAsset": lasset_scores(ns, mods, split)}
    if len(mean) == 2:
        tp, fp, fn = (sum(mean[s][k] for s in SPLITS) for k in ("TP", "FP", "FN"))
        out["all 41 modules"] = {"P": round(tp / (tp + fp), 3), "R": round(tp / (tp + fn), 3),
                                 "how": "per-run mean TP, FP, FN of each split, summed over the two splits"}
    else:
        out["all 41 modules"] = "pending (a split has no complete run)"
    lt = {}
    for name in ("LAsset spec+RTL initial", "LAsset spec+RTL refined", "LAsset RTL-only initial"):
        tp = sum(out[s]["LAsset"][name]["TP"] for s in SPLITS)
        fp = sum(out[s]["LAsset"][name]["FP"] for s in SPLITS)
        fn = sum(out[s]["LAsset"][name]["FN"] for s in SPLITS)
        lt[name] = {"P": round(tp / (tp + fp), 3), "R": round(tp / (tp + fn), 3), "TP": tp, "FP": fp, "FN": fn}
    out["LAsset, all 41 modules"] = lt
    return out


def analyse_config(ns, mods: dict, config: str, out: Path = OUT) -> dict:
    """Every reading for one configuration."""
    led = ledger(ns, mods, config)
    res = {"config": config, "status": run_status(ns, mods, config), "ledger": led}
    if not len(led):
        return res
    res.update(pooled=pooled_label(led), scores=run_scores(ns, mods, config), citations=citations(led), cited_types=cited_types(led),
               overlap=overlap(ns, mods, led), separability=separability(led), minimal_pairs=minimal_pairs(led),
               concepts=unreferenced_concepts(ns, led), transfer=transfer(ns, mods, config, led=led, out=out))
    return res


def summary(res: dict) -> dict:
    """The headline numbers of one configuration's readings (analyse_config), for the notebook. Pooled figures are
    under the label res['pooled'] (pooled_label). 'record type cited by the most FPs' is the first row of cited_types
    (sorted by FP count, then hits), with its share of all FPs and of all hits."""
    led, st = res["ledger"], res["status"]
    if not len(led):
        return {"config": res["config"], "status": "no complete run"}
    pooled = res["pooled"]
    cit = res["citations"].set_index(["split", "label"])
    ov, sep, tr, cc = res["overlap"], res["separability"]["features"]["profile"], res["transfer"], res["concepts"]
    ex, reach = ov["exact profile"], "share of draws with P >= the rules P"
    ct = res["cited_types"].set_index("cited type")
    top = ct.index[0]
    n = Counter(led["label"])
    cover = {sp: f"{led[led['split'] == sp]['module'].nunique()} modules, {len(st[sp]['complete'])} complete run(s)"
             + (", pending: " + ", ".join(f"{Path(r).name} ({st[sp]['pending on disk'][r]})" for r in st[sp]["pending"])
                if st[sp]["pending"] else "") for sp in SPLITS}
    pend = [sp for sp in SPLITS if not st[sp]["complete"]]
    cp = cc[pooled] if isinstance(cc.get(pooled), dict) else None
    h = {"config": res["config"], "coverage": cover,
         "scope": pooled + (f"; {', '.join(pend)} pending" if pend else ""),
         "pooled readings over": pooled,
         "listed assets (pooled over runs)": len(led), "hits": n["TP"], "FPs": n["FP"],
         "scores": res["scores"],
         "FP citations verified": f"{int(cit.loc[(pooled, 'FP'), 'verified'])}/{n['FP']} "
                                  f"({cit.loc[(pooled, 'FP'), 'verified share']:.3f})" if "verified" in cit else None,
         "hit citations verified": f"{int(cit.loc[(pooled, 'TP'), 'verified'])}/{n['TP']} "
                                   f"({cit.loc[(pooled, 'TP'), 'verified share']:.3f})" if "verified" in cit else None,
         "record type cited by the most FPs": f"{top}: {ct.loc[top, 'share of FPs']:.3f} of FPs, {ct.loc[top, 'share of hits']:.3f} of hits",
         "assets citing no record (edge null) that are FPs": (f"{int(ct.loc['none', 'FPs'])}/{int(ct.loc['none', 'FPs'] + ct.loc['none', 'hits'])}"
                                                              if "none" in ct.index else "0/0"),
         "relationship classes on both hits and FPs": f"{ov['relationship classes on both hits and FPs']}/{ov['relationship classes']}",
         "element attributes on both hits and FPs": f"{ov['element attributes on both hits and FPs']}/{ov['element attributes']}",
         "FPs whose exact profile a hit has": f"{ex['FPs whose exact profile a hit has']}/{ov['FPs']} ({ex['share']:.3f})",
         "... a hit in another module": f"{ex['... of a hit in another module']}/{ov['FPs']} ({ex['share (other module)']:.3f})",
         "AUC hit vs FP from the profile": {k: sep[k] for k in ("in-sample", "leave one module out", "train tuning, test held-out")},
         "AUC modules": res["separability"]["modules"],
         "FPs none of whose concepts lists a reference element": (f"{cp['FPs none of whose concepts lists one']}/{cp['FP total']} "
                                                                  f"({cp['share (none of its concepts)']:.3f})" if cp else None),
         "minimal pairs found": int(res["minimal_pairs"]["pair"].nunique()) if len(res["minimal_pairs"]) else 0}
    if tr.get("status") == "done":
        ho, rnd, la = tr["held-out"], tr["random removal"], tr["LAsset RTL-only, held-out"]
        h["rules tuning -> held-out"] = {
            "rules": tr["rule count"], "FPs removed": f"{ho['FPs removed']}/{ho['FP total']}", "hits lost": f"{ho['hits lost']}/{ho['hit total']}",
            "P": f"{ho['P before']} -> {ho['P after']} ({ho['exact']['P before']} -> {ho['exact']['P after']})",
            "R": f"{ho['R before']} -> {ho['R after']} ({ho['exact']['R before']} -> {ho['exact']['R after']})",
            f"random removal of the same count (mean of {rnd['draws']} draws)":
                f"P {rnd['mean P after']}, R {rnd['mean R after']}; draws reaching the rules' exact P "
                f"{rnd['exact']['draws with P >= the rules P']} ({rnd[reach]})",
            "LAsset RTL-only on held-out": f"P {la['P']}, R {la['R']}"}
    else:
        h["rules tuning -> held-out"] = f"pending ({tr.get('why')})"
    return h


# -------------------------------------------------------------------------------------------- writing ---
def _jsonable(o):
    import pandas as pd
    if isinstance(o, pd.DataFrame):
        return o.to_dict("records")
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    if hasattr(o, "item"):
        return o.item()
    return str(o)


def write(res: dict, out: Path = OUT) -> Path:
    """CSV tables and one JSON of the readings under out/<config slug>/."""
    d = out / CONFIGS[res["config"]]["slug"]
    d.mkdir(parents=True, exist_ok=True)
    led = res["ledger"].copy()
    for c in ("profile", "profile_type"):
        led[c] = led[c].map(lambda t: "; ".join(t))
    led["concepts"] = led["concepts"].map(lambda t: json.dumps(list(t), ensure_ascii=False))   # names may hold ';'
    led.to_csv(d / "ledger.csv", index=False, encoding="utf-8")
    for k in ("citations", "cited_types", "minimal_pairs"):
        if k in res:
            res[k].to_csv(d / f"{k}.csv", index=False, encoding="utf-8")
    keep = {k: v for k, v in res.items() if k not in ("ledger", "citations", "cited_types", "minimal_pairs")}
    keep["summary"] = summary(res)
    (d / "readings.json").write_text(json.dumps(keep, indent=1, default=_jsonable), encoding="utf-8")
    return d


def main(ns=None, mods=None, log=print) -> dict:
    """Every configuration: readings, files under map_pipeline/fp_trace41/, and the summaries."""
    if ns is None:
        sys.path.insert(0, str(ROOT / "map_pipeline"))
        import final_pipeline as FP
        ns = FP.setup()
        mods = FP.modules(ns.ea)
    out = {}
    for config in CONFIGS:
        res = analyse_config(ns, mods, config)
        if len(res["ledger"]):
            p = write(res)
            log(f"{config}: wrote {_rel(p)}")
        out[config] = summary(res)
    (OUT / "summary.json").write_text(json.dumps(out, indent=1, default=_jsonable), encoding="utf-8")
    return out


# ------------------------------------------------------------------------------------------- self-test ---
def rtl_line(split: str, module: str, n: int) -> str:
    """Line n of the RTL file, comment removed and stripped (as the traced inputs print it)."""
    s = (RTL_DIR[split] / f"{module}.vhd").read_text(encoding="utf-8").splitlines()[n - 1]
    q = False
    for i, ch in enumerate(s):
        if ch == '"':
            q = not q
        if not q and s[i:i + 2] == "--":
            return s[:i].strip()
    return s.strip()


# Read by hand on 2026-10-02: the RTL line with `sed -n '<line>p' <file>` (comment and indentation removed), the
# occurrence ID -> line and the records from the stored map step1/lasset_step1/relation_map_code_{tuning,heldout}/
# b0e767000ec2_codetags/<module>.json; the profile tokens derived by hand from those records.
_P_WDT_CTRL = ("constant driver; control -> internal; controlled <- input port; controlled <- internal; data -> output port; "
               "data <- input port; kind: signal; record field; reset; storage: stored")
_P_GPIO_IRQ = ("constant driver; controlled <- input port; data -> output port; data <- input port; kind: signal; reset; "
               "storage: stored")
HAND_ROWS = [
    # data/RTL_data/neorv32_wdt.vhd:134; map cnt occurrence 4 -> 134; CONSTRAINS cnt_timeout, SOURCES / DERIVES_FROM cnt,
    # CLOCKED_BY clk_i at 3 and 4, RESET_BY, GATED_BY ctrl.enable / reset_wdt / cnt_inc, constant drivers
    {"split": "tuning", "run": "assets_opt_v1_r0", "module": "neorv32_wdt", "element": "cnt", "label": "TP", "occurrence": 4,
     "line": 134, "text": "cnt <= std_ulogic_vector(unsigned(cnt) + 1);", "cited_edge": "CLOCKED_BY clk_i", "citation": "verified",
     "profile_text": "constant driver; control -> internal; controlled <- internal; kind: signal; reset; storage: stored; "
                     "updates itself (data)"},
    # data/RTL_data/neorv32_wdt.vhd:96; map ctrl.strict occurrence 3 -> 96; GATES hw_rst_access, CARRIES bus_rsp_o.data,
    # CLOCKED_BY clk_i, RESET_BY, GATED_BY bus_req_i.addr / rw / stb and ctrl.lock, DERIVES_FROM bus_req_i.data
    {"split": "tuning", "run": "assets_opt_v1_r0", "module": "neorv32_wdt", "element": "ctrl.strict", "label": "FP", "occurrence": 3,
     "line": 96, "text": "ctrl.strict  <= bus_req_i.data(ctrl_strict_c);", "cited_edge": "CLOCKED_BY clk_i", "citation": "verified",
     "profile_text": _P_WDT_CTRL},
    # data/RTL_data/neorv32_wdt.vhd:94: the hit next to it, same profile
    {"split": "tuning", "run": "assets_opt_v1_r0", "module": "neorv32_wdt", "element": "ctrl.enable", "label": "TP", "occurrence": 3,
     "line": 94, "text": "ctrl.enable  <= bus_req_i.data(ctrl_enable_c);", "cited_edge": "CLOCKED_BY clk_i", "citation": "verified",
     "profile_text": _P_WDT_CTRL},
    # data/RTL_heldout/neorv32_gpio.vhd:75 and :76; map irq_typ occurrence 3 -> 75, irq_pol occurrence 3 -> 76; both: CARRIES
    # bus_rsp_o.data, CLOCKED_BY clk_i, RESET_BY rstn_i, SELECTED_BY bus_req_i.addr, GATED_BY bus_req_i.rw / stb,
    # DERIVES_FROM bus_req_i.data, constant driver (identical record sets)
    {"split": "heldout", "run": "assets_opt_heldout_v1_r0", "module": "neorv32_gpio", "element": "irq_typ", "label": "TP",
     "occurrence": 3, "line": 75, "text": "when addr_tt_c  => irq_typ  <= bus_req_i.data(GPIO_NUM-1 downto 0);",
     "cited_edge": "CLOCKED_BY clk_i", "citation": "verified", "profile_text": _P_GPIO_IRQ},
    {"split": "heldout", "run": "assets_opt_heldout_v1_r0", "module": "neorv32_gpio", "element": "irq_pol", "label": "FP",
     "occurrence": 3, "line": 76, "text": "when addr_tp_c  => irq_pol  <= bus_req_i.data(GPIO_NUM-1 downto 0);",
     "cited_edge": "CLOCKED_BY clk_i", "citation": "verified", "profile_text": _P_GPIO_IRQ},
]
# Read by hand on 2026-10-02 with json from the flat run files runs/<run>/<module>.json ("Assets" -> "Asset RTL") and the
# reference data/ground_truth/manual_gt_neorv32.json ("modules" -> <module> -> "assets" -> "element"). Every listed name
# that is a reference name is a hit; no record <-> field near-match is involved in these two modules.
#   neorv32_wdt, assets_opt_v1_r0: 15 listed; reference ctrl.enable, ctrl.lock, ctrl.timeout, cnt, cnt_timeout,
#     reset_cause, reset_wdt, clkgen_en_o (8), all listed.
#   neorv32_gpio, assets_opt_heldout_v1_r0: 11 listed; reference gpio_o, irq_en, irq_typ, port_in, port_out, gpio_i,
#     irq_pend, irq_clrn, cpu_irq_o (9), all listed.
HAND_FLAT = [
    {"split": "tuning", "run": "runs/assets_opt_v1_r0", "module": "neorv32_wdt", "listed": 15, "TP": 8,
     "FP names": ["cnt_started", "ctrl.strict", "hw_rst_access", "hw_rst_timeout", "reset_force", "rstn_dbg_i", "rstn_o"]},
    {"split": "heldout", "run": "runs/assets_opt_heldout_v1_r0", "module": "neorv32_gpio", "listed": 11, "TP": 9,
     "FP names": ["irq_pol", "irq_trig"]},
]
# Read by hand on 2026-10-02 from runs/assets_opt_v1_r0/_nested/neorv32_wdt.json: 9 concepts. rstn_o (an FP) is listed
# under "Access-violation reset ..." (with reset_force, hw_rst_access: all FPs) and then "Timeout expiry and reset
# request ..." (with cnt_timeout, a hit). Concepts with no hit: "Strict-mode setting ..." (ctrl.strict) and
# "Access-violation reset ...". FPs whose first concept has no hit: ctrl.strict, reset_force, hw_rst_access, rstn_o (4);
# FPs none of whose concepts has a hit: the same minus rstn_o (3).
HAND_CONCEPTS = {"split": "tuning", "run": "assets_opt_v1_r0", "module": "neorv32_wdt", "element": "rstn_o",
                 "concepts": ("Access-violation reset -- a refused write (lock set or wrong password) and the hardware "
                              "reset it requests in strict mode",
                              "Timeout expiry and reset request -- the decision that the count reached the threshold "
                              "and the hardware reset it requests"),
                 "counts": {"concepts listed": 9, "concepts with no reference element": 2, "FP total": 7,
                            "FPs whose first concept lists no reference element": 4,
                            "FPs none of whose concepts lists one": 3}}
GT_FILE = ROOT / "data/ground_truth/manual_gt_neorv32.json"


def recount_flat(run: str, module: str) -> dict | None:
    """An independent recount of one module of one run, without eval_assets or fp_diagnosis: the flat run file and the
    raw reference file read with json; each reference entry, in order, takes an unused listed name that equals it, else
    one that is its record (reference dotted) or one of its fields (reference undotted), candidates in (name, index)
    order (the strict rule as eval_assets documents it). None when the reference repeats a name (the scorer caps
    repeats by the entities that declare the name, which this recount does not model)."""
    data = json.loads((ROOT / run / f"{module}.json").read_text(encoding="utf-8"))
    listed = [(a.get("Entity", ""), a["Asset RTL"]) for a in data.get("Assets", []) if a.get("Asset RTL")]
    ref = [a["element"] for a in json.loads(GT_FILE.read_text(encoding="utf-8"))["modules"][module]["assets"] if a.get("element")]
    if len(ref) != len(set(ref)):
        return None
    used = set()
    for rn in ref:
        free = sorted((i for i in range(len(listed)) if i not in used), key=lambda i: (listed[i][1], i))
        hit = next((i for i in free if listed[i][1] == rn), None)
        if hit is None:
            base = rn.split(".")[0]
            hit = next((i for i in free if (listed[i][1] == base if "." in rn else listed[i][1].split(".")[0] == rn)), None)
        if hit is not None:
            used.add(hit)
    return {"listed": listed, "labels": ["TP" if i in used else "FP" for i in range(len(listed))], "reference": len(ref)}


# The first minimal pair of the Claude ledger: data/RTL_data/neorv32_trng.vhd:171 and data/RTL_heldout/neorv32_neoled.vhd:191
HAND_PAIR = {"TP": {"module": "neorv32_trng", "element": "fifo.re", "line": 171,
                    "text": "fifo.re    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '0') and (bus_req_i.addr(2) = '1') else '0';"},
             "FP": {"module": "neorv32_neoled", "element": "tx_fifo.we", "line": 191,
                    "text": "tx_fifo.we    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(2) = '1') else '0';"}}


def selftest(ns, mods, log=print) -> bool:
    """Hand-read ledger rows against the RTL files; every ledger row with a line against its RTL line (rows without
    one counted and skipped); the ledger's labels against an independent recount from the flat run files (hand-read
    for two modules, recount_flat for every module of every complete run); the concepts of one hand-read asset and
    one module's concept counts; the token partition against fault_reporter.profile; one minimal pair read on both RTL
    lines; the random control is deterministic and compared exactly."""
    import pandas as pd
    ok = True

    def chk(c, msg):
        nonlocal ok
        ok &= bool(c)
        log(f"{'ok  ' if c else 'FAIL'} {msg}")
    led = ledger(ns, mods, "final prompt, Claude")
    for h in HAND_ROWS:
        r = led[(led["split"] == h["split"]) & (led["run"] == h["run"]) & (led["module"] == h["module"]) & (led["element"] == h["element"])]
        chk(len(r) == 1, f"{h['run']}/{h['module']}/{h['element']}: one ledger row ({len(r)})")
        if len(r) != 1:
            continue
        r = r.iloc[0]
        chk(r["label"] == h["label"] and r["line"] == h["line"] and r["rtl"] == h["text"] == rtl_line(h["split"], h["module"], h["line"]),
            f"{h['module']} {h['element']}: {h['label']}, occurrence {r['occurrence']} -> line {h['line']}, text equals the file's line")
        for k in ("occurrence", "cited_edge", "citation", "profile_text"):
            if k in h:
                chk(r[k] == h[k], f"{h['module']} {h['element']}: {k} = {h[k]!r} (ledger {r[k]!r})")
    # the ledger's labels against the flat run files: hand-read, then the independent recount on every module
    for h in HAND_FLAT:
        g = led[(led["split"] == h["split"]) & (led["run"] == Path(h["run"]).name) & (led["module"] == h["module"])]
        rc = recount_flat(h["run"], h["module"])
        chk((len(g), int((g["label"] == "TP").sum()), sorted(g[g["label"] == "FP"]["element"])) == (h["listed"], h["TP"], h["FP names"]),
            f"{Path(h['run']).name}/{h['module']}: ledger {len(g)} listed, {int((g['label'] == 'TP').sum())} TP, FPs as read by hand")
        chk(rc is not None and rc["labels"].count("TP") == h["TP"] and len(rc["listed"]) == h["listed"]
            and sorted(n for (_e, n), l in zip(rc["listed"], rc["labels"]) if l == "FP") == h["FP names"],
            f"{Path(h['run']).name}/{h['module']}: recount_flat agrees with the hand reading")
    for config in CONFIGS:
        st = run_status(ns, mods, config)
        L = led if config == "final prompt, Claude" else ledger(ns, mods, config)
        # every ledger row's text against its RTL line; a row whose occurrence has no line is counted and skipped
        has_line = L["line"].map(lambda v: v is not None and not (isinstance(v, float) and pd.isna(v)) and v != "")
        with_line, no_line = L[has_line], L[~has_line]
        bad = sum(r.rtl != rtl_line(r.split, r.module, int(r.line)) for r in with_line.itertuples())
        chk(bad == 0, f"{config}: ledger rows with a line whose text equals the RTL file line: {len(with_line) - bad}/"
                      f"{len(with_line)}; rows without a line (skipped): {len(no_line)}/{len(L)}")
        chk((no_line["rtl"] == "").all(), f"{config}: rows without a line carry no RTL text ({int((no_line['rtl'] != '').sum())} do)")
        chk(all(len(r.concepts) >= 1 and r.concepts[0] == r.concept for r in L.itertuples()),
            f"{config}: every ledger row lists at least one concept and the first is its 'concept' ({len(L)} rows)")
        for split in SPLITS:
            for r in st[split]["complete"]:
                same, diff, skipped = 0, [], []
                for m in mods[split]:
                    rc = recount_flat(r, m)
                    if rc is None:
                        skipped.append(m)
                        continue
                    g = L[(L["split"] == split) & (L["run"] == Path(r).name) & (L["module"] == m)]
                    if [(e, n, l) for (e, n), l in zip(rc["listed"], rc["labels"])] == list(zip(g["entity"], g["element"], g["label"])):
                        same += 1
                    else:
                        diff.append(m)
                chk(not diff, f"{config} {Path(r).name}: ledger rows and labels equal the independent recount in "
                              f"{same}/{same + len(diff)} modules; skipped (reference repeats a name): {len(skipped)} "
                              f"({', '.join(skipped) or '-'}){'; differ: ' + ', '.join(diff) if diff else ''}")
    # concepts: one asset and one module read by hand
    hc = HAND_CONCEPTS
    r = led[(led["split"] == hc["split"]) & (led["run"] == hc["run"]) & (led["module"] == hc["module"]) & (led["element"] == hc["element"])]
    chk(len(r) == 1 and tuple(r.iloc[0]["concepts"]) == hc["concepts"],
        f"{hc['module']} {hc['element']}: listed under the two concepts read by hand")
    g = led[(led["split"] == hc["split"]) & (led["run"] == hc["run"]) & (led["module"] == hc["module"])]
    cn = concept_counts(g)
    chk(all(cn[k] == v for k, v in hc["counts"].items()),
        f"{hc['module']} concept counts as read by hand: " + ", ".join(f"{k} {cn[k]}" for k in hc["counts"]))
    # token partition: the element-attribute tokens are exactly those fault_reporter.profile gives an element whose
    # relationship records and connections are removed
    attr_ok, seen, toks = True, 0, set()
    for split in SPLITS:
        cache: dict = {}
        for x in led[(led["split"] == split) & led["in_map"]].drop_duplicates(["module", "entity", "element"]).itertuples():
            mod = cache.setdefault(x.module, ns.fd.load_module(split, x.module))
            e = mod["els"].get((x.entity, x.element)) or next(v for k, v in mod["els"].items() if k[1] == x.element)
            bare = ns.fr.profile({**e, "relationship": [], "connections": []}, mod, "class")
            full = set(x.profile)
            toks |= full
            attr_ok &= bare == {t for t in full if token_kind(t) == "element attribute"}
            seen += 1
    chk(attr_ok, f"token partition matches fault_reporter.profile on {seen} distinct elements "
                 f"({sum(token_kind(t) == 'relationship class' for t in toks)} relationship classes, "
                 f"{sum(token_kind(t) == 'element attribute' for t in toks)} element attributes)")
    hp = set(_P_WDT_CTRL.split("; "))
    chk({t for t in hp if token_kind(t) == "element attribute"} == {"constant driver", "kind: signal", "record field", "storage: stored"},
        "neorv32_wdt ctrl.strict profile (hand-read): element attributes = constant driver, kind: signal, record field, storage: stored")
    mp = minimal_pairs(led)
    chk(len(mp) >= 2, f"minimal pairs found: {len(mp) // 2}")
    if len(mp) >= 2:
        a, b = mp.iloc[0], mp.iloc[1]
        chk(a["side"] == "TP" and b["side"] == "FP" and a["profile"] == b["profile"] and a["cited type"] == b["cited type"],
            "pair 1: a hit and an FP with the same profile and cited type")
        chk(a["rtl"] == rtl_line(a["split"], a["module"], int(a["line"])) and b["rtl"] == rtl_line(b["split"], b["module"], int(b["line"])),
            f"pair 1: both RTL lines read from the files ({a['module']}:{a['line']}, {b['module']}:{b['line']})")
        if HAND_PAIR:
            for side, r in (("TP", a), ("FP", b)):
                h = HAND_PAIR[side]
                chk((r["module"], r["element"], int(r["line"]), r["rtl"]) == (h["module"], h["element"], h["line"], h["text"]),
                    f"pair 1 {side}: {h['module']} {h['element']} line {h['line']} as read by hand")
    t1 = transfer_random_check()
    chk(t1, "random-removal control: same seed gives the same draws")
    # a draw just below the rules' exact P does not reach it, although both round to the same 3 decimals (0.478)
    chk(round(47799 / 100000, 3) == round(47801 / 100000, 3) and not _frac(47799, 100000) >= _frac(47801, 100000)
        and _ftxt(121, 253) == "121/253", "exact comparison where the rounded values tie; 'numerator/denominator' text")
    log("self-test " + ("PASS" if ok else "FAIL"))
    return ok


def transfer_random_check() -> bool:
    import numpy as np
    a = np.random.default_rng(SEED).choice(100, size=10, replace=False)
    b = np.random.default_rng(SEED).choice(100, size=10, replace=False)
    return bool((a == b).all())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(ROOT / "map_pipeline"))
    import final_pipeline as FP
    _ns = FP.setup()
    _mods = FP.modules(_ns.ea)
    passed = selftest(_ns, _mods)
    if "--selftest" in sys.argv:
        sys.exit(0 if passed else 1)
    if not passed:
        print("self-test failed: nothing reported from this run")
        sys.exit(1)
    print(json.dumps(main(_ns, _mods), indent=1, default=_jsonable))
