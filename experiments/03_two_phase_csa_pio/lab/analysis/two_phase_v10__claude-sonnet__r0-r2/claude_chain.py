"""two_phase_v10 on a Claude executor, the 14 heldout_v2 modules, runs r0-r2 (user 2026-10-16: "run v10 on the held out
modules, as I do not have the openai budget"). Code only: sends nothing to any API.

How: chain.py itself runs the chain with labkit.file_call as its executor. chain builds every request exactly as for
luna (system prompt = C.system(v10, phase), user message = chain.user_message, Phase 2 gets Phase 1's concepts as
written), checks and converts the replies with the same code, and stores records in the same run-folder shape, so
the scorers read them unchanged. Each call that has no reply yet is written as a request file for one Claude Code
subagent (model sonnet), which reads only that file and writes only its reply file. A reply is handed to chain only
after the audit of the agent's transcript is clean (claude_e3.audit: Reads of its own request covering every line,
a Write of its own reply, nothing else).

Run folders: runs/two_phase_v10__v1/claude-sonnet__agent/r0..r2 (model label "claude-sonnet", effort label "agent",
executor "claude-code-subagent-file"; chain's guard refuses any other set-up in these folders).
Bookkeeping: runs/two_phase_v10__v1/claude-sonnet__agent/_claude/ (requests/, replies/ = what the agents wrote,
manifest.json, audit.json, usage.json, set_aside.json).

Differences from a luna run, stated before the run:
  - executor: Claude Sonnet as a subagent, not gpt-5.6-luna (high); never compare these numbers with luna runs;
  - the request file pretty-prints the compact closed-set JSON line and word-wraps prose lines over 1,500 characters
    (claude_e3.render, lossless check), because the agents' Read tool cuts lines over 2,000 characters;
  - no JSON mode: the agent writes the reply text; chain parses it the same way (labkit.parse_json);
  - format-failure retry: a reply that stops the module (no readable list) is moved aside and asked once more from a
    new agent (chain's one-retry rule; with a file executor the same key would return the same reply).

  python -B claude_chain.py step                 advance every run: accept audited replies, write request files
  python -B claude_chain.py prompt <name>        the exact prompt for one agent
  python -B claude_chain.py audit <subagents folder>
  python -B claude_chain.py usage <name> <tokens> <tool uses> <ms>
"""
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "analysis" / "rule_isolation_v9"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402
import claude_e3 as E3  # noqa: E402  (render, audit, PROMPT)

VERSION, MODEL, EFFORT, EXECUTOR = "two_phase_v10", "claude-sonnet", "agent", "claude-code-subagent-file"
REPS = (0, 1, 2)
MODULES = json.loads((LAB / "splits" / "tuning_v2.json").read_text(encoding="utf-8"))["heldout"]
ROOT = CH.run_dir(VERSION, MODEL, 0, EFFORT).parent / "_claude"
REQ, REP = ROOT / "requests", ROOT / "replies"
MAN = ROOT / "manifest.json"


def manifest():
    return json.loads(MAN.read_text(encoding="utf-8")) if MAN.exists() else []


def accepted_dir(rep):
    return CH.run_dir(VERSION, MODEL, rep, EFFORT) / "_claude"


def finished(folder):
    """Request names whose agent transcript holds a SubagentHandback tool call (the agent has finished). An agent may
    write a skeleton reply and fill it in with Edit afterwards (seen once: r0_p2_twd, a '@@NEXT@@' placeholder), so a
    clean audit alone does not mean the reply is final. Written to finished.json; accept() requires it."""
    names = {x["name"] for x in manifest()}
    done = set()
    for f in sorted(Path(folder).glob("agent-*.jsonl")):
        first, hb = "", False
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            c = (e.get("message") or {}).get("content")
            if not first and e.get("type") == "user" and isinstance(c, str):
                first = c
            hb |= any(isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "SubagentHandback"
                      for b in (c if isinstance(c, list) else []))
        n = next((n for n in names if f"\\requests\\{n}.md" in first or f"/requests/{n}.md" in first), None)
        if n and hb:
            done.add(n)
    (ROOT / "finished.json").write_text(json.dumps(sorted(done), indent=1), encoding="utf-8")
    return done


