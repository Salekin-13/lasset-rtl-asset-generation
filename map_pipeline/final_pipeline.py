"""Helpers for FINAL_NOTEBOOK.ipynb: the whole pipeline, from VHDL to an audited asset list, on the 41 NEORV32 modules
that have a manual reference in the LAsset dataset. Every step is code except asset generation (one OpenAI call per
module and run), which runs only when the notebook's RUN_API switch is on.

Steps
  1 occurrence profiles   every name occurrence of every port and signal, numbered (Occurrence ID), with its line,
                          the enclosing VHDL structure (Context, Path; tree-sitter) and its SITE tags
                          (step1/build_heldout_code_map.entities)
  2 relationship map      typed records between elements (SOURCES, GATES, CLOCKED_BY, ...), each anchored on the
                          occurrence IDs where it holds (step1/code_pairs_v2 + relation_stage.merge)
  3 traced inputs         numbered RTL + the map with occurrence IDs + a flow graph: what the generator reads
                          (assetgen_meta/traced_inputs.text)
  4 checks                self-tests against hand-read lines; rebuilt outputs byte-identical to the stored ones;
                          every occurrence on its numbered line; typed-relation accuracy against a gold sample
  5 generation            the final prompt (assetgen_meta/prompt_opt/v1/exec_prompt.txt) via meta_tools.run_version
  6 audit trail           each listed asset -> its cited occurrence ID -> line -> relationship record
                          (fp_diagnosis.rows_for_run, trace_check), and what that evidence says about precision

Portability: the occurrence-profile builders under bahavioral_patterns_of_assets/... hard-code the absolute path of the
machine they were written on, and one of them is pinned by hash in a pre-registration. load_builders() therefore loads
them from source with that one line replaced in memory, so the files stay byte-identical and the pipeline runs from any
clone.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import types
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "map_pipeline"
BUILDERS = ROOT / "bahavioral_patterns_of_assets/annotation_pack_elements/occurrence_prompts_v2/rulebook_edits"
STORED_MAPS = {"tuning": ROOT / "step1/lasset_step1/relation_map_code_tuning/b0e767000ec2_codetags",
               "heldout": ROOT / "step1/lasset_step1/relation_map_code_heldout/b0e767000ec2_codetags",
               "design": ROOT / "step1/lasset_step1/relation_map_code_design/b0e767000ec2_codetags"}
TRACED_V2 = ROOT / "assetgen_meta/traced_inputs_v2"
FINAL_PROMPT = ROOT / "assetgen_meta/prompt_opt/v1/exec_prompt.txt"
FINAL_VERSION, FINAL_SHA = "m7e194es0opt1_g54", "802ee9a90d41"
DESIGN = ["neorv32_boot_rom", "neorv32_fifo"]          # no reference entries; their maps give the FIFO port directions
PROFILE_KEYS = ("Occurrence ID", "Occurrence Lines", "Name As Written", "Line Text", "Context", "Path", "SITE Tagged")


# ------------------------------------------------------------------------------------------------- setup ---
def load_builders() -> list[str]:
    """Load the occurrence-profile builders with their hard-coded ROOT replaced in memory (the files are unchanged)."""
    loaded = []
    for name in ("build_occurrence_notebook_v2", "build_occurrence_notebook_v3b"):
        src_path = BUILDERS / f"{name}.py"
        src = src_path.read_text(encoding="utf-8")
        old = 'ROOT = Path("E:/jobs/ff/test/Prepoison_subset/bahavioral_patterns_of_assets")'
        assert old in src, f"{name}: the expected ROOT line is not there"
        src = src.replace(old, f"ROOT = Path({str(ROOT / 'bahavioral_patterns_of_assets')!r})")
        mod = types.ModuleType(name)
        mod.__file__ = str(src_path)
        exec(compile(src, str(src_path), "exec"), mod.__dict__)
        sys.modules[name] = mod
        loaded.append(name)
    return loaded


def setup():
    """Working directory = repo root; import paths; builders; tree-sitter VHDL grammar. Returns the modules."""
    os.chdir(ROOT)
    stray = sorted(p.name for p in ROOT.glob("*.py"))    # the pinned modules put the root before src/ on sys.path
    if stray:
        raise RuntimeError(f"Python files in the repo root would be imported instead of src/: {stray}. "
                           "The study code lives in src/ since 2026-10-02 (logs/LAYOUT.md); move these out of the root.")
    for p in ("src", "step1", "assetgen_meta"):
        if str(ROOT / p) not in sys.path:
            sys.path.insert(0, str(ROOT / p))
    load_builders()
    try:
        from tree_sitter_language_pack import get_parser
        get_parser("vhdl")
    except Exception as e:      # the grammar is a download of tree-sitter-language-pack
        raise RuntimeError("tree-sitter VHDL grammar missing: run `import tree_sitter_language_pack as t; t.download(['vhdl'])` "
                           f"once (network), then re-run. ({type(e).__name__}: {e})")
    import build_heldout_code_map as CM          # noqa: E402  (imports the root parser modules first)
    import relation_stage as RS, code_site_tags as CT, code_pairs_v2 as V, traced_inputs as TI   # noqa: E402
    import meta_tools as mt, eval_assets as ea, trace_check as tc, fp_diagnosis as fd, fault_reporter as fr   # noqa: E402
    return types.SimpleNamespace(CM=CM, RS=RS, CT=CT, V=V, TI=TI, mt=mt, ea=ea, tc=tc, fd=fd, fr=fr)


def modules(ea) -> dict:
    gt = ea.load_refs()["gt"]
    tune = sorted(m for m in gt if (ROOT / "data/RTL_data" / f"{m}.vhd").exists())
    held = sorted(m for m in gt if (ROOT / "data/RTL_heldout" / f"{m}.vhd").exists())
    return {"gt": gt, "tuning": tune, "heldout": held, "all_rtl_data": sorted(p.stem for p in (ROOT / "data/RTL_data").glob("*.vhd")),
            "entries": {"tuning": sum(len(gt[m]) for m in tune), "heldout": sum(len(gt[m]) for m in held)}}


# --------------------------------------------------------------------------- 1-3 profiles, maps, traced inputs ---
def build_all(ns, mods: dict, out: Path = OUT) -> dict:
    """Closed sets, occurrence profiles, relationship maps and traced inputs for the 41 modules (+ the 2 design modules).
    Deterministic; about a minute. Writes under map_pipeline/."""
    CM, CT, TI = ns.CM, ns.CT, ns.TI
    t0 = time.time()
    cs = out / "closed_sets"
    CM.write_closed_sets(mods["all_rtl_data"], ROOT / "data/RTL_data", cs / "tuning")      # all 18: fifo's ports matter
    CM.write_closed_sets(mods["heldout"], ROOT / "data/RTL_heldout", cs / "heldout")
    src = {**{m: CM.Source(ROOT / "data/RTL_data", cs / "tuning") for m in mods["tuning"] + DESIGN},
           **{m: CM.Source(ROOT / "data/RTL_heldout", cs / "heldout") for m in mods["heldout"]}}
    split_of = {**{m: "tuning" for m in mods["tuning"] + DESIGN}, **{m: "heldout" for m in mods["heldout"]}}
    maps = {"tuning": out / "maps" / "tuning", "heldout": out / "maps" / "heldout"}
    profiles, _entities = {}, CM.entities

    def keep(m, s, tagger=CT.tagger):                     # build_module calls entities(); keep its rows
        profiles[m] = _entities(m, s, tagger)
        return profiles[m]
    CM.entities = keep
    try:
        for m in mods["tuning"] + DESIGN + mods["heldout"]:
            CM.build_module(m, src[m], maps[split_of[m]])
    finally:
        CM.entities = _entities
    pdir = out / "occurrence_profiles"
    pdir.mkdir(parents=True, exist_ok=True)
    for m, ents in profiles.items():
        (pdir / f"{m}.json").write_text(json.dumps(
            {E["entity"]: {n: [{k: r[k] for k in PROFILE_KEYS} for r in rs] for n, rs in E["profile"].items()} for E in ents},
            indent=1), encoding="utf-8")
    TI.MAPS = {"tuning": [maps["tuning"]], "heldout": [maps["heldout"]]}
    TI.PARSED = {"tuning": cs / "tuning", "heldout": cs / "heldout"}
    TI._PORT_DIRS = None
    tin = out / "traced_inputs"
    for split in ("tuning", "heldout"):
        (tin / split / "_flow").mkdir(parents=True, exist_ok=True)
        for m in mods[split]:
            text, flow = TI.text(split, m)
            (tin / split / f"{m}.txt").write_text(text, encoding="utf-8")
            (tin / split / "_flow" / f"{m}.json").write_text(json.dumps(flow, indent=1), encoding="utf-8")
    return {"closed_sets": cs, "maps": maps, "traced_inputs": tin, "profiles": profiles, "split_of": split_of,
            "seconds": round(time.time() - t0, 1)}


def profile_stats(built: dict, mods: dict) -> dict:
    """Per split: elements, occurrences, relationship records."""
    out = {}
    for split in ("tuning", "heldout"):
        el = occ = rec = 0
        for m in mods[split]:
            d = json.loads((built["maps"][split] / f"{m}.json").read_text(encoding="utf-8"))
            for a in ("ports", "signals"):
                for e in d[a]:
                    el += 1
                    occ += len(e.get("occurrences", []))
                    rec += len(e.get("relationship", []))
        out[split] = {"modules": len(mods[split]), "elements": el, "occurrences": occ, "relationship records": rec}
    return out


def example_element(built: dict, module: str, entity: str, name: str) -> dict:
    """The profile rows and map records of one element (for display)."""
    rows = next((E["profile"].get(name, []) for E in built["profiles"][module] if E["entity"] == entity), [])
    split = built["split_of"][module]
    d = json.loads((built["maps"][split] / f"{module}.json").read_text(encoding="utf-8"))
    el = next((e for a in ("ports", "signals") for e in d[a] if e["entity"] == entity and e["name"] == name), None)
    return {"profile": [{k: r[k] for k in ("Occurrence ID", "Occurrence Lines", "Line Text", "Context", "SITE Tagged")} for r in rows],
            "records": (el or {}).get("relationship", []), "storage": (el or {}).get("storage")}


# ------------------------------------------------------------------------------------------------- 4 checks ---
def self_tests(ns, built: dict) -> dict:
    """The self-tests of the pipeline modules (hand-read lines inside each). Quiet; returns name -> bool."""
    quiet = lambda *a, **k: None
    ns.tc.INPUTS = built["traced_inputs"]                  # trace_check reads the inputs it is pointed at
    res = {"code_pairs_v2 (relationship records, hand-read cases)": ns.V.self_test(),
           "closed sets (build_heldout_code_map.selftest_closed)": ns.CM.selftest_closed(log=quiet),
           "held-out gpio map, 9 hand-read facts": ns.CM.selftest_heldout_gpio(built["maps"]["heldout"], log=quiet),
           "traced inputs (hand-read lines, flow, connection directions)": ns.TI.selftest(log=quiet),
           "trace_check (citation checker)": ns.tc.selftest(log=quiet),
           "code SITE tagger (75 hand-read occurrences)": ns.CT.selftest(log=quiet)}
    return res


def reproducibility(built: dict, mods: dict) -> dict:
    """Rebuilt maps and traced inputs byte-identical to the stored ones the experiments used."""
    stored = {**{m: STORED_MAPS["tuning"] for m in mods["tuning"]}, **{m: STORED_MAPS["heldout"] for m in mods["heldout"]},
              **{m: STORED_MAPS["design"] for m in DESIGN}}
    same_maps = sum((built["maps"][built["split_of"][m]] / f"{m}.json").read_bytes() == (stored[m] / f"{m}.json").read_bytes()
                    for m in stored)
    same_tin = sum((built["traced_inputs"] / s / f"{m}.txt").read_bytes() == (TRACED_V2 / s / f"{m}.txt").read_bytes()
                   and (built["traced_inputs"] / s / "_flow" / f"{m}.json").read_bytes() == (TRACED_V2 / s / "_flow" / f"{m}.json").read_bytes()
                   for s in ("tuning", "heldout") for m in mods[s])
    return {"maps byte-identical to the stored maps": f"{same_maps}/{len(stored)}",
            "traced inputs byte-identical to assetgen_meta/traced_inputs_v2": f"{same_tin}/{len(mods['tuning']) + len(mods['heldout'])}"}


def line_integrity(ns, built: dict, mods: dict) -> dict:
    """Every occurrence in every traced input sits on a numbered RTL line that names the element: its own name, its
    field name, or (for a record field) its record, as on the record's declaration or a whole-record assignment."""
    out = {}
    for split in ("tuning", "heldout"):
        ok = n = 0
        for m in mods[split]:
            text = (built["traced_inputs"] / split / f"{m}.txt").read_text(encoding="utf-8")
            lines = ns.tc.numbered_lines(text)
            mp = ns.tc.parse_map_text(text)
            for e in mp["ports"] + mp["signals"]:
                parts = e["name"].lower().split(".")
                names = {parts[-1]} | {".".join(parts[:i]) for i in range(1, len(parts) + 1)}
                for o in e.get("occurrences", []):
                    n += 1
                    ln = o.get("line")
                    ok += ln in lines and any(x in lines[ln].lower() for x in names)
        out[split] = f"{ok}/{n}"
    return out


