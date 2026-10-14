"""Candidate structural check for R4 (synchronizer stage re-sampling an input port), on tuning closed sets.
A register R of entity E matches when: role has 'held on a clock edge'; every 'gets value from' partner is R itself,
an input port (or field) of E, or another matching register of E (a chain); and no 'decided by' partner is a field of a
bus request record (so a bus-written setting never matches). Self-test against hand-read lines: uart 337
(tx_engine.cts <= tx_engine.cts(0) & uart_ctsn_i) must match; uart ctrl.enable (179, bus write) must not."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
exec(open(Path(__file__).with_name("combined_rows.py"), encoding="utf-8").read().split("want = {")[0])
def r4(module):
    cs = json.loads((TUN / module / "closed_set.json").read_text(encoding="utf-8"))
    out = set()
    for e in cs["entity list"]:
        en = e["entity name"]
        inp = set()
        for p in e["port list"]:
            if p.get("direction") == "in":
                inp.add(p["port"]); inp |= {f["field"] for f in p.get("fields", [])}
        regs = {}
        for s in e["signal list"]:
            for x in [s] + s.get("fields", []):
                n = x.get("signal") or x.get("field")
                if "held on a clock edge" in x.get("role in RTL", []):
                    regs[n] = x
        cand = set(regs)
        changed = True
        while changed:
            changed = False
            for n in list(cand):
                cp = regs[n].get("counterparts", {})
                src = {c.get("element") for c in cp.get("gets value from", [])}
                dec = {c.get("element") for c in cp.get("decided by", [])}
                okc = src and all(s == n or s in inp or s in cand for s in src) and any(s in inp for s in src | set())
                okc = okc or (src and all(s == n or s in inp or s in cand for s in src) and any(s in cand and s != n for s in src))
                if not okc or any(d and d.startswith("bus_req_i") for d in dec):
                    cand.discard(n); changed = True
        out |= {(en, n) for n in cand}
    return out
CH["R4c"] = {m: r4(m) for m in MODS}
ok = ("neorv32_uart", "tx_engine.cts") in CH["R4c"]["neorv32_uart"] and ("neorv32_uart", "ctrl.enable") not in CH["R4c"]["neorv32_uart"]
print("self-test", "PASS" if ok else "FAIL")
if not ok: sys.exit(1)
for m in MODS:
    if CH["R4c"][m]: print(" ", m, sorted(n for _, n in CH["R4c"][m]))
for v in V:
    print(v, "R4 check alone:", [f"{T}/{L}={T/L:.3f} fp-{f} tp-{t}" for T, L, f, t in (prec(v, k, ["R4c"]) for k in RUNS)])
    # which TP elements would be hit
    for k in RUNS:
        for m, md in P[v]["modules"].items():
            run = md["runs"][k]; tps = set(run["tp"].values())
            for x in run["listed"]:
                if (x["entity"], x["element"]) in CH["R4c"][m] and x["element"] in tps: print("   TP hit", v, k, m, x["element"])
