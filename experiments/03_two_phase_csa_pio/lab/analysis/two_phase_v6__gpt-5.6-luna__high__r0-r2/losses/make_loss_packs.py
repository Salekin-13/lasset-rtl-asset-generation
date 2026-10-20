"""Evidence packs for the v6 recall diagnosis (read-only; nothing is sent).

Elements: every reference entry found in a smaller share of v6 runs (of 3) than of v5f runs (of 6) (compare_v6.json).
Per element: v5f's six runs (primary or not), and for v6 r0-r2 and v5g r0-r2 in full: primary in the scorer file or
not; Phase 1 concepts naming it (and whether they cite one of its RTL lines); Not Kept entries naming it (with Merged
Into / Why Not Kept); every Phase 2 row naming it (concept, label, Functionality, Justification); Not Reported entries;
the No Primary Reason of walks with no primary that name it. Writes <short>.md and losses.json.
Self-test: the shares recomputed here equal compare_v6.json.

  python make_loss_packs.py
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent
LAB = AN.parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB.parents[2] / "src"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402

FULL = [("v6", "two_phase_v6", r) for r in (0, 1, 2)] + [("v5g", "two_phase_v5g", r) for r in (0, 1, 2)]


def has(name, text):
    return bool(re.search(r"(?<![\w.])" + re.escape(name) + r"(?!\w)(?!\.\w)", text or ""))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cmp = json.loads((AN / "compare_v6.json").read_text(encoding="utf-8"))["found"]
    import eval_assets as ea
    with CH.at_root():
        refs = ea.load_refs()["gt"]
    out_all = {}
    for m in CH.tuning_modules():
        short = m.replace("neorv32_", "")
        names = CH.closed_names(m)
        ref = [n for n, _ in refs[m] if n in {x for (_, x) in names}]
        kth, chosen = Counter(), []
        for n in ref:
            kth[n] += 1
            key = f"{short}:{n}#{kth[n]}"
            g6, g5, gf = cmp["v6"].get(key, 0), cmp["v5g"].get(key, 0), cmp["v5f"].get(key, 0)
            if g6 / 3 < gf / 6 - 1e-9:
                chosen.append((n, key, g6, g5, gf))
        if not chosen:
            continue
        out = [f"# {short}: reference elements found less often in v6 (v6 of 3 vs v5g of 3, v5f of 6)", "",
               "v6 = v5g + 24 paired Phase 1 / Phase 2 rules. The v6 changes, file by file, with rule ids: "
               "analysis/two_phase_v5g__gpt-5.6-luna__high__r0-r2/rules/diff_v5g_to_v6.md; exact rule texts: rules/RULES_V6_APPENDIX.md.", ""]
        for n, key, g6, g5, gf in chosen:
            lines = set()
            for (e, x), fx in names.items():
                if x == n:
                    lines |= set(fx.get("occurrence lines") or [])
            out.append(f"## {n}: v6 {g6}/3, v5g {g5}/3, v5f {gf}/6 (RTL lines {sorted(lines)[:20]})")
            for k, v, r in FULL:
                run = CH.run_dir(v, "gpt-5.6-luna", r, "high")
                assets = json.loads((run / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]
                p1 = K.parse_json(json.loads((run / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
                p2 = K.parse_json(json.loads((run / "phase2" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
                isp = any(x["Asset RTL"] == n for x in assets)
                cname = {c.get("Concept ID"): c.get("Concept Name") for c in p1.get("Conceptual Assets", []) if isinstance(c, dict)}
                p1c = []
                for c in p1.get("Conceptual Assets", []):
                    if not isinstance(c, dict):
                        continue
                    cl = set(c.get("Held Lines") or []) | set(c.get("Entry Lines") or []) | set(c.get("Exit Lines") or [])
                    named = has(n, json.dumps(c, ensure_ascii=False))
                    if named or cl & lines:
                        p1c.append(f"{c.get('Concept ID')} '{c.get('Concept Name')}' ({'names it' if named else 'does not name it'}; "
                                   f"cites its lines: {sorted(cl & lines)[:8] or 'no'})")
                nk = [f"'{x.get('Candidate Name')}': " + (f"merged into {x.get('Merged Into')}" if x.get("Merged Into") else str(x.get("Why Not Kept")))
                      for x in p1.get("Not Kept", []) if isinstance(x, dict) and has(n, json.dumps(x, ensure_ascii=False))]
                rows = []
                for w in p2.get("Concept Walks", []) or []:
                    if not isinstance(w, dict):
                        continue
                    cid = w.get("Concept ID")
                    for a in (w.get("Assets") or []):
                        if isinstance(a, dict) and (a.get("Asset RTL") == n or n in (a.get("Same Role") or [])):
                            rows.append(f"{cid} '{cname.get(cid)}' {a.get('Label')}: F: {a.get('Functionality')} | J: {a.get('Justification')}")
                    for x in (w.get("Not Reported") or []):
                        if isinstance(x, dict) and x.get("Element RTL") == n:
                            rows.append(f"{cid} NOT REPORTED: {x.get('Why Not Reported')}")
                    npr = w.get("No Primary Reason")
                    if npr and has(n, npr):
                        rows.append(f"{cid} NO PRIMARY REASON naming it: {npr}")
                out.append(f"- {k} r{r}: {'PRIMARY' if isp else 'not primary'}; Phase 1 concepts naming it or citing its lines: {'; '.join(p1c) or '-'}"
                           + (f"; Not Kept naming it: {nk}" if nk else ""))
                out += [f"    - {x}" for x in rows] or ["    - no Phase 2 row names it"]
            out.append("")
        (HERE / f"{short}.md").write_text("\n".join(out), encoding="utf-8")
        out_all[short] = [{"element": n, "key": key, "v6 of 3": g6, "v5g of 3": g5, "v5f of 6": gf} for n, key, g6, g5, gf in chosen]
        print(f"{short}: {len(chosen)} elements")
    (HERE / "losses.json").write_text(json.dumps(out_all, indent=1), encoding="utf-8")
    print("total elements:", sum(len(v) for v in out_all.values()))


if __name__ == "__main__":
    main()
