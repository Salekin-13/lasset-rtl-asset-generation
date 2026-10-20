"""Candidate items for the v7 rules round (like the v6 rules round: one item per failure cluster). The grouping of C1
patterns into items is the orchestrator's reading (2026-10-13); code counts each item's targets from c1_status.json.
Split patterns name their items explicitly. Self-check: no target is counted in two items."""
import json
from collections import Counter

ITEMS = {
 "B1": ("both", "Which end of a connection to an instance of an entity of this file is primary (paired)",
        {"MB-P2": "all", "MC-P4": "all", "FPH-P11": "all", "FPA-P12": "all", "FPA-P13": "all"}),
 "R1": ("recall", "A switch's held requests and strobe stay with the grant (Phase 1)", {"MA-P1": "all", "MA-P2": "all"}),
 "R2": ("recall", "Sequencing-state bar over-applied: peer-clocked debug-port state, generator valid hand-off", {"MA-P4": "all", "MA-P9": "all"}),
 "R3": ("recall", "Status flags and pop/clear of a FIFO holding data the unit generates", {"MA-P5": "all", "MA-P8": "all", "MA-P6": "all"}),
 "R4": ("recall", "Access address and write enable of the unit's own store are pieces of their own", {"MA-P3": "all", "MA-P7": "all", "MA-P10": "all"}),
 "R5": ("recall", "Phase 2 labels: copies, operands of a mix, start pulses, reduced enables, grant state", {"ME-P1": "all", "ME-P2": "all", "MC-P2": "all", "ME-P3": "all", "MC-P1": "all", "MO-P1": "all"}),
 "R6": ("recall", "Held lines: hand-off port-map lines and accepted-outcome lines", {"MB-P3": "all", "MB-P4": "all", "MB-P5": "all"}),
 "P1": ("precision", "Code check: copies, operand copies and pass-through record fields (v7 bars P11.1, P11.6, record bars)",
        {"FPA-P1": "all", "FPH-P1": "all", "FPA-P3": "all", "FP1-P8": "all", "FPH-P15": "all", "FPA-P5": "all"}),
 "P2": ("precision", "Code check: one-bit transaction, busy and started flags; AMO state; merged responses (TF1, CX10.1, U3b)",
        {"FP1-P4": "all", "FPH-P2": "all", "FPH-P14": "all", "FP1-P2": "all", "FP1-P5": "all", "FPA-P4": "all"}),
 "P3": ("precision", "Code check: cache data words and port-buffer FIFO bits (cache bar, port-buffer bar)", {"FP1-P1": "all", "FP1-P6": "all"}),
 "P4": ("precision", "Code check: CSR read-back words, operation selectors, timing flags, per-region results, violation-reset setting",
        {"FPH-P3": "all", "FPA-P15": "all", "FPH-P4": "all", "FP1-P9": "all", "FP1-P11": "all", "FP1-P12": "all",
         "FPA-P2": ["F:cpu_cp_muldiv:neorv32_cpu_cp_muldiv:ctrl_i.ir_funct12:r1", "F:cpu_cp_muldiv:neorv32_cpu_cp_muldiv:ctrl_i.ir_funct3:r1", "F:cpu_cp_muldiv:neorv32_cpu_cp_muldiv:ctrl_i.ir_opcode:r1"],
         "FP1-P7": ["F:cpu:neorv32_cpu:alu_cp_done:r0", "F:cpu:neorv32_cpu:alu_cp_done:r2"]}),
}
# reference conventions: need the user's basis decision before any rule (no agent cost now)
DECIDE = {
 "D1": ("recall", "Input ports the RTL never reads (the reference lists them)", {"MB-P1": "all"}),
 "D2": ("both", "A non-bus record input port named whole, not by its fields", {"MC-P3": "all", "MC-P5": "all", "FPH-P13": "all"}),
 "D3": ("precision", "Memory arrays of a non-cache memory (the reference lists the read word)", {"FPH-P6": "all", "FPA-P14": "all"}),
 "D5": ("recall", "A debugger's reset-request register dropped by the reset-request bar", {"ME-P4": "all"}),
 "D4": ("precision", "Other elements the prompt makes primary but the reference omits", {p: "all" for p in
        ["FP1-P3", "FP1-P10", "FPH-P5", "FPH-P16", "FPH-P7", "FPH-P8", "FPH-P17", "FPH-P9", "FPH-P10", "FPA-P6", "FPA-P7", "FPA-P8", "FPA-P9", "FPA-P16", "FPA-P10", "FPA-P11", "FPH-P12"]}
        | {"FP1-P7": "rest", "FPA-P2": "rest"}),
}
st = json.load(open("c1_status.json", encoding="utf-8"))
seen = Counter()
out = {}
for tab in (ITEMS, DECIDE):
    for k, (kind, title, pats) in tab.items():
        tg = []
        for p, sel in pats.items():
            its = st["patterns"][p]["items"]
            if sel == "all":
                tg += its
            elif sel == "rest":
                taken = [i for t in (ITEMS, DECIDE) for _, _, ps in t.values() for pp, s in ps.items() if pp == p and isinstance(s, list) for i in s]
                tg += [i for i in its if i not in taken]
            else:
                tg += sel
        for i in tg:
            seen[i] += 1
        m = [i for i in tg if i.startswith("M:")]
        f = [i for i in tg if i.startswith("F:")]
        out[k] = {"kind": kind, "title": title, "patterns": list(pats), "misses": len(m), "false positives": len(f),
                  "per run": {r: sum(1 for i in tg if i.endswith(":" + r)) for r in ("r0", "r1", "r2")}, "items": tg}
dup = [i for i, n in seen.items() if n > 1]
allitems = {i for p in st["patterns"].values() for i in p["items"]}
print("self-check: no target in two items:", not dup, dup[:5], "| targets covered", len(seen), "of", len(allitems))
for k, v in out.items():
    print(f"{k:3s} {v['kind']:9s} misses {v['misses']:2d}  FPs {v['false positives']:2d}  {v['per run']}  {v['title']}")
print("items for drafting:", sum(1 for k in out if k in ITEMS), "| targets: misses", sum(out[k]["misses"] for k in ITEMS), "FPs", sum(out[k]["false positives"] for k in ITEMS))
print("for decision:", sum(1 for k in out if k in DECIDE), "| targets: misses", sum(out[k]["misses"] for k in DECIDE), "FPs", sum(out[k]["false positives"] for k in DECIDE))
json.dump(out, open("rules_items.json", "w", encoding="utf-8"), indent=1)
