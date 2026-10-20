"""P3 code check: drop listed primaries that two v7 Phase 1 bars already exclude.

Run:  python check.py <out.json> [--inputs DIR] [--raw DIR]
  --inputs  folder of <module>/{rtl.txt, closed_set.json, diagram.txt} (default inputs/v1/tuning)
  --raw     folder of r<k>/phase2/<module>.json replies (default failure_analysis/raw); a missing
            folder or run means only the closed-set flags are printed and nothing is dropped.
The self-test always runs on the tuning inputs, because its hand-read lines come from there.

Reads ONLY the stored v7 replies and the inputs, plus selftest_lines.json (the hand-read fixture next
to this script). Opens no reference, scoring, verdict or stage-B file.

Test A, the cache bar (phase1.md:40, "Cached copies"). A cache is found from closed-set facts:
  (a1) tag match: an entity E of this file, instantiated in the unit (diagram "[inst] ... (E, this file)"),
       has an element H (any element of E) "decided by" an element A and an element Tr, where A gets
       value from an input port of E (the access address), Tr is held on a clock edge and gets value from
       a store S held on a clock edge, and S gets value from A (the stored tag is written from the same
       address it is compared with);
  (a2) backing bus: the unit signal wired to the write-data input W of E's data arrays gets value from a
       field of a unit input port P, where P's record type is the record type of a unit output port Q
       that returns the cached words (a field of Q gets value from a unit signal taking a read output of
       E), and the unit also has another record type used by both an input and an output port (the
       request it forwards to the backing bus). So the words come in as a response over the backing bus,
       of the type the unit returns to its host; a host write of the request type alone does not pass.
  Dropped: (i) a data array of E: not a port, held on a clock edge, gets value only from W, gives value
  only to output ports of E; (ii) the carriers whose only assignments copy words into or out of such an
  array: an output port of E that gets value only from data arrays, the input port W itself, a signal of
  the unit (not a unit port) whose only "gives value to" is the instance port W, and a signal of the unit
  (not a unit port) that gets value only from an output port of E of kind (ii).
  Not dropped (the bar's own "judged as usual" list): the hit, the address, write enables, fill / clear /
  invalidate commands, pending sync state, the tag and valid stores (S, Tr: they get value from A or from
  no port, never from W), unit boundary ports, and any memory with no tag match (a1).

Test B, the port-buffer bar (phase1.md:35, "Port buffers"). A FIFO instance is judged from its port
names, as phase1.md:35 tells the model to ("Judge from port names that an instance is a FIFO"): an
instance of another IP whose port set has a write-data input, a read-data output, a clear input and a
fill flag. This is the one place the test reads names: the FIFO's own port-name stems, never an element
of the unit. The FIFO buffers port data when the signal wired to its write-data input reaches a unit input
port through element "gets value from" links (any depth): a bus write, or bits shifted in from a serial
input port. The walk does not pass through instance outputs. For such a FIFO, dropped:
  (b1) a command only clearing it: a non-port element held on a clock edge whose "decides" set is exactly
       the wire feeding the FIFO's clear input, that gives value to nothing (no element, no port, no
       instance port). A unit enable that also clears the FIFO is kept: it decides other elements, or it
       gives value to something (it is read back, or drives an instance's enable input).
  (b2) a flag recording a push while full: a non-port element held on a clock edge and set to constants
       only, decided by the wire feeding the FIFO's write enable and by the wire taking its has-room flag,
       that decides nothing, drives no instance port, and gives value to nothing but unit output ports.
  Not dropped: a FIFO whose write data reaches no unit input port (data the unit generates itself).

The tests use roles, counterparts, record types, port directions, block membership and the FIFO's port
names only. Unit element names appear only in the self-test fixture, which checks the tests against
hand-read RTL lines and against planted changes to the closed set.
"""
import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent            # failure_analysis/rules/P3
FA = HERE.parents[1]                              # failure_analysis
LAB = FA.parents[2]                               # experiments/03_two_phase_csa_pio/lab
TUNING = LAB / "inputs" / "v1" / "tuning"
RAW = FA / "raw"
RUNS = ("r0", "r1", "r2")


# ---------------------------------------------------------------- closed-set helpers
def nodes(ent):
    """name -> (node, is_port, direction, top-level port record type)"""
    out = {}

    def add(n, is_port, direction, rtype):
        nm = n.get("field") or n.get("port") or n.get("signal")
        d = n.get("direction", direction)
        out[nm] = (n, is_port, d, rtype)
        for f in n.get("fields", []):
            add(f, is_port, d, rtype)

    for p in ent.get("port list", []):
        add(p, True, p.get("direction"), p.get("record type"))
    for s in ent.get("signal list", []):
        add(s, False, None, s.get("record type"))
    return out


