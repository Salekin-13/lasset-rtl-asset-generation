"""Reach of change C10 (common.md 2.6: a bus request or response record PORT, or any field of one, is not a primary)
on the stored two_phase_v2 runs (gpt-5.6-luna, high, r0-r2).

Bus record port = a port whose closed-set "record type" carries an address, data and a strobe (request) or data, an
acknowledge and an error flag (response), decided from the record's field names in the closed set. Fields of such a port
count too. Internal record signals are not ports and are not covered.
Self-test against hand-read RTL lines first (wdt rtl.txt 24-25: bus_req_i : in bus_req_t; bus_rsp_o : out bus_rsp_t;
cpu_pmp rtl.txt 34: ctrl_i of the control-bus record type, no strobe or acknowledge field).

  python c10_busfields.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
TUNING = V2.parents[1] / "inputs" / "v1" / "tuning"
RUNS = ("r0", "r1", "r2")


def bus_ports(m):
    cs = json.loads((TUNING / m / "closed_set.json").read_text(encoding="utf-8"))
    out = {}
    for e in cs["entity list"]:
        for p in e["port list"]:
            if "record type" not in p:
                continue
            f = {x["field"].split(".", 1)[1] for x in p.get("fields", [])}
            req = {"addr", "data", "stb"} <= f
            rsp = {"data", "ack", "err"} <= f
            if req or rsp:
                out[(e["entity name"], p["port"])] = p["record type"]
    return out


def is_bus(m, entity, element, cache={}):
    if m not in cache:
        cache[m] = bus_ports(m)
    base = element.split(".", 1)[0]
    return (entity, base) in cache[m]


def selftest():
    assert is_bus("neorv32_wdt", "neorv32_wdt", "bus_req_i.data")
    assert is_bus("neorv32_wdt", "neorv32_wdt", "bus_rsp_o")
    assert not is_bus("neorv32_wdt", "neorv32_wdt", "ctrl.enable")
    assert not is_bus("neorv32_cpu_pmp", "neorv32_cpu_pmp", "ctrl_i.cpu_debug")
    assert not is_bus("neorv32_cpu_pmp", "neorv32_cpu_pmp", "ctrl_i")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    selftest()
    print("self-test passed")
    P = json.loads((V2 / "pack3.json").read_text(encoding="utf-8"))
    types = Counter(t for m in P["modules"] for t in bus_ports(m).values())
    print("record types counted as bus ports:", dict(types))
    for k in RUNS:
        fp = tp = fpb = tpb = 0
        lost = []
        for m, d in P["modules"].items():
            r = d["runs"][k]
            tpn = Counter(r["tp"].values())
            for x in r["listed"]:
                b = is_bus(m, x["entity"], x["element"])
                if tpn[x["element"]]:
                    tp += 1
                    tpb += b
                    if b:
                        lost.append(f"{m.replace('neorv32_', '')}:{x['element']}")
                else:
                    fp += 1
                    fpb += b
        L, T = len([1 for m in P["modules"] for _ in P["modules"][m]["runs"][k]["listed"]]), P["totals"][k]["tp"]
        print(f"{k}: listed {L}; FP {fp}, of which bus record ports/fields {fpb}; correct {tp}, of which bus {tpb} {lost}; "
              f"precision {T / L:.3f} -> {(T - tpb) / (L - fpb - tpb):.3f} if C10 removed all of them")


if __name__ == "__main__":
    main()
