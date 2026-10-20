"""Verifier for the Tier 3 run of two_phase_p1o_first (PLAN_P1_ORDER.md): held-out 26, gpt-5.6-luna / high, r0-r2.

Checks, with nothing sent and nothing imported from the run scripts:
  1. every stored Phase 2 record rebuilds exactly from prompts/two_phase_p1o_first and inputs/v1 (system sha, user sha,
     request key); the Phase 1 records rebuild too (same way, phase 1 files);
  2. the Phase 1 records are older than every Phase 2 record of the same run (mtime ranges);
  3. each Phase 2 record's usage names gpt-5.6-luna / high;
  4. counts: asset files per run, Phase 2 records with a "format:" problem, other problem classes;
  5. leftovers: _pending, _pending_abandoned, _failed_calls.jsonl, _failed, _schema_failed; _keys.jsonl duplicates;
  6. token totals per run and USD at cost_estimate.PRICES;
  7. the exact scorer (pooled over the 26) per run, as an extra.

  python -B verify_p1o_first.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]                      # verify_tier3 -> v10_diagnosis -> analysis -> lab
ROOT = LAB.parents[2]                      # lab -> pio -> final -> project
if str(LAB) not in sys.path:
    sys.path.insert(0, str(LAB))
import chain  # noqa: E402  (only chain.closed_names and chain.run_dir are used)
import cost_estimate  # noqa: E402  (only PRICES / usd)

VERSION, MODEL, EFFORT, REPS = "two_phase_p1o_first", "gpt-5.6-luna", "high", (0, 1, 2)
PROMPTS = LAB / "prompts" / VERSION
INPUTS = LAB / "inputs" / "v1"
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def parse_json(text: str) -> dict:
    """The lab's reading of a reply: strip a code fence, take the outermost braces."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    return json.loads(t[t.find("{"): t.rfind("}") + 1])


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def heldout_modules() -> list[str]:
    return sorted(d.name for d in (INPUTS / "heldout").iterdir() if d.is_dir())


def system_text(phase: int) -> str:
    return read(PROMPTS / "common.md").rstrip() + "\n\n" + read(PROMPTS / f"phase{phase}.md")


def user_text(phase: int, m: str, concepts=None) -> str:
    d = INPUTS / "heldout" / m
    t = read(PROMPTS / f"phase{phase}_user.md")
    vals = {"module": m, "rtl": read(d / "rtl.txt"), "diagram": read(d / "diagram.txt"),
            "closed_set": json.dumps(json.loads(read(d / "closed_set.json")), separators=(",", ":"))}
    if phase == 2:
        vals["concepts"] = json.dumps(concepts, indent=1, ensure_ascii=False)
    return t.format(**vals)


def ts(x: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(x))


# ------------------------------------------------------------------------------------------------ scorer ---
def score_module(listed_names: list[str], reference_rows: list[dict]) -> tuple[int, int, int]:
    """Exact scorer: (correct, listed, findable). Listed names are a bag; reference rows are walked in order and a
    row whose element still has a copy consumes one."""
    bag = Counter(listed_names)
    correct = 0
    for r in reference_rows:
        el = r.get("element")
        if bag.get(el, 0) > 0:
            bag[el] -= 1
            correct += 1
    return correct, len(listed_names), len(reference_rows)


def reference_rows(gt: dict, m: str) -> list[dict]:
    names = {n for (_, n) in chain.closed_names(m)}
    return [r for r in gt["modules"][m]["assets"] if r.get("element") in names]


# ------------------------------------------------------------------------------------------------ self-test ---
def selftest() -> None:
    assert sha12("") == "e3b0c44298fc", "sha12 is not sha256 hex[:12]"
    # scorer: duplicates kept on both sides, each listed copy consumed once
    ref = [{"element": "a"}, {"element": "a"}, {"element": "b"}, {"element": "z"}]
    assert score_module(["a", "c"], ref) == (1, 2, 4)
    assert score_module(["a", "a", "a", "b"], ref) == (3, 4, 4)
    assert score_module([], ref) == (0, 0, 4)
    # parse_json: a fenced reply and a bare one read the same
    assert parse_json('```json\n{"x": [1]}\n```') == parse_json('{"x": [1]}') == {"x": [1]}
    # the rebuilt templates agree with the run's own metadata (a check of the rebuild recipe itself)
    meta = json.loads(read(chain.run_dir(VERSION, MODEL, 0, EFFORT) / "_run_meta.json"))
    want = {"system sha phase 1": sha12(system_text(1)), "system sha phase 2": sha12(system_text(2)),
            "user template sha phase 1": sha12(read(PROMPTS / "phase1_user.md")),
            "user template sha phase 2": sha12(read(PROMPTS / "phase2_user.md")),
            "inputs manifest sha": sha12(read(INPUTS / "manifest.json"))}
    bad = {k: (meta.get(k), v) for k, v in want.items() if meta.get(k) != v}
    assert not bad, f"_run_meta.json disagrees with the rebuilt prompt/template shas: {bad}"
    assert len(heldout_modules()) == 26, f"held-out folder has {len(heldout_modules())} modules, not 26"


