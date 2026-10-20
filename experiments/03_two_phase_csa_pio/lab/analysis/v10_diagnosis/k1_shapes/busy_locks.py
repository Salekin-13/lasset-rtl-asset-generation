"""Construct C, "busy locks": every busy / active / pending / run flag in the 41 modules,
and whether a condition reads it to block a request-port write or refuse a new command.

Inputs: lab/inputs/v1/{tuning,heldout}/<module>/{rtl.txt, closed_set.json}; the reference file.
Output: k1_shapes/busy_locks.json and a table on stdout. No API calls.

Self-test: the RTL line scanner and the code lock test are checked against hand-read lines
(HAND below, read in the session of 2026-10-18) before anything is reported.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(r"E:/jobs/ff/test/Prepoison_subset")
INPUTS = ROOT / "experiments/03_two_phase_csa_pio/lab/inputs/v1"
GT = ROOT / "data/ground_truth/manual_gt_neorv32.json"
OUT = Path(__file__).resolve().parent / "busy_locks.json"
SKIP = {"neorv32_boot_rom", "neorv32_fifo"}
NAME_RX = re.compile(r"busy|active|pending|run", re.I)
STATE_RX = re.compile(r"(^|[._])(state|fsm)$", re.I)
COND_KW = re.compile(r"\b(if|elsif|when|while)\b", re.I)

# ---------------------------------------------------------------- hand-read lines (self-test)
# (module, element, line, kind)  kind: assign = the line assigns the element,
# condition = a test on the line reads it, read = it is read as an operand or copied.
HAND = [
    ("neorv32_debug_dm", "dm_ctrl.busy", 339, "assign"),
    ("neorv32_debug_dm", "dm_ctrl.busy", 438, "condition"),
    ("neorv32_debug_dm", "dm_ctrl.busy", 443, "condition"),
    ("neorv32_debug_dm", "dm_ctrl.busy", 464, "condition"),
    ("neorv32_debug_dm", "dm_ctrl.busy", 469, "condition"),
    ("neorv32_debug_dm", "dm_ctrl.busy", 474, "condition"),
    ("neorv32_debug_dm", "dm_ctrl.busy", 495, "condition"),
    ("neorv32_debug_dm", "dm_ctrl.busy", 587, "read"),
    ("neorv32_debug_dm", "dm_ctrl.busy", 626, "condition"),
    ("neorv32_debug_dtm", "dmi_ctrl.busy", 250, "condition"),
    ("neorv32_debug_dtm", "dmi_ctrl.busy", 258, "condition"),
    ("neorv32_debug_dtm", "dmi_ctrl.busy", 264, "condition"),
    ("neorv32_debug_dtm", "dmi_ctrl.busy", 270, "assign"),
    ("neorv32_debug_dtm", "dmi_ctrl.busy", 276, "assign"),
    ("neorv32_uart", "tx_engine.busy", 215, "read"),
    ("neorv32_uart", "tx_engine.busy", 389, "assign"),
    ("neorv32_xbus", "pending", 87, "condition"),
    ("neorv32_xbus", "pending", 89, "assign"),
    ("neorv32_xbus", "pending", 93, "assign"),
    ("neorv32_xbus", "pending", 97, "assign"),
    ("neorv32_xbus", "pending", 115, "condition"),
    ("neorv32_xbus", "pending", 146, "read"),
    ("neorv32_xbus", "pending", 154, "condition"),
    ("neorv32_xbus", "pending", 155, "read"),
    ("neorv32_xbus", "pending", 156, "read"),
    ("neorv32_cpu_cp_shifter", "shifter.busy", 86, "read"),
    ("neorv32_cpu_cp_shifter", "shifter.busy", 88, "assign"),
    ("neorv32_cpu_cp_shifter", "shifter.busy", 90, "assign"),
    ("neorv32_cpu_cp_shifter", "shifter.busy", 110, "read"),
]
# hand-read outcome of the code lock test
HAND_LOCK = {
    ("neorv32_debug_dm", "dm_ctrl.busy"): {"dm_reg.command", "dm_reg.abstractauto_autoexecdata",
                                           "dm_reg.abstractauto_autoexecprogbuf", "dm_reg.progbuf",
                                           "dci.data_reg_we"},
    ("neorv32_uart", "tx_engine.busy"): set(),
    ("neorv32_neoled", "serial.busy"): set(),
}


# ---------------------------------------------------------------- loading
def load_modules():
    mods = {}
    for split in ("tuning", "heldout"):
        for d in sorted((INPUTS / split).iterdir()):
            if not d.is_dir() or d.name in SKIP or not (d / "closed_set.json").exists():
                continue
            rtl = {}
            for line in open(d / "rtl.txt", encoding="utf-8", errors="replace"):
                m = re.match(r"\s*(\d+) \|(.*)", line)
                if m:
                    rtl[int(m.group(1))] = m.group(2)
            mods[d.name] = {"split": split, "rtl": rtl, "cs": json.load(open(d / "closed_set.json"))}
    return mods


def flatten(cs):
    """Every element of every entity: name -> record with entity, kind, type/direction, roles, counterparts."""
    els = {}
    for e in cs["entity list"]:
        ent = e["entity name"]
        for lk, nk, kind in (("port list", "port", "port"), ("signal list", "signal", "signal")):
            for x in e.get(lk, []):
                rec = {"entity": ent, "kind": kind, "type": x.get("type"), "direction": x.get("direction"),
                       "record": "fields" in x, "roles": x.get("role in RTL", []),
                       "cp": x.get("counterparts", {}), "lines": x.get("occurrence lines", [])}
                els[(ent, x[nk])] = rec
                for fl in x.get("fields", []):
                    els[(ent, fl["field"])] = {"entity": ent, "kind": kind + "-field", "type": fl.get("type"),
                                               "direction": x.get("direction"), "record": False,
                                               "parent": x[nk], "roles": fl.get("role in RTL", []),
                                               "cp": fl.get("counterparts", {}),
                                               "lines": fl.get("occurrence lines", [])}
    return els


def partners(rec, key):
    return [(c.get("element") or (c.get("instance", "?") + ":" + c.get("port", "?")), c.get("lines", []))
            for c in rec["cp"].get(key, [])]


# ---------------------------------------------------------------- RTL scan
def scan(rtl, name):
    """Lines mentioning the element as a whole token, each with its kind."""
    tok = re.compile(r"(?<![\w.])" + re.escape(name) + r"(?![\w])")
    target = re.compile(r"^\s*" + re.escape(name) + r"\s*(\([^<]*\))?\s*<=")
    out = []
    for n in sorted(rtl):
        text = rtl[n]
        if not tok.search(text):
            continue
        if target.match(text):
            kind = "assign"
        else:
            m = COND_KW.search(text)
            pos = tok.search(text).start()
            # a test reads it when the name sits after if / elsif / when on the line
            if m and any(k.start() < pos for k in COND_KW.finditer(text)):
                kind = "condition"
            else:
                kind = "read"
        out.append((n, kind))
    return out


# ---------------------------------------------------------------- code lock test
def request_ports(els, ent):
    """Record input ports an access or command arrives on: *req_i and the processor's ctrl_i."""
    return {n for (e, n), r in els.items() if e == ent and r["kind"] == "port" and r["record"]
            and r["direction"] == "in" and ("req" in n or n == "ctrl_i")}


