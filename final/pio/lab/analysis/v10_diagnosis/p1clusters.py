"""Phase 1 cluster test (user 2026-10-16: "we will fix the merged phase 1 first ... form clusters with rules with related /
adjacent scopes ... Then test each clusters failure with the performance of the isolated rules in that cluster. Does the
cluster fail where the isolated pass?").

Clusters: p1_clusters.json (the judged output of the p1-rule-clusters workflow, direct relations only).
Unit: one Phase 1 call (production Phase 1 prompt: v10 phase1.md with only the named rule blocks; p1probe.build_keep), luna,
high, repeats r0-r1, on the cluster's test modules.
Cells per cluster K: "alone" for every rule r in K (core + r) and "cluster" (core + every rule of K, in v10's order).
  Full v10 Phase 1 (stored r0-r1) is read alongside, free.
Test modules: greedy, at most 3 per cluster: the module where most of K's rules decide something alone first, then the
  modules that add a rule not yet covered.
Measure per rule r, over its consistent rule-alone decisions (Phase 1 wording, both repeats) in the test modules:
  bar rule   share of (element, repeat) pairs Phase 1 does NOT name (p1probe.p1_named == "named" is a break; line links
             are reported, not counted: they over-count)
  keep rule  share of pairs Phase 1 names or holds (named or line-linked)
Reading (set before the run): the cluster FAILS WHERE THE ISOLATED PASS for rule r when alone >= 0.8 and
  cluster <= alone - 0.25 and the cluster breaks at least 2 more pairs. A cluster "fails" when any of its rules does.

  python -B p1clusters.py plan        (modules, cells, cost; writes p1clusters_plan.json; sends nothing)
  <conda python> p1clusters.py run
  python -B p1clusters.py measure
"""
import json
import os
import sys
import threading
from collections import defaultdict

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import ladder as L  # noqa: E402
import p1probe as P  # noqa: E402
import rule_breaks as RB  # noqa: E402
import analyze_isolation as AN  # noqa: E402
import run_a  # noqa: E402

PLAN = HERE / "p1clusters_plan.json"
KEEP = {"P1-HO", "P1-10", "P1-26", "P1-24"}
PER_CALL = 0.022
CAP = 25.0


def titles():
    t = {rid: x["title"] for rid, x in json.loads((RB.ISOD / "rule_texts.json").read_text(encoding="utf-8")).items() if rid.startswith("P1-")}
    t["P1-HO"] = "Held outcomes, addresses and settings"
    return t


def decisions(mods):
    R, _, _ = RB.load_latest(mods)
    dec = defaultdict(lambda: defaultdict(set))           # rid -> module -> elements
    for (rid, ph, m, rep), rp in R.items():
        pass
    for rid in {k[0] for k in R if k[1] == "P1"}:
        key = "spared" if rid in KEEP else "barred"
        for m in mods:
            a, b = R.get((rid, "P1", m, 0)), R.get((rid, "P1", m, 1))
            if a is None or b is None:
                continue
            s = {e for e in AN.names(a, key) if AN.covered(e, AN.names(b, key))}
            if s:
                dec[rid][m] = s
    return dec


def plan():
    cl = json.loads((HERE / "p1_clusters.json").read_text(encoding="utf-8"))
    groups, _ = RB.CV.groups_and_ref()
    mods = groups["tuning"] + groups["held-out"]
    dec = decisions(mods)
    T = titles()
    out, calls = {}, 0
    for i, c in enumerate(cl["clusters"], 1):
        rules = [r for r in c["rules"] if r in T]
        chosen, covered = [], set()
        while len(chosen) < 3:
            best = max((m for m in mods if m not in chosen),
                       key=lambda m: (len({r for r in rules if m in dec[r]} - covered), sum(len(dec[r].get(m, ())) for r in rules), m))
            gain = {r for r in rules if best in dec[r]} - covered
            if not gain and chosen:
                break
            chosen.append(best)
            covered |= gain
            if covered >= set(rules):
                break
        if len(chosen) < 2:                              # user 2026-10-16: a second module for one-module clusters
            second = max((m for m in mods if m not in chosen),
                         key=lambda m: (len({r for r in rules if m in dec[r]}), sum(len(dec[r].get(m, ())) for r in rules), m))
            chosen.append(second)
        name = f"K{i}"
        out[name] = {"name": c["name"], "rules": rules, "titles": [T[r] for r in rules], "modules": chosen,
                     "rules without a decision in the test modules": sorted(set(rules) - covered),
                     "decisions": {r: {m[8:]: sorted(dec[r].get(m, ())) for m in chosen} for r in rules}}
        calls += (len(rules) + 1) * len(chosen) * 2
    PLAN.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k, p in out.items():
        print(f"{k} {p['name'][:40]:40s} rules {len(p['rules'])} modules {[m[8:] for m in p['modules']]}"
              + (f" (no decision in them: {p['rules without a decision in the test modules']})" if p['rules without a decision in the test modules'] else ""))
    print(f"calls at most {calls} (stored cells are reused), about USD {calls * PER_CALL:.2f}")
    return out


