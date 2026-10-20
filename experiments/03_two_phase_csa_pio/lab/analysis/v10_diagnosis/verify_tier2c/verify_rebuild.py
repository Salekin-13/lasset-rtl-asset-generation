"""verify_tier2c: do the stored Phase 1 records of two_phase_p1t2_O4 and two_phase_p1t2_O5 (and the working version
two_phase_p1o_first, W) rebuild exactly from lab/prompts/<version> and lab/inputs/v1?

Re-implements (never imports from the run scripts): sha12, the system prompt (common.md.rstrip() + "\n\n" + phase1.md),
the user message (phase1_user.md formatted with module, rtl, diagram and the compact closed set), the request key
(sha12(system + "\n\n" + user)), the raw-reply parse, the LOCATED rule, and the Phase 1 block-title order.
Uses chain only for chain.closed_names and chain.run_dir. Sends nothing.

  python -B verify_rebuild.py          (prints the report; writes results.json next to this file)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]                                    # .../experiments/03_two_phase_csa_pio/lab
ROOT = LAB.parents[2]                                    # .../Prepoison_subset
sys.path.insert(0, str(LAB))
import chain  # noqa: E402  (only chain.closed_names and chain.run_dir are used)

PROMPTS = LAB / "prompts"
HELDOUT = LAB / "inputs" / "v1" / "heldout"
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
BASE = "two_phase_p1o_first2"
VERSIONS = ["two_phase_p1o_first", "two_phase_p1t2_O4", "two_phase_p1t2_O5"]
MODEL, EFFORT, REPS = "gpt-5.6-luna", "high", (0, 1, 2)
ASSIGN_KEYS = ("gets value from", "decided by", "reset by", "clocked by")


# ------------------------------------------------------------------------------------------------ re-implemented pieces
def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")       # same call as chain: universal newlines


def system_text(version: str) -> str:
    d = PROMPTS / version
    return read(d / "common.md").rstrip() + "\n\n" + read(d / "phase1.md")


def user_text(version: str, m: str) -> str:
    d = HELDOUT / m
    vals = {"module": m, "rtl": read(d / "rtl.txt"), "diagram": read(d / "diagram.txt"),
            "closed_set": json.dumps(json.loads(read(d / "closed_set.json")), separators=(",", ":"))}
    return read(PROMPTS / version / "phase1_user.md").format(**vals)


def parse_raw(text: str):
    """The stored raw reply -> JSON object, or None when it does not parse."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < 0:
        return None
    try:
        return json.loads(t[a:b + 1])
    except ValueError:
        return None


def concepts_of(obj) -> list[dict] | None:
    """The "Conceptual Assets" list when it is a list of objects, else None."""
    if not isinstance(obj, dict):
        return None
    ca = obj.get("Conceptual Assets")
    if not isinstance(ca, list) or not all(isinstance(c, dict) for c in ca):
        return None
    return ca


def assignment_lines(m: str) -> dict[str, set[int]]:
    """name -> union over every entity carrying the name of the integer "lines" of its counterparts under
    gets value from, decided by, reset by, clocked by."""
    out: dict[str, set[int]] = {}
    for (_, name), entry in chain.closed_names(m).items():
        ls = out.setdefault(name, set())
        for key in ASSIGN_KEYS:
            for c in (entry.get("counterparts") or {}).get(key, []) or []:
                if isinstance(c, dict):
                    for l in c.get("lines") or []:
                        if isinstance(l, int) and not isinstance(l, bool):
                            ls.add(l)
    return out


def _as_list(v):
    return v if isinstance(v, list) else ([v] if isinstance(v, str) else [])


def located_union(m: str, concepts: list[dict], names: set[str], assign: dict[str, set[int]]) -> set[str]:
    """The union over the entries of the names each one locates (LOCATED rule)."""
    out: set[str] = set()
    for c in concepts:
        ports = [p for p in _as_list(c.get("Enters Through")) + _as_list(c.get("Leaves Through")) if isinstance(p, str)]
        held = {l for l in _as_list(c.get("Held Lines")) if isinstance(l, int) and not isinstance(l, bool)}
        out |= {p for p in ports if p in names}
        out |= {x for x, ls in assign.items() if ls & held}
    return out


