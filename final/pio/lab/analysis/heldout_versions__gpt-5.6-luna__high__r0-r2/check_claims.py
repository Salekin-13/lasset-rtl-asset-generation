"""Code checks of the analysts' claims (workflow heldout-prompt-diagnosis-analyze), before any verification agent sees
them. Read-only on prompts and runs; reads claims_round1.json (the workflow's return value), writes claims_checked.json.

Per claim:
  - prompt lines: the file exists; the quote (whitespace-normalised, straight quotes) is in the cited line; if not, the
    line where it is; the role matches the step ("added in this step": in the later version's file, not in the earlier
    one's; "removed in this step": the reverse; "existing line, unchanged": in both);
  - reply evidence: the quote is in the stored raw reply of that version, run, phase and module (whitespace-normalised;
    the JSON-escaped and the parsed text are both tried);
  - elements: each "module:name" is a closed-set name of the module;
  - run change: recomputed from the assets files for every version with held-out runs (finds: runs found, summed over
    the elements; FPs: runs listed as FP), so the verifiers read code numbers, not the claim's.
A claim "passes the code checks" when every prompt quote and every reply quote is found and every element exists.
Self-test: a hand-made claim with a known prompt quote (v7 phase1.md, Access command fields) and a known reply quote
(v7 r2 cpu_counters Phase 1, the cnt_en Not Kept reason) passes; the same claim with one word changed in each quote fails.

  python check_claims.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import transitions as T  # noqa: E402

CV, CH, LAB = T.CV, T.CH, T.LAB
VNAME = {"v1": "two_phase_v1", "v2": "two_phase_v2", "v2a": "two_phase_v2a", "v3": "two_phase_v3", "v4": "two_phase_v4",
         "v4a": "two_phase_v4a", "v5": "two_phase_v5", "v5f": "two_phase_v5f", "v5g": "two_phase_v5g", "v6": "two_phase_v6",
         "v6abc": "two_phase_v6abc", "v6d": "two_phase_v6d", "v7": "two_phase_v7", "v8": "two_phase_v8"}


def norm(s):
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("\\\"", '"')
    s = s.replace("–", "-").replace("—", "-")
    return " ".join(s.split()).strip(" .\"'")


def vshort(v):
    v = (v or "").strip().lower().replace("two_phase_", "")
    return v if v.startswith("v") else "v" + v


def check_prompt(pl, step):
    f = (pl.get("file") or "").replace("\\", "/")
    m = re.search(r"two_phase_(v\w+)/(common|phase1|phase2)\.md", f)
    if not m:
        return {"ok": False, "why": f"file not recognised: {f}"}
    v, fn = m.group(1), m.group(2) + ".md"
    p = LAB / "prompts" / f"two_phase_{v}" / fn
    if not p.exists():
        return {"ok": False, "why": f"no such file {p.relative_to(LAB)}"}
    lines = p.read_text(encoding="utf-8").splitlines()
    q = norm(pl.get("quote"))
    if not q and pl.get("role", "").startswith("governing"):
        return {"ok": True, "why": "governing line, no quote"}
    ln = pl.get("line") or 0
    at = [i + 1 for i, l in enumerate(lines) if q and q in norm(l)]
    res = {"ok": bool(at), "found at lines": at, "cited line": ln, "line matches": ln in at}
    if not at:
        res["why"] = "quote not found in the file"
        return res
    parts = [vshort(x) for x in re.split(r"\s*->\s*", step)] if "->" in step else [None, None]
    a, b = parts[0], parts[-1]
    role = pl.get("role", "")
    if a in VNAME and b in VNAME:
        pa, pb = LAB / "prompts" / VNAME[a] / fn, LAB / "prompts" / VNAME[b] / fn
        ina = pa.exists() and q in norm(pa.read_text(encoding="utf-8"))
        inb = pb.exists() and q in norm(pb.read_text(encoding="utf-8"))
        res["in earlier version"], res["in later version"] = ina, inb
        if role == "added in this step" and (ina or not inb):
            res["role note"] = f"role 'added' but quote in {a}: {ina}, in {b}: {inb}"
        if role == "removed in this step" and (not ina or inb):
            res["role note"] = f"role 'removed' but quote in {a}: {ina}, in {b}: {inb}"
        if role == "existing line, unchanged" and not (ina and inb):
            res["role note"] = f"role 'unchanged' but quote in {a}: {ina}, in {b}: {inb}"
    return res


def check_reply(ev):
    v = VNAME.get(vshort(ev.get("version")))
    mod = (ev.get("module") or "").replace("neorv32_", "")
    try:
        r, ph = int(ev.get("run")), int(ev.get("phase"))
    except (TypeError, ValueError):
        return {"ok": False, "why": "run or phase not a number"}
    if not v:
        return {"ok": False, "why": f"version not recognised: {ev.get('version')}"}
    p = CH.run_dir(v, T.MODEL, r, T.EFF) / f"phase{ph}" / f"neorv32_{mod}.json"
    if not p.exists():
        return {"ok": False, "why": f"no reply file {v} r{r} phase{ph} {mod}"}
    rec = json.loads(p.read_text(encoding="utf-8"))
    q = norm(ev.get("quote"))
    hay = [norm(rec.get("raw")), norm(json.dumps(rec.get("reply"), ensure_ascii=False))]
    ok = bool(q) and any(q in h for h in hay)
    out = {"ok": ok}
    if not ok:
        # the same quote elsewhere (another run or phase of the module and version)?
        for rr in T.REPS:
            for pp in (1, 2):
                p2 = CH.run_dir(v, T.MODEL, rr, T.EFF) / f"phase{pp}" / f"neorv32_{mod}.json"
                if p2.exists() and q and q in norm(json.loads(p2.read_text(encoding="utf-8")).get("raw")):
                    out["found instead in"] = f"r{rr} phase{pp}"
        out["why"] = "quote not in the stored reply"
    return out


def run_counts(claim, groups, ref, listed):
    vs = list(CV.VERS)                                  # the whole trajectory, every version with held-out runs
    out, bad = {}, []
    fp = claim.get("effect") in ("removed FPs", "new FPs", "persistent FPs")
    for el in claim.get("elements") or []:
        if ":" not in el:
            bad.append(el)
            continue
        mod, n = el.split(":", 1)
        n = n.split("#")[0].strip()
        m = "neorv32_" + mod.strip().replace("neorv32_", "").lstrip("*")
        if m not in ref:
            bad.append(el)
            continue
        if n not in {x for (_, x) in CH.closed_names(m)}:
            bad.append(el)
            continue
        for v in vs:
            c = 0
            for r in T.REPS:
                names = listed(v, r, m)
                if fp:
                    left = Counter(ref[m])
                    for x in names:
                        if left[x] > 0:
                            left[x] -= 1
                        elif x == n:
                            c += 1
                else:
                    c += 1 if (n in names and n in ref[m]) else 0
            out[v[10:]] = out.get(v[10:], 0) + c
    return out, bad


def check(claim, groups, ref, listed):
    pls = [check_prompt(pl, claim.get("step") or "") for pl in claim.get("prompt_lines") or []]
    evs = [check_reply(ev) for ev in claim.get("reply_evidence") or []]
    counts, bad = run_counts(claim, groups, ref, listed)
    passes = all(x["ok"] for x in pls) and all(x["ok"] for x in evs) and not bad and bool(claim.get("elements"))
    return {"passes code checks": passes, "prompt lines": pls, "reply evidence": evs, "unknown elements": bad,
            ("FP runs per version (code)" if claim.get("effect") in ("removed FPs", "new FPs", "persistent FPs") else "runs found per version (code)"): counts}


def selftest(groups, ref, listed):
    good = {"step": "v5 -> v7", "effect": "lost finds", "elements": ["cpu_counters:cnt_en"],
            "prompt_lines": [{"file": "prompts/two_phase_v7/phase1.md", "line": 43, "role": "added in this step",
                              "quote": "a write enable whose assignment reads only these fields and that only lets a register take the written data"}],
            "reply_evidence": [{"version": "v7", "run": 2, "module": "cpu_counters", "phase": 1,
                                "quote": "cnt_en only paces the counter increment step"}]}
    bad = json.loads(json.dumps(good))
    bad["prompt_lines"][0]["quote"] = bad["prompt_lines"][0]["quote"].replace("written", "stored")
    bad["reply_evidence"][0]["quote"] = bad["reply_evidence"][0]["quote"].replace("paces", "times")
    g, b = check(good, groups, ref, listed), check(bad, groups, ref, listed)
    ok = g["passes code checks"] and not b["passes code checks"] and g["prompt lines"][0]["line matches"] \
        and "role note" not in g["prompt lines"][0] and {k: g["runs found per version (code)"][k] for k in ("v5", "v7")} == {"v5": 3, "v7": 0}
    print("self-test (known quotes pass, altered quotes fail, counts v5 3 / v7 0):", "PASS" if ok else f"FAIL {g} {b}")
    return ok


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, ref = CV.groups_and_ref()
    cache = {}

    def listed(v, r, m):
        if (v, r, m) not in cache:
            cache[(v, r, m)] = [x["Asset RTL"] for x in json.loads((CH.run_dir(v, T.MODEL, r, T.EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]]
        return cache[(v, r, m)]
    if not selftest(groups, ref, listed):
        sys.exit(1)
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "claims_round1.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    out, n, npass = [], 0, 0
    for grp in data.get("analysts", []) + data.get("filled", []):
        for c in grp.get("claims", []):
            n += 1
            res = check(c, groups, ref, listed)
            npass += res["passes code checks"]
            out.append({"analyst": grp.get("key"), "claim": c, "code check": res})
    (HERE / "claims_checked.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    pq = sum(len(o["code check"]["prompt lines"]) for o in out)
    pqok = sum(x["ok"] for o in out for x in o["code check"]["prompt lines"])
    rq = sum(len(o["code check"]["reply evidence"]) for o in out)
    rqok = sum(x["ok"] for o in out for x in o["code check"]["reply evidence"])
    print(f"claims {n}; pass all code checks {npass}; prompt quotes found {pqok}/{pq}; reply quotes found {rqok}/{rq}; "
          f"claims with unknown elements {sum(bool(o['code check']['unknown elements']) for o in out)}")
    for o in out:
        if not o["code check"]["passes code checks"]:
            cc = o["code check"]
            print(f"  FAIL {o['analyst']} {o['claim']['id']}: prompt {[x.get('why') or 'ok' for x in cc['prompt lines']]} "
                  f"reply {[x.get('why', 'ok') + (' (' + x['found instead in'] + ')' if x.get('found instead in') else '') for x in cc['reply evidence']]} "
                  f"unknown {cc['unknown elements'][:4]}")


if __name__ == "__main__":
    main()
