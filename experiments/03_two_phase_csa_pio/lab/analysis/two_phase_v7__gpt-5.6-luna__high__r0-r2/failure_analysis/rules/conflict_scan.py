"""The B1 / R5 conflict case, scanned in code over every closed set (15 tuning + 26 held-out modules).

Case (stage D, D/conflicts.json): a non-record output port P of an entity of this file that the unit instantiates,
whose only assignment is one concurrent statement copying a whole element unchanged (R5's condition, minus the
reply-dependent "that this walk labels primary"), and that drives through the port map a unit signal S whose
closed-set entry gets its value from that instance port and lists "decides" partners (B1's condition).
Reported: every (module, instance, port, signal) meeting B1's condition; those also meeting R5's port condition are the
conflict cases. Superset of the real conflict (the walk's label is not tested).
Self-test (hand-read): cache: S = cache_i.sta_hit gets its value from neorv32_cache_memory_inst.hit_o (RTL 286) and
decides bus_req_o.stb (RTL 189), so it meets B1's condition; hit_o is computed by a compare (RTL 405), not a copy, so it
does not meet R5's.

  python conflict_scan.py
"""
import json
import re
import sys
from pathlib import Path

INP = Path(__file__).resolve().parents[4] / "inputs" / "v1"


def instances(diagram):
    """instance name -> child entity, for instances of an entity of this file."""
    out = {}
    for l in diagram.splitlines():
        m = re.match(r"\s+\[inst\]\s+(\S+)\s+\((\S+), this file\)", l)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def elements(cs):
    """(entity, name) -> entry, ports, signals and fields."""
    out = {}
    for e in cs["entity list"]:
        for x in e["port list"] + e["signal list"]:
            nm = x.get("port") or x.get("signal")
            out[(e["entity name"], nm)] = x
            for f in x.get("fields", []):
                out[(e["entity name"], f["field"])] = f
    return out


def rtl(text):
    return {int(m.group(1)): m.group(2) for l in text.splitlines() if (m := re.match(r"\s*(\d+) \|(.*)$", l))}


def copy_port(child, port, E, R):
    """R5's port condition: a non-record output port whose only assignment is one statement 'port <= X;' with X a whole
    element (no index or slice) of the child entity."""
    x = E.get((child, port))
    if not x or x.get("direction") != "out" or x.get("record type") or x.get("fields"):
        return False, "not a non-record output port"
    assigns = [(n, R[n]) for n in x.get("occurrence lines") or [] if n in R and re.match(r"\s*" + re.escape(port) + r"\s*<=", R[n])]
    if len(assigns) != 1:
        return False, f"{len(assigns)} assignment lines"
    m = re.match(r"\s*" + re.escape(port) + r"\s*<=\s*([\w.]+)\s*;\s*(--.*)?$", assigns[0][1])
    if not m:
        return False, f"not a plain copy: RTL {assigns[0][0]}: {assigns[0][1].strip()}"
    return True, f"RTL {assigns[0][0]}: {assigns[0][1].strip()}"


def scan():
    rows = []
    for split in ("tuning", "heldout"):
        for d in sorted((INP / split).iterdir()):
            cs = json.loads((d / "closed_set.json").read_text(encoding="utf-8"))
            inst = instances((d / "diagram.txt").read_text(encoding="utf-8"))
            E, R = elements(cs), rtl((d / "rtl.txt").read_text(encoding="utf-8"))
            for (ent, nm), x in E.items():
                cp = x.get("counterparts") or {}
                src = [c for c in cp.get("gets value from", []) if isinstance(c, dict) and c.get("instance") in inst]
                if not src or not cp.get("decides"):
                    continue
                for c in src:
                    ok, why = copy_port(inst[c["instance"]], c["port"], E, R)
                    rows.append({"split": split, "module": d.name, "signal": nm, "instance": c["instance"], "child": inst[c["instance"]],
                                 "port": c["port"], "port-map lines": c.get("lines"), "R5 port condition": ok, "why": why})
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = scan()
    hit = next((r for r in rows if r["module"] == "neorv32_cache" and r["signal"] == "cache_i.sta_hit"), None)
    ok = hit is not None and hit["port"] == "hit_o" and not hit["R5 port condition"] and "405" in hit["why"]
    print("self-test (cache_i.sta_hit meets B1's condition; hit_o is not a plain copy, RTL 405):", "PASS" if ok else f"FAIL {hit}")
    if not ok:
        sys.exit(1)
    print(f"signals meeting B1's condition: {len(rows)} (tuning {sum(r['split'] == 'tuning' for r in rows)}, held-out {sum(r['split'] == 'heldout' for r in rows)})")
    for r in rows:
        print(f"  {r['split']:7s} {r['module']:28s} {r['signal']:22s} <- {r['instance']}.{r['port']} | R5 port condition: {r['R5 port condition']} ({r['why']})")
    both = [r for r in rows if r["R5 port condition"]]
    print(f"conflict cases (both conditions): {len(both)}")
    (Path(__file__).parent / "conflict_scan.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
