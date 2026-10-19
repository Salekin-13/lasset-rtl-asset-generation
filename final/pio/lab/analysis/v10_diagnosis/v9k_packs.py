"""Reading packs for the v9k rule-alone replies: per rule and wording, how each repeat decided every intended, must-spare /
must-bar and harm element, with the reply's own "rule words" and "why" (so a failing wording can be revised from how the
text was read, not from a guess). Read-only; writes v9k_packs.json and prints a compact view.

  python -B v9k_packs.py [rule id ...]
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, register  # noqa: E402

ISO = register()
sys.path.insert(0, str(ISO.HERE))
import claude_rules as CR  # noqa: E402
import rule_breaks as RB  # noqa: E402

META = json.loads((HERE / "new_rules" / "meta_v9k.json").read_text(encoding="utf-8"))
TEXTS = json.loads((HERE / "new_rules" / "rule_texts_v9k.json").read_text(encoding="utf-8"))


def rows(reply):
    out = {}
    for k in ("barred", "spared", "unsure"):
        for x in reply.get(k) or []:
            if isinstance(x, dict) and x.get("element"):
                out[x["element"]] = (k, (x.get("rule words") or "")[:140], (x.get("why") or "")[:220])
    return out


def main(only=None):
    sys.stdout.reconfigure(encoding="utf-8")
    _, refl = RB.CV.groups_and_ref()
    out = {}
    for rid in TEXTS:
        if only and rid not in only:
            continue
        meta = META[rid]
        cases = [(c.split(":")[0], c.split(":", 1)[1], "intended") for c in meta["intended_cases"]]
        cases += [(c.split(":")[0], c.split(":", 1)[1], "must-spare" if "must_spare" in meta else "must-bar") for c in meta.get("must_spare") or meta.get("must_bar") or []]
        sides = ("new", "old") if CR.PLAN[rid].get("old") else ("new",)
        pack = {}
        for side in sides:
            variant = CR.STORE[side]
            ISO.use(variant)
            try:
                for ph in CR.PLAN[rid]["phases"]:
                    for m in CR.PLAN[rid]["modules"]:
                        reps = []
                        for rep in (0, 1):
                            f = ISO.run_root(rep=rep) / ph / rid / f"{m}.json"
                            rec = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
                            reps.append(rows(rec["reply"]) if rec and isinstance(rec.get("reply"), dict) else None)
                        key = f"{side} {ph} {m[8:]}"
                        ent = {}
                        for (mm, e, kind) in cases:
                            if mm != m:
                                continue
                            ent[e] = {"kind": kind, "reference": e in refl.get(m, ()),
                                      "r0": reps[0].get(e) if reps[0] is not None else "no reply",
                                      "r1": reps[1].get(e) if reps[1] is not None else "no reply"}
                        others = {}
                        for i, r in enumerate(reps):
                            for e, v in (r or {}).items():
                                if e not in ent and v[0] != "unsure":
                                    others.setdefault(e, {})[f"r{i}"] = v
                        pack[key] = {"cases": ent, "other decisions": {e: {**v, "reference": e in refl.get(m, ())} for e, v in others.items()}}
            finally:
                ISO.use("v9")
        out[rid] = pack
    (HERE / "v9k_packs.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for rid, pack in out.items():
        print(f"\n===== {rid} {TEXTS[rid]['title']}")
        for key, x in pack.items():
            print(f"-- {key}")
            for e, v in x["cases"].items():
                print(f"   [{v['kind']}{' REF' if v['reference'] else ''}] {e}: r0 {str(v['r0'])[:230]} | r1 {str(v['r1'])[:230]}")
            if x["other decisions"]:
                print("   other:", {e: (v.get('r0', v.get('r1')))[0] + ('*' if v['reference'] else '') for e, v in x["other decisions"].items()})


if __name__ == "__main__":
    main(sys.argv[1:] or None)
