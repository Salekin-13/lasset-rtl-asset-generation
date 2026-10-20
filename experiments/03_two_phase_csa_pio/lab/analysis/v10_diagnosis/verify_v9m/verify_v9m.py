"""Independent rebuild check of the stored two_phase_v9m records (gpt-5.6-luna, high, r0-r2, 41 modules).

Rebuilds every system and user message from prompts/two_phase_v9m and inputs/v1 with its own code (own sha12, own
JSON parse, own LOCATED rule, own exact scorer) and compares the sha12s with the stored "system sha", "user sha" and
usage "request key". Imports chain only for chain.closed_names and chain.run_dir. Sends nothing.

  python -B verify_v9m.py          (self-test first; nothing is reported if it fails)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
ROOT = Path(r"E:\jobs\ff\test\Prepoison_subset")
LAB = ROOT / "experiments" / "03_two_phase_csa_pio" / "lab"
if str(LAB) not in sys.path:
    sys.path.insert(0, str(LAB))
import chain  # noqa: E402  (only chain.closed_names and chain.run_dir are used)

VERSION, MODEL, EFFORT, REPS = "two_phase_v9m", "gpt-5.6-luna", "high", (0, 1, 2)
PROMPTS = LAB / "prompts" / VERSION
INPUTS = LAB / "inputs" / "v1"
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
SPLIT = LAB / "splits" / "tuning_v2.json"
HERE = Path(__file__).resolve().parent
ASSIGN_KEYS = ("gets value from", "decided by", "reset by", "clocked by")


# ------------------------------------------------------------------------------------------------ own helpers ---
def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def parse_json(text: str):
    """The reply text -> JSON object: optional code fence stripped, first '{' to last '}'."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    return json.loads(t[t.find("{"): t.rfind("}") + 1])


def is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def system_text(phase: int) -> str:
    return (PROMPTS / "common.md").read_text(encoding="utf-8").rstrip() + "\n\n" + \
        (PROMPTS / f"phase{phase}.md").read_text(encoding="utf-8")


def module_dir(m: str) -> Path:
    for split in ("tuning", "heldout"):
        if (INPUTS / split / m).is_dir():
            return INPUTS / split / m
    raise FileNotFoundError(m)


_INPUTS: dict[str, dict] = {}


def inputs(m: str) -> dict:
    if m not in _INPUTS:
        d = module_dir(m)
        _INPUTS[m] = {f: (d / f).read_text(encoding="utf-8") for f in ("rtl.txt", "closed_set.json", "diagram.txt")}
    return _INPUTS[m]


_NAMES: dict[str, tuple[set, dict, dict]] = {}


def name_tables(m: str) -> tuple[set, dict, dict]:
    """(closed-set names of any entity, name -> assignment lines, counts of irregular 'lines' entries)."""
    if m not in _NAMES:
        cn = chain.closed_names(m)
        names = {n for (_, n) in cn}
        assign: dict[str, set] = {}
        odd = Counter()
        for (_, n), entry in cn.items():
            ls = assign.setdefault(n, set())
            cps = entry.get("counterparts") or {}
            for key in ASSIGN_KEYS:
                for c in cps.get(key) or []:
                    if not isinstance(c, dict):
                        odd["counterpart not an object"] += 1
                        continue
                    for l in c.get("lines") or []:
                        if is_int(l):
                            ls.add(l)
                        else:
                            odd["non-integer line in counterparts"] += 1
        _NAMES[m] = (names, assign, odd)
    return _NAMES[m]


