"""Stage prompts for the staged test (PLAN.md Step D): v10's Phase 2 prompt with only a chosen set of rules.

build_p2(keep, last=None, add_after=None) rebuilds v10's phase2.md from v9's indexed sentences exactly as
prompt_builds/v10/make_v10.py does, but keeps only the rules in `keep`:
  - "general" sentences (step text), the Precedence sentences (P1-01) and the shared "Reading a rule" sentence are the
    CORE and are always kept (the procedure stays at its v10 place even when no rewritten rule is kept);
  - a rule's Phase 2 text (its v10 block, its in-place sentences, or its v9 sentences; P2X-* clauses; and line 35/157,
    the Phase 2 wording of Requests waiting for a grant, rule id P1-26) is kept only if its id is in `keep`;
  - last: a rule id written at the END of step 4 (right before step 5) instead of its own place (salience control);
  - add_after: extra text placed at the end of step 4 (a diagnostic sentence or neutral filler), checked by the caller.
common.md, phase1.md (unused: Phase 1 replies are held fixed), the user templates and the OUTPUT section are v10's.
Line ends as v10's files.

Checks (check()): build_p2(ALL) equals v10's phase2.md byte for byte; build_p2(set()) holds no rule title of the
inventory in step 4; every rule id has text; each single-rule prompt differs from the core by that rule's text only.

  python -B stages.py            (runs check(); writes nothing)
"""
import json
import re
import sys
from pathlib import Path

from diag_common import HERE, LAB, ISOD

sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
import make_v10 as MV  # noqa: E402

V10D = LAB / "prompts" / "two_phase_v10"
V9D = LAB / "prompts" / "two_phase_v9"
IDX = json.loads((ISOD / "pack" / "index.json").read_text(encoding="utf-8"))
RMAP = json.loads((ISOD / "rule_map.json").read_text(encoding="utf-8"))
DIX = json.loads((LAB / "analysis" / "prompt_builds" / "v10" / "dossiers" / "index.json").read_text(encoding="utf-8"))
F = MV.finals()
REQ_LINE = 35                                   # v9 phase2.md line 35: Requests waiting for a grant, Phase 2 wording


def slug(unit):
    return "P2X-" + re.sub(r"[^a-z0-9]+", "-", unit.split(":", 1)[1].strip().lower()).strip("-")


def rule_of(s):
    u = RMAP[s]["unit"]
    if u.startswith("general") or u.startswith("P1-01"):
        return None
    if u.startswith("P2-only"):
        return slug(u)
    return u[:5]


def all_rules():
    """Every Phase 2 rule id in v10's order of first appearance in phase2.md."""
    order = []
    owner = {s: rid for rid in F for s in DIX.get(rid, {}).get("P2 sentence ids", [])}
    for s in sorted(IDX["p2"], key=lambda s: (IDX["p2"][s]["line"], s)):
        if IDX["p2"][s]["line"] > REQ_LINE and "P1-26" not in order:
            order.append("P1-26")
        r = owner.get(s) or rule_of(s)
        if r and r not in order:
            order.append(r)
    if "P1-26" not in order:
        order.append("P1-26")
    return order


def rule_text(rid):
    """The rule's whole Phase 2 text as v10 has it (for moving it to the end)."""
    if rid in F:
        return "\n".join([F[rid]["P2_structured"].strip("\n")] + [t.strip() for t in (F[rid].get("P2_in_place") or {}).values()])
    if rid == "P1-26":
        return V9_LINES[REQ_LINE - 1].strip()
    return " ".join(IDX["p2"][s]["text"] for s in sorted(IDX["p2"]) if rule_of(s) == rid)


V9_LINES = (V9D / "phase2.md").read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def pieces(rid):
    """The rule's Phase 2 text as separate pieces (block lines, in-place sentences, or v9 sentences)."""
    if rid in F:
        return [l for l in F[rid]["P2_structured"].split("\n") if l.strip()] + [t.strip() for t in (F[rid].get("P2_in_place") or {}).values()]
    if rid == "P1-26":
        return [V9_LINES[REQ_LINE - 1].strip()]
    return [IDX["p2"][s]["text"] for s in sorted(IDX["p2"]) if rule_of(s) == rid]


