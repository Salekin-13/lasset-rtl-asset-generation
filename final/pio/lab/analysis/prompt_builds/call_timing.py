"""Where the time goes in a notebook run: per-call durations of past gpt-5.6-luna runs, read from OpenAI (read-only
responses.retrieve of stored response ids; no model call is made) and from file times.

For each stored reply (runs/<version>__v1/gpt-5.6-luna__high/r<k>/phase<p>/<module>.json): response id -> created_at and
completed_at (if the API returns it); the reply file's modification time is a fallback end time (it lags completion by at
most one poll interval). Also reports the status of any request still in _pending. Prints per-run makespan, the slowest
module chains, and per-module typical call times. Writes call_timing.json.

  python call_timing.py
"""
import json
import os
import statistics as st
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
RUNS = [("two_phase_v1", k) for k in (0, 1, 2)] + [("two_phase_v2", k) for k in (0, 1, 2)] + [("two_phase_v2a", 0)]


def key():
    if os.environ.get("OPENAI_API_KEY"):
        return
    root = LAB.parents[2]
    for env in (root / "API.env", root.parents[2] / "API.env", LAB.parents[1] / "API.env"):
        if env.exists():
            for l in env.read_text(encoding="utf-8").splitlines():
                if l.strip().startswith("OPENAI_API_KEY"):
                    os.environ["OPENAI_API_KEY"] = l.split("=", 1)[1].strip().strip('"')
                    return


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    key()
    from openai import OpenAI
    cli = OpenAI().with_options(timeout=60, max_retries=3)
    calls = []
    for v, k in RUNS:
        d = LAB / "runs" / f"{v}__v1" / "gpt-5.6-luna__high" / f"r{k}"
        for ph in (1, 2):
            for f in sorted((d / f"phase{ph}").glob("*.json")):
                rec = json.loads(f.read_text(encoding="utf-8"))
                calls.append({"run": f"{v} r{k}", "module": f.stem.replace("neorv32_", ""), "phase": ph, "id": rec["usage"].get("response id"),
                              "out": rec["usage"].get("out"), "reasoning": rec["usage"].get("reasoning"), "in": rec["usage"].get("in"),
                              "cached": rec["usage"].get("cached"), "file_mtime": f.stat().st_mtime})
        for p in (d / "_pending").glob("*.json") if (d / "_pending").exists() else []:
            calls.append({"run": f"{v} r{k}", "module": "?", "phase": 0, "id": json.loads(p.read_text(encoding="utf-8"))["id"], "pending": True})

    def get(c):
        if not c["id"]:
            return c
        try:
            r = cli.responses.retrieve(c["id"])
            c["created_at"] = getattr(r, "created_at", None)
            c["completed_at"] = getattr(r, "completed_at", None)
            c["status"] = r.status
            c["service_tier"] = getattr(r, "service_tier", None)
        except Exception as e:  # noqa: BLE001
            c["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        return c

    with ThreadPoolExecutor(16) as ex:
        calls = list(ex.map(get, calls))
    for c in calls:
        end = c.get("completed_at") or c.get("file_mtime")
        if c.get("created_at") and end and not c.get("pending"):
            c["seconds"] = end - c["created_at"]
    errs = [c for c in calls if c.get("error")]
    print(f"calls {len(calls)}; retrieved {sum(1 for c in calls if c.get('created_at'))}; errors {len(errs)} {errs[:2]}")
    print("completed_at available:", sum(1 for c in calls if c.get("completed_at")), "| service tiers:", {c.get("service_tier") for c in calls})
    for c in calls:
        if c.get("pending"):
            import time
            print(f"PENDING {c['run']} {c['id'][:20]}...: status {c.get('status')}, waiting {(time.time() - c['created_at']) / 60:.1f} min")
    # per run: makespan (first created to last completed) and module chains
    by = defaultdict(list)
    for c in calls:
        if "seconds" in c:
            by[c["run"]].append(c)
    print("\nrun            makespan  slowest module chains (phase1+phase2 seconds)")
    chains_all = defaultdict(list)
    for run, cs in by.items():
        t0 = min(c["created_at"] for c in cs)
        t1 = max((c.get("completed_at") or c["file_mtime"]) for c in cs)
        ch = defaultdict(float)
        for c in cs:
            ch[c["module"]] += c["seconds"]
        for m, s in ch.items():
            chains_all[m].append(s)
        top = sorted(ch.items(), key=lambda x: -x[1])[:4]
        print(f"{run:15s} {(t1 - t0) / 60:6.1f} min  " + ", ".join(f"{m} {s / 60:.1f}" for m, s in top))
    print("\nper module, minutes per call (median over runs): phase 1 | phase 2 | chain; output tokens per second (median)")
    per = defaultdict(lambda: defaultdict(list))
    for cs in by.values():
        for c in cs:
            per[c["module"]][c["phase"]].append(c["seconds"] / 60)
            if c.get("out") and c["seconds"] > 0:
                per[c["module"]]["tps"].append(c["out"] / c["seconds"])
    for m in sorted(per, key=lambda m: -st.median(chains_all[m])):
        print(f"  {m:14s} {st.median(per[m][1]):5.1f} | {st.median(per[m][2]):5.1f} | {st.median(chains_all[m]) / 60:5.1f}  max chain {max(chains_all[m]) / 60:5.1f} | {st.median(per[m]['tps']):.0f} tok/s")
    allp = [c["seconds"] / 60 for cs in by.values() for c in cs]
    print(f"\nall calls: median {st.median(allp):.1f} min, max {max(allp):.1f} min, n {len(allp)}")
    json.dump(calls, open(Path(__file__).with_name("call_timing.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
