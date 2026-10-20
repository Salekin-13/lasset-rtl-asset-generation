"""Test of the Phase 1 fix drafts (user 2026-10-16: "Test Forwarded transactions as drafted and Build-time values without the
'value computed only from them' part"). Texts: new_rules/rule_texts_v11p.json (variant v11p). Luna, high.

T1 rule-alone re-test (isolation format, v10's context, 41 modules x 2 repeats): Forwarded transactions P1 + P2, Build-time
   values P1. OLD = the latest luna rule-alone run of the v10 text (Forwarded: v10r; Build-time: v9; their contexts carry
   an older shared sentence: a confound, stated).
T2 Phase 1 cells (r0-r1): NEW alone = Phase 1 core + the revised rule; NEW merged = v10 phase1.md with the revised block
   swapped in for the old one. OLD alone = the stored p1clusters cells; OLD merged = the stored v10 run.
   Modules: Forwarded: cpu_icc, xbus, cpu; Build-time: uart, sysinfo, debug_dm.

Readings, set before the run (cuts chosen here):
 T1 ambiguity  each NEW wording: mean per-module disagreement <= 0.157 and contradictions in <= 1 module (D13 cut).
 T1 harm       reference entries barred in both repeats, NEW <= OLD (per wording, all 41 modules).
 T1 intended   Forwarded: slink slink_rx_data_i / slink_tx_data_o / slink_tx_last_o, cpu_lsu wdata_i, cpu_cp_cond rs1_i,
               cpu_alu rs3_i barred in NEITHER repeat (P1 and P2); cpu_icc csr_wdata_i and icc_tx_o.dat barred in both
               repeats (P1). Build-time: uart bus_req_i.data and bus_rsp_o.data not barred in both repeats (the whole-port
               over-application) - reported, no cut.
 T2 fixed      Forwarded: Phase 1 lists cpu_icc csr_wdata_i or icc_tx_o.dat as a concept port in NEW merged in <= 1 of 4
               pairs and at least 2 fewer than OLD merged; Build-time: replies holding a debug ROM concept in debug_dm
               (held lines inside 150-182, or "ROM" in its name), NEW merged fewer than OLD merged.
 T2 guard      reference entries of the six modules that Phase 1 names or line-links: NEW merged at least OLD merged - 1 per
               module; sysinfo's signal sysinfo named or line-linked in every NEW reply.

  python -B p1fix_test.py preview
  <conda python> p1fix_test.py run
  python -B p1fix_test.py measure
"""
import json
import os
import re
import sys
import threading

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import ladder as L  # noqa: E402
import p1probe as P  # noqa: E402
import p1clusters as PC  # noqa: E402
import rule_breaks as RB  # noqa: E402
import analyze_isolation as AN  # noqa: E402
import run_a  # noqa: E402

NEW = json.loads((HERE / "new_rules" / "rule_texts_v11p.json").read_text(encoding="utf-8"))
OLD = {}
for f in ("rule_texts.json", "rule_texts_v10m.json"):
    OLD.update(json.loads((RB.ISOD / f).read_text(encoding="utf-8")))
MODS = {"P1-05": ["neorv32_cpu_icc", "neorv32_xbus", "neorv32_cpu"], "P1-03": ["neorv32_uart", "neorv32_sysinfo", "neorv32_debug_dm"]}
OLD_ALONE = {"P1-05": "P1alone__P105__K2", "P1-03": "P1alone__P103__K3"}
CAP = 28.0


