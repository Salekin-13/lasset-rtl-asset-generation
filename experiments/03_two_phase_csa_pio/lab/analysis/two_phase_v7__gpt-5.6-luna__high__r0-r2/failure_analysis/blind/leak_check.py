"""Stage E leak check (code written for this run; the copied view builders have none). Runs before any blind judge.

Views (views/<short>.md and views/<short>_concepts.md):
  1. every line must match one of the builders' fixed template lines (the regexes below, one per line kind that
     make_blind_views.py and make_blind_concepts.py write);
  2. every value a template line carries must be text copied word for word from the "reply" field of the stored v7 record
     of that module and run (a list printed joined is split, and each part must be such a value); row ids must have the
     builder's form <short>:r<k>:<concept id>:<n>;
  3. the fixed template text (each template with its value slots removed) is scanned for RC ids (the refconcepts.json id
     form RC<number>), the key's labels ("correct if primary", "counted now") and the words correct, false positive,
     reference, target and spare. The model's own reply text is not word-scanned (the replies use words like "correct"
     and "target" in their own sense); a line that matches no template is scanned whole.
Wording diffs (blind/diffs/<FX>.diff, written from each surviving fix's wording field by fixcheck.check()): every added
  line is scanned for RC ids, the key's labels and per-run counts (r0-r2, "<n> of <n>", "<n>/<n>", "<n> runs", "<n>%").
  Words that appear in v7's own prompt text are allowed. Corpus names are caught earlier, by fixcheck.py.
Self-test (first): an RC id and a key label planted in one view template line and in one wording diff are all four
caught, and a clean view and a clean diff pass.

  python leak_check.py [diff files...]      -> exit 1 on any finding
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FA = HERE.parent
sys.path.insert(0, str(FA))
import common_fa as F  # noqa: E402

RC = re.compile(r"\bRC\d+\b")
LABELS = re.compile(r"correct if primary|counted now", re.I)
WORDS = re.compile(r"\b(correct|false positive|reference|target|spare)\b", re.I)
COUNTS = re.compile(r"\br[0-2]\b|\b\d+\s*(?:of|/)\s*\d+\b|\b\d+\s+runs?\b|\b\d+\s*%")
V = r"(?P<{}>.*)"
ROWS = [
    ("header", r"^# (?P<short>[\w]+): Phase 2 rows of three runs \(blind view\)$"),
    ("blank", r"^$"),
    ("run", r"^## Run r[0-2]$"),
    ("walk", r"^### r[0-2]:(?P<cid>\S+) (?P<name>.*)$"),
    ("information", r"^- information: (?P<info>.*)$"),
    ("anchors", r"^- objectives at risk: (?P<objs>.*?); enters through: (?P<ent>.*?); leaves through: (?P<lev>.*)$"),
    ("npr", r"^- no primary reason: (?P<npr>.*)$"),
    ("row", r"^- \[(?P<rid>[\w]+:r[0-2]:[^:\]]+:\d+)\] (?P<el>\S+) \((?P<entity>[^)]*)\) \| (?P<label>[^|]+?)"
            r"(?: \| same role: (?P<same>.*?))?(?: \| secondary to: (?P<sec>.*?))? \| found at: (?P<fa>.*?) \| lines (?P<lines>.*)$"),
    ("functionality", r"^    functionality: (?P<f>.*)$"),
    ("justification", r"^    justification: (?P<j>.*)$"),
    ("not reported", r"^- not reported: (?P<el>\S+) \((?P<entity>[^)]*)\): (?P<why>.*)$"),
]
CONCEPTS = [
    ("header", r"^# (?P<short>[\w]+): Phase 1 concepts of three runs with their Phase 2 elements \(blind view\)$"),
    ("blank", r"^$"),
    ("run", r"^## Run r[0-2]$"),
    ("concept", r"^### r[0-2]:(?P<cid>C\d+) (?P<name>.*) \(unit (?P<unit>\S+)\)$"),
    ("not kept head", r"^### r[0-2]: not kept$"),
    ("information", r"^- information: (?P<info>.*)$"),
    ("objectives", r"^- objectives at risk: (?P<objs>.*?); rubric yes: (?P<rub>.*)$"),
    ("anchors", r"^- enters through: (?P<ent>.*?); leaves through: (?P<lev>.*)$"),
    ("lines", r"^- entry lines (?P<l1>.*?); held lines (?P<l2>.*?); exit lines (?P<l3>.*)$"),
    ("primary", r"^- Phase 2 primary: (?P<p>.*)$"),
    ("secondary", r"^- Phase 2 secondary: (?P<s>.*)$"),
    ("not kept", r"^- (?P<cand>.*) \((?P<unit>[^()]*)\): (?P<why>.*)$"),
]
RUBRIC = {"Confidentiality", "Integrity", "Availability", "Undermined Expected Behavior"}


def values(obj, out):
    if isinstance(obj, dict):
        for v in obj.values():
            values(v, out)
    elif isinstance(obj, list):
        out.add(str(obj))
        for v in obj:
            values(v, out)
    elif obj is not None:
        out.add(str(obj))
    return out


def reply_values(short, r):
    m = "neorv32_" + short
    S = set()
    for ph in (1, 2):
        values(F.record(r, m, ph)["reply"], S)
    return S


def template_text(pat):
    """The fixed text of a template: the regex with its value groups and regex syntax removed."""
    t = re.sub(r"\(\?P<\w+>[^()]*(?:\([^()]*\)[^()]*)*\)", " ", pat)
    return re.sub(r"[\^\$\\\[\]\(\)\?\*\+\|\{\}]|\bS\b|\bw\b|\bd\b", " ", t)


def check_value(name, v, S, short):
    if v is None or v in ("", "-"):
        return True
    if name == "rid":
        return True                      # its form is fixed by the regex; the concept id inside is checked as cid below
    if name == "short":
        return v == short
    if name == "rub":
        return all(x in RUBRIC for x in v.split(", "))
    if name == "lines" or name in ("l1", "l2", "l3"):
        return v in S or v == "None"
    if v in S:
        return True
    parts = re.split(r", |; ", v)
    if name == "sec":
        parts = [re.sub(r" \((?:[a-z])\)$", "", p) for p in v.split("; ")]
        dirs = re.findall(r" \(([a-z])\)(?:;|$)", v)
        return all(p in S for p in parts) and all(d in S for d in dirs)
    if name == "why" and v.startswith("merged into "):
        return v in S or v[len("merged into "):] in S
    return all(p in S for p in parts)


def check_view(path, templates, short_of=None):
    probs = []
    text = Path(path).read_text(encoding="utf-8").splitlines()
    short = Path(path).stem.replace("_concepts", "")
    run, S = None, None
    for i, line in enumerate(text, 1):
        mm = re.match(r"^## Run r([0-2])$", line)
        if mm:
            run = int(mm.group(1))
            S = reply_values(short, run)
        hit = None
        for kind, pat in templates:
            m = re.match(pat, line)
            if m:
                hit = (kind, pat, m)
                break
        if not hit:
            bad = [x for x in (RC.findall(line) + LABELS.findall(line) + WORDS.findall(line))]
            probs.append(f"{path}:{i}: matches no template line" + (f"; contains {bad}" if bad else ""))
            continue
        kind, pat, m = hit
        for name, v in m.groupdict().items():
            if S is None and name not in ("short",):
                if v not in (None, ""):
                    probs.append(f"{path}:{i}: value before any run header")
                continue
            if not check_value(name, v, S, short):
                probs.append(f"{path}:{i}: {kind} value '{name}' is not text from the stored reply: {str(v)[:80]}")
            if name == "rid" and v:
                cid = v.split(":")[2]
                if cid not in S:
                    probs.append(f"{path}:{i}: row id concept {cid} not in the reply")
    return probs


def scan_templates():
    probs = []
    for kind, pat in ROWS + CONCEPTS:
        t = template_text(pat)
        bad = RC.findall(t) + LABELS.findall(t) + WORDS.findall(t)
        if bad:
            probs.append(f"template '{kind}' contains {bad}")
    return probs


def v7_text():
    return " ".join((F.PROMPTS / f).read_text(encoding="utf-8") for f in ("common.md", "phase1.md", "phase2.md"))


def check_diff(path):
    probs = []
    for i, l in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not l.startswith("+") or l.startswith("+++"):
            continue
        for rx, what in ((RC, "RC id"), (LABELS, "key label"), (COUNTS, "per-run count")):
            for x in rx.findall(l):
                probs.append(f"{path}:{i}: {what} '{x}'")
    return probs


def selftest(tmp):
    tmp.mkdir(exist_ok=True)
    clean_v = HERE / "views" / "wdt.md"
    L = clean_v.read_text(encoding="utf-8").splitlines()
    bad_v = tmp / "wdt.md"
    L2 = list(L)
    L2[0] = L2[0] + " RC3"                                        # an RC id in a template line
    j = next(k for k, l in enumerate(L2) if l.startswith("- information: "))
    L2[j] = L2[j].replace("- information: ", "- information (correct if primary): ", 1)   # a key label in a template line
    bad_v.write_text("\n".join(L2), encoding="utf-8")
    pv = check_view(bad_v, ROWS)
    clean_d = tmp / "clean.diff"
    clean_d.write_text("--- two_phase_v7/phase2.md\n+++ fix/phase2.md\n@@ -3,0 +4 @@\n+A held value is its own piece.\n", encoding="utf-8")
    bad_d = tmp / "bad.diff"
    bad_d.write_text("--- two_phase_v7/phase2.md\n+++ fix/phase2.md\n@@ -3,0 +4,2 @@\n+Keep RC4 as one piece.\n+Mark it counted now.\n", encoding="utf-8")
    pd = check_diff(bad_d)
    ok = (any("RC3" in p or (":1:" in p) for p in pv) and any("correct if primary" in p or f":{j + 1}:" in p for p in pv)
          and any("RC4" in p for p in pd) and any("counted now" in p for p in pd)
          and not check_view(clean_v, ROWS) and not check_diff(clean_d))
    for f in (bad_v, clean_d, bad_d):
        f.unlink()
    tmp.rmdir()
    return ok, pv, pd


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ok, pv, pd = selftest(HERE / "_leak_selftest")
    print(f"self-test (RC id and key label planted in a view template line and a wording diff, all four caught; clean view "
          f"and clean diff pass): {'PASS' if ok else 'FAIL'}")
    if not ok:
        print("  view findings:", pv[:4], "\n  diff findings:", pd)
        sys.exit(2)
    probs = scan_templates()
    nv = 0
    for p in sorted((HERE / "views").glob("*.md")):
        probs += check_view(p, CONCEPTS if p.stem.endswith("_concepts") else ROWS)
        nv += 1
    for d in sys.argv[1:]:
        probs += check_diff(d)
    print(f"views checked {nv}; diffs checked {len(sys.argv) - 1}; findings {len(probs)}")
    for x in probs[:50]:
        print("  " + x)
    sys.exit(1 if probs else 0)


if __name__ == "__main__":
    main()
