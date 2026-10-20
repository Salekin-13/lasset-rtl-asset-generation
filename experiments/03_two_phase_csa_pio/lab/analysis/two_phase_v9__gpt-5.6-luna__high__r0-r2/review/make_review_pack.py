"""Review pack for the v9 narrowing (blind: no reference list, no scores). Read-only on prompts, inputs and v8 runs;
writes next to this file:
  rule.md     v8's Forwarded transactions rule (phase1.md line 27), v9's two added sentences, the Phase 2 relayed-data
              bar around the second one, the Precedence rule and common.md 2.6 (lines 96-100) as context
  rows.md     every v8 Phase 1 Not Kept row (runs r0-r2, all 41 modules) whose text cites forwarding or relayed data,
              per module with its ports (record / non-record, direction, role) and the RTL lines the row cites (+-1)
  ports.md    every module's top-entity ports, split into record and non-record, for a corpus-wide scope check
Leak check: none of the three files contains the words of the scoring vocabulary (reference, ground truth, LAsset,
TP, FP, correct find, findable, recall, precision) or any per-element count.

  python make_review_pack.py
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
import labkit as K  # noqa: E402

V8, V9 = "two_phase_v8", "two_phase_v9"
LEAK = re.compile(r"\b(reference|ground truth|LAsset|TP|FP|correct find|findable|recall|precision)\b", re.I)


def ports(m):
    cs = json.loads(CH.inputs(m)["closed_set.json"])
    top = cs["entity list"][0]
    rec, non = [], []
    for x in top["port list"]:
        d = f"{x.get('port')} ({x.get('direction')}{', record ' + x['record type'] if 'record type' in x else ''}; {', '.join(x.get('role in RTL') or [])})"
        (rec if "record type" in x else non).append(d)
    return top["entity name"], rec, non


def cited(text):
    out = set()
    for seg in re.findall(r"\blines?\b([^.;]*)", text) + re.findall(r"\(([\d,\s\-–and]+)\)", text):
        for a, b in re.findall(r"(\d+)\s*(?:[-–]\s*(\d+))?", seg):
            a, b = int(a), int(b or a)
            if 0 <= b - a <= 12:
                out |= set(range(a, b + 1))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p1_8 = (LAB / "prompts" / V8 / "phase1.md").read_text(encoding="utf-8").split("\n")
    p1_9 = (LAB / "prompts" / V9 / "phase1.md").read_text(encoding="utf-8").split("\n")
    p2_9 = (LAB / "prompts" / V9 / "phase2.md").read_text(encoding="utf-8").split("\n")
    com = (LAB / "prompts" / V9 / "common.md").read_text(encoding="utf-8").split("\n")
    prec = next(l for l in p1_9 if l.startswith("- Precedence."))
    i = p2_9[33].find("Relayed data is data")
    end = "those sentences still hold."                       # the end of v9's added Phase 2 sentence
    j = p2_9[33].find(end)
    assert i >= 0 and j > i, "v9 phase2.md line 34: relayed-data block or added sentence not found"
    R = ["# The rule under review\n",
         "## v8 phase1.md line 27 (Forwarded transactions), as run\n", p1_8[26], "",
         "## v9 phase1.md line 27 (the same rule with the added clause)\n", p1_9[26], "",
         "## v9 phase2.md line 34, the relayed-data part (with the added Phase 2 sentence at its end)\n", p2_9[33][i:j + len(end)], "",
         "## Context: the Precedence rule (v9 phase1.md)\n", prec, "",
         "## Context: common.md 2.6 (lines 96-100)\n"] + com[95:100]
    (HERE / "rule.md").write_text("\n".join(R) + "\n", encoding="utf-8")
    mods = K.gt_modules()["tuning"] + K.gt_modules()["heldout"]
    rows_md = ["# v8 Phase 1 Not Kept rows that cite forwarding or relayed data (runs r0-r2), per module\n",
               "Each module: its top-entity ports, then each row (run, candidate, merged into, why), then the RTL lines the "
               "row cites (one line of context each side).\n"]
    ports_md = ["# Top-entity ports of every module (record vs non-record)\n"]
    nrows = 0
    for m in sorted(mods):
        ent, rec, non = ports(m)
        ports_md.append(f"\n## {m.replace('neorv32_', '')} ({ent})\n- record ports: {'; '.join(rec) or '-'}\n- non-record ports: {'; '.join(non) or '-'}")
        rtl = {int(mm.group(1)): l for l in CH.inputs(m)["rtl.txt"].splitlines() if (mm := re.match(r"\s*(\d+) \|", l))}
        rows = []
        for r in (0, 1, 2):
            raw = K.parse_json(json.loads((CH.run_dir(V8, "gpt-5.6-luna", r, "high") / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
            for x in raw.get("Not Kept") or []:
                t = " ".join(str(x.get(k) or "") for k in ("Candidate Name", "Why Not Kept"))
                if re.search(r"forward|relayed", t, re.I):
                    lines = sorted({n for c in cited(t) for n in (c - 1, c, c + 1) if n in rtl})
                    rows.append(f"- r{r} | candidate: {x.get('Candidate Name')} | unit: {x.get('Candidate Unit')} | merged into: "
                                f"{x.get('Merged Into') or '-'} | why: {x.get('Why Not Kept') or '-'}"
                                + ("\n  RTL:\n" + "\n".join("    " + rtl[n] for n in lines) if lines else ""))
        if rows:
            nrows += len(rows)
            rows_md.append(f"\n## {m.replace('neorv32_', '')} ({ent})\n- record ports: {'; '.join(rec) or '-'}\n- non-record ports: {'; '.join(non) or '-'}")
            rows_md += rows
    (HERE / "rows.md").write_text("\n".join(rows_md) + "\n", encoding="utf-8")
    (HERE / "ports.md").write_text("\n".join(ports_md) + "\n", encoding="utf-8")
    leaks = {f: LEAK.findall((HERE / f).read_text(encoding="utf-8")) for f in ("rule.md", "rows.md", "ports.md")}
    ok = not any(leaks.values())
    print(f"rows {nrows}; sizes " + ", ".join(f"{f} {len((HERE / f).read_text(encoding='utf-8')):,}" for f in leaks)
          + f"; leak check {'PASS' if ok else 'FAIL ' + str({k: v[:5] for k, v in leaks.items() if v})}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
