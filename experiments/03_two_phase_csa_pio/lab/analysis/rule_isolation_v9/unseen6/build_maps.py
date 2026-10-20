"""Clarity test on modules never used for tuning, step 1 of 2 (user 2026-10-15: "do the clarity test"): closed sets,
occurrence profiles, relationship maps and traced inputs for neorv32_crc, neorv32_dma, neorv32_clint and neorv32_cfs.
These 4 have no reference entries (LAsset's manual sheet and SA-EDI's identical copy have none), and no run, rule or
fix has read them. They are built with the same code and the same four map fixes as final/branch_label/all_four_fixes
(record-field expansion, per-entity flow graph, scoped record types, exact if-arm labels). No model.
neorv32_fifo and neorv32_boot_rom, the other two modules of the test, already have stored maps and inputs.

Source RTL: E:/jobs/ff/test/LAsset-Security-Assets/SoC/neorv32 RTL/ (neorv32 1.11.4.3; its other 44 files are byte-
identical to data/RTL_data and data/RTL_heldout), copied byte for byte to WT/final/unseen6/rtl/ (4 files only, since
the build globs a split's whole folder).

Writes, all new and inside the worktree WT (relation_stage.merge and pio_graph require paths under it):
  WT/final/unseen6/all_four_fixes/   byte copy of final/branch_label/all_four_fixes, plus the 4 modules under split
                                     "unseen": closed_sets/unseen, maps/unseen (+ _sites), occurrence_profiles/<m>.json,
                                     traced_inputs/unseen (+ _flow), expansions_unseen.json
  WT/final/unseen6/_check/           the check modules rebuilt by this driver (compared with all_four_fixes)
  WT/final/unseen6/_twice/           the 4 new modules built a second time (determinism)
Never called (they write stored folders): FP.build_all, RF.build/main, FE.build/main, RSC.build/main, BL.main,
CM.selftest, CM.build_heldout.

Checks, in order; the script stops at the first failure and nothing it wrote counts as built:
  1. the pipeline's own self-tests, before any patch: code_pairs_v2, CM.selftest_closed, record_scope.selftest_closed,
     branch_label.selftest_frames;
  2. reproduction through this driver: neorv32_fifo, neorv32_boot_rom, neorv32_cache, neorv32_bus (tuning),
     neorv32_cpu_control, neorv32_cpu_cp_fpu (held-out) equal all_four_fixes byte for byte (closed set, map, _sites,
     profile; traced input and _flow where stored; expansions JSON-equal); the stored hand-read map self-tests pass on
     the rebuilt maps (record_fields cache/bus, record_scope fpu, branch_label cpu_control);
  3. negative control: cpu_control rebuilt without the if-arm fix differs from all_four_fixes;
  4. hand-read lines of the new RTL (read 2026-10-15, listed in HAND below), checked on the written closed sets and maps;
  5. the 4 new modules built a second time give identical bytes.

  %USERPROFILE%/miniconda3/python.exe -B build_maps.py
"""
from __future__ import annotations

import filecmp
import json
import shutil
import sys
from pathlib import Path

WT = Path("E:/jobs/ff/test/Prepoison_subset/.claude/worktrees/friendly-hopper-2fb731")
SRC = Path("E:/jobs/ff/test/LAsset-Security-Assets/SoC/neorv32 RTL")
BASE = WT / "final" / "unseen6"
NEW_RTL = BASE / "rtl"
NEW_FIX = BASE / "all_four_fixes"
CHECK = BASE / "_check"
TWICE = BASE / "_twice"
FIX4 = WT / "final" / "branch_label" / "all_four_fixes"
NEW = ["neorv32_cfs", "neorv32_clint", "neorv32_crc", "neorv32_dma"]
SPLIT = "unseen"
CHECK_MODS = [("neorv32_fifo", "tuning"), ("neorv32_boot_rom", "tuning"), ("neorv32_cache", "tuning"),
              ("neorv32_bus", "tuning"), ("neorv32_cpu_control", "heldout"), ("neorv32_cpu_cp_fpu", "heldout")]

