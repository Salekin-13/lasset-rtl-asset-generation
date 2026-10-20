"""Tally of the readers' verdicts on the one-sided differences (onesided/verdicts.json, from the workflow's journal).
Checks that every case of onesided/key.json has exactly one verdict and that no unknown case id appears.

  python -B tally_onesided.py <journal.jsonl> [folder]   (folder: onesided (v9, default) or onesided_v10r)
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHORT = {"covered: the other run missed it": "missed", "not covered: the listing run over-applied the rule": "over-applied",
         "unclear wording: both readings fit": "unclear", "cannot tell": "cannot tell"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    folder = HERE / (sys.argv[2] if len(sys.argv) > 2 else "onesided")
    key = json.loads((folder / "key.json").read_text(encoding="utf-8"))
    texts = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    got = {}
    for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
        x = json.loads(l)
        if x.get("type") != "result":
            continue
        r = x.get("result") or x.get("value")
        r = json.loads(r) if isinstance(r, str) else r
        for g in (r if isinstance(r, list) else [r]):
            for v in (g.get("verdicts") or []) if isinstance(g, dict) else []:
                got.setdefault(v["case"].strip(), []).append(v)
    unknown = sorted(set(got) - set(key))
    missing = sorted(set(key) - set(got))
    dup = sorted(k for k, v in got.items() if len(v) > 1)
    print(f"cases {len(key)}, answered {len(set(got) & set(key))}, missing {len(missing)}, unknown ids {len(unknown)}, duplicates {len(dup)}")
    if unknown or dup:
        print("  unknown:", unknown[:5], "dup:", dup[:5])
    per = defaultdict(Counter)
    ex = defaultdict(list)
    tot = Counter()
    for cid, vs in got.items():
        if cid not in key:
            continue
        v = vs[0]
        s = SHORT.get(v["verdict"], v["verdict"])
        k = key[cid]
        per[(k["rule"], k["phase"])][s] += 1
        tot[s] += 1
        if s == "unclear":
            ex[(k["rule"], k["phase"])].append(f"{k['module'][8:]}:{k['element']}: \"{v['words'][:140]}\"")
    print("all cases:", dict(tot))
    rows = []
    for (rid, ph), c in sorted(per.items(), key=lambda kv: (-kv[1]["unclear"], -kv[1]["missed"])):
        print(f"  {rid:44s} {ph} {texts[rid]['title'][:32]:32s} {dict(c)}")
        for e in ex[(rid, ph)][:3]:
            print("       unclear:", e)
        rows.append({"rule": rid, "title": texts[rid]["title"], "wording": ph, **c, "unclear examples": ex[(rid, ph)]})
    (folder / "tally.json").write_text(json.dumps({"total": tot, "per wording": rows, "missing": missing},
                                                             indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