def relation_accuracy(built: dict, seed: int = 7, draws: int = 1000) -> dict:
    """Typed relationship records of the rebuilt tuning maps against the gold sample (step1/bakeoff: 120 occurrences,
    212 records). Stratum-weighted precision / recall with a bootstrap 95% interval. The gold was written by an LLM
    (gpt-6-astra, two passes) and adjudicated, not by a person; the held-out maps have no such measurement."""
    import random
    B = ROOT / "step1" / "bakeoff"
    G = json.loads((B / "gold_items.json").read_text(encoding="utf-8"))
    items, pop = G["items"], G["population"]
    gold = json.loads((B / "gold_final.json").read_text(encoding="utf-8"))
    n_g = Counter(it["group"] for it in items)
    W = {g: pop[g] / n_g[g] for g in n_g}
    key = {it["item"]: (it["module"], it["entity"], it["element"]["name"], it["occurrence"]["id"]) for it in items}
    truth = {it["item"]: {(r["type"], r["target"]) for r in (gold[it["item"]] or {}).get("records", [])} for it in items}
    grp = {it["item"]: it["group"] for it in items}
    found = defaultdict(set)
    for m in sorted({it["module"] for it in items}):
        d = json.loads((built["maps"]["tuning"] / f"{m}.json").read_text(encoding="utf-8"))
        for a in ("ports", "signals"):
            for e in d[a]:
                for rec in e["relationship"]:
                    for at in rec["at"]:
                        for x in rec["targets"]:
                            found[(m, e["entity"], e["name"], at)].add((rec["type"], x))
    ids = [it["item"] for it in items]

    def pr(sel, typed=True):
        tp = fp = fn = 0.0
        for i in sel:
            s, t = found.get(key[i], set()), truth[i]
            if not typed:
                s, t = {x for _, x in s}, {x for _, x in t}
            w = W[grp[i]]
            tp += w * len(s & t); fp += w * len(s - t); fn += w * len(t - s)
        return tp / (tp + fp), tp / (tp + fn)
    strata = defaultdict(list)
    for i in ids:
        strata[grp[i]].append(i)
    rng = random.Random(seed)
    boots = [pr([rng.choice(v) for v in strata.values() for _ in v]) for _ in range(draws)]
    ci = lambda v: (round(sorted(v)[int(.025 * len(v))], 3), round(sorted(v)[int(.975 * len(v)) - 1], 3))
    p, r = pr(ids)
    pu, ru = pr(ids, False)
    tp = sum(len(found.get(key[i], set()) & truth[i]) for i in ids)
    fp = sum(len(found.get(key[i], set()) - truth[i]) for i in ids)
    fn = sum(len(truth[i] - found.get(key[i], set())) for i in ids)
    return {"occurrences": len(ids), "gold records": sum(len(v) for v in truth.values()),
            "typed precision": round(p, 3), "precision 95% CI": ci([b[0] for b in boots]),
            "typed recall": round(r, 3), "recall 95% CI": ci([b[1] for b in boots]),
            "target-only precision": round(pu, 3), "target-only recall": round(ru, 3),
            "correct / wrong / missed (unweighted)": f"{tp} / {fp} / {fn}"}


