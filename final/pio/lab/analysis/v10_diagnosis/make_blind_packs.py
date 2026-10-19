"""Evidence packs for writing rules for the blind spots (user 2026-10-16 07:24: "create rules for them ... create a bar
for the reference and record the decision in the log"). Read-only on runs and inputs; writes blind_packs/<unit>.md and
blind_packs/index.json. Sends nothing.

Each unit groups blindspots.py patterns that one rule could address. A pack lists, per element: the module, entity,
closed-set entry (kind, direction, role, occurrence lines, counterparts), whether the reference lists it, v10's label in
each run with its justification and the concept it was walked under (Phase 1 name and information), or, for a miss,
where it was lost and the reply's words; the reference members of the same groups (a rule must spare them); and the
RTL file to read.

Check printed: the pairs each pack holds, against blindspots.py's unaddressed totals (packs need not cover every pair:
the patterns below the size cut are left out and listed).

  python -B make_blind_packs.py
"""
import json
import os
import sys
from collections import defaultdict

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, register  # noqa: E402

ISO = register()
import rule_breaks as RB  # noqa: E402

CH, T, CV, K = RB.CH, RB.T, RB.CV, RB.K
V10 = RB.V10
OUT = HERE / "blind_packs"
# unit -> (kind, [(module, stem or None, explicit names or None)])
UNITS = {
    "U1_control_unit_state": ("FP", [("neorv32_cpu_control", "csr", None), ("neorv32_cpu_control", "trap_ctrl", None),
                                     ("neorv32_cpu_control", "exe_engine", None)]),
    "U2_control_record_naming": ("FP+FN", [("neorv32_cpu_alu", "ctrl_i", None), ("neorv32_cpu_lsu", "ctrl_i", None),
                                           ("neorv32_cpu_frontend", "ctrl_i", None), ("neorv32_cpu_cp_bitmanip", "ctrl_i", None),
                                           ("neorv32_cpu_cp_shifter", "ctrl_i", None)]),
    "U3_handshake_and_sampling_flags": ("FP", [("neorv32_twd", "smp", None), ("neorv32_cpu_cp_fpu", "ctrl_engine", None),
                                               ("neorv32_cpu_control", None, ["illegal_cmd", "csr_valid"]),
                                               ("neorv32_cpu_cp_bitmanip", None, ["valid_cmd"]), ("neorv32_cpu_cp_shifter", None, ["valid_cmd"]),
                                               ("neorv32_cpu_cp_crypto", None, ["cmd_valid"]), ("neorv32_sdi", None, ["serial.start"])]),
    "U4_debug_module_registers": ("FP", [("neorv32_debug_dm", "dm_reg", None), ("neorv32_debug_dm", "dm_ctrl", None)]),
    "U5_peripheral_settings": ("FP", [("neorv32_neoled", "ctrl", None), ("neorv32_twd", "ctrl", None), ("neorv32_onewire", "ctrl", None)]),
    "U6_output_ports_missed": ("FN", "*_o"),
    "U7_input_ports_missed": ("FN", "*_i"),
    "U8_ports_listed": ("FP", "*_o FP"),
    "U9_memory_arrays": ("FP", [("neorv32_dmem", None, ["mem_ram_b0", "mem_ram_b1", "mem_ram_b2", "mem_ram_b3"]),
                                ("neorv32_imem", None, ["mem_ram_b0", "mem_ram_b1", "mem_ram_b2", "mem_ram_b3"])]),
    "U10_input_ports_listed": ("FP", "*_i FP"),          # round 2 (combine_round1.json): input ports listed, no rule bars them
}


def closed_entry(m, n):
    for (e, x), fx in CH.closed_names(m).items():
        if x == n:
            return e, fx
    return None, {}


def p1_concepts(r, m):
    rec = T.load(V10, r, m, 1)
    return {c.get("id"): c for c in (CH.phase1_concepts(rec.get("reply")) or [])}