def build_p2(keep, last=None, add_after=None):
    keep = set(keep)
    p2 = list(V9_LINES)
    by_line = {}
    for s in sorted(IDX["p2"]):
        by_line.setdefault(IDX["p2"][s]["line"], []).append(s)
    owner = {s: rid for rid in F for s in DIX.get(rid, {}).get("P2 sentence ids", [])}
    placed, proc_done = set(), False
    for ln, sids in by_line.items():
        parts, run = [], []
        for s in sids:
            rid = owner.get(s)
            if rid and s in (F[rid].get("P2_in_place") or {}):
                if rid in keep and rid != last:
                    run.append(F[rid]["P2_in_place"][s].strip())
            elif rid and s in (F[rid].get("P2_replaces") or []):
                if rid not in placed:
                    if not proc_done:
                        if run:
                            parts.append(" ".join(run))
                            run = []
                        parts.append(MV.PROC_P2)
                        proc_done = True
                    if rid in keep and rid != last:
                        if run:
                            parts.append(" ".join(run))
                            run = []
                        parts.append(F[rid]["P2_structured"].strip("\n"))
                    placed.add(rid)
            else:
                r = rule_of(s)
                if r is None or (r in keep and r != last):
                    run.append(IDX["p2"][s]["text"])
        if run:
            parts.append(" ".join(run))
        p2[ln - 1] = "\n".join(parts)
    if "P1-26" not in keep or last == "P1-26":
        p2[REQ_LINE - 1] = None
    tail = []
    if last:
        tail.append(rule_text(last))
    if add_after:
        tail.append(add_after.strip())
    if tail:                                      # the end of step 4 = the line before step 5's blank line
        step5 = next(i for i, l in enumerate(p2) if l is not None and l.startswith("5. Secondary."))
        j = step5 - 1
        while j > 0 and (p2[j] is None or p2[j] == ""):
            j -= 1
        p2[j] = p2[j] + "\n" + "\n".join(tail)
    return "\n".join(l for l in p2 if l is not None)


def write_prompt(name, p2_text, readme):
    """prompts/diag_v10/<name>/ with v10's other files; returns the version string chain uses."""
    d = LAB / "prompts" / "diag_v10" / name
    d.mkdir(parents=True, exist_ok=True)
    crlf = b"\r\n" in (V10D / "phase2.md").read_bytes()
    for f in ("common.md", "phase1.md", "phase1_user.md", "phase2_user.md"):
        (d / f).write_bytes((V10D / f).read_bytes())
    (d / "phase2.md").write_bytes((p2_text.replace("\n", "\r\n") if crlf else p2_text).encode("utf-8"))
    (d / "README.md").write_text(readme, encoding="utf-8")
    return f"diag_v10/{name}"


def norm(t):
    return re.sub(r"\s+", " ", t).strip()


def check(log=print):
    ok = True
    v10 = (V10D / "phase2.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    rules = all_rules()
    full = build_p2(rules)
    ok &= full == v10
    log(f"build_p2(all {len(rules)} rules) == v10 phase2.md: {full == v10}")
    core = build_p2(set())
    step4 = core[core.index("4. Primary."):core.index("5. Secondary.")]
    titles = [t["title"] for rid, t in json.loads((ISOD / "rule_texts.json").read_text(encoding="utf-8")).items()
              if not rid.startswith("P2X") and rid != "P1-22R"]
    left = [t for t in titles if re.search(r"(^|\n|\s)- " + re.escape(t) + r"\.", step4) or (t + ".") in step4.split("Reading a rule")[0][-0:]]
    ok &= not left and MV.PROC_P2 in core
    log(f"core: no rule block titles left in step 4 ({left or 'none'}); procedure kept: {MV.PROC_P2 in core}; "
        f"words {len(core.split())} (v10 {len(v10.split())})")
    for rid in rules:
        t = build_p2({rid})
        txt = rule_text(rid)
        extra = len(t.split()) - len(core.split())
        good = extra > 0 and all(w in t.lower() for w in re.findall(r"[a-z]{6,}", txt.lower())[:5]) and all(norm(x) in norm(t) for x in pieces(rid))
        if not good:
            ok = False
            log(f"  {rid}: single-rule prompt adds {extra} words; text check {good}")
    moved = build_p2(rules, last=rules[0])
    ok &= moved != v10 and len(moved.split()) == len(v10.split())
    log(f"moving a rule to the end keeps the word count: {len(moved.split()) == len(v10.split())}")
    log(f"stages self-check: {'PASS' if ok else 'FAIL'}; Phase 2 rules in v10 order: {rules}")
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if check() else 1)
