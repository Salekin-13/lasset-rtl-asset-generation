"""Rule-isolation diagnostics for two_phase_v9 (user request 2026-10-14): each rule applied ALONE to each of the 41
modules, in its Phase 1 wording and in its Phase 2 wording, two repeats, on the production model (gpt-5.6-luna, high).
The user sends the paid calls (notebook cell "Rule isolation"); this file builds the requests, previews and estimates
them, runs them through chain.openai (stored once, pending ids kept, stop-safe) and parses the replies.

Request (one per rule wording x module x repeat):
  system  = SYSTEM_HEAD + common.md (v9, full) + the phase context: phase1.md without its titled rule bullets except
            Precedence (P1 wordings), or phase2.md with every step-4/5 sentence mapped to a rule removed (P2 wordings);
            the OUTPUT sections are left out. One system text per phase, so it is identical across rules (cached).
  user    = the module's inputs exactly as the production user message gives them (RTL, closed set, diagram; v9
            template without its last line), then "RULE UNDER TEST" with the rule's text. The module part comes first so
            the cached prefix covers it across rules.
Reply (JSON): {"applies": "yes"|"no", "barred": [...], "spared": [...], "unsure": [...]}, each item {"element",
"entity", "rule words", "lines", "why"}; "barred" = closed-set elements the rule's bar covers in this module (for a
Phase 1 wording: the elements holding or carrying information the rule says is not a piece of its own), "spared" =
elements the rule's own "Judged as usual" / "Not covered" words keep although they look like the bar's case.

Files: rule_texts.json (built by build(), from pack/index.json and rule_map.json, the checked output of the
rule-mapping workflow), context_p1.md, context_p2.md. Runs: lab/runs/rule_isolation_v9/<model>__<effort>/r<rep>/
<P1|P2|...>/<rule id>/<module>.json.

  python isolation.py build            (writes rule_texts.json and the two contexts)
  python isolation.py preview [pilot]  (counts, sizes and a cost range; sends nothing)
  python isolation.py selftest         (stub executor: storing, resume, parsing; sends nothing)
"""
from __future__ import annotations

import json
import re
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402

V9 = "two_phase_v9"
PILOT = ["neorv32_wdt", "neorv32_cpu_icc"]
# Variants (2026-10-15): "v9" = the v9 rules (default); "v10r" = the rewritten critical rules (prompt_builds/v10, not yet
# assembled into a prompt), tested alone in the same format, with the shared "Reading a rule" procedure in the context.
VARIANTS = {"v9": {"run": "rule_isolation_v9", "texts": "rule_texts.json", "ctx": ("context_p1.md", "context_p2.md")},
            "v10r": {"run": "rule_isolation_v10r", "texts": "rule_texts_v10r.json", "ctx": ("context_p1_v10r.md", "context_p2_v10r.md")},
            # 2026-10-15: four over-applied rules rewritten facts-first (prompt_builds/v10f), tested in the facts reply format
            "v10f": {"run": "rule_isolation_v10f", "texts": "rule_texts_v10f.json", "ctx": ("context_p1_v10f.md", "context_p2_v10f.md"),
                     "facts": True},
            # 2026-10-15 (user: "apply" G2): Slices and Clocks and resets fixed (prompt_builds/v10f/C_final.json); the facts
            # format allows "an exception applies" only for a part the rule labels as an exception
            "v10f2": {"run": "rule_isolation_v10f2", "texts": "rule_texts_v10f2.json", "ctx": ("context_p1_v10f.md", "context_p2_v10f.md"),
                      "facts": True, "head": "facts2"},
            # 2026-10-15 (user "ok"): Slices only, with "never the whole element" and "concatenated (side by side, not
            # combined by a logic or arithmetic operator)" (prompt_builds/v10f/D_final.json); same format as v10f2
            "v10f3": {"run": "rule_isolation_v10f3", "texts": "rule_texts_v10f3.json", "ctx": ("context_p1_v10f.md", "context_p2_v10f.md"),
                      "facts": True, "head": "facts2"}}
# 2026-10-15 (user "implement"): v10f3 Slices without "(never the whole element)" (prompt_builds/v10f/E_final.json)
VARIANTS["v10f4"] = {"run": "rule_isolation_v10f4", "texts": "rule_texts_v10f4.json",
                     "ctx": ("context_p1_v10f.md", "context_p2_v10f.md"), "facts": True, "head": "facts2"}
