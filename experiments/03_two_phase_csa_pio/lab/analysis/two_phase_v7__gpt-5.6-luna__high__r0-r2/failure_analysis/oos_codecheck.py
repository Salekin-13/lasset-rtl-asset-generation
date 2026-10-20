"""Out-of-sample check of the four code-check filters (rules/P1-P4/check.py), written by drafters who saw v7's false
positives: run them on OTHER stored outputs of the same 15 modules (v6d r0-r2, v6 r0-r2, v5f r0-r2, v5f r3-r5), which
the drafters did not target, and score what they drop with the exact scorer of compare_condensed (names equal, each
reference entry used once). Same modules, so this is a weak out-of-sample test; the 26 held-out modules are the real one.

How: the replies of each run set are copied byte for byte from each record's "raw" field into oos_raw/<set>/r<k>/phase2/;
each check.py is copied next to itself as check_oos.py with only its replies folder made settable (RAW_DIR); the copies
are run; the originals are not touched.
Self-test: on the v7 replies (a copy of raw/ through the same path) the copies drop exactly what the originals dropped
(rules/<P>/check_out.json).

  python oos_codecheck.py
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import common_fa as F

CH = F.CH
SETS = {"v7": ("two_phase_v7", (0, 1, 2)), "v6d": ("two_phase_v6d", (0, 1, 2)), "v6": ("two_phase_v6", (0, 1, 2)),
        "v5f_a": ("two_phase_v5f", (0, 1, 2)), "v5f_b": ("two_phase_v5f", (3, 4, 5))}
OOS = F.HERE / "oos_raw"


def prepare(name, version, reps):
    for k, r in enumerate(reps):
        for m in F.MODS:
            for ph in (1, 2):
                rec = json.loads((CH.run_dir(version, F.MODEL, r, F.EFF) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))
                p = OOS / name / f"r{k}" / f"phase{ph}" / f"{m}.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="") as f:
                    f.write(rec["raw"])


def make_copy(fx):
    src = (F.HERE / "rules" / fx / "check.py").read_text(encoding="utf-8")
    new, n = re.subn(r'^RAW = FA / "raw"\s*$', 'RAW = __import__("pathlib").Path(__import__("os").environ["RAW_DIR"])', src, flags=re.M)
    assert n == 1, f"{fx}: RAW line not found once ({n})"
    p = F.HERE / "rules" / fx / "check_oos.py"
    p.write_text(new, encoding="utf-8")
    return p


def run(fx, script, name):
    out = F.HERE / "rules" / fx / f"oos_{name}.json"
    env = dict(os.environ, RAW_DIR=str(OOS / name))
    args = [sys.executable, "-I", str(script), str(out)]
    if fx in ("P1", "P3"):
        args += ["--raw", str(OOS / name)]
    pr = subprocess.run(args, cwd=str(script.parent), env=env, capture_output=True, text=True, timeout=900)
    if pr.returncode != 0 or not out.exists():
        raise RuntimeError(f"{fx} on {name}: exit {pr.returncode}: {pr.stderr[-500:]}")
    return json.loads(out.read_text(encoding="utf-8"))


def score(version, reps, drops):
    res = {}
    for k, r in enumerate(reps):
        C = L = lost = fpr = 0
        lost_names = []
        for m in F.MODS:
            s = F.short(m)
            a = json.loads((CH.run_dir(version, F.MODEL, r, F.EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]
            d = {(x.get("entity"), x.get("element")) for x in (drops.get(f"r{k}", {}).get(s, []) or [])}
            keep = [x for x in a if (x["Entity"], x["Asset RTL"]) not in d]
            ref = [n for (_k, n, _kk, _h) in F.ref_entries(m)]

            def corr(rows):
                cnt, got = Counter(x["Asset RTL"] for x in rows), []
                for n in ref:
                    if cnt[n] > 0:
                        cnt[n] -= 1
                        got.append(n)
                return got
            g0, g1 = corr(a), corr(keep)
            lost_names += [f"{s}:{n}" for n in (Counter(g0) - Counter(g1)).elements()]
            fpr += (len(a) - len(keep)) - (len(g0) - len(g1))
            C, L = C + len(g1), L + len(keep)
        res[f"r{r}"] = {"correct": C, "listed": L, "correct lost": lost_names, "false positives removed": fpr}
    return res


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    scripts = {fx: make_copy(fx) for fx in ("P1", "P2", "P3", "P4")}
    for name, (v, reps) in SETS.items():
        prepare(name, v, reps)
    # self-test: the copies on v7 drop exactly what the originals dropped
    ok = True
    for fx, sc in scripts.items():
        a = run(fx, sc, "v7")
        b = json.loads((F.HERE / "rules" / fx / "check_out.json").read_text(encoding="utf-8"))
        norm = lambda o: sorted((r, m, x.get("entity"), x.get("element")) for r, mods in o.items() for m, rows in (mods or {}).items() for x in rows)
        same = norm(a) == norm(b)
        ok &= same
        print(f"self-test {fx}: copy on v7 = original output: {same} ({len(norm(a))} rows)")
    if not ok:
        sys.exit("self-test failed: nothing reported")
    out = {}
    for name, (v, reps) in SETS.items():
        union = {}
        per = {}
        for fx, sc in scripts.items():
            o = run(fx, sc, name)
            per[fx] = score(v, reps, o)
            for r, mods in o.items():
                for m, rows in (mods or {}).items():
                    for x in rows:
                        union.setdefault(r, {}).setdefault(m, {})[(x.get("entity"), x.get("element"))] = x
        drops = {r: {m: list(d.values()) for m, d in mods.items()} for r, mods in union.items()}
        allsc = score(v, reps, drops)
        base = score(v, reps, {})
        out[name] = {"per check": per, "all four": allsc, "base": base}
        T0 = sum(x["correct"] for x in base.values()); L0 = sum(x["listed"] for x in base.values())
        T1 = sum(x["correct"] for x in allsc.values()); L1 = sum(x["listed"] for x in allsc.values())
        lost = [n for x in allsc.values() for n in x["correct lost"]]
        print(f"\n{name} ({v} runs {reps}): pooled precision {T0}/{L0} = {T0 / L0:.3f} -> {T1}/{L1} = {T1 / L1:.3f}; "
              f"recall {T0}/{109 * len(reps)} -> {T1}/{109 * len(reps)}; correct finds lost {len(lost)} {lost}")
        for fx in scripts:
            p = per[fx]
            print(f"   {fx}: FP removed {sum(x['false positives removed'] for x in p.values())}, correct lost "
                  f"{sum(len(x['correct lost']) for x in p.values())} {[n for x in p.values() for n in x['correct lost']]}")
    (F.HERE / "rules" / "oos_codecheck.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
