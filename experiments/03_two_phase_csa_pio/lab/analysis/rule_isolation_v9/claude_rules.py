"""One rule, one module per Claude agent, for any texts variant (generalizes claude_single.py; user 2026-10-17: "test the
rule on the modules in isolation ... improve it where needed"; no OpenAI budget is spent). Same request as the OpenAI
isolation test (isolation.system + isolation.user, old reply format), rendered for the agents' Read tool
(claude_e3.render), one agent per (side, rule, phase, module, repeat). Sends nothing to any API.

Plan (PLAN below, set 2026-10-17 before any agent ran): per rule the phases tested and the modules (its intended cases'
modules plus must-spare / must-bar modules; neorv32_bus and the two largest control-unit requests kept out where the
rule has smaller targets). Sides: "new" = rule_texts_v9k.json (five new rules N21-N25 and three revised rules); "old" =
rule_texts_v9k_old.json (the v11r3 texts of the three revised rules, the texts inside two_phase_v9f). Context: v10's
core with the merged "Reading a rule" procedure (context_p1_v10m.md / context_p2_v10m.md), which equals v9f's core.
Agents: general-purpose subagents, model sonnet, the fixed prompt claude_e3.PROMPT. Audit: claude_e3.audit(folder,
root=ROOT). Records go to the variants v9k__claude1 / v9k_old__claude1 (isolation.CLAUDE1_EXEC), in isolation.ask's
record shape, so read_v9k.py reads them like any variant.

  python -B claude_rules.py build            (request files + manifest; checks the two sides differ only in the rule text)
  python -B claude_rules.py jobs             (JSON list of {name, req, out, prompt} for the requests without a reply)
  python -B claude_rules.py prompt <name>
  python -B claude_rules.py audit <subagents folder>
  python -B claude_rules.py collect
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402
import claude_e3 as CE3  # noqa: E402

import os
NEW_RULES = HERE.parents[0] / "v10_diagnosis" / "new_rules"
VARIANT = os.environ.get("V9K_VARIANT", "v9k")          # "v9k" (round 1) or "v9k2" (the revision round)
ROOT = ISO.LAB / "runs" / f"{VARIANT}_claude"
REQ, REP = ROOT / "requests", ROOT / "replies"
CTX = (str(HERE / "context_p1_v10m.md"), str(HERE / "context_p2_v10m.md"))
for _v in ("v9k", "v9k2"):
    ISO.VARIANTS[_v] = {"run": f"rule_isolation_{_v}", "texts": str(NEW_RULES / f"rule_texts_{_v}.json"), "ctx": CTX}
ISO.VARIANTS["v9k_old"] = {"run": "rule_isolation_v9k_old", "texts": str(NEW_RULES / "rule_texts_v9k_old.json"), "ctx": CTX}
for _v in ("v9k", "v9k2", "v9k_old"):
    ISO.VARIANTS[_v + "__claude1"] = {**ISO.VARIANTS[_v], "run": ISO.VARIANTS[_v]["run"] + "__claude1", "executor": ISO.CLAUDE1_EXEC}
SIDES = {"new": VARIANT, "old": "v9k_old"}
STORE = {"new": VARIANT + "__claude1", "old": "v9k_old__claude1"}
REPS = (0, 1)
PLAN = {
    "N21": {"phases": ["P1", "P2"], "modules": ["neorv32_cpu_alu", "neorv32_cpu_regfile", "neorv32_cpu_cp_cond", "neorv32_cpu_lsu", "neorv32_cpu_frontend"]},
    "N22": {"phases": ["P1", "P2"], "modules": ["neorv32_cpu_cp_fpu", "neorv32_cpu_icc", "neorv32_debug_auth", "neorv32_cpu_cp_cfu", "neorv32_pwm"]},
    "N23": {"phases": ["P1", "P2"], "modules": ["neorv32_cpu_counters", "neorv32_cpu_regfile", "neorv32_pwm", "neorv32_hwspinlock", "neorv32_cpu_alu"]},
    "N24": {"phases": ["P2"], "modules": ["neorv32_debug_dm", "neorv32_slink", "neorv32_cpu_lsu", "neorv32_gpio", "neorv32_xbus"]},
    "N25": {"phases": ["P1", "P2"], "modules": ["neorv32_cpu_cp_shifter", "neorv32_cpu_cp_muldiv", "neorv32_cpu_cp_bitmanip", "neorv32_cpu_cp_crypto"]},
    "P1-04": {"phases": ["P1", "P2"], "modules": ["neorv32_cpu_control", "neorv32_cpu_counters", "neorv32_pwm", "neorv32_spi"], "old": True},
    "P1-14": {"phases": ["P1", "P2"], "modules": ["neorv32_slink", "neorv32_cpu_frontend", "neorv32_cpu_icc", "neorv32_uart"], "old": True},
    "P1-15": {"phases": ["P1", "P2"], "modules": ["neorv32_debug_dm", "neorv32_cpu_cp_shifter", "neorv32_uart", "neorv32_spi"], "old": True},
}
# the revision round (make_v9k2_texts.py): the revised wordings on their modules; cpu_cp_fpu and cpu_cp_cfu are left out of
# N22's round 2 (their requests are the largest; the change touches read strobes only, which they have none of)
PLAN2 = {
    "N21": {"phases": ["P1"], "modules": PLAN["N21"]["modules"]},
    "N22": {"phases": ["P1", "P2"], "modules": ["neorv32_cpu_icc", "neorv32_debug_auth", "neorv32_pwm"]},
    "N24": {"phases": ["P2"], "modules": PLAN["N24"]["modules"]},
    "N25": {"phases": ["P1", "P2"], "modules": PLAN["N25"]["modules"]},
}
if VARIANT == "v9k2":
    PLAN = PLAN2


def request(side, rid, ph, m):
    ISO.use(SIDES[side])
    try:
        tx = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
        s, u = ISO.system(ph), ISO.user(m, rid, ph, tx)
    finally:
        ISO.use("v9")
    return s, u


def entries():
    for rid, p in PLAN.items():
        for m in p["modules"]:
            for ph in p["phases"]:
                for side in (("new", "old") if p.get("old") else ("new",)):
                    for rep in REPS:
                        yield side, rid, ph, m, rep


def name_of(side, rid, ph, m, rep):
    return f"{VARIANT}_{side}_{rid}_{ph}_{m.replace('neorv32_', '')}_r{rep}"


def build():
    REQ.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)
    mf = ROOT / "manifest.json"
    man = {x["name"]: x for x in json.loads(mf.read_text(encoding="utf-8"))} if mf.exists() else {}
    cache = {}
    for side, rid, ph, m, rep in entries():
        key = (side, rid, ph, m)
        if key not in cache:
            cache[key] = request(side, rid, ph, m)
        s, u = cache[key]
        name = name_of(side, rid, ph, m, rep)
        f = REQ / f"{name}.md"
        body = CE3.render("=== SYSTEM ===\n" + s + "\n=== USER ===\n" + u + "\n")
        if not f.exists() or f.read_text(encoding="utf-8") != body:
            if f.exists() and (REP / f"{name}.json").exists():
                raise RuntimeError(f"{name}: the request changed but a reply is stored; move the reply away first")
            f.write_text(body, encoding="utf-8")
        man[name] = {"name": name, "side": side, "rule": rid, "phase": ph, "module": m, "rep": rep, "request": str(f),
                     "reply": str(REP / f"{name}.json"), "system sha": CE3.sha(s), "user sha": CE3.sha(u),
                     "chars": len(body), "lines": body.count("\n")}
    mf.write_text(json.dumps(list(man.values()), indent=1), encoding="utf-8")
    bad = []
    for rid, p in PLAN.items():                           # the two sides differ only in the rule text; repeats identical
        if not p.get("old"):
            continue
        for m in p["modules"]:
            for ph in p["phases"]:
                so, uo = cache[("old", rid, ph, m)]
                sn, un = cache[("new", rid, ph, m)]
                to = json.loads(Path(ISO.VARIANTS["v9k_old"]["texts"]).read_text(encoding="utf-8"))[rid][ph]
                tn = json.loads(Path(ISO.VARIANTS["v9k"]["texts"]).read_text(encoding="utf-8"))[rid][ph]
                if so != sn or uo.replace(to, tn) != un or to == tn:
                    bad.append(f"{rid} {m} {ph}: sides differ beyond the rule text")
    sel = list(man.values())
    print(f"{len(sel)} request files ({sum(1 for x in sel if x['side'] == 'new')} new side, {sum(1 for x in sel if x['side'] == 'old')} old side); "
          f"{min(x['chars'] for x in sel):,}-{max(x['chars'] for x in sel):,} chars; checks: {'PASS' if not bad else bad}")


def jobs():
    man = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    out = []
    for x in man:
        if not Path(x["reply"]).exists():
            out.append({"name": x["name"], "req": x["request"], "out": x["reply"], "chars": x["chars"],
                        "prompt": CE3.PROMPT.format(req=x["request"], out=x["reply"])})
    return out


def audit(folder, log=print):
    """claude_e3.audit for Workflow transcripts: the task text (with the request path) is the second user message, after
    the harness relay, so the request name is looked for in every user message with string content. Same checks: only
    Reads of its own request covering every line, one Write (or Edits) of its own reply, nothing else."""
    man = {x["name"]: x for x in json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))}
    sa = ROOT / "set_aside.json"
    skip = set(json.loads(sa.read_text(encoding="utf-8"))) if sa.exists() else set()
    res = {}
    folders = folder if isinstance(folder, (list, tuple)) else [folder]
    for f in sorted(p for d in folders for p in Path(d).glob("agent-*.jsonl")):
        if f.name in skip:
            continue
        entries = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        texts = "\n".join(e["message"]["content"] for e in entries if e.get("type") == "user"
                          and isinstance((e.get("message") or {}).get("content"), str))
        name = next((n for n in man if f"\\requests\\{n}.md" in texts or f"/requests/{n}.md" in texts), None)
        if name is None:
            continue
        x, probs, spans, writes = man[name], [], [], 0
        req, rep = Path(x["request"]).resolve(), Path(x["reply"]).resolve()
        for e in entries:
            c = (e.get("message") or {}).get("content")
            for b in c if isinstance(c, list) else []:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                nm, inp = b.get("name"), b.get("input") or {}
                p = Path(inp["file_path"]).resolve() if inp.get("file_path") else None
                if nm == "Read" and p == req:
                    off = int(inp.get("offset") or 0)
                    spans.append((max(off, 1), off + int(inp.get("limit") or 2000)))
                elif nm == "Write" and p == rep:
                    writes += 1
                elif nm == "Edit" and p == rep:
                    pass
                elif nm != "SubagentHandback":
                    probs.append(f"tool {nm} {str(inp)[:120]}")
        covered = 1
        for a, b in sorted(spans):
            if a > covered + 1:
                break
            covered = max(covered, b)
        if covered < x["lines"]:
            probs.append(f"read lines up to {covered} of {x['lines']}")
        if writes < 1:
            probs.append("its reply was never written")
        res[name] = res.get(name, []) + [f"{f.name}: {p}" for p in probs]
    clean = sum(1 for v in res.values() if not v)
    log(f"audit: {len(res)} transcripts matched to requests; {clean} clean; problems: "
        + ("; ".join(f"{k}: {v}" for k, v in res.items() if v) or "none"))
    (ROOT / "audit.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def setaside(log=print):
    """After an audit: every request whose transcript has a problem other than 'never written' (the agent used another
    tool, or did not read every line) gets its reply moved to replies/_invalid/ and its transcript name recorded in
    set_aside.json, so `jobs` lists it again for a re-run and the next audit skips the old transcript."""
    aud = json.loads((ROOT / "audit.json").read_text(encoding="utf-8"))
    man = {x["name"]: x for x in json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))}
    sa = ROOT / "set_aside.json"
    skip = json.loads(sa.read_text(encoding="utf-8")) if sa.exists() else []
    inv = REP / "_invalid"
    inv.mkdir(exist_ok=True)
    moved = []
    for name, probs in aud.items():
        real = [p for p in probs if "never written" not in p]
        if not real:
            continue
        for p in real:
            tf = p.split(":")[0]
            if tf not in skip:
                skip.append(tf)
        rep = Path(man[name]["reply"])
        if rep.exists():
            k = len(list(inv.glob(f"{name}*.json")))
            rep.rename(inv / f"{name}__{k}.json")
            moved.append(name)
    sa.write_text(json.dumps(skip, indent=1), encoding="utf-8")
    log(f"set aside: {len(moved)} replies moved to _invalid ({moved}); {len(skip)} transcripts skipped by later audits")


def collect(log=print):
    man = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    aud = json.loads((ROOT / "audit.json").read_text(encoding="utf-8"))
    stored = skipped = bad = 0
    for x in man:
        p = Path(x["reply"])
        if not p.exists() or x["name"] not in aud or aud[x["name"]]:
            skipped += 1
            continue
        s, u = request(x["side"], x["rule"], x["phase"], x["module"])
        if (CE3.sha(s), CE3.sha(u)) != (x["system sha"], x["user sha"]):
            raise RuntimeError(f"{x['name']}: request changed since build")
        raw = p.read_text(encoding="utf-8")
        obj = ISO.K.parse_json(raw)
        ISO.use(STORE[x["side"]])
        try:
            try:
                problems = ISO.check(x["module"], obj)
            except Exception as e:  # noqa: BLE001
                problems = [f"check crashed: {e}"[:300]]
            rec = {"rule": x["rule"], "phase": x["phase"], "module": x["module"], "rep": x["rep"], "system sha": x["system sha"],
                   "user sha": x["user sha"], "usage": None, "batch": x["name"],
                   "executor": "Claude Code subagent, model sonnet, one rule per call", "raw": raw, "reply": obj,
                   "problems": problems}
            q = ISO.path(x["rule"], x["phase"], x["module"], x["rep"])
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        finally:
            ISO.use("v9")
        stored += 1
        bad += bool(problems)
    log(f"collect: {stored} records stored ({bad} with problems); {skipped} of {len(man)} not stored (absent or failed audit)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "jobs":
        print(json.dumps(jobs(), indent=1))
    elif cmd == "prompt":
        x = next(y for y in json.loads((ROOT / "manifest.json").read_text(encoding="utf-8")) if y["name"] == sys.argv[2])
        print(CE3.PROMPT.format(req=x["request"], out=x["reply"]))
    elif cmd == "audit":
        audit(sys.argv[2:])
    elif cmd == "setaside":
        setaside()
    elif cmd == "collect":
        collect()