def located(m: str, concepts, stats: Counter | None = None) -> dict:
    """The LOCATED rule, re-implemented from the task text: per Phase 1 entry (keys as written), the sorted closed-set
    names that are listed in Enters Through / Leaves Through, or have an assignment line among the Held Lines."""
    names, assign, _ = name_tables(m)
    stats = stats if stats is not None else Counter()

    def as_list(v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            stats["port field given as one string"] += 1
            return [v]
        if v is not None:
            stats["port field neither list nor string"] += 1
        return []
    out = {}
    for c in concepts or []:
        if not isinstance(c, dict):
            stats["entry not an object"] += 1
            continue
        cid = c.get("Concept ID")
        if not cid:
            stats["entry without Concept ID"] += 1
            continue
        if str(cid) in out:
            stats["duplicate Concept ID"] += 1
        ports = [p for p in as_list(c.get("Enters Through")) + as_list(c.get("Leaves Through")) if isinstance(p, str)]
        hl = c.get("Held Lines")
        if not isinstance(hl, list):
            stats["Held Lines not a list"] += 1
            hl = []
        held = set()
        for l in hl:
            if is_int(l):
                held.add(l)
            else:
                stats["non-integer Held Lines entry"] += 1
        out[str(cid)] = sorted({p for p in ports if p in names} | {n for n, ls in assign.items() if ls & held})
    return out


def user_text(phase: int, m: str, concepts=None, stats: Counter | None = None) -> str:
    x = inputs(m)
    t = (PROMPTS / f"phase{phase}_user.md").read_text(encoding="utf-8")
    vals = {"module": m, "rtl": x["rtl.txt"], "diagram": x["diagram.txt"],
            "closed_set": json.dumps(json.loads(x["closed_set.json"]), separators=(",", ":"))}
    if phase == 2:
        vals["concepts"] = json.dumps(concepts, indent=1, ensure_ascii=False)
        vals["located"] = json.dumps(located(m, concepts, stats), indent=1, ensure_ascii=False)
    return t.format(**vals)


def score(listed: list[str], reference: list[str]) -> tuple[int, int, int]:
    """Exact scorer: (correct, listed, findable). Reference rows walked in order; a row whose element still has an
    unconsumed listed copy consumes one and counts correct."""
    have = Counter(listed)
    correct = 0
    for r in reference:
        if have[r] > 0:
            have[r] -= 1
            correct += 1
    return correct, len(listed), len(reference)


# ------------------------------------------------------------------------------------------------ self-test ---
def selftest() -> list[str]:
    """Hand-read cases (neorv32_wdt RTL and closed set, read on 2026-10-18) and known sha256 values."""
    fails = []

    def check(label, cond):
        if not cond:
            fails.append(label)
    check("sha12('') = e3b0c44298fc", sha12("") == "e3b0c44298fc")
    check("sha12('abc') = ba7816bf8f01", sha12("abc") == "ba7816bf8f01")
    check("parse_json strips a code fence", parse_json("```json\n{\"a\": 1}\n```") == {"a": 1})
    check("parse_json takes first { to last }", parse_json("x {\"a\": [1, {\"b\": 2}]} y") == {"a": [1, {"b": 2}]})
    check("scorer: ['a','a','b'] vs ['a','c','a','a'] -> (2, 3, 4)", score(["a", "a", "b"], ["a", "c", "a", "a"]) == (2, 3, 4))
    check("scorer: empty listed -> (0, 0, n)", score([], ["a"]) == (0, 0, 1))
    w = "neorv32_wdt"
    names, assign, odd = name_tables(w)
    # hand-read: ctrl.enable gets value from bus_req_i.data (94), decided by addr 92 / rw 91 / stb 90 / lock 93,
    # reset by rstn_sys_i (73), clocked by clk_i (81)
    check("wdt ctrl.enable assignment lines = {73, 81, 90, 91, 92, 93, 94}", assign.get("ctrl.enable") == {73, 81, 90, 91, 92, 93, 94})
    c = [{"Concept ID": "C1", "Enters Through": ["bus_req_i.data", "not_a_name"], "Leaves Through": [], "Held Lines": [94]},
         {"Concept ID": "C2", "Enters Through": [], "Leaves Through": ["clkgen_en_o"], "Held Lines": [130]},
         {"Concept ID": "C3", "Enters Through": [], "Leaves Through": [], "Held Lines": [131]},
         {"Concept ID": "C4", "Enters Through": [], "Leaves Through": [], "Held Lines": [999]},
         {"Concept ID": "C5", "Enters Through": "clk_i", "Leaves Through": [], "Held Lines": []},
         {"Concept Name": "no id"}, "not an object"]
    st = Counter()
    loc = located(w, c, st)
    # line 94: only ctrl.enable is assigned; line 130: only cnt_started; line 131: the condition that decides cnt
    check("LOCATED C1 (held 94, enters bus_req_i.data) = [bus_req_i.data, ctrl.enable]", loc.get("C1") == ["bus_req_i.data", "ctrl.enable"])
    check("LOCATED C2 (held 130, leaves clkgen_en_o) = [clkgen_en_o, cnt_started]", loc.get("C2") == ["clkgen_en_o", "cnt_started"])
    check("LOCATED C3 (held 131) = [cnt]", loc.get("C3") == ["cnt"])
    check("LOCATED C4 (held 999) = []", loc.get("C4") == [])
    check("LOCATED C5 (enters 'clk_i' as a string) = [clk_i]", loc.get("C5") == ["clk_i"])
    check("LOCATED keeps entry order and skips entries without an id", list(loc) == ["C1", "C2", "C3", "C4", "C5"])
    check("LOCATED stats count the irregular entries", st["entry without Concept ID"] == 1 and st["entry not an object"] == 1
          and st["port field given as one string"] == 1)
    check("system text = common.rstrip + 2 newlines + phase", system_text(1).startswith((PROMPTS / "common.md").read_text(encoding="utf-8").rstrip() + "\n\n")
          and system_text(1).endswith((PROMPTS / "phase1.md").read_text(encoding="utf-8")))
    return fails


# ------------------------------------------------------------------------------------------------ main ---
def main() -> int:
    fails = selftest()
    if fails:
        print("SELF-TEST FAILED; nothing reported:")
        for f in fails:
            print("  FAIL", f)
        return 1
    print("self-test: all cases pass")

    gt = json.loads(GT.read_text(encoding="utf-8"))["modules"]
    tuning_dirs = sorted(p.name for p in (INPUTS / "tuning").iterdir() if p.is_dir())
    heldout_dirs = sorted(p.name for p in (INPUTS / "heldout").iterdir() if p.is_dir())
    tuning15 = [m for m in tuning_dirs if m in gt and gt[m]["assets"]]
    heldout26 = list(heldout_dirs)
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    groups = {"tuning 15": tuning15, "held-out 26": heldout26, "tuning_v2": list(split["tuning"]),
              "heldout_v2": list(split["heldout"])}
    modules = sorted(set(tuning15) | set(heldout26))
    group_check = {
        "tuning folders": len(tuning_dirs), "tuning folders without a reference row": [m for m in tuning_dirs if m not in tuning15],
        "held-out folders": len(heldout_dirs), "held-out folders without a reference row": [m for m in heldout26 if m not in gt or not gt[m]["assets"]],
        "modules (union)": len(modules),
        "tuning_v2 + heldout_v2 == union": sorted(set(split["tuning"]) | set(split["heldout"])) == modules and not (set(split["tuning"]) & set(split["heldout"])),
        "group sizes": {g: len(ms) for g, ms in groups.items()}}

    # reference rows kept: element is a closed-set name of the module (any entity)
    ref_rows, ref_dropped = {}, {}
    for m in modules:
        names, _, _ = name_tables(m)
        rows = [r.get("element") for r in gt[m]["assets"]]
        ref_rows[m] = [e for e in rows if e in names]
        ref_dropped[m] = [e for e in rows if e not in names]

    sys_sha = {ph: sha12(system_text(ph)) for ph in (1, 2)}
    tmpl_sha = {ph: sha12((PROMPTS / f"phase{ph}_user.md").read_text(encoding="utf-8")) for ph in (1, 2)}
    man_sha = sha12((INPUTS / "manifest.json").read_text(encoding="utf-8"))

    out = {"version": VERSION, "model": MODEL, "effort": EFFORT, "runs": {}, "group check": group_check,
           "rebuilt system sha": sys_sha, "rebuilt user template sha": tmpl_sha, "rebuilt inputs manifest sha": man_sha,
           "reference rows dropped (element not a closed-set name)": {m: d for m, d in ref_dropped.items() if d}}
    mismatches, located_sizes, located_stats = [], [], Counter()
    closed_set_odd = Counter()
    for m in modules:
        closed_set_odd.update(name_tables(m)[2])
    models, efforts = Counter(), Counter()
    scores = {g: {} for g in groups}

    for k in REPS:
        rd = chain.run_dir(VERSION, MODEL, k, EFFORT)
        meta = json.loads((rd / "_run_meta.json").read_text(encoding="utf-8"))
        meta_ok = {"prompt version": meta.get("prompt version") == VERSION, "input version": meta.get("input version") == "v1",
                   "model": meta.get("model") == MODEL, "effort": meta.get("effort") == EFFORT,
                   "executor": meta.get("executor"), "system sha phase 1": meta.get("system sha phase 1") == sys_sha[1],
                   "system sha phase 2": meta.get("system sha phase 2") == sys_sha[2],
                   "user template sha phase 1": meta.get("user template sha phase 1") == tmpl_sha[1],
                   "user template sha phase 2": meta.get("user template sha phase 2") == tmpl_sha[2],
                   "inputs manifest sha": meta.get("inputs manifest sha") == man_sha}
        files = {d: sorted(p.stem for p in (rd / d).glob("*.json")) for d in ("phase1", "phase2", "assets")}
        extra = {d: [x for x in fs if x not in modules] for d, fs in files.items()}
        missing = {d: [x for x in modules if x not in fs] for d, fs in files.items()}
        keys = {}
        kl = rd / "_keys.jsonl"
        if kl.exists():
            for l in kl.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    x = json.loads(l)
                    keys[x["key"]] = (x.get("module"), x.get("phase"))
        run = {"records": 0, "rebuilt (system and user sha match)": 0, "request key matches sha12(system+2 newlines+user)": 0,
               "parsed (own parse of 'raw')": 0, "stored 'reply' is an object": 0,
               "records with problems 'not checked yet' / unparseable / check crashed": 0,
               "phase 1 with a 'Conceptual Assets' list": 0, "phase 2 rebuildable (phase 1 list read)": 0,
               "phase 2 records with a 'format:' problem": 0, "phase 2 'format:' problems (module: problems)": {},
               "phase 1 records with any problem": 0, "phase 2 records with any problem": 0,
               "files": {d: len(fs) for d, fs in files.items()}, "files not in the 41": extra, "files missing": missing,
               "_run_meta check": meta_ok, "_keys.jsonl keys": len(keys),
               "_pending files": sorted(p.name for p in (rd / "_pending").iterdir()) if (rd / "_pending").exists() else "(no folder)",
               "_failed files": sorted(p.name for p in (rd / "_failed").iterdir()) if (rd / "_failed").exists() else "(no folder)",
               "_failed_calls.jsonl": [], "_schema_failed": sorted(str(p.relative_to(rd)) for p in (rd / "_schema_failed").rglob("*")) if (rd / "_schema_failed").exists() else "(no folder)",
               "concepts (LOCATED entries)": 0}
        fl = rd / "_failed_calls.jsonl"
        if fl.exists():
            for l in fl.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    x = json.loads(l)
                    mod, ph = keys.get(x.get("key"), (None, None))
                    run["_failed_calls.jsonl"].append({"key": x.get("key"), "status": x.get("status"), "reason": x.get("reason"),
                                                       "module": mod, "phase": ph, "stored record now": None})
        request_keys = {}
        listed = {}
        for m in modules:
            p1 = json.loads((rd / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
            concepts = None
            try:
                obj = parse_json(p1["raw"])
                p1_parsed = True
                ca = obj.get("Conceptual Assets") if isinstance(obj, dict) else None
                if isinstance(ca, list):
                    concepts = ca
                    run["phase 1 with a 'Conceptual Assets' list"] += 1
            except ValueError:
                p1_parsed = False
            texts = {1: (system_text(1), user_text(1, m))}
            if concepts is not None:
                run["phase 2 rebuildable (phase 1 list read)"] += 1
                loc = located(m, concepts, located_stats)
                located_sizes += [(len(v), k, m, cid) for cid, v in loc.items()]
                run["concepts (LOCATED entries)"] += len(loc)
                texts[2] = (system_text(2), user_text(2, m, concepts, Counter()))
            for ph, rec in ((1, p1), (2, json.loads((rd / "phase2" / f"{m}.json").read_text(encoding="utf-8")))):
                run["records"] += 1
                u = rec.get("usage") or {}
                models[u.get("model")] += 1
                efforts[u.get("effort")] += 1
                if ph == 1:
                    parsed = p1_parsed
                else:
                    try:
                        parse_json(rec["raw"])
                        parsed = True
                    except ValueError:
                        parsed = False
                run["parsed (own parse of 'raw')"] += parsed
                run["stored 'reply' is an object"] += isinstance(rec.get("reply"), dict)
                probs = rec.get("problems") or []
                if rec.get("check crashed") or probs == ["not checked yet"] or any(str(p).startswith("unparseable reply") for p in probs):
                    run["records with problems 'not checked yet' / unparseable / check crashed"] += 1
                run[f"phase {ph} records with any problem"] += bool(probs)
                if ph == 2:
                    fp = [p for p in probs if str(p).startswith("format:")]
                    if fp:
                        run["phase 2 records with a 'format:' problem"] += 1
                        run["phase 2 'format:' problems (module: problems)"][m] = fp
                ident = {"module": rec.get("module") == m, "prompt version": rec.get("prompt version") == VERSION,
                         "input version": rec.get("input version") == "v1", "phase": rec.get("phase") == ph}
                if ph not in texts:
                    mismatches.append({"run": k, "phase": ph, "module": m, "what": "phase 2 not rebuildable: phase 1 raw has no Conceptual Assets list"})
                    continue
                s, usr = texts[ph]
                ss, us, key = sha12(s), sha12(usr), sha12(s + "\n\n" + usr)
                request_keys[(m, ph)] = u.get("request key")
                ok = rec.get("system sha") == ss and rec.get("user sha") == us
                run["rebuilt (system and user sha match)"] += ok
                run["request key matches sha12(system+2 newlines+user)"] += (u.get("request key") == key)
                bad = [w for w, c in ident.items() if not c]
                if not ok or u.get("request key") != key or bad:
                    mismatches.append({"run": k, "phase": ph, "module": m, "system sha stored/rebuilt": [rec.get("system sha"), ss],
                                       "user sha stored/rebuilt": [rec.get("user sha"), us],
                                       "request key stored/rebuilt": [u.get("request key"), key], "identity fields wrong": bad})
            a = json.loads((rd / "assets" / f"{m}.json").read_text(encoding="utf-8"))
            listed[m] = [r.get("Asset RTL") for r in a["Assets"]]
        for f in run["_failed_calls.jsonl"]:
            if f["module"] and f["phase"]:
                f["stored record now"] = {"request key": request_keys.get((f["module"], f["phase"])),
                                          "same request as the failed call": request_keys.get((f["module"], f["phase"])) == f["key"]}
        run["stored request keys listed in _keys.jsonl"] = f"{sum(v in keys for v in request_keys.values())} of {len(request_keys)}"
        for g, ms in groups.items():
            c = l = f = 0
            for m in ms:
                ci, li, fi = score(listed[m], ref_rows[m])
                c, l, f = c + ci, l + li, f + fi
            scores[g][f"r{k}"] = {"correct": c, "listed": l, "findable": f}
        out["runs"][f"r{k}"] = run

    pooled = {}
    for g in groups:
        c = sum(v["correct"] for v in scores[g].values())
        l = sum(v["listed"] for v in scores[g].values())
        f = sum(v["findable"] for v in scores[g].values())
        pooled[g] = {"per run": scores[g], "pooled correct": c, "pooled listed": l, "pooled findable": f,
                     "precision (correct/listed)": f"{c}/{l} = {c / l:.3f}" if l else "n/a",
                     "recall (correct/findable)": f"{c}/{f} = {c / f:.3f}" if f else "n/a",
                     "modules": len(groups[g]), "findable per run": f // len(REPS)}
    sizes = [s for s, *_ in located_sizes]
    mx = max(located_sizes) if located_sizes else None
    out["mismatches"] = mismatches
    out["models in stored usage"] = dict(models)
    out["efforts in stored usage"] = dict(efforts)
    out["LOCATED"] = {"entries (concepts over 3 runs x 41 modules)": len(sizes),
                      "names per entry: mean": round(sum(sizes) / len(sizes), 3) if sizes else None,
                      "names per entry: max": mx[0] if mx else None,
                      "max at (run, module, concept id)": [mx[1], mx[2], mx[3]] if mx else None,
                      "entries with 0 names": sum(s == 0 for s in sizes),
                      "names per entry: distribution": dict(sorted(Counter(sizes).items())),
                      "irregular Phase 1 entries seen": dict(located_stats),
                      "irregular closed-set counterpart lines seen (all 41 modules)": dict(closed_set_odd)}
    out["exact scorer"] = pooled
    (HERE / "result.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
