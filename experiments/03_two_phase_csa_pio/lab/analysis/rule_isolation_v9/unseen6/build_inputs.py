"""Clarity test on modules never used for tuning, step 2 of 2: graph g2, block diagram and the PIO inputs (rtl.txt,
closed_set.json, diagram.txt, format of inputs/v1) for neorv32_crc, neorv32_dma, neorv32_clint and neorv32_cfs, plus
neorv32_fifo and neorv32_boot_rom (already in inputs/v1; rebuilt here as a check). Reads step 1's
WT/final/unseen6/all_four_fixes (build_maps.py). No model.

Writes: experiments/03_two_phase_csa_pio/lab/inputs/unseen6/{tuning,unseen}/<module>/{rtl.txt, closed_set.json, diagram.txt} + manifest.json
(new folder; inputs/v1 is not touched). The isolation lab reads the 4 new modules from here (isolation.py
"__unseen6" variants); fifo and boot_rom keep reading inputs/v1, whose files these must equal.

Checks, in order; the script stops at the first failure:
  A. stock code, nothing patched: the 5 self-tests (pio_graph, pio_flowfix, pio_blocks, pio_diagram, pio_inputs);
     every stored graph (43) and every stored v1 input file (129) is reproduced in memory;
  B. patched (G.RTL gains split "unseen" = WT/final/unseen6/rtl, last; G.FIX = the step-1 folder; the 35 caches
     cleared): every new module has its 5 upstream files and lands in split "unseen"; the 5 self-tests again (their
     all-file loops now include the 4 new modules); hand-read lines of the new RTL (HAND below) in the graph,
     the diagram and the closed set; the 43 stored graphs and 129 v1 input files still reproduced;
  C. after writing: pio_inputs.consistency passes for all 6; fifo and boot_rom files equal inputs/v1 byte for byte.

  %USERPROFILE%/miniconda3/python.exe -B build_inputs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WT = Path("E:/jobs/ff/test/Prepoison_subset/.claude/worktrees/friendly-hopper-2fb731")
LAB = Path("E:/jobs/ff/test/Prepoison_subset/experiments/03_two_phase_csa_pio/lab")
NEW_RTL = WT / "final" / "unseen6" / "rtl"
NEW_FIX = WT / "final" / "unseen6" / "all_four_fixes"
OUT = LAB / "inputs" / "unseen6"
V1 = LAB / "inputs" / "v1"
NEW = ["neorv32_cfs", "neorv32_clint", "neorv32_crc", "neorv32_dma"]
SIX = NEW + ["neorv32_fifo", "neorv32_boot_rom"]
SPLIT = "unseen"

# Hand-read 2026-10-15 from WT/final/unseen6/rtl (lines quoted in build_maps.py and below).
#   (module, src, dst, kind, via or None, line)
HAND_EDGES = [
    ("neorv32_crc", "neorv32_crc:bus_req_i.data", "neorv32_crc:crc.poly", "explicit", None, 74),   # 74 crc.poly <= bus_req_i.data(31 downto 0)
    ("neorv32_crc", "neorv32_crc:bus_req_i.addr", "neorv32_crc:crc.poly", "implicit", None, 73),   # 73 if (bus_req_i.addr(3 downto 2) = poly_addr_c)
    ("neorv32_crc", "neorv32_crc:crc.poly", "neorv32_crc:bus_rsp_o.data", "explicit", None, 88),   # 88 bus_rsp_o.data(31 downto 0) <= crc.poly
    ("neorv32_crc", "neorv32_crc:crc.poly", "neorv32_crc:crc.sreg", "explicit", None, 118),        # 118 ... xor crc.poly
    ("neorv32_crc", "neorv32_crc:crc.mode", "neorv32_crc:crc.msb", "implicit", None, 125),         # 125 with crc.mode select crc.msb <=
    ("neorv32_dma", "neorv32_dma:bus_req_i.stb", "neorv32_dma:bus_rsp_o.ack", "explicit", None, 113),  # 113 bus_rsp_o.ack <= bus_req_i.stb
    ("neorv32_dma", "neorv32_dma:bus_req_i.data", "neorv32_dma:cfg.src_base", "explicit", None, 130),  # 130 cfg.src_base <= bus_req_i.data
    ("neorv32_dma", "neorv32_dma:bus_req_i.addr", "neorv32_dma:cfg.src_base", "implicit", None, 129),  # 129 if (bus_req_i.addr(3 downto 2) = "01")
    ("neorv32_cfs", "neorv32_cfs:bus_req_i.data", "neorv32_cfs:cfs_reg_wr", "explicit", None, 174),    # 174 cfs_reg_wr(0) <= bus_req_i.data
    ("neorv32_cfs", "neorv32_cfs:bus_req_i.addr", "neorv32_cfs:cfs_reg_wr", "implicit", None, 173),    # 173 if (bus_req_i.addr(15 downto 2) = ...)
    ("neorv32_clint", "neorv32_clint_mtime:mtime_o", "neorv32_clint:mtime", "explicit", "PORT_MAP", 113),  # 113 mtime_o => mtime
    ("neorv32_clint", "neorv32_clint:mtime_en", "neorv32_clint_mtime:en_i", "explicit", "PORT_MAP", 108),  # 108 en_i => mtime_en
    ("neorv32_clint", "neorv32_clint:bus_req_i.stb", "neorv32_clint:mtime_en", "implicit", None, 117),     # 117 mtime_en <= '1' when (bus_req_i.stb = '1') ...
    ("neorv32_clint", "neorv32_clint:mtime", "neorv32_clint:time_o", "explicit", None, 125),               # 125 time_o(31 downto 0) <= mtime(31 downto 0)
    ("neorv32_clint", "neorv32_clint_swi:wdata_i", "neorv32_clint_swi:sip_q", "explicit", None, 417),      # 417 sip_q <= wdata_i(0)
]
#   diagram blocks: crc process bus_access (54-94) assigns crc.mode/poly/data and we_ack; process crc_core (99-122)
#   assigns crc.cnt and crc.sreg; both clocked by clk_i, reset by rstn_i.
HAND_BLOCKS = [("neorv32_crc", "bus_access", {"crc.mode", "crc.poly", "crc.data", "we_ack"}),
               ("neorv32_crc", "crc_core", {"crc.cnt", "crc.sreg"})]
#   clint 104 `neorv32_clint_mtime_inst: neorv32_clint_mtime` (component form, same file, parent neorv32_clint).
HAND_INSTANCES = [("neorv32_clint", "neorv32_clint_mtime_inst", "neorv32_clint")]
#   cfs 121 `irq_o <= '0';` -> role in RTL includes "tied to a constant"; crc 20 clk_i -> role "clock".
HAND_ROLES = [("neorv32_cfs", "neorv32_cfs", "irq_o", "tied to a constant"), ("neorv32_crc", "neorv32_crc", "clk_i", "clock")]


def fail(msg):
    print("FAIL:", msg)
    sys.exit(1)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(WT / "src" / "pio_diagram"))
    import pio_graph as G       # noqa: E402
    import pio_flowfix as F     # noqa: E402
    import pio_blocks as B      # noqa: E402
    import pio_diagram as D     # noqa: E402
    import pio_inputs as PI     # noqa: E402
    if not all(m.G is G for m in (F, B, D, PI)) or Path(G.__file__).parent != WT / "src" / "pio_diagram":
        fail("the pio modules must share one pio_graph from the worktree")
    quiet = lambda *a, **k: None    # noqa: E731

    def clear():
        n = 0
        for mod in (G, F, B, D, PI):
            for v in vars(mod).values():
                if hasattr(v, "cache_clear") and getattr(v, "__module__", None) == mod.__name__:
                    v.cache_clear()
                    n += 1
        return n

    def selftests():
        return {"pio_graph": G.selftest(quiet), "pio_flowfix": F.selftest(quiet), "pio_blocks": B.selftest(quiet),
                "pio_diagram": D.selftest(quiet), "pio_inputs": PI.selftest(quiet)}

    stored = [(s, m) for s in ("tuning", "heldout") for m in G.modules(s) if G.code_map(m) is not None]

    def reproduce():
        bad = []
        for s, m in stored:
            g = G.build(m)
            want = json.loads((G.OUT / s / f"{m}.json").read_text(encoding="utf-8"))
            if {k: v for k, v in g.items() if k != "version"} != {k: v for k, v in want.items() if k != "version"}:
                bad.append(f"graph {m}")
            d = V1 / s / m
            for name, txt in (("rtl.txt", D.rtl_text(m)), ("diagram.txt", B.text(m, lines=False, key="v1")),
                              ("closed_set.json", json.dumps(PI.closed_set(m), indent=1))):
                if (d / name).read_text(encoding="utf-8") != txt:
                    bad.append(f"{name} {m}")
        return bad

    # A. stock
    st = selftests()
    print("A. stock self-tests:", st)
    if not all(st.values()):
        fail("stock self-test")
    bad = reproduce()
    print(f"   stock reproduction: {len(stored)} graphs and {3 * len(stored)} v1 input files,", "all equal" if not bad else f"DIFFER {bad[:6]}")
    if bad:
        fail("stock reproduction")

    # B. patched
    if PI.ARROWS_KEY != "v1":
        fail("ARROWS_KEY must stay v1 (the format of inputs/v1)")
    G.RTL = {**G.RTL, SPLIT: NEW_RTL}
    G.FIX = NEW_FIX
    PI.OUT = OUT
    PI.VERSION = "unseen6"
    print(f"B. patched: G.RTL += {SPLIT}, G.FIX = {NEW_FIX.relative_to(WT)}, {clear()} caches cleared")
    for m in NEW:
        need = [NEW_FIX / "closed_sets" / SPLIT / f"{m}.json", NEW_FIX / "maps" / SPLIT / f"{m}.json",
                NEW_FIX / "maps" / SPLIT / "_sites" / f"{m}.json", NEW_FIX / "occurrence_profiles" / f"{m}.json",
                NEW_FIX / "traced_inputs" / SPLIT / f"{m}.txt"]
        if not all(p.exists() for p in need) or G.split_of(m) != SPLIT:
            fail(f"{m}: upstream files or split")
    if [m for s in G.RTL for m in G.modules(s) if s == SPLIT] != NEW:
        fail("split unseen must hold exactly the 4 new modules")
    st = selftests()
    print("   self-tests with the new modules in their all-file loops:", st)
    if not all(st.values()):
        fail("self-test with the new modules")
    res = {}
    for m, src, dst, kind, via, ln in HAND_EDGES:
        res[f"{m}:{ln} {src.split(':')[1]} -> {dst} {kind}{' ' + via if via else ''}"] = \
            G._has(G.file_graph(m)["edges"], src, dst, kind, via, ln)
    for m, label, parent in HAND_INSTANCES:
        h = G.file_graph(m)["hierarchy"]
        res[f"{m} instance {label}: same file, parent {parent}; root {parent} only"] = \
            any(i["label"] == label and i["same_file"] and i["parent"] == parent for i in h["instances"]) and h["roots"] == [parent]
    for m, block, members in HAND_BLOCKS:
        line = next((ln for ln in B.text(m, lines=False, key="v1").splitlines() if ln.strip().startswith(f"[process] {block}:")), "")
        names = {x.strip() for x in line.split(":", 1)[-1].split(";")[0].split(",")} if line else set()
        res[f"{m} diagram block {block} holds {sorted(members)}, clocked by clk_i, reset by rstn_i"] = \
            members <= names and "clocked by clk_i" in line and "reset by rstn_i" in line
    for m, ent, port, role in HAND_ROLES:
        cs = PI.closed_set(m)
        e = next(x for x in cs["entity list"] if x["entity name"] == ent)
        p = next((x for x in e["port list"] if x["port"] == port), None)
        res[f"{m} {port} role in RTL includes '{role}'"] = bool(p) and role in p["role in RTL"]
    bad = [k for k, v in res.items() if not v]
    print(f"   hand-read lines of the new RTL: {len(res) - len(bad)}/{len(res)} hold")
    for k, v in res.items():
        print(f"   {'ok  ' if v else 'FAIL'} {k}")
    if bad:
        fail("hand-read checks")
    bad = reproduce()
    print(f"   stored outputs unchanged under the patch: {len(stored)} graphs, {3 * len(stored)} v1 files,",
          "all equal" if not bad else f"DIFFER {bad[:6]}")
    if bad:
        fail("stored outputs changed under the patch")

    # C. write and check
    man = PI.write(SIX, log=quiet)
    cons = {m: PI.consistency(m)["ok"] for m in SIX}
    print("C. written", len(man["modules"]), "modules to", OUT, "; consistency:", cons)
    if not all(cons.values()):
        fail("consistency")
    same = {m: all((OUT / "tuning" / m / f).read_bytes() == (V1 / "tuning" / m / f).read_bytes()
                   for f in ("rtl.txt", "diagram.txt", "closed_set.json")) for m in ("neorv32_fifo", "neorv32_boot_rom")}
    print("   fifo and boot_rom equal inputs/v1 byte for byte:", same)
    if not all(same.values()):
        fail("fifo/boot_rom differ from inputs/v1")
    for m in NEW:
        d = OUT / SPLIT / m
        cs = json.loads((d / "closed_set.json").read_text(encoding="utf-8"))
        n = sum(len(e["port list"]) + len(e["signal list"]) for e in cs["entity list"])
        print(f"   {m}: rtl.txt {len((d / 'rtl.txt').read_text(encoding='utf-8').splitlines())} lines, "
              f"closed set {len(cs['entity list'])} entities / {n} top-level entries, "
              f"diagram {len((d / 'diagram.txt').read_text(encoding='utf-8').splitlines())} lines")
    print("ALL CHECKS PASS")


if __name__ == "__main__":
    main()
