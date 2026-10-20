"""two_phase_v11 = v10 + the carried fixes (PLAN_MERGED.md; user 2026-10-17: "Build stage 0 (make_v11.py, the readers with
their self-tests, the attribution table), send the Phase 1 smoke batch and stop if a reading fails, then the Stage A order
test, then r0 with the stop gate, then r1-r2, all with the readings and caps in PLAN_MERGED.md, and report.").
This file is make_v11.py and the readers in one: the builder writes prompts/diag_v10/P1m__O1 and P1m__O2 (Stage A cells)
and, after Stage A, prompts/two_phase_v11.

Fixes: F1 Access command fields = carried_P1-23.json (phase1.md lines 157-168); F2 Forwarded transactions P1 = v11p
"P1-05" (lines 44-55); F3 Operation selectors (phase2.md lines 139-145) moved to the end of step 4 + the 48-word sentence
after it; F4 the bus record-port sentence (end of phase2.md line 41) moved to the end of step 4. Order O1: bus, OS,
sentence; O2: OS, sentence, bus.

Readings (copied from PLAN_MERGED.md before any call; full definitions there):
  4b smoke (v11 phase1, 7 modules x r0-r1): S1 cpu_regfile replies naming >= 3 of its 6 barred fields: 2/2 -> stop.
     S2 slink_rx_data_i / slink_tx_data_o / slink_tx_last_o named or line-linked, v11 r0-r1 >= v10 r0-r1, else stop.
     S3 cpu_alu replies naming any of its 4 barred signals, v11 vs v10 r0-r1 (read).
  4c Stage A (O1, O2, v10 phase2 on v11's Phase 1 r0-r1; 4 modules): order = larger summed compliance over the two
     targets (Operation selectors on cpu_cp_bitmanip / cpu_cp_fpu; bus bar on cpu_control / cpu_frontend); tie -> O1;
     never removes a fix. Read: each order vs the base; Operation selectors elements labelled secondary.
  Stop gate after r0: stop if v11 r0 tuning_v2 recall < 0.694 (143/206) or precision < 0.404, or heldout_v2 recall
     < 0.767 (69/90) or precision < 0.530.
  M1 tuning_v2 and M2 heldout_v2 vs v9 (cuts 0.02 / 0.03), both needed; M3 stability; M4 per-fix Phase 2 non-reference
  breaks lower than v10 by >= 3, reference pairs not lower by > 1, slink's data entries; M5 load (20 unchanged rules,
  non-reference named <= 116 + m), F1 / F2 against their own bars (lower by >= 3), T2 <= 1 of 6, F2 guard shares
  (cpu_icc, xbus, cpu, slink, cpu_lsu, cpu_alu) not lower than v10 by > 0.10; M6 watch items both directions; M7 v10's
  V4 / V5; M8 output tokens per call.
Caps (USD): smoke 0.5, Stage A 1.2, r0 2.5, r1-r2 5.0.

  python -B v11.py selftest
  python -B v11.py build-cells            (writes the two Stage A prompt folders)
  python -B v11.py preview <step>          (smoke | stagea | r0 | r12: calls and cost estimate; sends nothing)
  <conda python> v11.py smoke | stagea | r0 | r12
  python -B v11.py read-smoke | read-stagea | finalize | gate | measure
"""
import json
import os
import shutil
import sys
import threading
from collections import Counter
from pathlib import Path

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import stages as S  # noqa: E402
import ladder as L  # noqa: E402
import p1probe as P  # noqa: E402
import p1clusters as PC  # noqa: E402
import rule_breaks as RB  # noqa: E402
import analyze_isolation as AN  # noqa: E402
import read_v10 as R10  # noqa: E402
import run_a  # noqa: E402
import p1tighten  # noqa: E402,F401  (registers the v12c_old / v12c_new / v12n / v12t rule-alone variants)

V11, V9 = "two_phase_v11", "two_phase_v9"
V10D = LAB / "prompts" / "two_phase_v10"
CELL = {"O1": "P1m__O1", "O2": "P1m__O2", "base": "P1m__base"}
FT_NEW = json.loads((HERE / "new_rules" / "rule_texts_v11p.json").read_text(encoding="utf-8"))["P1-05"]["P1"]
ACF_NEW = json.loads((HERE / "carried_P1-23.json").read_text(encoding="utf-8"))["P1-23"]["P1"]
SENT = ("The bar just above holds for every element it covers even where 2.6, this step's first sentence or CONCEPTS (its "
        "held lines, its information or the points it names) would make that element primary: label such an element "
        "secondary to a primary it serves, or leave it unreported.")
BUS = "A bus request or response record port, or any field of one, never qualifies (2.6), even as the conceptual asset's only entry or exit port."
BUS_ID = "P2X-bus-request-response-record-port"
SMOKE = ["neorv32_cpu_regfile", "neorv32_cpu_alu", "neorv32_slink", "neorv32_cpu_cp_bitmanip", "neorv32_cpu_cp_fpu",
         "neorv32_cpu_control", "neorv32_cpu_frontend"]
OS_MODS, BUS_MODS = ["neorv32_cpu_cp_bitmanip", "neorv32_cpu_cp_fpu"], ["neorv32_cpu_control", "neorv32_cpu_frontend"]
REGBARS = ["ctrl_i.rf_rd", "ctrl_i.rf_rs1", "ctrl_i.rf_rs2", "ctrl_i.rf_wb_en", "ctrl_i.rf_zero_we", "rf_we"]
ALUBARS = ["cfu_csr_we", "ctrl_i.csr_addr", "ctrl_i.csr_we", "fpu_csr_we"]
SLINK = ["slink_rx_data_i", "slink_tx_data_o", "slink_tx_last_o"]
GUARD_MODS = ["neorv32_cpu_icc", "neorv32_xbus", "neorv32_cpu", "neorv32_slink", "neorv32_cpu_lsu", "neorv32_cpu_alu"]
WATCH = [("neorv32_cpu_frontend", "ibus_rsp_i.ack"), ("neorv32_cpu_lsu", "ctrl_i.lsu_req"), ("neorv32_cpu_lsu", "ctrl_i.lsu_rw"),
         ("neorv32_cpu_lsu", "ctrl_i"), ("neorv32_cache", "host_req_i.rw"), ("neorv32_cache", "host_req_i.ben"),
         ("neorv32_cache", "host_req_i.stb"), ("neorv32_cpu_control", "csr.we_nxt"), ("neorv32_cpu_control", "ctrl_o.csr_addr"),
         ("neorv32_cpu_icc", "icc_tx_o.ack"), ("neorv32_hwspinlock", "bus_req_i.rw"), ("neorv32_cpu_alu", "fpu_csr_en"),
         ("neorv32_cpu_alu", "cfu_csr_en")]
