"""Why does a target bar break even in core + target alone? Two code readings on the staged-test cells (read-only; writes
core_clash.json; sends nothing).

1. Phase 1 pull. Phase 2 receives luna's v10 Phase 1 reply (held fixed). For each (module, consistently barred element,
   repeat k): did Phase 1 run rk name the element: by name (in a concept's information, Enters Through or Leaves Through),
   or by line (one of its closed-set occurrence lines is a held, entry or exit line of a concept; attribute.py's
   line link, which over-counts)? Cross-tab against "listed primary" for each cell. If breaks happen mostly where Phase 1
   named the element, the clash is the Phase 1 -> Phase 2 hand-off (the bar must override CONCEPTS).
2. What a broken row says. For every pair labelled primary: does its Justification / Functionality text use the target
   rule's own key words (attribute.RULE_KEYS for its title; the model saw the bar and labelled primary anyway: cause E
   or a deliberate override), 2.6's words (stored, computed, decision, decides, crosses, boundary, setting: the
   definition pulling), or neither.
Self-test: on the stored full-v10 cell the pair counts equal ladder.measure's.

  python -B core_clash.py
"""
import json
import os
import re
import sys
from collections import Counter

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, register  # noqa: E402

ISO = register()
import ladder as L  # noqa: E402
import rule_breaks as RB  # noqa: E402

CH, T, A = RB.CH, RB.T, RB.A
WORDS26 = ["stored", "computed", "decision", "decides", "crosses", "boundary", "setting", "holds the", "where it is"]


def p1_names(m, r):
    rec = T.load(RB.V10, r, m, 1)
    cons = CH.phase1_concepts(rec.get("reply")) or []
    named, lines = set(), set()
    txt = " ".join(str(c.get("information") or "") + " " + str(c.get("concept") or "") for c in cons)
    for c in cons:
        named |= {x for x in CH.as_list(c.get("enters through")) + CH.as_list(c.get("leaves through")) if isinstance(x, str)}
        lines |= set(CH.as_list(c.get("held lines")) + CH.as_list(c.get("entry lines")) + CH.as_list(c.get("exit lines")))
    return named, lines, txt


def occ(m, e):
    for (_, x), fx in CH.closed_names(m).items():
        if x == e:
            return set(fx.get("occurrence lines") or [])
    return set()


def keys_for(target):
    rid = target.split()[0]
    titles = {r: t["title"] for r, t in json.loads((RB.ISOD / "rule_texts.json").read_text(encoding="utf-8")).items()}
    title = titles.get(rid, "")
    ks = [k for r, v in A.RULE_KEYS.items() if r.split(" (")[0] == title for k in v]
    if rid.startswith("P2X-"):
        ks += {"P2X-bus-request-response-record-port": ["bus request", "response record", "record port", "bus-record", "bus record"],
               "P2X-other-2-6-non-primaries": ["not primary", "never primary", "only passes", "copy kept", "carrier"]}.get(rid, [])
    return ks


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    plan = json.loads((HERE / "plan_round1.json").read_text(encoding="utf-8"))
    out = {}
    for t, x in plan.items():
        if t.startswith("P1-05"):
            continue
        base = t.split()[0].replace("-", "")
        ks = keys_for(t)
        cellnames = ["full"] + [n for n in (f"{base}__S1", f"{base}__S2", f"{base}__P_pos", f"{base}__P_clar") if n in L.cells()]
        for cn in cellnames:
            m_ = L.measure("full", target=t, modules=x["modules"], reps=[0, 1, 2]) if cn == "full" else L.measure(cn)
            if cn == "full":
                ref = L.measure("full", target=t, modules=x["modules"], reps=[0, 1, 2])
                assert (ref["pairs"], ref["complied"]) == (m_["pairs"], m_["complied"])
            tab = Counter()
            said = Counter()
            for row in m_["rows"]:
                named, lines, txt = p1_names(row["module"], row["rep"])
                e = row["element"]
                by_name = e in named or bool(re.search(r"(?<![\w.])" + re.escape(e) + r"(?!\w)", txt))
                by_line = bool(occ(row["module"], e) & lines)
                p1 = "named by Phase 1" if by_name else "line-linked only" if by_line else "not in Phase 1"
                tab[(p1, row["state"] == "primary")] += 1
                if row["state"] == "primary":
                    low = " ".join(row["texts"]).lower()
                    k = "cites the target's words" if any(w in low for w in ks) else \
                        "cites 2.6's words" if any(w in low for w in WORDS26) else "cites neither"
                    said[k] += 1
            out[f"{t} | {cn}"] = {"pairs": m_["pairs"], "primary (broken)": m_["pairs"] - m_["complied"],
                                  "Phase 1 x broken": {f"{a} | {'broken' if b else 'kept to the bar'}": n for (a, b), n in sorted(tab.items())},
                                  "what broken rows say": dict(said)}
    (HERE / "core_clash.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("self-test (full-v10 pair counts = ladder.measure): PASS")
    for k, v in out.items():
        b = v["Phase 1 x broken"]
        def rate(lbl):
            n_b, n_k = b.get(f"{lbl} | broken", 0), b.get(f"{lbl} | kept to the bar", 0)
            return f"{n_b}/{n_b + n_k}"
        print(f"{k:58s} broken {v['primary (broken)']:3d}/{v['pairs']:3d} | broken when Phase 1 named it {rate('named by Phase 1')}, "
              f"line-linked {rate('line-linked only')}, not in Phase 1 {rate('not in Phase 1')} | {v['what broken rows say']}")


if __name__ == "__main__":
    main()