# --------------------------------------------------------------------------------------------- 5 generation ---
def final_prompt(ns) -> str:
    p = FINAL_PROMPT.read_text(encoding="utf-8")
    assert ns.mt.sha12(p) == FINAL_SHA, "the final prompt changed"
    assert ns.mt.check_exec_prompt(p, ns.mt.corpus_names(), FINAL_VERSION)["ok"], "the prompt fails its leak / quota checks"
    return p


def run_dirs(split: str) -> list[Path]:
    stem = "assets_tuning18" if split == "tuning" else "assets_heldout26"
    return [ROOT / f"runs/{stem}_{FINAL_VERSION}_r{k}" for k in range(3)]


def generation_status(ns, mods: dict) -> dict:
    out = {}
    for split in ("tuning", "heldout"):
        out[split] = [f"{d.name}: {sum((d / f'{m}.json').exists() and (d / '_nested' / f'{m}.json').exists() for m in mods[split])}/{len(mods[split])} modules"
                      for d in run_dirs(split)]
    return out


def generate(ns, mods: dict, built: dict, client, model: str = "gpt-5.4", splits=("heldout",)) -> list[dict]:
    """3 runs per split; modules already on disk are skipped (run_version resumes)."""
    prompt = final_prompt(ns)
    out = []
    for split in splits:
        rtl = ROOT / ("data/RTL_data" if split == "tuning" else "data/RTL_heldout")
        names = mods["all_rtl_data"] if split == "tuning" else mods["heldout"]
        kw = {} if split == "tuning" else {"stem": "assets_heldout26", "parsed_dir": "data/parsed_heldout26"}
        build = (lambda s: (lambda stem, _rtl: (built["traced_inputs"] / s / f"{stem}.txt").read_text(encoding="utf-8")))(split)
        for rep in range(3):
            out.append(ns.mt.run_version(client, FINAL_VERSION, rep, prompt, [(m, rtl / f"{m}.vhd") for m in names],
                                         model=model, extra_meta={"executor": model, "system_sha12": FINAL_SHA}, workers=6,
                                         build=build, input_note=f"traced inputs ({split})", **kw))
    return out