M4_RULES = [("P1-22", "P2"), (BUS_ID, "P2"), ("P1-23", "P2"), ("P1-05", "P2")]
CAPS = {"smoke": 0.5, "stagea": 1.2, "r0": 2.5, "r12": 5.0}
MEAN = {1: 0.0187, 2: 0.0287}            # v10's measured per-call means (r0-r2 stored usage)
GATE = {"tuning_v2": (0.694, 0.404), "heldout_v2": (0.767, 0.530)}   # (recall, precision) cuts, PLAN_MERGED.md 6
INTENDED_P1_REMOVALS = [("neorv32_cpu_control", "ctrl_o.csr_addr"), ("neorv32_cpu_icc", "icc_tx_o.ack")]


# ------------------------------------------------------------------------------------------------ builder ---
def v10_lines(f):
    return (V10D / f).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def build_p1():
    v = v10_lines("phase1.md")
    ft, acf = FT_NEW.split("\n"), ACF_NEW.split("\n")
    assert v[43] == "- Forwarded transactions (a)." and v[55].startswith("- Second copies"), "v10 Forwarded block moved"
    assert v[156] == "- Access command fields (a)." and v[168].startswith("- Per-region checks"), "v10 Access command fields block moved"
    assert len(ft) == 12 and len(acf) == 12
    return "\n".join(v[:43] + ft + v[55:156] + acf + v[168:])


def build_p2(moves):
    """moves: an ordered list of 'BUS', 'OS', 'SENT' placed at the end of step 4 (after line 157)."""
    v = v10_lines("phase2.md")
    os_lines = S.rule_text("P1-22").split("\n")
    assert v[138:145] == os_lines, "Operation selectors blocks are not at lines 139-145"
    assert v[40].endswith(" " + BUS), "the bus sentence is not the end of line 41"
    assert v[156].strip().startswith("Requests waiting for a grant.") and v[157] == "" and v[158].startswith("5. Secondary.")
    if "BUS" in moves:
        v[40] = v[40][:-len(" " + BUS)]
    body = v[:138] + v[145:] if "OS" in moves else list(v)
    j = body.index(v[156])
    tail = []
    for x in moves:
        tail += {"BUS": [BUS], "OS": os_lines, "SENT": [SENT]}[x]
    return "\n".join(body[:j + 1] + tail + body[j + 1:])


ORDER = {"O1": ["BUS", "OS", "SENT"], "O2": ["OS", "SENT", "BUS"]}


def write_version(name, p1, p2, readme):
    d = LAB / "prompts" / name
    d.mkdir(parents=True, exist_ok=True)
    for f, t in (("phase1.md", p1), ("phase2.md", p2)):
        crlf = b"\r\n" in (V10D / f).read_bytes()
        data = (t.replace("\n", "\r\n") if crlf else t).encode("utf-8")
        if (d / f).exists() and (d / f).read_bytes() != data:
            raise RuntimeError(f"{d / f} holds another text")
        (d / f).write_bytes(data)
    for f in ("common.md", "phase1_user.md", "phase2_user.md"):
        (d / f).write_bytes((V10D / f).read_bytes())
    (d / "README.md").write_text(readme, encoding="utf-8")
    if not CK.check(name, log=lambda *a: None):
        raise RuntimeError(f"{name}: check_lab_prompt fails")
    return name


def build_cells():
    p1 = build_p1()
    for o in ("O1", "O2"):
        write_version(f"diag_v10/{CELL[o]}", p1, build_p2(ORDER[o]),
                      f"# {CELL[o]}\n\nStage A cell (PLAN_MERGED.md 4c): v11's phase1.md; phase2.md = v10 with Operation selectors "
                      f"and the bus record-port sentence moved to the end of step 4 in order {o} ({' -> '.join(ORDER[o])}).\n")
    print("built", [CELL[o] for o in ("O1", "O2")])