def gets_from_request(els, ent, name, reqs):
    rec = els.get((ent, name))
    if not rec:
        return []
    return [(p, L) for p, L in partners(rec, "gets value from") if p.split(".")[0] in reqs]


def lock_test(els, ent, rec, reqs):
    """For each element the flag decides: is it a register (or the write enable of one) that a
    request port writes?  Returns the blocked writes and the other decided elements."""
    blocked, other = [], []
    for p, L in partners(rec, "decides"):
        src = gets_from_request(els, ent, p, reqs)
        hop = []
        prec = els.get((ent, p))
        if not src and prec and "set to constants only" in prec["roles"]:
            for q, _ in partners(prec, "decides"):
                hop += [(q, s) for s in gets_from_request(els, ent, q, reqs)]
        if src or hop:
            blocked.append({"element": p, "lines": L, "written from": src or hop})
        else:
            kind = "output port" if prec and prec["kind"] == "port" and prec["direction"] == "out" else \
                   "state register" if STATE_RX.search(p) else "internal"
            other.append({"element": p, "lines": L, "kind": kind})
    return blocked, other


# ---------------------------------------------------------------- main
def main():
    mods = load_modules()
    assert len(mods) == 41, len(mods)
    gt = json.load(open(GT))["modules"]

    # self-test 1: the line scanner against hand-read lines
    fails = []
    for mod, el, line, kind in HAND:
        got = dict(scan(mods[mod]["rtl"], el))
        if got.get(line) != kind:
            fails.append((mod, el, line, kind, got.get(line)))
    # self-test 2: the code lock test against hand-read outcomes
    for (mod, el), want in HAND_LOCK.items():
        els = flatten(mods[mod]["cs"])
        key = next(k for k in els if k[1] == el)
        blocked, _ = lock_test(els, key[0], els[key], request_ports(els, key[0]))
        got = {b["element"] for b in blocked}
        if got != want:
            fails.append((mod, el, "lock", sorted(want), sorted(got)))
    if fails:
        print("SELF-TEST FAIL; nothing reported")
        for f in fails:
            print("  ", f)
        sys.exit(1)
    print(f"SELF-TEST PASS ({len(HAND)} hand-read lines, {len(HAND_LOCK)} lock outcomes)")

    rows = []
    for mod, M in mods.items():
        els = flatten(M["cs"])
        gt_names = {a["element"]: a for a in gt[mod]["assets"]}
        for (ent, name), rec in els.items():
            if rec["record"]:
                continue
            by_name = bool(NAME_RX.search(name))
            lines = scan(M["rtl"], name)
            assigns = {n for n, k in lines if k == "assign"}
            # decoded from a state register: a wire whose own assignment line is the line on which
            # the state register decides it (busy <= '0' when (state = IDLE) else '1'); a register the
            # state machine's case statement loads is "decided by" the state too, but is not a decode.
            by_state = (rec["kind"] != "port" and rec["type"] == "wire" and "condition" in rec["roles"]
                        and not STATE_RX.search(name)
                        and any(STATE_RX.search(p) and set(L) & assigns for p, L in partners(rec, "decided by")))
            if not (by_name or by_state):
                continue
            reqs = request_ports(els, ent)
            blocked, other = lock_test(els, ent, rec, reqs)
            rows.append({
                "module": mod, "split": M["split"], "entity": ent, "element": name,
                "coprocessor": mod.startswith("neorv32_cpu_cp_"),
                "kind": rec["kind"], "type": rec["type"] or rec["direction"], "roles": rec["roles"],
                "class": ("name" if by_name else "") + ("+state" if by_state else ""),
                "decided by": partners(rec, "decided by"), "gets from": partners(rec, "gets value from"),
                "gives to": partners(rec, "gives value to"),
                "blocked writes (code)": blocked, "other decided (code)": other,
                "lock (code)": bool(blocked), "request ports": sorted(reqs),
                "rtl lines": lines,
                "reference": name in gt_names,
                "reference why": gt_names[name]["why"] if name in gt_names else None,
            })
    json.dump(rows, open(OUT, "w"), indent=1)
    n_ref = sum(r["reference"] for r in rows)
    print(f"candidates {len(rows)} (non-coprocessor {sum(not r['coprocessor'] for r in rows)}, "
          f"coprocessor {sum(r['coprocessor'] for r in rows)}); reference {n_ref}; wrote {OUT}")
    for r in rows:
        cond = [n for n, k in r["rtl lines"] if k == "condition"]
        print(f"{'CP ' if r['coprocessor'] else '   '}{r['module']:26s} {r['element']:34s} {r['type']:5s} "
              f"{r['class']:11s} ref={int(r['reference'])} lock(code)={int(r['lock (code)'])} "
              f"cond_lines={cond} assign={[n for n, k in r['rtl lines'] if k == 'assign']} "
              f"read={[n for n, k in r['rtl lines'] if k == 'read']}")
        for b in r["blocked writes (code)"]:
            print(f"      blocks {b['element']} at {b['lines']}, written from {b['written from']}")
        if r["reference"]:
            print(f"      reference why: {r['reference why'][:160]}")


if __name__ == "__main__":
    main()
