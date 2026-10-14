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
            "v10r": {"run": "rule_isolation_v10r", "texts": "rule_texts_v10r.json", "ctx": ("context_p1_v10r.md", "context_p2_v10r.md")}}
VARIANT = "v9"


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


def system(phase: str) -> str:
    common = (LAB / "prompts" / V9 / "common.md").read_text(encoding="utf-8")
    ctx = (HERE / VARIANTS[VARIANT]["ctx"][0 if phase == "P1" else 1]).read_text(encoding="utf-8")
    label = "PHASE 1 STEPS (the rule under test belongs here)" if phase == "P1" else "PHASE 2 STEPS (the rule under test belongs to step 4)"
    return SYSTEM_HEAD + common + f"\n=== CONTEXT: {label} ===\n" + ctx


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
    if not isinstance(obj, dict) or not all(isinstance(obj.get(k), list) for k in ("barred", "spared", "unsure")):
        return ["schema: barred / spared / unsure lists missing"]
    names = {n for (_, n) in CH.closed_names(m)}
    return [f"{k}: {x.get('element')!r} is not a closed-set name" for k in ("barred", "spared", "unsure")
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
    rec = {"rule": rid, "phase": ph, "module": m, "rep": rep, "system sha": ss, "user sha": us, "usage": usage,
           "raw": text, "reply": obj, "problems": check(m, obj)}
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
