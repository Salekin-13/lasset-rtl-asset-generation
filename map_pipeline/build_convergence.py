"""build_convergence.py -- the convergence table: how the asset-generation prompt moved, August to October 2026.

Run from the repository root (the folder that holds eval_assets.py):

    python <path>/build_convergence.py            # self-test, then writes convergence.csv and heldout.csv
    python <path>/build_convergence.py --out DIR  # write the two CSVs to DIR instead of next to this script

What it does
- Finds every asset-run folder (see FAMILIES), groups the repeats of one version, and scores each repeat with the
  project scorer: eval_assets.score(run_dir, eval_assets.load_refs()["gt"], strict=True, only=<split modules>).
- Tuning split = the 15 modules of RTL_data/ that have a reference entry (111 entries). Held-out split = the 26
  modules of RTL_heldout/ (189 entries). Tuning rows go to convergence.csv, held-out rows to heldout.csv.
- A run is COMPLETE when every module of its split has an output file. Means use complete runs only; incomplete
  runs are named in the description and left out of every number.
- P, R, F1 and emitted are means over complete runs of the per-run values (as eval_assets.ablate does).
  P = precision, R = recall, both strict. "emitted" counts listed elements in the scored modules only.
- Date: the earliest _run_meta.json "timestamp" of the version's complete runs; if no run has one, the earliest
  file mtime inside those run folders. date_source says which.
- Descriptions, stages and log pointers are hand-written in META below; everything numeric is computed here.
- Self-test first: known figures from the logs must reproduce (to 3 decimals), plus hand-read per-module counts.
  If any check fails, nothing is written and the exit code is 1.

External rows (one list each, not runs of ours): LAsset initial spec + RTL (load_refs()["paper"]), LAsset refined
(load_refs()["paper_refined"]), LAsset initial RTL-only (LAsset_initial_results/asset_list_neorv32_initial.json,
loaded uncapped the way assetgen_meta/hand_arms/read_ist2.py and assetgen_meta/lasset_layer.py load it).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True   # read-only on the repository: no __pycache__ writes from this script
ROOT = Path.cwd()
if not (ROOT / "eval_assets.py").exists():
    sys.exit("run this from the repository root (the folder that holds eval_assets.py)")
sys.path.insert(0, str(ROOT))
import eval_assets as ea  # noqa: E402

HERE = Path(__file__).resolve().parent
COLUMNS = ["version", "stage", "description", "executor", "date", "date_source", "runs_complete", "P_mean",
           "R_mean", "F1_mean", "emitted_mean", "P_runs", "R_runs", "folder_glob", "log_source"]

# ------------------------------------------------------------------------------------------------ folders ---
# (regex on the posix path relative to the root, split, row key). The key is the version name in the CSV.
# Archive runs and pilots get their own key, so they are never pooled with top-level runs of the same name.
FAMILIES = [
    (r"^assets_tuning18_(?P<v>.+)_r(?P<k>\d+)$", "tuning", "{v}"),
    (r"^archive/assets_tuning18_(?P<v>.+)_r(?P<k>\d+)$", "tuning", "{v} [archive]"),
    (r"^assets_opt_heldout_(?P<v>.+)_r(?P<k>\d+)$", "heldout", "opt_{v}"),
    (r"^assets_opt_(?!heldout_)(?P<v>.+)_r(?P<k>\d+)$", "tuning", "opt_{v}"),
    (r"^assets_heldout26_(?P<v>.+)_r(?P<k>\d+)$", "heldout", "{v}"),
    (r"^pilot_tuning18_(?P<v>.+)_r(?P<k>\d+)$", "tuning", "pilot_{v}"),
    # blind-agent study: scored copies (eval_assets format, written by blind_agent/score_blind.py); dates come
    # from the executor outputs in blind_agent/runs/<split>/<prompt>/r<k>/
    (r"^blind_agent/scored/tuning/(?P<v>[^/]+)_r(?P<k>\d+)$", "tuning", "blind_{v}"),
    (r"^blind_agent/scored/heldout/(?P<v>[^/]+)_r(?P<k>\d+)$", "heldout", "blind_{v}"),
]
SEARCH = ["", "archive", "blind_agent/scored/tuning", "blind_agent/scored/heldout"]


def blind_source(rel: str) -> Path | None:
    m = re.match(r"^blind_agent/scored/(tuning|heldout)/([^/]+)_r(\d+)$", rel)
    return ROOT / "blind_agent" / "runs" / m.group(1) / m.group(2) / f"r{m.group(3)}" if m else None


def find_runs() -> dict:
    """{(key, split): {"runs": [(k, Path)], "glob": str}}; also warns about run-like folders no family claims."""
    groups = {}
    for base in SEARCH:
        b = ROOT / base if base else ROOT
        if not b.is_dir():
            continue
        for d in sorted(p for p in b.iterdir() if p.is_dir()):
            rel = d.relative_to(ROOT).as_posix()
            for rx, split, key in FAMILIES:
                m = re.match(rx, rel)
                if m:
                    g = groups.setdefault((key.format(v=m.group("v")), split), {"runs": [], "glob": None})
                    g["runs"].append((int(m.group("k")), d))
                    g["glob"] = re.sub(r"_r\d+$", "_r*", rel)
                    break
            else:
                if re.search(r"_r\d+$", rel) and (rel.startswith(("assets", "pilot")) or "/" in rel):
                    print(f"  [warn] run-like folder not claimed by any family: {rel}")
    for g in groups.values():
        g["runs"].sort()
    return groups


# ------------------------------------------------------------------------------------------------- metadata ---
S0 = "0 external reference (LAsset)"
S1 = "1 recall study, v1 prompts"
S2 = "2 precision study, v2 prompts"
S3 = "3 meta-prompt screen (gpt-6-astra writes the executor prompt)"
S4 = "4 hand arms on the seed prompt"
S5 = "5 blind-agent prompt study (Claude executor)"
S6 = "6 traced arms (occurrence IDs + relationship map)"
S7 = "7 prompt-optimization loop (Claude executor)"
S8 = "8 final version on gpt-5.4"
SH = "held-out check (26 modules, 189 entries)"

AL1, AL2 = "ABLATION_LOG.md", "ABLATION_LOG_V2.md"
REL = "step1/lasset_step1/RELATION_EXPERIMENTS_LOG.md"
OPT = "assetgen_meta/prompt_opt/OPTIMIZATION_LOG.md"
NB = "assetgen_meta.ipynb"
CLAUDE = "claude-opus-5-5 (Claude Code agent; model read from local session transcripts, not recorded in the repo)"

# key -> (stage, description, log_source[, executor override])
META = {
    # ---- 1: recall study (finetuning_assetgen.ipynb) ----
    "v0": (S1, "A-00 root and noise floor: core ASSET_PRIMARY_CORE + P3164 section 3.2 examples only (not "
               "format-matched); input spec summary + parsed closed set + RTL", f"{AL1} 3 A-00, 4"),
    "v01": (S1, "A-01 ICL construction: worked input-reasoning-output examples omsp_gpio + tiny_aes; port recall up, "
                "signal recall down; kept as baseline", f"{AL1} 3 A-01, 4"),
    "v01c2": (S1, "A-02 core insertion 'role, not location'; paired recall +0.162 vs v01; promoted. The log's table "
                  "is r0-r2 (n=3); r3-r4 were added 2026-08-06", f"{AL1} 3 A-02, 4, Baseline promotions"),
    "v01c3": (S1, "A-03 port-record granularity rule (record ports named whole); paired precision +0.042; promoted. "
                  "The log's table is r0-r2 (n=3); r3-r4 added later", f"{AL1} 3 A-03, 4"),
    "v01r": (S1, "A-03 control: the same granularity rule on the v0 core; n=2, directional only", f"{AL1} 3 A-03, 4"),
    "v01c4": (S1, "T-1 diagnostic: core exposes STEP 1 as a ConceptualAssets array (output-contract change; "
                  "not an arm)", f"{AL1} 3 T-1, 4"),
    "v01c5": (S1, "T-1 diagnostic + ICL 01B that shows concepts; null vs v01c4; promoted (lowest recall sd)",
              f"{AL1} 3 T-1, Baseline promotions"),
    "v01c6": (S1, "A-08 per-concept closure sweep; only arm to raise the union-of-runs ceiling; promoted; "
                  "end of the recall study", f"{AL1} 3 A-08, 4"),
    "v01c6p1": (S1, "P-1 drop the SpecRAG technical summary (the paper's Only-RTL variant); null",
                f"{AL1} 3 P-1"),
    "v01c6p1p2": (S1, "P-2 drop the parsed closed set: comment-stripped RTL only; null on recall, emissions down; "
                      "becomes v2's input regime", f"{AL1} 3 P-2"),
    # ---- 2: precision study (finetuning_assetgen_v2.ipynb) ----
    "v2": (S2, "v2 baseline: flat core prompts_v2.ASSET_V2_BASE + ICL 01B_NOPARSE, RTL only; corrections D "
               "(closed-set parity), L (de-leak, v1 arm L-1) and N (neutralise identifiers)", f"{AL2} 3, 5"),
    "v2s1": (S2, "S-1 container vs content (a store is an asset only if its content is); null on precision; "
                 "rejected", f"{AL2} 7 S-1"),
    "v2r8": (S2, "R-8 revert v1's A-08 closure sweep; mechanism confirmed, precision null; not promoted",
             f"{AL2} 7 R-8"),
    "v2x3": (S2, "X-3 third ICL case study with composition-matched negative examples; null on precision; run "
                 "without pre-registration", f"{AL2} 7 X-3"),
    "v2x3r8": (S2, "X-3R-8 = R-8 core + X-3 ICL; first distinguishable precision gain, recall guard fails; later "
                   "the baseline row (BASE) of the meta-prompt work", f"{AL2} 7 X-3R-8, 10"),
    "v2s3": (S2, "S-3 routed traffic belongs to the fabric, not to every stop along it; precision fell; rejected",
             f"{AL2} 7 S-3"),
    "v2sec": (S2, "SEC line-6 expansion: influencers demoted to a per-primary secondary array; recall collapsed; "
                  "rejected on the guard", f"{AL2} 7 SEC"),
    "v2rp": (S2, "RP restore the parsed closed set annotated with functional roles (152-label taxonomy, "
                 "prompts_parse_v2); the RP entry's Got is blank, the result is in C1's table",
             f"{AL2} 7 RP, C1"),
    "v2p3c1 [archive]": (S2, "C1 reading procedure for the v3-parse annotations, on parse gen2 (450d8de774ca): the "
                             "runs C1's table records; parsed input buys no precision over v2 and costs recall",
                         f"{AL2} 7 C1"),
    "v2p3c1": (S2, "C1 prompt re-run on parse gen3 (540765753f16); not the runs C1's table records (that table is "
                   "the archive gen2 runs)", f"{AL2} 7 C1, parser generations; _run_meta.json parse_fingerprint"),
    # ---- 3: meta-prompt screen (assetgen_meta.ipynb cells 0-13) ----
    "m4bc606s0": (S3, "meta prompt v1, sample 0: gpt-6-astra writes methodology + execution prompt; screened 1 run",
                  f"{NB} cells 0-10; assetgen_meta/error_analysis_screen1.md"),
    "m4bc606s1": (S3, "meta prompt v1, sample 1; screened 1 run", f"{NB} cells 0-10; error_analysis_screen1.md"),
    "m4bc606s2": (S3, "meta prompt v1, sample 2; screened 1 run", f"{NB} cells 0-10; error_analysis_screen1.md"),
    "m7e194es0": (S3, "meta prompt v2, sample 0: execution prompt e8df164fddb3 = the 'seed'; screen pick (recall "
                      "92/111, one under the 0.83 floor; pick rule overridden)", f"{NB} cells 7-13; _run_meta.json"),
    "m7e194es1": (S3, "meta prompt v2, sample 1; screened 1 run", f"{NB} cells 7-10"),
    "m7e194es2": (S3, "meta prompt v2, sample 2; screened 1 run", f"{NB} cells 7-10"),
    "med96f4s0": (S3, "meta prompt v3, sample 0; screened 1 run", f"{NB} cells 7-10"),
    "med96f4s1": (S3, "meta prompt v3, sample 1; screened 1 run", f"{NB} cells 7-10"),
    "med96f4s2": (S3, "meta prompt v3, sample 2; screened 1 run", f"{NB} cells 7-10"),
    "m7e194es0c": (S3, "confirmation: 3 fresh runs of the seed prompt e8df164fddb3", f"{NB} cell 11; _run_meta.json"),
    "m7e194es0ax": (S3, "path test T4: the seed prompt on the stronger gpt-6-astra executor (1 run)",
                    "_run_meta.json stage"),
    "m2a78a4s0": (S3, "meta prompt v4s_A: seeded revision of the seed, fixed changes X1-X7 (arm A keeps the seed's "
                      "input-port rule)", f"{NB} cell 10; assetgen_meta/meta_prompt_v4s_A.txt"),
    "m55eea9s0": (S3, "meta prompt v4s_B: as v4s_A with X7 boundary rule for input ports (arm B)",
                  f"{NB} cell 10; assetgen_meta/meta_prompt_v4s_B.txt"),
    "m43f965s0": (S3, "meta prompt v5s: seeded revision with X1, X3, X4 rescoped (transport interfaces "
                      "secondary), X5", f"{NB} cell 2; assetgen_meta/meta_prompt_v5s.txt"),
    # ---- 4: hand arms (assetgen_meta.ipynb cells 18-41) ----
    "m7e194es0i01b": (S4, "seed + v2's ICL_ASSET_EXAMPLES_01B_NOPARSE converted to the seed's schema",
                      "_run_meta.json stage; assetgen_meta/hand_arms/m7e194es0i01b/build_info.json"),
    "m7e194es0ism": (S4, "seed + two worked examples that follow the seed's own procedure (omsp_gpio, tiny_aes); "
                         "the winner (0d0def4c6fe3); validated once on held-out", f"{AL2} 10; {REL}"),
    "m7e194es0ismp": (S4, "ism with revised worked examples (attachment rule; validation removes operand, word and "
                          "strobe intermediates); no log entry, read from the hand_arms diff; ism stayed the winner",
                      "assetgen_meta/hand_arms/m7e194es0ismp (no log entry)"),
    "m7e194es0ismr": (S4, "+ relationship-map section and LLM-written E3 maps in the input; pre-registered bar "
                          "(P >= 0.374 at R >= 0.83) not met; recall cost", f"{NB} cell 18; {AL2} 10"),
    "m7e194es0ismc": (S4, "ismr prompt with the code-written relationship map (code_pairs_v2 b0e767000ec2)",
                      f"{NB} cell 22; {AL2} 10"),
    "m7e194es0ismcap": (S4, "+ one captured-input bullet after seed line 218; ineffective", f"{NB} cell 26; {REL}"),
    "m7e194es0ismq": (S4, "+ four P3164 questions per value with a required negative; harmful (recall cost)",
                      f"{NB} cell 30; {REL}"),
    "m7e194es0ismrq": (S4, "relationship map + four questions; harmful", f"{NB} cell 30; {REL}"),
    "m7e194es0ismd": (S4, "ASSET_DEFINITION.md rules (deciders primary, transit registers secondary); not adopted, "
                          "the transit rule was not used", f"{NB} cell 34; {REL}; assetgen_meta/ASSET_DEFINITION.md"),
    # ---- 5: blind-agent study ----
    "blind_A1": (S5, "A1 definition-first (prompt written blind, RTL + code map input)", "blind_agent/REPORT.md 2"),
    "blind_A2": (S5, "A2 = A1 self-revised without the reference", "blind_agent/REPORT.md 2"),
    "blind_B1": (S5, "B1 threat-first", "blind_agent/REPORT.md 2"),
    "blind_B2": (S5, "B2 = B1 self-revised", "blind_agent/REPORT.md 2"),
    "blind_C1": (S5, "C1 map procedure", "blind_agent/REPORT.md 2"),
    "blind_C2": (S5, "C2 = C1 self-revised", "blind_agent/REPORT.md 2"),
    "blind_D1": (S5, "D1 minimal definitional prompt (6.6k chars); winner by the pre-set rule. An r2 stopped at 6/15 "
                     "sits in blind_agent/runs_unused (not pooled)", "blind_agent/REPORT.md 2; PREREG.md"),
    "blind_D2": (S5, "D2 = D1 self-revised (37% longer). An r2 stopped at 6/15 sits in blind_agent/runs_unused "
                     "(not pooled)", "blind_agent/REPORT.md 2"),
    "blind_E1": (S5, "E1 worked examples", "blind_agent/REPORT.md 2"),
    "blind_E2": (S5, "E2 = E1 self-revised", "blind_agent/REPORT.md 2"),
    "blind_BASE": (S5, "BASE: the v2x3r8 prompt on the Claude executor with RTL + map input",
                   "blind_agent/REPORT.md 3-4"),
    "blind_CUR": (S5, "CUR: the m7e194es0ism prompt on the Claude executor with RTL + map input",
                  "blind_agent/REPORT.md 3-4"),
    # ---- 6: traced arms ----
    "m7e194es0ist": (S6, "winner restructured into eight parts; input numbered RTL + map with occurrence IDs + code "
                         "flow graph; every element cites an occurrence ID + edge; traceable, recall fails",
                     f"{NB} cells 42-49; {REL}; {AL2} 10"),
    "m7e194es0ist2": (S6, "ist without questions and side lists; established-value criteria restored; transport "
                          "and sub-unit citation fixes; inputs traced_inputs_v2; = prompt_opt v0 (e5fe4918c22b)",
                      f"{NB} cells 50-56; {REL}; {OPT}"),
    "pilot_m7e194es0ist": (S6, "Claude-executor pilot of ist (format and reasoning test, 3 modules, nested output "
                               "only); not a score", f"{REL} (pilot 2)", CLAUDE),
    "pilot_m7e194es0ist2": (S6, "Claude-executor pilots of ist2 (cpu, wdt, uart; nested output only); not a score",
                            f"{REL} (ist2 pilots)", CLAUDE),
    # ---- 7: optimization loop ----
    "opt_v0": (S7, "loop baseline: the ist2 generation prompt (e5fe4918c22b) on Claude executors, traced_inputs_v2",
               f"{OPT} v0", CLAUDE),
    "opt_v1": (S7, "edits A (a stored register needs a use record), B (no one-clock copies), C (inputs wired into "
                   "unsupplied sub-units 'set'); prompt 802ee9a90d41; kept; final loop version", f"{OPT} v1", CLAUDE),
    # ---- 8: final ----
    "m7e194es0opt1_g54": (S8, "final: the prompt_opt v1 prompt on gpt-5.4 (assetgen_meta.ipynb, cells marked opt-final)",
                          f"{OPT} last section; {NB} cells 57-60"),
    "m7e194es0ist2_g54": (S8, "paired baseline: the ist2 prompt on gpt-5.4 (OpenAI credits ran out during r2)",
                          f"{OPT} last section; {NB} cells 57-60"),
}

# held-out rows: same keys, different text
META_HELDOUT = {
    "m7e194es0ism": (SH, "winner prompt, no code levers; pre-registered, read once", "assetgen_meta/HELDOUT_PREREG.md; "
                     f"{AL2} 10"),
    "opt_v0": (SH, "loop v0 (ist2 prompt) on Claude executors; pre-registered paired check, one run",
               f"{OPT} held-out check; assetgen_meta/prompt_opt/HELDOUT_CHECK_PREREG.md", CLAUDE),
    "opt_v1": (SH, "loop v1 on Claude executors; one run; cpu_control's first output was unparseable, moved to "
                   "_invalid/ and retried once", f"{OPT} held-out check; HELDOUT_CHECK_PREREG.md", CLAUDE),
    "blind_D1": (SH, "blind-study winner D1 read once on held-out", "blind_agent/REPORT.md 2"),
}

# blind-agent executors are Claude agents too (no _run_meta.json in those folders)
for _d in (META, META_HELDOUT):
    for _k, _v in list(_d.items()):
        if _k.startswith("blind_") and len(_v) == 3:
            _d[_k] = _v + (CLAUDE,)

# registered or named versions with no run folder: listed so the plot can annotate the decision
NOT_RUN = [
    ("v1", S1, "A-01 variant with examples adapted to the parsed shape; not run (its examples were fabricated)",
     f"{AL1} 3 A-01"),
    ("v02", S1, "A-01 variant with the AES example swapped to aes_highthroughput_lowarea; registered, no run folder, "
                "no result recorded", f"{AL1} 3 A-01"),
    ("v01c6p1p2d", S1, "L-1 remove evaluation-set identifiers; registered, never run; folded into v2 as correction L",
     f"{AL1} 3 L-1; {AL2} 3"),
    ("v2p3", S2, "P3 v3-parse annotations without a reading procedure; registered, no run folder, Got blank",
     f"{AL2} 7 P3"),
    ("opt_v2", S7, "edit D withdrawn after review (contradicted the prompt's own definitions); moved to the "
                   "evaluation layer as R1a; prompt identical to v1, not run", f"{OPT} v2"),
    ("opt_v3", S7, "no edit: no candidate with a Prompt-row basis beats run noise; stopping rule met; not run",
     f"{OPT} v3"),
]

EXTERNAL = [
    ("LAsset initial (spec+RTL)", "spec_rtl", "LAsset Algorithm 1 line 5 output, spec + RTL configuration "
     "(ground_truth/lasset_initial.json); the pre-refinement comparator", f"{AL1} 4; {AL2} 1"),
    ("LAsset initial (RTL-only)", "rtl_only", "LAsset line 5 output, RTL-only configuration "
     "(LAsset_initial_results/asset_list_neorv32_initial.json); the like-for-like row for our RTL-only pipeline",
     "assetgen_meta/ASSET_DEFINITION.md (scoring policy row)"),
    ("LAsset refined", "refined", "LAsset after refinement (attack scenario, CWE, self-critique) "
     "(ground_truth/lasset_refined.json)", "assetgen_meta/ASSET_DEFINITION.md"),
]


# ---------------------------------------------------------------------------------------------- reference ---
def splits(gt: dict) -> dict:
    t = sorted(p.stem for p in (ROOT / "RTL_data").glob("*.vhd") if p.stem in gt)
    h = sorted(p.stem for p in (ROOT / "RTL_heldout").glob("*.vhd") if p.stem in gt)
    return {"tuning": t, "heldout": h}


def external_run(which: str, refs: dict) -> dict:
    if which == "spec_rtl":
        return refs["paper"]
    if which == "refined":
        return refs["paper_refined"]
    f = ROOT / "LAsset_initial_results" / "asset_list_neorv32_initial.json"
    run = {}
    for ip in json.loads(f.read_text(encoding="utf-8")):
        run.setdefault(ip["IP"], []).extend(
            (a.get("Entity", ""), a["Asset RTL"], a.get("Security Objective", ""))
            for a in ip.get("Assets", []) or [] if a.get("Asset RTL"))
    return run


# ------------------------------------------------------------------------------------------------ scoring ---
def run_meta(d: Path) -> dict:
    p = d / "_run_meta.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def earliest_mtime(dirs) -> datetime | None:
    ts = [f.stat().st_mtime for d in dirs if d and d.exists() for f in d.rglob("*") if f.is_file()]
    return datetime.fromtimestamp(min(ts)) if ts else None


def f3(x) -> str:
    return f"{x:.3f}"


def score_group(key, split, g, gt, mods) -> dict:
    per, incomplete = [], []
    for k, d in g["runs"]:
        src = blind_source(d.relative_to(ROOT).as_posix())
        have = {m for m in mods if (d / f"{m}.json").exists()}
        if src is not None:                       # blind study: the executor's own output must exist as well
            have &= {m for m in mods if (src / f"{m}.json").exists()}
        if len(have) < len(mods):
            miss = sorted(set(mods) - have)
            incomplete.append(f"r{k} {len(have)}/{len(mods)}"
                              + (f" missing {', '.join(miss)}" if 0 < len(miss) <= 3 else ""))
            continue
        s = ea.score(d, gt, strict=True, only=set(mods))
        per.append({"k": k, "dir": d, "src": src, "P": s["precision"], "R": s["recall"], "F1": s["f1"],
                    "emit": s["emit"], "tp": s["tp"], "fp": s["fp"], "fn": s["fn"], "res": s,
                    "meta": run_meta(d)})
    # date: complete runs first; all runs when none is complete
    pool = per or [{"dir": d, "src": blind_source(d.relative_to(ROOT).as_posix()), "meta": run_meta(d)}
                   for _k, d in g["runs"]]
    stamps = [(x["meta"]["timestamp"], x["meta"].get("timestamp_source")) for x in pool
              if x["meta"].get("timestamp")]
    if stamps:
        date, src_note = min(stamps)
        backfilled = any(sn for _t, sn in stamps)
        date_source = "_run_meta.json timestamp, earliest run" + (
            " (some backfilled from asset mtimes, per their timestamp_source)" if backfilled else "")
        date = date[:16]
    else:
        dirs = [x["src"] or x["dir"] for x in pool]
        t = earliest_mtime(dirs)
        date = t.strftime("%Y-%m-%d %H:%M") if t else ""
        date_source = ("earliest file mtime in " + ("blind_agent/runs/" if pool and pool[0]["src"] else "the run ")
                       + "folders (no _run_meta.json)") if t else "no files"
    metas = [x["meta"] for x in pool if x["meta"]]
    execs = sorted({(m.get("executor") or m.get("model") or "") + (f" (effort {m['effort']})" if m.get("effort")
                                                                     else "") for m in metas} - {""})
    shas = sorted({m.get("system_prompt_sha256", "")[:12] for m in metas} - {""})
    n = len(per)
    mean = (lambda f: sum(x[f] for x in per) / n) if n else None
    return {"per": per, "incomplete": incomplete, "date": date, "date_source": date_source,
            "executor": "; ".join(execs), "shas": shas, "n": n,
            "P": mean("P") if n else None, "R": mean("R") if n else None, "F1": mean("F1") if n else None,
            "emit": mean("emit") if n else None}


def build(refs) -> tuple[list, list, dict]:
    gt = refs["gt"]
    sp = splits(gt)
    groups = find_runs()
    scored = {}
    rows = {"tuning": [], "heldout": []}
    for (key, split), g in sorted(groups.items()):
        r = score_group(key, split, g, gt, sp[split])
        scored[(key, split)] = r
        meta = (META_HELDOUT.get(key) if split == "heldout" else None) or META.get(key)
        if meta is None:
            stage, desc, log, exe = "UNLABELLED", "no hand-written description for this folder", "", None
        else:
            stage, desc, log = meta[:3]
            exe = meta[3] if len(meta) > 3 else None
        notes = []
        if r["shas"]:
            notes.append("prompt sha " + " / ".join(r["shas"]) + (" (DIFFERS across runs)" if len(r["shas"]) > 1
                                                                    else ""))
        if r["incomplete"]:
            notes.append("excluded incomplete: " + "; ".join(r["incomplete"]))
        rows[split].append({
            "version": key, "stage": stage, "description": desc + (" [" + "; ".join(notes) + "]" if notes else ""),
            "executor": exe or r["executor"] or "not recorded", "date": r["date"], "date_source": r["date_source"],
            "runs_complete": r["n"],
            "P_mean": f3(r["P"]) if r["n"] else "", "R_mean": f3(r["R"]) if r["n"] else "",
            "F1_mean": f3(r["F1"]) if r["n"] else "", "emitted_mean": f"{r['emit']:.1f}" if r["n"] else "",
            "P_runs": ";".join(f3(x["P"]) for x in r["per"]), "R_runs": ";".join(f3(x["R"]) for x in r["per"]),
            "folder_glob": g["glob"], "log_source": log})
    for name, which, desc, log in EXTERNAL:
        run = external_run(which, refs)
        for split, mods in sp.items():
            present = [m for m in mods if m in run]
            s = ea.score({m: run[m] for m in present}, gt, strict=True, only=set(mods))
            scored[(name, split)] = {"P": s["precision"], "R": s["recall"], "F1": s["f1"], "emit": s["emit"],
                                     "n": 1 if len(present) == len(mods) else 0, "per": [{"res": s}]}
            rows[split].append({
                "version": name, "stage": S0 if split == "tuning" else SH,
                "description": desc + ("" if len(present) == len(mods) else
                                       f" [list covers {len(present)}/{len(mods)} modules]"),
                "executor": "LAsset pipeline (published output list)", "date": "",
                "date_source": "external: published LAsset list, not a run of ours",
                "runs_complete": 1 if len(present) == len(mods) else 0,
                "P_mean": f3(s["precision"]), "R_mean": f3(s["recall"]), "F1_mean": f3(s["f1"]),
                "emitted_mean": f"{s['emit']:.1f}", "P_runs": f3(s["precision"]), "R_runs": f3(s["recall"]),
                "folder_glob": "", "log_source": log})
    for key, stage, desc, log in NOT_RUN:
        rows["tuning"].append({"version": key, "stage": stage, "description": desc, "executor": "",
                               "date": "", "date_source": "no run folder", "runs_complete": 0, "P_mean": "",
                               "R_mean": "", "F1_mean": "", "emitted_mean": "", "P_runs": "", "R_runs": "",
                               "folder_glob": "", "log_source": log})
    for split in rows:
        rows[split].sort(key=lambda r: (0 if r["date_source"].startswith("external") else
                                        2 if r["date_source"] == "no run folder" else 1,
                                        r["date"], r["version"]))
    return rows["tuning"], rows["heldout"], scored


# --------------------------------------------------------------------------------------------- self-test ---
# (key, split, P, R, complete runs, where the figure was stated)
KNOWN = [
    ("m7e194es0ism", "tuning", 0.344, 0.847, 3, f"{AL2} 10 (task brief)"),
    ("m7e194es0ist2", "tuning", 0.343, 0.733, 3, f"{OPT} last section (task brief)"),
    ("LAsset initial (spec+RTL)", "tuning", 0.737, 0.910, 1, f"{AL1} 4 (task brief)"),
    ("v0", "tuning", 0.300, 0.553, 3, f"{AL1} 4"),
    ("v01r", "tuning", 0.331, 0.626, 2, f"{AL1} 4"),
    ("v2", "tuning", 0.251, 0.925, 3, f"{AL2} 5"),
    ("v2x3r8", "tuning", 0.296, 0.853, 3, f"{AL2} 7 X-3R-8"),
    ("opt_v0", "tuning", 0.335, 0.887, 2, f"{OPT} v0"),
    ("opt_v1", "tuning", 0.371, 0.934, 3, f"{OPT} v1 third tuning run"),
    ("m7e194es0opt1_g54", "tuning", 0.407, 0.820, 3, f"{OPT} last section"),
    ("m7e194es0ist2_g54", "tuning", 0.407, 0.815, 2, f"{OPT} last section"),
    ("blind_D1", "tuning", 0.359, 0.577, 2, "blind_agent/REPORT.md 2"),
    ("LAsset initial (RTL-only)", "tuning", 0.680, 0.748, 1, "assetgen_meta/ASSET_DEFINITION.md"),
    ("LAsset refined", "tuning", 0.800, 0.901, 1, "assetgen_meta/ASSET_DEFINITION.md"),
    ("m7e194es0ism", "heldout", 0.352, 0.852, 3, f"{AL2} 10"),
    ("opt_v1", "heldout", 0.329, 0.931, 1, f"{OPT} held-out check H1"),
    ("opt_v0", "heldout", 0.310, 0.899, 1, f"{OPT} held-out check H2"),
    ("blind_D1", "heldout", 0.362, 0.619, 2, "blind_agent/REPORT.md 2"),
    ("LAsset initial (spec+RTL)", "heldout", 0.734, 0.862, 1, f"{AL2} 10"),
    ("LAsset initial (RTL-only)", "heldout", 0.730, 0.757, 1, f"{AL2} 10"),
    ("LAsset refined", "heldout", 0.791, 0.862, 1, "assetgen_meta/ASSET_DEFINITION.md"),
]
# hand-read per-module counts: assetgen_meta/prompt_opt/v0/eval_r0.md, table rows for bus and cpu
HAND = [("opt_v0", "tuning", 0, "neorv32_bus", 11, 10, 0), ("opt_v0", "tuning", 0, "neorv32_cpu", 5, 9, 9),
        ("opt_v0", "tuning", 0, "neorv32_cache", 4, 31, 2)]


def self_test(refs, scored) -> list:
    fails = []
    gt = refs["gt"]
    sp = splits(gt)
    for split, (nm, ne) in {"tuning": (15, 111), "heldout": (26, 189)}.items():
        got = (len(sp[split]), sum(len(gt[m]) for m in sp[split]))
        if got != (nm, ne):
            fails.append(f"{split} denominator {got} != {(nm, ne)}")
    ident = ea.score({m: gt[m] for m in sp["tuning"]}, gt, strict=True, only=set(sp["tuning"]))
    if (ident["precision"], ident["recall"]) != (1.0, 1.0):
        fails.append("the reference scored against itself is not P 1.0 R 1.0")
    for key, split, p, r, n, src in KNOWN:
        s = scored.get((key, split))
        if s is None or not s["n"]:
            fails.append(f"{key} ({split}): not found or no complete run [{src}]")
            continue
        if abs(s["P"] - p) > 0.0005 + 1e-9 or abs(s["R"] - r) > 0.0005 + 1e-9 or s["n"] != n:
            fails.append(f"{key} ({split}): got P {s['P']:.4f} R {s['R']:.4f} n {s['n']}, expected {p} / {r} "
                         f"n {n} [{src}]")
    for key, split, k, mod, tp, fp, fn in HAND:
        s = scored.get((key, split))
        run = next((x for x in (s or {}).get("per", []) if x.get("k") == k), None)
        pm = run["res"]["per_module"].get(mod) if run else None
        got = (pm["tp"], len(pm["fp"]), len(pm["fn"])) if pm else None
        if got != (tp, fp, fn):
            fails.append(f"{key} r{k} {mod}: got TP/FP/FN {got}, hand-read {(tp, fp, fn)}")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE), help="output folder (default: next to this script)")
    a = ap.parse_args()
    refs = ea.load_refs()
    tuning, heldout, scored = build(refs)
    fails = self_test(refs, scored)
    n_checks = 3 + len(KNOWN) + len(HAND)
    if fails:
        print(f"SELF-TEST FAIL ({len(fails)} of {n_checks} checks). Nothing written.")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print(f"self-test PASS ({n_checks} checks)")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("convergence.csv", tuning), ("heldout.csv", heldout)):
        with open(out / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {out / name} ({len(rows)} rows)")
    unl = [r["version"] for r in tuning + heldout if r["stage"] == "UNLABELLED"]
    if unl:
        print("  [warn] folders with no metadata entry:", ", ".join(unl))


if __name__ == "__main__":
    main()
