"""Checks for the critic issues. Reads stored replies only. Run with python -I."""
import json, os, re, sys
LAB = r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab"
M = "gpt-5.6-luna__high"
VERS = ["v1", "v2", "v2a", "v3", "v4", "v4a", "v5"]

def p2(ver, r, mod):
    f = os.path.join(LAB, "runs", f"two_phase_{ver}__v1", M, f"r{r}", "phase2", f"neorv32_{mod}.json")
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else None

def p1(ver, r, mod):
    f = os.path.join(LAB, "runs", f"two_phase_{ver}__v1", M, f"r{r}", "phase1", f"neorv32_{mod}.json")
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else None

def assets(ver, r, mod):
    f = os.path.join(LAB, "runs", f"two_phase_{ver}__v1", M, f"r{r}", "assets", f"neorv32_{mod}.json")
    if not os.path.exists(f):
        return None
    d = json.load(open(f, encoding="utf-8"))
    out = {}
    for a in d.get("Assets", []):
        out.setdefault(a["Asset RTL"], set()).update(a.get("Concepts", []))
    return out

def rows(ver, r, mod):
    d = p2(ver, r, mod)
    if not d:
        return []
    rep = d["reply"]
    return rep.get("structural assets", []) if isinstance(rep, dict) else []

# ---------- self-test against hand-read facts from the evidence ----------
st = []
a = assets("v5", 0, "cache"); st.append(("v5 r0 cache we_i not primary", "we_i" not in a))
a = assets("v4a", 0, "cache"); st.append(("v4a r0 cache we_i primary", "we_i" in a))
a = assets("v4a", 1, "cache"); st.append(("v4a r1 cache host_req_i.rw primary, we_i not", "host_req_i.rw" in a and "we_i" not in a))
a = assets("v5", 1, "cache"); st.append(("v5 r1 cache host_req_i.ben primary", "host_req_i.ben" in a))
a = assets("v5", 0, "cpu"); st.append(("v5 r0 cpu xcsr_alu primary under C12", "C12" in a.get("xcsr_alu", set())))
a = assets("v5", 2, "trng"); st.append(("v5 r2 trng fifo.we primary under C6", "C6" in a.get("fifo.we", set())))
ok = all(x[1] for x in st)
for n, v in st:
    print(("PASS " if v else "FAIL ") + n)
print("SELF-TEST", "PASS" if ok else "FAIL")
if not ok:
    sys.exit(1)

# ---------- issue 2: we_i vs host_req_i.ben/.rw co-primary ----------
print("\n== issue 2: cache we_i vs host_req_i.ben/.rw primary ==")
g1 = [0, 0]; g2 = [0, 0]
for v in VERS:
    for r in range(3):
        a = assets(v, r, "cache")
        if a is None:
            print(v, r, "missing"); continue
        hb = ("host_req_i.ben" in a) or ("host_req_i.rw" in a)
        we = "we_i" in a
        g = g1 if hb else g2
        g[0] += we; g[1] += 1
        print(f"  {v} r{r} ben/rw primary={hb} we_i primary={we}")
print(f"  we_i primary where ben/rw primary: {g1[0]} of {g1[1]}; where not: {g2[0]} of {g2[1]}")

# ---------- issue 4: xcsr_* primary rows, with concepts ----------
print("\n== issue 4: cpu xcsr_* primaries (assets) ==")
for v in ["v4", "v4a", "v5"]:
    for r in range(3):
        a = assets(v, r, "cpu")
        hits = {k: sorted(c) for k, c in a.items() if k.startswith("xcsr_")}
        # which concept holds csr_rdata instance-output line 263?
        d1 = p1(v, r, "cpu")
        rb = []
        if d1:
            for c in d1["reply"].get("conceptual assets", []):
                held = c.get("held lines") or c.get("held") or []
                if 263 in held:
                    rb.append(c.get("id"))
        print(f"  {v} r{r} xcsr primaries {hits}  concepts holding 263: {rb}")

# ---------- issue 5: muldiv ctrl_i.ir_* primaries ----------
print("\n== issue 5: muldiv ctrl_i.ir_* primaries ==")
for v in ["v4a", "v5"]:
    for r in range(3):
        a = assets(v, r, "cpu_cp_muldiv")
        print(f"  {v} r{r}", {k: sorted(c) for k, c in a.items() if k.startswith("ctrl_i.")})

# ---------- issue 8: 'has no links' warnings ----------
print("\n== issue 8: 'secondary ... has no links' warnings in Phase 2 problems ==")
mods = [f[len("neorv32_"):-5] for f in os.listdir(os.path.join(LAB, "runs", "two_phase_v5__v1", M, "r0", "phase2")) if f.endswith(".json")]
for v in ["v4", "v4a", "v5"]:
    tot = 0; per = {}
    for r in range(3):
        for m in mods:
            d = p2(v, r, m)
            if not d: continue
            n = sum(1 for x in (d.get("problems") or []) if re.search(r"secondary '.*' has no links", x))
            if n:
                per[f"r{r} {m}"] = n; tot += n
    print(f"  {v}: total {tot}  {per}")

# ---------- issue 24: trng fifo.we primary vs held lines 138/162 ----------
print("\n== issue 24: trng fifo.we label in concepts, held lines ==")
for v in ["v4", "v4a", "v5"]:
    for r in range(3):
        d1 = p1(v, r, "trng")
        held = {}
        for c in d1["reply"].get("conceptual assets", []):
            held[c.get("id")] = c.get("held lines") or []
        for row in rows(v, r, "trng"):
            if row.get("element") == "fifo.we":
                cid = row.get("concept id")
                h = held.get(cid, [])
                print(f"  {v} r{r} {cid} label={row.get('label')} holds138={138 in h} holds162={162 in h} holds367={367 in h}")
        # valid_o labels in the same concepts
        for row in rows(v, r, "trng"):
            if row.get("element") == "valid_o":
                print(f"     valid_o {row.get('concept id')} label={row.get('label')}")