def builder_selftest(log=print):
    import check_new_rules as CN
    import meta_tools as mt
    c = {}
    p1 = build_p1().split("\n")
    v1 = v10_lines("phase1.md")
    diff = [i for i, (a, b) in enumerate(zip(v1, p1)) if a != b]
    c["phase1: only lines 44-55 and 157-168 may differ"] = len(p1) == len(v1) and all(43 <= i <= 54 or 156 <= i <= 167 for i in diff)
    c["phase1: new blocks equal their sources"] = "\n".join(p1[43:55]) == FT_NEW and "\n".join(p1[156:168]) == ACF_NEW
    c["phase1 words 7,624 -> 7,772"] = (len(" ".join(v1).split()), len(" ".join(p1).split())) == (7624, 7772)
    c["check_new_rules passes F1 and F2 blocks"] = not CN.check_text("P1-23", "P1", ACF_NEW) and not CN.check_text("P1-05", "P1", FT_NEW)
    c["F3 sentence passes meta_tools.check_prompt"] = not mt.check_prompt(SENT, CN.names(), "F3")["problems"]
    v2 = "\n".join(v10_lines("phase2.md"))
    rules = S.all_rules()
    c["build_p2([]) == v10 phase2.md"] = build_p2([]) == v2
    c["build_p2(OS, SENT) == stages.build_p2(all, last=P1-22, add_after=SENT)"] = build_p2(["OS", "SENT"]) == S.build_p2(rules, last="P1-22", add_after=SENT)
    c["build_p2(BUS) == stages.build_p2(all, last=bus bar)"] = build_p2(["BUS"]) == S.build_p2(rules, last=BUS_ID)
    for o in ("O1", "O2"):
        t = build_p2(ORDER[o])
        c[f"{o}: v10's words + the 48 sentence words"] = len(t.split()) == len(v2.split()) + 48 == 9058
        c[f"{o}: Operation selectors and the bus sentence each appear once"] = t.count(S.rule_text("P1-22")) == 1 and t.count(BUS) == 1 and t.count(SENT) == 1
        step4 = t[t.index("4. Primary."):t.index("5. Secondary.")].rstrip("\n").split("\n")
        tail = step4[-1]
        c[f"{o}: step 4 ends with the planned item"] = tail == (SENT if o == "O1" else BUS)
    bad = [k for k, ok in c.items() if not ok]
    log(f"builder self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


# ------------------------------------------------------------------------------------------------ readers ---
_cache = {}


def mods_ref():
    if "g" not in _cache:
        g, refl = RB.CV.groups_and_ref()
        _cache["g"] = (g["tuning"] + g["held-out"], {m: set(v) for m, v in refl.items()})
    return _cache["g"]


def splits():
    sp = json.loads((LAB / "splits" / "tuning_v2.json").read_text(encoding="utf-8"))
    f = lambda xs: [m if m.startswith("neorv32_") else "neorv32_" + m for m in xs]  # noqa: E731
    return {"tuning_v2": f(sp["tuning"]), "heldout_v2": f(sp["heldout"])}


def p1rec(v, m, r):
    f = CH.run_dir(v, MODEL, r, EFFORT) / "phase1" / f"{m}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def named_count(rec, m, els):
    return sum(P.p1_named(rec, m, e) == "named" for e in els)


def latest():
    if "R" not in _cache:
        mods, _ = mods_ref()
        _cache["R"] = RB.load_latest(mods)
    return _cache["R"]


def m4(v):
    """Phase 2 breaks per fix: consistent bars of v10's rule-alone Phase 2 wording; a break = v lists the element primary."""
    mods, ref = mods_ref()
    R, want, probs = latest()
    lst, _ = RB.primaries(v, mods)
    out = {}
    for rid, ph in M4_RULES:
        nonref = refp = 0
        per = Counter()
        for m in mods:
            if (rid, ph, m, 0) not in R or (rid, ph, m, 1) not in R:
                continue
            b = [AN.names(R[(rid, ph, m, r)], "barred") for r in (0, 1)]
            cl = {n for (_, n) in CH.closed_names(m)}
            for e in (e for e in cl if RB.down(e, b[0]) and RB.down(e, b[1])):
                k = sum(e in lst[(r, m)] for r in (0, 1, 2))
                if e in ref[m]:
                    refp += k
                    if k:
                        per[f"{m[8:]}:{e}"] = k
                else:
                    nonref += k
        out[f"{rid} {ph}"] = {"all": nonref + refp, "non-reference": nonref, "reference": refp, "reference pairs": dict(per)}
    return out


def m5(v, reps=(0, 1, 2)):
    """Phase 1 named pairs per bar wording (p1_full_breaks.json's measure: PC.decisions consistent bars, p1probe.p1_named)."""
    mods, ref = mods_ref()
    dec = PC.decisions(mods)
    rows = {}
    for rid in dec:
        if rid in PC.KEEP:
            continue
        c = Counter()
        for m, els in dec[rid].items():
            for r in reps:
                rec = p1rec(v, m, r)
                if rec is None:
                    c["missing"] += 1
                    continue
                for e in els:
                    if P.p1_named(rec, m, e) == "named":
                        c["named"] += 1
                        c[f"r{r}"] += 1
                        c["reference"] += e in ref.get(m, set())
                        c[f"r{r} non-reference"] += e not in ref.get(m, set())
        rows[rid] = dict(c)
    return rows


def own_bars(variant, rid):
    """Consistent bars (both repeats) of a rule-alone variant's P1 wording, per module."""
    mods, _ = mods_ref()
    ISO.use(variant)
    out = {}
    for m in mods:
        reps = []
        for r in (0, 1):
            f = ISO.run_root(rep=r) / "P1" / rid / f"{m}.json"
            reps.append(json.loads(f.read_text(encoding="utf-8")).get("reply") if f.exists() else None)
        if all(isinstance(x, dict) for x in reps):
            cl = {n for (_, n) in CH.closed_names(m)}
            b = [AN.names(x, "barred") for x in reps]
            s = {e for e in cl if RB.down(e, b[0]) and RB.down(e, b[1])}
            if s:
                out[m] = s
    ISO.use("v9")
    return out


def named_on(v, bars, reps=(0, 1, 2), skip=()):
    n = 0
    for m, els in bars.items():
        for r in reps:
            rec = p1rec(v, m, r)
            if rec is not None:
                n += sum(P.p1_named(rec, m, e) == "named" for e in els if (m, e) not in skip)
    return n


def port_listed(rec, e):
    cons = CH.phase1_concepts(rec.get("reply")) or []
    return any(e in CH.as_list(c.get("enters through")) + CH.as_list(c.get("leaves through")) for c in cons)


def t2(v, reps):
    n = d = 0
    for r in reps:
        rec = p1rec(v, "neorv32_cpu_icc", r)
        if rec:
            for e in ("csr_wdata_i", "icc_tx_o.dat"):
                n += port_listed(rec, e)
                d += 1
    return n, d


def guard_shares(v, reps):
    _, ref = mods_ref()
    out = {}
    for m in GUARD_MODS:
        k = d = 0
        for r in reps:
            rec = p1rec(v, m, r)
            if rec:
                for e in ref[m]:
                    k += P.p1_named(rec, m, e) != "not in Phase 1"
                    d += 1
        out[m[8:]] = (k, d)
    return out


def assets(v, m, r):
    f = CH.run_dir(v, MODEL, r, EFFORT) / "assets" / f"{m}.json"
    return {x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]} if f.exists() else None


