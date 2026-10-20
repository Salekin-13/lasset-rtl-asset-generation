"""Combined code rows (R1-enforce, R8 for U1, U2 check, U6 check, U10 check) applied to stored v4a AND v5 replies.
Each check's predicate is copied from its self-tested prototype in the scratchpad (u1_codecheck.py, u2_codecheck_sim.py,
u6_code_check.py, u10_codecheck.py) and c10_busfields.is_bus. Tuning closed sets only; no reference file is read
except through pack3.json (tp/fp already scored).
Self-test: each single check must reproduce the per-check precision figures reported earlier this session."""
import json, re, sys
from pathlib import Path
from collections import defaultdict, deque
sys.stdout.reconfigure(encoding="utf-8")
LAB = Path(r"E:/jobs/ff/test/Prepoison_subset/experiments/03_two_phase_csa_pio/lab")
AN = LAB / "analysis"
TUN = LAB / "inputs" / "v1" / "tuning"
sys.path.insert(0, str(AN / "two_phase_v2__gpt-5.6-luna__high__r0-r2" / "p1_rules"))
import c10_busfields as BF  # noqa
V = {"v4a": "two_phase_v4a__gpt-5.6-luna__high__r0-r2", "v5": "two_phase_v5__gpt-5.6-luna__high__r0-r2"}
RUNS = ("r0", "r1", "r2")

# ---------------- R8 (U1) ----------------
def r8(module):
    cs = json.loads((TUN / module / "closed_set.json").read_text(encoding="utf-8"))
    E = {}
    for e in cs["entity list"]:
        en = e["entity name"]
        for kind, lst, key in (("port", e["port list"], "port"), ("signal", e["signal list"], "signal")):
            for x in lst:
                x2 = dict(x); x2["kind"] = kind; E[(en, x[key])] = x2
                for f in x.get("fields", []):
                    f2 = dict(f); f2["kind"] = kind + " field"; E[(en, f["field"])] = f2
    def partners(entry, groups):
        return [p.get("element") or (p.get("instance"), p.get("port")) for g in groups for p in entry.get("counterparts", {}).get(g, [])]
    irq = {n for (en, n), v in E.items() if v["kind"] == "port" and v.get("direction") == "out" and n.startswith("irq")}
    out = set()
    for key, e in E.items():
        if "bus_req_i.data" not in partners(e, ["gets value from"]):
            continue
        fo = [p for p in partners(e, ["gives value to", "decides"]) if not (isinstance(p, str) and p.startswith("bus_rsp_o"))]
        if fo and all(isinstance(p, str) and p in irq for p in fo):
            out.add(key)
    return out

# ---------------- U2 ----------------
FLAG_PORTS = {"avail_o", "free_o", "half_o", "we_i", "re_i", "clear_i"}
def u2(module):
    cs = json.loads((TUN / module / "closed_set.json").read_text(encoding="utf-8"))
    unit = cs["entity list"][0]["entity name"]
    def entries():
        for ent in cs["entity list"]:
            en = ent["entity name"]
            for p in ent.get("port list", []):
                yield en, p.get("port"), p, True
                for f in p.get("fields", []) or []:
                    yield en, f.get("field"), f, True
            for s in ent.get("signal list", []):
                yield en, s.get("signal"), s, False
                for f in s.get("fields", []) or []:
                    yield en, f.get("field"), f, False
    info, inports, inst = {}, set(), defaultdict(dict)
    for en, name, e, isport in entries():
        if en != unit or not name: continue
        info[name] = (e, isport)
        if isport and e.get("direction") == "in": inports.add(name)
        for kind in ("gives value to", "gets value from"):
            for c in e.get("counterparts", {}).get(kind, []):
                if "instance" in c:
                    inst[c["instance"]][c["port"]] = name
    for name, (e, isport) in list(info.items()):
        if isport and "." in name and name.split(".")[0] in inports: inports.add(name)
    def reaches_input(start):
        seen, q = {start}, deque([start])
        while q:
            x = q.popleft()
            if x in inports: return True
            e = info.get(x, ({}, False))[0]
            for c in e.get("counterparts", {}).get("gets value from", []):
                if "instance" in c: continue
                y = c.get("element")
                if y and y not in seen: seen.add(y); q.append(y)
        return False
    demote = set()
    for i, pm in inst.items():
        if not {"wdata_i", "we_i", "re_i", "avail_o"} <= set(pm): continue
        if not reaches_input(pm["wdata_i"]): continue
        for p, el in pm.items():
            if p in FLAG_PORTS and not info.get(el, ({}, False))[1]:
                demote.add((unit, el))
        we, fr = pm.get("we_i"), pm.get("free_o")
        for name, (e, isport) in info.items():
            if isport or "set to constants only" not in e.get("role in RTL", []): continue
            dec = {c.get("element") for c in e.get("counterparts", {}).get("decided by", [])}
            if we in dec and fr in dec: demote.add((unit, name))
    return demote

