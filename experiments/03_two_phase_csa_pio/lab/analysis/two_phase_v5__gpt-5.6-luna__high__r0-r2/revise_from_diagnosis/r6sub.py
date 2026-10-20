"""R6 sub-unit sub-row (RULES_PROPOSAL R6): drop primary labels on FIELDS of an input port whose closed-set record type is
the CPU control-bus record (ctrl_bus_t) or fetch record (if_bus_t); never the whole port. Applied alone and on top of the
five code rows (combined_rows.py). Self-test: cpu_pmp rtl line 34 declares ctrl_i of the control-bus record type
(the earlier c10_busfields self-test reads the same line); the row must flag cpu_pmp ctrl_i.cpu_debug and never ctrl_i."""
import json, sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
exec(open(Path(__file__).with_name("combined_rows.py"), encoding="utf-8").read().split("want = {")[0])
def r6(module):
    cs = json.loads((TUN / module / "closed_set.json").read_text(encoding="utf-8"))
    out = set()
    for e in cs["entity list"]:
        for p in e["port list"]:
            if p.get("direction") == "in" and str(p.get("record type", "")).split(".")[-1] in ("ctrl_bus_t", "if_bus_t"):
                out |= {(e["entity name"], f["field"]) for f in p.get("fields", [])}
    return out
CH["R6sub"] = {m: r6(m) for m in MODS}
rtl = (TUN / "neorv32_cpu_pmp" / "rtl.txt").read_text(encoding="utf-8")
line34 = [l for l in rtl.splitlines() if re.match(r"\s*34 \|", l)]
print("cpu_pmp line 34:", line34)
ok = ("neorv32_cpu_pmp", "ctrl_i.cpu_debug") in CH["R6sub"]["neorv32_cpu_pmp"] and ("neorv32_cpu_pmp", "ctrl_i") not in CH["R6sub"]["neorv32_cpu_pmp"] and "ctrl_bus_t" in line34[0]
print("self-test", "PASS" if ok else "FAIL")
if not ok: sys.exit(1)
print("R6sub fires in:", {m: len(s) for m, s in CH["R6sub"].items() if s})
for v in V:
    a = [prec(v, k, ["R6sub"]) for k in RUNS]
    b = [prec(v, k, ["R1", "R8", "U2", "U6", "U10", "R6sub"]) for k in RUNS]
    print(v, "R6sub alone:", [f"{T}/{L}={T/L:.3f} fp-{f} tp-{t}" for T, L, f, t in a])
    print(v, "five + R6sub:", [f"{T}/{L}={T/L:.3f} fp-{f} tp-{t}" for T, L, f, t in b])