# Hand-read 2026-10-15 from WT/final/unseen6/rtl (and data/RTL_data/neorv32_package.vhd 121-157: bus_req_t has 12
# fields, bus_rsp_t 3).
#   crc 20-23 ports clk_i, rstn_i, bus_req_i, bus_rsp_o -> 4 + 12 + 3 = 19 port entries; 36-48 crc (crc_t: mode, poly,
#     data, sreg, cnt, msb) and we_ack -> 8 signal entries.
#   crc 56/57 reset arm `bus_rsp_o <= rsp_terminate_c;`; dma 99/100 and cfs 152/157 the same statement.
#   crc 73-74 `if (bus_req_i.addr(3 downto 2) = poly_addr_c)` / `crc.poly <= bus_req_i.data(31 downto 0);` (clocked,
#     process bus_access 54); 88 `bus_rsp_o.data(31 downto 0) <= crc.poly;`; 118 `crc.sreg <= (crc.sreg(30 downto 0)
#     & '0') xor crc.poly;`; 125-128 `with crc.mode select crc.msb <= crc.sreg(7) when "00", ...` (concurrent).
#   dma 20-26 ports clk_i, rstn_i, bus_req_i, bus_rsp_o, dma_req_o, dma_rsp_i, irq_o -> 7 + 12 + 3 + 12 + 3 = 37;
#     113 `bus_rsp_o.ack  <= bus_req_i.stb;`; 129-130 `if (bus_req_i.addr(3 downto 2) = "01")` / `cfg.src_base <=
#     bus_req_i.data;`.
#   cfs 121 `irq_o <= '0';`; 173-174 `if (bus_req_i.addr(15 downto 2) = "00000000000000")` / `cfs_reg_wr(0) <=
#     bus_req_i.data;`.
#   clint 21 entity neorv32_clint, 389 entity neorv32_clint_swi (4 entities in the file); swi 414-417 clocked
#     `sip_q <= wdata_i(0);`, 427 `swi_o <= sip_q;`; clint 125 `time_o(31 downto 0) <= mtime(31 downto 0);` (clocked).
HAND_COUNTS = {"neorv32_crc": (19, 8), "neorv32_dma": (37, None)}       # (port entries, signal entries); None = not read
HAND_LINKS = [  # (module, entity, element a, element b, lines): a relationship between a and b anchored on these lines
    ("neorv32_crc", "neorv32_crc", "crc.poly", "bus_req_i.data", {74}),
    ("neorv32_crc", "neorv32_crc", "crc.poly", "bus_req_i.addr", {73, 74}),
    ("neorv32_crc", "neorv32_crc", "bus_rsp_o.data", "crc.poly", {88}),
    ("neorv32_crc", "neorv32_crc", "crc.sreg", "crc.poly", {118}),
    ("neorv32_crc", "neorv32_crc", "crc.msb", "crc.mode", {125}),
    ("neorv32_crc", "neorv32_crc", "crc.msb", "crc.sreg", {126, 127, 128}),
    ("neorv32_dma", "neorv32_dma", "bus_rsp_o.ack", "bus_req_i.stb", {113}),
    ("neorv32_dma", "neorv32_dma", "cfg.src_base", "bus_req_i.data", {130}),
    ("neorv32_cfs", "neorv32_cfs", "cfs_reg_wr", "bus_req_i.data", {174}),
    ("neorv32_clint", "neorv32_clint_swi", "sip_q", "wdata_i", {417}),
    ("neorv32_clint", "neorv32_clint_swi", "swi_o", "sip_q", {427}),
    ("neorv32_clint", "neorv32_clint", "time_o", "mtime", {125}),
]
HAND_STORAGE = [("neorv32_crc", "neorv32_crc", "crc.poly", "edge"), ("neorv32_clint", "neorv32_clint_swi", "sip_q", "edge")]
HAND_NOT_EDGE = [("neorv32_crc", "neorv32_crc", "crc.msb")]
HAND_RESET_EXPANSION = [("neorv32_crc", 57), ("neorv32_dma", 100), ("neorv32_cfs", 157)]   # bus_rsp_o.<f> at that line
HAND_CONST = [("neorv32_cfs", "neorv32_cfs", "irq_o", 121, "'0'")]
HAND_ENTITIES = {"neorv32_clint": ["neorv32_clint", "neorv32_clint_mtime", "neorv32_clint_mtimecmp", "neorv32_clint_swi"]}


