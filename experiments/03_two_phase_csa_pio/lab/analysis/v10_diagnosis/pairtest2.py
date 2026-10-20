"""Before / after test of the three conflict-pair fixes (conflict_fixes.json: C2 conditional precedence + scope, C4 scope
clarification, C5 conditional precedence), with the fixes placed exactly where the checked analyses put them. Luna,
high, repeats r0-r1. Sends only on `run`.

Expected outcome per element (from the checked analyses, written here before the run): True = primary (Phase 2 cell) or
named / its lines held (Phase 1 cell); False = not. Groups: conflict (the precedence decides), bar_only and keep_only (the
compatible cases: each rule alone), unrelated (other elements the fix must not move).
Readings (set before the run):
  conflict   share of (element, repeat) pairs decided as expected; FIXED when AFTER >= 0.8 and (AFTER - BEFORE >= 0.25 or
             BEFORE already >= 0.8)
  compatible bar_only and keep_only: AFTER share at least BEFORE - 0.1
  unrelated  listed elements: AFTER share at least BEFORE - 0.1; and, Phase 2 only, primaries outside every group:
             shared / union of BEFORE and AFTER >= 0.8
Phase 1 "kept" = named, or one of its occurrence lines is a held / entry / exit line (p1probe.p1_named; line links
over-count, so a bar is read as followed only when Phase 1 neither names it nor cites its lines).

  python -B pairtest2.py check     (builds the prompts, runs the prompt checker, prints the inserted text; sends nothing)
  <conda python> pairtest2.py run
  python -B pairtest2.py measure
"""
import json
import os
import sys
import threading

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, MODEL, EFFORT, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import ladder as L  # noqa: E402
import p1probe as P  # noqa: E402
import stages as S  # noqa: E402
import run_a  # noqa: E402

FX = {x["id"]: x for x in json.loads((HERE / "conflict_fixes.json").read_text(encoding="utf-8"))}
C2_P2A = ("Like every bar in this step, Forwarded transactions (c) wins over the sentence above on a non-record unit input "
          "port the RTL copies, reduces or wires into an instance: a port meeting that bar's scope and criteria, with no "
          "exception covering it, is not primary under a conceptual asset its outcome names; that sentence judges every "
          "other port as usual.")
C2_P2B = ("an operand that a non-record unit input port brings to an operation a statement of this unit performs, even one "
          "only returning the operand or a constant, or to an instance other than a buffer that computes from it; data a "
          "statement of this unit slices or replicates into a register of its own; ")
C4_FXA = ("For an access address, this rule adds only the instance ports above as held lines; a register holding that address "
          "is judged as if this rule were absent, so where Held addresses covers it, its lines are not held lines.")
C4_FXB = ("A read-back word returning the address bits unchanged counts as an address it feeds (it only carries them, 2.6); a "
          "register whose bits also pick which bytes of a received response word are returned, which is not indexing a "
          "memory, is not covered: judge it as usual.")
C5_FIX = FX["C5"]["fix_text"].strip()
for t in (C2_P2A, C2_P2B.strip("; "), C4_FXA, C4_FXB):
    assert t.split()[0] in " ".join(FX[c]["fix_text"] for c in ("C2", "C4")), t[:40]

