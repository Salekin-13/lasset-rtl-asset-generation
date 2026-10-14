"""Merge the checkers' verdicts (workflow heldout-prompt-diagnosis-verify) with the claims; code decides each claim's
status. Read-only on everything but its outputs: verify/verdicts_raw.json (the workflow's return value, saved before),
writes verify/merged.json and prints a summary.

Status per claim (two checkers: lens A evidence and scope, lens B causal skeptic):
  kept        neither checker says "refuted" (corrections, if any, are attached and must be applied in the write-up)
  contested   exactly one checker says "refuted"
  refuted     both say "refuted"
  one check   only one checker returned a verdict for it (its verdict is attached; never counted as kept)
  not checked no verdict
Self-test: every verdict's claim_id is a check id of the unit its checker had (else listed as stray, not used); a
checker giving two verdicts for one claim is flagged and only its first verdict is used.

  python merge_verdicts.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
V = HERE / "verify"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    idx = json.loads((V / "units.json").read_text(encoding="utf-8"))
    raw = json.loads((V / "verdicts_raw.json").read_text(encoding="utf-8"))
    unit_ids = {u["unit"]: set(u["check ids"]) for u in idx}
    got = defaultdict(dict)              # check id -> lens -> verdict
    stray, dup = [], []
    for r in raw["results"]:
        seen = set()
        for v in r["verdicts"]:
            cid = (v.get("claim_id") or "").split(" ")[0].strip()
            if cid not in unit_ids.get(r["unit"], set()):
                stray.append((r["unit"], r["lens"], v.get("claim_id")))
                continue
            if cid in seen:
                dup.append((r["unit"], r["lens"], cid))
                continue
            seen.add(cid)
            got[cid][r["lens"]] = v
    merged, status = [], Counter()
    for u in idx:
        d = json.loads((V / "units" / f"{u['unit']}.json").read_text(encoding="utf-8"))
        for it in d["items"]:
            cid = it["check id"]
            vs = got.get(cid, {})
            ref = [l for l, v in vs.items() if v["verdict"] == "refuted"]
            if len(vs) == 2:
                st = "kept" if not ref else ("contested" if len(ref) == 1 else "refuted")
            elif len(vs) == 1:
                st = "one check"
            else:
                st = "not checked"
            status[st] += 1
            merged.append({"check id": cid, "unit": u["unit"], "topic": u["topic"], "status": st, "analyst": it["analyst"],
                           "claim": it["claim"], "code check": it["code check"], "verdicts": vs})
    (V / "merged.json").write_text(json.dumps(merged, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"claims {len(merged)}: {dict(status)}")
    print(f"self-test: stray verdicts {len(stray)} {stray[:5]}; duplicate verdicts {len(dup)} {dup[:5]}; not checked "
          f"{raw.get('not_checked')}")
    by = defaultdict(Counter)
    for m in merged:
        by[m["claim"]["effect"]][m["status"]] += 1
    for e, c in by.items():
        print(f"  {e:18s} {dict(c)}")
    corr = sum(1 for m in merged for v in m["verdicts"].values() if v["verdict"] == "supported with correction")
    print(f"verdicts 'supported with correction': {corr}")


if __name__ == "__main__":
    main()
