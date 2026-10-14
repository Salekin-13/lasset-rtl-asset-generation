"""After stage C1 (code): recompute every pattern's status from the files alone, compare with the workflow's own
decisions, and check coverage.

Reads, per group: C1/<g>/analyst.json, C1/<g>/revised.json, verdicts/<g>__critic.json, verdicts/<id>__C1-1__{A,B}.json,
verdicts/<id>__C1-recheck__{A,B}.json; and the workflow's run record (its returned result, incl. the items code moved
to the unexplained list after the analyst's re-run) and journal (each agent's returned object).

Rules (the task's "C1 step 4" and "Status of a fix", applied to findings):
  - re-check triggers: a first-round skeptic refuted it (any finding_verdict other than "stands"); the critic flagged it
    (or gave it no verdict); it is new (not in the analyst's file); its record differs in any field other than
    replies_to_reviewers between analyst.json and revised.json (whole record, canonical JSON);
  - a pattern whose first-round skeptic failed twice is "not checked"; a triggered pattern whose re-check skeptic failed
    twice is "not checked";
  - confirmed = not triggered, or triggered and both re-check skeptics "stands"; otherwise "not confirmed".
  - the same for each group's unexplained list (record = its items and reasons).
Coverage: after the revision and after the re-check, every item of the group sits in exactly one of: a confirmed
pattern, a not-confirmed pattern, a not-checked pattern, or the unexplained list.
Each verdict file must equal the journal return of the agent that wrote it in its verdict fields.
Also per pattern: its items' classes (consistent / frequent / intermittent: is it made only of intermittent items?),
whether any Skeptic B file (first round or re-check) found a separating condition.

Writes c1_status.json.   python c1_post.py <C1 run id>
"""
import glob
import json
import os
import sys
from collections import Counter

import common_fa as F
import b2

V = F.HERE / "verdicts"