EXPECT = {
    "C2": {"modules": ["neorv32_cpu_alu", "neorv32_cpu_cp_cond", "neorv32_cpu_icc", "neorv32_cpu_lsu", "neorv32_slink"], "phase": 2,
           "conflict": {"cpu_icc:csr_wdata_i": False, "cpu_alu:rs3_i": True, "cpu_cp_cond:rs1_i": True, "cpu_lsu:wdata_i": True,
                        "slink:slink_rx_data_i": True},
           "bar_only": {"cpu_lsu:dbus_req_o.data": False, "slink:rx_fifo.rdata": False, "slink:rx_fifo.wdata": False,
                        "slink:tx_fifo.rdata": False, "slink:slink_tx_data_o": True, "slink:slink_tx_last_o": True},
           "keep_only": {"cpu_alu:rs1_i": True, "cpu_alu:rs2_i": True, "cpu_lsu:addr_i": True, "cpu_lsu:pmp_fault_i": True,
                         "slink:slink_rx_last_i": True, "slink:slink_rx_src_i": True},
           "unrelated": {"cpu_cp_cond:res_o": True}},
    "C4": {"modules": ["neorv32_debug_dtm", "neorv32_sysinfo", "neorv32_cpu_lsu", "neorv32_imem"], "phase": 1,
           "conflict": {"debug_dtm:dmi_ctrl.addr": False, "sysinfo:buf_adr": False, "cpu_lsu:mar": True},
           "bar_only": {"imem:addr_ff": False},
           "keep_only": {"debug_dtm:dmi_ctrl.busy": True, "cpu_lsu:rdata_o": True},
           "unrelated": {"cpu_lsu:misaligned": True}},
    "C5": {"modules": ["neorv32_twi", "neorv32_pwm", "neorv32_sdi", "neorv32_wdt"], "phase": 1,
           "conflict": {"twi:engine.done": False, "pwm:cnt_tick": False, "sdi:serial.done": False, "twi:clk_gen.tick": False},
           "bar_only": {"pwm:cnt_cdiv": False, "sdi:rx_fifo.re": False, "sdi:rx_fifo.we": False, "sdi:tx_fifo.we": False},
           "keep_only": {"wdt:reset_wdt": True},
           "unrelated": {"pwm:clkgen_i": None}},          # None: report only (a reference entry the existing bar covers)
}


def p1_with(keep_titles, appends):
    """Phase 1 core + the rule blocks, each (title, sentence) appended as the last line of that rule's block."""
    lines = P.build_keep(keep_titles).split(P.LF)
    for title, sent in appends:
        blk = [(a, b, t) for a, b, t in P.blocks(lines, lines.index("OUTPUT")) if P.base_title(t) == title]
        a, b, _ = blk[-1]
        if b - a == 1:                                  # a one-line bullet: append the sentence to it
            lines[a] = lines[a] + " " + sent
        else:
            lines.insert(b, "  " + sent)
    return P.LF.join(lines)


def texts():
    out = {}
    b2 = S.build_p2({"P1-05", "P2X-input-port-setting-the-value"})
    end = b2.index("is labelled as if this sentence were absent.", b2.index("A non-record unit input port")) + len("is labelled as if this sentence were absent.")
    a2 = b2[:end] + " " + C2_P2A + b2[end:]
    anchor = "and data the unit stores (not a register stage's copy)"
    assert a2.count(anchor) == 1
    a2 = a2.replace(anchor, C2_P2B + anchor)
    out["C2"] = (b2, a2)
    out["C4"] = (P.build_keep(["Held addresses", "Held outcomes, addresses and settings"]),
                 p1_with(["Held addresses", "Held outcomes, addresses and settings"],
                         [("Held outcomes, addresses and settings", C4_FXA), ("Held addresses", C4_FXB)]))
    out["C5"] = (P.build_keep(["Pacing pulses", "Held outcomes, addresses and settings"]),
                 p1_with(["Pacing pulses", "Held outcomes, addresses and settings"],
                         [("Held outcomes, addresses and settings", C5_FIX)]))
    return out


def cell_names(cid):
    return f"{cid}__before", f"{cid}__after"


def check():
    for cid, (bt, at) in texts().items():
        print(f"{cid}: before {len(bt.split())} words, after {len(at.split())} (+{len(at.split()) - len(bt.split())})")
        for name, t in zip(cell_names(cid), (bt, at)):
            if EXPECT[cid]["phase"] == 2:
                v = S.write_prompt(name, t, f"# {name}\n\nConflict-pair test (pairtest2.py).\n")
            else:
                v = P.cell_version(name, t)
            print("   ", name, "prompt check:", "ok" if CK.check(v, log=lambda *a: None) else "FAIL")