def phase1_texts(rid):
    v10 = (LAB / "prompts" / "two_phase_v10" / "phase1.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert v10.count(OLD[rid]["P1"]) == 1
    merged = v10.replace(OLD[rid]["P1"], NEW[rid]["P1"])
    lines = merged.split("\n")
    end = lines.index("OUTPUT")
    keep = NEW[rid]["title"]
    drop = set()
    for a, b, t in P.blocks(lines, end):
        if P.base_title(t) != keep:
            drop |= set(range(a, b))
    alone = "\n".join(l for i, l in enumerate(lines) if i not in drop)
    return alone, merged


def t2_cells():
    out = {}
    for rid in MODS:
        alone, merged = phase1_texts(rid)
        out[f"P1fix__{rid.replace('-', '')}__alone"] = (alone, MODS[rid])
        out[f"P1fix__{rid.replace('-', '')}__merged"] = (merged, MODS[rid])
    return out


def preview():
    import run_new
    run_new.preview("v11p", "all")
    n = 0
    for name, (text, mods) in t2_cells().items():
        v = P.cell_version(name, text)
        ok = CK.check(v, log=lambda *a: None)
        print(f"{name}: {len(text.split())} words; prompt check {'ok' if ok else 'FAIL'}")
        n += len(mods) * 2
    print(f"T2 calls {n} (about USD {n * 0.022:.2f})")


def run():
    import run_new
    from concurrent.futures import ThreadPoolExecutor
    spent = run_a.spent(log=lambda *a: None)
    print(f"spent so far USD {spent:.2f}; cap {CAP}")
    run_new.CAP = CAP
    run_new.send("v11p", "all")
    cells = t2_cells()
    L.track_folders(list(cells))
    stop = CH._new_run_flag()
    jobs = []
    for name, (text, mods) in cells.items():
        v = P.cell_version(name, text)
        for rep in (0, 1):
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            call = CH.openai(MODEL, EFFORT, out=out, poll=5)
            for m in mods:
                jobs.append((v, m, out, call))
    if run_a.spent(log=lambda *a: None) + len(jobs) * 0.022 > CAP:
        sys.exit("T2 over the cap; not sent")

    def one(j):
        threading.current_thread().lab_stop = stop
        v, m, out, call = j
        try:
            return CH._ask(call, CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                           lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                           adapt=CH.from_format_phase1).get("problems")
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"[:200]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        res = list(pool.map(one, jobs))
    print("T2 done", sum(not isinstance(r, str) for r in res), "of", len(res), [r for r in res if isinstance(r, str)][:2])
    print("spent after USD", round(run_a.spent(log=lambda *a: None), 2))


def iso_sets(variant, rid, ph, m):
    ISO.use(variant)
    reps = []
    for rep in (0, 1):
        f = ISO.run_root(rep=rep) / ph / rid / f"{m}.json"
        reps.append(json.loads(f.read_text(encoding="utf-8")).get("reply") if f.exists() else None)
    ISO.use("v9")
    return reps


def t1():
    import read_v11n as RV
    groups, refl = RB.CV.groups_and_ref()
    mods = groups["tuning"] + groups["held-out"]
    ref = {m: set(v) for m, v in refl.items()}
    out = {}
    for rid, phs in (("P1-05", ("P1", "P2")), ("P1-03", ("P1",))):
        for ph in phs:
            row = {}
            for side, var in (("NEW", "v11p"), ("OLD", RB.source(rid, ph))):
                dis, contra, harm, bars = [], 0, [], {}
                for m in mods:
                    reps = iso_sets(var, rid, ph, m)
                    if None in reps:
                        continue
                    d, c, cons, _ = RV.decide(reps, keep=False)
                    if d is not None:
                        dis.append(d)
                    contra += c
                    harm += [f"{m[8:]}:{e}" for e in ref[m] if RB.down(e, cons)]
                    bars[m] = (cons, AN.names(reps[0], "barred") | AN.names(reps[1], "barred"))
                row[side] = {"mean disagreement": round(sum(dis) / len(dis), 3) if dis else 0.0, "contradiction modules": contra,
                             "reference barred (both repeats)": sorted(harm)}
                row[side + " bars"] = bars
            n, o = row["NEW"], row["OLD"]
            n["ambiguity PASS"] = n["mean disagreement"] <= 0.157 and n["contradiction modules"] <= 1
            n["harm PASS"] = len(n["reference barred (both repeats)"]) <= len(o["reference barred (both repeats)"])
            if rid == "P1-05":
                unbar = ["slink:slink_rx_data_i", "slink:slink_tx_data_o", "slink:slink_tx_last_o", "cpu_lsu:wdata_i",
                         "cpu_cp_cond:rs1_i", "cpu_alu:rs3_i"]
                got = {s: not any(RB.down(s.split(":", 1)[1], row["NEW bars"].get("neorv32_" + s.split(":")[0], (set(), set()))[1]) for _ in [0])
                       for s in unbar}
                n["intended: no longer barred"] = got
                if ph == "P1":
                    n["intended: icc payload barred both"] = {s: RB.down(s.split(":", 1)[1], row["NEW bars"].get("neorv32_cpu_icc", (set(), set()))[0])
                                                              for s in ("cpu_icc:csr_wdata_i", "cpu_icc:icc_tx_o.dat")}
            else:
                n["uart whole data ports barred both (NEW vs OLD)"] = {
                    s: [RB.down(s, row[side + " bars"].get("neorv32_uart", (set(), set()))[0]) for side in ("NEW", "OLD")]
                    for s in ("bus_req_i.data", "bus_rsp_o.data")}
            row.pop("NEW bars"); row.pop("OLD bars")
            out[f"{rid} {ph}"] = row
            print(f"T1 {rid} {ph}: NEW dis {n['mean disagreement']} contra {n['contradiction modules']} ref barred {len(n['reference barred (both repeats)'])} | "
                  f"OLD dis {o['mean disagreement']} contra {o['contradiction modules']} ref barred {len(o['reference barred (both repeats)'])} | "
                  f"ambiguity {'PASS' if n['ambiguity PASS'] else 'FAIL'}, harm {'PASS' if n['harm PASS'] else 'FAIL'}")
            for k in ("intended: no longer barred", "intended: icc payload barred both", "uart whole data ports barred both (NEW vs OLD)"):
                if k in n:
                    print(f"     {k}: {n[k]}")
    return out


def rom_concept(rec):
    cons = CH.phase1_concepts(rec.get("reply")) or []
    return any(("rom" in str(c.get("concept") or "").lower().split() or "ROM" in str(c.get("concept") or ""))
               or any(150 <= int(x) <= 182 for x in CH.as_list(c.get("held lines")) if str(x).isdigit())
               for c in cons)


def port_listed(rec, e):
    cons = CH.phase1_concepts(rec.get("reply")) or []
    return any(e in CH.as_list(c.get("enters through")) + CH.as_list(c.get("leaves through")) for c in cons)


def t2():
    groups, refl = RB.CV.groups_and_ref()
    ref = {m: set(v) for m, v in refl.items()}
    out = {}
    for rid, mods in MODS.items():
        src = {"NEW alone": f"P1fix__{rid.replace('-', '')}__alone", "NEW merged": f"P1fix__{rid.replace('-', '')}__merged",
               "OLD alone": OLD_ALONE[rid], "OLD merged": None}
        res = {}
        for tag, name in src.items():
            r = {"fix case": [0, 0], "reference named or linked": {}}
            for m in mods:
                rr = [0, 0]
                for rep in (0, 1):
                    f = (CH.run_dir(V10, MODEL, rep, EFFORT) if name is None else L.cell_dir(name, rep)) / "phase1" / f"{m}.json"
                    if not f.exists():
                        continue
                    rec = json.loads(f.read_text(encoding="utf-8"))
                    if rid == "P1-05" and m == "neorv32_cpu_icc":
                        for e in ("csr_wdata_i", "icc_tx_o.dat"):
                            r["fix case"][0] += port_listed(rec, e)
                            r["fix case"][1] += 1
                    if rid == "P1-03" and m == "neorv32_debug_dm":
                        r["fix case"][0] += rom_concept(rec)
                        r["fix case"][1] += 1
                    for e in ref[m]:
                        rr[0] += P.p1_named(rec, m, e) != "not in Phase 1"
                        rr[1] += 1
                    if m == "neorv32_sysinfo":
                        r.setdefault("sysinfo kept", []).append(P.p1_named(rec, m, "sysinfo"))
                r["reference named or linked"][m[8:]] = rr
            res[tag] = r
        nm, om = res["NEW merged"], res["OLD merged"]
        if rid == "P1-05":
            fixed = nm["fix case"][0] <= 1 and om["fix case"][0] - nm["fix case"][0] >= 2
        else:
            fixed = nm["fix case"][0] < om["fix case"][0]
        guard = all(nm["reference named or linked"][k][0] >= om["reference named or linked"][k][0] - 1 for k in nm["reference named or linked"])
        if rid == "P1-03":
            guard = guard and all(x != "not in Phase 1" for t in ("NEW alone", "NEW merged") for x in res[t].get("sysinfo kept", []))
        res["FIXED"], res["guard PASS"] = fixed, guard
        out[rid] = res
        print(f"T2 {rid}: fix case (pairs where the break shows) NEW alone {res['NEW alone']['fix case']}, NEW merged {nm['fix case']}, "
              f"OLD alone {res['OLD alone']['fix case']}, OLD merged {om['fix case']} -> FIXED {fixed}")
        print(f"     reference named or linked (NEW merged vs OLD merged): {nm['reference named or linked']} vs {om['reference named or linked']} -> guard {'PASS' if guard else 'FAIL'}")
        if rid == "P1-03":
            print(f"     sysinfo kept: " + "; ".join(f"{t} {res[t].get('sysinfo kept')}" for t in res if isinstance(res[t], dict) and 'sysinfo kept' in res[t]))
    return out


def measure():
    out = {"T1": t1(), "T2": t2()}
    (HERE / "p1fix_test.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"preview": preview, "run": run, "measure": measure}[sys.argv[1]]()
