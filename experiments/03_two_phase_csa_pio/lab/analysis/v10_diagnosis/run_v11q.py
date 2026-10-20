"""Rule-alone tests of the v11 blind-spot drafts N11-N15 (user 2026-10-17: "analyze the failure patterns of v11 ... draft rules
to address them and perform isolated tests of the rules to verify they find target assets or bar FPs").
Texts: new_rules/rule_texts_v11q.json; meta (kind, basis, intended cases, must-spare): new_rules/meta_v11q.json. Drafted by
workflow wf_b7bc621c-cef from blindspots_v11.json (v11 r0's errors no rule covers); N14's criterion (2) narrowed after a
blind judge barred a reference entry with it.
Format: the isolation format (old reply format, max_tokens 64,000), in the v11n tests' context (context_p1_v10m.md /
context_p2_v10m.md = v10's core with the merged procedure, no other rule), luna, high, r0-r1.
Modules (targeted, to save budget): the Phase 2 wording on every module of the rule's intended and must-spare cases; the
Phase 1 wording on the intended cases' modules only. Harm in other modules is NOT measured (stated in the report).
Readings (decision D13's cuts, as for N01-N10; set 2026-10-17 before sending):
  ambiguity  per wording: mean per-module disagreement <= 0.157 and contradictions in <= 1 module (read_v11n.decide)
  coverage   Phase 2 wording: intended cases decided as intended in both repeats (bar: barred; keep: kept), share >= 0.8;
             Phase 1 reported
  harm       bar: reference entries barred in both repeats, on the tested modules: 0. keep: non-reference elements kept in
             both repeats no more than the reference entries it recovers
  must-spare listed: each must-spare case barred (bar rule) or kept (keep rule) in both repeats
  PASS per rule = every tested wording passes ambiguity and harm, and the Phase 2 coverage passes.
  Basis: N11 and N15 need a logged user decision (reference convention) before any adoption; a PASS is not adoption.

  python -B run_v11q.py selftest
  python -B run_v11q.py preview
  <conda python> run_v11q.py run          (cap 100 requests, USD 1.5)
  python -B run_v11q.py measure           (writes read_v11q.json and v11q_test.json)
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, MODEL, EFFORT, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import analyze_isolation as AN  # noqa: E402
import rule_breaks as RB  # noqa: E402
import ladder as L  # noqa: E402
import run_a  # noqa: E402

ISO.VARIANTS["v11q"] = {"run": "rule_isolation_v11q", "texts": str(HERE / "new_rules" / "rule_texts_v11q.json"),
                        "ctx": (str(ISO.HERE / "context_p1_v10m.md"), str(ISO.HERE / "context_p2_v10m.md"))}
META = json.loads((HERE / "new_rules" / "meta_v11q.json").read_text(encoding="utf-8"))
CAP_N, CAP_USD, PER = 100, 1.5, 0.0115


def mods_of(cases):
    return sorted({c.split(":")[0] for c in cases})


def jobs():
    ISO.use("v11q")
    tx = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    jl = []
    for rid, m in META.items():
        p2 = mods_of(m["intended_cases"] + m["must_spare"])
        p1 = mods_of(m["intended_cases"])
        jl += [(rid, "P2", mod, r) for mod in p2 for r in (0, 1)]
        if tx[rid].get("P1"):
            jl += [(rid, "P1", mod, r) for mod in p1 for r in (0, 1)]
    todo = [j for j in jl if not ISO.path(*j).exists()]
    ISO.use("v9")
    return jl, tx, todo


def selftest(log=print):
    c = {}
    ISO.use("v11q")
    tx = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    sq = {ph: CH.sha12(ISO.system(ph)) for ph in ("P1", "P2")}
    m = "neorv32_pwm"
    u = ISO.user(m, "N11", "P2", tx)
    ISO.use("v11n")
    sn = {ph: CH.sha12(ISO.system(ph)) for ph in ("P1", "P2")}
    ISO.use("v9")
    c["v11q uses the v11n tests' context (same system text)"] = sq == sn
    c["the N11 P2 request carries the rule text"] = tx["N11"]["P2"].split("\n")[1].strip() in u
    c["5 rules, each with intended and must-spare cases"] = len(META) == 5 and all(x["intended_cases"] and x["must_spare"] for x in META.values())
    c["every case module has inputs"] = all((CH.module_dir(mm) / "rtl.txt").exists() for x in META.values() for mm in mods_of(x["intended_cases"] + x["must_spare"]))
    c["isolation self-test"] = ISO.selftest(log=lambda *a: None)
    bad = [k for k, v in c.items() if not v]
    log(f"run_v11q self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    jl, tx, todo = jobs()
    print(f"{len(todo)} requests to send (of {len(jl)}); about USD {len(todo) * PER:.2f} at USD {PER} per request (v12t's 41-module mean was 0.0091; these modules are larger on average)")
    ISO.use("v11q")
    ISO.preview(todo, tx)
    ISO.use("v9")
    print(f"spent so far USD {run_a.spent(log=lambda *a: None):.2f}")


def run():
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    jl, tx, todo = jobs()
    if len(todo) > CAP_N or len(todo) * PER > CAP_USD:
        sys.exit("over the cap; nothing sent")
    ex = json.loads(L.EXTRA.read_text(encoding="utf-8")) if L.EXTRA.exists() else []
    p = str(ISO.LAB / "runs" / "rule_isolation_v11q" / f"{MODEL}__{EFFORT}") if hasattr(ISO, "LAB") else str(L.LAB / "runs" / "rule_isolation_v11q" / f"{MODEL}__{EFFORT}")
    L.EXTRA.write_text(json.dumps(ex + ([p] if p not in ex else []), indent=1), encoding="utf-8")
    ISO.use("v11q")
    print(f"sending {len(todo)}")
    ISO.run(todo, tx, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5, max_tokens=64000), MODEL, EFFORT, workers=50)
    ISO.use("v9")


def measure():
    import read_v11n as RV
    RV.main("v11q")                                  # writes read_v11q.json (ambiguity, coverage, harm per wording)
    rd = json.loads((HERE / "read_v11q.json").read_text(encoding="utf-8"))
    _, refl = RB.CV.groups_and_ref()
    ISO.use("v11q")
    out = {}
    for rid, m in META.items():
        keep = m["kind"].startswith("keep")
        key = "spared" if keep else "barred"
        ms = []
        for case in m["must_spare"]:
            mod, e = case.split(":", 1)
            reps = []
            for r in (0, 1):
                f = ISO.run_root(rep=r) / "P2" / rid / f"{mod}.json"
                rep = json.loads(f.read_text(encoding="utf-8")).get("reply") if f.exists() else None
                reps.append(isinstance(rep, dict) and RB.down(e, AN.names(rep, key)))
            if all(reps):
                ms.append(f"{mod[8:]}:{e} ({'kept' if keep else 'barred'} in both)")
        intended = []
        for case in m["intended_cases"]:
            mod, e = case.split(":", 1)
            st = []
            for ph in ("P1", "P2"):
                for r in (0, 1):
                    f = ISO.run_root(rep=r) / ph / rid / f"{mod}.json"
                    rep = json.loads(f.read_text(encoding="utf-8")).get("reply") if f.exists() else None
                    if isinstance(rep, dict):
                        st.append(f"{ph} r{r}: " + ("barred" if RB.down(e, AN.names(rep, "barred")) else "kept" if e in AN.names(rep, "spared") else "-"))
            intended.append({"case": f"{mod[8:]}:{e}", "reference": e in refl.get(mod, ()), "decisions": st})
        out[rid] = {"title": META[rid].get("draft id"), "kind": m["kind"], "basis": m["basis_kind"],
                    "read_v11q": {k: v for k, v in rd.items() if k == rid or k.startswith(rid + " ")},
                    "intended cases": intended, "must-spare decided against": ms}
    ISO.use("v9")
    (HERE / "v11q_test.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False)[:9000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview, "run": run, "measure": measure}[sys.argv[1]]()