def run():
    from concurrent.futures import ThreadPoolExecutor
    tx = texts()
    n = sum(len(e["modules"]) * 2 * 2 for e in EXPECT.values())
    spent = run_a.spent(log=lambda *a: None)
    print(f"at most {n} calls; spent so far USD {spent:.2f}")
    if spent + n * 0.022 > 21.5:
        sys.exit("over the cap 21.5; nothing sent")
    stop = CH._new_run_flag()
    c = L.cells()
    names2, jobs1 = [], []
    for cid, e in EXPECT.items():
        for name, t in zip(cell_names(cid), tx[cid]):
            L.track_folders([name])
            if e["phase"] == 2:
                c[name] = {"target": cid, "stage": "pair2", "keep": ["P1-05", "P2X-input-port-setting-the-value"], "last": None,
                           "add_after": None, "p2_text": t, "modules": e["modules"], "reps": [0, 1], "why": "conflict pair " + cid}
                names2.append(name)
            else:
                v = P.cell_version(name, t)
                for rep in (0, 1):
                    out = L.cell_dir(name, rep)
                    out.mkdir(parents=True, exist_ok=True)
                    call = CH.openai(MODEL, EFFORT, out=out, poll=5)
                    for m in e["modules"]:
                        jobs1.append((v, m, out, call))
    (HERE / "cells.json").write_text(json.dumps(c, indent=1, ensure_ascii=False), encoding="utf-8")

    def one(j):
        threading.current_thread().lab_stop = stop
        v, m, out, call = j
        return CH._ask(call, CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                       lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                       adapt=CH.from_format_phase1).get("problems")
    with ThreadPoolExecutor(max_workers=len(jobs1) or 1) as pool:
        list(pool.map(one, jobs1))
    L.run(names2)
    print("spent after USD", round(run_a.spent(log=lambda *a: None), 2))


def measure():
    out = {}
    for cid, e in EXPECT.items():
        res = {}
        prims = {}
        for tag, name in zip(("before", "after"), cell_names(cid)):
            r = {}
            got = {}
            for m in e["modules"]:
                for rep in (0, 1):
                    if e["phase"] == 2:
                        f = L.cell_dir(name, rep) / "assets" / f"{m}.json"
                        got[(m, rep)] = {x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]} if f.exists() else None
                    else:
                        f = L.cell_dir(name, rep) / "phase1" / f"{m}.json"
                        got[(m, rep)] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
            prims[tag] = got
            for grp in ("conflict", "bar_only", "keep_only", "unrelated"):
                ok = tot = 0
                for item, want in e[grp].items():
                    mod, el = item.split(":", 1)
                    m = "neorv32_" + mod
                    for rep in (0, 1):
                        g = got.get((m, rep))
                        if g is None:
                            continue
                        val = (el in g) if e["phase"] == 2 else (P.p1_named(g, m, el) != "not in Phase 1")
                        if want is None:
                            r.setdefault("report only", []).append(f"{item} r{rep}: {val}")
                            continue
                        tot += 1
                        ok += val == want
                r[grp] = [ok, tot]
            res[tag] = r
        if e["phase"] == 2:
            named = {k.split(":", 1)[1] for g in ("conflict", "bar_only", "keep_only", "unrelated") for k in e[g]}
            sh = un = 0
            for k in prims["before"]:
                a, b = prims["before"][k] or set(), prims["after"].get(k) or set()
                a, b = a - named, b - named
                sh += len(a & b)
                un += len(a | b)
            res["other primaries, shared / union"] = [sh, un, round(sh / un, 3) if un else None]
        cb, ca = res["before"]["conflict"], res["after"]["conflict"]
        rb_, ra = (cb[0] / cb[1] if cb[1] else 0), (ca[0] / ca[1] if ca[1] else 0)
        res["conflict FIXED"] = ra >= 0.8 and (ra - rb_ >= 0.25 or rb_ >= 0.8)
        res["compatible kept"] = all((res["after"][g][0] / res["after"][g][1] if res["after"][g][1] else 1) >=
                                     (res["before"][g][0] / res["before"][g][1] if res["before"][g][1] else 1) - 0.1 for g in ("bar_only", "keep_only"))
        u0, u1 = res["before"]["unrelated"], res["after"]["unrelated"]
        res["unrelated kept"] = ((u1[0] / u1[1] if u1[1] else 1) >= (u0[0] / u0[1] if u0[1] else 1) - 0.1) and \
                                (e["phase"] == 1 or (res["other primaries, shared / union"][2] or 0) >= 0.8)
        out[cid] = res
        print(f"{cid}: conflict {cb} -> {ca} | bar-only {res['before']['bar_only']} -> {res['after']['bar_only']} | keep-only "
              f"{res['before']['keep_only']} -> {res['after']['keep_only']} | unrelated {u0} -> {u1}"
              + (f" | other primaries {res['other primaries, shared / union']}" if e["phase"] == 2 else "")
              + f" || FIXED {res['conflict FIXED']}, compatible kept {res['compatible kept']}, unrelated kept {res['unrelated kept']}")
    (HERE / "pairtest2.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"check": check, "run": run, "measure": measure}[sys.argv[1]]()