def accept(log=print):
    """Copy each audited, clean reply of a finished agent into its run's file-executor folder (<run>/_claude/<key>.json),
    once."""
    aud = json.loads((ROOT / "audit.json").read_text(encoding="utf-8")) if (ROOT / "audit.json").exists() else {}
    fin = set(json.loads((ROOT / "finished.json").read_text(encoding="utf-8"))) if (ROOT / "finished.json").exists() else set()
    n = 0
    for x in manifest():
        p, dest = Path(x["reply"]), accepted_dir(x["rep"]) / f"{x['key']}.json"
        if x.get("retired") or dest.exists() or not p.exists() or x["name"] not in fin:
            continue
        if x["name"] not in aud or aud[x["name"]]:
            log(f"  not accepted (audit {'missing' if x['name'] not in aud else aud[x['name']]}): {x['name']}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        n += 1
    log(f"accepted {n} new replies")


def _retry(rep, out, m, row, man, log):
    """chain's one-retry rule for a file executor: move the phase record to _schema_failed (as chain does) and the
    accepted reply to <run>/_claude/_failed/, so the next call writes a new request (name suffix _retry)."""
    ph = 1 if "phase 1" in row["status"] else 2
    dest = out / "_schema_failed" / f"phase{ph}"
    if (dest / f"{m}.json").exists():
        return False                                    # already had its retry
    rec = json.loads((out / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))
    key = rec["usage"]["key"]
    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(out / f"phase{ph}" / f"{m}.json"), str(dest / f"{m}.json"))
    with open(out / "_schema_failed" / "README.txt", "a", encoding="utf-8") as fh:
        fh.write(f"{m} phase {ph}: the first reply failed the format check ({row.get('problems')}); moved here and "
                 "asked once more from a new agent.\n")
    fd = accepted_dir(rep) / "_failed"
    fd.mkdir(parents=True, exist_ok=True)
    shutil.move(str(accepted_dir(rep) / f"{key}.json"), str(fd / f"{key}.json"))
    for x in man:
        if x["rep"] == rep and x["key"] == key and not x.get("retired"):
            x["retired"] = "format failure; asked again"
    log(f"  r{rep} {m}: phase {ph} format failure -> retry")
    return True


def step(log=print):
    """Accept audited replies, run every (rep, module) through chain as far as the replies reach, write a request file
    for every call still waiting, and print the state."""
    REQ.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)
    accept(log)
    man = manifest()
    have = {(x["rep"], x["key"]) for x in man if not x.get("retired")}
    state = {}
    for rep in REPS:
        out = CH._prepare(VERSION, MODEL, EFFORT, rep, EXECUTOR)
        call = K.file_call(accepted_dir(rep))
        for m in MODULES:
            row = CH._one(VERSION, m, call, out)
            if "schema failure" in str(row.get("status")) and _retry(rep, out, m, row, man, log):
                have = {(x["rep"], x["key"]) for x in man if not x.get("retired")}
                row = CH._one(VERSION, m, call, out)
            state[(rep, m)] = row
            st = str(row.get("status"))
            if st.startswith("waiting for reply"):
                key = st.split()[-1]
                if (rep, key) in have:
                    continue
                d = accepted_dir(rep)
                system = (d / f"{key}.system.md").read_text(encoding="utf-8")
                user = (d / f"{key}.user.txt").read_text(encoding="utf-8")
                ph = 1 if system == CH.C.system(VERSION, 1) else 2
                assert system == CH.C.system(VERSION, ph) and K.sha12(system + "\n\n" + user) == key
                n_before = sum(1 for x in man if x["rep"] == rep and x["module"] == m and x["phase"] == ph)
                name = f"r{rep}_p{ph}_{m.replace('neorv32_', '')}" + (f"_retry{n_before}" if n_before else "")
                body = E3.render("=== SYSTEM ===\n" + system + "\n=== USER ===\n" + user + "\n")
                f = REQ / f"{name}.md"
                f.write_text(body, encoding="utf-8")
                man.append({"name": name, "rep": rep, "module": m, "phase": ph, "key": key, "request": str(f),
                            "reply": str(REP / f"{name}.json"), "system sha": K.sha12(system), "user sha": K.sha12(user),
                            "chars": len(body), "lines": body.count("\n")})
                have.add((rep, key))
    MAN.write_text(json.dumps(man, indent=1), encoding="utf-8")
    done = sum(1 for r in state.values() if r.get("status") == "done")
    waiting = [x["name"] for x in man if not x.get("retired") and not (accepted_dir(x["rep"]) / f"{x['key']}.json").exists()]
    other = {f"r{k[0]} {k[1]}": r["status"] for k, r in state.items()
             if r.get("status") != "done" and not str(r.get("status")).startswith("waiting")}
    log(f"{done} of {len(state)} (run, module) pairs done; {len(waiting)} requests waiting for an agent"
        + (f"; other states: {other}" if other else ""))
    return waiting