def rel(n, key):
    return n.get("counterparts", {}).get(key, [])


def els(n, key):
    return {t["element"] for t in rel(n, key) if "element" in t}


def inst_targets(n, key):
    return {(t["instance"], t["port"]) for t in rel(n, key) if "instance" in t}


def roles(n):
    return set(n.get("role in RTL", []))


def diagram_instances(text):
    """instance -> (entity, 'this file' | 'another IP')"""
    out = {}
    for m in re.finditer(r"\[inst\]\s+(\S+)\s+\((\S+),\s*(this file|another IP)\)", text):
        out[m.group(1)] = (m.group(2), m.group(3))
    return out


# ---------------------------------------------------------------- test A: cache bar
def cache_drops(cs, insts):
    ents = {e["entity name"]: e for e in cs["entity list"]}
    flagged = {}
    for top_name, top in ents.items():
        T = nodes(top)
        # unit ports of the top entity, by record type
        in_types = {rt for k, (n, ip, d, rt) in T.items() if ip and d == "in" and rt}
        out_types = {rt for k, (n, ip, d, rt) in T.items() if ip and d == "out" and rt}
        shared_types = in_types & out_types
        for inst, (ename, where) in insts.items():
            if where != "this file" or ename not in ents or ename == top_name:
                continue
            wired_in = {}  # E input port -> top signals wired to it
            wired_out = {}  # E output port -> top signals taking it
            for k, (n, ip, d, rt) in T.items():
                for (i2, p) in inst_targets(n, "gives value to"):
                    if i2 == inst:
                        wired_in.setdefault(p, set()).add(k)
                for (i2, p) in inst_targets(n, "gets value from"):
                    if i2 == inst:
                        wired_out.setdefault(p, set()).add(k)
            if not wired_in:
                continue
            E = nodes(ents[ename])
            e_in = {k for k, (n, ip, d, rt) in E.items() if ip and d == "in"}
            e_out = {k for k, (n, ip, d, rt) in E.items() if ip and d == "out"}
            held = {k for k, (n, ip, d, rt) in E.items() if "held on a clock edge" in roles(n)}
            # (a1) tag match
            tag_match = False
            for h, (hn, _, _, _) in E.items():
                db = els(hn, "decided by")
                for a in db:
                    if a not in E or not (els(E[a][0], "gets value from") & e_in):
                        continue
                    for tr in db - {a}:
                        if tr not in held:
                            continue
                        for s in els(E[tr][0], "gets value from"):
                            if s in held and a in els(E[s][0], "gets value from"):
                                tag_match = True
            if not tag_match:
                continue
            # data arrays: non-port, held, gets value only from one input port W, gives value only to outputs
            arrays = {}
            for k, (n, ip, d, rt) in E.items():
                if ip or k not in held:
                    continue
                g = els(n, "gets value from")
                gv = els(n, "gives value to")
                if len(g) == 1 and g <= e_in and gv and gv <= e_out:
                    arrays[k] = next(iter(g))
            if not arrays:
                continue
            # (a2) backing bus. Q: unit output ports returning the cached words (a field gets value from a
            # unit signal taking a read output of E). P: a unit input port of Q's record type feeding the
            # signal wired to W. A second shared record type: the request forwarded to the backing bus.
            read_outs = {k for k, (n, ip, d, rt) in E.items()
                         if ip and d == "out" and els(n, "gets value from")
                         and els(n, "gets value from") <= set(arrays)}
            read_sigs = set()
            for o in read_outs:
                read_sigs |= wired_out.get(o, set())
            rsp_types = {rt for k, (n, ip, d, rt) in T.items()
                         if ip and d == "out" and rt and els(n, "gets value from") & read_sigs}
            fwd_types = shared_types - rsp_types
            kept_arrays = {}
            if rsp_types and fwd_types:
                for k, w in arrays.items():
                    ok = False
                    for sig in wired_in.get(w, set()):
                        for src in els(T[sig][0], "gets value from"):
                            if (src in T and T[src][1] and T[src][2] == "in"
                                    and T[src][3] in rsp_types and T[src][3] in shared_types):
                                ok = True
                    if ok:
                        kept_arrays[k] = w
            if not kept_arrays:
                continue
            for k in kept_arrays:
                flagged[(ename, k)] = "A(i) data array of a tag-matched cache with a backing bus"
            ws = set(kept_arrays.values())
            for w in ws:
                flagged[(ename, w)] = "A(ii) write-data input feeding only cache data arrays"
            outs = set()
            for k, (n, ip, d, rt) in E.items():
                g = els(n, "gets value from")
                if ip and d == "out" and g and g <= set(kept_arrays):
                    outs.add(k)
                    flagged[(ename, k)] = "A(ii) output port reading only cache data arrays"
            for k, (n, ip, d, rt) in T.items():
                if ip:
                    continue
                gv = rel(n, "gives value to")
                gf = rel(n, "gets value from")
                if gv and all("instance" in t and t["instance"] == inst and t["port"] in ws for t in gv):
                    flagged[(top_name, k)] = "A(ii) unit signal whose only use is the cache write data"
                if gf and all("instance" in t and t["instance"] == inst and t["port"] in outs for t in gf):
                    flagged[(top_name, k)] = "A(ii) unit signal taking only the cache read data"
    return flagged


