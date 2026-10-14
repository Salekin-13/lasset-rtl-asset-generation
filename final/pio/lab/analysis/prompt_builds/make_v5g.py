"""Build prompt version two_phase_v5g = two_phase_v5f + the Phase 1 / Phase 2 consistency fix in phase2.md ONLY
(user request 2026-10-13: "find if there are any inconsistencies in rules between phase 1 & 2, if there are, fix
phase 2"). common.md, phase1.md and both user templates stay byte-identical to v5f, so the Phase 1 system sha stays
f05279744fdc and the stored v5f Phase 1 replies can be reused for a Phase 2-only test.

Source of the text: analysis/two_phase_v5f__gpt-5.6-luna__high__r0-r2/consistency/
  audit_workflow_result.json   (wf_5d7fb7b2-d73: findings, skeptic votes, drafts, integration check)
  blocks.json                  (make_long.py: the integrated long texts per anchor, resolutions applied)
  compression_workflow_result.json (wf_0b540b62-d24: compressed text, clause-checked 'equivalent' by two checkers)
Checks after writing: v5f files other than phase2.md byte-identical; Phase 1 system sha unchanged; undoing the
inserts and the I22 replace gives v5f phase2.md; the project prompt checker (check_lab_prompt.check); words; shas.

  python make_v5g.py            (refuses to overwrite an existing two_phase_v5g unless --force)
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
import check_lab_prompt as CK  # noqa: E402

P = LAB / "prompts"
V5F, V5G = P / "two_phase_v5f", P / "two_phase_v5g"
CONS = LAB / "analysis" / "two_phase_v5f__gpt-5.6-luna__high__r0-r2" / "consistency"
FILES = ("common.md", "phase1.md", "phase2.md", "phase1_user.md", "phase2_user.md")


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def build_phase2():
    fin = json.loads((CONS / "compression_workflow_result.json").read_text(encoding="utf-8"))["final"]
    blocks = json.loads((CONS / "blocks.json").read_text(encoding="utf-8"))
    p2 = (V5F / "phase2.md").read_text(encoding="utf-8")
    rep = blocks["replaces"][0]
    assert len(blocks["replaces"]) == 1 and p2.count(rep["anchor"]) == 1
    t = p2.replace(rep["anchor"], fin["i22_replace_new_text"])
    ins = []
    for a in fin["anchors"]:
        assert a["anchor"] in blocks["anchors"] and t.count(a["anchor"]) == 1, a["anchor"][:60]
        new = " " + a["text"].strip()
        t = t.replace(a["anchor"], a["anchor"] + new)
        ins.append((a["anchor"], new))
    u = t
    for a, new in ins:
        u = u.replace(a + new, a)
    u = u.replace(fin["i22_replace_new_text"], rep["anchor"])
    assert u == p2, "undo check failed"
    return t


def main(force=False):
    sys.stdout.reconfigure(encoding="utf-8")
    if V5G.exists() and not force:
        raise SystemExit(f"{V5G} exists; use --force to rebuild")
    V5G.mkdir(exist_ok=True)
    for f in FILES:
        if f != "phase2.md":
            shutil.copyfile(V5F / f, V5G / f)
    t = build_phase2()
    crlf = b"\r\n" in (V5F / "phase2.md").read_bytes()
    (V5G / "phase2.md").write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
    ok = True
    for f in FILES:
        same = (V5G / f).read_bytes() == (V5F / f).read_bytes()
        want = f != "phase2.md"
        print(f"  {f}: {'byte-identical to v5f' if same else 'changed'} ({'ok' if same == want else 'UNEXPECTED'})")
        ok &= same == want
    s1, s1f = sha(CK.system("two_phase_v5g", 1)), sha(CK.system("two_phase_v5f", 1))
    s2, s2f = sha(CK.system("two_phase_v5g", 2)), sha(CK.system("two_phase_v5f", 2))
    print(f"system sha phase 1: v5f {s1f} -> v5g {s1} ({'unchanged' if s1 == s1f else 'CHANGED'}); phase 2: v5f {s2f} -> v5g {s2}")
    ok &= s1 == s1f
    ok &= bool(CK.check("two_phase_v5g"))
    wc = lambda x: len(x.split())
    print(f"phase2.md words: v5f {wc((V5F / 'phase2.md').read_text(encoding='utf-8'))} -> v5g {wc(t)}")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main("--force" in sys.argv) else 1)
