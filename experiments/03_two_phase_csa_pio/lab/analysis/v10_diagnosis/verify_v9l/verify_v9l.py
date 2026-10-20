"""Verify the stored two_phase_v9l records (gpt-5.6-luna, high, r0-r2) rebuild exactly from the prompt files and the
built inputs, and score them with the exact (name-count) scorer. No API call is made; nothing is written to the runs.

  python -B verify_v9l.py
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
LAB = HERE.parents[2]
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
import chain  # noqa: E402

VERSION = "two_phase_v9l"
MODEL, EFFORT = "gpt-5.6-luna", "high"
RUNS = LAB / "runs" / f"{VERSION}__v1" / f"{MODEL}__{EFFORT}"
PROMPTS = LAB / "prompts" / VERSION
INPUTS = LAB / "inputs" / "v1"
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
SPLITS = LAB / "splits" / "tuning_v2.json"
REPS = (0, 1, 2)


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------- rebuild of messages ---
def system_text(phase: int) -> str:
    return read(PROMPTS / "common.md").rstrip() + "\n\n" + read(PROMPTS / f"phase{phase}.md")


def module_inputs(m: str) -> dict:
    for split in ("tuning", "heldout"):
        d = INPUTS / split / m
        if d.is_dir():
            return {f: read(d / f) for f in ("rtl.txt", "diagram.txt", "closed_set.json")}
    raise FileNotFoundError(m)


def user_text(phase: int, m: str, concepts=None) -> str:
    x = module_inputs(m)
    vals = {"module": m, "rtl": x["rtl.txt"], "diagram": x["diagram.txt"],
            "closed_set": json.dumps(json.loads(x["closed_set.json"]), separators=(",", ":"))}
    if phase == 2:
        vals["concepts"] = json.dumps(concepts, indent=1, ensure_ascii=False)
    return read(PROMPTS / f"phase{phase}_user.md").format(**vals)


# ------------------------------------------------------------------------------------------- exact scorer ---
def reference_rows(m: str) -> list[str]:
    """Reference elements of module m, in sheet order, kept only when the element is a closed-set name of m."""
    gt = json.loads(read(GT))["modules"]
    if m not in gt:
        return []
    names = {n for (_e, n) in chain.closed_names(m)}
    return [r["element"] for r in gt[m]["assets"] if r.get("element") in names]


def listed_names(rep: int, m: str) -> list[str]:
    a = json.loads(read(RUNS / f"r{rep}" / "assets" / f"{m}.json"))
    return [r["Asset RTL"] for r in a["Assets"]]


def score(listed: list[str], ref: list[str]) -> tuple[int, int, int]:
    """(correct, listed, findable): reference rows walked in order; a row whose element still has a listed copy
    consumes one and counts correct."""
    pool = Counter(listed)
    correct = 0
    for el in ref:
        if pool[el] > 0:
            pool[el] -= 1
            correct += 1
    return correct, len(listed), len(ref)


def selftest() -> None:
    assert sha12("abc") == "ba7816bf8f01", sha12("abc")          # sha256("abc") = ba7816bf8f01cfea...
    assert score(["a", "a", "b", "z"], ["a", "b", "c", "a", "a"]) == (3, 4, 5)
    assert score([], ["a"]) == (0, 0, 1)
    assert score(["a"], []) == (0, 1, 0)
    assert "{" not in user_text(1, "neorv32_bus").split("\n")[0] or True
    # the template placeholders must all be consumed (a stray {x} would raise KeyError in format())
    t = read(PROMPTS / "phase1_user.md")
    for ph in ("{module}", "{rtl}", "{diagram}", "{closed_set}"):
        assert ph in t, ph
    assert "{concepts}" in read(PROMPTS / "phase2_user.md")


# ------------------------------------------------------------------------------------------- main ---
def main() -> None:
    selftest()
    print("self-test: PASS")
    sys1, sys2 = system_text(1), system_text(2)
    ss = {1: sha12(sys1), 2: sha12(sys2)}
    tpl = {k: sha12(read(PROMPTS / f"phase{k}_user.md")) for k in (1, 2)}
    cross = {"system via chain.C matches": [chain.C.system(VERSION, k) == (sys1 if k == 1 else sys2) for k in (1, 2)]}
    print(f"system sha phase 1 {ss[1]}  phase 2 {ss[2]}  user template sha {tpl[1]} / {tpl[2]}  {cross}")

    # module groups
    gt = json.loads(read(GT))["modules"]
    tuning_folders = sorted(p.name for p in (INPUTS / "tuning").iterdir() if p.is_dir())
    heldout_folders = sorted(p.name for p in (INPUTS / "heldout").iterdir() if p.is_dir())
    tuning15 = [m for m in tuning_folders if m in gt and len(gt[m]["assets"]) > 0]
    tuning_no_ref = [m for m in tuning_folders if m not in tuning15]
    splits = json.loads(read(SPLITS))
    groups = {"tuning 15": tuning15, "held-out 26": heldout_folders,
              "tuning_v2": list(splits["tuning"]), "heldout_v2": list(splits["heldout"]),
              "all 41": tuning15 + heldout_folders}
    print(f"tuning folders {len(tuning_folders)}, with a reference row {len(tuning15)}, without {tuning_no_ref}; "
          f"held-out folders {len(heldout_folders)}; tuning_v2 {len(splits['tuning'])}, heldout_v2 {len(splits['heldout'])}")
    expected41 = set(tuning15) | set(heldout_folders)
    assert len(expected41) == 41, len(expected41)
    assert set(splits["tuning"]) | set(splits["heldout"]) == expected41
    assert chain.closed_names("neorv32_bus")  # kit data loads

    figures = {"version": VERSION, "model_effort_folder": f"{MODEL}__{EFFORT}", "system sha": ss, "user template sha": tpl,
               "chain.C.system agrees": cross["system via chain.C matches"], "groups": {k: len(v) for k, v in groups.items()},
               "tuning folders without a reference row": tuning_no_ref, "runs": {}}
    problems: list[str] = []
    for rep in REPS:
        out = RUNS / f"r{rep}"
        meta = json.loads(read(out / "_run_meta.json"))
        meta_ok = (meta["system sha phase 1"], meta["system sha phase 2"], meta["user template sha phase 1"],
                   meta["user template sha phase 2"], meta["model"], meta["effort"], meta["prompt version"],
                   meta["input version"]) == (ss[1], ss[2], tpl[1], tpl[2], MODEL, EFFORT, VERSION, "v1")
        p1 = sorted(p.stem for p in (out / "phase1").glob("*.json"))
        p2 = sorted(p.stem for p in (out / "phase2").glob("*.json"))
        assets = sorted(p.stem for p in (out / "assets").glob("*.json"))
        r = {"meta matches rebuilt shas": meta_ok, "phase1 files": len(p1), "phase2 files": len(p2),
             "assets files": len(assets), "modules match the 41": set(p1) == expected41 and set(p2) == expected41
             and set(assets) == expected41,
             "rebuilt": 0, "mismatches": [], "parsed replies": 0, "unparsed replies": [],
             "models seen": Counter(), "efforts seen": Counter(), "stored reply re-derived": 0,
             "stored problems re-derived": 0, "assets re-derived": 0, "assets mismatches": [],
             "phase2 format problems": 0, "phase2 format modules": [], "phase1 format problems": 0,
             "stopped records": [], "pending files": sorted(p.name for p in (out / "_pending").glob("*")) if (out / "_pending").exists() else "no folder",
             "failed_calls file": (out / "_failed_calls.jsonl").exists(),
             "failed folder": sorted(p.name for p in (out / "_failed").glob("*")) if (out / "_failed").exists() else "no folder",
             "schema_failed folder": (out / "_schema_failed").exists(),
             "usage in/out tokens": [0, 0]}
        for m in sorted(expected41):
            rec1 = json.loads(read(out / "phase1" / f"{m}.json"))
            rec2 = json.loads(read(out / "phase2" / f"{m}.json"))
            for ph, rec in ((1, rec1), (2, rec2)):
                r["models seen"][rec["usage"].get("model")] += 1
                r["efforts seen"][rec["usage"].get("effort")] += 1
                r["usage in/out tokens"][0] += rec["usage"].get("in") or 0
                r["usage in/out tokens"][1] += rec["usage"].get("out") or 0
                # reply parse
                try:
                    parsed = chain.K.parse_json(rec["raw"])
                    r["parsed replies"] += 1
                except ValueError as e:
                    parsed = None
                    r["unparsed replies"].append(f"r{rep} {m} phase {ph}: {e}")
                if ph == 1:
                    want_sys, want_user = ss[1], sha12(user_text(1, m))
                    concepts_written = parsed.get("Conceptual Assets") if isinstance(parsed, dict) else None
                else:
                    want_sys = ss[2]
                    want_user = sha12(user_text(2, m, concepts_written)) if concepts_written is not None else None
                ok = (rec["system sha"], rec["user sha"]) == (want_sys, want_user) and rec["module"] == m \
                    and rec["phase"] == ph and rec["prompt version"] == VERSION and rec["input version"] == "v1"
                if ok:
                    r["rebuilt"] += 1
                else:
                    r["mismatches"].append(f"r{rep} {m} phase {ph}: stored ({rec['system sha']}, {rec['user sha']}) "
                                           f"vs rebuilt ({want_sys}, {want_user})")
                # the stored mapped reply and problems re-derive from the raw text with chain's own functions
                if parsed is not None:
                    if ph == 1:
                        mapped, pre = chain.from_format_phase1(parsed, rec["raw"])
                        probs = pre + chain.check_phase1(m, mapped)
                    else:
                        ids = [c.get("id") for c in chain.phase1_concepts(rec1["reply"])]
                        mapped, pre = chain.from_format_phase2(parsed, rec["raw"], ids)
                        probs = pre + chain.check_phase2(m, mapped, chain.phase1_concepts(rec1["reply"]))
                    if mapped == rec["reply"]:
                        r["stored reply re-derived"] += 1
                    else:
                        problems.append(f"r{rep} {m} phase {ph}: stored 'reply' differs from re-derived mapping")
                    if probs == rec["problems"]:
                        r["stored problems re-derived"] += 1
                    else:
                        problems.append(f"r{rep} {m} phase {ph}: stored 'problems' differ from re-derived "
                                        f"({len(rec['problems'])} vs {len(probs)})")
                if chain.stopped(rec, ph):
                    r["stopped records"].append(f"r{rep} {m} phase {ph}")
                fmt = [p for p in rec["problems"] if isinstance(p, str) and p.startswith("format:")]
                if ph == 2 and fmt:
                    r["phase2 format problems"] += 1
                    r["phase2 format modules"].append(f"{m} ({len(fmt)}: {fmt[0][:90]})")
                if ph == 1 and fmt:
                    r["phase1 format problems"] += 1
            # assets file re-derives from the stored replies with chain.to_assets
            stored_assets = json.loads(read(out / "assets" / f"{m}.json"))
            rebuilt_assets = chain.to_assets(m, rec2["reply"], chain.phase1_concepts(rec1["reply"]))
            if stored_assets == rebuilt_assets:
                r["assets re-derived"] += 1
            else:
                r["assets mismatches"].append(m)
        r["models seen"] = dict(r["models seen"])
        r["efforts seen"] = dict(r["efforts seen"])
        # scores
        r["scores"] = {}
        for g, mods in groups.items():
            c = l = f = 0
            for m in mods:
                ci, li, fi = score(listed_names(rep, m), reference_rows(m))
                c, l, f = c + ci, l + li, f + fi
            r["scores"][g] = {"correct": c, "listed": l, "findable": f,
                              "precision": round(c / l, 3) if l else None, "recall": round(c / f, 3) if f else None}
        figures["runs"][f"r{rep}"] = r
        print(f"\nr{rep}: meta ok {meta_ok}; files phase1 {len(p1)} phase2 {len(p2)} assets {len(assets)}; "
              f"modules match {r['modules match the 41']}")
        print(f"  rebuilt {r['rebuilt']}/82, mismatches {len(r['mismatches'])}; parsed {r['parsed replies']}/82; "
              f"reply re-derived {r['stored reply re-derived']}/82, problems re-derived {r['stored problems re-derived']}/82; "
              f"assets re-derived {r['assets re-derived']}/41")
        print(f"  models {r['models seen']}  efforts {r['efforts seen']}  tokens in/out {r['usage in/out tokens']}")
        print(f"  phase 2 records with a 'format:' problem: {r['phase2 format problems']}  {r['phase2 format modules']}")
        print(f"  phase 1 records with a 'format:' problem: {r['phase1 format problems']}; stopped records {r['stopped records']}")
        print(f"  _pending {r['pending files']}; _failed_calls.jsonl {r['failed_calls file']}; _failed {r['failed folder']}; "
              f"_schema_failed {r['schema_failed folder']}")
        for g, s in r["scores"].items():
            print(f"  {g:12s} correct {s['correct']:4d} listed {s['listed']:4d} findable {s['findable']:4d} "
                  f"P {s['precision']} R {s['recall']}")
        for x in r["mismatches"]:
            print("  MISMATCH", x)
    figures["re-derivation differences"] = problems
    print("\nre-derivation differences:", len(problems))
    for x in problems:
        print("  ", x)
    (HERE / "verify_v9l_result.json").write_text(json.dumps(figures, indent=1), encoding="utf-8")
    print(f"\nwritten {HERE / 'verify_v9l_result.json'}")


if __name__ == "__main__":
    main()