# ---------------- U6 ----------------
UNIT_SET = {"held on a clock edge", "set without a clock", "reset to a constant", "set to constants only", "tied to a constant"}
def u6(module):
    mdir = TUN / module
    ext = set()
    for ln in (mdir / "diagram.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*\[inst\] (\S+) \(([^,]+), another IP\)", ln)
        if m: ext.add(m.group(1))
    cs = json.loads((mdir / "closed_set.json").read_text(encoding="utf-8"))
    out = set()
    for ent in cs["entity list"]:
        for x in ent.get("signal list", []):
            if not x.get("fields"): continue
            g = x.get("counterparts", {}).get("gets value from", [])
            gv = x.get("counterparts", {}).get("gives value to", [])
            if len(g) != 1 or "instance" not in g[0] or "." in g[0]["port"] or g[0]["instance"] not in ext: continue
            if not any("instance" in p and "." not in p["port"] for p in gv): continue
            if set(x.get("role in RTL", [])) & UNIT_SET: continue
            inst, port = g[0]["instance"], g[0]["port"]
            ok = True
            for f in x["fields"]:
                if set(f.get("role in RTL", [])) & UNIT_SET: ok = False
                for p in f.get("counterparts", {}).get("gets value from", []):
                    if p.get("instance") != inst or not p.get("port", "").startswith(port + "."): ok = False
            if ok:
                out.add((ent["entity name"], x["signal"]))
                out |= {(ent["entity name"], f["field"]) for f in x["fields"]}
    return out

# ---------------- U10 ----------------
def u10(module):
    cs = json.loads((TUN / module / "closed_set.json").read_text(encoding="utf-8"))
    ents = {}
    for e in cs["entity list"]:
        el = {}
        for p in e.get("port list", []):
            fields = [f["field"].split(".", 1)[1] for f in p.get("fields", [])]
            busreq = p.get("direction") == "in" and {"addr", "data", "stb"} <= set(fields)
            el[p["port"]] = dict(type=None, cp=p.get("counterparts", {}), lockfield=False)
            for f in p.get("fields", []):
                el[f["field"]] = dict(type=None, cp=f.get("counterparts", {}), lockfield=busreq and f["field"].split(".", 1)[1] == "lock")
        for s in e.get("signal list", []):
            el[s["signal"]] = dict(type=s.get("type"), cp=s.get("counterparts", {}), lockfield=False)
            for f in s.get("fields", []):
                el[f["field"]] = dict(type=f.get("type"), cp=f.get("counterparts", {}), lockfield=False)
        ents[e["entity name"]] = el
    def names(cp, key):
        return {x.get("element") for x in cp.get(key, []) if isinstance(x, dict) and x.get("element")}
    out = set()
    for en, el in ents.items():
        for r, x in el.items():
            if x["type"] != "reg": continue
            gets = names(x["cp"], "gets value from") - {r}
            own_next = {w for w in gets if w in el and el[w]["type"] == "wire" and names(el[w]["cp"], "gives value to") <= {r}
                        and r in names(el[w]["cp"], "gets value from")}
            src = set()
            for w in gets:
                src |= (names(el[w]["cp"], "gets value from") - {r}) if w in own_next else {w}
            gives = names(x["cp"], "gives value to") - {r} - own_next
            if gives or not src: continue
            if all(s in el and el[s]["lockfield"] for s in src) or (len(src) == 1 and next(iter(src)) in names(x["cp"], "decides")):
                out.add((en, r))
    return out

