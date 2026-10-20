"""After the rules round (code). Per item in rules/args.json:
  - the record: rules/<ID>/revised.json (the revision; if its file write was blocked, the revision's return value in
    the workflow journal, flagged); the draft likewise;
  - the prompt-rule code check (fixcheck.check: meta_tools on the wording; planted self-test first) on the draft and
    on the revision;
  - the two skeptic verdicts (rules/verdicts/<ID>__R-1__{A,B}.json): fix_verdict and finding_verdict;
  - a code-check fix: its script must exist and open no reference file (fixcheck's source test); it is run with a
    timeout as "python check.py <out.json>" from its own folder; the rows it drops are scored here with the exact
    scorer (names equal, each reference entry used once): correct finds lost and false positives removed, per run.
    Only this scoring step reads the reference; the script never does.
  - a prompt-rule fix: its wording diff against v7 goes to blind/diffs/<ID>.diff for stage E.
Status, as in the v6 rules round (no re-check round): "drafted, challenged, revised", with both skeptics' verdicts and
the code-check result; "not checked: <agent> failed twice" if a record or verdict is missing.
Self-test of the scoring: dropping nothing reproduces compare_v7.runs() (92/89/86 correct of 146/158/131 listed);
dropping one hand-read correct find (wdt r0 ctrl.enable) loses exactly one correct find.

  python rules_post.py <rules run id>     -> rules_status.json
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import common_fa as F
import fixcheck as FC
import b2

RD = F.HERE / "rules"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else None


def rescore(drops):
    """drops: {"r0": {"wdt": [{"element", "entity"}]}} -> per run (correct, listed, lost [keys], fp removed)."""
    out = {}
    for r in F.REPS:
        C = L = 0
        lost, fpr = [], 0
        for m in F.MODS:
            s = F.short(m)
            a = F.assets(r, m)
            d = {(x.get("entity"), x.get("element")) for x in (drops.get(f"r{r}", {}).get(s, []) or [])}
            keep = [x for x in a if (x["Entity"], x["Asset RTL"]) not in d and (None, x["Asset RTL"]) not in d]
            ref = [n for (_k, n, _kk, _h) in F.ref_entries(m)]

            def corr(rows):
                cnt = Counter(x["Asset RTL"] for x in rows)
                got = []
                for n in ref:
                    if cnt[n] > 0:
                        cnt[n] -= 1
                        got.append(n)
                return got
            g0, g1 = corr(a), corr(keep)
            lost += [f"{s}:{n}" for n in (Counter(g0) - Counter(g1)).elements()]
            fpr += (len(a) - len(keep)) - (len(g0) - len(g1))
            C, L = C + len(g1), L + len(keep)
        out[f"r{r}"] = {"correct": C, "listed": L, "correct lost": lost, "false positives removed": fpr}
    return out


def selftest():
    base = rescore({})
    runs = F.C7.runs(F.VERSION, F.REPS)
    ok1 = all((base[f"r{r}"]["correct"], base[f"r{r}"]["listed"]) == (runs[r]["correct"], runs[r]["listed"]) for r in F.REPS)
    one = rescore({"r0": {"wdt": [{"entity": "neorv32_wdt", "element": "ctrl.enable"}]}})
    ok2 = one["r0"]["correct lost"] == ["wdt:ctrl.enable"] and one["r0"]["false positives removed"] == 0
    return ok1 and ok2


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    run_id = sys.argv[1]
    ok, detail = FC.selftest()
    st = selftest()
    print("self-tests: fixcheck planted", "PASS" if ok else "FAIL", "| rescore", "PASS" if st else "FAIL")
    if not (ok and st):
        sys.exit(2)
    J = b2.journal(run_id)
    args = json.loads((RD / "args.json").read_text(encoding="utf-8"))["fixes"]
    (F.HERE / "blind" / "diffs").mkdir(parents=True, exist_ok=True)
    res = {}
    for fx in args:
        s = {"title": args[fx]["title"]}
        dr = load(RD / fx / "draft.json") or (J.get(f"draft:{fx}:rerun") or J.get(f"draft:{fx}"))
        rv = load(RD / fx / "revised.json")
        if rv is None and (J.get(f"revise:{fx}:rerun") or J.get(f"revise:{fx}")):
            rv = J.get(f"revise:{fx}:rerun") or J.get(f"revise:{fx}")
            s["record source"] = "workflow journal (the revision's file write was blocked)"
            (RD / fx / "revised_from_journal.json").write_text(json.dumps(rv, indent=1, ensure_ascii=False), encoding="utf-8")
        A, B = load(RD / "verdicts" / f"{fx}__R-1__A.json"), load(RD / "verdicts" / f"{fx}__R-1__B.json")
        if dr is None:
            s["status"] = "not checked: the drafter failed twice"
        elif A is None or B is None:
            s["status"] = "not checked: a skeptic failed twice"
        elif rv is None:
            s["status"] = "not checked: the revision failed twice"
        if "status" in s:
            res[fx] = s
            continue
        cd, cr = FC.check(dr), FC.check(rv)
        s.update({"kind": rv["kind"], "status": "drafted, challenged, revised",
                  "skeptic A (fix / finding)": [A["fix_verdict"], A["finding_verdict"]],
                  "skeptic B (fix / finding)": [B["fix_verdict"], B["finding_verdict"]],
                  "code check draft": cd["problems"] or "pass", "code check revised": cr["problems"] or "pass",
                  "words added": cr["words added"], "basis": rv["basis"]["label"],
                  "expected precision": rv["expected_precision_effect"]["direction"], "expected recall": rv["expected_recall_effect"]["direction"]})
        cc = (rv.get("wording") or {}).get("code_check") or {}
        if cc.get("script_file"):
            p = Path(cc["script_file"])
            outp = RD / fx / "check_out.json"
            if not cr["ok"]:
                s["code-check run"] = "not run: the code check on the fix failed"
            else:
                try:
                    pr = subprocess.run([sys.executable, "-I", str(p), str(outp)], cwd=str(p.parent), capture_output=True, text=True, timeout=600)
                    s["code-check run"] = {"exit": pr.returncode, "stdout tail": pr.stdout[-600:], "stderr tail": pr.stderr[-400:]}
                    if pr.returncode == 0 and outp.exists():
                        sc = rescore(json.loads(outp.read_text(encoding="utf-8")))
                        s["code-check score"] = {r: {k: (v if k != "correct lost" else v) for k, v in x.items()} for r, x in sc.items()}
                except subprocess.TimeoutExpired:
                    s["code-check run"] = "timed out after 600 s"
        if any(e for e in (rv.get("wording") or {}).get("edits") or []) and cr["ok"]:
            (F.HERE / "blind" / "diffs" / f"{fx}.diff").write_text(cr["diff"], encoding="utf-8")
            s["wording diff"] = F.rel(F.HERE / "blind" / "diffs" / f"{fx}.diff")
        res[fx] = s
    (F.HERE / "rules_status.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for fx, s in res.items():
        sc = s.get("code-check score")
        print(fx, "|", s.get("kind"), "|", s["status"], "| A", s.get("skeptic A (fix / finding)"), "B", s.get("skeptic B (fix / finding)"),
              "| check:", "pass" if s.get("code check revised") == "pass" else s.get("code check revised"),
              "| words", s.get("words added"),
              ("| code check: " + "; ".join(f"{r} lost {len(x['correct lost'])} FP removed {x['false positives removed']}" for r, x in sc.items())) if sc else "")


if __name__ == "__main__":
    main()
