"""Evidence dossiers for the v10 rule rewrite, one per group of related rules. Code only; writes dossiers/G<k>.md.

Per rule: the job (reword + structure, or structure only), the v9 Phase 1 text and the v9 Phase 2 sentences (S-ids, in
prompt order, with their neighbours), word counts, and the evidence from the isolation analysis:
  two-reading groups (clause_contradictions.json), contradiction details with both runs' words (isolation_report.json),
  one-sided reader verdicts (onesided/verdicts.json + key.json), Phase 1 / Phase 2 contradictions with both wordings'
  words (read from the stored replies), the code-checked Phase 1 / Phase 2 text divergences (text_conflicts.json), the
  pattern coverage (pattern_coverage.json) and the v8 design targets that touch the rule, and the RTL paths of every
  module named.

  python -B make_dossiers.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISOD = HERE.parents[0].parent / "rule_isolation_v9"
sys.path.insert(0, str(ISOD))
import isolation as ISO  # noqa: E402
import analyze_isolation as A  # noqa: E402

CH = ISO.CH
GROUPS = {
    "G1": ["P1-05", "P1-07"],
    "G2": ["P1-23", "P1-22", "P1-27"],
    "G3": ["P1-04", "P1-02"],
    "G4": ["P1-08", "P1-09"],
    "G5": ["P1-14", "P1-17", "P1-10"],
    "G6": ["P1-16", "P1-15"],
    "G7": ["P1-18", "P1-24", "P1-06"],
}
STRUCTURE_ONLY = {"P1-15", "P1-18", "P1-24", "P1-06"}
WHY = {
    "P1-05": "read two ways in 7 modules (28 signals); Phase 1 / Phase 2 conflict on OR-merged bus responses (decision D2)",
    "P1-07": "read two ways in 5 modules (9 signals)",
    "P1-23": "read two ways in 10 modules (12 signals)",
    "P1-22": "read two ways in 6 modules (12 signals); start from v9 (decision D4)",
    "P1-27": "read two ways in 2 modules (7 signals)",
    "P1-04": "read two ways in 3 modules (7 signals); its Phase 1 bar takes an enable input another rule was written to keep (decision D8)",
    "P1-02": "unclear wording in 3 of 10 sampled one-sided cases (and 7 over-applied)",
    "P1-08": "read two ways in 6 modules (7 signals); Phase 2 has an exception Phase 1 lacks (decision D3)",
    "P1-09": "unclear wording in 7 of 10 sampled one-sided cases",
    "P1-14": "Phase 1 wording unclear in 4 of 5 sampled one-sided cases; 18 contradictions are the same clause filed both ways",
    "P1-17": "read two ways in 4 modules (6 signals)",
    "P1-10": "read two ways in 5 modules (18 signals)",
    "P1-16": "Phase 2 wording unclear in 4 of 5 sampled one-sided cases",
    "P1-15": "over-applied in 10 of 10 sampled one-sided cases: structure only",
    "P1-18": "over-applied in 9 of 10 sampled one-sided cases: structure only",
    "P1-24": "over-applied in 4 of 5 sampled one-sided cases: structure only",
    "P1-06": "over-applied in 3 of 5 sampled one-sided cases: structure only",
}


def words_for(rid, ph, m, e):
    out = []
    for r in (0, 1):
        p = ISO.path(rid, ph, m, r)
        if not p.exists():
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))["reply"] or {}
        for k in ("barred", "spared", "unsure"):
            for x in rec.get(k) or []:
                if isinstance(x, dict) and x.get("element") and A.covered(e, {x["element"]}):
                    out.append(f"{ph} run {r} {k} `{x['element']}`: \"{x.get('rule words')}\" | why: {x.get('why')} | lines {x.get('lines')}")
    return out[:4]


def main():
    texts = json.loads((ISOD / "rule_texts.json").read_text(encoding="utf-8"))
    idx = json.loads((ISOD / "pack" / "index.json").read_text(encoding="utf-8"))
    rmap = json.loads((ISOD / "rule_map.json").read_text(encoding="utf-8"))
    rep = json.loads((ISOD / "isolation_report.json").read_text(encoding="utf-8"))
    cc = json.loads((ISOD / "clause_contradictions.json").read_text(encoding="utf-8"))
    ver = json.loads((ISOD / "onesided" / "verdicts.json").read_text(encoding="utf-8"))
    key = json.loads((ISOD / "onesided" / "key.json").read_text(encoding="utf-8"))
    tc = json.loads((ISOD / "text_conflicts.json").read_text(encoding="utf-8"))["kept divergences"]
    pc = json.loads((ISOD / "pattern_coverage.json").read_text(encoding="utf-8"))
    sids = sorted(idx["p2"])
    out = HERE / "dossiers"
    out.mkdir(exist_ok=True)
    index = {}
    for g, rules in GROUPS.items():
        L = [f"# Dossier {g}: {', '.join(texts[r]['title'] for r in rules)}\n",
             "Read STRUCTURE_SPEC.md (same folder) first. Evidence below is from the rule-isolation run (each rule alone, 41 modules,",
             "2 runs) and its analyses. 'r0' / 'r1' are the two runs. RTL: each module's rtl.txt ('line | text') and closed_set.json.\n"]
        mods = set()
        for rid in rules:
            t = texts[rid]
            job = "structure only" if rid in STRUCTURE_ONLY else "reword, then structure"
            L.append(f"\n---\n\n## {rid} {t['title']}: {job}\nWhy: {WHY[rid]}.\n")
            L.append(f"### v9 Phase 1 wording ({len((t.get('P1') or '').split())} words)\n\n" + (t.get("P1") or "(none)") + "\n")
            mine = [s for s in sids if rmap[s]["unit"].startswith(rid)]
            L.append(f"### v9 Phase 2 sentences ({len((t.get('P2') or '').split())} words), phase2.md line 34, in prompt order")
            for s in mine:
                i = sids.index(s)
                prev_s, next_s = (sids[i - 1] if i else None), (sids[i + 1] if i + 1 < len(sids) else None)
                ctx = f"(before: {prev_s} [{rmap[prev_s]['unit'][:30]}]; after: {next_s} [{rmap[next_s]['unit'][:30]}])" if prev_s and next_s else ""
                L.append(f"- {s} {ctx}: {idx['p2'][s]['text']}")
            L.append("")
            # two readings
            for ph in ("P1", "P2"):
                c = cc.get(f"{rid} {ph}")
                if c and c["reading-difference groups"]:
                    L.append(f"### Read two ways ({ph} wording): {c['different clauses']} signals in {c['modules with a reading difference']} modules "
                             f"(plus {c['same clause']} filed both ways under the same clause, a reply-format effect)")
                    for gr in c["reading-difference groups"][:6]:
                        L.append(f"- {gr['elements']} signals / {gr['modules']} modules. BAR clause: \"{gr['barred by clause']}\" | KEEP clause: \"{gr['kept by clause']}\" | e.g. {', '.join(gr['examples'][:4])}")
                        mods |= {x.split(':')[0] for x in gr["examples"][:4]}
                    for d in (rep.get(rid, {}).get(ph, {}).get("contradiction details") or [])[:3]:
                        L.append(f"  - detail {d['case']}:")
                        for two in d["repeats"]:
                            for x in two[:2]:
                                L.append(f"    - run {x['repeat']} {x['list']} `{x['element']}`: \"{x['rule words']}\" | why: {x['why']}")
                    L.append("")
            # one-sided verdicts
            os_ = [(cid, v) for cid, v in ver.items() if key.get(cid, {}).get("rule") == rid]
            if os_:
                L.append("### One-sided differences (one run lists the signal, the other does not mention it), judged by a reader against the RTL")
                for cid, v in sorted(os_):
                    k = key[cid]
                    mods.add(k["module"])
                    L.append(f"- {cid} {k['module']} `{k['element']}` ({k['phase']}): **{v['verdict']}** | words: \"{v['words']}\" | {v['reason']}")
                L.append("")
            # phase contradictions
            pco = rep.get(rid, {}).get("phase contradictions") or []
            if pco:
                L.append(f"### Phase 1 vs Phase 2 wording (stable in both runs of each, opposite lists): {len(pco)} signals")
                for c in pco[:6]:
                    L.append(f"- {c}")
                for c in pco[:3]:
                    m, rest = c.split(":", 1)
                    e = rest.split(" (")[0]
                    mods.add(m)
                    for ph in ("P1", "P2"):
                        for w in words_for(rid, ph, m, e)[:2]:
                            L.append(f"  - {w}")
                L.append("")
            # text conflicts
            mine_tc = [x for x in tc if x["unit"] == rid]
            if mine_tc:
                L.append("### Phase 1 / Phase 2 text divergences found earlier (quotes code-checked verbatim)")
                for x in mine_tc:
                    L.append(f"- [{x['severity']}, {x['kind']}] P1: {x['p1_quote']} | P2: {x['p2_quote']} | case: {x['case_decided_differently']} | effect: {x['effect']}")
                L.append("")
            # pattern coverage and design targets
            pats = [(k, v) for k, v in pc["patterns"].items() if t["title"] in v["rules"]]
            if pats:
                L.append("### Code-defined pattern of this bar (v7 detectors over all 41 modules) and what the rule alone barred")
                for k, v in pats:
                    L.append(f"- {v['pattern']}: {v['instances']} signals in {v['modules']} modules; barred alone {v['barred alone']}; never barred e.g. {v['never barred, examples'][:5]}")
                L.append("")
            tg = [(rk, x) for rk, d in pc["v8 design targets"].items() for x in d["targets"] if x["rule"] == t["title"]]
            if tg:
                L.append("### Signals a v8 rule was written to recover that this rule decides")
                for rk, x in tg:
                    L.append(f"- {rk} {x['signal']} ({x['wording']}): kept in {x['kept in runs']} of 2 runs, barred in {x['barred in runs']} of 2")
                L.append("")
            index[rid] = {"group": g, "job": job, "P2 sentence ids": mine}
        L.append("\n## RTL and closed-set paths of the modules named above")
        for m in sorted(mods):
            if m.startswith("neorv32_"):
                L.append(f"- {m}: {CH.module_dir(m) / 'rtl.txt'} ; {CH.module_dir(m) / 'closed_set.json'}")
        (out / f"{g}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    for g in GROUPS:
        print(g, (out / f"{g}.md").stat().st_size, "bytes")


if __name__ == "__main__":
    main()