# ------------------------------------------------------------------------------------------------ main ---
def main() -> dict:
    selftest()
    print("self-test: PASS (sha12, scorer, parse_json, _run_meta shas vs rebuilt, 26 held-out folders)")
    gt = json.loads(read(GT))
    mods = heldout_modules()
    sys2 = system_text(2)
    sys1 = system_text(1)
    ss2, ss1 = sha12(sys2), sha12(sys1)
    print(f"rebuilt system sha: phase 1 {ss1}, phase 2 {ss2}; modules: {len(mods)}")
    out = {"version": VERSION, "model": MODEL, "effort": EFFORT, "modules": len(mods), "runs": {}}
    for k in REPS:
        rd = chain.run_dir(VERSION, MODEL, k, EFFORT)
        meta = json.loads(read(rd / "_run_meta.json"))
        R = {"run dir": str(rd), "meta ok": (meta.get("model"), meta.get("effort"), meta.get("prompt version"),
                                             meta.get("input version")) == (MODEL, EFFORT, VERSION, "v1")}
        # ---- 1. rebuild every Phase 2 (and Phase 1) record
        rebuilt = mism = 0
        p1_rebuilt = p1_mism = 0
        mism_rows, missing = [], []
        usage_ok = 0
        usage_bad = []
        fmt = cons = other = 0
        fmt_rows = []
        tok = Counter()
        tok1 = Counter()
        none_reasoning = 0
        usd = usd1 = 0.0
        mt1, mt2 = [], []
        sc = Counter()
        per_module_score = {}
        for m in mods:
            p1p, p2p, ap = rd / "phase1" / f"{m}.json", rd / "phase2" / f"{m}.json", rd / "assets" / f"{m}.json"
            if not p1p.exists() or not p2p.exists():
                missing.append(m)
                continue
            r1, r2 = json.loads(read(p1p)), json.loads(read(p2p))
            mt1.append(os.path.getmtime(p1p))
            mt2.append(os.path.getmtime(p2p))
            # Phase 1 rebuild (extra): same recipe with the phase 1 files
            u1 = user_text(1, m)
            p1_rebuilt += 1
            if (r1.get("system sha"), r1.get("user sha")) != (ss1, sha12(u1)) or \
                    (r1.get("usage") or {}).get("request key") != sha12(sys1 + "\n\n" + u1):
                p1_mism += 1
            # Phase 2 rebuild: concepts = the stored Phase 1 raw reply's "Conceptual Assets", as written
            concepts = parse_json(r1["raw"]).get("Conceptual Assets")
            u2 = user_text(2, m, concepts)
            us2, key2 = sha12(u2), sha12(sys2 + "\n\n" + u2)
            rebuilt += 1
            got = (r2.get("system sha"), r2.get("user sha"), (r2.get("usage") or {}).get("request key"),
                   r2.get("module"), r2.get("phase"), r2.get("prompt version"))
            want = (ss2, us2, key2, m, 2, VERSION)
            if got != want:
                mism += 1
                mism_rows.append({"module": m, "stored": got, "rebuilt": want})
            # 3. usage model / effort
            u = r2.get("usage") or {}
            if (u.get("model"), u.get("effort")) == (MODEL, EFFORT):
                usage_ok += 1
            else:
                usage_bad.append({"module": m, "model": u.get("model"), "effort": u.get("effort")})
            # 4. problem classes
            probs = [str(p) for p in r2.get("problems", [])]
            if any(p.startswith("format:") for p in probs):
                fmt += 1
                fmt_rows.append({"module": m, "format problems": [p for p in probs if p.startswith("format:")]})
            if any(p.startswith("consistency:") for p in probs):
                cons += 1
            if r2.get("check crashed") or probs == ["not checked yet"] or any(
                    p.startswith(("unparseable reply", "schema:", "check crashed")) for p in probs):
                other += 1
            # 6. tokens
            for f in ("in", "out", "reasoning", "cached"):
                if u.get(f) is None:
                    if f == "reasoning":
                        none_reasoning += 1
                else:
                    tok[f] += int(u[f])
            usd += cost_estimate.usd(u, MODEL)
            u1r = r1.get("usage") or {}
            for f in ("in", "out", "reasoning", "cached"):
                if u1r.get(f) is not None:
                    tok1[f] += int(u1r[f])
            usd1 += cost_estimate.usd(u1r, MODEL)
            # 7. exact scorer
            if ap.exists():
                a = json.loads(read(ap))
                listed = [row.get("Asset RTL") for row in a.get("Assets", [])]
                c, l, f_ = score_module(listed, reference_rows(gt, m))
                sc["correct"] += c
                sc["listed"] += l
                sc["findable"] += f_
                per_module_score[m] = [c, l, f_]
        # ---- asset files, leftovers, keys
        assets = sorted(p.name for p in (rd / "assets").glob("*.json"))
        assets_not_heldout = [a for a in assets if a[:-5] not in mods]
        pending = sorted(p.name for p in (rd / "_pending").iterdir()) if (rd / "_pending").exists() else None
        aband_dir = rd / "_pending_abandoned"
        abandoned = []
        keys_lines = [json.loads(l) for l in read(rd / "_keys.jsonl").splitlines() if l.strip()] if (rd / "_keys.jsonl").exists() else []
        key_of = {}
        for x in keys_lines:
            key_of.setdefault(x["key"], (x.get("module"), x.get("phase")))
        if aband_dir.exists():
            for p in sorted(aband_dir.iterdir()):
                x = json.loads(read(p))
                key = p.stem
                m_, ph_ = key_of.get(key, (None, None))
                stored = None
                if m_ and ph_:
                    rec = json.loads(read(rd / f"phase{ph_}" / f"{m_}.json"))
                    stored = {"request key": (rec.get("usage") or {}).get("request key"),
                              "response id": (rec.get("usage") or {}).get("response id"),
                              "same key as stored": (rec.get("usage") or {}).get("request key") == key,
                              "same response id as stored": (rec.get("usage") or {}).get("response id") == x.get("id")}
                abandoned.append({"file": p.name, "module": m_, "phase": ph_, "abandoned response id": x.get("id"),
                                  "created": ts(x["created"]) if x.get("created") else None, "stored record": stored})
        key_counts = Counter(x["key"] for x in keys_lines)
        dup_keys = [{"key": kk, "times": n, **dict(zip(("module", "phase"), key_of[kk]))} for kk, n in key_counts.items() if n > 1]
        leftovers = {"_pending files": pending, "_pending_abandoned": abandoned,
                     "_failed_calls.jsonl": (rd / "_failed_calls.jsonl").exists(),
                     "_failed dir": (rd / "_failed").exists(), "_schema_failed dir": (rd / "_schema_failed").exists(),
                     "_keys.jsonl lines": len(keys_lines), "_keys.jsonl distinct keys": len(key_counts),
                     "_keys.jsonl duplicate keys": dup_keys}
        R.update({
            "phase2 records rebuilt": rebuilt, "phase2 mismatches": mism, "phase2 mismatch rows": mism_rows,
            "phase1 records rebuilt": p1_rebuilt, "phase1 mismatches": p1_mism, "modules missing a record": missing,
            "phase1 mtime range": [ts(min(mt1)), ts(max(mt1))] if mt1 else None,
            "phase2 mtime range": [ts(min(mt2)), ts(max(mt2))] if mt2 else None,
            "all phase1 older than every phase2": bool(mt1 and mt2 and max(mt1) < min(mt2)),
            "phase1 newest to phase2 oldest, minutes": round((min(mt2) - max(mt1)) / 60, 1) if mt1 and mt2 else None,
            "usage model+effort ok": usage_ok, "usage model+effort bad": usage_bad,
            "asset files": len(assets), "asset files outside held-out": assets_not_heldout,
            "phase2 records with a format: problem": fmt, "format rows": fmt_rows,
            "phase2 records with a consistency: problem": cons,
            "phase2 records unparseable/schema/crashed/unchecked": other,
            "leftovers": leftovers,
            "phase2 tokens": {"input": tok["in"], "output": tok["out"], "reasoning": tok["reasoning"], "cached": tok["cached"],
                              "records with reasoning None": none_reasoning},
            "phase2 usd": round(usd, 4),
            "phase1 tokens (paid in Tier 1, for reference)": {"input": tok1["in"], "output": tok1["out"],
                                                              "reasoning": tok1["reasoning"], "cached": tok1["cached"]},
            "phase1 usd (paid in Tier 1, for reference)": round(usd1, 4),
            "exact scorer pooled": {"correct": sc["correct"], "listed": sc["listed"], "findable": sc["findable"],
                                    "recall": round(sc["correct"] / sc["findable"], 4) if sc["findable"] else None,
                                    "precision": round(sc["correct"] / sc["listed"], 4) if sc["listed"] else None},
            "exact scorer per module": per_module_score,
        })
        out["runs"][f"r{k}"] = R
        print(f"\n== r{k}  {rd}")
        for kk, v in R.items():
            if kk in ("run dir", "exact scorer per module", "phase2 mismatch rows", "format rows"):
                continue
            print(f"  {kk}: {json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v}")
        if mism_rows:
            print(f"  MISMATCH ROWS: {json.dumps(mism_rows, ensure_ascii=False)}")
        if fmt_rows:
            print(f"  format rows: {json.dumps(fmt_rows, ensure_ascii=False)}")
    out["prices used (USD per 1M)"] = cost_estimate.PRICES[MODEL]
    out["usd formula"] = "((in - cached) * in_price + cached * cached_price + out * out_price) / 1e6, cost_estimate.usd"
    (HERE / "result.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nprices: {cost_estimate.PRICES[MODEL]}")
    print(f"written: {HERE / 'result.json'}")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