# 2026-10-15 (user "do the clarity test"): the same variants on 6 neorv32 modules that no run, rule or fix has read and
# that have no reference entries (clarity only: no precision or recall). Same texts, contexts, format and max_tokens as
# the 41-module run of each variant; only the run folder differs ("__unseen6"), so the 41-module folders never mix.
# crc, dma, clint and cfs are read from lab/inputs/unseen6 (unseen6/build_maps.py + build_inputs.py); fifo and
# boot_rom from inputs/v1 (byte-identical in both). Call redirect_unseen_inputs() after any reload of chain.
UNSEEN6 = ["neorv32_cfs", "neorv32_clint", "neorv32_crc", "neorv32_dma", "neorv32_fifo", "neorv32_boot_rom"]
UNSEEN_NEW = UNSEEN6[:4]
UNSEEN_INPUTS = LAB / "inputs" / "unseen6"
for _v in ("v9", "v10r", "v10f", "v10f2", "v10f3", "v10f4"):
    VARIANTS[_v + "__unseen6"] = {**VARIANTS[_v], "run": VARIANTS[_v]["run"] + "__unseen6"}
# The run plan (notebook cell 16): (variant, rules, modules or None for the 41, max_tokens as in that variant's
# 41-module run: cell 11 used chain.openai's default 128000 for v9, cells 12-15 used 64000).
RULES17 = ["P1-02", "P1-04", "P1-05", "P1-06", "P1-07", "P1-08", "P1-09", "P1-10", "P1-14", "P1-15", "P1-16", "P1-17",
           "P1-18", "P1-22", "P1-23", "P1-24", "P1-27"]                 # the 17 rules re-tested since v9
LATEST = {"v10r": ["P1-04", "P1-05", "P1-06", "P1-07", "P1-08", "P1-10", "P1-14", "P1-16", "P1-17", "P1-22", "P1-23",
                   "P1-24", "P1-27"], "v10f": ["P1-15", "P1-18"], "v10f2": ["P1-02"], "v10f3": ["P1-09"]}
UNSEEN_PLAN = [("v10f4", ["P1-09"], None, 64000),
               ("v9__unseen6", RULES17, UNSEEN6, 128000)] + \
              [(v + "__unseen6", r, UNSEEN6, 64000) for v, r in LATEST.items()] + \
              [("v10f4__unseen6", ["P1-09"], UNSEEN6, 64000)]
# 2026-10-16 (user "do the g3 test"; decision G3, V10F_RESULTS.md): the four adopted facts-first wordings
# (prompt_builds/v10/current_rules.json) in the OLD reply format (SYSTEM_HEAD, as v9 and v10r). Texts (built by
# make_v10f_texts.py v10fo, equal to the texts each facts-format test read) and contexts (the v10f shared procedure) are
# those of the facts-format runs, so only the reply format differs. Read with read_g3.py.
VARIANTS["v10fo"] = {"run": "rule_isolation_v10fo", "texts": "rule_texts_v10fo.json",
                     "ctx": ("context_p1_v10f.md", "context_p2_v10f.md")}
G3_RULES = ["P1-02", "P1-09", "P1-15", "P1-18"]
G3_FACTS = {"P1-15": "v10f", "P1-18": "v10f", "P1-02": "v10f2", "P1-09": "v10f3"}    # where each was tested facts-first
# 2026-10-16 (user "Use the merged procedure. Build the E3 re-test of all 17 rules"): every rule with the text of its last
# old-format test (13 as v10r, 4 as v10fo; make_v10m_texts.py) and the merged procedure of prompt_builds/v10/make_v10.py
# in the context; old reply format. Read with read_e3.py.
VARIANTS["v10m"] = {"run": "rule_isolation_v10m", "texts": "rule_texts_v10m.json",
                    "ctx": ("context_p1_v10m.md", "context_p2_v10m.md")}
E3_LAST = {r: ("v10fo" if r in G3_RULES else "v10r") for r in RULES17}               # each rule's last old-format test
# 2026-10-16 (user: "test it here, as I do not have openai budget to cover the run"): E3 on a Claude executor
# (claude_e3.py). Both procedures run on Claude, so the two sides share one executor; never compare them with luna runs.
CLAUDE_EXEC = "claude-sonnet__agent-batched"
for _v in ("v10m", "v10r", "v10fo"):
    VARIANTS[_v + "__claude"] = {**VARIANTS[_v], "run": VARIANTS[_v]["run"] + "__claude", "executor": CLAUDE_EXEC}
