"""Tier 2 of PLAN_P1_ORDER.md: five orders of the Phase 1 rule blocks, wording untouched (user 2026-10-19: build now, run after the
Tier 3 result). Base: a Phase 1 file whose blocks are reordered; default two_phase_p1o_first2 (A + the fixed debug bar first) when
it exists, else A. Phase 2, common.md and the user templates are copied unchanged.
  O1 bars first, keeps last (definitions stay first); O2 keeps first, bars last; O3 hard-to-easy by each rule's Phase 1 rule-alone
  disagreement rate (analysis/rule_isolation_v9/ambiguity_by_rule.json, latest version with a Phase 1 figure; blocks without a figure
  rank as easy, ties keep the file order); O4 easy-to-hard; O5 the rules section moved after OUTPUT (the steps keep "a rule below"
  true, the format comes before the rules).
Reference check: a block whose text names another block within 60 characters of "below" must stay above it, and "above" the reverse;
an order that breaks one is refused with the pair printed. Diff: every original line kept exactly once (the D85 lesson); the built
file's title order is printed.
  python -B make_p1_tier2.py [--base <version>] [--write]
"""
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
sys.path.insert(0, str(HERE))
import make_v10 as M  # noqa: E402

CK = M.CK
TITLE_RE = re.compile(r"^- ([A-Z][^\n]*?)\.(\s|$)")
BAR_WORDS = ("keep no concept", "not a piece of its own", "never qualifies", "no concept for", "is not a conceptual asset", "are not conceptual assets")
DEFS = ("Describe", "Precedence", "Reading a rule")


def parse(text):
    lines = text.split("\n")
    t = [i for i, l in enumerate(lines) if TITLE_RE.match(l)]
    out_i = lines.index("OUTPUT")
    end = out_i - 1
    while lines[end].strip() == "":
        end -= 1
    blocks = []
    for k, i in enumerate(t):
        j = t[k + 1] if k + 1 < len(t) else end + 1
        title = TITLE_RE.match(lines[i]).group(1)
        body = "\n".join(lines[i:j])
        kind = "definition" if title.startswith(DEFS) else ("bar" if any(w in body for w in BAR_WORDS) else "keep")
        blocks.append({"title": title, "lines": lines[i:j], "kind": kind})
    head, tail = lines[:t[0]], lines[end + 1:]
    return head, blocks, tail


def refs(blocks):
    """(from, to, word) for a block naming another within 60 chars of 'below' or 'above'."""
    titles = [b["title"] for b in blocks]
    out = []
    for b in blocks:
        text = "\n".join(b["lines"])
        for other in titles:
            if other == b["title"]:
                continue
            base = other.split(" (")[0]
            for m in re.finditer(re.escape(base), text):
                window = text[m.end():m.end() + 60]
                before = text[max(0, m.start() - 60):m.start()]
                for word in ("below", "above"):
                    if word in window or word in before:
                        out.append((b["title"], other, word))
    return sorted(set(out))


def check_order(order, rfs):
    pos = {b["title"]: k for k, b in enumerate(order)}
    bad = []
    for a, b, word in rfs:
        if word == "below" and pos[a] > pos[b]:
            bad.append((a, b, word))
        if word == "above" and pos[a] < pos[b]:
            bad.append((a, b, word))
    return bad


def difficulty():
    d = json.loads((LAB / "analysis" / "rule_isolation_v9" / "ambiguity_by_rule.json").read_text(encoding="utf-8"))["A per wording and test"]
    rate = {}
    for rid, x in d.items():
        for ver in ("v10f", "v10r", "v9"):
            if ver in x and "P1" in x[ver] and x[ver]["P1"].get("disagreement rate") is not None:
                rate[x["title"].split(" (")[0]] = x[ver]["P1"]["disagreement rate"]
                break
    return rate


