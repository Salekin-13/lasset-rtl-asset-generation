"""Direct relations between v10's Phase 1 rules (user 2026-10-16: "from the isolated rules, form clusters with rules with
related / adjacent scopes, similar functionality ... form the clusters with rules that have direct relations with each
other"). Read-only; writes p1_relations.json and p1_rules.md (every Phase 1 rule's v10 text, for the cluster agents).

Two kinds of direct relation, both from stored data (no model judgment):
  text      rule A's v10 Phase 1 text names rule B (its title, or a listed variant such as "port-buffer bar",
            "hand-off", "sequencing state") — A defers to, excepts or overrides B.
  shared    in the luna rule-alone runs of the Phase 1 wordings, A and B decide the same (module, element) in both repeats
            (a bar rule's "barred" list; a keep rule's "spared" list). Split into "both bar" (supporting) and "one bars,
            one keeps" (conflict).
Keep rules (their decision list is "spared"): Held outcomes, Hand-offs, Requests waiting for a grant, Per-region checks,
and the keep part of Serial shift registers (its port clause) — from their Outcome words (checked 2026-10-16).
Self-test: the shared count of Sequencing state and Held outcomes (P1 wordings) equals combine.py's 4 elements.

  python -B p1_relations.py
"""
import json
import os
import re
import sys
from collections import defaultdict
from itertools import combinations

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, ISOD, register  # noqa: E402

ISO = register()
import rule_breaks as RB  # noqa: E402
import analyze_isolation as AN  # noqa: E402
import p1probe as P  # noqa: E402

KEEP = {"P1-HO", "P1-10", "P1-26", "P1-24"}
VARIANTS = {"Port buffers": ["port-buffer", "port buffer"], "Hand-offs": ["hand-off"], "Sequencing state": ["sequencing state"],
            "Pacing pulses": ["pacing pulse"], "Forwarded transactions": ["forwarded transaction"], "Slices": ["slices rule"],
            "Working values": ["working value"], "Second copies": ["second cop"], "Bus handshake copies": ["handshake cop"],
            "Held outcomes, addresses and settings": ["held outcomes"], "Held addresses": ["held addresses"],
            "Buffer and engine status bits": ["status bits rule", "engine status"], "Clocks and resets": ["clocks and resets"],
            "Operation selectors": ["operation selector"], "Access command fields": ["access command field"],
            "Processor context fields": ["processor context field"], "Port options": ["port option"],
            "Serial shift registers": ["serial shift register"], "Cached copies": ["cached cop"],
            "Register read-back": ["register read-back"], "Instance-driven records": ["instance-driven"],
            "Decided-on instance outputs": ["decided-on"], "Build-time values": ["build-time"],
            "Memory access address": ["memory access address"], "Per-region checks": ["per-region"],
            "Arbitration bookkeeping": ["arbitration bookkeeping"], "Requests waiting for a grant": ["waiting for a grant"]}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    titles = {rid: t["title"] for rid, t in json.loads((ISOD / "rule_texts.json").read_text(encoding="utf-8")).items()
              if rid.startswith("P1-") and rid != "P1-22R"}
    titles["P1-HO"] = "Held outcomes, addresses and settings"
    by_title = {t: rid for rid, t in titles.items()}
    lines = (LAB / "prompts" / "two_phase_v10" / "phase1.md").read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    text = defaultdict(list)
    for a, b, t in P.blocks(lines, lines.index("OUTPUT")):
        text[P.base_title(t)].append("\n".join(lines[a:b]))
    order = P.order()
    rules = [by_title[t] for t in order if t in by_title and t in text]
    groups, refl = RB.CV.groups_and_ref()
    mods = groups["tuning"] + groups["held-out"]
    ref = {m: set(v) for m, v in refl.items()}
    R, _, _ = RB.load_latest(mods)
    dec = defaultdict(set)                                    # rid -> {(module, element)} decided in both repeats (P1 wording)
    for rid in rules:
        key = "spared" if rid in KEEP else "barred"
        for m in mods:
            a, b = R.get((rid, "P1", m, 0)), R.get((rid, "P1", m, 1))
            if a is None or b is None:
                continue
            s = {e for e in AN.names(a, key) if AN.covered(e, AN.names(b, key))}
            if rid == "P1-16":                               # Serial shift registers also keeps its port
                pass
            dec[rid] |= {(m, e) for e in s}
    edges = {}
    for a, b in combinations(rules, 2):
        ta, tb = " ".join(text[titles[a]]).lower(), " ".join(text[titles[b]]).lower()
        names_b = [titles[b].lower().split(",")[0]] + VARIANTS.get(titles[b], [])
        names_a = [titles[a].lower().split(",")[0]] + VARIANTS.get(titles[a], [])
        t_ab = any(n in ta for n in names_b)
        t_ba = any(n in tb for n in names_a)
        shared = set()
        for (m, e) in dec[a]:
            if any(m == m2 and (e == e2 or e.startswith(e2 + ".") or e2.startswith(e + ".")) for (m2, e2) in dec[b]):
                shared.add((m, e))
        kind = "conflict" if (a in KEEP) != (b in KEEP) else "support"
        if t_ab or t_ba or shared:
            edges[f"{a}|{b}"] = {"a": a, "b": b, "a names b": t_ab, "b names a": t_ba, "shared elements": len(shared),
                                 "shared kind": kind if shared else None,
                                 "shared reference": sum(1 for (m, e) in shared if e in ref[m]),
                                 "examples": sorted(f"{m[8:]}:{e}" for m, e in shared)[:6]}
    st = edges.get("P1-15|P1-HO") or edges.get("P1-HO|P1-15")
    ok = st is not None and st["shared elements"] == 4
    print(f"self-test (Sequencing state x Held outcomes shared = combine.py's 4): {'PASS' if ok else 'FAIL'} ({st and st['shared elements']})")
    out = {"rules": [{"id": r, "title": titles[r], "kind": "keep" if r in KEEP else "bar", "decided (module, element) pairs": len(dec[r]),
                      "modules": sorted({m[8:] for m, _ in dec[r]})} for r in rules], "edges": edges}
    (HERE / "p1_relations.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    md = ["# v10 Phase 1 rules (exact text) with their rule-alone decisions", ""]
    for r in out["rules"]:
        md += [f"## {r['id']} {r['title']} ({r['kind']}; decides {r['decided (module, element) pairs']} (module, element) pairs alone; modules {r['modules']})", "",
               "```", "\n".join(text[r["title"]]), "```", ""]
    (HERE / "p1_rules.md").write_text("\n".join(md), encoding="utf-8")
    print(f"{len(rules)} Phase 1 rules; {len(edges)} directly related pairs "
          f"({sum(1 for e in edges.values() if e['a names b'] or e['b names a'])} by text, {sum(1 for e in edges.values() if e['shared elements'])} by shared elements)")
    for k, e in sorted(edges.items(), key=lambda kv: -kv[1]["shared elements"]):
        print(f"  {titles[e['a']][:26]:26s} - {titles[e['b']][:26]:26s} text {'A>B' if e['a names b'] else '   '} {'B>A' if e['b names a'] else '   '} "
              f"shared {e['shared elements']:3d} {e['shared kind'] or '':8s} ref {e['shared reference']}")


if __name__ == "__main__":
    main()