def r1(module, entity, element):
    return BF.is_bus(module, entity, element)

P = {v: json.loads((AN / d / "pack3.json").read_text(encoding="utf-8")) for v, d in V.items()}
MODS = sorted(P["v5"]["modules"])
CH = {"R8": {m: r8(m) for m in MODS}, "U2": {m: u2(m) for m in MODS}, "U6": {m: u6(m) for m in MODS}, "U10": {m: u10(m) for m in MODS}}

def apply(v, k, checks):
    t = P[v]["totals"][k]; L, T = t["listed"], t["tp"]
    dfp = dtp = 0
    for m, md in P[v]["modules"].items():
        run = md["runs"][k]
        for x in run["listed"]:
            key = (x["entity"], x["element"])
            hit = any(key in CH[c][m] for c in checks if c != "R1") or ("R1" in checks and r1(m, *key))
            if hit:
                n_tp = sum(1 for val in run["tp"].values() if val == x["element"])
                if n_tp: dtp += n_tp
                else: dfp += 1
    L2 = L - dfp - (dtp and dtp)  # a dropped TP element also leaves the listed set
    return T - dtp, L - dfp - sum(0 for _ in ()) - (0), dfp, dtp

def prec(v, k, checks):
    t = P[v]["totals"][k]; L, T = t["listed"], t["tp"]
    dfp = 0; dtp_el = 0; dtp = 0
    for m, md in P[v]["modules"].items():
        run = md["runs"][k]
        for x in run["listed"]:
            key = (x["entity"], x["element"])
            hit = any(key in CH[c][m] for c in checks if c != "R1") or ("R1" in checks and r1(m, *key))
            if hit:
                n_tp = sum(1 for val in run["tp"].values() if val == x["element"])
                if n_tp: dtp += n_tp; dtp_el += 1
                else: dfp += 1
    return (T - dtp), (L - dfp - dtp_el), dfp, dtp

want = {("v5", "R1"): (0.370, 0.386, 0.407), ("v5", "R8"): (0.384, 0.391, 0.424), ("v5", "U2"): (0.396, 0.393, 0.426),
        ("v5", "U6"): (0.391, 0.415, 0.408), ("v5", "U10"): (0.374, 0.377, 0.410),
        ("v4a", "R1"): (0.324, 0.327, 0.329), ("v4a", "R8"): (0.302, 0.294, 0.331), ("v4a", "U6"): (0.307, 0.295, 0.344)}
ok = True
for (v, c), w in want.items():
    got = []
    for k in RUNS:
        T2, L2, dfp, dtp = prec(v, k, [c]); got.append(round(T2 / L2, 3))
        if dtp: ok = False; print("TP lost", v, c, k, dtp)
    good = tuple(got) == w
    ok &= good
    print(f"self-test {v} {c}: {tuple(got)} want {w} {'PASS' if good else 'FAIL'}")
print("SELF-TEST", "PASS" if ok else "FAIL")
if not ok: sys.exit(1)
ALL = ["R1", "R8", "U2", "U6", "U10"]
NF = P["v5"]["entries"] - P["v5"]["absent"]
for v in V:
    for c in (["U2", "U10"] if v == "v4a" else []):
        print(v, c, [f"{prec(v,k,[c])[0]}/{prec(v,k,[c])[1]}={prec(v,k,[c])[0]/prec(v,k,[c])[1]:.3f} (fp-{prec(v,k,[c])[2]}, tp-{prec(v,k,[c])[3]})" for k in RUNS])
    row = []
    for k in RUNS:
        T2, L2, dfp, dtp = prec(v, k, ALL)
        t = P[v]["totals"][k]
        row.append(f"{k}: P {t['tp']}/{t['listed']}={t['tp']/t['listed']:.3f} -> {T2}/{L2}={T2/L2:.3f} (FP dropped {dfp}, TP lost {dtp}); R {T2/NF:.3f}")
    print(v, "ALL FIVE:", " | ".join(row))
print("modules where each check fires:", {c: sorted(m for m in MODS if CH[c][m]) for c in CH})