def scores(ns, mods: dict) -> dict:
    """Strict precision / recall of every complete run of the final version, per split, and LAsset's published lists."""
    gt = mods["gt"]
    res = {}
    for split in ("tuning", "heldout"):
        only = set(mods[split])
        runs = [d for d in run_dirs(split) if all((d / "_nested" / f"{m}.json").exists() for m in mods[split])]
        rows = []
        for d in runs:
            s = ns.ea.score(d, gt, strict=True, only=only)
            rows.append({"run": d.name, "P": round(s["precision"], 3), "R": round(s["recall"], 3), "TP": s["tp"], "FP": s["fp"], "FN": s["fn"]})
        ls = {}
        for name, lst in (("LAsset spec+RTL initial", ns.ea.load_refs()["paper"]),):
            s = ns.ea.score({m: lst.get(m, []) for m in mods[split]}, gt, strict=True, only=only)
            ls[name] = (round(s["precision"], 3), round(s["recall"], 3))
        import lasset_layer as LL
        rtl = LL.load_list("rtl_only")
        s = ns.ea.score(LL.as_run({m: rtl.get(m, []) for m in mods[split]}), gt, strict=True, only=only)
        ls["LAsset RTL-only initial"] = (round(s["precision"], 3), round(s["recall"], 3))
        res[split] = {"runs": rows, "entries": mods["entries"][split], "lasset": ls}
    return res


