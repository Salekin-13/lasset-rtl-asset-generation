"""C2 step 2 (code): the project's prompt checks on a fix's wording (meta_tools.check_prompt, as check_lab_prompt.py
uses it: corpus identifiers, numeric emission hints, comments used as evidence, prompts_v2.audit).

A fix file is JSON with a "wording" field:
  {"edits": [{"file": "common.md"|"phase1.md"|"phase2.md", "action": "insert after"|"replace", "line": <v7 line>,
              "old_text": <exact text on that line, for replace>, "new_text": <text>}],
   "core_sentence": <for a paired rule, the core sentence, word for word in a phase1.md edit and a phase2.md edit; else "">,
   "code_check": {"script_file": <path or "">, "sentence": <one sentence or "">},
   "input_change": {"diff_file": <path or "">, "sentence": <one sentence or "">}}
The edits are applied to the v7 files in memory (never on disk). Checked:
  - every edit applies (a replaced text occurs exactly once on its line; the line exists);
  - the assembled Phase 1 and Phase 2 system prompts (common.md + phaseK.md) pass meta_tools.check_prompt, and so does
    every new text on its own;
  - a paired rule: the core sentence occurs word for word in a phase1.md edit and in a phase2.md edit;
  - a code-check fix: its script source and sentence pass the corpus-name check, and the source opens no reference file
    (eval_assets, refconcepts.json, compare_*.json, ground_truth, manual_gt, boundary_key);
  - an input change: its sentence passes the check; its diff file exists and touches only files under inputs/.
Also returns the words added per phase file and the unified diff against v7 (used by the stage E wording diffs).

Planted self-test (runs first): a numeric hint and a corpus identifier planted in a new text are both caught; an edit
whose old text is not on its line fails; a paired rule whose core sentence is missing from phase2.md fails; a code-check
script that imports eval_assets fails; a clean edit (a sentence copied from v7's own phase2.md) passes.

  python fixcheck.py <fix.json> [<fix.json> ...]      -> prints one JSON line per file; exit 1 if any fails
"""
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

import common_fa as F

sys.path.insert(0, str(F.ROOT / "assetgen_meta"))
sys.path.insert(0, str(F.ROOT / "bahavioral_patterns_of_assets"))
import meta_tools as mt  # noqa: E402

NAMES = F.K.corpus_names() | mt.corpus_names(str(F.ROOT))
FILES = ("common.md", "phase1.md", "phase2.md")
REF_FILES = re.compile(r"eval_assets|refconcepts\.json|compare_\w*\.json|ground_truth|manual_gt|boundary_key")


def v7_lines(f):
    return (F.PROMPTS / f).read_text(encoding="utf-8").splitlines()


def apply(edits):
    """-> ({file: new lines}, problems)."""
    new = {f: v7_lines(f) for f in FILES}
    probs = []
    # apply in descending line order per file so v7 line numbers stay valid
    for e in sorted(edits, key=lambda e: (e.get("file"), -(e.get("line") or 0))):
        f, ln, act = e.get("file"), e.get("line"), e.get("action")
        if f not in FILES:
            probs.append(f"edit on unknown file {f}")
            continue
        L = new[f]
        if not isinstance(ln, int) or ln < 0 or ln > len(L) or (act == "replace" and ln == 0):
            probs.append(f"{f}: line {ln} does not exist")
            continue
        if act == "replace":
            cur = L[ln - 1]
            old = e.get("old_text") or ""
            if not old or cur.count(old) != 1:
                probs.append(f"{f}:{ln}: the replaced text occurs {cur.count(old) if old else 0} times on that line (needs exactly 1)")
                continue
            L[ln - 1] = cur.replace(old, e.get("new_text") or "")
        elif act == "insert after":
            L.insert(ln, e.get("new_text") or "")
        else:
            probs.append(f"{f}:{ln}: unknown action {act}")
    return new, probs