def watch(v, reps=(0, 1, 2)):
    out = {}
    for m, e in WATCH:
        p1 = [P.p1_named(p1rec(v, m, r), m, e) if p1rec(v, m, r) else None for r in reps]
        p2 = [(e in a) if (a := assets(v, m, r)) is not None else None for r in reps]
        out[f"{m[8:]}:{e}"] = {"phase 1": p1, "primary": p2, "primary runs": sum(bool(x) for x in p2)}
    return out


def cvref():
    if "cv" not in _cache:
        _cache["cv"] = R10.CV.groups_and_ref()[1]
    return _cache["cv"]


def findable(mods):
    return sum(len(cvref()[m]) for m in mods)


def score_run(v, r, mods):
    T = Ls = 0
    miss = []
    for m in mods:
        s = R10.CV.C8.score(v, r, m, cvref())
        if s is None:
            miss.append(m)
            continue
        Ls, T = Ls + s[0], T + s[1]
    return T, Ls, miss


def stability(v, mods):
    any_, all_ = set(), None
    for r in (0, 1, 2):
        s = {(m, n) for m in mods for n in (assets(v, m, r) or set())}
        any_ |= s
        all_ = s if all_ is None else all_ & s
    return len(all_), len(any_)


def readers_selftest(log=print):
    c = {}
    mods, ref = mods_ref()
    sp = splits()
    c["splits 27 / 14"] = (len(sp["tuning_v2"]), len(sp["heldout_v2"])) == (27, 14)
    x = m4(V10)
    c["M4 v10 = 47 / 25 / 20 / 29 (reference 3 / 0 / 2 / 16)"] = ([x[f"{r} {p}"]["all"] for r, p in M4_RULES], [x[f"{r} {p}"]["reference"] for r, p in M4_RULES]) == ([47, 25, 20, 29], [3, 0, 2, 16])
    y = m5(V10)
    tot = sum(r.get("named", 0) for r in y.values())
    oth = {k: v for k, v in y.items() if k not in ("P1-23", "P1-05")}
    c["M5 v10 = 168 (P1-23 23, P1-05 19, the other 20 rules 126, 116 non-reference)"] = (
        tot == 168 and y["P1-23"].get("named") == 23 and y["P1-05"].get("named") == 19 and len(oth) == 20
        and sum(v.get("named", 0) for v in oth.values()) == 126 and sum(v.get("named", 0) - v.get("reference", 0) for v in oth.values()) == 116)
    c["T2 v10 r0-r1 = 4 / 4"] = t2(V10, (0, 1)) == (4, 4)
    g = guard_shares(V10, (0, 1))
    c["F2 guard v10 r0-r1 = cpu_icc 2/10, xbus 13/18, cpu 28/28"] = (g["cpu_icc"], g["xbus"], g["cpu"]) == ((2, 10), (13, 18), (28, 28))
    t, l, miss = score_run(V10, 0, sp["tuning_v2"])
    t2_, l2, miss2 = score_run(V10, 0, sp["heldout_v2"])
    c["per-run scorer v10 r0 = tuning 141/324, heldout 69/128; findable 206 / 90"] = (t, l, t2_, l2, miss, miss2) == (141, 324, 69, 128, [], []) and (findable(sp["tuning_v2"]), findable(sp["heldout_v2"])) == (206, 90)
    c["stability v10 tuning_v2 = 209 / 448, v9 240 / 457"] = stability(V10, sp["tuning_v2"]) == (209, 448) and stability(V9, sp["tuning_v2"]) == (240, 457)
    reg = sum(named_count(p1rec(V10, "neorv32_cpu_regfile", r), "neorv32_cpu_regfile", REGBARS) for r in (0, 1, 2))
    c["cpu_regfile v10 named pairs r0-r2 = 10 (p1_full_breaks)"] = reg == 10
    c["slink data ports are reference entries"] = all(e in ref["neorv32_slink"] for e in SLINK)
    c["cpu_lsu ctrl_i is a reference entry; watch items exist in the closed set"] = "ctrl_i" in ref["neorv32_cpu_lsu"] and all(
        e in {n for (_, n) in CH.closed_names(m)} for m, e in WATCH)
    bad = [k for k, ok in c.items() if not ok]
    log(f"readers self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


# ------------------------------------------------------------------------------------------------ attribution ---
def attribution():
    """Which fix's rule-alone output decides each watched element (PLAN_MERGED.md 4a)."""
    def dec(variant, rid, ph, m, e):
        ISO.use(variant)
        s = []
        for r in (0, 1):
            f = ISO.run_root(rep=r) / ph / rid / f"{m}.json"
            rep = json.loads(f.read_text(encoding="utf-8")).get("reply") if f.exists() else None
            s.append(isinstance(rep, dict) and RB.down(e, AN.names(rep, "barred")))
        ISO.use("v9")
        return "barred" if all(s) else "not barred" if not any(s) else "split"
    R, want, _ = latest()
    rows = []
    items = list(WATCH) + [("neorv32_cpu_icc", "csr_wdata_i"), ("neorv32_cpu_icc", "icc_tx_o.dat"), ("neorv32_cpu_icc", "icc_rx_i.ack")] + \
        [("neorv32_slink", e) for e in SLINK] + [("neorv32_cpu_regfile", e) for e in REGBARS] + [("neorv32_cpu_alu", e) for e in ALUBARS]
    for m, e in items:
        f1 = (dec("v12c_old", "P1-23", "P1", m, e), dec("v12t", "P1-23", "P1", m, e))
        f2 = (dec("v10r", "P1-05", "P1", m, e), dec("v11p", "P1-05", "P1", m, e))
        f3 = all((("P1-22", "P2", m, r) in R) and RB.down(e, AN.names(R[("P1-22", "P2", m, r)], "barred")) for r in (0, 1))
        f4 = all(((BUS_ID, "P2", m, r) in R) and RB.down(e, AN.names(R[(BUS_ID, "P2", m, r)], "barred")) for r in (0, 1))
        by = [k for k, hit in (("F1", f1[0] != f1[1]), ("F2", f2[0] != f2[1]), ("F3", f3), ("F4", f4)) if hit]
        rows.append({"module": m[8:], "element": e, "F1 old -> new (P1)": f1, "F2 old -> new (P1)": f2, "F3 bars (P2)": f3,
                     "F4 bars (P2)": f4, "decided by": by, "attributable to": by[0] if len(by) == 1 else ("none" if not by else "not attributable")})
    return rows


# ------------------------------------------------------------------------------------------------ sending ---
def track(paths):
    ex = json.loads(L.EXTRA.read_text(encoding="utf-8")) if L.EXTRA.exists() else []
    L.EXTRA.write_text(json.dumps(ex + [str(p) for p in paths if str(p) not in ex], indent=1), encoding="utf-8")


def smoke_jobs():
    v = f"diag_v10/{CELL['O1']}"
    return [(m, r) for r in (0, 1) for m in SMOKE if not (CH.run_dir(V11, MODEL, r, EFFORT) / "phase1" / f"{m}.json").exists()], v


def run_smoke():
    jobs, v = smoke_jobs()
    est = len(jobs) * MEAN[1]
    print(f"smoke: {len(jobs)} Phase 1 calls, about USD {est:.2f} (cap {CAPS['smoke']})")
    if est > CAPS["smoke"] or len(jobs) > 14:
        sys.exit("over the cap; nothing sent")
    track([LAB / "runs" / f"{V11}__v1" / f"{MODEL}__{EFFORT}"])
    from concurrent.futures import ThreadPoolExecutor
    stop = CH._new_run_flag()
    calls = {r: CH.openai(MODEL, EFFORT, out=CH.run_dir(V11, MODEL, r, EFFORT), poll=5) for r in (0, 1)}
    for r in (0, 1):
        CH.run_dir(V11, MODEL, r, EFFORT).mkdir(parents=True, exist_ok=True)

    def one(j):
        threading.current_thread().lab_stop = stop
        m, r = j
        out = CH.run_dir(V11, MODEL, r, EFFORT)
        rec = CH._ask(calls[r], CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                      lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": V11, "input version": CH.INPUT_VERSION, "phase": 1,
                                                       "note": f"smoke batch, asked with {v}'s phase 1 system (= v11's)"},
                      adapt=CH.from_format_phase1)
        return (m, r, len(rec.get("problems") or []), CH.stopped(rec, 1))
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        res = list(pool.map(one, jobs))
    print("smoke done:", res)


