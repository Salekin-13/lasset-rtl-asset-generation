"""Evidence for the one revision round of the new rules that failed their rule-alone cuts (decision D13). Read-only;
writes new_rules/revision_packs/<rule>.md. Sends nothing.

Per failing wording: every element the two repeats decided differently (each repeat's list, quoted rule words and
reason), every harmed reference entry (bar) or extra non-reference keep (keep) with the quoted words, and every intended
case not decided as meant, with what each repeat said.

  python -B make_revision_packs.py v11n
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, register  # noqa: E402

ISO = register()
import rule_breaks as RB  # noqa: E402
import analyze_isolation as AN  # noqa: E402


def items(rp, key):
    return {x.get("element"): x for x in rp.get(key) or [] if isinstance(x, dict) and x.get("element")}


def say(x):
    return f"\"{(x or {}).get('rule words', '')}\" | {(x or {}).get('why', '')} | lines {(x or {}).get('lines')}"


def main(variant="v11n"):
    sys.stdout.reconfigure(encoding="utf-8")
    rd = json.loads((HERE / f"read_{variant}.json").read_text(encoding="utf-8"))
    meta = json.loads((HERE / "new_rules" / f"meta_{variant}.json").read_text(encoding="utf-8"))
    texts = json.loads((HERE / "new_rules" / f"rule_texts_{variant}.json").read_text(encoding="utf-8"))
    groups, refl = RB.CV.groups_and_ref()
    ref = {m: set(v) for m, v in refl.items()}
    out = HERE / "new_rules" / "revision_packs"
    out.mkdir(exist_ok=True)
    ISO.use(variant)
    for rid, t in texts.items():
        if rd[rid]["PASS"]:
            continue
        keep = (meta[rid].get("kind") or "").startswith("keep")
        L = [f"# Revision evidence for {rid} \"{t['title']}\" ({meta[rid].get('kind')})", "",
             f"Rule-alone test on luna (variant {variant}), 41 modules x 2 repeats for Phase 2, Phase 1 where Phase 2 decided "
             "something. Cuts (decision D13): mean disagreement <= 0.157 and contradictions in <= 1 module; coverage of the "
             "intended cases >= 0.8; a bar bars no reference entry in both repeats; a keep rule keeps no more non-reference "
             "elements than reference entries it recovers.", ""]
        for ph in ("P1", "P2"):
            k = f"{rid} {ph}"
            if k not in rd:
                continue
            r = rd[k]
            L += [f"## {ph} wording", "", "```", t[ph], "```", "",
                  f"Readings: mean disagreement {r['mean disagreement']} over {r['modules deciding something']} modules; "
                  f"contradiction modules {r['contradiction modules']}; coverage {r['intended decided as meant (both repeats)']}"
                  f"/{r['intended cases']}; harm {r['harm count']} (recovered reference entries {len(r['recovered reference entries'])}). "
                  f"Ambiguity {'PASS' if r['ambiguity PASS'] else 'FAIL'}, harm {'PASS' if r['harm PASS'] else 'FAIL'}"
                  + (f", coverage {'PASS' if r.get('coverage PASS') else 'FAIL'}" if 'coverage PASS' in r else "") + ".", ""]
            dkey = "spared" if keep else "barred"
            L.append("### Elements the two repeats decided differently (the ambiguity)")
            n = 0
            for f0 in sorted((ISO.run_root(rep=0) / ph / rid).glob("*.json")):
                f1 = ISO.run_root(rep=1) / ph / rid / f0.name
                if not f1.exists():
                    continue
                a = json.loads(f0.read_text(encoding="utf-8")).get("reply") or {}
                b = json.loads(f1.read_text(encoding="utf-8")).get("reply") or {}
                da, db = items(a, dkey), items(b, dkey)
                for e in sorted(set(da) ^ set(db)):
                    if AN.covered(e, set(db) if e in da else set(da)) and not (meta[rid].get("kind") or "").startswith("naming"):
                        continue
                    n += 1
                    if n > 40:
                        break
                    ob = items(b, "spared" if dkey == "barred" else "barred").get(e) or items(b, "unsure").get(e)
                    oa = items(a, "spared" if dkey == "barred" else "barred").get(e) or items(a, "unsure").get(e)
                    L.append(f"- {f0.stem[8:]}:{e}: repeat 0 {'decides' if e in da else 'does not decide'} ({say(da.get(e) or oa)}); "
                             f"repeat 1 {'decides' if e in db else 'does not decide'} ({say(db.get(e) or ob)})")
            L.append(f"({n} listed)" if n else "none")
            L.append("")
            L.append("### Harm" + (" (non-reference elements kept in both repeats)" if keep else " (reference entries barred in both repeats)"))
            L += [f"- {x}" for x in r["harm list"]] or ["none"]
            if keep:
                L.append(f"Reference entries it keeps in both repeats (recovered): {r['recovered reference entries']}")
            L += ["", "### Intended cases not decided as meant", *([f"- {x}" for x in r["not covered"]] or ["none"]), ""]
        L += ["## Writer's notes", "", f"basis: {meta[rid].get('basis')}", "", f"overlaps: {meta[rid].get('overlaps')}", "",
              f"expected harm: {meta[rid].get('expected_harm')}", ""]
        (out / f"{rid}.md").write_text("\n".join(L), encoding="utf-8")
        print(f"{rid}: {sum(1 for l in L if l.startswith('- '))} evidence lines")
    ISO.use("v9")


if __name__ == "__main__":
    main(*(sys.argv[1:2] or ["v11n"]))
