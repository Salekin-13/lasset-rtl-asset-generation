"""Evidence packets for the diagnosis of v5f's four rule-2 elements (bus stb, muldiv div.start and mul.start, imem
rdata). For every version v1..v5f (inputs v1, gpt-5.6-luna, high, r0-r2): whether the element is a listed primary
(scorer file), every Phase 2 row naming it (concept, label, reason), every Phase 1 concept whose text names it, and the
module's concept names; plus the element's RTL lines. Writes <case>.md and counts.json next to this file.
Self-test: v5 and v5f primary counts per element must equal compare_v5f.json's per-element run counts.

  python make_diag4.py
"""
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
sys.path.insert(0, str(LAB))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402

VERSIONS = ["two_phase_v1", "two_phase_v2", "two_phase_v2a", "two_phase_v3", "two_phase_v4", "two_phase_v4a",
            "two_phase_v5", "two_phase_v5f"]
CASES = {"bus_stb": ("neorv32_bus", ["stb"]),
         "muldiv_start": ("neorv32_cpu_cp_muldiv", ["div.start", "mul.start"]),
         "imem_rdata": ("neorv32_imem", ["rdata"])}


def has(name, text):
    return bool(re.search(r"(?<![\w.])" + re.escape(name) + r"(?!\w)(?!\.\w)", text or ""))


def rec(v, r, ph, m):
    p = CH.run_dir(v, "gpt-5.6-luna", r, "high") / f"phase{ph}" / f"{m}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    counts = {}
    for case, (m, els) in CASES.items():
        names = CH.closed_names(m)
        rtl = {int(mm.group(1)): l for l in CH.inputs(m)["rtl.txt"].splitlines() if (mm := re.match(r"\s*(\d+) \|", l))}
        out = [f"# Evidence: {case} ({m}: {', '.join(els)})", "",
               "Rows are read from the stored replies (\"reply\" in v5 keys; for v5f, chain.py's mapping of the reply as written:",
               "'reason' = Functionality + Justification). 'primary in scorer file' = listed in assets/<module>.json.", ""]
        for el in els:
            ents = sorted(e for (e, n) in names if n == el)
            out.append(f"## RTL of {el} (entities: {', '.join(ents)})")
            for e in ents:
                x = names[(e, el)]
                lines = sorted(set(x.get("occurrence lines", [])))
                out.append(f"- {e}: tags {x.get('tags') or x.get('role in RTL')}; counterparts {json.dumps(x.get('counterparts'), ensure_ascii=False)[:600]}")
                out += [f"    {rtl[i]}" for i in lines if i in rtl]
            out.append("")
        table = ["## Primary in the scorer file, runs out of 3", "", "| version | " + " | ".join(els) + " |",
                 "|---|" + "---|" * len(els)]
        for v in VERSIONS:
            row = []
            for el in els:
                n = 0
                for r in (0, 1, 2):
                    a = CH.run_dir(v, "gpt-5.6-luna", r, "high") / "assets" / f"{m}.json"
                    n += a.exists() and any(x["Asset RTL"] == el for x in json.loads(a.read_text(encoding="utf-8"))["Assets"])
                row.append(n)
                counts.setdefault(case, {}).setdefault(el, {})[v] = n
            table.append(f"| {v.replace('two_phase_', '')} | " + " | ".join(map(str, row)) + " |")
        out += table + [""]
        for v in VERSIONS:
            out.append(f"## {v}")
            for r in (0, 1, 2):
                r1, r2 = rec(v, r, 1, m), rec(v, r, 2, m)
                if not r1 or not r2:
                    out.append(f"### r{r}: missing")
                    continue
                ca = CH.phase1_concepts(r1["reply"]) or []
                cname = {c.get("id"): c.get("concept") for c in ca}
                out.append(f"### {v.replace('two_phase_', '')} r{r}")
                out.append("- Phase 1 concepts: " + "; ".join(f"{c.get('id')} {c.get('concept')}" for c in ca))
                for c in ca:
                    blob = json.dumps(c, ensure_ascii=False)
                    hit = [el for el in els if has(el, blob)]
                    if hit:
                        out.append(f"- Phase 1 {c.get('id')} '{c.get('concept')}' names {hit}: information: {c.get('information')} | "
                                   f"rubric reason: {c.get('rubric reason')} | held lines {c.get('held lines')}")
                for x in r1["reply"].get("considered, not kept", []) or []:
                    if isinstance(x, dict) and any(has(el, json.dumps(x, ensure_ascii=False)) for el in els):
                        out.append(f"- Phase 1 NOT KEPT names it: {x.get('concept')}: {x.get('reason')}")
                rows = [a for a in r2["reply"].get("structural assets", []) if isinstance(a, dict)
                        and any(el == a.get("element") or el in (a.get("same role") or []) for el in els)]
                if not rows:
                    out.append(f"- Phase 2: no row names {els}")
                for a in rows:
                    out.append(f"- Phase 2 row: {a.get('element')} | {a.get('concept id')} '{cname.get(a.get('concept id'))}' | "
                               f"{a.get('label')} | links {json.dumps(a.get('links'))} | reason: {a.get('reason')}")
                for x in r2["reply"].get("not reported", []) or []:
                    if x.get("element") in els:
                        out.append(f"- Phase 2 NOT REPORTED: {x.get('element')} under {x.get('concept id')}: {x.get('reason')}")
                notes = [n for n in r2["reply"].get("notes", []) if any(has(el, str(n)) for el in els)]
                out += [f"- Phase 2 note: {n}" for n in notes]
            out.append("")
        (HERE / f"{case}.md").write_text("\n".join(out), encoding="utf-8")
        print(f"{case}.md written ({len(out)} lines)")
    # self-test against compare_v5f.json (per-element run counts, exact scorer)
    cmp = json.loads((HERE.parent / "compare_v5f.json").read_text(encoding="utf-8"))["B"]["found"]
    ok = True
    for case, (m, els) in CASES.items():
        for el in els:
            key = f"{m.replace('neorv32_', '')}:{el}#1"
            for v, short in (("two_phase_v5", "v5"), ("two_phase_v5f", "v5f")):
                ok &= counts[case][el][v] == cmp[short].get(key, 0)
    print("self-test (counts equal compare_v5f.json for v5 and v5f):", ok)
    (HERE / "counts.json").write_text(json.dumps(counts, indent=1), encoding="utf-8")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