# 2026-10-16 (user: "apply the E1 gloss fix to Buffer and engine status bits and test that rule alone first"): the
# fixed P1-17 (make_v10e1_texts.py) in v10's context; old side = "v10m" (current v10 text). Read with read_e1.py.
# On Claude, one rule per agent ("__claude1", claude_single.py), in its own executor folder (never with the batched E3).
VARIANTS["v10e1"] = {"run": "rule_isolation_v10e1", "texts": "rule_texts_v10e1.json",
                     "ctx": ("context_p1_v10m.md", "context_p2_v10m.md")}
CLAUDE1_EXEC = "claude-sonnet__agent-single"
for _v in ("v10m", "v10e1"):
    VARIANTS[_v + "__claude1"] = {**VARIANTS[_v], "run": VARIANTS[_v]["run"] + "__claude1", "executor": CLAUDE1_EXEC}
VARIANT = "v9"


def redirect_unseen_inputs():
    """chain.module_dir finds only inputs/<version>/{tuning,heldout}; send the 4 new modules to inputs/unseen6/unseen.
    Returns the original function (to restore). Idempotent."""
    orig = getattr(CH.module_dir, "_orig", CH.module_dir)

    def module_dir(m):
        if m in UNSEEN_NEW:
            d = UNSEEN_INPUTS / "unseen" / m
            if not (d / "rtl.txt").is_file():
                raise FileNotFoundError(f"{d}: run unseen6/build_maps.py and build_inputs.py first")
            return d
        return orig(m)
    module_dir._orig = orig
    CH.module_dir = module_dir
    return orig


def stored_requests_match(variant: str, rules=None, log=print) -> bool:
    """Gate before a comparison run: every stored 41-module record of `variant` (for `rules`, or all) is rebuilt
    exactly by the current texts, contexts and inputs (system and user sha). Sends nothing."""
    keep = VARIANT
    use(variant)
    try:
        texts = json.loads(texts_file().read_text(encoding="utf-8"))
        n = bad = 0
        sys_sha = {}
        for r in (0, 1):
            for f in run_root(rep=r).glob("P*/*/*.json"):
                rec = json.loads(f.read_text(encoding="utf-8"))
                if rules is not None and rec["rule"] not in rules:
                    continue
                ph = rec["phase"]
                if ph not in sys_sha:
                    sys_sha[ph] = CH.sha12(system(ph))
                n += 1
                bad += (rec.get("system sha"), rec.get("user sha")) != (sys_sha[ph], CH.sha12(user(rec["module"], rec["rule"], ph, texts)))
    finally:
        use(keep)
    log(f"   {variant}: {n - bad} of {n} stored requests rebuilt exactly")
    return n > 0 and bad == 0


def use(variant: str):
    """Switch the run folder, rule texts and contexts (every function below reads the current variant)."""
    global VARIANT
    if variant not in VARIANTS:
        raise ValueError(variant)
    VARIANT = variant


def texts_file() -> Path:
    return HERE / VARIANTS[VARIANT]["texts"]
SYSTEM_HEAD = """THIS CALL: ONE RULE, APPLIED ALONE

You are given one rule from a longer prompt that identifies security assets in RTL, and one design module. Apply only
that rule, exactly as written, to the module, and report what it decides. Do not apply any other rule of the longer
prompt; the definitions and steps below are context the rule refers to (section numbers such as 2.6, step names), not
rules to apply.

Task: list every closed-set element of the module that the rule's bar covers (for a Phase 1 rule: each element that
holds or carries information the rule says is not a conceptual asset or not a piece of its own; for a Phase 2 rule:
each element the rule says never qualifies or is not primary). Then, under "spared", list every element the rule keeps:
the elements its own exceptions ("Judged as usual", "Not covered", "unless", "except") keep when they otherwise look like
the bar's case, and, for a rule that makes elements primary or keeps information as a piece of its own, those elements.
List an element under "unsure" only when the rule's words can be read both ways for it, and say which words. Read the
RTL and the closed set to check each condition the rule states; cite RTL line numbers. If the rule covers nothing in
this module, return empty lists and "applies": "no".

Return one JSON object:
{"applies": "yes" | "no",
 "barred": [{"element": "<exact closed-set name>", "entity": "<entity>", "rule words": "<the rule's words that bar it>", "lines": [<RTL line numbers>], "why": "<one sentence>"}],
 "spared": [{"element": "...", "entity": "...", "rule words": "<the exception's words>", "lines": [...], "why": "..."}],
 "unsure": [{"element": "...", "entity": "...", "rule words": "<the words that can be read two ways>", "lines": [...], "why": "..."}]}
Follow this format strictly: these keys only, exact closed-set names.

=== CONTEXT: DEFINITIONS (common.md) ===
"""