def read_smoke():
    out = {}
    s1 = [named_count(p1rec(V11, "neorv32_cpu_regfile", r), "neorv32_cpu_regfile", REGBARS) for r in (0, 1)]
    b1 = sum(k >= 3 for k in s1)
    out["S1 cpu_regfile named of 6 per reply"] = s1
    out["S1"] = "stop" if b1 == 2 else "go (1 of 2 broken; said so)" if b1 == 1 else "go"
    cnt = lambda v: sum(P.p1_named(p1rec(v, "neorv32_slink", r), "neorv32_slink", e) != "not in Phase 1" for r in (0, 1) for e in SLINK)  # noqa: E731
    out["S2 slink data ports named or line-linked (of 6): v11 / v10"] = [cnt(V11), cnt(V10)]
    out["S2"] = "go" if cnt(V11) >= cnt(V10) else "stop"
    a = lambda v: [named_count(p1rec(v, "neorv32_cpu_alu", r), "neorv32_cpu_alu", ALUBARS) for r in (0, 1)]  # noqa: E731
    out["S3 cpu_alu barred signals named per reply: v11 / v10"] = [a(V11), a(V10)]
    out["problems per smoke reply"] = {f"{m[8:]} r{r}": len(p1rec(V11, m, r).get("problems") or []) for m in SMOKE for r in (0, 1)}
    out["go"] = out["S1"].startswith("go") and out["S2"] == "go"
    (HERE / "v11_smoke.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return out


def stagea_versions():
    return {"O1": f"diag_v10/{CELL['O1']}", "O2": f"diag_v10/{CELL['O2']}", "base": V10}


def stagea_jobs():
    vs = stagea_versions()
    return [(tag, m, r) for tag in ("O1", "O2", "base") for m in OS_MODS + BUS_MODS for r in (0, 1)
            if not (L.cell_dir(CELL[tag], r) / "phase2" / f"{m}.json").exists()], vs


def ask_p2(call, version, m, r, out):
    r1 = p1rec(V11, m, r)
    concepts = CH.phase1_concepts(r1.get("reply"))
    ids = [c.get("id") for c in concepts]
    # the concept list as Phase 1 wrote it; read with the Stage A cell's phase1.md (= v11's), as two_phase_v11 is not built yet
    rec = CH._ask(call, CK.system(version, 2), CH.user_message(version, 2, m, CH.concepts_as_written(r1, f"diag_v10/{CELL['O1']}")),
                  out / "phase2" / f"{m}.json", lambda o: CH.check_phase2(m, o, concepts),
                  {"module": m, "prompt version": version, "input version": CH.INPUT_VERSION, "phase": 2, "phase 1 from": f"{V11} r{r}"},
                  adapt=lambda o, t: CH.from_format_phase2(o, t, ids))
    if CH.stopped(rec, 2):
        return "phase 2 schema failure"
    a = CH.to_assets(m, rec["reply"], concepts)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    (out / "assets" / f"{m}.json").write_text(json.dumps(a, indent=1, ensure_ascii=False), encoding="utf-8")
    return "done"


def run_stagea():
    jobs, vs = stagea_jobs()
    est = len(jobs) * 0.036
    print(f"Stage A: {len(jobs)} Phase 2 calls, about USD {est:.2f} (cap {CAPS['stagea']})")
    if est > CAPS["stagea"] or len(jobs) > 24:
        sys.exit("over the cap; nothing sent")
    L.track_folders([CELL[t] for t in ("O1", "O2", "base")])
    from concurrent.futures import ThreadPoolExecutor
    stop = CH._new_run_flag()
    calls = {}
    for tag, m, r in jobs:
        out = L.cell_dir(CELL[tag], r)
        out.mkdir(parents=True, exist_ok=True)
        calls.setdefault((tag, r), CH.openai(MODEL, EFFORT, out=out, poll=5))

    def one(j):
        threading.current_thread().lab_stop = stop
        tag, m, r = j
        return (tag, m, r, ask_p2(calls[(tag, r)], vs[tag], m, r, L.cell_dir(CELL[tag], r)))
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        res = list(pool.map(one, jobs))
    print("Stage A done:", [x for x in res if x[3] != "done"] or "all done")


def compliance(tag, target, modules):
    B = L.bars(target, modules)
    ok = n = sec = 0
    for m in modules:
        for r in (0, 1):
            d = L.cell_dir(CELL[tag], r)
            rec = json.loads((d / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
            a = json.loads((d / "assets" / f"{m}.json").read_text(encoding="utf-8"))
            for e in B[m]:
                st, _ = L.states(rec, m, e, a)
                n += 1
                ok += st != "primary"
                sec += st == "secondary"
    return ok, n, sec


def read_stagea():
    out = {}
    for tag in ("O1", "O2", "base"):
        os_ = compliance(tag, "P1-22 P2", OS_MODS)
        bus = compliance(tag, f"{BUS_ID} P2", BUS_MODS)
        out[tag] = {"Operation selectors complied / pairs": os_[:2], "Operation selectors elements secondary": os_[2],
                    "bus bar complied / pairs": bus[:2], "sum": os_[0] + bus[0]}
    o1, o2 = out["O1"]["sum"], out["O2"]["sum"]
    out["chosen order"] = "O1" if o1 >= o2 else "O2"
    out["rule"] = "larger summed compliance over both targets; tie -> O1; never removes a fix"
    out["core + rule cells for reference"] = {"Operation selectors moved + sentence": "45/46", "bus bar moved": "43/46"}
    (HERE / "v11_stagea.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return out


def finalize():
    order = json.loads((HERE / "v11_stagea.json").read_text(encoding="utf-8"))["chosen order"]
    readme = (f"# two_phase_v11: v10 + the carried fixes (built 2026-10-17)\n\nPLAN_MERGED.md has the fixes, the readings (set before "
              f"the run) and the costs. phase1.md: v10 with Forwarded transactions (lines 44-55) = new_rules/rule_texts_v11p.json "
              f"P1-05 P1 and Access command fields (lines 157-168) = carried_P1-23.json. phase2.md: v10 with Operation selectors "
              f"(lines 139-145) and the bus record-port sentence (end of line 41) moved to the end of step 4, order {order} "
              f"({' -> '.join(ORDER[order])}), chosen by Stage A (analysis/v10_diagnosis/v11_stagea.json). common.md and the user "
              f"templates are v10's. Built by analysis/v10_diagnosis/v11.py.\n")
    write_version(V11, build_p1(), build_p2(ORDER[order]), readme)
    cell = stagea_versions()[order]
    ok = CK.system(V11, 1) == CK.system(cell, 1) and CK.system(V11, 2) == CK.system(cell, 2)
    print(f"v11 built with order {order}; system texts equal the Stage A cell's: {ok}; sha12 phase 1 {CH.sha12(CK.system(V11, 1))}, phase 2 {CH.sha12(CK.system(V11, 2))}")
    if not ok:
        sys.exit("v11 differs from the Stage A cell; nothing copied")
    copied = []
    for m in OS_MODS + BUS_MODS:
        for r in (0, 1):
            src = L.cell_dir(CELL[order], r) / "phase2" / f"{m}.json"
            rec = json.loads(src.read_text(encoding="utf-8"))
            r1 = p1rec(V11, m, r)
            us = CH.sha12(CH.user_message(V11, 2, m, CH.concepts_as_written(r1, V11)))
            if rec["system sha"] == CH.sha12(CK.system(V11, 2)) and rec["user sha"] == us:
                dst = CH.run_dir(V11, MODEL, r, EFFORT) / "phase2" / f"{m}.json"
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.exists():
                    rec["note"] = f"copied from the Stage A cell {CELL[order]} (same system and user message)"
                    dst.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
                copied.append(f"{m[8:]} r{r}")
            else:
                print(f"not copied (sha differs): {m} r{r}")
    print("copied:", copied)


def remaining(reps):
    mods, _ = mods_ref()
    n1 = n2 = 0
    for r in reps:
        d = CH.run_dir(V11, MODEL, r, EFFORT)
        n1 += sum(not (d / "phase1" / f"{m}.json").exists() for m in mods)
        n2 += sum(not (d / "phase2" / f"{m}.json").exists() for m in mods)
    return n1, n2


def run_full(step):
    reps = (0,) if step == "r0" else (1, 2)
    n1, n2 = remaining(reps)
    est = n1 * MEAN[1] + n2 * MEAN[2]
    print(f"{step}: about {n1} Phase 1 and {n2} Phase 2 calls, about USD {est:.2f} (cap {CAPS[step]})")
    if est > CAPS[step]:
        sys.exit("over the cap; nothing sent")
    track([LAB / "runs" / f"{V11}__v1" / f"{MODEL}__{EFFORT}"])
    mods, _ = mods_ref()
    res = CH.run_many([(V11, r) for r in reps], mods, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai")
    bad = {k: [x for x in v if x.get("status") != "done"] for k, v in res.items()}
    print("not done:", {f"r{k[1]}": [(x["module"], x["status"]) for x in v] for k, v in bad.items() if v} or "none")


def gate():
    sp = splits()
    out = {}
    for g, mods in sp.items():
        T, Ls, miss = score_run(V11, 0, mods)
        F = findable(mods)
        rec, prec = T / F, (T / Ls if Ls else 0.0)
        cr, cp = GATE[g]
        out[g] = {"correct": T, "listed": Ls, "findable": F, "recall": round(rec, 3), "precision": round(prec, 3),
                  "cuts (recall, precision)": [cr, cp], "missing": miss, "pass": rec >= cr and prec >= cp and not miss}
    out["go to r1-r2"] = all(x["pass"] for x in out.values() if isinstance(x, dict))
    (HERE / "v11_gate.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return out


def measure():
    sp = splits()
    mods, ref = mods_ref()
    out = {}
    for g, ms in sp.items():
        row = {}
        for v in (V9, V10, V11):
            p = R10.pooled(v, ms, cvref())
            row[v] = {"precision": p["precision"], "recall": p["recall"], "TP": p["TP"], "listed": p["listed"], "findable x3": 3 * p["findable per run"],
                      "per run (correct, listed)": p["per run (correct, listed)"]}
        cut = 0.02 if g == "tuning_v2" else 0.03
        row["pass"] = row[V11]["precision"] >= row[V9]["precision"] - cut and row[V11]["recall"] >= row[V9]["recall"] - cut
        out["M1" if g == "tuning_v2" else "M2"] = row
    out["replace v9"] = out["M1"]["pass"] and out["M2"]["pass"]
    out["M3 stability tuning_v2 (all 3 / any)"] = {v: stability(v, sp["tuning_v2"]) for v in (V9, V10, V11)}
    a, b = m4(V10), m4(V11)
    out["M4"] = {k: {"v10": a[k], "v11": b[k], "non-reference lower by >= 3": b[k]["non-reference"] <= a[k]["non-reference"] - 3,
                     "reference not lower by > 1": b[k]["reference"] >= a[k]["reference"] - 1} for k in a}
    sl = {v: {e: sum(e in (assets(v, "neorv32_slink", r) or set()) for r in (0, 1, 2)) for e in sorted(ref["neorv32_slink"])} for v in (V10, V11)}
    out["M4 slink reference entries primary runs (F2 drafted reading)"] = sl
    y10, y11 = m5(V10), m5(V11)
    oth = [k for k in y10 if k not in ("P1-23", "P1-05")]
    nr = lambda y, r=None: sum((y[k].get(f"r{r} non-reference", 0) if r is not None else y[k].get("named", 0) - y[k].get("reference", 0)) for k in oth)  # noqa: E731
    per = [nr(y10, r) for r in (0, 1, 2)]
    mean = sum(per) / 3
    mgn = 3 * max(abs(x - mean) for x in per)
    out["M5 load (20 unchanged rules, non-reference named)"] = {"v10": nr(y10), "v10 per run": per, "m": round(mgn, 2), "v11": nr(y11),
                                                                 "pass": nr(y11) <= nr(y10) + mgn}
    f1b, f2b = own_bars("v12t", "P1-23"), own_bars("v11p", "P1-05")
    skip = set(INTENDED_P1_REMOVALS)
    out["M5 F1 own bars (v12t, 474-word text)"] = {"v10": named_on(V10, f1b, skip=skip), "v11": named_on(V11, f1b, skip=skip)}
    out["M5 F1 own bars (v12t, 474-word text)"]["pass"] = out["M5 F1 own bars (v12t, 474-word text)"]["v11"] <= out["M5 F1 own bars (v12t, 474-word text)"]["v10"] - 3
    out["M5 F1 intended removals named (v10 / v11)"] = {f"{m[8:]}:{e}": [sum(P.p1_named(p1rec(v, m, r), m, e) == "named" for r in (0, 1, 2)) for v in (V10, V11)] for m, e in INTENDED_P1_REMOVALS}
    out["M5 F2 own bars (v11p)"] = {"v10": named_on(V10, f2b), "v11": named_on(V11, f2b)}
    out["M5 F2 own bars (v11p)"]["pass"] = out["M5 F2 own bars (v11p)"]["v11"] <= out["M5 F2 own bars (v11p)"]["v10"] - 3
    out["M5 T2 (cpu_icc payload as a concept port)"] = {"v10": t2(V10, (0, 1, 2)), "v11": t2(V11, (0, 1, 2)), "pass": t2(V11, (0, 1, 2))[0] <= 1}
    g10, g11 = guard_shares(V10, (0, 1, 2)), guard_shares(V11, (0, 1, 2))
    out["M5 F2 guard (named or line-linked reference shares)"] = {k: {"v10": g10[k], "v11": g11[k], "pass": (g11[k][0] / g11[k][1]) >= (g10[k][0] / g10[k][1]) - 0.10} for k in g10}
    w10, w11 = watch(V10), watch(V11)
    out["M6 watch items"] = {k: {"v10": w10[k], "v11": w11[k], "flag": w10[k]["primary runs"] != w11[k]["primary runs"]} for k in w10}
    out["M6 cpu_alu barred signals named in Phase 1 per run (v10 / v11)"] = [[named_count(p1rec(v, "neorv32_cpu_alu", r), "neorv32_cpu_alu", ALUBARS) for r in (0, 1, 2)] for v in (V10, V11)]
    out["M7 V4 Sequencing-state signals primary pairs (v9 / v10 / v11)"] = [sum(e in (assets(v, m, r) or set()) for m, es in R10.V4.items() for e in es for r in (0, 1, 2)) for v in (V9, V10, V11)]
    out["M7 V5 debug_dm dm_ctrl.busy primary runs (v9 / v10 / v11)"] = [sum("dm_ctrl.busy" in (assets(v, "neorv32_debug_dm", r) or set()) for r in (0, 1, 2)) for v in (V9, V10, V11)]
    tok = {}
    for v in (V10, V11):
        for ph in (1, 2):
            o = [json.loads(f.read_text(encoding="utf-8"))["usage"].get("out") for r in (0, 1, 2)
                 for f in (CH.run_dir(v, MODEL, r, EFFORT) / f"phase{ph}").glob("*.json") if json.loads(f.read_text(encoding="utf-8")).get("usage")]
            tok[f"{v} phase {ph}"] = round(sum(x or 0 for x in o) / len(o)) if o else None
    out["M8 output tokens per call"] = tok
    out["attribution"] = attribution()
    (HERE / "v11_measure.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=list), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "attribution"}, indent=1, ensure_ascii=False, default=list)[:12000])


def preview(step):
    if step == "smoke":
        jobs, _ = smoke_jobs()
        print(f"smoke: {len(jobs)} Phase 1 calls, about USD {len(jobs) * MEAN[1]:.2f}")
    elif step == "stagea":
        jobs, _ = stagea_jobs()
        print(f"Stage A: {len(jobs)} Phase 2 calls, about USD {len(jobs) * 0.036:.2f}")
    else:
        n1, n2 = remaining((0,) if step == "r0" else (1, 2))
        print(f"{step}: {n1} Phase 1 + {n2} Phase 2 calls, about USD {n1 * MEAN[1] + n2 * MEAN[2]:.2f}")
    print(f"spent so far USD {run_a.spent(log=lambda *a: None):.2f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "selftest":
        sys.exit(0 if builder_selftest() and readers_selftest() else 1)
    if cmd in ("smoke", "stagea", "r0", "r12") and not builder_selftest(log=lambda *a: None):
        sys.exit("builder self-test FAIL; nothing sent")
    {"build-cells": build_cells, "preview": lambda: preview(sys.argv[2]), "smoke": run_smoke, "read-smoke": read_smoke,
     "stagea": run_stagea, "read-stagea": read_stagea, "finalize": finalize, "r0": lambda: run_full("r0"),
     "gate": gate, "r12": lambda: run_full("r12"), "measure": measure,
     "attribution": lambda: print(json.dumps(attribution(), indent=1)),
     "read-r0": lambda: None}[cmd]()


# ------------------------------------------------------------------------------------------------ r0 only (after the stop gate) ---
def read_r0():
    """Diagnostic readings on r0 only (the stop gate stopped r1-r2). No preset cut: the plan's readings pool r0-r2."""
    mods, ref = mods_ref()
    sp = splits()
    out = {"note": "r0 only, read after the stop gate failed; diagnostic, no preset cut"}
    per = {}
    for g, ms in sp.items():
        rows = []
        for m in ms:
            s = {v: R10.CV.C8.score(v, 0, m, cvref()) for v in (V9, V10, V11)}
            rows.append({"module": m[8:], **{v.split("_")[-1]: (x[1], x[0]) if x else None for v, x in s.items()}})
        per[g] = rows
    out["per module r0 (correct, listed)"] = per
    R, want, probs = latest()
    m4r = {}
    for rid, ph in M4_RULES:
        c = {}
        for v in (V10, V11):
            nonref = refp = 0
            for m in mods:
                if (rid, ph, m, 0) not in R or (rid, ph, m, 1) not in R:
                    continue
                a = assets(v, m, 0)
                if a is None:
                    continue
                b = [AN.names(R[(rid, ph, m, r)], "barred") for r in (0, 1)]
                cl = {n for (_, n) in CH.closed_names(m)}
                for e in (e for e in cl if RB.down(e, b[0]) and RB.down(e, b[1])):
                    if e in a:
                        refp += e in ref[m]
                        nonref += e not in ref[m]
            c[v] = {"non-reference": nonref, "reference": refp}
        m4r[f"{rid} {ph}"] = c
    out["M4 r0 (Phase 2 breaks)"] = m4r
    y10, y11 = m5(V10, (0,)), m5(V11, (0,))
    oth = [k for k in y10 if k not in ("P1-23", "P1-05")]
    nr = lambda y: sum(y[k].get("named", 0) - y[k].get("reference", 0) for k in oth)  # noqa: E731
    out["M5 r0 load (20 unchanged rules, non-reference named)"] = {"v10": nr(y10), "v11": nr(y11)}
    out["M5 r0 per rule named (v10 / v11)"] = {k: [y10[k].get("named", 0), y11.get(k, {}).get("named", 0)] for k in y10 if y10[k].get("named", 0) or y11.get(k, {}).get("named", 0)}
    f1b, f2b = own_bars("v12t", "P1-23"), own_bars("v11p", "P1-05")
    out["M5 r0 F1 own bars named (v10 / v11)"] = [named_on(V10, f1b, (0,), set(INTENDED_P1_REMOVALS)), named_on(V11, f1b, (0,), set(INTENDED_P1_REMOVALS))]
    out["M5 r0 F2 own bars named (v10 / v11)"] = [named_on(V10, f2b, (0,)), named_on(V11, f2b, (0,))]
    out["M5 r0 T2 cpu_icc payload as a concept port (v10 / v11)"] = [t2(V10, (0,)), t2(V11, (0,))]
    out["M5 r0 F2 guard shares (v10 / v11)"] = {k: [guard_shares(V10, (0,))[k], guard_shares(V11, (0,))[k]] for k in guard_shares(V10, (0,))}
    out["M6 r0 watch items (v10 / v11)"] = {k: [watch(V10, (0,))[k], watch(V11, (0,))[k]] for k in watch(V10, (0,))}
    out["M6 r0 cpu_alu barred named (v10 / v11)"] = [named_count(p1rec(v, "neorv32_cpu_alu", 0), "neorv32_cpu_alu", ALUBARS) for v in (V10, V11)]
    (HERE / "v11_r0.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=list), encoding="utf-8")
    return out


if __name__ == "__main__" and sys.argv[1:] == ["read-r0"]:
    print(json.dumps(read_r0(), indent=1, ensure_ascii=False, default=list)[:15000])