def rows_for(r, m, n):
    p2 = T.load(V10, r, m, 2)["reply"] or {}
    cons = p1_concepts(r, m)
    out = []
    for a in p2.get("structural assets") or []:
        if isinstance(a, dict) and (a.get("element") == n or n in CH.as_list(a.get("same role"))):
            c = cons.get(a.get("concept id")) or {}
            info = str(c.get("information") or "")[:160]
            out.append(f"r{r} {a.get('label')} under {a.get('concept id')} \"{c.get('concept') or ''}\" ({info}): {a.get('justification') or ''}")
    for x in p2.get("not reported") or []:
        if isinstance(x, dict) and x.get("element") == n:
            out.append(f"r{r} not reported under {x.get('concept id')}: {x.get('reason') or ''}")
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, refl = CV.groups_and_ref()
    mods = groups["tuning"] + groups["held-out"]
    ref = {m: set(v) for m, v in refl.items()}
    bs = json.loads((HERE / "blindspots.json").read_text(encoding="utf-8"))
    fpl = [(("neorv32_" + s.split(":")[0]), s.split(":")[1].rsplit(" r", 1)[0], int(s.rsplit(" r", 1)[1])) for s in bs["FP unaddressed list"]]
    fnl = []
    for s in bs["FN unaddressed list"]:
        a, st = s.rsplit(" (", 1)
        fnl.append(("neorv32_" + a.split(":")[0], a.split(":")[1].rsplit(" r", 1)[0], int(a.rsplit(" r", 1)[1]), st.rstrip(")")))
    lst, _ = RB.primaries(V10, mods)
    OUT.mkdir(exist_ok=True)
    index = {}
    for unit, (kind, spec) in UNITS.items():
        els = defaultdict(list)                              # (m, n) -> unaddressed runs
        if spec == "*_o":
            for m, n, r, st in fnl:
                if n.endswith("_o") and "." not in n:
                    els[(m, n)].append((r, st))
        elif spec == "*_i":
            for m, n, r, st in fnl:
                if n.endswith("_i") and "." not in n:
                    els[(m, n)].append((r, st))
        elif spec in ("*_o FP", "*_i FP"):
            suf = spec[1:3]
            for m, n, r in fpl:
                if n.endswith(suf) and "." not in n:
                    els[(m, n)].append((r, "FP"))
        else:
            for m, stem, names in spec:
                for (mm, n, r) in fpl:
                    if mm == m and ((stem and n.split(".")[0] == stem) or (names and n in names)):
                        els[(m, n)].append((r, "FP"))
                for (mm, n, r, st) in fnl:
                    if mm == m and ((stem and n == stem) or (names and n in names)):
                        els[(m, n)].append((r, st))
        lines = [f"# Evidence pack {unit} ({kind})", "",
                 "Unaddressed = no rule of v10 bars it alone (false positive) or bars or keeps it alone (miss), in its luna "
                 "rule-alone runs (blindspots.py). v10 = gpt-5.6-luna, high, runs r0-r2, all 41 modules.", ""]
        mods_u = sorted({m for m, _ in els})
        for m in mods_u:
            d = CH.module_dir(m)
            lines.append(f"## {m}  (RTL with line numbers: {d / 'rtl.txt'}; closed set: {d / 'closed_set.json'}; "
                         f"diagram: {d / 'diagram.txt'})")
            stems = {n.split(".")[0] for (mm, n) in els if mm == m}
            same = sorted(x for x in ref[m] if x.split(".")[0] in stems)
            lines.append(f"Reference entries in the same groups ({', '.join(sorted(stems))}): {same or 'none'}; their v10 primary "
                         f"runs: {[(x, sum(x in lst[(r, m)] for r in (0, 1, 2))) for x in same]}")
            lines.append(f"All reference entries of this module: {sorted(ref[m])}")
            for (mm, n), runs in sorted(els.items()):
                if mm != m:
                    continue
                e, fx = closed_entry(m, n)
                cp = {k: [y.get("element") for y in v][:12] for k, v in (fx.get("counterparts") or {}).items()}
                lines.append(f"- **{n}** (entity {e}; {'port ' + str(fx.get('direction')) if fx.get('port') else 'signal'}; role "
                             f"{fx.get('role in RTL')}; lines {fx.get('occurrence lines')}; reference: {n in ref[m]}; unaddressed runs: "
                             f"{sorted(runs)}; v10 primary runs: {sum(n in lst[(r, m)] for r in (0, 1, 2))})")
                lines.append(f"  counterparts: {json.dumps(cp, ensure_ascii=False)}")
                for r in (0, 1, 2):
                    for t in rows_for(r, m, n):
                        lines.append(f"  {t}")
                    if kind != "FP" and n not in lst[(r, m)]:
                        st, why = T.where_lost(V10, r, m, n, lst[(r, m)])
                        lines.append(f"  r{r} lost at: {st}: {' | '.join(str(w) for w in why)[:600]}")
            lines.append("")
        (OUT / f"{unit}.md").write_text("\n".join(lines), encoding="utf-8")
        index[unit] = {"kind": kind, "modules": [m[8:] for m in mods_u], "elements": len(els),
                       "pairs": sum(len(v) for v in els.values()),
                       "element list": sorted(f"{m[8:]}:{n}" for (m, n) in els)}
    (OUT / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    covered = sum(x["pairs"] for x in index.values())
    print(json.dumps(index, indent=1))
    print(f"pairs in packs: {covered} (unaddressed: FP {len(fpl)}, FN {len(fnl)})")


if __name__ == "__main__":
    main()
