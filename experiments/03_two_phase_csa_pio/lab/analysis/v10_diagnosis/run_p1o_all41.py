"""All-41 run of the working version two_phase_p1o_first (user, 2026-10-19: "run this for all 41 modules & include the
result in the readme. I have openai budget"). The 26 held-out modules have r0-r2 already (D102). This sends the 15 tuning
modules, r0-r2: gpt-5.6-luna, high, chain.run_many, at most 8 requests at a time, poll timeout 1800 s per request.
Cost estimate before the send: v9j's tuning run cost USD 0.72 (r0 and r1 each); p1o_first's held-out r0 cost USD 1.22 for
26 modules; so about USD 0.75 per run, USD 2.2 to 2.5 for three.

Readings, set before the send (exact scorer, compare_v8.score; findable 109 per run on the tuning 15, 187 on the held-out
26, 296 on all 41). The comparison is two_phase_v9j, the last version measured on all 41: tuning r0-r2 93/130, 94/145,
96/131 (pooled P 0.697, R 0.865); held-out pooled 0.569 / 0.848; all 41 pooled 0.611 / 0.855. LAsset's RTL-only initial
list under the same scorer: tuning 0.672 / 0.752, held-out 0.724 / 0.759, all 41 0.704 / 0.757.
  R1  tuning 15, per run and pooled P / R.
  R2  all 41, pooled P / R: the new tuning runs with the stored held-out r0-r2.
  R3  transfer of the held-out gain. On the held-out 26, p1o_first is +0.120 precision over v9j at -0.010 recall. The gain
      transfers if tuning pooled precision is above v9j's 0.697 with pooled recall not below v9j's lowest tuning run
      (93/109 = 0.853). It does not transfer if tuning pooled precision is below v9j's lowest tuning run (94/145 = 0.648).
      Anything between is inside noise and is reported as such.
  R4  cost: USD from the stored usage records at the list prices (cost_estimate.usd).

  python -B run_p1o_all41.py preview        what is on disk, nothing sent
  <conda python> -B run_p1o_all41.py run    sends (needs API.env)
  python -B run_p1o_all41.py measure        R1-R4 (writes read_p1o_all41.json beside this file)
"""
import json
import os
import sys
from collections import Counter

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402

sys.path.insert(0, str(LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2"))
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402
import compare_v8 as C8  # noqa: E402
import cost_estimate as CE  # noqa: E402

V, V9J = "two_phase_p1o_first", "two_phase_v9j"
REPS = (0, 1, 2)
V9J_TUNING = [(93, 130), (94, 145), (96, 131)]


def on_disk(v, r, mods):
    return [m for m in mods if (CH.run_dir(v, MODEL, r, EFFORT) / "assets" / f"{m}.json").exists()]


def score(v, r, mods, ref):
    """(correct, listed) over mods for run r, or None if a module's assets file is missing."""
    T = L = 0
    for m in mods:
        f = CH.run_dir(v, MODEL, r, EFFORT) / "assets" / f"{m}.json"
        if not f.exists():
            return None
        names = [x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]]
        listed = Counter(names)
        for n in ref[m]:
            if listed[n] > 0:
                listed[n] -= 1
                T += 1
        L += len(names)
    return T, L


def cost(v, r, mods):
    usd = 0.0
    for m in mods:
        for ph in (1, 2):
            f = CH.run_dir(v, MODEL, r, EFFORT) / f"phase{ph}" / f"{m}.json"
            if f.exists():
                usd += CE.usd(json.loads(f.read_text(encoding="utf-8"))["usage"], MODEL)
    return usd


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preview"
    g = K.gt_modules()
    tuning, held = list(g["tuning"]), list(g["heldout"])
    if cmd == "preview":
        for r in REPS:
            print(f"r{r}: tuning {len(on_disk(V, r, tuning))} of {len(tuning)} on disk; held-out {len(on_disk(V, r, held))} of {len(held)}")
        return 0
    if cmd == "run":
        todo = {r: [m for m in tuning if m not in on_disk(V, r, tuning)] for r in REPS}
        print({f"r{r}": len(ms) for r, ms in todo.items()}, "tuning modules to send")
        rows = CH.run_many([(V, r) for r in REPS], tuning, lambda out: CH.openai(MODEL, EFFORT, out=out, timeout=1800),
                           MODEL, EFFORT, workers=8)
        for k, v in rows.items():
            print(k, len(v), "rows")
        for r in REPS:
            print(f"r{r}: tuning {len(on_disk(V, r, tuning))} of {len(tuning)} on disk after the run")
        return 0
    if cmd == "measure":
        ref = C8.refs(sorted(set(tuning) | set(held)))
        ok = C8.selftest(ref)
        print("scorer self-test (v7 92/89/86 of 146/158/131):", "PASS" if ok else "FAIL")
        if not ok:
            return 1
        Ft, Fh = sum(len(ref[m]) for m in tuning), sum(len(ref[m]) for m in held)
        out = {"version": V, "findable": {"tuning": Ft, "heldout": Fh, "all41": Ft + Fh}, "runs": {}}
        tT = tL = hT = hL = 0
        complete = True
        for r in REPS:
            st, sh = score(V, r, tuning, ref), score(V, r, held, ref)
            row = {"tuning": st, "heldout": sh, "cost_tuning_usd": round(cost(V, r, tuning), 2)}
            if st and sh:
                row["all41"] = (st[0] + sh[0], st[1] + sh[1])
                tT += st[0]; tL += st[1]; hT += sh[0]; hL += sh[1]
            else:
                complete = False
            out["runs"][f"r{r}"] = row
            print(f"r{r}: tuning {st}  held-out {sh}  all41 {row.get('all41')}  tuning cost USD {row['cost_tuning_usd']}")
        if not complete:
            print("not every run is complete: nothing pooled")
            return 1
        P_t, R_t = tT / tL, tT / (3 * Ft)
        P_a, R_a = (tT + hT) / (tL + hL), (tT + hT) / (3 * (Ft + Fh))
        out["R1 tuning pooled"] = {"correct": tT, "listed": tL, "P": round(P_t, 3), "R": round(R_t, 3)}
        out["R2 all41 pooled"] = {"correct": tT + hT, "listed": tL + hL, "P": round(P_a, 3), "R": round(R_a, 3)}
        v9j_P = sum(c for c, l in V9J_TUNING) / sum(l for c, l in V9J_TUNING)
        v9j_low_R, v9j_low_P = 93 / Ft, 94 / 145
        if P_t > v9j_P and R_t >= v9j_low_R:
            r3 = "transfers: tuning precision above v9j's 0.697 with recall not below v9j's lowest run"
        elif P_t < v9j_low_P:
            r3 = "does not transfer: tuning precision below v9j's lowest run (0.648)"
        else:
            r3 = "inside noise: between the two cuts"
        out["R3 transfer"] = r3
        out["R4 cost tuning runs USD"] = round(sum(out["runs"][f"r{r}"]["cost_tuning_usd"] for r in REPS), 2)
        print("R1 tuning pooled:", out["R1 tuning pooled"])
        print("R2 all 41 pooled:", out["R2 all41 pooled"])
        print("R3:", r3)
        print("R4 cost of the three tuning runs: USD", out["R4 cost tuning runs USD"])
        (HERE / "read_p1o_all41.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