# ------------------------------------------------------------------------------------------- 6 audit trail ---
def audit_rows(ns, split: str, mods: dict) -> list[dict]:
    """One row per listed asset of every complete final run: label, role, cited occurrence -> line -> RTL text, cited
    edge, and whether trace_check verifies the citation against the map."""
    out = []
    for d in run_dirs(split):
        if not all((d / "_nested" / f"{m}.json").exists() for m in mods[split]):
            continue
        rows, _ = ns.fd.rows_for_run(d, split)
        for r in rows:
            out.append({"run": d.name[-2:], "module": r["module"].replace("neorv32_", ""), "element": r["element"], "label": r["label"],
                        "role": r["role"], "occurrence": r["occurrence"], "line": r["line"], "RTL line": r["rtl"],
                        "cited edge": r["edge"], "citation": r["status"], "family": r["family"]})
    return out


def precision_cap_evidence(ns, mods: dict, out: Path = OUT, client=None) -> dict:
    """What the occurrence-level evidence says about the precision plateau (final runs on gpt-5.4).
    Code only unless a client is given (then the fault reporter's gpt-5.4 step also runs). The code rules are found on
    the tuning runs; once complete held-out runs exist they are tested there unchanged (the transfer test).
    Writes the diagnosis and the fault report under map_pipeline/."""
    complete = lambda s: [str(d) for d in run_dirs(s) if all((d / "_nested" / f"{m}.json").exists() for m in mods[s])]
    runs, held = complete("tuning"), complete("heldout")
    ns.fd.OUT = out / "fp_diagnosis"
    ns.fr.OUT = out / "fault_report"
    sets = {"final prompt, gpt-5.4": runs}
    diag = ns.fd.diagnose(runs, "final_gpt54_tuning", run_sets=sets, log=lambda *a: None)
    fr = ns.fr.analyse(sets, "final prompt, gpt-5.4", "final_gpt54_tuning", client=client, llm=client is not None,
                       log=lambda *a: None, transfer_runs=held or None)
    tok = fr["token_table_class"]
    sc = fr["separability_class"]["pooled"]
    return {"diagnosis": diag, "fault": fr, "heldout_runs": held,
            "headline": {"listed": fr["listed"], "hits": fr["hits"], "false positives": fr["false_positives"],
                         "relationship classes on both hits and FPs": f"{sum(t['both'] for t in tok)}/{len(tok)}",
                         "FPs with exactly a hit's profile": fr["overlap_class"][0]["fp_in_mixed_share"],
                         "AUC hit vs FP, in-sample": sc.get("logistic_in_sample_auc"),
                         "AUC hit vs FP, leave one module out": sc.get("logistic_leave_one_module_out_auc"),
                         "FP citations verified": diag["D1"]["FP"]["verified_share"],
                         "hit citations verified": diag["D1"]["TP"]["verified_share"],
                         "FPs in concepts with no reference element": diag["D5"]["share"]}}


