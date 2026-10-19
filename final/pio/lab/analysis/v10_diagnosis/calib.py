"""Step C of PLAN.md (cut down by decision D5): which Claude model answers like luna. Code only: sends nothing to any
API; Claude subagents (models haiku, sonnet, opus) answer request files written here, launched from the session.

Requests are EXACTLY the ones luna answered (same system and user text, reflowed for the Read tool by claude_e3.render,
lossless):
  C1  v10's Phase 2 call on luna's own v10 r0 Phase 1 reply, for the calibration modules (one request per module and
      model). Compared with luna's stored v10 r0 Phase 2 reply: target-rule breaks repeated (of luna's breaks), breaks
      luna did not make (of luna's kept), agreement of the primary sets (shared / union), precision and recall.
  C2  rule-alone requests of the target wordings (their luna source variant), 2 modules x repeats 0-1 per model.
      Compared with luna's stored replies: agreement on the barred elements, and self-agreement between the two repeats.
Proxy reading (PLAN.md): repeats at least 0.6 of luna's breaks and breaks no more than 0.2 of what luna keeps (C1).
Reported for later use only: decision D5 put the staged test on luna.

Files: runs/diag_v10_claude/ (requests/<name>.md, replies/<name>.json, manifest.json, audit.json, usage.json).

  python -B calib.py build <calibration modules...> -- <target wordings, e.g. "P1-16 P2"...>
  python -B calib.py prompt <name>
  python -B calib.py audit <subagents folder>
  python -B calib.py collect
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, ISOD, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
sys.path.insert(0, str(ISOD))
import claude_e3 as E3  # noqa: E402
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import labkit as K  # noqa: E402

ROOT = LAB / "runs" / "diag_v10_claude"
REQ, REP = ROOT / "requests", ROOT / "replies"
MAN = ROOT / "manifest.json"
MODELS = ("haiku", "sonnet", "opus")


def manifest():
    return json.loads(MAN.read_text(encoding="utf-8")) if MAN.exists() else []


def write_req(name, system, user, kind, info):
    REQ.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)
    body = E3.render("=== SYSTEM ===\n" + system + "\n=== USER ===\n" + user + "\n")
    f = REQ / f"{name}.md"
    f.write_text(body, encoding="utf-8")
    return {"name": name, "kind": kind, **info, "request": str(f), "reply": str(REP / f"{name}.json"),
            "lines": body.count("\n") + 1, "chars": len(body), "system sha": CH.sha12(system), "user sha": CH.sha12(user)}


def build(mods, targets):
    man = []
    for m in mods:
        r1 = json.loads((CH.run_dir(V10, MODEL, 0, EFFORT) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
        s, u = CK.system(V10, 2), CH.user_message(V10, 2, m, CH.concepts_as_written(r1, V10))
        luna = json.loads((CH.run_dir(V10, MODEL, 0, EFFORT) / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
        assert (luna["system sha"], luna["user sha"]) == (CH.sha12(s), CH.sha12(u)), f"{m}: not luna's request"
        for mo in MODELS:
            man.append(write_req(f"c1_{mo}_{m[8:]}", s, u, "C1", {"model": mo, "module": m, "rep": 0}))
    import rule_breaks as RB
    for t in targets:
        rid, ph = t.split()
        ISO.use(RB.source(rid, ph))
        texts = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
        for m in mods[:2]:
            for rep in (0, 1):
                rec = json.loads((ISO.run_root(rep=rep) / ph / rid / f"{m}.json").read_text(encoding="utf-8"))
                s, u = ISO.system(ph), ISO.user(m, rid, ph, texts)
                assert (rec["system sha"], rec["user sha"]) == (CH.sha12(s), CH.sha12(u)), f"{t} {m}: not luna's request"
                for mo in MODELS:
                    man.append(write_req(f"c2_{mo}_{rid}{ph}_{m[8:]}_r{rep}", s, u, "C2",
                                         {"model": mo, "module": m, "rep": rep, "target": t, "variant": RB.source(rid, ph)}))
        ISO.use("v9")
    MAN.write_text(json.dumps(man, indent=1), encoding="utf-8")
    print(f"{len(man)} requests; largest {max(x['chars'] for x in man):,} characters; models {MODELS}")


def audit_wf(folders, log=print):
    """Workflow agents: the task text (with the request path) is in a later user message, not the first. Each transcript
    must Read its own request covering every line and Write its own reply; any other tool call is a problem."""
    man = {x["name"]: x for x in manifest()}
    res = {}
    for folder in folders:
        for f in sorted(Path(folder).glob("agent-*.jsonl")):
            entries = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
            texts = " ".join(e["message"]["content"] for e in entries if e.get("type") == "user"
                             and isinstance((e.get("message") or {}).get("content"), str))
            name = next((n for n in man if f"\requests\{n}.md" in texts or f"/requests/{n}.md" in texts
                         or f"\\requests\\{n}.md" in texts), None)
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
                    pth = Path(inp["file_path"]).resolve() if inp.get("file_path") else None
                    if nm == "Read" and pth == req:
                        off = int(inp.get("offset") or 0)
                        spans.append((max(off, 1), off + int(inp.get("limit") or 2000)))
                    elif nm in ("Write", "Edit") and pth == rep:
                        writes += nm == "Write"
                    elif nm == "Read" and pth == rep:
                        pass                               # re-reading its own reply (seen in earlier Claude runs)
                    elif nm != "SubagentHandback":
                        probs.append(f"tool {nm} {str(inp)[:100]}")
            cov = 1
            for a, b in sorted(spans):
                if a > cov + 1:
                    break
                cov = max(cov, b)
            if cov < x["lines"]:
                probs.append(f"read lines up to {cov} of {x['lines']}")
            if not writes:
                probs.append("reply never written")
            res[name] = res.get(name, []) + probs
    clean = sum(1 for v in res.values() if not v)
    log(f"audit: {len(res)} transcripts matched; {clean} clean; problems: " + ("; ".join(f"{k}: {v}" for k, v in res.items() if v) or "none"))
    (ROOT / "audit.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def collect():
    import ladder as L
    import rule_breaks as RB
    import analyze_isolation as AN
    aud = json.loads((ROOT / "audit.json").read_text(encoding="utf-8")) if (ROOT / "audit.json").exists() else {}
    out = {"C1": {}, "C2": {}, "skipped": []}
    for x in manifest():
        f = Path(x["reply"])
        if not f.exists() or aud.get(x["name"]) is None or aud.get(x["name"]):
            out["skipped"].append(f"{x['name']}: {'no reply' if not f.exists() else 'audit ' + str(aud.get(x['name']))}")
            continue
        text = f.read_text(encoding="utf-8")
        try:
            obj = K.parse_json(text)
        except ValueError as e:
            out["skipped"].append(f"{x['name']}: unparseable ({e})")
            continue
        m = x["module"]
        if x["kind"] == "C1":
            r1 = json.loads((CH.run_dir(V10, MODEL, 0, EFFORT) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
            concepts = CH.phase1_concepts(r1["reply"])
            rep, _ = CH.from_format_phase2(obj, text, [c.get("id") for c in concepts])
            mine = {a["Asset RTL"] for a in CH.to_assets(m, rep, concepts)["Assets"]}
            luna = {a["Asset RTL"] for a in json.loads((CH.run_dir(V10, MODEL, 0, EFFORT) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]}
            ref = set(RB.CV.groups_and_ref()[1][m])
            row = out["C1"].setdefault(x["model"], {"luna breaks": 0, "repeated": 0, "luna kept": 0, "broke where luna kept": 0,
                                                     "shared primaries": 0, "union primaries": 0, "TP": 0, "listed": 0, "findable": 0,
                                                     "luna TP": 0, "luna listed": 0})
            for t in json.loads((HERE / "rule_breaks.json").read_text(encoding="utf-8"))["targets"]:
                for e in L.bars(t, [m])[m]:
                    if e in luna:
                        row["luna breaks"] += 1
                        row["repeated"] += e in mine
                    else:
                        row["luna kept"] += 1
                        row["broke where luna kept"] += e in mine
            row["shared primaries"] += len(mine & luna)
            row["union primaries"] += len(mine | luna)
            row["TP"] += len(mine & ref)
            row["listed"] += len(mine)
            row["findable"] += len(ref)
            row["luna TP"] += len(luna & ref)
            row["luna listed"] += len(luna)
        else:
            mine = AN.names(obj, "barred")
            ISO.use(x["variant"])
            rid, ph = x["target"].split()
            luna = AN.names(json.loads((ISO.run_root(rep=x["rep"]) / ph / rid / f"{m}.json").read_text(encoding="utf-8"))["reply"], "barred")
            ISO.use("v9")
            row = out["C2"].setdefault(x["model"], {"shared barred": 0, "union barred": 0, "replies": 0})
            row["shared barred"] += len(mine & luna)
            row["union barred"] += len(mine | luna)
            row["replies"] += 1
            out.setdefault("_c2 sets", {})[x["name"]] = sorted(mine)
    for mo, r in out["C1"].items():
        r["repeat share"] = round(r["repeated"] / r["luna breaks"], 3) if r["luna breaks"] else None
        r["false break share"] = round(r["broke where luna kept"] / r["luna kept"], 3) if r["luna kept"] else None
        r["primary agreement"] = round(r["shared primaries"] / r["union primaries"], 3) if r["union primaries"] else None
        r["proxy reading met"] = bool(r["repeat share"] is not None and r["repeat share"] >= 0.6
                                      and (r["false break share"] or 0) <= 0.2)
    for mo, r in out["C2"].items():
        r["barred agreement with luna"] = round(r["shared barred"] / r["union barred"], 3) if r["union barred"] else None
    selfagree = {}
    sets = out.get("_c2 sets", {})
    for n, s in sets.items():
        if n.endswith("_r0") and n[:-1] + "1" in sets:
            mo = n.split("_")[1]
            a, b = set(s), set(sets[n[:-1] + "1"])
            x = selfagree.setdefault(mo, [0, 0])
            x[0] += len(a & b)
            x[1] += len(a | b)
    out["C2 self-agreement (shared / union of the two repeats)"] = {mo: (v[0], v[1], round(v[0] / v[1], 3) if v[1] else None) for mo, v in selfagree.items()}
    (HERE / "calib.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "_c2 sets"}, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "build":
        a = sys.argv[2:]
        i = a.index("--")
        build(a[:i], a[i + 1:])
    elif cmd == "prompt":
        x = next(y for y in manifest() if y["name"] == sys.argv[2])
        print(E3.PROMPT.format(req=x["request"], out=x["reply"]))
    elif cmd == "audit":
        audit_wf(sys.argv[2:])
    elif cmd == "collect":
        collect()
