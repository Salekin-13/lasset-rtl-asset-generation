"""Cell plans for the staged test (PLAN.md Step D), one round at a time. Writes cells.json entries (ladder.save_cell)
and prints what each round would send. The readings are PLAN.md's; the cut-offs are the constants below.

  python -B plan_cells.py round1            S1 (core + target) and S2 (+ compatible rules) for every target
  python -B plan_cells.py compat <target>   the compatibility table behind S2 (read-only)
  python -B plan_cells.py next <target>     the next cells for one target, from its measured cells (rounds 2+)

Choices (PLAN.md, fixed before the cells run):
  modules     the target's 2 modules with most v10 broken pairs (ties: more consistent-bar elements; then name)
  reps        S1, S2, S4, S4 confirm and load controls: r0-r2; search cells (S2 probes, S3 prefixes): r0-r1
  compatible  another Phase 2 rule that in its luna rule-alone runs never keeps (a primary-making rule listing it as
              spared, in either repeat) an element the target bars consistently, in any of the 41 modules (a bar rule's
              "spared" list is no decision: analyze_isolation's convention); ranked by the elements both bar
              consistently in the test modules ("supporting"), then by membership of the target's v10 rewrite group,
              then by the number of its own consistent bars in the test modules; at most 4, each with at least one
              consistent bar in the test modules
  pass        compliance >= 0.8
  decline     compliance at least 0.25 below S1's and at least 2 more broken pairs
  S3          the remaining Phase 2 rules in v10's order (stages.all_rules), added as prefixes: round 2 at about a
              quarter, a half and three quarters (the whole = full v10, already measured); round 3 single steps of
              two rules inside the first declining quarter; round 4 the last single step
"""
import json
import sys
from collections import defaultdict

from diag_common import HERE, LAB, register

ISO = register()
import ladder as L  # noqa: E402
import rule_breaks as RB  # noqa: E402
import stages as S  # noqa: E402
import analyze_isolation as AN  # noqa: E402

CH = L.CH
PASS, DROP, DROP_PAIRS = 0.8, 0.25, 2
GROUPS = {}
for f in sorted((LAB / "analysis" / "prompt_builds" / "v10" / "dossiers").glob("G*_final.json")):
    for rid in json.loads(f.read_text(encoding="utf-8")):
        GROUPS[rid] = f.stem.split("_")[0]
ALL41 = None


def mods41():
    global ALL41
    if ALL41 is None:
        g, _ = RB.CV.groups_and_ref()
        ALL41 = g["tuning"] + g["held-out"]
    return ALL41


def p2_source(rid):
    return RB.source(rid, "P2")


def replies(rid):
    """{(module, rep): reply} of a Phase 2 rule's luna rule-alone runs (P2 wording)."""
    ISO.use(p2_source(rid))
    out = {}
    for m in mods41():
        for rep in (0, 1):
            f = ISO.run_root(rep=rep) / "P2" / rid / f"{m}.json"
            if f.exists():
                out[(m, rep)] = json.loads(f.read_text(encoding="utf-8")).get("reply") or {}
    ISO.use("v9")
    return out


def consistent(rep_map, m, key="barred"):
    b = [AN.names(rep_map.get((m, r)) or {}, key) for r in (0, 1)]
    cl = {n for (_, n) in CH.closed_names(m)}
    return {e for e in cl if RB.down(e, b[0]) and RB.down(e, b[1])}


def target_modules(t, rb):
    x = rb["M2"][t]
    cnt = defaultdict(int)
    for s in x["broken"]:
        m = "neorv32_" + s.split(":")[0]
        cnt[m] += int(s.split(" v10 ")[1].split("/")[0])
    rid = t.split()[0]
    rm = replies(rid)
    return sorted(cnt, key=lambda m: (-cnt[m], -len(consistent(rm, m)), m))[:2]


def compat(t, mods, log=print):
    rid = t.split()[0]
    rt = replies(rid)
    tbars = {m: consistent(rt, m) for m in mods41()}
    rows = []
    for r in S.all_rules():
        if r == rid:
            continue
        rr = replies(r)
        is_keep = AN.adds(r) or r in ("P1-HO", "P1-26")     # only a primary-making rule's "spared" list is a keep
        kept = [(m, e) for (m, rep), rep_ in rr.items() for e in AN.names(rep_, "spared")
                if is_keep and any(RB.down(e, {b}) or RB.down(b, {e}) for b in tbars[m])]
        ok = not kept
        sup = sum(len(consistent(rr, m) & tbars[m]) for m in mods)
        own = sum(len(consistent(rr, m)) for m in mods)
        rows.append({"rule": r, "compatible": ok, "keeps a target-barred element": sorted(set(f"{m[8:]}:{e}" for m, e in kept))[:6],
                     "supporting (both bar, test modules)": sup, "same group": GROUPS.get(r) == GROUPS.get(rid) and rid in GROUPS,
                     "own consistent bars (test modules)": own})
    good = sorted([x for x in rows if x["compatible"] and x["own consistent bars (test modules)"] > 0],
                  key=lambda x: (-x["supporting (both bar, test modules)"], not x["same group"], -x["own consistent bars (test modules)"], x["rule"]))
    return good[:4], rows


def round1(log=print):
    rb = json.loads((HERE / "rule_breaks.json").read_text(encoding="utf-8"))
    plan = {}
    for t in rb["targets"]:
        rid, ph = t.split()
        if ph != "P2":
            log(f"{t}: a Phase 1-only wording; not in the Phase 2 staged test (PLAN.md)")
            continue
        mods = target_modules(t, rb)
        chosen, rows = compat(t, mods)
        conflicts = [x for x in rows if not x["compatible"]]
        base = rid.replace("-", "")
        s1 = {"target": t, "stage": "S1", "keep": [rid], "last": None, "add_after": None, "modules": mods, "reps": [0, 1, 2],
              "why": "core + target"}
        s2 = {"target": t, "stage": "S2", "keep": [rid] + [x["rule"] for x in chosen], "last": None, "add_after": None,
              "modules": mods, "reps": [0, 1, 2], "why": "core + target + compatible: " + ", ".join(x["rule"] for x in chosen)}
        L.save_cell(f"{base}__S1", s1)
        L.save_cell(f"{base}__S2", s2)
        plan[t] = {"modules": mods, "S2 rules": [x["rule"] for x in chosen], "compatibility": rows,
                   "rules that keep a target-barred element (conflict candidates)": [x["rule"] for x in conflicts]}
        log(f"{t}: modules {[m[8:] for m in mods]}; S2 adds {[x['rule'] for x in chosen]}; conflict candidates "
            f"{[x['rule'] for x in conflicts]}")
    (HERE / "plan_round1.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
    names = [n for n, c in L.cells().items() if c["stage"] in ("S1", "S2")]
    log(f"round 1 cells: {names}; calls {L.to_send(names)}, about USD {L.to_send(names) * L.PER_CALL:.2f}")
    return names


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "round1":
        round1()
    elif cmd == "compat":
        rb = json.loads((HERE / "rule_breaks.json").read_text(encoding="utf-8"))
        t = " ".join(sys.argv[2:4])
        mods = target_modules(t, rb)
        good, rows = compat(t, mods)
        print(json.dumps({"modules": mods, "chosen": good, "all": rows}, indent=1, ensure_ascii=False))
