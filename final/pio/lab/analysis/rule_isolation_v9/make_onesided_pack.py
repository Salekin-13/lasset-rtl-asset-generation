"""Reading packs for the one-sided differences of the rules outside the nine: one isolated run bars a signal, the other
run does not list it at all. Code only; writes onesided/group_<k>.md and onesided/key.json.

Selected wordings: rules outside the nine (and not the revised Operation selectors) whose one-sided differences touch
3 or more modules. Per wording, up to 5 cases, one per module first, cases where the other run barred nothing in the
module ("rule not applied there") before cases where it barred others but left this signal out; at most 2 per module.
Each case gives the rule text, the barring run's quoted words, reason and lines, what the other run did in that module,
and where the RTL and closed set are.

  python -B make_onesided_pack.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402
import analyze_isolation as A  # noqa: E402

CH = ISO.CH
NINE = {"P1-05", "P1-10", "P1-22", "P1-23", "P1-07", "P1-04", "P1-08", "P1-27", "P1-17", "P1-22R"}
OUT = HERE / "onesided"
GROUPS = 7


def entry(reply, key, e):
    return [x for x in reply.get(key) or [] if isinstance(x, dict) and x.get("element") and A.covered(e, {x["element"]})]


def main():
    R = A.load(lambda r: ISO.run_root(rep=r))
    texts = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    sel = []
    for rid in sorted({k[0] for k in R}):
        if rid in NINE:
            continue
        for ph in ("P1", "P2"):
            mods = sorted({k[2] for k in R if k[0] == rid and k[1] == ph and k[3] == 0} & {k[2] for k in R if k[0] == rid and k[1] == ph and k[3] == 1})
            dkey = "spared" if A.adds(rid) else "barred"
            cands = defaultdict(list)
            for m in mods:
                D = [A.names(R[(rid, ph, m, r)], dkey) for r in (0, 1)]
                for a, b in ((0, 1), (1, 0)):
                    for e in sorted(D[a]):
                        if not A.covered(e, D[b]):
                            cands[m].append((0 if not D[b] else 1, e, a, b, len(D[b])))
            if len(cands) < 3:
                continue
            picked, rnd = [], 0
            while len(picked) < 5 and rnd < 2:
                for m in sorted(cands, key=lambda mm: min(c[0] for c in cands[mm])):
                    cs = sorted(cands[m])
                    if rnd < len(cs) and len(picked) < 5:
                        picked.append((m, *cs[rnd]))
                rnd += 1
            sel.append((rid, ph, dkey, picked, len(cands)))
    OUT.mkdir(exist_ok=True)
    key, groups = {}, defaultdict(list)
    for i, s in enumerate(sel):
        groups[i % GROUPS].append(s)
    for g, items in groups.items():
        L = [f"# One-sided differences, group {g + 1}\n",
             "Each case: one rule, applied ALONE by a model to one module, twice with identical input. One run listed the signal",
             "under the rule's decision list; the other run did not list it at all. Judge, from the rule's words and the RTL, which",
             "is right. Read the cited RTL lines (rtl.txt has 'line | text' rows; closed_set.json lists each signal's role,",
             "counterparts and lines).\n"]
        for rid, ph, dkey, picked, nmods in items:
            L.append(f"\n## Rule {rid} ({texts[rid]['title']}), {'Phase 1' if ph == 'P1' else 'Phase 2'} wording")
            L.append(f"Decision list: \"{dkey}\" ({'signals the rule bars' if dkey == 'barred' else 'signals this clause makes primary'}). "
                     f"One-sided differences in {nmods} modules.\n")
            L.append("Rule text:\n\n> " + texts[rid][ph].replace("\n", "\n> ") + "\n")
            for j, (m, emp, e, a, b, nb) in enumerate(picked):
                cid = f"{rid}|{ph}|{j}"
                key[cid] = {"rule": rid, "phase": ph, "module": m, "element": e, "listing run": a, "other run": b,
                            "other run listed nothing": emp == 0}
                ra, rb = R[(rid, ph, m, a)], R[(rid, ph, m, b)]
                ea = entry(ra, dkey, e)[:1]
                other = [f"{k}: {x['element']}" for k in ("barred", "spared", "unsure") for x in entry(rb, k, e)]
                L.append(f"### Case {cid}: module {m}, signal `{e}`")
                L.append(f"- RTL: {CH.module_dir(m) / 'rtl.txt'} ; closed set: {CH.module_dir(m) / 'closed_set.json'}")
                if ea:
                    x = ea[0]
                    L.append(f"- Run {a} listed `{x['element']}` under \"{dkey}\": rule words \"{x.get('rule words')}\"; lines {x.get('lines')}; why: {x.get('why')}")
                L.append(f"- Run {b}: applies = {rb.get('applies')!r}; listed {nb} signals under \"{dkey}\" in this module"
                         + (f"; mentions this signal elsewhere: {other}" if other else "; does not mention this signal anywhere") + "\n")
        (OUT / f"group_{g + 1}.md").write_text("\n".join(L), encoding="utf-8")
    (OUT / "key.json").write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(sel)} wordings, {len(key)} cases, {len(groups)} groups:",
          {f"group_{g + 1}": [f"{s[0]} {s[1]}" for s in it] for g, it in groups.items()})


if __name__ == "__main__":
    main()