def lasset_layer_result() -> dict:
    """The pre-registered test of the evidence layer on LAsset's own published list (held-out, read once)."""
    p = ROOT / "assetgen_meta" / "lasset_layer" / "heldout_rtl_only.json"
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------- convergence ---
def convergence_plot(ax_p, ax_r, csv_path: Path = OUT / "convergence.csv"):
    """Precision and recall of every scored prompt version over time (tuning split, 15 modules, 111 entries), by
    executor; LAsset's published lists as reference lines. Two panels with one y-scale each (no dual axis). The
    reference-blind prompt study (stage 5) is a side study that did not feed the final prompt: left out here, listed in
    the table."""
    import pandas as pd
    INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
    FAM = {"gpt-5-mini": ("#2a78d6", "o"), "Claude agent": ("#eb6834", "s"), "gpt-5.4": ("#1baf7a", "D"), "gpt-6-astra": ("#8a8984", "^")}
    PHASES = [("2026-08-03", "v1 prompts:\nrecall study"), ("2026-08-09", "v2 prompts:\nprecision study"),
              ("2026-08-25", "parser, edge definitions,\noccurrence profiles\n(no asset runs)"),
              ("2026-09-19", "meta prompts\n+ hand arms"), ("2026-09-30", "maps, traces,\nloop, gpt-5.4")]
    d = pd.read_csv(csv_path)
    d = d[d["runs_complete"] > 0].copy()
    ext = d[d["executor"].str.startswith("LAsset")].sort_values("P_mean")
    d = d[~d["executor"].str.startswith("LAsset") & d["date"].notna() & ~d["stage"].astype(str).str.startswith("5")].copy()
    d["when"] = pd.to_datetime(d["date"].str.slice(0, 10))
    d["family"] = d["executor"].map(lambda e: "gpt-5-mini" if e.startswith("gpt-5-mini") else "gpt-5.4" if e.startswith("gpt-5.4")
                                    else "gpt-6-astra" if e.startswith("gpt-6") else "Claude agent")
    right = d["when"].max() + pd.Timedelta(days=1)
    for ax, col, name in ((ax_p, "P_mean", "precision"), (ax_r, "R_mean", "recall")):
        ax.set_facecolor(SURFACE)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.spines["left"].set_color(MUTED); ax.spines["bottom"].set_color(MUTED); ax.tick_params(colors=MUTED, labelsize=8)
        ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
        for fam, (c, mk) in FAM.items():
            x = d[d["family"] == fam]
            ax.scatter(x["when"], x[col], s=36, color=c, marker=mk, edgecolors=SURFACE, linewidths=1.2, label=fam, zorder=3)
        last = None
        for _, row in ext.sort_values(col).iterrows():
            y = row[col]
            ax.axhline(y, color=MUTED, linewidth=0.9, linestyle=(0, (4, 3)), zorder=1)
            ty = y if last is None or y - last > 0.035 else last + 0.035
            ax.text(right, ty, f" {row['version'].replace('LAsset initial ', 'LAsset ').replace('LAsset refined', 'LAsset refined')} {y:.2f}",
                    color=MUTED, fontsize=7.5, va="center")
            last = ty
        fin = d[d["version"] == "m7e194es0opt1_g54"]
        for _, row in fin.iterrows():
            ax.annotate(f"final prompt {row[col]:.3f}", (row["when"], row[col]), xytext=(-95, 14),
                        textcoords="offset points", fontsize=8, color=INK, arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})
        ax.set_ylabel(name, color=INK)
        ax.set_ylim(0.15, 1.02)
    for day, label in PHASES:
        ax_p.text(pd.Timestamp(day), 0.98, label, color=MUTED, fontsize=7.5, va="top")
    ax_p.set_title("Prompt versions over time, tuning set (15 modules, 111 reference entries; strict scoring)",
                   color=INK, fontsize=11, loc="left")
    ax_p.legend(fontsize=8, frameon=False, ncol=2, loc="center", bbox_to_anchor=(0.45, 0.45), labelcolor=INK, title="executor",
                title_fontsize=8)
    ax_r.set_xlabel("date of the run (2026)", color=MUTED)
    return d