# ---------------------------------------------------------------- test B: port-buffer bar
def fifo_port_roles(ports):
    """Judge FIFO port roles from the FIFO's own port names (phase1.md:35)."""
    r = {}
    for p in ports:
        q = p.lower()
        if "wdata" in q:
            r["wdata"] = p
        elif "rdata" in q:
            r["rdata"] = p
        elif "clear" in q:
            r["clear"] = p
        elif q.startswith("we"):
            r["we"] = p
        elif q.startswith("free"):
            r["free"] = p
        elif q.startswith(("avail", "full", "empty", "half")):
            r.setdefault("flag", p)
    return r


def fifo_drops(cs, insts):
    flagged = {}
    for ent in cs["entity list"]:
        en = ent["entity name"]
        N = nodes(ent)
        inports = {k for k, (n, ip, d, rt) in N.items() if ip and d == "in"}
        outports = {k for k, (n, ip, d, rt) in N.items() if ip and d == "out"}
        inst_in, inst_out = {}, {}
        for k, (n, ip, d, rt) in N.items():
            for (i, p) in inst_targets(n, "gives value to"):
                inst_in.setdefault(i, {})[p] = k
            for (i, p) in inst_targets(n, "gets value from"):
                inst_out.setdefault(i, {})[p] = k

        def reaches_inport(sig, seen):
            if sig in seen:
                return False
            seen.add(sig)
            if sig in inports:
                return True
            if sig not in N:
                return False
            return any(reaches_inport(s, seen) for s in els(N[sig][0], "gets value from"))

        for inst, ins in inst_in.items():
            if insts.get(inst, ("", ""))[1] != "another IP":
                continue
            outs = inst_out.get(inst, {})
            ri, ro = fifo_port_roles(ins), fifo_port_roles(outs)
            if not ("wdata" in ri and "clear" in ri and "rdata" in ro and ("free" in ro or "flag" in ro)):
                continue
            if not reaches_inport(ins[ri["wdata"]], set()):
                continue  # data the unit generates itself: not covered by the bar
            clear_w = ins[ri["clear"]]
            we_w = ins.get(ri.get("we"))
            free_w = outs.get(ro.get("free"))
            for k, (n, ip, d, rt) in N.items():
                if ip or "held on a clock edge" not in roles(n):
                    continue
                if inst_targets(n, "gives value to"):
                    continue
                dec = els(n, "decides")
                gv = els(n, "gives value to")
                if dec == {clear_w} and not gv:
                    flagged[(en, k)] = "B(1) command only clearing a port-data FIFO"
                db = els(n, "decided by")
                if ("set to constants only" in roles(n) and not dec and gv <= outports
                        and we_w and free_w and we_w in db and free_w in db):
                    flagged[(en, k)] = "B(2) flag recording a push into a full port-data FIFO"
    return flagged


# ---------------------------------------------------------------- replies
def primaries(reply):
    out = set()
    for w in reply.get("Concept Walks", []) or []:
        for a in w.get("Assets", []) or []:
            if not isinstance(a, dict) or a.get("Label") != "primary":
                continue
            same = a.get("Same Role") or []
            if isinstance(same, str):
                same = [same]
            for n in [a.get("Asset RTL")] + list(same):
                if isinstance(n, str):
                    out.add((a.get("Entity"), n))
    return out


def load_module(inputs, mdir):
    cs = json.load(open(inputs / mdir / "closed_set.json", encoding="utf-8"))
    insts = diagram_instances(open(inputs / mdir / "diagram.txt", encoding="utf-8").read())
    return cs, insts


def flags_of(cs, insts):
    f = cache_drops(cs, insts)
    f.update(fifo_drops(cs, insts))
    return f


def module_flags(mdir, inputs=TUNING):
    return flags_of(*load_module(inputs, mdir))


def rtl_line(mdir, num, inputs=TUNING):
    pat = re.compile(r"^\s*%d \|(.*)$" % num)
    for line in open(inputs / mdir / "rtl.txt", encoding="utf-8"):
        m = pat.match(line.rstrip("\n"))
        if m:
            return m.group(1)
    return ""


def find_node(cs, entity, element):
    for e in cs["entity list"]:
        if e["entity name"] == entity:
            return nodes(e)[element][0]
    raise KeyError((entity, element))


