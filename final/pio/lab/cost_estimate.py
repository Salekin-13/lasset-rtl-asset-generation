"""Cost estimate for a two-phase lab prompt on the 15 test modules, calibrated on a measured gpt-5.4 run.

  python final/pio/lab/cost_estimate.py two_phase_v1

Input tokens. No tokenizer is installed. The input is split with the first stage of the o200k tokenizer (its
pre-token pattern, run with the `regex` package): every pre-token becomes one or more tokens, so the pre-token count is
a floor. The estimate is that count times the ratio billed tokens / pre-tokens measured on the one run whose exact
inputs and billed input tokens are known: the final prompt on gpt-5.4, held-out run r0 (26 calls; system prompt
assetgen_meta/prompt_opt/v1/exec_prompt.txt, sha12 802ee9a90d41; user messages
assetgen_meta/traced_inputs_v2/heldout/<module>.txt; billed tokens from runs/assets_heldout26_m7e194es0opt1_g54_r0/
_usage.json in the main checkout).

Output tokens cannot be counted before a run. The only measured figure is BORROWED: output tokens per call (reasoning
included) of the final prompt's three held-out gpt-5.4 runs. This prompt's Phase 2 asks for a much longer JSON reply,
so the borrowed figure is likely low for Phase 2, and nothing is measured for gpt-5-mini. A pilot on two modules gives
measured figures (pilot()).

Prices (USD per 1M tokens, standard tier, read from developers.openai.com/api/docs/pricing on 2026-10-11):
gpt-5.4 2.50 input / 0.25 cached input / 15.00 output; above 272K input tokens 5.00 / 0.50 / 22.50.
gpt-5-mini 0.25 / 0.025 / 2.00.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import regex

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[2]
MAIN = ROOT.parents[2] if (ROOT.parents[2] / "runs").exists() else ROOT   # the measured runs live in the main checkout
for p in (LAB, LAB.parent, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PRICES = {"gpt-5.4": {"in": 2.50, "cached": 0.25, "out": 15.00, "long_above": 272_000},
          "gpt-5-mini": {"in": 0.25, "cached": 0.025, "out": 2.00},
          # developers.openai.com/api/docs/pricing and the model pages, read 2026-10-11. gpt-5.4-mini: max input 272K.
          # gpt-5.6-luna: above 272K input, 2x input and 1.5x output for the whole request (no call here comes near it).
          "gpt-5.4-mini": {"in": 0.75, "cached": 0.075, "out": 4.50},
          "gpt-5.6-luna": {"in": 0.20, "cached": 0.02, "out": 1.20, "long_above": 272_000}}
# the o200k pre-token pattern (tiktoken, o200k_base)
O200K = regex.compile("|".join([
    r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]*[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
    r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]+[\p{Ll}\p{Lm}\p{Lo}\p{M}]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
    r"""\p{N}{1,3}""",
    r""" ?[^\s\p{L}\p{N}]+[\r\n/]*""",
    r"""\s*[\r\n]+""",
    r"""\s+(?!\S)""",
    r"""\s+""",
]))


def pretokens(t: str) -> int:
    return sum(1 for _ in O200K.finditer(t))


def fake_concepts(n_chars: int) -> str:
    """A stand-in Phase 1 list of about n_chars characters, written like a real one (indented JSON, short English
    sentences, names and line numbers)."""
    one = {"id": "C1", "unit": "unit_entity", "concept": "stored timeout setting",
           "information": "The timeout value that software writes over the bus; the counter compares against it to decide when the reset fires.",
           "rubric": {"confidentiality": "no", "integrity": "yes", "availability": "yes", "undermined expected behavior": "no"},
           "rubric reason": "It must stay unchanged while the counter runs (lines 94, 131); clearing it stops the reset (line 144).",
           "objectives": ["I", "A"], "attack": "A bus write while unlocked shortens the timeout and forces a reset.",
           "enters through": ["bus_req_i.data"], "leaves through": ["bus_rsp_o.data"],
           "entry lines": [94], "held lines": [94, 97], "exit lines": [109]}
    out, k = [], 0
    while len(json.dumps(out, indent=1)) < n_chars:
        k += 1
        out.append({**one, "id": f"C{k}"})
    return json.dumps(out, indent=1)


def calibration() -> dict:
    system = (ROOT / "assetgen_meta/prompt_opt/v1/exec_prompt.txt").read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert hashlib.sha256(system.encode()).hexdigest()[:12] == "802ee9a90d41", "system prompt is not the measured one"
    users = sorted((ROOT / "assetgen_meta/traced_inputs_v2/heldout").glob("*.txt"))
    assert len(users) == 26, len(users)
    usage = json.loads((MAIN / "runs/assets_heldout26_m7e194es0opt1_g54_r0/_usage.json").read_text(encoding="utf-8"))
    assert usage["calls"] == 26 and usage["model"] == "gpt-5.4"
    pt = 26 * pretokens(system) + sum(pretokens(u.read_text(encoding="utf-8")) for u in users)
    outs = []
    for r in range(3):
        u = json.loads((MAIN / f"runs/assets_heldout26_m7e194es0opt1_g54_r{r}/_usage.json").read_text(encoding="utf-8"))
        outs.append(u["output_tokens"] / u["calls"])
    return {"input_tokens": usage["input_tokens"], "pretokens": pt, "ratio": usage["input_tokens"] / pt,
            "out_per_call": outs}


def estimate(version: str = "two_phase_v1", modules=None, concepts_chars: int = 20000, log=print) -> dict:
    """concepts_chars: size of the Phase 1 list passed to Phase 2. A hand dry run of wdt gave 9,026 characters for 10
    concepts; 20,000 is taken to cover larger modules."""
    import check_lab_prompt as C
    import chain as CH
    cal = calibration()
    modules = list(modules or CH.tuning_modules())
    if not modules:
        raise ValueError("no modules: the reference list was not found")
    log(f"calibration (measured gpt-5.4 run, 26 calls): {cal['input_tokens']:,} billed input tokens for "
        f"{cal['pretokens']:,} pre-tokens, ratio {cal['ratio']:.4f}")
    s = {k: C.system(version, k) for k in (1, 2)}
    sys_pt = {k: pretokens(v) for k, v in s.items()}
    floor = largest = 0
    for m in modules:
        for k, u in ((1, CH.user_message(version, 1, m)), (2, CH.user_message(version, 2, m, concepts=fake_concepts(concepts_chars)))):
            pt = sys_pt[k] + pretokens(u)
            floor += pt
            largest = max(largest, pt * cal["ratio"])
    n = 2 * len(modules)
    tin = floor * cal["ratio"]
    sys_tok = len(modules) * (sys_pt[1] + sys_pt[2]) * cal["ratio"]
    cached = sys_tok - (sys_pt[1] + sys_pt[2]) * cal["ratio"]       # every call after the first of each phase
    log(f"calls: {n} ({len(modules)} modules x 2 phases); input tokens: floor {floor:,}, estimate {tin:,.0f} "
        f"(of which repeated system prompt {sys_tok:,.0f}); largest call {largest:,.0f} "
        f"({'below' if largest < PRICES['gpt-5.4']['long_above'] else 'ABOVE'} the 272,000 long-context line)")
    anchor = sum(cal["out_per_call"]) / 3
    per_out = {"half the lowest of the 3 borrowed runs": 0.5 * min(cal["out_per_call"]),
               "mean of the 3 borrowed runs (final prompt)": anchor,
               "twice the highest of the 3 borrowed runs": 2 * max(cal["out_per_call"])}
    res = {}
    for model, p in PRICES.items():
        note = "" if model == "gpt-5.4" else "  [output borrowed from gpt-5.4; not measured for this model]"
        for label, o in per_out.items():
            tout = o * n
            hi = (tin * p["in"] + tout * p["out"]) / 1e6
            lo = ((tin - cached) * p["in"] + cached * p["cached"] + tout * p["out"]) / 1e6
            res[(model, label)] = (lo, hi, tout)
            log(f"  {model:10s} output {label:40s} {tout:>9,.0f} tokens -> USD {lo:6.2f} (cache) to {hi:6.2f} (no cache){note}")
    log("  The borrowed output figure is likely low for Phase 2, whose reply lists every point and structural asset; "
        "pilot two modules to measure it (pilot()).")
    return {"calibration": cal, "input estimate": tin, "input floor": floor, "largest call": largest, "usd": res}


def pilot(version: str, model: str, rep: int = 0, effort: str = "high", modules=("neorv32_wdt", "neorv32_bus")) -> dict:
    """After a pilot run of a few modules: input and output tokens by phase, of stored replies and of failed calls."""
    import chain as CH
    out = CH.run_dir(version, model, rep, effort)
    rows = {}
    failed = CH.failed_calls(out, modules)
    for ph in (1, 2):
        us = [json.loads((out / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8")).get("usage") or {}
              for m in modules if (out / f"phase{ph}" / f"{m}.json").exists()]
        fu = [x.get("usage") or {} for x in failed if x.get("phase") == ph]
        rows[ph] = {"stored calls": len(us), "in": sum(u.get("in", 0) or 0 for u in us),
                    "out": sum(u.get("out", 0) or 0 for u in us), "failed calls": len(fu),
                    "failed in": sum(u.get("in", 0) or 0 for u in fu), "failed out": sum(u.get("out", 0) or 0 for u in fu)}
    return rows


def usd(u: dict, model: str = "gpt-5.4") -> float:
    """Cost of one call from its stored usage: uncached input, cached input and output (reasoning included)."""
    p = PRICES[model]
    i, c, o = u.get("in", 0) or 0, u.get("cached", 0) or 0, u.get("out", 0) or 0
    return ((i - c) * p["in"] + c * p["cached"] + o * p["out"]) / 1e6


def reestimate(version: str, model: str = "gpt-5.4", rep: int = 0, effort: str = "high",
               pilot_modules=("neorv32_wdt", "neorv32_bus"), modules=None, concepts_chars: int = 20000, log=print) -> dict:
    """After the pilot: what it cost (stored replies and failed calls), and the full-run estimate redone with the
    pilot's measured output. Two ways to carry the pilot's output over to the other modules, both shown: (a) its mean
    output per call, per phase; (b) its output per input token, per phase, applied to each module's input estimate."""
    import check_lab_prompt as C
    import chain as CH
    out = CH.run_dir(version, model, rep, effort)
    cal = calibration()
    spent, per = 0.0, {1: {"in": 0, "out": 0, "calls": 0}, 2: {"in": 0, "out": 0, "calls": 0}}
    for ph in (1, 2):
        for m in pilot_modules:
            f = out / f"phase{ph}" / f"{m}.json"
            if f.exists():
                u = json.loads(f.read_text(encoding="utf-8")).get("usage") or {}
                spent += usd(u, model)
                per[ph]["in"] += u.get("in", 0) or 0
                per[ph]["out"] += u.get("out", 0) or 0
                per[ph]["calls"] += 1
    failed = CH.failed_calls(out, list(pilot_modules))
    spent_failed = sum(usd(x.get("usage") or {}, model) for x in failed)
    log(f"pilot ({', '.join(pilot_modules)}): stored calls phase 1 {per[1]['calls']}, phase 2 {per[2]['calls']}; "
        f"failed calls {len(failed)}; USD spent {spent + spent_failed:.2f} (stored {spent:.2f}, failed {spent_failed:.2f})")
    for ph in (1, 2):
        if per[ph]["calls"]:
            log(f"  phase {ph}: output per call {per[ph]['out'] / per[ph]['calls']:,.0f} tokens, "
                f"output per input token {per[ph]['out'] / max(1, per[ph]['in']):.3f}")
    if not (per[1]["calls"] and per[2]["calls"]):
        log("  the pilot has no stored reply for one of the phases: no re-estimate")
        return {"spent": spent + spent_failed, "per phase": per}
    modules = list(modules or CH.tuning_modules())
    done = [m for m in modules if all((out / f"phase{k}" / f"{m}.json").exists() for k in (1, 2))]
    todo = [m for m in modules if m not in done]
    s = {k: C.system(version, k) for k in (1, 2)}
    a_out = b_out = tin = 0.0
    for m in todo:
        for ph, u in ((1, CH.user_message(version, 1, m)), (2, CH.user_message(version, 2, m, concepts=fake_concepts(concepts_chars)))):
            i = (pretokens(s[ph]) + pretokens(u)) * cal["ratio"]
            tin += i
            a_out += per[ph]["out"] / per[ph]["calls"]
            b_out += i * per[ph]["out"] / max(1, per[ph]["in"])
    p = PRICES[model]
    res = {"spent": spent + spent_failed, "per phase": per}
    log(f"  still to pay: {len(todo)} of {len(modules)} modules ({len(done)} have both replies stored and are not paid again)")
    for label, o in (("(a) mean output per call", a_out), ("(b) output per input token", b_out)):
        cost = (tin * p["in"] + o * p["out"]) / 1e6
        res[label] = cost
        log(f"  remaining {len(todo)} modules, {label}: output {o:,.0f} tokens, input {tin:,.0f} -> USD {cost:.2f} "
            f"(no cache); with what is spent, the full run totals USD {cost + spent + spent_failed:.2f}")
    return res


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    estimate(sys.argv[1] if len(sys.argv) > 1 else "two_phase_v1")
