"""E3 on a Claude executor (user 2026-10-16: "after building E3, I need you to test it here, as I do not have openai
budget to cover the run"). Code only: builds the request files the Claude agents read, and stores their replies in the
record shape of isolation.ask, so read_e3.py reads them unchanged. Sends nothing to any API.

Why not cell 18's design: one call per (rule wording, module, repeat) is 2,706 calls, each carrying the whole module;
as Claude subagents that is far beyond the session's usage limits. And luna's stored runs cannot serve as the "last"
side for a Claude run: a different executor disagrees with itself at a different rate. So:
  sides    "last"   each rule's last procedure: the v10r procedure for the 13 v10 rewrites, the v10f procedure for the
                    4 adopted rules (their isolation contexts, unchanged);
           "merged" the v10 procedure (context_p*_v10m.md).
           Rule texts byte-equal on both sides (rule_texts_v10m.json); old reply format; same executor and model.
  batches  one agent per (side, group, phase, module, repeat). Group "13" = the 13 v10 rewrites, group "4" = the 4 adopted
           rules; the agent applies every rule of its group, each alone, and returns one object per rule. The groups are
           the same on both sides, so the comparison stays paired. DEVIATION from "one rule per call": a rule may be read
           in the light of the others in its batch; this holds equally on both sides, and absolute rates are not
           comparable with any luna run.
  modules  MODULES: uart, twi (both hold Second copies' code-defined pattern), wdt (the G3 watch list), xbus.
  repeats  2: identical requests, separate agents.
Readings: read_e3.py's E3-1 ... E3-9, set before the run, on these modules and these sides
(python -B read_e3.py claude). E3-4's v9 / v10r reference values are luna values; on Claude, read "new vs last".
Agents: Claude Code subagents (model sonnet), told to read only their request file and write only their reply file.
Audit after the run: claude_e3.py audit <subagents folder> lists every tool call that is not a Read of the agent's own
request or a Write of its own reply (such replies are set aside, not scored).

  python -B claude_e3.py build              request files + manifest.json under lab/runs/e3_claude/ (sends nothing)
  python -B claude_e3.py prompt <name>      the exact prompt for one agent
  python -B claude_e3.py collect            parse the replies, check them, store per-rule records
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402

LAB = ISO.LAB
ROOT_E3 = LAB / "runs" / "e3_claude"
REQ, REP = ROOT_E3 / "requests", ROOT_E3 / "replies"
MODULES = ["neorv32_uart", "neorv32_twi", "neorv32_wdt", "neorv32_xbus"]
GROUPS = {"4": list(ISO.G3_RULES), "13": [r for r in ISO.RULES17 if r not in ISO.G3_RULES]}
LAST_CTX = {"13": "v10r", "4": "v10fo"}                    # the context each group was last tested with
STORE = {("merged", g): "v10m__claude" for g in GROUPS} | {("last", "13"): "v10r__claude", ("last", "4"): "v10fo__claude"}
MODEL = "sonnet"

_OLD_INTRO = ("THIS CALL: ONE RULE, APPLIED ALONE\n\nYou are given one rule from a longer prompt that identifies security "
              "assets in RTL, and one design module. Apply only\nthat rule, exactly as written, to the module, and report what "
              "it decides. Do not apply any other rule of the longer\nprompt; the definitions and steps below are context the "
              "rule refers to (section numbers such as 2.6, step names), not\nrules to apply.\n")
_NEW_INTRO = ("THIS CALL: SEVERAL RULES, EACH APPLIED ALONE\n\nYou are given several rules from a longer prompt that identifies "
              "security assets in RTL, and one design module. Apply\neach rule on its own, exactly as written, to the module, "
              "as if it were the only rule, and report what it decides: a\ndecision under one rule never depends on another "
              "rule in the list or on what you decided for it. Do not apply any\nother rule of the longer prompt; the "
              "definitions and steps below are context the rules refer to (section numbers such\nas 2.6, step names), not "
              "rules to apply.\n")
_OLD_RET = "Return one JSON object:\n"
_NEW_RET = ("Return one JSON object whose keys are the rule ids given (every one, in the order given) and whose value for each\n"
            "rule is an object of this form:\n")
assert ISO.SYSTEM_HEAD.startswith(_OLD_INTRO) and ISO.SYSTEM_HEAD.count(_OLD_RET) == 1 and ISO.SYSTEM_HEAD.count("\nTask: ") == 1
HEAD_BATCH = (ISO.SYSTEM_HEAD.replace(_OLD_INTRO, _NEW_INTRO).replace(_OLD_RET, _NEW_RET)
              .replace("\nTask: ", "\nTask, for each rule separately: "))

PROMPT = """You are the executor in a controlled test. Read the file {req} completely: it is long, so use the Read tool with
offset and limit until you have read every line. The file has a SYSTEM part and a USER part. Follow them exactly, as if
they were your own instructions, using only the content of that file. Do not open, list or search any other file, do
not run commands, do not use the web.
When you are done, write ONLY the JSON object the task asks for (no prose, no code fence) to {out} with the Write tool.
Then reply with the single word: done."""


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


MAX_LINE = 1500      # the agents' Read tool cuts lines longer than 2,000 characters


def render(text):
    """The request as the agent reads it: lines over MAX_LINE reflowed, nothing else changed. A JSON line (the closed set)
    is pretty-printed (json.loads equal); a prose line (Phase 2's step-4 line, which ends with the procedure under test)
    is word-wrapped (rejoined with single spaces it equals the original). Raises if either check fails."""
    import textwrap
    out = []
    for line in text.split("\n"):
        if len(line) <= MAX_LINE:
            out.append(line)
            continue
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            obj = json.loads(s)
            pretty = json.dumps(obj, indent=1, ensure_ascii=False)
            assert json.loads(pretty) == obj
            out.extend(pretty.split("\n"))
            continue
        parts = textwrap.wrap(line, 1000, break_long_words=False, break_on_hyphens=False)
        if " ".join(parts) != line:
            raise ValueError(f"word-wrap would change a line: {line[:80]}")
        out.extend(parts)
    r = "\n".join(out)
    longest = max(len(l) for l in out)
    if longest > MAX_LINE:
        raise ValueError(f"a line of {longest} characters is left")
    return r


def texts():
    return json.loads((HERE / "rule_texts_v10m.json").read_text(encoding="utf-8"))


def system_batch(side, group, ph):
    ISO.use("v10m" if side == "merged" else LAST_CTX[group])
    try:
        s = ISO.system(ph)
    finally:
        ISO.use("v9")
    assert s.startswith(ISO.SYSTEM_HEAD)
    return HEAD_BATCH + s[len(ISO.SYSTEM_HEAD):]


def user_batch(m, group, ph, tx):
    base = ISO.CH.user_message(ISO.V9, 1, m)
    base = base[:base.rindex("\nDo Phase 1")]
    rules = [r for r in GROUPS[group] if tx[r].get(ph)]
    parts = [base, f"\n\n=== RULES UNDER TEST ({'Phase 1' if ph == 'P1' else 'Phase 2'} wordings; each applied alone) ==="]
    for r in rules:
        parts.append(f"\n--- RULE {r} (rule: {tx[r]['title']}) ---\n{tx[r][ph]}\n")
    parts.append(f"\nApply each rule above alone to module '{m}' and return the JSON object keyed by rule id "
                 f"({', '.join(rules)}).")
    return "".join(parts), rules


def plan():
    out = []
    for m in MODULES:
        for g in ("13", "4"):
            for ph in ("P1", "P2"):
                for side in ("last", "merged"):
                    for rep in (0, 1):
                        out.append({"name": f"{side}_g{g}_{ph}_{m.replace('neorv32_', '')}_r{rep}", "side": side, "group": g,
                                    "phase": ph, "module": m, "rep": rep})
    return out


def build():
    tx = texts()
    REQ.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)
    man = []
    for j in plan():
        s = system_batch(j["side"], j["group"], j["phase"])
        u, rules = user_batch(j["module"], j["group"], j["phase"], tx)
        body = render("=== SYSTEM ===\n" + s + "\n=== USER ===\n" + u + "\n")
        f = REQ / f"{j['name']}.md"
        f.write_text(body, encoding="utf-8")
        man.append({**j, "rules": rules, "request": str(f), "reply": str(REP / f"{j['name']}.json"),
                    "system sha": sha(s), "user sha": sha(u), "chars": len(body), "lines": body.count("\n")})
    (ROOT_E3 / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    # checks: the two sides differ only by the procedure; both repeats identical; sizes
    bad = []
    by = {}
    for x in man:
        by.setdefault((x["group"], x["phase"], x["module"]), {})[(x["side"], x["rep"])] = x
    for k, d in by.items():
        if d[("last", 0)]["user sha"] != d[("merged", 0)]["user sha"]:
            bad.append(f"{k}: user text differs between sides")
        if any(d[(s, 0)]["system sha"] != d[(s, 1)]["system sha"] for s in ("last", "merged")):
            bad.append(f"{k}: repeats differ")
    print(f"{len(man)} request files ({len({x['module'] for x in man})} modules); sizes {min(x['chars'] for x in man):,}"
          f"-{max(x['chars'] for x in man):,} chars, {min(x['lines'] for x in man)}-{max(x['lines'] for x in man)} lines; "
          f"checks: {'PASS' if not bad else bad}")
    return man


def collect(log=print):
    man = json.loads((ROOT_E3 / "manifest.json").read_text(encoding="utf-8"))
    aud = ROOT_E3 / "audit.json"
    if not aud.exists():
        raise RuntimeError("run the audit first: python -B claude_e3.py audit <subagents folder>")
    audit_res = json.loads(aud.read_text(encoding="utf-8"))
    tx = texts()
    stored = missing = bad = 0
    for x in man:
        p = Path(x["reply"])
        if not p.exists() or x["name"] not in audit_res or audit_res[x["name"]]:
            missing += 1                                    # absent, never audited, or failed the audit: not scored
            continue
        raw = p.read_text(encoding="utf-8")
        obj = ISO.K.parse_json(raw)
        u, rules = user_batch(x["module"], x["group"], x["phase"], tx)
        if sha(u) != x["user sha"] or sha(system_batch(x["side"], x["group"], x["phase"])) != x["system sha"]:
            raise RuntimeError(f"{x['name']}: request files changed since build")
        ISO.use(STORE[(x["side"], x["group"])])
        try:
            for rid in rules:
                one = obj.get(rid) if isinstance(obj, dict) else None
                try:
                    problems = ISO.check(x["module"], one)
                except Exception as e:
                    problems = [f"check crashed: {e}"[:300]]
                rec = {"rule": rid, "phase": x["phase"], "module": x["module"], "rep": x["rep"],
                       "system sha": x["system sha"], "user sha": x["user sha"], "usage": None, "batch": x["name"],
                       "executor": f"Claude Code subagent, model {MODEL}, batched by group", "raw": json.dumps(one, ensure_ascii=False),
                       "reply": one, "problems": problems}
                q = ISO.path(rid, x["phase"], x["module"], x["rep"])
                q.parent.mkdir(parents=True, exist_ok=True)
                q.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
                stored += 1
                bad += bool(problems)
        finally:
            ISO.use("v9")
    log(f"collect: {len(man) - missing} of {len(man)} replies present; {stored} per-rule records stored, {bad} with problems")
    return stored, missing, bad


def audit(folder, root=None, log=print):
    """Every subagent transcript in `folder` whose prompt names a request of this run: its tool calls must be Reads of
    its own request file that together cover every line, one Write of its own reply file, and the hand-back. Returns
    {request name: [problems]}; collect() skips replies whose audit has problems."""
    root = Path(root) if root else ROOT_E3                  # the run folder holding manifest.json (claude_single.py too)
    man = {x["name"]: x for x in json.loads((root / "manifest.json").read_text(encoding="utf-8"))}
    sa = root / "set_aside.json"                          # transcripts whose replies were set aside and re-run
    skip = set(json.loads(sa.read_text(encoding="utf-8"))) if sa.exists() else set()
    res = {}
    for f in sorted(Path(folder).glob("agent-*.jsonl")):
        if f.name in skip:
            continue
        entries = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        first = next((e["message"]["content"] for e in entries if e.get("type") == "user"
                      and isinstance((e.get("message") or {}).get("content"), str)), "")
        name = next((n for n in man if f"\\requests\\{n}.md" in first or f"/requests/{n}.md" in first), None)
        if name is None:
            continue
        x, probs, spans = man[name], [], []
        req, rep = Path(x["request"]).resolve(), Path(x["reply"]).resolve()
        writes = 0
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
                elif nm == "Edit" and p == rep:             # a correction inside its own reply (seen once: a "why" wording)
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
    (root / "audit.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "audit":
        audit(sys.argv[2])
        sys.exit(0)
    if cmd == "build":
        build()
    elif cmd == "prompt":
        x = next(y for y in json.loads((ROOT_E3 / "manifest.json").read_text(encoding="utf-8")) if y["name"] == sys.argv[2])
        print(PROMPT.format(req=x["request"], out=x["reply"]))
    elif cmd == "collect":
        collect()
