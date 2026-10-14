"""Stage C2 decisions in code, from the files alone.

  python c2_post.py after1      after the first C2 workflow (drafter, two skeptics, revision)
  python c2_post.py after2      after the re-check workflow

after1, per fix item C2/<FX>/:
  - the prompt-rule code check (fixcheck.check: meta_tools on the wording, planted self-test first) on draft.json and on
    revised.json;
  - re-check triggers (C2 step 5): a first-round skeptic refuted the fix or the finding (any verdict other than "stands");
    the draft's code check failed (before the re-check a failure counts as a refutation); the revised wording's code
    check failed (likewise); the record differs in any field other than replies_to_reviewers between draft.json and
    revised.json (whole record; file_written, the path the agent wrote to, is bookkeeping and left out);
  - findings to send to two fresh finding skeptics: those of a fix whose first-round skeptic refuted the finding.
  Writes c2_after1.json, including the arguments of the re-check workflow.
after2:
  - a fix stands only if: its findings are confirmed in C1 (true for every fix item by construction) and no fresh
    finding skeptic refuted them; in C2 it had no first-round refutation and no trigger, or neither re-check skeptic
    refuted it (fix or finding); and its current wording (revised.json) passed the code check;
  - a re-check skeptic's finding_verdict "refuted" counts as a refutation of the fix, and the finding then also needs
    two fresh finding skeptics (listed as "finding rechecks still needed" if not yet done);
  - a missing verdict file of a checking agent = "not checked".
  Writes c2_status.json and, for every surviving fix, blind/diffs/<FX>.diff (the wording as a diff against v7).
"""
import json
import sys

import common_fa as F
import fixcheck as FC

C2 = F.HERE / "C2"
V = F.HERE / "verdicts"


def load(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def rec_of(x):
    return {k: v for k, v in (x or {}).items() if k not in ("replies_to_reviewers", "file_written")}


def after1():
    ok, detail = FC.selftest()
    print("fixcheck planted self-test:", "PASS" if ok else f"FAIL {detail}")
    if not ok:
        sys.exit(2)
    c1 = json.loads((F.HERE / "c1_status.json").read_text(encoding="utf-8"))
    args = json.loads((F.HERE / "c1_args.json").read_text(encoding="utf-8"))["groups"]
    out, rechecks, frech = {}, {}, {}
    for d in sorted(C2.glob("FX*")):
        fx = d.name
        item = load(d / "item.json")
        dr, rv = load(d / "draft.json"), load(d / "revised.json")
        A, B = load(V / f"{fx}__C2-1__A.json"), load(V / f"{fx}__C2-1__B.json")
        s = {"title": item["title"], "findings": [f["id"] for f in item["findings"]]}
        if dr is None:
            s["status"] = "not checked: the drafter failed twice"
        elif A is None or B is None:
            s["status"] = "not checked: a fix skeptic failed twice"
        elif rv is None:
            s["status"] = "not checked: the revision failed twice"
        if "status" in s:
            out[fx] = s
            continue
        cd, cr = FC.check(dr), FC.check(rv)
        s["code check draft"] = cd["problems"] or "pass"
        s["code check revised"] = cr["problems"] or "pass"
        s["first round"] = {"A": [A["fix_verdict"], A["finding_verdict"]], "B": [B["fix_verdict"], B["finding_verdict"]]}
        why = []
        if A["fix_verdict"] != "stands" or B["fix_verdict"] != "stands":
            why.append("a skeptic refuted the fix")
        if A["finding_verdict"] != "stands" or B["finding_verdict"] != "stands":
            why.append("a skeptic refuted the finding (counts as a refutation of the fix)")
            for f in item["findings"]:
                frech[f["id"]] = {"group": f["group"], "title": f["name"], "pack": str(F.ROOT / f["evidence pack"]).replace("/", "\\")}
        if not cd["ok"]:
            why.append("the draft failed the code check")
        if not cr["ok"]:
            why.append("the revised wording failed the code check")
        if json.dumps(rec_of(dr), sort_keys=True) != json.dumps(rec_of(rv), sort_keys=True):
            why.append("record changed in the revision")
        s["triggers"] = why
        if why:
            rechecks[fx] = {"title": item["title"], "item_file": str(d / "item.json"), "why": why}
        s["status"] = "re-check needed" if why else "stands after the first round"
        out[fx] = s
    res = {"fixes": out, "recheck args": {"rechecks": rechecks, "finding_rechecks": frech}}
    (F.HERE / "c2_after1.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for fx, s in out.items():
        print(fx, "|", s["status"], "|", s.get("triggers"), "| check draft:", "pass" if s.get("code check draft") == "pass" else s.get("code check draft"),
              "| revised:", "pass" if s.get("code check revised") == "pass" else s.get("code check revised"))
    print(f"re-checks: {len(rechecks)} fixes, {len(frech)} findings")


def after2():
    a1 = json.loads((F.HERE / "c2_after1.json").read_text(encoding="utf-8"))
    out, still = {}, []
    (F.HERE / "blind" / "diffs").mkdir(parents=True, exist_ok=True)
    fstat = {}
    for pid in a1["recheck args"]["finding_rechecks"]:
        A, B = load(V / f"{pid}__C2-finding__A.json"), load(V / f"{pid}__C2-finding__B.json")
        fstat[pid] = ("not checked: a finding skeptic failed twice" if A is None or B is None
                      else "confirmed" if A["finding_verdict"] == "stands" and B["finding_verdict"] == "stands" else "not confirmed")
    for fx, s in a1["fixes"].items():
        s = dict(s)
        if s["status"].startswith("not checked"):
            out[fx] = s
            continue
        rv = load(C2 / fx / "revised.json")
        cr = FC.check(rv)
        bad_f = [f for f in s["findings"] if fstat.get(f) and fstat[f] != "confirmed"]
        if s["triggers"]:
            A, B = load(V / f"{fx}__C2-recheck__A.json"), load(V / f"{fx}__C2-recheck__B.json")
            if A is None or B is None:
                s["status"] = "not checked: a re-check skeptic failed twice"
            else:
                s["re-check"] = {"A": [A["fix_verdict"], A["finding_verdict"]], "B": [B["fix_verdict"], B["finding_verdict"]]}
                if "stands" == A["fix_verdict"] == B["fix_verdict"] == A["finding_verdict"] == B["finding_verdict"]:
                    s["status"] = "stands"
                else:
                    s["status"] = "fix not confirmed"
                    if A["finding_verdict"] != "stands" or B["finding_verdict"] != "stands":
                        for f in s["findings"]:
                            if f not in fstat:
                                still.append(f)
        else:
            s["status"] = "stands"
        if bad_f:
            s["status"] = f"finding not confirmed ({', '.join(bad_f)}): fix not ranked"
        if s["status"] == "stands" and not cr["ok"]:
            s["status"] = "fix not confirmed: code check"
        s["code check current wording"] = cr["problems"] or "pass"
        s["words added"] = cr["words added"]
        if s["status"] == "stands":
            (F.HERE / "blind" / "diffs" / f"{fx}.diff").write_text(cr["diff"], encoding="utf-8")
        out[fx] = s
    res = {"fixes": out, "finding re-checks": fstat, "finding rechecks still needed": sorted(set(still))}
    (F.HERE / "c2_status.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for fx, s in out.items():
        print(fx, "|", s["status"])
    print("finding re-checks:", fstat, "| still needed:", sorted(set(still)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"after1": after1, "after2": after2}[sys.argv[1]]()
