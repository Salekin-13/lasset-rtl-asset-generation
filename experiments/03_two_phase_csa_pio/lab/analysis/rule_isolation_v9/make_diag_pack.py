"""Diagnosis packs for the rewritten rules that did worse in the re-test (v10r) than in the v9 isolation test. Code only;
writes diag_v10r/D<k>.md.

Per rule: the v9 and the v10r wording, the comparison numbers (compare_v10r.json), the new two-reading groups
(clause_contradictions_v10r.json) with both runs' quoted words and reasons for up to 3 cases per group, and the
signals of a lost code-defined pattern with each run's entry in v9 and v10r; RTL paths of every module named.

  python -B make_diag_pack.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402
import analyze_isolation as A  # noqa: E402

CH = ISO.CH
PACKS = {
    "D1": {"P1-05": ["P1", "P2"], "P1-22": ["P1"], "P1-04": ["P1"]},
    "D2": {"P1-15": ["P1", "P2"], "P1-09": ["P1", "P2"], "P1-17": ["P1", "P2"]},
    "D3": {"P1-06": ["P1", "P2"], "P1-02": ["P2"], "P1-10": ["P1"]},
}
NOTES = {
    "P1-05": "Phase 2 now has 18 two-reading signals in 8 modules (v9: 2 in 2). Phase 1 halved its two readings (26 -> 13) but bars "
             "fewer records only wired to an instance: 43 of 105 in both runs (v9 61), the lost ones in xbus and cpu. Decision D2 "
             "(merging bus responses is forwarding) is not met in Phase 2: bus int_rsp / main_rsp are kept in run 0, barred in run 1.",
    "P1-22": "Phase 1 two readings rose 3 -> 10 (cpu_control: decoded flags vs 'a start command or pulse').",
    "P1-04": "Phase 1 two readings rose 0 -> 7 (cpu_cp_fpu done pulses vs 'a start pulse ... decoded from a received command').",
    "P1-15": "Restructured only (no word changed except scope punctuation). Phase 1 two readings rose 2 -> 12 in 7 modules; one-sided "
             "differences 40 -> 50 over both wordings; stable bars fell 71 -> 43 (P1) and 91 -> 46 (P2).",
    "P1-09": "Two readings rose 1 -> 5.",
    "P1-17": "Two readings rose 6 -> 9; Phase 2 one-sided differences 37 -> 107.",
    "P1-06": "Restructured only. Its code-defined pattern (registers copying another register; none in the reference): barred in both "
             "runs 13 -> 6 of 14 (P1), 11 -> 8 (P2); applied-once modules 3 -> 6.",
    "P1-02": "Phase 2 stable bars 26 -> 112 (now agreeing with Phase 1: stable P1/P2 disagreements 97 -> 8), but 3 reference signals "
             "(exact names) are now barred in both runs (v9 0).",
    "P1-10": "Two readings 18 -> 0, but its Phase 1 wording now lists 4 reference signals (exact names) under 'barred' in both runs "
             "(v9 0). Hand-offs is a rule that keeps signals as pieces; check what 'barred' means for these 4.",
}


def entries(R, rid, ph, m, e):
    out = []
    for r in (0, 1):
        rep = R.get((rid, ph, m, r))
        if rep is None:
            out.append(f"run {r}: reply missing")
            continue
        hit = [f"{k} `{x['element']}`: \"{x.get('rule words')}\" | why: {x.get('why')}" for k in ("barred", "spared", "unsure")
               for x in rep.get(k) or [] if isinstance(x, dict) and x.get("element") and A.covered(e, {x["element"]})]
        out.append(f"run {r}: " + (" ; ".join(hit[:2]) if hit else "not mentioned"))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    t9 = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    t10 = json.loads((HERE / "rule_texts_v10r.json").read_text(encoding="utf-8"))
    cmp_ = json.loads((HERE / "compare_v10r.json").read_text(encoding="utf-8"))
    cc10 = json.loads((HERE / "clause_contradictions_v10r.json").read_text(encoding="utf-8"))
    R9 = A.load(lambda r: ISO.run_root(rep=r))
    ISO.use("v10r")
    R10 = A.load(lambda r: ISO.run_root(rep=r))
    ISO.use("v9")
    import pattern_coverage as PC
    hits, ok, _ = PC.scan()
    pat = {"P1-06": [(m, n) for fx, t, m, en, n in hits if fx == "P1" and t == "COPY"],
           "P1-05": [(m, n) for fx, t, m, en, n in hits if fx == "P1" and t == "RECORD" and m.split("_", 1)[1] in ("xbus", "cpu")]}
    out = HERE / "diag_v10r"
    out.mkdir(exist_ok=True)
    for d, rules in PACKS.items():
        L = [f"# Diagnosis pack {d}\n",
             "Context: each rule was applied ALONE by a model to each of 41 hardware modules, twice ('run 0', 'run 1'), first in its",
             "v9 wording, then in a rewritten v10 wording (reworded and/or restructured into Scope / Criteria / Exceptions / Outcome /",
             "Evidence slots, with a shared procedure: check scope, then each criterion, then each exception; a criterion the RTL or",
             "the named evidence does not show is not met). A 'two-reading' case: one run bars a signal quoting one clause, the other",
             "keeps it quoting another clause of the same text. The rewrite made the numbers below worse for these rules.\n"]
        mods = set()
        for rid, phs in rules.items():
            L.append(f"\n---\n\n## {rid} {t9[rid]['title']}\n\n{NOTES[rid]}\n")
            for ph in phs:
                a, b = cmp_["v9"][rid].get(ph, {}), cmp_["v10r"][rid].get(ph, {})
                L.append(f"### {ph} wording: v9 -> v10")
                L.append(f"- numbers v9: {json.dumps(a)}\n- numbers v10: {json.dumps(b)}\n")
                L.append("v9 text:\n```\n" + (t9[rid].get(ph) or "") + "\n```\nv10 text (tested):\n```\n" + (t10[rid].get(ph) or "") + "\n```\n")
                for g in cc10.get(f"{rid} {ph}", [])[:4]:
                    L.append(f"- Two readings in v10: {g['n']} signals / {g['modules']} modules. BAR clause: \"{g['bar']}\" | KEEP clause: \"{g['keep']}\"")
                    for ex in g["examples"][:3]:
                        m, e = ex.split(":", 1)
                        mods.add(m)
                        L += [f"  - {ex}: " + w for w in entries(R10, rid, ph, m, e)]
                L.append("")
            if rid in pat:
                L.append("### Code-defined pattern signals: each run's entry (v9 | v10)")
                for m, n in sorted(pat[rid]):
                    for ph in phs:
                        e9, e10 = entries(R9, rid, ph, m, n), entries(R10, rid, ph, m, n)
                        b9 = all("barred" in x.split(":", 1)[1][:9] for x in e9)
                        b10 = all("barred" in x.split(":", 1)[1][:9] for x in e10)
                        if b9 != b10:
                            mods.add(m)
                            L.append(f"- {m}:{n} ({ph}) v9: {' / '.join(e9)}  ||  v10: {' / '.join(e10)}")
                L.append("")
            if rid == "P1-05":
                L.append("### Merged bus responses in bus (decision D2: merging several ports' responses is forwarding), Phase 2 wording")
                for n in ("int_rsp", "int_rsp.data", "main_rsp", "main_rsp.data"):
                    L += [f"- neorv32_bus:{n}: " + w for w in entries(R10, "P1-05", "P2", "neorv32_bus", n)]
                mods.add("neorv32_bus")
            if rid in ("P1-02", "P1-10"):
                _, refl = __import__("compare_versions").groups_and_ref()
                for ph in phs:
                    have = {k[2] for k in R10 if k[0] == rid and k[1] == ph}
                    for m in sorted(have):
                        D = [A.names(R10.get((rid, ph, m, r), {}), "barred") for r in (0, 1)]
                        for e in sorted(D[0]):
                            if A.covered(e, D[1]) and e in set(refl.get(m, [])):
                                mods.add(m)
                                L.append(f"- reference signal barred in both v10 runs: {m}:{e} ({ph})")
                                L += [f"  - {w}" for w in entries(R10, rid, ph, m, e)]
                L.append("")
        L.append("\n## RTL and closed-set paths")
        L += [f"- {m}: {CH.module_dir(m) / 'rtl.txt'} ; {CH.module_dir(m) / 'closed_set.json'}" for m in sorted(mods) if m.startswith("neorv32_")]
        (out / f"{d}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
        print(d, (out / f"{d}.md").stat().st_size, "bytes")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE.parent / "heldout_versions__gpt-5.6-luna__high__r0-r2"))
    main()