# ---------------------------------------------------------------- self-test against hand-read lines
def self_test():
    """Hand-read RTL lines and the flags they imply live in selftest_lines.json next to this script (the
    fixture names elements; the tests above do not). Checks: (1) each hand-read line holds the words read
    by hand; (2) the flags on the fixture's modules equal the hand-read lists, and the kept elements stay;
    (3) planted changes to the closed set (a counterpart removed or added, as a hand reading says it would
    matter) change the flags as expected; (4) for every flagged element, each RTL line the closed set cites
    for its value or decision links names the counterpart, and also the element unless the line is the
    counterpart's condition (the closed set agrees with the RTL)."""
    fx = json.load(open(HERE / "selftest_lines.json", encoding="utf-8"))
    bad = []
    for m, ln, words in fx["lines"]:
        text = rtl_line(m, ln)
        for w in words:
            if w not in text:
                bad.append(f"{m} RTL {ln}: '{w}' not in {text!r}")
    for m, pairs in fx["expect"].items():
        got = set(module_flags(m))
        exp = {tuple(p) for p in pairs}
        if got != exp:
            bad.append(f"{m}: flags {sorted(got)} != hand-read {sorted(exp)}")
    for m, en, el in fx["keep"]:
        if (en, el) in module_flags(m):
            bad.append(f"{m}: kept element flagged: {en} {el}")
    for pl in fx.get("plants", []):
        cs, insts = load_module(TUNING, pl["module"])
        cs = copy.deepcopy(cs)
        for ch in pl["changes"]:
            n = find_node(cs, ch["entity"], ch["element"])
            lst = n.setdefault("counterparts", {}).setdefault(ch["key"], [])
            if "remove" in ch:
                lst[:] = [t for t in lst if t.get("element") != ch["remove"]]
            if ch.get("remove_instances"):
                lst[:] = [t for t in lst if "instance" not in t]
            if "add" in ch:
                lst.append({"element": ch["add"], "lines": []})
        got = set(flags_of(cs, insts))
        exp = {tuple(p) for p in pl["expect"]}
        if got != exp:
            bad.append(f"plant {pl['why']}: flags {sorted(got)} != expected {sorted(exp)}")
    for mdir in module_dirs(TUNING):
        cs = json.load(open(TUNING / mdir / "closed_set.json", encoding="utf-8"))
        ents = {e["entity name"]: nodes(e) for e in cs["entity list"]}
        for (en, el) in module_flags(mdir):
            n = ents[en][el][0]
            base = el.split(".")[-1]
            for key in ("gets value from", "gives value to", "decides", "decided by"):
                for t in rel(n, key):
                    other = (t.get("element") or t.get("port") or "").split(".")[-1]
                    for ln in t.get("lines", []):
                        text = rtl_line(mdir, ln)
                        if other not in text or (key != "decided by" and base not in text):
                            bad.append(f"{mdir}: RTL {ln} cited for {el} ({key} {other}) does not match")
    return bad


def module_dirs(inputs):
    return sorted(d for d in os.listdir(inputs) if (inputs / d / "closed_set.json").exists())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--inputs", default=str(TUNING))
    ap.add_argument("--raw", default=str(RAW))
    args = ap.parse_args()
    inputs, raw = Path(args.inputs), Path(args.raw)
    bad = self_test()
    if bad:
        print("SELF-TEST FAILED; nothing reported")
        for b in bad:
            print("  ", b)
        sys.exit(1)
    print("self-test passed")
    result = {r: {} for r in RUNS}
    all_flags = {}
    for mdir in module_dirs(inputs):
        fl = module_flags(mdir, inputs)
        if fl:
            all_flags[mdir] = fl
    for mdir, fl in all_flags.items():
        for k, v in sorted(fl.items()):
            print(f"flagged {mdir}: {k[0]} {k[1]} -- {v}")
    for r in RUNS:
        rdir = raw / r / "phase2"
        if not rdir.is_dir():
            continue
        for fn in sorted(os.listdir(rdir)):
            m = fn[:-5]
            if m not in all_flags:
                continue
            short = m.split("_", 1)[1]  # module short name: the part after the design prefix
            reply = json.load(open(rdir / fn, encoding="utf-8"))
            fl = all_flags[m]
            drops = [{"element": e, "entity": en, "action": "drop", "why": fl[(en, e)]}
                     for (en, e) in sorted(primaries(reply)) if (en, e) in fl]
            if drops:
                result[r][short] = drops
    json.dump(result, open(args.out, "w", encoding="utf-8"), indent=1)
    for r in RUNS:
        n = sum(len(v) for v in result[r].values())
        print(r, n, {m: [d["element"] for d in v] for m, v in result[r].items()})


if __name__ == "__main__":
    main()
