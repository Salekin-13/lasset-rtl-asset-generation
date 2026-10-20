"""Rule texts for the rule-alone test of the new blind-spot rules (variant v11n; round 2: v11n2).

Reads drafts/N??_<suffix>.json (the workflow's final drafts), keeps those with a Phase 1 or Phase 2 block and an empty
"no_rule", runs check_new_rules (a BLOCKER stops it), and writes:
  rule_texts_<variant>.json   {id: {"title", "P1", "P2"}} in isolation.py's texts format
  meta_<variant>.json         {id: {"kind", "basis", "basis_kind", "intended_cases", "must_spare", "overlaps", "expected_harm"}}
Sends nothing.

  python -B make_v11n_texts.py [v11n final | v11n2 final2]
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKS = json.loads((HERE.parent / "blind_packs" / "index.json").read_text(encoding="utf-8"))
UNIT_OF = {f"N{int(u.split('_')[0][1:]):02d}": u for u in PACKS}          # N01 = U1 ... N10 = U10 (the workflows' ids)


def main(variant="v11n", suffix="final"):
    sys.stdout.reconfigure(encoding="utf-8")
    texts, meta, skipped = {}, {}, {}
    for f in sorted((HERE / "drafts").glob(f"N*_{suffix}.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        rid = d.get("id") or f.stem.split("_")[0]
        if not (d.get("P1") or d.get("P2")):            # "no_rule" may only note cases a rule with text leaves uncovered
            skipped[rid] = d.get("no_rule") or "no text"
            continue
        texts[rid] = {"title": d["title"], "P1": (d.get("P1") or "").strip() or None, "P2": (d.get("P2") or "").strip() or None}
        meta[rid] = {k: d.get(k) for k in ("kind", "basis", "basis_kind", "intended_cases", "must_spare", "overlaps", "expected_harm", "no_rule")}
        unit = UNIT_OF.get(rid)                          # intended cases = the pack's unaddressed elements (code, not the agent)
        if unit:
            meta[rid]["writer's intended cases"] = meta[rid].pop("intended_cases")
            meta[rid]["intended_cases"] = PACKS[unit]["element list"]
    tmp = HERE / f"_check_{variant}.json"
    tmp.write_text(json.dumps(texts, indent=1, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, "-B", str(HERE.parent / "check_new_rules.py"), str(tmp)], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout[-3000:])
    tmp.unlink()
    if r.returncode:
        sys.exit("checker BLOCKERS: nothing written")
    (HERE / f"rule_texts_{variant}.json").write_text(json.dumps(texts, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / f"meta_{variant}.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{variant}: {len(texts)} rules, {sum(bool(t['P1']) for t in texts.values())} Phase 1 and "
          f"{sum(bool(t['P2']) for t in texts.values())} Phase 2 wordings; skipped {skipped}")


if __name__ == "__main__":
    main(*sys.argv[1:3]) if len(sys.argv) > 2 else main()