def block_titles(text: str) -> list[tuple[int, str]]:
    """(line number, title) of each line starting "- ", title = the text up to the first period."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("- "):
            body = line[2:]
            j = body.find(".")
            out.append((i, body[:j] if j >= 0 else body))
    return out


def lcs(a: list, b: list) -> list:
    n, k = len(a), len(b)
    dp = [[0] * (k + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(k - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if a[i] == b[j] else max(dp[i + 1][j], dp[i][j + 1])
    out, i, j = [], 0, 0
    while i < n and j < k:
        if a[i] == b[j]:
            out.append(a[i]); i += 1; j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


# ------------------------------------------------------------------------------------------------ self-test
def selftest() -> list[str]:
    """Hand-read cases. Every figure below is printed only when this list is empty."""
    fails = []

    def check(label, cond):
        if not cond:
            fails.append(label)
    check("sha12 of 'abc' = first 12 hex of sha256", sha12("abc") == "ba7816bf8f01")
    # titles: hand-written snippet
    t = block_titles("intro\n- Port buffers (a). text here.\n  - not a title.\n- Precedence. A rule's bar\n- No period here\n")
    check("block titles from a hand-written snippet", t == [(2, "Port buffers (a)"), (4, "Precedence"), (5, "No period here")])
    check("lcs of hand-made orders", lcs(["a", "b", "c", "d"], ["b", "a", "c", "d"]) in (["a", "c", "d"], ["b", "c", "d"]))
    # LOCATED: neorv32_gpio closed set, hand-read: port_in gets value from gpio_i at line 103, clocked by clk_i at 102,
    # reset by rstn_i at 99; port_out gets value from bus_req_i.data at 74, decided by lines 71-73, clocked 64, reset 57
    g = "neorv32_gpio"
    asg = assignment_lines(g)
    check("gpio port_in assignment lines {99,102,103}", asg.get("port_in") == {99, 102, 103})
    check("gpio port_out assignment lines {57,64,71,72,73,74}", asg.get("port_out") == {57, 64, 71, 72, 73, 74})
    names = {x for (_, x) in chain.closed_names(g)}
    loc = located_union(g, [{"Concept ID": "C1", "Enters Through": ["gpio_i", "nope_i"], "Leaves Through": "gpio_o",
                             "Held Lines": [103]}], names, asg)
    check("LOCATED: ports kept only when closed-set names; held line 103 locates port_in, not port_out",
          "gpio_i" in loc and "gpio_o" in loc and "nope_i" not in loc and "port_in" in loc and "port_out" not in loc)
    loc2 = located_union(g, [{"Concept ID": "C2", "Held Lines": ["74", 74.0]}], names, asg)
    check("LOCATED: non-integer held lines are ignored", loc2 == set())
    # rebuild pieces
    u = user_text("two_phase_p1t2_O4", g)
    check("user message starts with MODULE: neorv32_gpio", u.startswith("MODULE: neorv32_gpio\n"))
    check("closed set is compact in the user message", '"module name":"neorv32_gpio"' in u and '"module name": "' not in u)
    s = system_text("two_phase_p1t2_O4")
    check("system = common.rstrip + two newlines + phase1", s.endswith(read(PROMPTS / "two_phase_p1t2_O4" / "phase1.md"))
          and "\n\n" + read(PROMPTS / "two_phase_p1t2_O4" / "phase1.md") in s and not s.startswith("\n"))
    check("a one-character change to the system text changes its sha12", sha12(s) != sha12(s + " "))
    check("parse_raw reads fenced JSON", parse_raw("```json\n{\"IP\": \"x\", \"Conceptual Assets\": []}\n```") == {"IP": "x", "Conceptual Assets": []})
    check("parse_raw returns None on junk", parse_raw("no braces here") is None and parse_raw("{bad json}") is None)
    return fails


# ------------------------------------------------------------------------------------------------ the checks
def reference(modules: list[str]) -> dict[str, list[str]]:
    """module -> reference elements that are closed-set names of the module (rows kept, duplicates kept as rows)."""
    g = json.loads(read(GT))["modules"]
    out = {}
    for m in modules:
        names = {x for (_, x) in chain.closed_names(m)}
        rows = g.get(m, {}).get("assets", []) if isinstance(g.get(m), dict) else []
        out[m] = [r.get("element") for r in rows if isinstance(r, dict) and r.get("element") in names]
    return out


def check_version(version: str, modules: list[str], ref: dict[str, list[str]]) -> dict:
    sys_t = system_text(version)
    sys_sha = sha12(sys_t)
    tmpl_sha = sha12(read(PROMPTS / version / "phase1_user.md"))
    users = {m: user_text(version, m) for m in modules}
    assign = {m: assignment_lines(m) for m in modules}
    names = {m: {x for (_, x) in chain.closed_names(m)} for m in modules}
    n_ref = sum(len(v) for v in ref.values())
    res = {"version": version, "rebuilt system sha phase 1": sys_sha, "rebuilt user template sha phase 1": tmpl_sha,
           "runs": {}}
    all_ids, all_raw = [], []
    for k in REPS:
        d = chain.run_dir(version, MODEL, k, EFFORT)
        row = {"run dir": str(d), "exists": d.exists()}
        if not d.exists():
            res["runs"][f"r{k}"] = row
            continue
        files = sorted(p.stem for p in (d / "phase1").glob("*.json")) if (d / "phase1").exists() else []
        present = [m for m in modules if m in files]
        row["phase1 files"] = len(files)
        row["of the 26 present"] = len(present)
        row["missing modules"] = [m for m in modules if m not in files]
        row["extra files (not one of the 26)"] = [f for f in files if f not in modules]
        meta = json.loads(read(d / "_run_meta.json")) if (d / "_run_meta.json").exists() else None
        row["_run_meta"] = None if meta is None else {
            "prompt version": meta.get("prompt version"), "model": meta.get("model"), "effort": meta.get("effort"),
            "executor": meta.get("executor"), "input version": meta.get("input version"),
            "system sha phase 1 matches rebuilt": meta.get("system sha phase 1") == sys_sha,
            "user template sha phase 1 matches rebuilt": meta.get("user template sha phase 1") == tmpl_sha}
        pend = sorted(p.name for p in (d / "_pending").iterdir()) if (d / "_pending").exists() else None
        row["_pending files"] = pend
        other = sorted(p.name for p in d.iterdir() if p.is_dir() and p.name.startswith("_") and p.name != "_pending")
        row["other _ folders"] = {n: sorted(q.name for q in (d / n).iterdir()) for n in other}
        row["_failed_calls.jsonl lines"] = (len([l for l in read(d / "_failed_calls.jsonl").splitlines() if l.strip()])
                                            if (d / "_failed_calls.jsonl").exists() else 0)
        keys_lines = [json.loads(l) for l in read(d / "_keys.jsonl").splitlines() if l.strip()] if (d / "_keys.jsonl").exists() else []
        kc = Counter(x.get("key") for x in keys_lines)
        row["_keys.jsonl"] = {"lines": len(keys_lines), "distinct keys": len(kc),
                              "keys written more than once": {k_: n for k_, n in kc.items() if n > 1},
                              "modules of those": sorted({x.get("module") for x in keys_lines if kc[x.get("key")] > 1})}
        # per record
        rebuilt = mism = 0
        mism_list, meta_bad, parsed, stored_parsed, probs = [], [], 0, 0, Counter()
        models, efforts, key_ok, key_in_log = Counter(), Counter(), 0, 0
        located_n, located_mods = 0, 0
        for m in present:
            rec = json.loads(read(d / "phase1" / f"{m}.json"))
            u_sha = sha12(users[m])
            req_key = sha12(sys_t + "\n\n" + users[m])
            ok_s, ok_u = rec.get("system sha") == sys_sha, rec.get("user sha") == u_sha
            if ok_s and ok_u:
                rebuilt += 1
            else:
                mism += 1
                mism_list.append({"module": m, "system sha stored": rec.get("system sha"), "system sha rebuilt": sys_sha,
                                  "user sha stored": rec.get("user sha"), "user sha rebuilt": u_sha})
            fields = {"module": m, "prompt version": version, "input version": "v1", "phase": 1}
            bad = {f: rec.get(f) for f, want in fields.items() if rec.get(f) != want}
            if bad:
                meta_bad.append({"module": m, **bad})
            usage = rec.get("usage") or {}
            models[usage.get("model")] += 1
            efforts[usage.get("effort")] += 1
            if usage.get("request key") == req_key:
                key_ok += 1
            if req_key in kc:
                key_in_log += 1
            all_ids.append(usage.get("response id"))
            all_raw.append(rec.get("raw"))
            obj = parse_raw(rec.get("raw") or "")
            ca = concepts_of(obj)
            if ca is not None:
                parsed += 1
                located_mods += 1
                loc = located_union(m, ca, names[m], assign[m])
                located_n += sum(1 for e in ref[m] if e in loc)
            if isinstance(rec.get("reply"), dict) and isinstance(rec["reply"].get("conceptual assets"), list):
                stored_parsed += 1
            for p in rec.get("problems") or []:
                s = str(p)
                probs["unparseable" if s.startswith("unparseable") else "check crashed" if s.startswith("check crashed")
                      else "not checked yet" if s == "not checked yet" else "other"] += 1
        row["records"] = {"rebuilt (system and user sha match)": rebuilt, "mismatches": mism, "mismatch list": mism_list,
                          "request key = sha12(system + 2 newlines + user)": key_ok,
                          "request key found in _keys.jsonl": key_in_log,
                          "meta fields wrong (module/prompt version/input version/phase)": meta_bad,
                          "model": dict(models), "effort": dict(efforts),
                          "raw parses to a 'Conceptual Assets' list of objects (own parse)": parsed,
                          "stored 'reply' has a 'conceptual assets' list": stored_parsed,
                          "problem kinds": dict(probs),
                          "reference entries located (own LOCATED rule)": located_n,
                          "reference entries total": n_ref,
                          "modules with a parsed reply used for located": located_mods}
        res["runs"][f"r{k}"] = row
    idc = Counter(x for x in all_ids if x)
    rc = Counter(x for x in all_raw if x)
    res["across the three runs"] = {"records": len(all_ids), "missing response id": sum(1 for x in all_ids if not x),
                                    "response ids repeated": {k_: n for k_, n in idc.items() if n > 1},
                                    "identical raw texts": sum(n - 1 for n in rc.values() if n > 1)}
    return res


def title_report(version: str) -> dict:
    base_t = block_titles(read(PROMPTS / BASE / "phase1.md"))
    ver_t = block_titles(read(PROMPTS / version / "phase1.md"))
    b, v = [t for _, t in base_t], [t for _, t in ver_t]
    common = lcs(b, v)
    moved = [t for t in v if t in b and t not in common]
    bpos, vpos = {t: i + 1 for i, t in enumerate(b)}, {t: i + 1 for i, t in enumerate(v)}
    base_text, ver_text = read(PROMPTS / BASE / "phase1.md"), read(PROMPTS / version / "phase1.md")

    def out_line(text):
        return next((i for i, l in enumerate(text.splitlines(), 1) if l.startswith("OUTPUT")), None)
    return {"version": version, "titles": len(v), "base titles": len(b),
            "set identical to base": set(v) == set(b) and Counter(v) == Counter(b),
            "only in version": [t for t in v if t not in b], "only in base": [t for t in b if t not in v],
            "order identical to base": v == b,
            "blocks moved (not in the longest common subsequence)": [{"title": t, "base position": bpos[t], "version position": vpos[t]} for t in moved],
            "kept in base order": len(common),
            "first '- ' line": {"base": base_t[0][0] if base_t else None, "version": ver_t[0][0] if ver_t else None},
            "OUTPUT heading line": {"base": out_line(base_text), "version": out_line(ver_text)},
            "phase1.md lines": {"base": len(base_text.splitlines()), "version": len(ver_text.splitlines())},
            "phase1.md identical to base": ver_text == base_text,
            "version order": v}


def main() -> int:
    fails = selftest()
    if fails:
        print("SELF-TEST FAILED; nothing reported:")
        for f in fails:
            print("  FAIL", f)
        return 1
    print("self-test: all hand-read checks pass")
    modules = sorted(p.name for p in HELDOUT.iterdir() if p.is_dir())
    tuning_overlap = sorted(m for m in modules if (LAB / "inputs" / "v1" / "tuning" / m).exists())
    ref = reference(modules)
    n_ref = sum(len(v) for v in ref.values())
    out = {"group": {"heldout folders": len(modules), "also under tuning": tuning_overlap,
                     "reference entries (element is a closed-set name)": n_ref,
                     "per module": {m: len(v) for m, v in ref.items()}},
           "model": MODEL, "effort": EFFORT, "base for titles": BASE,
           "versions": {v: check_version(v, modules, ref) for v in VERSIONS},
           "titles": {v: title_report(v) for v in VERSIONS}}
    (HERE / "results.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    # plain print
    print(f"group: {len(modules)} heldout folders; also under tuning: {tuning_overlap}; reference entries kept: {n_ref}")
    for v in VERSIONS:
        r = out["versions"][v]
        print(f"\n== {v}: rebuilt system sha {r['rebuilt system sha phase 1']}, user template sha {r['rebuilt user template sha phase 1']}")
        for k, row in r["runs"].items():
            if not row.get("exists"):
                print(f"  {k}: run dir missing")
                continue
            rec = row["records"]
            print(f"  {k}: phase1 files {row['phase1 files']}, of the 26 present {row['of the 26 present']}, missing {row['missing modules']}, extra {row['extra files (not one of the 26)']}")
            print(f"      rebuilt {rec['rebuilt (system and user sha match)']}, mismatches {rec['mismatches']}, request-key match {rec['request key = sha12(system + 2 newlines + user)']}, key in _keys {rec['request key found in _keys.jsonl']}, meta wrong {rec['meta fields wrong (module/prompt version/input version/phase)']}")
            print(f"      model {rec['model']}, effort {rec['effort']}; parsed (own) {rec['raw parses to a \'Conceptual Assets\' list of objects (own parse)']}, stored reply list {rec['stored \'reply\' has a \'conceptual assets\' list']}, problems {rec['problem kinds']}")
            print(f"      located {rec['reference entries located (own LOCATED rule)']} of {rec['reference entries total']} (modules used {rec['modules with a parsed reply used for located']})")
            print(f"      _run_meta {row['_run_meta']}")
            print(f"      _pending {row['_pending files']}; other _ folders {row['other _ folders']}; failed-calls lines {row['_failed_calls.jsonl lines']}; _keys {row['_keys.jsonl']}")
        print(f"  across runs: {r['across the three runs']}")
    for v in VERSIONS:
        t = out["titles"][v]
        print(f"\n== titles {v} vs {BASE}: n {t['titles']} vs {t['base titles']}; set identical {t['set identical to base']}; order identical {t['order identical to base']}; phase1.md identical {t['phase1.md identical to base']}")
        print(f"   only in version {t['only in version']}; only in base {t['only in base']}; kept in base order {t['kept in base order']}")
        first = t["first '- ' line"]
        print(f"   first '- ' line {first}; OUTPUT heading line {t['OUTPUT heading line']}; lines {t['phase1.md lines']}")
        print(f"   moved ({len(t['blocks moved (not in the longest common subsequence)'])}):")
        for x in t["blocks moved (not in the longest common subsequence)"]:
            print(f"     {x['title']}: base {x['base position']} -> version {x['version position']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
