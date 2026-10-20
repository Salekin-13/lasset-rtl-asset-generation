"""Reference elements whose found-run count changed between v4 and v4a, plus v4a's lone misses (missed in one run, found
in the other two), with their record across all Luna versions (x = found in that run). Writes regression_items.json.

  python regression_items.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent
V = ["v1", "v2", "v2a", "v3", "v4", "v4a"]
RUNS = ("r0", "r1", "r2")


def main():
    P = {v: json.loads((AN / f"two_phase_{v}__gpt-5.6-luna__high__r0-r2" / "pack3.json").read_text(encoding="utf-8")) for v in V}
    c = json.loads((HERE / "compare_v4_v4a.json").read_text(encoding="utf-8"))
    names = [x[0] for x in c["elements"]["more"] + c["elements"]["fewer"]]
    lone = [n for k in RUNS for n in c["lone_misses"][k]]
    out = {}
    for n in dict.fromkeys(names + lone):
        s, el = n.split(":", 1)
        m = f"neorv32_{s}"
        e = next(e for e in P["v4"]["modules"][m]["reference entries"] if e["name"] == el and not e["absent"])
        rec = {v: "".join("x" if e["entry"] in P[v]["modules"][m]["runs"][k]["tp"] else "." for k in RUNS) for v in V}
        kind = "gain" if n in [x[0] for x in c["elements"]["more"]] else "loss" if n in [x[0] for x in c["elements"]["fewer"]] else "lone miss"
        out.setdefault(s, []).append({"element": el, "reference concept": e["home concept"], "change": kind, "record": rec})
    (HERE / "regression_items.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print({s: len(v) for s, v in out.items()}, "total", sum(len(v) for v in out.values()))


if __name__ == "__main__":
    main()
