"""Evidence for rewording three Phase 1 rules that fail ALONE in the production Phase 1 (p1followup.py): Operation selectors
(P1-22), Forwarded transactions (P1-05), Build-time values (P1-03). Read-only; writes p1fix_packs/<rule>.md and
p1fix_packs/index.json. Sends nothing.

For each rule: its exact v10 Phase 1 and Phase 2 texts; every signal it bars in both rule-alone repeats (Phase 1 wording)
in its failure modules, with the rule-alone "rule words" and reason; for each Phase 1 reply (alone cell r0-r1, full v10
r0-r2) whether the signal is named, and HOW: which concept, whether in its Enters / Leaves Through list, or only inside
the information text (with the sentence that names it), and the concept's held lines; reference membership; and the
reply's own Not Kept rows that cite the rule (did the model consider the rule and still keep the signal?).
Also a "mention-only" count: named only inside an information sentence, not as a port, so a rewording of the rule
cannot be the fix for those.

  python -B make_p1fix_packs.py
"""
import json
import os
import re
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import ladder as L  # noqa: E402
import p1clusters as PC  # noqa: E402
import rule_breaks as RB  # noqa: E402
import make_blind_packs as MB  # noqa: E402
import analyze_isolation as AN  # noqa: E402

RULES = {"P1-22": ("K2", ["neorv32_cpu_control", "neorv32_cpu_lsu"], ("Operation selectors",)),
         "P1-05": ("K2", ["neorv32_cpu_icc", "neorv32_xbus", "neorv32_cpu"], ("Forwarded transactions",)),
         "P1-03": ("K3", ["neorv32_uart", "neorv32_sysinfo", "neorv32_debug_dm"], ("Build-time values",))}
KEYS = {"P1-22": ["operation selector", "selector"], "P1-05": ["forward", "relay"], "P1-03": ["build-time", "build time", "generic", "constant"]}


def how_named(rec, m, e):
    cons = CH.phase1_concepts(rec.get("reply")) or []
    out = []
    for c in cons:
        ports = CH.as_list(c.get("enters through")) + CH.as_list(c.get("leaves through"))
        info = str(c.get("information") or "") + " " + str(c.get("concept") or "")
        if e in ports:
            out.append(f"PORT of {c.get('id')} \"{c.get('concept')}\"")
        elif re.search(r"(?<![\w.])" + re.escape(e) + r"(?!\w)", info):
            sent = next((s for s in re.split(r"(?<=[.;])\s+", info) if re.search(r"(?<![\w.])" + re.escape(e) + r"(?!\w)", s)), "")
            out.append(f"MENTION in {c.get('id')} \"{c.get('concept')}\": {sent[:220]}")
    return out


def notkept(rec, rid):
    raw = CH.K.parse_json(rec["raw"]) if rec.get("raw") else {}
    rows = raw.get("Not Kept") if isinstance(raw, dict) else None
    return [json.dumps(x, ensure_ascii=False)[:300] for x in rows or [] if any(k in json.dumps(x).lower() for k in KEYS[rid])]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, refl = RB.CV.groups_and_ref()
    mods41 = groups["tuning"] + groups["held-out"]
    ref = {m: set(v) for m, v in refl.items()}
    R, _, _ = RB.load_latest(mods41)
    dec = PC.decisions(mods41)
    out = HERE / "p1fix_packs"
    out.mkdir(exist_ok=True)
    texts = {}
    for f in ("rule_texts.json", "rule_texts_v10m.json"):
        texts.update(json.loads((RB.ISOD / f).read_text(encoding="utf-8")))
    index = {}
    for rid, (k, mods, _) in RULES.items():
        t = texts[rid]
        Lines = [f"# {rid} {t['title']}: evidence for a wording and scope fix", "",
                 "Phase 1 cells: alone = Phase 1 core + this rule (luna, r0-r1); full v10 = the stored v10 run (r0-r2). A break = a "
                 "Phase 1 reply names a signal this rule bars in both rule-alone repeats.", "",
                 "## v10 Phase 1 wording", "", "```", t["P1"], "```", "", "## v10 Phase 2 wording", "", "```", t.get("P2") or "(none)", "```", ""]
        tally = {"named as port": 0, "mention only": 0, "not named": 0, "pairs": 0}
        for m in mods:
            els = sorted(dec[rid].get(m, ()))
            Lines.append(f"## {m}  (RTL {CH.module_dir(m) / 'rtl.txt'}; closed set {CH.module_dir(m) / 'closed_set.json'})")
            for e in els:
                ent, fx = MB.closed_entry(m, e)
                its = [AN.names(R[(rid, 'P1', m, r)], 'barred') for r in (0, 1)]
                item = next((x for x in (R[(rid, 'P1', m, 0)] or {}).get('barred') or [] if isinstance(x, dict) and
                             (x.get('element') == e or e.startswith(str(x.get('element')) + '.'))), {})
                Lines.append(f"### {e}  (reference: {e in ref[m]}; {'port ' + str(fx.get('direction')) if fx.get('port') else 'signal'}; "
                             f"role {fx.get('role in RTL')}; lines {fx.get('occurrence lines')})")
                Lines.append(f"- rule alone bars it: \"{item.get('rule words', '')}\" | {item.get('why', '')} | lines {item.get('lines')}")
                for tag, d, reps in (("alone", L.cell_dir(f"P1alone__{rid.replace('-', '')}__{k}", 0).parent, (0, 1)),
                                     ("full v10", CH.run_dir(V10, MODEL, 0, EFFORT).parent, (0, 1, 2))):
                    for r in reps:
                        f = d / f"r{r}" / "phase1" / f"{m}.json"
                        if not f.exists():
                            continue
                        rec = json.loads(f.read_text(encoding="utf-8"))
                        h = how_named(rec, m, e)
                        tally["pairs"] += 1
                        if any(x.startswith("PORT") for x in h):
                            tally["named as port"] += 1
                        elif h:
                            tally["mention only"] += 1
                        else:
                            tally["not named"] += 1
                        if h:
                            Lines.append(f"- {tag} r{r}: " + " || ".join(h))
                Lines.append("")
            nk = []
            for r in (0, 1):
                f = L.cell_dir(f"P1alone__{rid.replace('-', '')}__{k}", r) / "phase1" / f"{m}.json"
                if f.exists():
                    nk += [f"alone r{r}: {x}" for x in notkept(json.loads(f.read_text(encoding="utf-8")), rid)]
            if nk:
                Lines += ["Not Kept rows citing the rule (alone cell):"] + [f"- {x}" for x in nk[:8]] + [""]
        Lines += ["## Tally (alone r0-r1 and full v10 r0-r2, over the signals above)", "", json.dumps(tally), ""]
        (out / f"{rid}.md").write_text("\n".join(Lines), encoding="utf-8")
        index[rid] = {"title": t["title"], "modules": mods, "tally": tally}
        print(rid, t["title"], tally)
    (out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
