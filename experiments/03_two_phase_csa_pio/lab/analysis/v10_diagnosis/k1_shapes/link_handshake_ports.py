"""Construct B, "link handshake ports": find every candidate in the 41 modules.

A candidate is a NON-RECORD unit port whose counterparts reach, within two hops,
a neorv32_fifo instance port named we_i / re_i / avail_o / free_o / half_o / level_o,
or whose name suggests a handshake and which copies to / is driven from a register.

Also lists the INTERNAL elements on the path between such a port and the FIFO
instance port (the elements a keep rule for the ports must NOT keep).

Run:  python -B link_handshake_ports.py
Reads closed_set.json + rtl.txt per module and the manual reference. Never calls an API.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"E:\jobs\ff\test\Prepoison_subset")
INPUTS = ROOT / "experiments" / "03_two_phase_csa_pio" / "lab" / "inputs" / "v1"
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
SKIP = {"neorv32_boot_rom", "neorv32_fifo"}

FIFO_STROBE_IN = {"we_i", "re_i"}
FIFO_FLAG_OUT = {"avail_o", "free_o", "half_o", "level_o"}
FIFO_PORTS = FIFO_STROBE_IN | FIFO_FLAG_OUT
NAME_HINTS = {"valid", "ready", "ack", "cts", "ctsn", "rts", "rtsn", "req", "stb", "strobe",
              "busy", "wait", "done", "avail", "free", "full", "empty", "csn"}


def use_class(name):
    n = name.lower()
    if "irq" in n:
        return "interrupt"
    if any(t in n for t in ("dat", "sda", "sdo", "sdi_", "txd", "rxd", "neoled", "result", "res_")):
        return "data line"
    if any(t in n for t in ("clk", "clkgen", "scl")):
        return "clock line"
    if any(t in n for t in ("csn", "cs_")):
        return "select line"
    return "handshake-like"

FWD_KEYS = ("gives value to", "decides")          # input port -> inside
BWD_KEYS = ("gets value from", "decided by")      # output port <- inside


def load_modules():
    mods = {}
    for split in ("tuning", "heldout"):
        for d in sorted((INPUTS / split).iterdir()):
            if not d.is_dir() or d.name in SKIP:
                continue
            cs = json.loads((d / "closed_set.json").read_text(encoding="utf-8"))
            rtl = {}
            for ln in (d / "rtl.txt").read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"\s*(\d+) \| (.*)$", ln)
                if m:
                    rtl[int(m.group(1))] = m.group(2)
            mods[d.name] = {"split": split, "cs": cs, "rtl": rtl}
    return mods


def fifo_instances(rtl):
    """instance name -> line, from '<name>: entity neorv32.neorv32_fifo'."""
    out = {}
    for n, txt in rtl.items():
        m = re.match(r"\s*(\w+)\s*:\s*entity\s+\w+\.neorv32_fifo\b", txt)
        if m:
            out[m.group(1)] = n
    return out


def index_entity(ent):
    """name -> (kind, entry) for ports, record fields, signals, signal fields."""
    idx = {}
    for p in ent.get("port list", []):
        idx[p["port"]] = ("port", p)
        for f in p.get("fields", []):
            idx[f["field"]] = ("port-field", f)
    for s in ent.get("signal list", []):
        idx[s["signal"]] = ("signal", s)
        for f in s.get("fields", []):
            idx[f["field"]] = ("signal-field", f)
    return idx


def hop(entry, keys):
    """yield (counterpart dict, lines) over the chosen counterpart keys."""
    cp = entry.get("counterparts", {}) or {}
    for k in keys:
        for c in cp.get(k, []) or []:
            yield k, c


def search(mods, gt):
    candidates = []   # ports
    internals = {}    # (module, element) -> info
    for mod, M in mods.items():
        ref = {a["element"] for a in gt["modules"][mod]["assets"]}
        insts = fifo_instances(M["rtl"])
        for ent in M["cs"]["entity list"]:
            ename = ent["entity name"]
            idx = index_entity(ent)
            for p in ent.get("port list", []):
                if "fields" in p or "record type" in p:
                    continue  # record port: not this construct
                name, direc = p["port"], p["direction"]
                keys = FWD_KEYS if direc == "in" else BWD_KEYS
                want = FIFO_STROBE_IN if direc == "in" else FIFO_FLAG_OUT
                paths = []   # list of (via_element or None, inst, port, lines_port_side, lines_inst_side)
                reg_links = []
                for k0, c0 in hop(p, keys):
                    if "instance" in c0:
                        if c0["instance"] in insts and c0["port"] in FIFO_PORTS:
                            paths.append((k0, None, c0["instance"], c0["port"], c0["lines"], c0["lines"]))
                        continue
                    el = c0["element"]
                    kind, e1 = idx.get(el, (None, None))
                    if e1 is None:
                        continue
                    if e1.get("type") == "reg":
                        reg_links.append((k0, el, c0["lines"]))
                    for k1, c1 in hop(e1, keys):
                        if "instance" in c1 and c1["instance"] in insts and c1["port"] in FIFO_PORTS:
                            paths.append((k0, el, c1["instance"], c1["port"], c0["lines"], c1["lines"]))
                        elif "element" in c1:
                            # one register in between, then the fifo strobe/flag
                            el2 = c1["element"]
                            kind2, e2 = idx.get(el2, (None, None))
                            if e2 is None:
                                continue
                            for k2, c2 in hop(e2, keys):
                                if "instance" in c2 and c2["instance"] in insts and c2["port"] in FIFO_PORTS:
                                    paths.append((k0, el + " > " + el2, c2["instance"], c2["port"],
                                                  c0["lines"], c2["lines"]))
                hinted = bool(NAME_HINTS & set(name.lower().split("_")))
                if not paths and not (hinted and reg_links):
                    continue
                lines = sorted(set(p["occurrence lines"]))
                # direct = port <-> one wire <-> fifo port (no register on the way)
                direct = [pp for pp in paths
                          if pp[1] is None or (" > " not in pp[1] and idx[pp[1]][1].get("type") != "reg")]
                candidates.append({
                    "module": mod, "split": M["split"], "entity": ename, "element": name,
                    "direction": direc, "reference": name in ref, "lines": lines,
                    "use": use_class(name),
                    "path_class": "direct" if direct else ("via register" if paths else "register only"),
                    "fifo_paths": [{"key": k, "via": v, "instance": i, "fifo_port": fp,
                                    "port_side_lines": a, "inst_side_lines": b}
                                   for (k, v, i, fp, a, b) in paths],
                    "reg_links": [{"key": k, "element": e, "lines": l} for (k, e, l) in reg_links],
                    "name_hint": hinted,
                })
                for (k, v, i, fp, a, b) in paths:
                    for el in (v.split(" > ") if v else []):
                        kind, e = idx[el]
                        key = (mod, el)
                        info = internals.setdefault(key, {
                            "module": mod, "entity": ename, "element": el, "kind": kind,
                            "type": e.get("type"), "reference": el in ref,
                            "lines": sorted(set(e["occurrence lines"])), "between": set()})
                        info["between"].add(f"{name} <-> {i}.{fp}")
    for v in internals.values():
        v["between"] = sorted(v["between"])
    return candidates, list(internals.values())


def self_test(mods, candidates, internals):
    """Hand-read lines (read in the rtl.txt files by eye before this script was written)."""
    checks = [
        ("neorv32_slink", 229, ("rx_fifo.we", "slink_rx_valid_i")),
        ("neorv32_slink", 233, ("slink_rx_ready_o", "rx_fifo.free")),
        ("neorv32_slink", 298, ("tx_fifo.re", "slink_tx_ready_i")),
        ("neorv32_slink", 302, ("slink_tx_valid_o", "tx_fifo.avail")),
        ("neorv32_slink", 218, ("we_i", "rx_fifo.we")),
        ("neorv32_uart", 337, ("tx_engine.cts", "uart_ctsn_i")),
        ("neorv32_uart", 474, ("rx_fifo.half",)),
    ]
    fails = []
    for mod, ln, toks in checks:
        txt = mods[mod]["rtl"].get(ln, "")
        for t in toks:
            if t not in txt:
                fails.append(f"{mod}:{ln} lacks {t!r}: {txt!r}")
    byname = {(c["module"], c["element"]): c for c in candidates}
    expect = [
        ("neorv32_slink", "slink_rx_valid_i", True, "rx_fifo_inst", "we_i", 229),
        ("neorv32_slink", "slink_tx_ready_i", True, "tx_fifo_inst", "re_i", 298),
        ("neorv32_slink", "slink_rx_ready_o", True, "rx_fifo_inst", "free_o", 233),
        ("neorv32_slink", "slink_tx_valid_o", True, "tx_fifo_inst", "avail_o", 302),
    ]
    for mod, el, isref, inst, fp, ln in expect:
        c = byname.get((mod, el))
        if c is None:
            fails.append(f"missing candidate {mod}.{el}")
            continue
        if c["reference"] != isref:
            fails.append(f"{mod}.{el} reference flag wrong")
        ok = any(pp["instance"] == inst and pp["fifo_port"] == fp and ln in pp["port_side_lines"]
                 for pp in c["fifo_paths"])
        if not ok:
            fails.append(f"{mod}.{el} path to {inst}.{fp} at line {ln} not found: {c['fifo_paths']}")
    c = byname.get(("neorv32_uart", "uart_ctsn_i"))
    if c is None or not any(r["element"] == "tx_engine.cts" and 337 in r["lines"] for r in c["reg_links"]):
        fails.append("uart_ctsn_i -> tx_engine.cts at 337 not found")
    c = byname.get(("neorv32_uart", "uart_rtsn_o"))
    if c is None or not any(pp["instance"] == "rx_engine_fifo_inst" and pp["fifo_port"] == "half_o"
                            for pp in c["fifo_paths"]):
        fails.append("uart_rtsn_o <- rx_fifo.half <- rx_engine_fifo_inst.half_o not found")
    ints = {(i["module"], i["element"]): i for i in internals}
    for mod, el, isref in [("neorv32_slink", "rx_fifo.we", False), ("neorv32_slink", "tx_fifo.re", False),
                           ("neorv32_slink", "tx_fifo.avail", False), ("neorv32_slink", "rx_fifo.free", False)]:
        i = ints.get((mod, el))
        if i is None:
            fails.append(f"internal {mod}.{el} missing")
        elif i["reference"] != isref:
            fails.append(f"internal {mod}.{el} reference flag wrong")
    # every cited port-side line must mention the port (value copy) or the deciding element (decision),
    # and every inst-side line the instance port name
    for c in candidates:
        rtl = mods[c["module"]]["rtl"]
        for pp in c["fifo_paths"]:
            first = pp["via"].split(" > ")[0] if pp["via"] else None
            for ln in pp["port_side_lines"]:
                txt = rtl.get(ln, "")
                # a multi-line expression cites the term's line, which names the flag, not the port
                ok = c["element"] in txt or (first is not None and first in txt)
                if not ok:
                    fails.append(f"{c['module']}:{ln} ({pp['key']}) mentions neither {c['element']} nor {first}")
            for ln in pp["inst_side_lines"]:
                if pp["fifo_port"] not in rtl.get(ln, ""):
                    fails.append(f"{c['module']}:{ln} does not mention {pp['fifo_port']}")
    return fails


def main():
    mods = load_modules()
    gt = json.loads(GT.read_text(encoding="utf-8"))
    assert len(mods) == 41, len(mods)
    assert set(mods) == set(gt["modules"]), set(mods) ^ set(gt["modules"])
    candidates, internals = search(mods, gt)
    fails = self_test(mods, candidates, internals)
    out = {"self_test": "PASS" if not fails else "FAIL", "self_test_fails": fails,
           "n_modules": len(mods), "n_candidates": len(candidates),
           "n_reference": sum(c["reference"] for c in candidates),
           "candidates": candidates, "internals": internals}
    here = Path(__file__).resolve().parent
    (here / "link_handshake_ports.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("SELF-TEST", out["self_test"])
    for f in fails:
        print("  FAIL:", f)
    print(f"modules {len(mods)}  candidates {len(candidates)}  reference {out['n_reference']}")
    verbose = "-v" in sys.argv
    print("\n== PORT CANDIDATES (REF = in the reference) ==")
    for c in sorted(candidates, key=lambda x: (x["path_class"], x["use"], x["module"], x["element"])):
        tag = "REF" if c["reference"] else "---"
        print(f"{tag} {c['path_class']:13s} {c['use']:14s} {c['module']:22s} {c['element']:18s} "
              f"{c['direction']:3s} hint={int(c['name_hint'])} lines={c['lines']}")
        for pp in c["fifo_paths"]:
            print(f"      fifo: {pp['key']} via {pp['via']} -> {pp['instance']}.{pp['fifo_port']} "
                  f"port-side {pp['port_side_lines']} inst-side {pp['inst_side_lines']}")
        if verbose:
            for r in c["reg_links"]:
                print(f"      reg : {r['key']} {r['element']} {r['lines']}")
            rtl = mods[c["module"]]["rtl"]
            for ln in c["lines"]:
                print(f"      {ln:5d} | {rtl.get(ln, '')}")
    print("\n== INTERNAL ELEMENTS ON THE PATHS ==")
    for i in sorted(internals, key=lambda x: (x["module"], x["element"])):
        tag = "REF" if i["reference"] else "---"
        print(f"{tag} {i['module']:22s} {i['element']:20s} {i['kind']}/{i['type']} lines={i['lines']} "
              f"between={i['between']}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