def check(fix):
    w = fix.get("wording") or {}
    edits = w.get("edits") or []
    new, probs = apply(edits)
    out = {"id": fix.get("id"), "problems": probs}
    for k in (1, 2):
        s = "\n".join(new["common.md"]).rstrip() + "\n\n" + "\n".join(new[f"phase{k}.md"])
        r = mt.check_prompt(s, NAMES, f"phase {k}")
        out["problems"] += [f"assembled phase {k}: {p}" for p in r["problems"]]
        out[f"sha12 phase {k}"] = hashlib.sha256(s.encode()).hexdigest()[:12]
    for e in edits:
        r = mt.check_prompt(e.get("new_text") or "", NAMES, "new text")
        out["problems"] += [f"new text for {e.get('file')}:{e.get('line')}: {p}" for p in r["problems"]]
    core = (w.get("core_sentence") or "").strip()
    if core and fix.get("kind", "paired rule") == "paired rule":      # the same core in both phases is required of a paired rule only
        for f in ("phase1.md", "phase2.md"):
            # the core sentence must stand word for word in the edited file, and come from an edit of that file
            edited = "\n".join(new[f])
            if core not in edited or not any(e.get("file") == f for e in edits) or core in "\n".join(v7_lines(f)):
                out["problems"].append(f"paired rule: the core sentence is not word for word in the edited {f}"
                                       + (" (it was already there in v7)" if core in "\n".join(v7_lines(f)) else ""))
    cc = w.get("code_check") or {}
    if cc.get("script_file"):
        p = Path(cc["script_file"])
        if not p.exists():
            out["problems"].append(f"code check: script {p} does not exist")
        else:
            src = p.read_text(encoding="utf-8")
            if REF_FILES.search(src):
                out["problems"].append(f"code check: the script opens a reference file ({REF_FILES.search(src).group(0)})")
            r = mt.check_prompt(src, NAMES, "code check source")
            out["problems"] += [f"code check source: {x}" for x in r["problems"] if x.startswith("corpus identifier")]
        r = mt.check_prompt(cc.get("sentence") or "", NAMES, "code check sentence")
        out["problems"] += [f"code check sentence: {x}" for x in r["problems"]]
    ic = w.get("input_change") or {}
    if ic.get("diff_file"):
        p = Path(ic["diff_file"])
        if not p.exists():
            out["problems"].append(f"input change: diff {p} does not exist")
        else:
            heads = re.findall(r"^(?:\+\+\+|---) (\S+)", p.read_text(encoding="utf-8"), re.M)
            if not heads or any("inputs/" not in h.replace("\\", "/") and h != "/dev/null" for h in heads):
                out["problems"].append(f"input change: the diff touches files outside inputs/ ({heads})")
        r = mt.check_prompt(ic.get("sentence") or "", NAMES, "input change sentence")
        out["problems"] += [f"input change sentence: {x}" for x in r["problems"]]
    out["words added"] = {f: len(" ".join(new[f]).split()) - len(" ".join(v7_lines(f)).split()) for f in FILES}
    out["diff"] = "".join("".join(difflib.unified_diff([l + "\n" for l in v7_lines(f)], [l + "\n" for l in new[f]],
                                                       f"two_phase_v7/{f}", f"fix/{f}", n=0)) for f in FILES)
    out["ok"] = not out["problems"]
    return out


def selftest():
    p2 = v7_lines("phase2.md")
    ln = next(i for i, l in enumerate(p2, 1) if len(l) > 80)
    clean = {"id": "clean", "wording": {"edits": [{"file": "phase2.md", "action": "insert after", "line": ln, "old_text": "", "new_text": p2[ln - 1][:120]}]}}
    ident = sorted(n for n in NAMES if len(n) > 5 and n.isidentifier())[0]
    planted = {"id": "planted", "wording": {"edits": [{"file": "phase1.md", "action": "insert after", "line": 3, "old_text": "",
                                                        "new_text": f"Report at most 20 elements such as {ident}."}]}}
    badold = {"id": "badold", "wording": {"edits": [{"file": "phase1.md", "action": "replace", "line": 3, "old_text": "no such text here", "new_text": "x"}]}}
    pair = {"id": "pair", "wording": {"core_sentence": "A held value is its own piece.",
                                      "edits": [{"file": "phase1.md", "action": "insert after", "line": 3, "old_text": "", "new_text": "A held value is its own piece."},
                                                {"file": "phase2.md", "action": "insert after", "line": 3, "old_text": "", "new_text": "A held value is one piece."}]}}
    tmp = F.HERE / "_selftest_codecheck.py"
    tmp.write_text("import eval_assets\n", encoding="utf-8")
    code = {"id": "code", "wording": {"edits": [], "code_check": {"script_file": str(tmp), "sentence": "Drop rows a check flags."}}}
    r = {k: check(x) for k, x in (("clean", clean), ("planted", planted), ("badold", badold), ("pair", pair), ("code", code))}
    tmp.unlink()
    pl = r["planted"]["problems"]
    ok = (r["clean"]["ok"] and any("numeric hint" in p for p in pl) and any("corpus identifier" in p for p in pl)
          and not r["badold"]["ok"] and any("core sentence" in p for p in r["pair"]["problems"])
          and any("reference file" in p for p in r["code"]["problems"]))
    return ok, {k: v["problems"] for k, v in r.items()}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ok, detail = selftest()
    print(json.dumps({"self-test": "PASS" if ok else "FAIL", "detail": detail}))
    if not ok:
        sys.exit(2)
    bad = False
    for a in sys.argv[1:]:
        fix = json.loads(Path(a).read_text(encoding="utf-8"))
        r = check(fix)
        r["file"] = a
        bad |= not r["ok"]
        print(json.dumps({k: v for k, v in r.items() if k != "diff"}, ensure_ascii=False))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
