"""Independent re-derivation of the stored two_phase_v9h (and v9g) records on seven modules.

Nothing here imports chain.py, labkit.py or any run/compare script. The record format was read from chain.py:
  sha12(t)      = sha256(t.encode("utf-8")).hexdigest()[:12]
  system (k)    = common.md.rstrip() + "\n\n" + phase<k>.md
  user (k)      = phase<k>_user.md .format(module, rtl, diagram, closed_set=compact JSON, [concepts])
  concepts      = json.dumps(parse_json(stored Phase 1 "raw")["Conceptual Assets"], indent=1, ensure_ascii=False)
  request key   = sha12(system + "\n\n" + user)      (stored in usage["request key"])
  record fields = "system sha", "user sha", "usage" {model, effort, request key, ...}, "raw", "reply", "problems"
parse_json: strip, drop a ``` fence, take text from the first "{" to the last "}", json.loads.

Run:  python -B verify_records.py        (no network; reads files only)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

LAB = Path(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab")
INPUTS = LAB / "inputs" / "v1"
MODEL, EFFORT = "gpt-5.6-luna", "high"
MODULES = ["neorv32_cpu_frontend", "neorv32_slink", "neorv32_cpu_icc", "neorv32_cpu_counters",
           "neorv32_cpu_control", "neorv32_debug_dm", "neorv32_xbus"]
REPS = (0, 1, 2)


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def parse_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


def module_dir(m: str) -> Path:
    for split in ("tuning", "heldout"):
        d = INPUTS / split / m
        if d.exists():
            return d
    raise FileNotFoundError(m)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def system_text(version: str, phase: int) -> str:
    d = LAB / "prompts" / version
    return read(d / "common.md").rstrip() + "\n\n" + read(d / f"phase{phase}.md")


def user_text(version: str, phase: int, m: str, concepts_json: str | None = None, inputs: dict | None = None) -> str:
    d = module_dir(m)
    x = inputs or {f: read(d / f) for f in ("rtl.txt", "closed_set.json", "diagram.txt")}
    t = read(LAB / "prompts" / version / f"phase{phase}_user.md")
    vals = {"module": m, "rtl": x["rtl.txt"], "diagram": x["diagram.txt"],
            "closed_set": json.dumps(json.loads(x["closed_set.json"]), separators=(",", ":"))}
    if phase == 2:
        vals["concepts"] = concepts_json
    return t.format(**vals)


def run_dir(version: str, rep: int) -> Path:
    return LAB / "runs" / f"{version}__v1" / f"{MODEL}__{EFFORT}" / f"r{rep}"


def has_parsed_reply(rec: dict) -> bool:
    """A parsed reply: "reply" is a JSON object, no 'not checked yet', no 'unparseable reply', no 'check crashed'."""
    probs = rec.get("problems") or []
    if rec.get("check crashed") or probs == ["not checked yet"]:
        return False
    if any(str(p).startswith(("unparseable reply", "check crashed")) for p in probs):
        return False
    return isinstance(rec.get("reply"), dict)


def check_record(version: str, rep: int, m: str, phase: int, rec: dict, sys_t: str, usr_t: str) -> dict:
    """Compare one stored record with the rebuilt message. Returns the per-record row."""
    ss, us = sha12(sys_t), sha12(usr_t)
    key = sha12(sys_t + "\n\n" + usr_t)
    u = rec.get("usage") or {}
    row = {
        "version": version, "rep": rep, "module": m, "phase": phase,
        "system sha ok": rec.get("system sha") == ss,
        "user sha ok": rec.get("user sha") == us,
        "request key ok": u.get("request key") == key,
        "model": u.get("model"), "effort": u.get("effort"),
        "meta ok": (rec.get("module"), rec.get("prompt version"), rec.get("input version"), rec.get("phase"))
                   == (m, version, "v1", phase),
        "parsed reply": has_parsed_reply(rec),
        "format problems": sum(1 for p in (rec.get("problems") or []) if str(p).startswith("format:")),
        "n problems": len(rec.get("problems") or []),
    }
    row["rebuilds"] = row["system sha ok"] and row["user sha ok"] and row["request key ok"]
    row["stored"] = {"system sha": rec.get("system sha"), "user sha": rec.get("user sha"), "request key": u.get("request key")}
    row["rebuilt"] = {"system sha": ss, "user sha": us, "request key": key}
    return row


def verify(version: str) -> dict:
    rows, per_run = [], {}
    sys1, sys2 = system_text(version, 1), system_text(version, 2)
    for rep in REPS:
        out = run_dir(version, rep)
        assets = sorted(p.name for p in (out / "assets").glob("*.json")) if (out / "assets").exists() else []
        assets_seven = [a for a in assets if a[:-5] in MODULES]
        pend = sorted(p.name for p in (out / "_pending").glob("*.json")) if (out / "_pending").exists() else []
        keys = {}
        kl = out / "_keys.jsonl"
        if kl.exists():
            for l in read(kl).splitlines():
                if l.strip():
                    x = json.loads(l)
                    keys[x["key"]] = (x.get("module"), x.get("phase"))
        per_run[f"r{rep}"] = {
            "asset files (all)": len(assets), "asset files (the seven)": len(assets_seven),
            "assets of the seven missing": sorted(set(MODULES) - {a[:-5] for a in assets_seven}),
            "pending request files": [(k[:-5], keys.get(k[:-5])) for k in pend],
            "phase 2 records with a 'format:' problem": 0, "phase 2 records": 0,
            "phase 1 records with a 'format:' problem": 0, "phase 1 records": 0,
        }
        for m in MODULES:
            p1, p2 = out / "phase1" / f"{m}.json", out / "phase2" / f"{m}.json"
            d = module_dir(m)
            inputs = {f: read(d / f) for f in ("rtl.txt", "closed_set.json", "diagram.txt")}
            if not p1.exists():
                rows.append({"version": version, "rep": rep, "module": m, "phase": 1, "missing": True, "rebuilds": False})
                continue
            r1 = json.loads(read(p1))
            row1 = check_record(version, rep, m, 1, r1, sys1, user_text(version, 1, m, inputs=inputs))
            rows.append(row1)
            per_run[f"r{rep}"]["phase 1 records"] += 1
            per_run[f"r{rep}"]["phase 1 records with a 'format:' problem"] += row1["format problems"] > 0
            if not p2.exists():
                rows.append({"version": version, "rep": rep, "module": m, "phase": 2, "missing": True, "rebuilds": False})
                continue
            r2 = json.loads(read(p2))
            # Phase 2's CONCEPTS block: Phase 1's "Conceptual Assets" as the model wrote it, re-read from the raw text
            concepts = parse_json(r1["raw"]).get("Conceptual Assets")
            cj = json.dumps(concepts, indent=1, ensure_ascii=False)
            row2 = check_record(version, rep, m, 2, r2, sys2, user_text(version, 2, m, cj, inputs=inputs))
            rows.append(row2)
            per_run[f"r{rep}"]["phase 2 records"] += 1
            per_run[f"r{rep}"]["phase 2 records with a 'format:' problem"] += row2["format problems"] > 0
    # the run meta files, recomputed from the prompt folder and the manifest
    meta_check = {}
    d = LAB / "prompts" / version
    want = {"system sha phase 1": sha12(sys1), "system sha phase 2": sha12(sys2),
            "user template sha phase 1": sha12(read(d / "phase1_user.md")),
            "user template sha phase 2": sha12(read(d / "phase2_user.md")),
            "inputs manifest sha": sha12(read(INPUTS / "manifest.json")),
            "prompt version": version, "input version": "v1", "model": MODEL, "effort": EFFORT}
    for rep in REPS:
        mp = run_dir(version, rep) / "_run_meta.json"
        stored = json.loads(read(mp)) if mp.exists() else {}
        meta_check[f"r{rep}"] = {k: stored.get(k) == v for k, v in want.items()}
    return {"rows": rows, "per run": per_run, "run meta matches": meta_check, "expected meta": want}


def selftest() -> bool:
    """Controls that the comparison can fail: (1) sha12 on a known string; (2) one real v9h record rebuilds; (3) the
    same record with one byte of the RTL changed does NOT rebuild (user sha and key differ, system sha still matches);
    (4) a record whose stored key is altered is caught; (5) a Phase 2 rebuilt with chain's indent=1 concepts matches
    but with indent=2 does not (so the concepts serialization is really being tested)."""
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"   {'ok  ' if cond else 'FAIL'} {label}")
    check("sha12('abc') = ba7816bf8f01", sha12("abc") == "ba7816bf8f01")
    v, m = "two_phase_v9h", "neorv32_xbus"
    out = run_dir(v, 0)
    r1 = json.loads(read(out / "phase1" / f"{m}.json"))
    r2 = json.loads(read(out / "phase2" / f"{m}.json"))
    d = module_dir(m)
    inputs = {f: read(d / f) for f in ("rtl.txt", "closed_set.json", "diagram.txt")}
    s1 = system_text(v, 1)
    a = check_record(v, 0, m, 1, r1, s1, user_text(v, 1, m, inputs=inputs))
    check("positive control: v9h r0 xbus Phase 1 rebuilds", a["rebuilds"])
    bad = dict(inputs, **{"rtl.txt": inputs["rtl.txt"].replace("signal", "signaL", 1)})
    check("one byte of the RTL changed: rtl.txt actually changed", bad["rtl.txt"] != inputs["rtl.txt"])
    b = check_record(v, 0, m, 1, r1, s1, user_text(v, 1, m, inputs=bad))
    check("negative control: altered RTL -> user sha and key mismatch, system sha still ok",
          b["system sha ok"] and not b["user sha ok"] and not b["request key ok"] and not b["rebuilds"])
    tam = json.loads(json.dumps(r1))
    tam["usage"]["request key"] = "000000000000"
    c = check_record(v, 0, m, 1, tam, s1, user_text(v, 1, m, inputs=inputs))
    check("tampered stored key is caught", c["system sha ok"] and c["user sha ok"] and not c["request key ok"] and not c["rebuilds"])
    concepts = parse_json(r1["raw"]).get("Conceptual Assets")
    s2 = system_text(v, 2)
    e1 = check_record(v, 0, m, 2, r2, s2, user_text(v, 2, m, json.dumps(concepts, indent=1, ensure_ascii=False), inputs=inputs))
    e2 = check_record(v, 0, m, 2, r2, s2, user_text(v, 2, m, json.dumps(concepts, indent=2, ensure_ascii=False), inputs=inputs))
    check("Phase 2 with indent=1 concepts rebuilds; indent=2 does not", e1["rebuilds"] and not e2["rebuilds"])
    probs = ["format: reply lacks ['Notes']", "C1: no point listed"]
    check("'format:' counter counts prefix only", sum(1 for p in probs if p.startswith("format:")) == 1)
    return ok


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("SELF-TEST")
    if not selftest():
        print("SELF-TEST FAILED; nothing reported")
        sys.exit(1)
    report = {}
    for v in ("two_phase_v9h", "two_phase_v9g"):
        res = verify(v)
        rows = res["rows"]
        n = len(rows)
        reb = [r for r in rows if r.get("rebuilds")]
        fail = [r for r in rows if not r.get("rebuilds")]
        print(f"\n== {v}: {len(reb)} of {n} records rebuild exactly (system sha, user sha and request key)")
        for r in fail:
            if r.get("missing"):
                print(f"   MISSING r{r['rep']} {r['module']} phase {r['phase']}")
            else:
                print(f"   MISMATCH r{r['rep']} {r['module']} phase {r['phase']}: stored {r['stored']} rebuilt {r['rebuilt']}")
        models = sorted({(r.get("model"), r.get("effort")) for r in rows if not r.get("missing")})
        parsed = sum(1 for r in rows if r.get("parsed reply"))
        meta_ok = sum(1 for r in rows if r.get("meta ok"))
        print(f"   model/effort stored: {models}")
        print(f"   records with a parsed reply: {parsed} of {n}")
        print(f"   records whose module/version/input version/phase fields match the path: {meta_ok} of {n}")
        for rep, x in res["per run"].items():
            f2, n2 = x["phase 2 records with a 'format:' problem"], x["phase 2 records"]
            f1, n1 = x["phase 1 records with a 'format:' problem"], x["phase 1 records"]
            print(f"   {rep}: asset files {x['asset files (all)']} (of the seven: {x['asset files (the seven)']}, "
                  f"missing {x['assets of the seven missing']}); Phase 2 records with a 'format:' problem: {f2} of {n2}; "
                  f"Phase 1: {f1} of {n1}; pending request files: {x['pending request files']}")
        for rep, x in res["run meta matches"].items():
            bad = [k for k, v2 in x.items() if not v2]
            print(f"   _run_meta.json {rep}: {'all fields match the recomputed values' if not bad else 'MISMATCH ' + str(bad)}")
        report[v] = {"records": n, "rebuild": len(reb),
                     "not rebuilding": [{k: r.get(k) for k in ('rep', 'module', 'phase', 'missing', 'stored', 'rebuilt')} for r in fail],
                     "model/effort": models, "parsed replies": parsed, "meta fields ok": meta_ok,
                     "per run": res["per run"], "run meta matches": res["run meta matches"]}
    (Path(__file__).parent / "verify_result.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwritten: {Path(__file__).parent / 'verify_result.json'}")


if __name__ == "__main__":
    main()