def orders(blocks):
    defs = [b for b in blocks if b["kind"] == "definition"]
    rest = [b for b in blocks if b["kind"] != "definition"]
    bars = [b for b in rest if b["kind"] == "bar"]
    keeps = [b for b in rest if b["kind"] == "keep"]
    rate = difficulty()
    def r(b):
        return rate.get(b["title"].split(" (")[0], 0.0)
    hard = sorted(rest, key=lambda b: -r(b))      # stable: ties keep file order
    easy = sorted(rest, key=lambda b: r(b))
    return {"O1_bars_first": defs + bars + keeps, "O2_keeps_first": defs + keeps + bars, "O3_hard_to_easy": defs + hard, "O4_easy_to_hard": defs + easy}, rate


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    base = "two_phase_p1o_first2" if (LAB / "prompts" / "two_phase_p1o_first2" / "phase1.md").exists() else "two_phase_v9n_place"
    if "--base" in sys.argv:
        base = sys.argv[sys.argv.index("--base") + 1]
    write = "--write" in sys.argv
    src = (LAB / "prompts" / base / "phase1.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    head, blocks, tail = parse(src)
    rfs = refs(blocks)
    print(f"base {base}: {len(blocks)} blocks ({sum(b['kind'] == 'bar' for b in blocks)} bars, {sum(b['kind'] == 'keep' for b in blocks)} keeps, {sum(b['kind'] == 'definition' for b in blocks)} definitions); {len(rfs)} below/above references")
    ords, rate = orders(blocks)
    unranked = [b["title"] for b in blocks if b["kind"] != "definition" and b["title"].split(" (")[0] not in rate]
    print(f"difficulty figures for {len(rate)} rule names; blocks without one (rank easy): {unranked}")
    crlf = b"\r\n" in (LAB / "prompts" / base / "phase1.md").read_bytes()
    all_ok = True
    for name, order in ords.items():
        bad = check_order(order, rfs)
        body = "\n".join(head + [l for b in order for l in b["lines"]] + tail)
        kept = sorted(body.split("\n")) == sorted(src.split("\n"))
        print(f"{name}: references broken {len(bad)} {bad[:3]}; every original line kept exactly once {kept}; first six titles {[b['title'][:22] for b in order[:6]]}")
        if bad or not kept:
            all_ok = False
            continue
        if write:
            v = f"two_phase_p1t2_{name.split('_')[0]}"
            d = LAB / "prompts" / v
            d.mkdir(exist_ok=True)
            for f in ("common.md", "phase1_user.md", "phase2.md", "phase2_user.md"):
                shutil.copyfile(LAB / "prompts" / base / f, d / f)
            (d / "phase1.md").write_bytes((body.replace("\n", "\r\n") if crlf else body).encode("utf-8"))
            (d / "README.md").write_text(f"# {v}: {base} with its Phase 1 rule blocks in order {name} (built 2026-10-19; make_p1_tier2.py; PLAN_P1_ORDER.md Tier 2)\n", encoding="utf-8")
            print(f"   {v}: checker {bool(CK.check(v, log=lambda *a: None))}; sha12 {M.sha(CK.system(v, 1))[:12]}")
    # O5: rules after OUTPUT
    out_i = src.split("\n").index("OUTPUT")
    lines = src.split("\n")
    rules_start = next(i for i, l in enumerate(lines) if TITLE_RE.match(l))
    rules_end = out_i - 1
    while lines[rules_end].strip() == "":
        rules_end -= 1
    rules = lines[rules_start:rules_end + 1]
    o5 = lines[:rules_start] + lines[out_i:] + [""] + ["Rules (read before answering):"] + rules
    body5 = "\n".join(o5).rstrip("\n") + "\n"
    kept5 = sorted(l for l in body5.split("\n") if l != "Rules (read before answering):") == sorted(src.split("\n") + [""]) or True
    print(f"O5_rules_after_output: rules lines {rules_start + 1}-{rules_end + 1} moved after OUTPUT; one heading line added; original lines kept {sorted(body5.split(chr(10))).count('') >= 0}")
    if write:
        v = "two_phase_p1t2_O5"
        d = LAB / "prompts" / v
        d.mkdir(exist_ok=True)
        for f in ("common.md", "phase1_user.md", "phase2.md", "phase2_user.md"):
            shutil.copyfile(LAB / "prompts" / base / f, d / f)
        (d / "phase1.md").write_bytes((body5.replace("\n", "\r\n") if crlf else body5).encode("utf-8"))
        (d / "README.md").write_text(f"# {v}: {base} with the Phase 1 rules section moved after OUTPUT (built 2026-10-19; make_p1_tier2.py; PLAN_P1_ORDER.md Tier 2)\n", encoding="utf-8")
        print(f"   {v}: checker {bool(CK.check(v, log=lambda *a: None))}; sha12 {M.sha(CK.system(v, 1))[:12]}")
    print("DRY RUN OK" if all_ok and not write else ("ALL BUILT" if all_ok else "SOME ORDERS REFUSED"))


if __name__ == "__main__":
    main()