def audit(folder, log=print):
    """claude_e3.audit with one allowance added for this run (2026-10-16, decided after three large-module agents did
    it; stated as a change made after seeing the behaviour): a Read or Grep of the agent's OWN reply file. Such agents
    write a skeleton reply, fill it with Edit, then search it for leftover placeholders; the file holds only what the
    agent wrote, so no outside information enters. Still a problem: any tool on any other path, a request not read in
    full, a reply never written. Transcripts listed in set_aside.json are skipped. Writes audit.json."""
    man = {x["name"]: x for x in manifest()}
    sa = ROOT / "set_aside.json"
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
        x, probs, spans, writes = man[name], [], [], 0
        req, rep = Path(x["request"]).resolve(), Path(x["reply"]).resolve()
        for e in entries:
            c = (e.get("message") or {}).get("content")
            for b in c if isinstance(c, list) else []:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                nm, inp = b.get("name"), b.get("input") or {}
                fp = inp.get("file_path") or inp.get("path")
                p = Path(fp).resolve() if fp else None
                if nm == "Read" and p == req:
                    off = int(inp.get("offset") or 0)
                    spans.append((max(off, 1), off + int(inp.get("limit") or 2000)))
                elif nm == "Write" and p == rep:
                    writes += 1
                elif nm in ("Edit", "Read", "Grep") and p == rep:
                    pass                                    # its own reply: allowed in this run
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
    (ROOT / "audit.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    log(f"audit: {len(res)} transcripts matched to requests; {sum(1 for v in res.values() if not v)} clean")
    return res


def usage(name, tokens, tools, ms):
    p = ROOT / "usage.json"
    u = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {
        "_note": "subagent_tokens / tool_uses / duration_ms as the Agent tool reported each run (model sonnet)"}
    u[name] = [int(tokens), int(tools), int(ms)]
    p.write_text(json.dumps(u, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "step"
    if cmd == "step":
        for w in step():
            print("  waiting:", w)
    elif cmd == "prompt":
        x = next(y for y in manifest() if y["name"] == sys.argv[2])
        print(E3.PROMPT.format(req=x["request"], out=x["reply"]))
    elif cmd == "audit":
        audit(sys.argv[2])
        print(f"finished agents: {len(finished(sys.argv[2]))}")
    elif cmd == "unlaunched":                         # waiting requests no agent transcript names yet (run audit first)
        aud = json.loads((ROOT / "audit.json").read_text(encoding="utf-8"))
        acc = lambda x: (accepted_dir(x["rep"]) / f"{x['key']}.json").exists()  # noqa: E731
        print(" ".join(x["name"] for x in manifest() if not x.get("retired") and not acc(x) and x["name"] not in aud))
    elif cmd == "usage":                              # name tokens tools ms, repeated
        a = sys.argv[2:]
        for i in range(0, len(a) - 3, 4):
            usage(*a[i:i + 4])