def cell_list():
    pl = json.loads(PLAN.read_text(encoding="utf-8"))
    T = titles()
    cells = {}
    for k, p in pl.items():
        for r in p["rules"]:
            cells[f"P1alone__{r.replace('-', '')}__{k}"] = {"keep": [T[r]], "modules": p["modules"]}
        order = P.order()
        cells[f"P1cluster__{k}"] = {"keep": sorted([T[r] for r in p["rules"]], key=order.index), "modules": p["modules"]}
    return cells


def run():
    from concurrent.futures import ThreadPoolExecutor
    cells = cell_list()
    todo = []
    for name, c in cells.items():
        for rep in (0, 1):
            for m in c["modules"]:
                if not (L.cell_dir(name, rep) / "phase1" / f"{m}.json").exists():
                    todo.append((name, rep, m))
    spent = run_a.spent(log=lambda *a: None)
    print(f"{len(cells)} cells, {len(todo)} calls to send, about USD {len(todo) * PER_CALL:.2f}; spent so far USD {spent:.2f}; cap {CAP}")
    if spent + len(todo) * PER_CALL > CAP:
        sys.exit("over the cap; nothing sent")
    L.track_folders(list(cells))
    stop = CH._new_run_flag()
    vers, calls = {}, {}
    for name, c in cells.items():
        vers[name] = P.cell_version(name, P.build_keep(c["keep"]))
        for rep in (0, 1):
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            calls[(name, rep)] = CH.openai(MODEL, EFFORT, out=out, poll=5)

    def one(j):
        threading.current_thread().lab_stop = stop
        name, rep, m = j
        v, out = vers[name], L.cell_dir(name, rep)
        try:
            return CH._ask(calls[(name, rep)], CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                           lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                           adapt=CH.from_format_phase1).get("problems")
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"[:200]
    with ThreadPoolExecutor(max_workers=max(1, len(todo))) as pool:
        res = list(pool.map(one, todo))
    bad = [r for r in res if isinstance(r, str)]
    print(f"done {len(res) - len(bad)} of {len(res)}" + (f"; errors {bad[:3]}" if bad else ""))
    print("spent after USD", round(run_a.spent(log=lambda *a: None), 2))


def score(rec, m, elements, keep):
    ok = tot = linked = 0
    for e in elements:
        st = P.p1_named(rec, m, e)
        tot += 1
        linked += st == "line-linked"
        ok += (st != "not in Phase 1") if keep else (st != "named")
    return ok, tot, linked


def measure():
    pl = json.loads(PLAN.read_text(encoding="utf-8"))
    out = {}
    for k, p in pl.items():
        rows = {}
        for r in p["rules"]:
            keep = r in KEEP
            row = {}
            for tag, name in (("alone", f"P1alone__{r.replace('-', '')}__{k}"), ("cluster", f"P1cluster__{k}"), ("full v10", None)):
                ok = tot = lk = 0
                missing = 0
                for m in p["modules"]:
                    els = p["decisions"][r].get(m[8:], [])
                    for rep in (0, 1):
                        f = (CH.run_dir(V10, MODEL, rep, EFFORT) if name is None else L.cell_dir(name, rep)) / "phase1" / f"{m}.json"
                        if not f.exists():
                            missing += 1
                            continue
                        a, b, c = score(json.loads(f.read_text(encoding="utf-8")), m, els, keep)
                        ok, tot, lk = ok + a, tot + b, lk + c
                row[tag] = {"followed": ok, "pairs": tot, "share": round(ok / tot, 3) if tot else None, "line-linked": lk, "missing": missing}
            al, cu = row["alone"], row["cluster"]
            row["cluster fails where alone passes"] = bool(al["share"] is not None and cu["share"] is not None and al["share"] >= 0.8
                                                           and cu["share"] <= al["share"] - 0.25 and (al["followed"] - cu["followed"]) >= 2)
            rows[r] = row
        out[k] = {"name": p["name"], "rules": rows, "cluster fails": any(x["cluster fails where alone passes"] for x in rows.values())}
        print(f"{k} {p['name'][:44]:44s} FAILS: {out[k]['cluster fails']}")
        for r, x in rows.items():
            print(f"   {r:6s} {'keep' if r in KEEP else 'bar ':4s} alone {x['alone']['followed']}/{x['alone']['pairs']} | cluster "
                  f"{x['cluster']['followed']}/{x['cluster']['pairs']} | full v10 {x['full v10']['followed']}/{x['full v10']['pairs']}"
                  + ("  <-- fails in the cluster" if x["cluster fails where alone passes"] else ""))
    (HERE / "p1clusters.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"plan": plan, "run": run, "measure": measure}[sys.argv[1]]()