def canon(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def strip(p):
    return {k: v for k, v in p.items() if k != "replies_to_reviewers"}


def load(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def run_record(run_id):
    f = glob.glob(os.path.expanduser(f"~/.claude/projects/*/*/workflows/{run_id}.json"))
    return json.loads(open(f[0], encoding="utf-8").read()) if f else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    run_id = sys.argv[1]
    rec = run_record(run_id)
    J = b2.journal(run_id)
    args = json.loads((F.HERE / "c1_args.json").read_text(encoding="utf-8"))["groups"]
    res = {g["g"]: g for g in rec["result"]["groups"]}
    fx = json.loads((F.HERE / "funnel_final.json").read_text(encoding="utf-8"))
    fp = json.loads((F.HERE / "fp_typed.json").read_text(encoding="utf-8"))
    cls = {x["item"]: x["class"] for x in fx + fp}
    out, problems, cov_lines = {"patterns": {}, "unexplained": {}, "groups": {}}, [], []

    def jr(label):
        return J.get(label + ":rerun") or J.get(label)

    def vfile(item, rnd, lens):
        x = load(V / f"{item}__{rnd}__{lens}.json")
        lab = ("skeptic" if rnd == "C1-1" else "recheck") + lens + ":" + item
        j = jr(lab)
        if x is not None and j is not None and (x.get("finding_verdict"), (x.get("separating_condition") or {}).get("found")) != \
                (j.get("finding_verdict"), (j.get("separating_condition") or {}).get("found")):
            problems.append(f"{item} {rnd} {lens}: file differs from the journal return in a verdict field")
        if x is None and j is not None:
            problems.append(f"{item} {rnd} {lens}: the agent returned but wrote no file")
        return x

    for g, G in args.items():
        r = res.get(g, {})
        st = {"workflow status": r.get("status")}
        an = load(F.HERE / "C1" / g / "analyst.json")
        if an is None:
            # the harness blocked this analyst's file write; its returned object is in the workflow journal
            an = jr(f"analyst-replace:{g}") or jr(f"analyst:{g}")
            if an is not None:
                st["analyst record"] = "from the workflow journal: the analyst's file write was blocked by the harness"
                (F.HERE / "C1" / g / "analyst_from_journal.json").write_text(json.dumps(an, indent=1, ensure_ascii=False), encoding="utf-8")
        rv = load(F.HERE / "C1" / g / "revised.json")
        critic = load(V / f"{g}__critic.json")
        if an is None:
            st["status"] = "analyst failed"
            out["groups"][g] = st
            for i in G["items"]:
                out["unexplained"].setdefault(g, []).append({"item": i, "reason": "analyst failed"})
            continue
        # code's adjustment after the analyst's re-run (returned by the workflow)
        added = r.get("added") or []
        for a in added:
            for p in an["patterns"]:
                p["items"] = [y for y in p["items"] if y != a["item"]]
            an["unexplained"] = [u for u in an.get("unexplained", []) if u["item"] != a["item"]]
        an["unexplained"] = an.get("unexplained", []) + added
        if rv is None or (r.get("status") or "").startswith("not checked"):
            st["status"] = r.get("status") or "revision missing"
            for p in an["patterns"]:
                out["patterns"][p["id"]] = {"group": g, "status": st["status"], "record": p, "items": p["items"]}
            out["groups"][g] = st
            continue
        before = {p["id"]: p for p in an["patterns"]}
        statuses, trig = {}, {}
        ids = [p["id"] for p in rv["patterns"]] + (([f"{g}-UNEXPLAINED"]) if rv.get("unexplained") else [])
        for it in ids:
            is_u = it.endswith("-UNEXPLAINED")
            A1, B1 = vfile(it, "C1-1", "A"), vfile(it, "C1-1", "B")
            why = []
            if is_u:
                rec_b = sorted([u["item"], u["reason"]] for u in an.get("unexplained", [])) if an.get("unexplained") else None
                rec_a = sorted([u["item"], u["reason"]] for u in rv["unexplained"])
                if rec_b is None:
                    why.append("new")
                elif A1 is None or B1 is None:
                    statuses[it] = "not checked: a first-round skeptic failed twice"
                    continue
                else:
                    if canon(rec_b) != canon(rec_a):
                        why.append("record changed")
                    if A1["finding_verdict"] != "stands" or B1["finding_verdict"] != "stands":
                        why.append("refuted by a skeptic")
            else:
                p = next(q for q in rv["patterns"] if q["id"] == it)
                if it not in before:
                    why.append("new")
                elif A1 is None or B1 is None:
                    statuses[it] = "not checked: a first-round skeptic failed twice"
                    continue
                else:
                    if canon(strip(before[it])) != canon(strip(p)):
                        why.append("record changed")
                    if A1["finding_verdict"] != "stands" or B1["finding_verdict"] != "stands":
                        why.append("refuted by a skeptic")
                    cv = next((c for c in (critic or {}).get("patterns", []) if c["pattern_id"] == it), None)
                    if not cv or cv["verdict"] != "stands":
                        why.append("flagged by the critic")
            if why:
                trig[it] = why
                A2, B2 = vfile(it, "C1-recheck", "A"), vfile(it, "C1-recheck", "B")
                if A2 is None or B2 is None:
                    statuses[it] = "not checked: a re-check skeptic failed twice"
                else:
                    statuses[it] = "confirmed" if A2["finding_verdict"] == "stands" and B2["finding_verdict"] == "stands" else "not confirmed"
            else:
                statuses[it] = "confirmed"
        wf = r.get("statuses") or {}
        if wf != statuses:
            problems.append(f"{g}: statuses from the files {statuses} differ from the workflow's {wf}")
        if (r.get("triggers") or {}) != trig:
            problems.append(f"{g}: re-check triggers from the files differ from the workflow's")
        # coverage after the revision and after the re-check
        seen = Counter()
        for p in rv["patterns"]:
            for i in p["items"]:
                seen[i] += 1
        for u in rv.get("unexplained", []):
            seen[u["item"]] += 1
        bad = [i for i in G["items"] if seen[i] != 1] + [i for i in seen if i not in G["items"]]
        n_ok = sum(1 for i in G["items"] if seen[i] == 1)
        cov_lines.append(f"{g}: coverage after revision {n_ok}/{len(G['items'])}; after re-check {n_ok}/{len(G['items'])}"
                         + (f" PROBLEMS {bad}" if bad else ""))
        if bad:
            problems.append(f"{g}: coverage problem {bad}")
        for p in rv["patterns"]:
            seps = []
            for rnd in ("C1-1", "C1-recheck"):
                b = load(V / f"{p['id']}__{rnd}__B.json")
                if b and (b.get("separating_condition") or {}).get("found"):
                    seps.append({"round": rnd, "condition": b["separating_condition"]["condition"], "evidence": b["separating_condition"]["evidence"]})
            out["patterns"][p["id"]] = {"group": g, "status": statuses[p["id"]], "triggers": trig.get(p["id"], []),
                                        "items": p["items"], "classes": dict(Counter(cls[i] for i in p["items"])),
                                        "only intermittent": all(cls[i] == "intermittent (1 of 3)" for i in p["items"]) if p["items"] else False,
                                        "fix_route": p["fix_route"], "separating conditions found by Skeptic B": seps,
                                        "record file": F.rel(F.HERE / "C1" / g / "revised.json")}
        if rv.get("unexplained"):
            out["unexplained"][g] = {"status": statuses[f"{g}-UNEXPLAINED"], "items": rv["unexplained"]}
        st["status"] = "done"
        st["dropped patterns"] = rv.get("dropped_patterns", [])
        out["groups"][g] = st
    out["problems"] = problems
    out["coverage"] = cov_lines
    tot = len([i for G in args.values() for i in G["items"]])
    placed = sum(len(p["items"]) for p in out["patterns"].values()) + sum(len(u["items"]) if isinstance(u, dict) else len(u) for u in out["unexplained"].values())
    out["coverage total"] = f"{placed}/{tot}"
    (F.HERE / "c1_status.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n".join(cov_lines))
    print("coverage total:", out["coverage total"])
    print("statuses:", dict(Counter(p["status"] for p in out["patterns"].values())))
    print("unexplained lists:", {g: (u["status"], len(u["items"])) if isinstance(u, dict) else len(u) for g, u in out["unexplained"].items()})
    print("problems:", problems or "none")


if __name__ == "__main__":
    main()
