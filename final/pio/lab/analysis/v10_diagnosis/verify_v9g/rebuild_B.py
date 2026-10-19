"""Independent re-derivation (suffix _B): do the 30 stored two_phase_v9g run-0 records of the 15 tuning modules
rebuild from the prompt folder and the inputs?

Nothing here imports chain.py, labkit.py or any earlier verify script. The rules re-implemented from reading chain.py
and check_lab_prompt.py:
  sha12(t)            = sha256(t.encode("utf-8")).hexdigest()[:12]
  system(phase k)     = common.md.rstrip() + "\n\n" + phase<k>.md
  user(phase 1)       = phase1_user.md.format(module, rtl=rtl.txt, diagram=diagram.txt,
                                              closed_set=json.dumps(json.loads(closed_set.json), separators=(",", ":")))
  user(phase 2)       = phase2_user.md.format(... same ..., concepts=json.dumps(CA, indent=1, ensure_ascii=False))
                        where CA = parse_json(phase-1 record "raw")["Conceptual Assets"] (the list as the model wrote it)
  parse_json(text)    = strip; drop a ``` fence; json.loads(text[first "{" : last "}" + 1])
  record stores       "system sha" = sha12(system), "user sha" = sha12(user),
                      usage["request key"] = sha12(system + "\n\n" + user), usage["model"], usage["effort"]
No API call is made. Output: a table on stdout and rebuild_B_result.json next to this file.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]                                   # .../final/pio/lab
VERSION = "two_phase_v9g"
PROMPTS = LAB / "prompts" / VERSION
INPUTS = LAB / "inputs" / "v1"
RUN = LAB / "runs" / f"{VERSION}__v1" / "gpt-5.6-luna__high" / "r0"
WANT_MODEL, WANT_EFFORT = "gpt-5.6-luna", "high"


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def system_text(phase: int) -> str:
    return (PROMPTS / "common.md").read_text(encoding="utf-8").rstrip() + "\n\n" + \
           (PROMPTS / f"phase{phase}.md").read_text(encoding="utf-8")


def parse_json(text: str):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    return json.loads(t[t.find("{"): t.rfind("}") + 1])


def user_text(phase: int, m: str, concepts=None) -> str:
    d = INPUTS / "tuning" / m
    tpl = (PROMPTS / f"phase{phase}_user.md").read_text(encoding="utf-8")
    vals = {"module": m,
            "rtl": (d / "rtl.txt").read_text(encoding="utf-8"),
            "diagram": (d / "diagram.txt").read_text(encoding="utf-8"),
            "closed_set": json.dumps(json.loads((d / "closed_set.json").read_text(encoding="utf-8")),
                                     separators=(",", ":"))}
    if phase == 2:
        vals["concepts"] = json.dumps(concepts, indent=1, ensure_ascii=False)
    return tpl.format(**vals)


def selftest() -> None:
    """Hand-checked anchors before anything is reported."""
    # 1. sha12 against a value computed by hand with the standard library on a fixed string
    assert sha12("abc") == "ba7816bf8f01", sha12("abc")          # sha256("abc") = ba7816bf8f01cfea...
    # 2. the system text rule: rstrip + two newlines + phase file, checked on tiny stand-ins
    assert ("x\n\n".rstrip() + "\n\n" + "y") == "x\n\ny"
    # 3. the template substitution leaves braces inside the values alone
    assert "A {b} B".format(b="{c}") == "A {c} B"
    # 4. parse_json drops a fence and reads the outer object
    assert parse_json("```json\n{\"a\": [1]}\n```") == {"a": [1]}
    # 5. a one-character change in the system text changes the hash (the comparison is not vacuous)
    s = system_text(1)
    assert sha12(s) != sha12(s + " ")
    print("self-test: 5/5 anchors pass")


def main() -> int:
    selftest()
    meta = json.loads((RUN / "_run_meta.json").read_text(encoding="utf-8"))
    tuning_folders = sorted(p.name for p in (INPUTS / "tuning").iterdir() if p.is_dir())
    # the 15 modules with reference entries, read from the kit's data file (data, not code)
    kit = json.loads((LAB / "kit_data" / "v1.json").read_text(encoding="utf-8"))
    tuning15 = list(kit["tuning modules"])
    assert set(tuning15) <= set(tuning_folders), "kit tuning list is not a subset of the input folders"
    no_record = [m for m in tuning_folders if not (RUN / "phase1" / f"{m}.json").exists()]

    sys_sha = {1: sha12(system_text(1)), 2: sha12(system_text(2))}
    meta_match = {k: sys_sha[k] == meta.get(f"system sha phase {k}") for k in (1, 2)}
    keys_file = {}
    for line in (RUN / "_keys.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            x = json.loads(line)
            keys_file[x["key"]] = (x.get("module"), x.get("phase"))

    rows, exact = [], 0
    for m in tuning15:
        p1 = json.loads((RUN / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
        concepts = None
        try:
            concepts = parse_json(p1["raw"]).get("Conceptual Assets")
        except (ValueError, AttributeError) as e:
            concepts = f"<unparseable phase-1 raw: {e}>"
        for phase in (1, 2):
            rec = p1 if phase == 1 else json.loads((RUN / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
            s = system_text(phase)
            u = user_text(phase, m) if phase == 1 else (
                user_text(2, m, concepts) if isinstance(concepts, list) else None)
            want = {"system sha": sha12(s),
                    "user sha": sha12(u) if u is not None else None,
                    "request key": sha12(s + "\n\n" + u) if u is not None else None}
            have = {"system sha": rec.get("system sha"), "user sha": rec.get("user sha"),
                    "request key": (rec.get("usage") or {}).get("request key")}
            ok = all(want[k] is not None and want[k] == have[k] for k in want)
            exact += ok
            problems = rec.get("problems") or []
            parsed = isinstance(rec.get("reply"), dict) and not rec.get("check crashed") \
                and problems != ["not checked yet"] and not any(str(p).startswith("unparseable reply") for p in problems)
            # stricter: the phase's own lists are there in the stored (v5-key) reply, as chain.stopped() requires
            rep = rec.get("reply") if isinstance(rec.get("reply"), dict) else {}
            if phase == 1:
                ca = rep.get("conceptual assets")
                schema_ok = isinstance(ca, list) and all(isinstance(c, dict) for c in ca)
            else:
                schema_ok = isinstance(rep.get("points"), list) and isinstance(rep.get("structural assets"), list)
            parsed = parsed and schema_ok
            rows.append({"module": m, "phase": phase, "rebuilds": ok, "want": want, "have": have,
                         "model": (rec.get("usage") or {}).get("model"), "effort": (rec.get("usage") or {}).get("effort"),
                         "parsed reply": parsed, "n problems": len(problems),
                         "key in _keys.jsonl": keys_file.get(have["request key"]) == (m, phase),
                         "record module/phase": (rec.get("module"), rec.get("phase")),
                         "record prompt version": rec.get("prompt version"), "record input version": rec.get("input version")})

    n_assets = len(list((RUN / "assets").glob("*.json")))
    n_phase1 = len(list((RUN / "phase1").glob("*.json")))
    n_phase2 = len(list((RUN / "phase2").glob("*.json")))
    bad = [r for r in rows if not r["rebuilds"]]
    summary = {
        "records checked": len(rows), "rebuild exactly": exact, "do not rebuild": [(r["module"], r["phase"]) for r in bad],
        "system sha phase 1 (recomputed)": sys_sha[1], "system sha phase 2 (recomputed)": sys_sha[2],
        "system sha matches _run_meta.json": meta_match,
        "model == gpt-5.6-luna (records)": sum(r["model"] == WANT_MODEL for r in rows),
        "effort == high (records)": sum(r["effort"] == WANT_EFFORT for r in rows),
        "parsed reply (records)": sum(r["parsed reply"] for r in rows),
        "key found in _keys.jsonl with same module/phase (records)": sum(r["key in _keys.jsonl"] for r in rows),
        "record says two_phase_v9g/v1 (records)": sum(r["record prompt version"] == VERSION and r["record input version"] == "v1" for r in rows),
        "record module/phase field agrees (records)": sum(r["record module/phase"] == (r["module"], r["phase"]) for r in rows),
        "records with problems > 0": [(r["module"], r["phase"], r["n problems"]) for r in rows if r["n problems"]],
        "asset files in r0": n_assets, "phase1 files in r0": n_phase1, "phase2 files in r0": n_phase2,
        "pending requests in r0/_pending": len(list((RUN / "_pending").glob("*"))) if (RUN / "_pending").exists() else 0,
        "failed-call log present": (RUN / "_failed_calls.jsonl").exists(),
        "schema-failed retries present": (RUN / "_schema_failed").exists(),
        "tuning input folders": len(tuning_folders), "tuning modules with reference entries (kit_data)": len(tuning15),
        "tuning input folders with no r0 record": no_record,
        "_run_meta.json": meta,
    }
    (HERE / "rebuild_B_result.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")

    print(f"{'module':26} ph  rebuilds  sys        user         key          model          effort  parsed  probs  keysfile")
    for r in rows:
        w, h = r["want"], r["have"]
        mark = lambda k: "=" if w[k] == h[k] else "X"
        print(f"{r['module']:26} {r['phase']}   {str(r['rebuilds']):5}   {h['system sha']}{mark('system sha')} "
              f"{h['user sha']}{mark('user sha')} {h['request key']}{mark('request key')} {r['model']:14} {r['effort']:7} "
              f"{str(r['parsed reply']):6}  {r['n problems']:4}   {r['key in _keys.jsonl']}")
    print()
    for k, v in summary.items():
        if k != "_run_meta.json":
            print(f"{k}: {v}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
