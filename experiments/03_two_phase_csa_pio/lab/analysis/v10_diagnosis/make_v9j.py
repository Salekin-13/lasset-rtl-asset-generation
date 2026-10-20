"""two_phase_v9j = two_phase_v9i with (1) the Processor control-unit state bar's Outcome sparing the unit's ports, its output
control record and its two reference flags (the recall loss of section 12 sat there), and (2) every keep block moved to the
end of its step (order B of section 13). User 2026-10-18: "Build v9j ... run it on all 41 modules, r0-r2". Builds the prompt
folder only; sends nothing.

  python -B make_v9j.py [--write]
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
sys.path.insert(0, str(HERE))
import make_v10 as M  # noqa: E402
import make_order_b as OB  # noqa: E402

CK, CH = M.CK, M.CH
SRC, PRE, DST = "two_phase_v9i", "two_phase_v9j_pre", "two_phase_v9j"
SPARE = (" The unit's own ports (its interrupt, fault, wait and done inputs; its output control record), the debug-run flag and "
         "the trigger start are judged as usual: keep their concepts and their labels.")


def texts():
    t = json.loads((HERE / "new_rules" / "rule_texts_v9i.json").read_text(encoding="utf-8"))
    new = {k: dict(v) for k, v in t.items()}
    for ph in ("P1", "P2"):
        lines = t["B2"][ph].split("\n")
        idx = [i for i, l in enumerate(lines) if l.startswith("  Outcome:")]
        assert len(idx) == 1, "B2 Outcome line not found once"
        lines[idx[0]] = lines[idx[0]].rstrip() + SPARE
        new["B2"][ph] = "\n".join(lines)
    return t, new


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    old, new = texts()
    (HERE / "new_rules" / "rule_texts_v9j.json").write_text(json.dumps(new, indent=1, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, "-B", str(HERE / "check_new_rules.py"), str(HERE / "new_rules" / "rule_texts_v9j.json")], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout[-400:])
    if r.returncode:
        sys.exit("checker BLOCKERS")
    log = []
    files = M.FILES
    pre = {}
    for f, ph in (("phase1.md", "P1"), ("phase2.md", "P2")):
        body = (LAB / "prompts" / SRC / f).read_text(encoding="utf-8").replace("\r\n", "\n")
        o, n = old["B2"][ph].strip("\n"), new["B2"][ph].strip("\n")
        if body.count(o) != 1:
            log.append(f"{f}: B2 block occurs {body.count(o)} times")
        pre[f] = body.replace(o, n)
    pre["common.md"] = (LAB / "prompts" / SRC / "common.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    print(f"B2 words P1 {len(new['B2']['P1'].split())} P2 {len(new['B2']['P2'].split())} (v9i {len(old['B2']['P1'].split())} / {len(old['B2']['P2'].split())}); "
          + ("\n".join(log) if log else "B2 replaced once in each phase"))
    if log:
        sys.exit(1)
    if write:
        crlf = b"\r\n" in (LAB / "prompts" / SRC / "phase1.md").read_bytes()
        d = LAB / "prompts" / PRE
        d.mkdir(exist_ok=True)
        for f in ("phase1_user.md", "phase2_user.md"):
            shutil.copyfile(LAB / "prompts" / SRC / f, d / f)
        for f in files:
            (d / f).write_bytes((pre[f].replace("\n", "\r\n") if crlf else pre[f]).encode("utf-8"))
        (d / "README.md").write_text("# two_phase_v9j_pre: v9i with the control-unit bar sparing the unit's ports (intermediate, order A)\n", encoding="utf-8")
        log2 = []
        ok, orig, moved_text, moved = OB.build(PRE, log2)
        print("\n".join(log2) if log2 else f"order B: moved {moved['phase1.md']}")
        if not ok:
            sys.exit(1)
        dd = LAB / "prompts" / DST
        dd.mkdir(exist_ok=True)
        for f in ("phase1_user.md", "phase2_user.md"):
            shutil.copyfile(LAB / "prompts" / SRC / f, dd / f)
        for f in files:
            (dd / f).write_bytes((moved_text[f].replace("\n", "\r\n") if crlf else moved_text[f]).encode("utf-8"))
        (dd / "README.md").write_text("# two_phase_v9j: v9i + the control-unit bar sparing the unit's ports and output record + every keep block last in its step "
                                      "(built 2026-10-18; analysis/v10_diagnosis/make_v9j.py; PLAN_ISOLATE_CLUSTER_ORDER.md section 14)\n", encoding="utf-8")
        chk = bool(CK.check(DST, log=print))
        nf = CH.new_format(DST, 1) and CH.new_format(DST, 2)
        same = all((LAB / "prompts" / SRC / f).read_bytes() == (dd / f).read_bytes() for f in ("common.md", "phase1_user.md", "phase2_user.md"))
        print(f"checker {chk}; new_format {nf}; common.md and user templates identical to v9i {same}; sha12 {M.sha(CK.system(DST, 1))[:12]} / {M.sha(CK.system(DST, 2))[:12]}")
        print("ALL CHECKS PASS" if chk and nf and same else "CHECKS FAILED")
        if not (chk and nf and same):
            sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
