"""Check 2 of the v10 diagnosis (user 2026-10-16): "check if all 41 modules were tested on isolated rules to check for any
individual rule failure. If any rule hasn't been tested, it needs testing."

For every rule wording v10 carries, find the rule-alone runs whose rule text equals v10's text (the latest adopted test,
verify_v10_rules.py) and count, per executor, the stored replies: modules covered (of the 41), repeats, and replies with
no check problem. Also says which shared procedure each run's context carried (v9 none, v10r/v10f their own, v10m the
merged one v10 uses). A rule text is compared by its sha12 over the text, so a run with an older text never counts.

Self-test (hand-checked 2026-10-16 with `ls`): runs/rule_isolation_v9/gpt-5.6-luna__high holds 82 files for P1-26
(41 modules x 2 repeats, Phase 1 only).
Sends nothing; writes verify_isolation_coverage.json.

  python -B verify_isolation_coverage.py
"""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
ISO = LAB / "analysis" / "rule_isolation_v9"
RUNS = LAB / "runs"
sys.path.insert(0, str(LAB))
import labkit as K  # noqa: E402

# variant -> (run folder, executor folder, texts file, procedure in its context)
RUNSETS = {
    "v9": ("rule_isolation_v9", "gpt-5.6-luna__high", "rule_texts.json", "none (v9 context)"),
    "v10r": ("rule_isolation_v10r", "gpt-5.6-luna__high", "rule_texts_v10r.json", "v10r procedure"),
    "v10f": ("rule_isolation_v10f", "gpt-5.6-luna__high", "rule_texts_v10f.json", "v10f procedure, facts format"),
    "v10f2": ("rule_isolation_v10f2", "gpt-5.6-luna__high", "rule_texts_v10f2.json", "v10f procedure, facts format"),
    "v10f3": ("rule_isolation_v10f3", "gpt-5.6-luna__high", "rule_texts_v10f3.json", "v10f procedure, facts format"),
    "v10fo": ("rule_isolation_v10fo", "gpt-5.6-luna__high", "rule_texts_v10fo.json", "v10f procedure"),
    "v10m__claude": ("rule_isolation_v10m__claude", "claude-sonnet__agent-batched", "rule_texts_v10m.json", "merged (v10)"),
    "v10m__claude1": ("rule_isolation_v10m__claude1", "claude-sonnet__agent-single", "rule_texts_v10m.json", "merged (v10)"),
    "v10e1__claude1": ("rule_isolation_v10e1__claude1", "claude-sonnet__agent-single", "rule_texts_v10e1.json", "merged (v10)"),
}


def sha(t):
    return hashlib.sha256((t or "").encode("utf-8")).hexdigest()[:12]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    n26 = len(list((RUNS / "rule_isolation_v9" / "gpt-5.6-luna__high").glob("r*/P1/P1-26/*.json")))
    print(f"self-test (P1-26 files in the v9 run, hand-checked 82): {'PASS' if n26 == 82 else 'FAIL'} ({n26})")
    if n26 != 82:
        sys.exit(1)
    mods41 = set(K.gt_modules()["tuning"] + K.gt_modules()["heldout"])
    ver = json.loads((HERE / "verify_v10_rules.json").read_text(encoding="utf-8"))
    latest_src = ver["latest tested text per rule"]
    srcfile = {"v9": "rule_texts.json", "v10m": "rule_texts_v10m.json", "v10e1": "rule_texts_v10e1.json"}
    v10text = {}
    for rid, s in latest_src.items():
        t = json.loads((ISO / srcfile[s]).read_text(encoding="utf-8"))[rid]
        for ph in ("P1", "P2"):
            if t.get(ph):
                v10text[(rid, ph)] = sha(t[ph])
    texts = {v: json.loads((ISO / f).read_text(encoding="utf-8")) for v, (_, _, f, _) in RUNSETS.items()}
    cover = defaultdict(list)
    for v, (run, ex, _, proc) in RUNSETS.items():
        for (rid, ph), s in v10text.items():
            t = texts[v].get(rid, {})
            if sha(t.get(ph)) != s:
                continue
            recs = [json.loads(f.read_text(encoding="utf-8")) for f in (RUNS / run / ex).glob(f"r*/{ph}/{rid}/*.json")]
            if not recs:
                continue
            mods = {r["module"] for r in recs}
            reps = {r["rep"] for r in recs}
            clean = sum(1 for r in recs if not r.get("problems") and r.get("reply") is not None)
            cover[(rid, ph)].append({"variant": v, "executor": ex, "procedure": proc, "modules": len(mods & mods41),
                                     "repeats": sorted(reps), "replies": len(recs), "clean replies": clean})
    rows = []
    for (rid, ph) in sorted(v10text):
        c = cover.get((rid, ph), [])
        luna = [x for x in c if x["executor"].startswith("gpt-5.6-luna")]
        full = [x for x in luna if x["modules"] == 41 and len(x["repeats"]) >= 2]
        rows.append({"rule": rid, "phase": ph, "v10 text from": latest_src[rid], "runs with v10's exact text": c,
                     "luna, 41 modules x 2 repeats": bool(full),
                     "luna with the merged procedure": any(x["procedure"].startswith("merged") for x in luna)})
    (HERE / "verify_isolation_coverage.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    ok = [r for r in rows if r["luna, 41 modules x 2 repeats"]]
    print(f"v10 rule wordings: {len(rows)}; tested alone on luna on all 41 modules x 2 repeats with v10's exact text: {len(ok)}")
    for r in rows:
        if not r["luna, 41 modules x 2 repeats"]:
            c = r["runs with v10's exact text"]
            print(f"  NOT on luna x 41: {r['rule']} {r['phase']} (text {r['v10 text from']}); other runs: "
                  + ("; ".join(f"{x['variant']} {x['modules']} modules, {x['replies']} replies" for x in c) or "none"))
    print(f"with the merged procedure (v10's context) on luna: {sum(r['luna with the merged procedure'] for r in rows)} of {len(rows)}")
    procs = defaultdict(int)
    for r in ok:
        x = next(x for x in r["runs with v10's exact text"] if x["executor"].startswith("gpt-5.6-luna") and x["modules"] == 41)
        procs[x["procedure"]] += 1
    print("context of those luna runs:", dict(procs))
    bad = [(r["rule"], r["phase"], x["variant"], x["replies"] - x["clean replies"]) for r in rows for x in r["runs with v10's exact text"]
           if x["executor"].startswith("gpt-5.6-luna") and x["replies"] != x["clean replies"]]
    print(f"luna replies with a check problem (rule, phase, variant, count): {bad}")


if __name__ == "__main__":
    main()