def fail(msg):
    print("FAIL:", msg)
    sys.exit(1)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    # 0. RTL copies
    NEW_RTL.mkdir(parents=True, exist_ok=True)
    for m in NEW:
        dst = NEW_RTL / f"{m}.vhd"
        if not dst.exists():
            shutil.copyfile(SRC / f"{m}.vhd", dst)
        if not filecmp.cmp(SRC / f"{m}.vhd", dst, shallow=False):
            fail(f"{m}.vhd copy differs from the LAsset file")
    if sorted(p.stem for p in NEW_RTL.glob("*.vhd")) != NEW:
        fail(f"{NEW_RTL} must hold exactly the 4 new files")
    for d in (WT / "data" / "RTL_data", WT / "data" / "RTL_heldout"):
        for p in d.glob("*.vhd"):
            if not filecmp.cmp(p, SRC / p.name, shallow=False):
                fail(f"{p.name}: corpus file differs from the LAsset copy (version mismatch)")
    print("0. RTL: 4 new files copied byte for byte; the 44 corpus files equal the LAsset copies")

    sys.path.insert(0, str(WT / "final"))
    import final_pipeline as FP                    # noqa: E402
    ns = FP.setup()                                 # chdir WT, sys.path, builders, tree-sitter grammar
    import record_fields as RF                      # noqa: E402
    import flow_entities as FE                      # noqa: E402
    import record_scope as RSC                      # noqa: E402
    import branch_label as BL                       # noqa: E402
    CM, RS, V, TI = ns.CM, ns.RS, ns.V, ns.TI
    quiet = lambda *a, **k: None                    # noqa: E731

    # 1. self-tests before any patch
    st = {"code_pairs_v2": V.self_test(), "CM.selftest_closed": CM.selftest_closed(log=quiet),
          "record_scope.selftest_closed": RSC.selftest_closed(CM, log=quiet),
          "branch_label.selftest_frames": BL.selftest_frames(RS, log=quiet)}
    print("1. pipeline self-tests before patching:", st)
    if not all(st.values()):
        fail("a pipeline self-test")

    orig = {"parse_closed": CM.parse_closed, "RS._frames": RS._frames, "V._frames": V._frames, "entities": CM.entities}
    profiles = {}

    def keep(m, s, tagger=ns.CT.tagger):
        profiles[m] = orig["entities"](m, s, tagger)
        return profiles[m]

    def patch(frames=True):
        CM.parse_closed = RSC.parse_closed_scoped
        RS._frames = V._frames = (BL.frames_fixed if frames else orig["RS._frames"])
        CM.entities = keep

    def restore():
        CM.parse_closed = orig["parse_closed"]
        RS._frames, V._frames, CM.entities = orig["RS._frames"], orig["V._frames"], orig["entities"]

    def build_one(m, rtl_dir, split, out):
        CM.write_closed_sets([m], rtl_dir, out / "closed_sets" / split)
        RF.build_module(m, CM.Source(rtl_dir, out / "closed_sets" / split), out / "maps" / split, "all")
        (out / "occurrence_profiles").mkdir(parents=True, exist_ok=True)
        ents = profiles[m]                            # written after build_module: expand_entity adds rows in place
        (out / "occurrence_profiles" / f"{m}.json").write_text(json.dumps(
            {E["entity"]: {n: [{k: r[k] for k in FP.PROFILE_KEYS} for r in rs] for n, rs in E["profile"].items()} for E in ents},
            indent=1), encoding="utf-8")

    def traced(out, mods, maps_first):
        saved = (dict(TI.MAPS), dict(TI.PARSED), dict(TI.RTL), TI._PORT_DIRS)
        try:
            TI.MAPS = {"tuning": [maps_first / "maps" / "tuning", FIX4 / "maps" / "tuning"],
                       "heldout": [maps_first / "maps" / "heldout", FIX4 / "maps" / "heldout"],
                       SPLIT: [maps_first / "maps" / SPLIT]}
            TI.PARSED = {"tuning": FIX4 / "closed_sets" / "tuning", "heldout": FIX4 / "closed_sets" / "heldout",
                         SPLIT: maps_first / "closed_sets" / SPLIT}
            TI.RTL = {**TI.RTL, SPLIT: NEW_RTL}
            TI._PORT_DIRS = None
            for m, split in mods:
                t, fg = FE.text(TI, split, m)
                d = out / "traced_inputs" / split
                (d / "_flow").mkdir(parents=True, exist_ok=True)
                (d / f"{m}.txt").write_text(t, encoding="utf-8")
                (d / "_flow" / f"{m}.json").write_text(json.dumps(fg, indent=1), encoding="utf-8")
        finally:
            TI.MAPS, TI.PARSED, TI.RTL, TI._PORT_DIRS = saved

    # 2. reproduction of check modules
    for d in (CHECK, TWICE):
        if d.exists():
            shutil.rmtree(d)
    RF.EXPANSIONS.clear()
    patch()
    try:
        for m, split in CHECK_MODS:
            build_one(m, CM.TUNE_RTL if split == "tuning" else CM.HELD_RTL, split, CHECK)
    finally:
        restore()
    stored_exp = json.loads((FIX4 / "expansions.json").read_text(encoding="utf-8"))
    bad = []
    for m, split in CHECK_MODS:
        pairs = [(CHECK / "closed_sets" / split / f"{m}.json", FIX4 / "closed_sets" / split / f"{m}.json"),
                 (CHECK / "maps" / split / f"{m}.json", FIX4 / "maps" / split / f"{m}.json"),
                 (CHECK / "maps" / split / "_sites" / f"{m}.json", FIX4 / "maps" / split / "_sites" / f"{m}.json"),
                 (CHECK / "occurrence_profiles" / f"{m}.json", FIX4 / "occurrence_profiles" / f"{m}.json")]
        bad += [str(a.relative_to(CHECK)) for a, b in pairs if a.read_bytes() != b.read_bytes()]
        if json.loads(json.dumps(RF.EXPANSIONS.get(m))) != stored_exp.get(m):
            bad.append(f"expansions {m}")
    traced(CHECK, [(m, s) for m, s in CHECK_MODS if (FIX4 / "traced_inputs" / s / f"{m}.txt").exists()], CHECK)
    for m, split in CHECK_MODS:
        t = FIX4 / "traced_inputs" / split / f"{m}.txt"
        if t.exists():
            bad += [f"traced {m}" for a, b in ((CHECK / "traced_inputs" / split / f"{m}.txt", t),
                                               (CHECK / "traced_inputs" / split / "_flow" / f"{m}.json",
                                                FIX4 / "traced_inputs" / split / "_flow" / f"{m}.json"))
                    if a.read_bytes() != b.read_bytes()]
    print(f"2. reproduction, {len(CHECK_MODS)} check modules through this driver vs all_four_fixes:",
          "byte-identical" if not bad else f"DIFFER {bad}")
    if bad:
        fail("reproduction")
    hand = {"record_fields cache/bus": RF.selftest_hand_read({"maps": {"tuning": CHECK / "maps" / "tuning"}}, "all", log=quiet),
            "record_scope fpu": RSC.selftest_map({"heldout": CHECK / "maps" / "heldout"}, log=quiet),
            "branch_label cpu_control": BL.selftest_map(CHECK / "maps", log=quiet)}
    print("   stored hand-read map self-tests on the rebuilt maps:", hand)
    if not all(hand.values()):
        fail("hand-read map self-test on the check modules")

    # 3. negative control: without the if-arm fix, cpu_control must differ
    neg = CHECK / "_negative"
    patch(frames=False)
    try:
        build_one("neorv32_cpu_control", CM.HELD_RTL, "heldout", neg)
    finally:
        restore()
    differs = (neg / "maps" / "heldout" / "neorv32_cpu_control.json").read_bytes() != \
        (FIX4 / "maps" / "heldout" / "neorv32_cpu_control.json").read_bytes()
    print("3. negative control (cpu_control without the if-arm fix differs from all_four_fixes):", differs)
    if not differs:
        fail("negative control: the byte check cannot fail")

    # 4. the new modules: NEW_FIX = copy of all_four_fixes + the 4 under split "unseen"
    if NEW_FIX.exists():
        shutil.rmtree(NEW_FIX)
    shutil.copytree(FIX4, NEW_FIX)
    for out in (NEW_FIX, TWICE):
        RF.EXPANSIONS.clear()
        patch()
        try:
            for m in NEW:
                build_one(m, NEW_RTL, SPLIT, out)
        finally:
            restore()
        (out / "expansions_unseen.json").write_text(json.dumps({m: RF.EXPANSIONS[m] for m in NEW}, indent=1), encoding="utf-8")
        traced(out, [(m, SPLIT) for m in NEW], out)
    same = []
    for m in NEW:
        for rel in (f"closed_sets/{SPLIT}/{m}.json", f"maps/{SPLIT}/{m}.json", f"maps/{SPLIT}/_sites/{m}.json",
                    f"occurrence_profiles/{m}.json", f"traced_inputs/{SPLIT}/{m}.txt", f"traced_inputs/{SPLIT}/_flow/{m}.json"):
            same.append((NEW_FIX / rel).read_bytes() == (TWICE / rel).read_bytes())
    print(f"5. determinism, the 4 new modules built twice: {sum(same)}/{len(same)} files identical")
    if not all(same):
        fail("determinism")

    # 4 (checked on the written files). Hand-read lines of the new RTL.
    def load_map(m):
        d = json.loads((NEW_FIX / "maps" / SPLIT / f"{m}.json").read_text(encoding="utf-8"))
        return {(e["entity"], e["name"]): e for a in ("ports", "signals") for e in d[a]}

    def ids_on(e, lines):
        return {o["id"] for o in e["occurrences"] if o["line"] in lines}

    def linked(M, ent, a, b, lines):
        ea, eb = M.get((ent, a)), M.get((ent, b))
        if not ea or not eb:
            return False
        return any(b in r["targets"] and set(r["at"]) & ids_on(ea, lines) for r in ea["relationship"]) or \
            any(a in r["targets"] and set(r["at"]) & ids_on(eb, lines) for r in eb["relationship"])

    res = {}
    for m, (np_, ns_) in HAND_COUNTS.items():
        cs = json.loads((NEW_FIX / "closed_sets" / SPLIT / f"{m}.json").read_text(encoding="utf-8"))
        res[f"{m} closed set {np_} port entries" + (f", {ns_} signal entries" if ns_ else "")] = \
            len(cs["ports"]) == np_ and (ns_ is None or len(cs["signals"]) == ns_)
    for m, ents in HAND_ENTITIES.items():
        cs = json.loads((NEW_FIX / "closed_sets" / SPLIT / f"{m}.json").read_text(encoding="utf-8"))
        res[f"{m} entities {ents}"] = sorted(cs["entities"]) == sorted(ents)
    for m, ent, a, b, lines in HAND_LINKS:
        res[f"{m}:{sorted(lines)} {a} ~ {b}"] = linked(load_map(m), ent, a, b, lines)
    for m, ent, n, st_ in HAND_STORAGE:
        res[f"{m} {n} storage {st_}"] = load_map(m)[(ent, n)]["storage"] == st_
    for m, ent, n in HAND_NOT_EDGE:
        res[f"{m} {n} storage not edge"] = load_map(m)[(ent, n)]["storage"] != "edge"
    for m, ln in HAND_RESET_EXPANSION:
        M = load_map(m)
        for f in ("ack", "err", "data"):
            e = M[(m, f"bus_rsp_o.{f}")]
            ids = ids_on(e, {ln})
            res[f"{m}:{ln} bus_rsp_o.{f} expanded, reset by rstn_i, constant rsp_terminate_c"] = (
                len(ids) == 1 and any(r["type"] == "RESET_BY" and "rstn_i" in r["targets"] and set(r["at"]) & ids
                                      for r in e["relationship"])
                and any(c["at"] in ids and c["value"] == "rsp_terminate_c" for c in e["constant_drivers"]))
    for m, ent, n, ln, val in HAND_CONST:
        e = load_map(m)[(ent, n)]
        res[f"{m}:{ln} {n} constant {val}"] = any(c["at"] in ids_on(e, {ln}) and c["value"] == val for c in e["constant_drivers"])
    exp = json.loads((NEW_FIX / "expansions_unseen.json").read_text(encoding="utf-8"))
    res["expansions: crc, dma, cfs at least one each"] = all(exp.get(m) for m in ("neorv32_crc", "neorv32_dma", "neorv32_cfs"))
    bad = [k for k, v in res.items() if not v]
    print(f"4. hand-read lines of the new RTL: {len(res) - len(bad)}/{len(res)} hold")
    for k, v in res.items():
        print(f"   {'ok  ' if v else 'FAIL'} {k}")
    if bad:
        fail("hand-read checks on the new modules")
    summary = {m: {"closed set entries": None} for m in NEW}
    for m in NEW:
        cs = json.loads((NEW_FIX / "closed_sets" / SPLIT / f"{m}.json").read_text(encoding="utf-8"))
        M = load_map(m)
        summary[m] = {"entities": len(cs["entities"]), "ports": len(cs["ports"]), "signals": len(cs["signals"]),
                      "map elements": len(M), "relationship records": sum(len(e["relationship"]) for e in M.values()),
                      "expansions": len(exp.get(m) or [])}
    print("built:", json.dumps(summary))
    print("ALL CHECKS PASS; built into", NEW_FIX)


if __name__ == "__main__":
    main()