def run_root(model="gpt-5.6-luna", effort="high", rep=0) -> Path:
    if VARIANTS[VARIANT].get("executor"):         # a variant run by another executor (claude_e3.py) keeps its own folder
        return LAB / "runs" / VARIANTS[VARIANT]["run"] / VARIANTS[VARIANT]["executor"] / f"r{rep}"
    return LAB / "runs" / VARIANTS[VARIANT]["run"] / f"{model}__{effort}" / f"r{rep}"


def build():
    idx = json.loads((HERE / "pack" / "index.json").read_text(encoding="utf-8"))
    rmap = json.loads((HERE / "rule_map.json").read_text(encoding="utf-8"))           # sentence id -> unit
    p1 = (LAB / "prompts" / V9 / "phase1.md").read_text(encoding="utf-8").split("\n")
    p2 = (LAB / "prompts" / V9 / "phase2.md").read_text(encoding="utf-8").split("\n")
    out1 = p1.index("OUTPUT")
    out2 = p2.index("OUTPUT")
    ctx1 = [l for l in p1[:out1] if not (re.match(r"- [A-Z][A-Za-z -]*\.", l) and not l.startswith("- Precedence."))]
    keep = {}
    for sid, x in idx["p2"].items():
        if rmap[sid]["unit"].startswith("general"):
            keep.setdefault(x["line"], []).append(x["text"])
    ctx2 = []
    for i, l in enumerate(p2[:out2], 1):
        if any(x["line"] == i for x in idx["p2"].values()):
            ctx2.append(" ".join(keep.get(i, [])))
        else:
            ctx2.append(l)
    texts = {}
    for rid, x in idx["p1"].items():
        if x["title"] == "Precedence":
            continue
        sents = [idx["p2"][s]["text"] for s in sorted(idx["p2"]) if rmap[s]["unit"].startswith(rid)]
        texts[rid] = {"title": x["title"], "P1": x["text"], "P2": " ".join(sents) or None}
    for s in sorted(idx["p2"]):
        u = rmap[s]["unit"]
        if u.startswith("P2-only"):
            rid = "P2X-" + re.sub(r"[^a-z0-9]+", "-", u.split(":", 1)[1].strip().lower()).strip("-")
            t = texts.setdefault(rid, {"title": u, "P1": None, "P2": ""})
            t["P2"] = (t["P2"] + " " + idx["p2"][s]["text"]).strip()
    extra = HERE / "rule_texts_extra.json"                                             # revised wordings under test
    if extra.exists():
        texts.update(json.loads(extra.read_text(encoding="utf-8")))
    (HERE / "rule_texts.json").write_text(json.dumps(texts, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "context_p1.md").write_text("\n".join(ctx1) + "\n", encoding="utf-8")
    (HERE / "context_p2.md").write_text("\n".join(ctx2) + "\n", encoding="utf-8")
    n1 = sum(1 for t in texts.values() if t.get("P1"))
    n2 = sum(1 for t in texts.values() if t.get("P2"))
    print(f"rule texts: {len(texts)} rules; {n1} Phase 1 wordings, {n2} Phase 2 wordings; contexts written")
    return texts


SYSTEM_HEAD_FACTS = """THIS CALL: ONE RULE, APPLIED ALONE

You are given one rule from a longer prompt that identifies security assets in RTL, and one design module. Apply only
that rule, exactly as written, to the module, and report what it decides. Do not apply any other rule of the longer
prompt; the definitions and steps below are context the rule refers to (section numbers such as 2.6, step names), not
rules to apply.

Task:
1. Unit: say what kind of unit this module is, as far as the rule's scope needs it, with the ports or lines that show it.
2. For every closed-set element the rule could decide in this module, write the facts BEFORE the decision: one entry per
   part of the rule (its scope, then each numbered criterion, then any exception it still lists), each with the fact read
   from the RTL or the closed set, its line numbers, and whether that part holds for the element. Where a part says
   "only", "every", "nothing but" or "one element", list every assignment or every use (from the RTL and the element's
   closed-set entry), not one. Then decide, following your own facts:
     "outcome applies"       the scope and every criterion hold (one, where marked "any of") and no exception applies;
     "an exception applies"  the scope and criteria hold, and an exception the rule lists applies;
     "outside the rule"      the scope or a criterion does not hold.
   For "outcome applies", quote the Outcome words that apply and give their effect on this element: "bars" (not a piece
   of its own, not a conceptual asset, never primary) or "keeps" (its own piece, or primary).
3. List an element under "unsure" only when the rule's words can be read both ways for it, and say which words.
If the rule decides nothing in this module, return "applies": "no" and empty lists.

Return one JSON object:
{"applies": "yes" | "no",
 "unit": {"kind": "<what the scope needs to know>", "lines": [<RTL line numbers>]},
 "decisions": [{"element": "<exact closed-set name>", "entity": "<entity>",
                "facts": [{"part": "<scope | criterion (1) | ... | exception>", "fact": "<one sentence>", "lines": [<RTL line numbers>], "holds": true | false}],
                "decision": "outcome applies" | "an exception applies" | "outside the rule",
                "rule words": "<the rule's words that decide it>", "effect": "bars" | "keeps" | "none", "why": "<one sentence>"}],
 "unsure": [{"element": "...", "entity": "...", "rule words": "<the words that can be read two ways>", "lines": [...], "why": "..."}]}
Follow this format strictly: these keys only, exact closed-set names.

=== CONTEXT: DEFINITIONS (common.md) ===
"""


SYSTEM_HEAD_FACTS2 = SYSTEM_HEAD_FACTS.replace(
    '     "an exception applies"  the scope and criteria hold, and an exception the rule lists applies;',
    '     "an exception applies"  the scope and criteria hold, and a part the rule labels "Exceptions" applies (a rule\n'
    '                             with no Exceptions slot has none: a carve-out inside a criterion, such as "apart from ..."\n'
    '                             or "leaving out ...", is part of that criterion);')
assert SYSTEM_HEAD_FACTS2 != SYSTEM_HEAD_FACTS


def facts_variant() -> bool:
    return bool(VARIANTS[VARIANT].get("facts"))


def from_facts(obj) -> dict:
    """The facts reply mapped to the barred / spared / unsure lists the analysis scripts read: barred = the outcome
    applies and bars it; spared = an exception applies, or the outcome applies and keeps it; "outside the rule" is in
    neither (as a signal the v9 format did not list)."""
    if not isinstance(obj, dict) or not isinstance(obj.get("decisions"), list):
        return None
    out = {"applies": obj.get("applies"), "barred": [], "spared": [], "unsure": obj.get("unsure") or []}
    for d in obj["decisions"]:
        if not isinstance(d, dict):
            continue
        item = {k: d.get(k) for k in ("element", "entity", "rule words", "why")}
        item["lines"] = sorted({n for f in d.get("facts") or [] if isinstance(f, dict)
                                for n in (f.get("lines") or []) if isinstance(n, int)})
        # 2026-10-15: "outcome applies" with effect "none" (a slip in the effect field; 9 of about 1,600 such decisions in
        # v10f and v10f2) counts as barred: the rules tested in this format bar unless the reply says the outcome keeps
        if d.get("decision") == "outcome applies" and d.get("effect") != "keeps":
            out["barred"].append(item)
        elif d.get("decision") == "an exception applies" or (d.get("decision") == "outcome applies" and d.get("effect") == "keeps"):
            out["spared"].append(item)
    return out


def against_facts(obj) -> int:
    """Instrument (measures, changes nothing): decisions whose verdict contradicts the reply's own facts, i.e. "outcome
    applies" with a scope or criterion part marked false, or "outside the rule" with every scope and criterion part true."""
    n = 0
    for d in (obj or {}).get("decisions") or []:
        if not isinstance(d, dict):
            continue
        parts = [f for f in d.get("facts") or [] if isinstance(f, dict) and not str(f.get("part", "")).lower().startswith("exception")]
        if not parts:
            continue
        anys = [f for f in parts if "any" in str(f.get("part", "")).lower()]     # "any of": one holding is enough
        alls = [f for f in parts if f not in anys]
        allhold = all(f.get("holds") is True for f in alls) and (not anys or any(f.get("holds") is True for f in anys))
        n += (d.get("decision") == "outcome applies" and not allhold) or (d.get("decision") == "outside the rule" and allhold)
    return n


def system(phase: str) -> str:
    common = (LAB / "prompts" / V9 / "common.md").read_text(encoding="utf-8")
    ctx = (HERE / VARIANTS[VARIANT]["ctx"][0 if phase == "P1" else 1]).read_text(encoding="utf-8")
    label = "PHASE 1 STEPS (the rule under test belongs here)" if phase == "P1" else "PHASE 2 STEPS (the rule under test belongs to step 4)"
    head = (SYSTEM_HEAD_FACTS2 if VARIANTS[VARIANT].get("head") == "facts2" else SYSTEM_HEAD_FACTS) if facts_variant() else SYSTEM_HEAD
    return head + common + f"\n=== CONTEXT: {label} ===\n" + ctx


def user(m: str, rule_id: str, phase: str, texts: dict) -> str:
    base = CH.user_message(V9, 1, m)
    base = base[:base.rindex("\nDo Phase 1")]
    t = texts[rule_id]
    return (base + f"\n\n=== RULE UNDER TEST ({'Phase 1' if phase == 'P1' else 'Phase 2'} wording; rule: {t['title']}) ===\n"
            + t[phase] + f"\n\nApply only this rule to module '{m}' and return the JSON object.")


def jobs(modules=None, reps=(0, 1), rules=None, phases=("P1", "P2")):
    texts = json.loads(texts_file().read_text(encoding="utf-8"))
    mods = modules or (K.gt_modules()["tuning"] + K.gt_modules()["heldout"])
    out = []
    for m in mods:                                   # module-major: requests sharing a cached prefix go together
        for ph in phases:
            for rid, t in texts.items():
                if (rules is None or rid in rules) and t.get(ph):
                    for r in reps:
                        out.append((rid, ph, m, r))
    return out, texts


def path(rid, ph, m, rep, model="gpt-5.6-luna", effort="high") -> Path:
    return run_root(model, effort, rep) / ph / rid / f"{m}.json"


def check(m: str, obj) -> list[str]:
    if facts_variant() and not (isinstance(obj, dict) and "barred" in obj):
        if not isinstance(obj, dict) or not isinstance(obj.get("decisions"), list) or not isinstance(obj.get("unsure", []), list):
            return ["schema: decisions / unsure lists missing"]
        names = {n for (_, n) in CH.closed_names(m)}
        bad = [f"decisions: {(d.get('element') if isinstance(d, dict) else d)!r} is not a closed-set name" for d in obj["decisions"]
               if not isinstance(d, dict) or d.get("element") not in names]
        bad += [f"decisions: {d.get('element')!r} has decision {d.get('decision')!r}" for d in obj["decisions"] if isinstance(d, dict)
                and d.get("decision") not in ("outcome applies", "an exception applies", "outside the rule")]
        bad += [f"unsure: {(x.get('element') if isinstance(x, dict) else x)!r} is not a closed-set name" for x in obj.get("unsure") or []
                if not isinstance(x, dict) or x.get("element") not in names]
        return bad
    if not isinstance(obj, dict) or not all(isinstance(obj.get(k), list) for k in ("barred", "spared", "unsure")):
        return ["schema: barred / spared / unsure lists missing"]
    names = {n for (_, n) in CH.closed_names(m)}
    return [f"{k}: {(x.get('element') if isinstance(x, dict) else x)!r} is not a closed-set name" for k in ("barred", "spared", "unsure")
            for x in obj[k] if not isinstance(x, dict) or x.get("element") not in names]


def ask(call, rid, ph, m, rep, texts, model, effort) -> str:
    p = path(rid, ph, m, rep, model, effort)
    sysm, usr = system(ph), user(m, rid, ph, texts)
    ss, us = CH.sha12(sysm), CH.sha12(usr)
    if p.exists():
        rec = json.loads(p.read_text(encoding="utf-8"))
        if (rec.get("system sha"), rec.get("user sha")) != (ss, us):
            raise RuntimeError(f"{p} was asked with another message; delete it or use another run folder")
        return "stored"
    text, usage = call(sysm, usr)
    obj = K.parse_json(text) if text else None
    try:                                            # a paid reply is stored even if its check crashes
        problems = check(m, obj)
    except Exception as e:
        problems = [f"check crashed: {e}"[:300]]
    rec = {"rule": rid, "phase": ph, "module": m, "rep": rep, "system sha": ss, "user sha": us, "usage": usage,
           "raw": text, "reply": obj, "problems": problems}
    if facts_variant():                             # the analysis scripts read barred / spared / unsure lists
        rec["facts reply"], rec["reply"] = obj, from_facts(obj)
        rec["verdicts against own facts"] = against_facts(obj)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    if hasattr(call, "done"):
        call.done(CH.sha12(sysm + "\n\n" + usr))
    return "sent"


def run(job_list, texts, make_call, model="gpt-5.6-luna", effort="high", workers=24, log=print) -> dict:
    """make_call(out_folder) -> executor (notebook: lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5)). One executor
    per repeat folder (pending ids live there). Stop-safe like chain.run_many."""
    from concurrent.futures import ThreadPoolExecutor, wait
    stop = CH._new_run_flag()
    calls = {}
    for r in sorted({j[3] for j in job_list}):
        run_root(model, effort, r).mkdir(parents=True, exist_ok=True)
        calls[r] = make_call(run_root(model, effort, r))
    res = {}

    def one(j):
        threading.current_thread().lab_stop = stop
        try:
            return ask(calls[j[3]], *j, texts, model, effort)
        except Exception as e:                     # a failed call is reported, the others go on
            return f"error: {e}"[:300]
    pool = ThreadPoolExecutor(max_workers=max(1, workers))
    futs = {}
    try:
        for j in job_list:
            futs[j] = pool.submit(one, j)
        pending = set(futs.values())
        while pending:
            _, pending = wait(pending, timeout=1)
    except BaseException:
        CH._stop_pool(stop, pool, list(futs.values()), log)
        raise
    pool.shutdown(wait=True)
    for j, f in futs.items():
        res[j] = f.result()
    from collections import Counter
    c = Counter(v.split(":")[0] for v in res.values())
    log(f"rule isolation: {dict(c)}")
    for j, v in res.items():
        if v.startswith("error"):
            log(f"  {j}: {v}")
    return res


def preview(job_list, texts, model="gpt-5.6-luna", effort="high", log=print) -> dict:
    """Counts and sizes (nothing is sent). Input tokens by the o200k pre-token floor (cost_estimate.pretokens) times its
    calibration ratio; output tokens are not known before a run, so the cost is given for 2,000 / 5,000 / 10,000
    output tokens per call (reasoning included). The cached share assumes the system text and the module part are
    cached after the first request of each (phase, module, repeat)."""
    import cost_estimate as CE
    import check_lab_prompt as C
    stored = sum(1 for j in job_list if path(*j, model, effort).exists())
    # calibration on this repository's own v9 Phase 1 calls: billed input tokens / pre-token floor of the same messages
    cal = []
    for m in ("neorv32_wdt", "neorv32_cpu_icc", "neorv32_xbus"):
        u = json.loads((CH.run_dir(V9, "gpt-5.6-luna", 0, "high") / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["usage"]["in"]
        cal.append(u / (CE.pretokens(C.system(V9, 1)) + CE.pretokens(CH.user_message(V9, 1, m))))
    ratio = sum(cal) / len(cal)
    sizes = {}
    tot_in = cached = 0
    seen = set()
    for (rid, ph, m, r) in job_list:
        if path(rid, ph, m, r, model, effort).exists():
            continue
        if (ph, m) not in sizes:
            s = CE.pretokens(system(ph)) * ratio
            u = CE.pretokens(user(m, rid, ph, texts)) * ratio
            sizes[(ph, m)] = (s, u)
        s, u = sizes[(ph, m)]
        n = s + u
        tot_in += n
        if (ph, m, r) in seen:
            cached += s + u * 0.9                      # all but the rule text, roughly
        seen.add((ph, m, r))
    P = CE.PRICES[model]
    to_send = len(job_list) - stored
    usd_in = ((tot_in - cached) * P["in"] + cached * P["cached"]) / 1e6
    est = {o: round(usd_in + to_send * o * P["out"] / 1e6, 2) for o in (2000, 5000, 10000)}
    log(f"rule isolation: {len(job_list)} requests ({stored} stored, {to_send} to send); input about {tot_in / 1e6:.1f}M tokens "
        f"({cached / 1e6:.1f}M cached); USD {usd_in:.2f} input; total USD {est[2000]} / {est[5000]} / {est[10000]} "
        f"at 2k / 5k / 10k output tokens per call")
    return {"requests": len(job_list), "to send": to_send, "input tokens": int(tot_in), "usd by output per call": est}


def measured(job_list, model="gpt-5.6-luna", effort="high", log=print) -> dict:
    """From the stored replies (e.g. the pilot): mean billed input, cached input and output tokens per call, the cost
    so far, and the cost of the requests in job_list not stored yet at those means."""
    import cost_estimate as CE
    P = CE.PRICES[model]
    us = []
    for r in (0, 1):
        for f in run_root(model, effort, r).glob("*/*/*.json"):
            u = json.loads(f.read_text(encoding="utf-8")).get("usage") or {}
            if u.get("in") is not None:
                us.append(u)
    if not us:
        log("no stored replies")
        return {}
    n = len(us)
    mi, mc, mo = (sum(u.get(k) or 0 for u in us) / n for k in ("in", "cached", "out"))
    cost = lambda i, c, o: ((i - c) * P["in"] + c * P["cached"] + o * P["out"]) / 1e6  # noqa: E731
    spent = sum(cost(u["in"], u.get("cached") or 0, u.get("out") or 0) for u in us)
    left = sum(1 for j in job_list if not path(*j, model, effort).exists())
    est = left * cost(mi, mc, mo)
    log(f"stored {n} replies: mean input {mi:,.0f} tokens ({mc:,.0f} cached), output {mo:,.0f}; spent USD {spent:.2f}; "
        f"{left} requests left, about USD {est:.2f} at these means")
    return {"stored": n, "mean in": mi, "mean cached": mc, "mean out": mo, "spent usd": spent, "left": left, "left usd": est}


def selftest(log=print) -> bool:
    """Stub executor on one tiny job list in a scratch run folder: a reply is stored once and parsed; a re-run sends
    nothing; a reply naming a non-closed-set element is flagged. Sends nothing to any API."""
    import shutil
    texts = json.loads(texts_file().read_text(encoding="utf-8"))
    rid = next(iter(texts))
    m = "neorv32_wdt"
    name = sorted(n for (_, n) in CH.closed_names(m))[0]
    sent = []

    def stub(s, u):
        sent.append(1)
        return json.dumps({"applies": "yes", "barred": [{"element": name, "entity": "x", "rule words": "w", "lines": [1], "why": "y"}],
                           "spared": [], "unsure": [{"element": "no_such_element", "entity": "x", "rule words": "w", "lines": [], "why": "y"}]}), {"in": 1, "out": 1}
    model, effort = "stub-model", "test"
    root = LAB / "runs" / VARIANTS[VARIANT]["run"] / f"{model}__{effort}"
    shutil.rmtree(root, ignore_errors=True)
    jl = [(rid, "P1", m, 0)]
    r1 = run(jl, texts, lambda out: stub, model, effort, workers=1, log=lambda *a: None)
    r2 = run(jl, texts, lambda out: stub, model, effort, workers=1, log=lambda *a: None)
    rec = json.loads(path(rid, "P1", m, 0, model, effort).read_text(encoding="utf-8"))
    ok = (r1[jl[0]] == "sent" and r2[jl[0]] == "stored" and len(sent) == 1 and rec["reply"]["barred"][0]["element"] == name
          and any("no_such_element" in p for p in rec["problems"]) and len(rec["problems"]) == 1
          and system("P1") != system("P2") and texts[rid]["P1"] in user(m, rid, "P1", texts))
    shutil.rmtree(root, ignore_errors=True)
    log(f"isolation self-test (stub: stored once, resumed without sending, parsed, bad name flagged): {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if cmd == "build":
        build()
    elif cmd == "selftest":
        sys.exit(0 if selftest() else 1)
    else:
        mods = PILOT if "pilot" in sys.argv else None
        jl, tx = jobs(mods, reps=(0,) if "pilot" in sys.argv else (0, 1))
        preview(jl, tx)
