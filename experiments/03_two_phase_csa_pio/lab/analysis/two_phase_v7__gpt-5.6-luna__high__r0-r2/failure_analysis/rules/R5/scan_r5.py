"""R5 measurement scan (revised fix). Measurement only: it reads the reference through common_fa to say which rows are
reference elements; it is not a code check.

Shapes of the revised R5 wording:
  (i)  a non-record unit input port that one statement reduces to one bit (or_/and_/xor_reduce_f of the whole port)
       into a signal whose closed-set "gets value from" partners are that port only (LS1 extension);
  (ii) a non-record output port, of any entity, whose only assignment is one plain copy '<port> <= <name>;' of a
       whole element (no index or slice).
For each run and each concept walk where the linked element (the reduced signal for (i), the copied element for
(ii)) is labelled primary, it reports the port row's label, whether the port is a reference element, and whether the
run already lists it. It also prints, for (i), whether the row's text says 'reduc' (falsifier item).

Usage:
  python scan_r5.py                         # the stored v7 replies (raw/r0..r2), self-test on hand-read v7 lines
  python scan_r5.py --raw <folder> [--expect r0:neorv32_sys:C1:enable_i:primary ...]
      <folder> holds r<k>/phase1/<module>.json and r<k>/phase2/<module>.json (raw reply text); for a new run, give
      at least two hand-read rows with --expect, or the run-specific self-test is reported as NOT RUN.
Re-score (listed and correct if every qualifying secondary row were primary) is computed only for the v7 replies,
whose baseline is common_fa.score_run.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

FA = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FA))
import common_fa as F  # noqa: E402

INP = F.INPUTS
V7RAW = FA / "raw"


def cs(m):
    return json.loads((INP / m / "closed_set.json").read_text(encoding="utf-8"))


def rtl(m):
    d = {}
    for l in (INP / m / "rtl.txt").read_text(encoding="utf-8").splitlines():
        mm = re.match(r"\s*(\d+) \| (.*)$", l)
        if mm:
            d[int(mm.group(1))] = mm.group(2)
    return d


def units(m):
    return [l.split()[1] for l in (INP / m / "diagram.txt").read_text(encoding="utf-8").splitlines() if l.startswith("UNIT ")]


def raw(folder, r, m, ph):
    t = (folder / r / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8")
    try:
        return json.loads(t)
    except Exception:
        return F.K.parse_json(t)


def walks(folder, r, m):
    return [(w["Concept ID"], w) for w in raw(folder, r, m, 2).get("Concept Walks", [])]


def rows(w, name):
    return [a for a in w.get("Assets", []) if a.get("Asset RTL") == name]


# ---------------------------------------------------------------- shape (ii)
def copy_out_ports(m):
    R = rtl(m)
    out = []
    for e in cs(m)["entity list"]:
        for p in e.get("port list", []):
            if p["direction"] != "out" or p.get("record type"):
                continue
            name = p["port"]
            asg = [ln for ln in p["occurrence lines"] if re.match(rf"\s*{re.escape(name)}\s*<=", R.get(ln, ""))]
            if len(asg) != 1:
                continue
            mm = re.match(rf"\s*{re.escape(name)}\s*<=\s*([A-Za-z_][\w\.]*)\s*;\s*$", R[asg[0]])
            if mm:
                out.append((e["entity name"], name, mm.group(1), asg[0]))
    return out


# ---------------------------------------------------------------- shape (i)
def reduced_in_ports(m):
    R = rtl(m)
    U = set(units(m))
    out = []
    for e in cs(m)["entity list"]:
        if e["entity name"] not in U:
            continue
        sigs = {s["signal"]: s for s in e.get("signal list", [])}
        for p in e.get("port list", []):
            if p["direction"] != "in" or p.get("record type"):
                continue
            name = p["port"]
            for ln in p["occurrence lines"]:
                mm = re.match(rf"\s*([A-Za-z_]\w*)\s*<=\s*(?:or|and|xor)_reduce_f\(\s*{re.escape(name)}\s*\)\s*;\s*$", R.get(ln, ""))
                if not mm or mm.group(1) not in sigs:
                    continue
                gv = {x["element"] for x in sigs[mm.group(1)].get("counterparts", {}).get("gets value from", [])}
                if gv == {name}:
                    out.append((e["entity name"], name, mm.group(1), ln))
    return out


def selftest(folder, expects):
    ok = True
    A = {(m, x[1]): x for m in F.MODS for x in copy_out_ports(m)}
    ok &= A.get(("neorv32_uart", "clkgen_en_o"), (None,) * 4)[2:] == ("ctrl.enable", 228)   # rtl.txt:172
    ok &= A.get(("neorv32_trng", "data_o"), (None,) * 4)[2:] == ("sample_sreg", 366)        # rtl.txt:228
    ok &= ("neorv32_trng", "valid_o") not in A                                                # RTL 367, one bit
    B = [(m, x) for m in F.MODS for x in reduced_in_ports(m)]
    ok &= B == [("neorv32_sys", ("neorv32_sys_clock", "enable_i", "en", 129))]               # rtl.txt:75; RTL 276 mixed
    run_ok = None
    if folder.resolve() == V7RAW.resolve():
        w0 = dict(walks(folder, "r0", "neorv32_sys"))
        run_ok = [a["Label"] for a in rows(w0["C1"], "enable_i")] == ["secondary"]          # raw/r0/phase2/neorv32_sys.json:51
        w2 = dict(walks(folder, "r2", "neorv32_uart"))
        run_ok &= [a["Label"] for a in rows(w2["C3"], "clkgen_en_o")] == ["secondary"]      # raw/r2/phase2/neorv32_uart.json:1034
        w0t = dict(walks(folder, "r0", "neorv32_trng"))
        run_ok &= [a["Label"] for a in rows(w0t["C1"], "data_o")] == ["secondary"]          # raw/r0/phase2/neorv32_trng.json:125
    elif len(expects) >= 2:
        run_ok = True
        for x in expects:
            r, m, c, el, lab = x.split(":")
            run_ok &= [a["Label"] for a in rows(dict(walks(folder, r, m))[c], el)] == [lab]
    return ok, run_ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(V7RAW))
    ap.add_argument("--expect", action="append", default=[])
    a = ap.parse_args()
    folder = Path(a.raw)
    ok, run_ok = selftest(folder, a.expect)
    print("SELFTEST inputs", "PASS" if ok else "FAIL", "| run lines", {None: "NOT RUN", True: "PASS", False: "FAIL"}[run_ok])
    if not ok or run_ok is False:
        print("self-test failed: nothing reported")
        return
    runs = sorted(p.name for p in folder.iterdir() if re.fullmatch(r"r\d+", p.name))
    is_v7 = folder.resolve() == V7RAW.resolve()
    flips = {r: set() for r in runs}
    for shape, fn in (("i", reduced_in_ports), ("ii", copy_out_ports)):
        print(f"\n== shape ({shape})")
        cnt = Counter()
        for m in F.MODS:
            refn = Counter(n for (_k, n, _kk, _h) in F.ref_entries(m))
            for ent, port, src, ln in fn(m):
                for r in runs:
                    for cid, w in walks(folder, r, m):
                        if not any(x["Label"] == "primary" for x in rows(w, src)):
                            continue
                        pr = rows(w, port)
                        lab = pr[0]["Label"] if pr else "no row"
                        cnt[(lab, "ref" if port in refn else "notref")] += 1
                        say = (" says 'reduc'" if "reduc" in json.dumps(pr, ensure_ascii=False).lower() else "") if shape == "i" else ""
                        print(f"   {r} {F.short(m)} {cid} {port} (RTL {ln}, from {src} primary): {lab}; ref={port in refn}{say}")
                        if lab == "secondary":
                            flips[r].add((m, port))
        print("  counts (label, ref):", dict(cnt))
    if not is_v7:
        return
    print("\n== re-score of the v7 replies if every qualifying secondary row were primary (names only, as the scorer)")
    for r in runs:
        k = int(r[1:])
        s = F.score_run(k)
        L = sum(s[m][0] for m in F.MODS)
        C = sum(s[m][1] for m in F.MODS)
        dl = dc = 0
        for m, port in sorted(flips[r]):
            listed_names = {n.split(":", 1)[1] for n in s[m][3]}
            if port in listed_names:
                continue
            dl += 1
            nref = sum(1 for (_k, n, _kk, _h) in F.ref_entries(m) if n == port)
            nfound = sum(1 for key in s[m][2] if key.split(":", 1)[1].split("#")[0] == port)
            if nref > nfound:
                dc += 1
        print(f"   {r}: P {C}/{L} = {C/L:.3f} -> {(C+dc)}/{(L+dl)} = {(C+dc)/(L+dl):.3f};"
              f" R {C}/109 = {C/109:.3f} -> {(C+dc)}/109 = {(C+dc)/109:.3f}; flips {sorted(p for _m, p in flips[r])}")


if __name__ == "__main__":
    main()
