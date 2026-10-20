"""Evidence packs for the conflicting rule pairs of REPORT.md section 7 (user 2026-10-16: identify the relationship of each
conflict, fix it with precedence / conditional precedence / scope, and test it). Read-only; writes conflict_packs/<id>.md
and conflict_packs/index.json. Sends nothing.

Per pair: both rules' exact v10 texts (each wording), the precedence sentences v10 already has, every element both rules
decide in both rule-alone repeats (the bar's and the keep rule's quoted words, reasons and lines), each element's
closed-set entry, whether the reference lists it, and v10's label in each run with its justification; plus, for the
boundary cases, the elements in the same modules that only one of the two rules decides.

  python -B make_conflict_packs.py
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, ISOD, register  # noqa: E402

ISO = register()
import rule_breaks as RB  # noqa: E402
import analyze_isolation as AN  # noqa: E402
import make_blind_packs as MB  # noqa: E402

CH = RB.CH
PAIRS = {  # id -> (bar rule, bar phases, keep rule, keep phase)
    "C1": ("P1-14", ("P1", "P2"), "P2X-side-by-side-port-signal-into-instance", "P2"),
    "C2": ("P1-05", ("P2",), "P2X-input-port-setting-the-value", "P2"),
    "C3": ("P1-15", ("P1", "P2"), "P1-HO", "P1"),
    "C4": ("P1-20", ("P1",), "P1-HO", "P1"),
    "C5": ("P1-04", ("P1",), "P1-HO", "P1"),
    "C6": ("P1-17", ("P1",), "P2X-unmixed-copy-output-port", "P2"),
    # added 2026-10-16 after the user asked about the other pairs: the two with the most v10 primaries outside the table
    "C7": ("P1-10", ("P1",), "P2X-side-by-side-port-signal-into-instance", "P2"),
    "C8": ("P1-10", ("P1",), "P1-HO", "P1"),
}


def text_of(rid, ph):
    src = RB.source(rid, ph)
    ISO.use(src)
    t = json.loads(ISO.texts_file().read_text(encoding="utf-8")).get(rid, {})
    ISO.use("v9")
    return t.get("title", rid), t.get(ph)


def items(rp, key):
    return {x.get("element"): x for x in (rp or {}).get(key) or [] if isinstance(x, dict) and x.get("element")}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, refl = RB.CV.groups_and_ref()
    mods = groups["tuning"] + groups["held-out"]
    ref = {m: set(v) for m, v in refl.items()}
    R, _, _ = RB.load_latest(mods)
    lst, _ = RB.primaries(RB.V10, mods)
    out = LAB / "analysis" / "v10_diagnosis" / "conflict_packs"
    out.mkdir(exist_ok=True)
    p1 = (LAB / "prompts" / "two_phase_v10" / "phase1.md").read_text(encoding="utf-8")
    p2 = (LAB / "prompts" / "two_phase_v10" / "phase2.md").read_text(encoding="utf-8")
    prec1 = next(l for l in p1.splitlines() if l.startswith("- Precedence."))
    prec2 = [s.strip() for s in p2.replace("\r\n", "\n").split("\n") if "Each bar in this step" in s or "spared only from that rule" in s]
    index = {}
    for cid, (bar, bphs, keep, kph) in PAIRS.items():
        L = [f"# Conflict pair {cid}: bar {bar} vs keep {keep}", ""]
        for rid, phs in ((bar, bphs), (keep, (kph,))):
            for ph in ("P1", "P2"):
                title, t = text_of(rid, ph)
                if t:
                    L += [f"## {rid} \"{title}\", {ph} wording{' (in the pair)' if ph in phs else ' (other phase)'}", "", "```", t, "```", ""]
        L += ["## Precedence sentences v10 already has", "", f"- Phase 1: {prec1}"] + [f"- Phase 2: {x[:900]}" for x in prec2] + [""]
        shared, onlybar, onlykeep = [], {}, {}
        for m in mods:
            kreps = [R.get((keep, kph, m, r)) for r in (0, 1)]
            if None in kreps:
                continue
            kc = {e for e in AN.names(kreps[0], "spared") if e in AN.names(kreps[1], "spared")}
            for bph in bphs:
                breps = [R.get((bar, bph, m, r)) for r in (0, 1)]
                if None in breps:
                    continue
                bc = {e for e in AN.names(breps[0], "barred") if AN.covered(e, AN.names(breps[1], "barred"))}
                both = sorted(e for e in kc if RB.down(e, bc))
                for e in both:
                    shared.append((m, e, bph, breps, kreps))
                if both:
                    onlybar[m] = sorted(bc - set(both))[:8]
                    onlykeep[m] = sorted(kc - set(both))[:8]
        seen = set()
        L.append("## Elements both rules decide alone, in both repeats (the conflict cases)")
        for m, e, bph, breps, kreps in shared:
            if (m, e) in seen:
                continue
            seen.add((m, e))
            ent, fx = MB.closed_entry(m, e)
            cp = {k: [y.get("element") for y in v][:10] for k, v in (fx.get("counterparts") or {}).items()}
            L.append(f"### {m[8:]}:{e}  (reference: {e in ref[m]}; v10 primary runs {sum(e in lst[(r, m)] for r in (0, 1, 2))}/3; "
                     f"RTL {CH.module_dir(m) / 'rtl.txt'})")
            L.append(f"- closed set: entity {ent}; {'port ' + str(fx.get('direction')) if fx.get('port') else 'signal'}; role "
                     f"{fx.get('role in RTL')}; lines {fx.get('occurrence lines')}; counterparts {json.dumps(cp, ensure_ascii=False)}")
            for r in (0, 1):
                bi = items(breps[r], "barred").get(e) or next((x for k, x in items(breps[r], "barred").items() if e.startswith(k + ".")), {})
                ki = items(kreps[r], "spared").get(e, {})
                L.append(f"- bar {bar} {bph} repeat {r}: \"{bi.get('rule words', '')}\" | {bi.get('why', '')} | lines {bi.get('lines')}")
                L.append(f"- keep {keep} {kph} repeat {r}: \"{ki.get('rule words', '')}\" | {ki.get('why', '')} | lines {ki.get('lines')}")
            for t in MB.rows_for(0, m, e) + MB.rows_for(1, m, e) + MB.rows_for(2, m, e):
                L.append(f"- v10 {t[:400]}")
            L.append("")
        L.append("## Boundary cases: elements in the same modules that only one rule decides (consistent, both repeats)")
        for m in sorted(onlybar):
            L.append(f"- {m[8:]}: only the bar: {onlybar[m]}; only the keep rule: {onlykeep[m]}")
        (out / f"{cid}.md").write_text("\n".join(L), encoding="utf-8")
        index[cid] = {"bar": bar, "bar phases": list(bphs), "keep": keep, "keep phase": kph,
                      "conflict elements": sorted({f"{m[8:]}:{e}" for m, e, *_ in shared}),
                      "modules": sorted({m for m, *_ in shared}),
                      "reference among them": sum(1 for (m, e) in seen if e in ref[m]),
                      "v10 primary runs": sum(sum(e in lst[(r, m)] for r in (0, 1, 2)) for (m, e) in seen),
                      "boundary only-bar": {m[8:]: v for m, v in onlybar.items()}, "boundary only-keep": {m[8:]: v for m, v in onlykeep.items()}}
        print(cid, bar, "vs", keep, "| elements", len(seen), "| ref", index[cid]["reference among them"], "| v10 primary runs", index[cid]["v10 primary runs"])
    (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
