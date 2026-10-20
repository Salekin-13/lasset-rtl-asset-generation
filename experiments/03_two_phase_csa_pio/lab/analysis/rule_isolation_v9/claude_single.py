"""One rule, one module per Claude agent: the rule-alone test of the E1 fix to Buffer and engine status bits (user
2026-10-16: "apply the E1 gloss fix to Buffer and engine status bits and test that rule alone first"; no OpenAI budget).
Same request as the OpenAI isolation test (isolation.system + isolation.user, old reply format), rendered for the
agents' Read tool (claude_e3.render), one agent per (side, phase, module, repeat). Sends nothing to any API.

  sides    "old" = v10m (the current v10 text of P1-17, v10's merged procedure)
           "new" = v10e1 (the same with the two E1 edits)
  modules  PART1 now (gptmr: timer count and compare flag; sysinfo, cache: response acknowledge / error lines; uart:
           FIFO-flag and busy targets), PART2 after the 5-hour usage window resets (debug_dm: error and reset records;
           spi, slink: targets). neorv32_bus is left out: its requests are about 300,000 characters each.
  repeats  2: identical requests, separate agents.
Agents: Claude Code subagents, model sonnet (claude_e3.PROMPT). Audit: claude_e3.audit(<subagents folder>, root=ROOT).
Records go to the variants v10m__claude1 / v10e1__claude1 (isolation.CLAUDE1_EXEC) in isolation.ask's record shape.

  python -B claude_single.py build [part1|part2|all]
  python -B claude_single.py prompt <name>
  python -B claude_single.py collect
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402
import claude_e3 as CE3  # noqa: E402

RID = "P1-17"
ROOT = ISO.LAB / "runs" / "e1_claude"
REQ, REP = ROOT / "requests", ROOT / "replies"
PART1 = ["neorv32_gptmr", "neorv32_sysinfo", "neorv32_cache", "neorv32_uart"]
PART2 = ["neorv32_debug_dm", "neorv32_spi", "neorv32_slink"]
SIDES = {"old": "v10m", "new": "v10e1"}
STORE = {"old": "v10m__claude1", "new": "v10e1__claude1"}


def request(side, ph, m):
    ISO.use(SIDES[side])
    try:
        tx = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
        s, u = ISO.system(ph), ISO.user(m, RID, ph, tx)
    finally:
        ISO.use("v9")
    return s, u


def build(part="all"):
    mods = {"part1": PART1, "part2": PART2, "all": PART1 + PART2}[part]
    REQ.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)
    mf = ROOT / "manifest.json"
    man = {x["name"]: x for x in json.loads(mf.read_text(encoding="utf-8"))} if mf.exists() else {}
    for m in mods:
        for ph in ("P1", "P2"):
            for side in ("old", "new"):
                s, u = request(side, ph, m)
                for rep in (0, 1):
                    name = f"e1_{side}_{ph}_{m.replace('neorv32_', '')}_r{rep}"
                    f = REQ / f"{name}.md"
                    body = CE3.render("=== SYSTEM ===\n" + s + "\n=== USER ===\n" + u + "\n")
                    f.write_text(body, encoding="utf-8")
                    man[name] = {"name": name, "side": side, "phase": ph, "module": m, "rep": rep, "request": str(f),
                                 "reply": str(REP / f"{name}.json"), "system sha": CE3.sha(s), "user sha": CE3.sha(u),
                                 "chars": len(body), "lines": body.count("\n")}
    mf.write_text(json.dumps(list(man.values()), indent=1), encoding="utf-8")
    # checks: sides differ only in the rule text; repeats identical
    bad = []
    for m in mods:
        for ph in ("P1", "P2"):
            so, uo = request("old", ph, m)
            sn, un = request("new", ph, m)
            ISO.use("v10m")
            to = json.loads(ISO.texts_file().read_text(encoding="utf-8"))[RID][ph]
            ISO.use("v10e1")
            tn = json.loads(ISO.texts_file().read_text(encoding="utf-8"))[RID][ph]
            ISO.use("v9")
            if so != sn or uo.replace(to, tn) != un or to == tn:
                bad.append(f"{m} {ph}: sides differ beyond the rule text")
    sel = [x for x in man.values() if x["module"] in mods]
    print(f"{len(sel)} request files for {len(mods)} modules; {min(x['chars'] for x in sel):,}-{max(x['chars'] for x in sel):,} "
          f"chars; checks: {'PASS' if not bad else bad}")


def collect(log=print):
    man = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    aud = json.loads((ROOT / "audit.json").read_text(encoding="utf-8"))
    stored = skipped = bad = 0
    for x in man:
        p = Path(x["reply"])
        if not p.exists() or x["name"] not in aud or aud[x["name"]]:
            skipped += 1
            continue
        s, u = request(x["side"], x["phase"], x["module"])
        if (CE3.sha(s), CE3.sha(u)) != (x["system sha"], x["user sha"]):
            raise RuntimeError(f"{x['name']}: request changed since build")
        raw = p.read_text(encoding="utf-8")
        obj = ISO.K.parse_json(raw)
        ISO.use(STORE[x["side"]])
        try:
            try:
                problems = ISO.check(x["module"], obj)
            except Exception as e:
                problems = [f"check crashed: {e}"[:300]]
            rec = {"rule": RID, "phase": x["phase"], "module": x["module"], "rep": x["rep"], "system sha": x["system sha"],
                   "user sha": x["user sha"], "usage": None, "batch": x["name"],
                   "executor": "Claude Code subagent, model sonnet, one rule per call", "raw": raw, "reply": obj,
                   "problems": problems}
            q = ISO.path(RID, x["phase"], x["module"], x["rep"])
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
        build(sys.argv[2] if len(sys.argv) > 2 else "all")
    elif cmd == "prompt":
        x = next(y for y in json.loads((ROOT / "manifest.json").read_text(encoding="utf-8")) if y["name"] == sys.argv[2])
        print(CE3.PROMPT.format(req=x["request"], out=x["reply"]))
    elif cmd == "collect":
        collect()
