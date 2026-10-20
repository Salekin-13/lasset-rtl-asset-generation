"""Build two_phase_v6d and two_phase_v6e from the condensed units (user request 2026-10-13).

  v6d  = v6abc with every unit traced to a lost element put back to v6's wording (restore_v6d.json, from the trace
         workflow wf_de176bc0-f7a, skeptic-kept culprits only).
  v6e  = the evaluated suggestions applied to v6 ("keep only the changes that passed their test, protect the words that
         set a rule's scope"):
         - Phase 1 and the shared core sentences stay v6's (their tracks, v6a and v6c, fired the README readings);
         - Phase 2 keeps v6b's condensing (its track held: recall not below v6's lowest run; element sign test p 0.79),
           except the units traced to a loss and the units the protected-word register flags (restore_v6e.json).
         Phase 1 is byte-identical to v6, so v6's stored Phase 1 replies can be reused (a Phase 2-only run, as for v6b).

A unit is one segment of a chunk (a rule line, or a sentence part of a very long line) or one core sentence; restoring
it puts back exactly v6's segment. Checks per version: the project prompt checker, chain.new_format, OUTPUT sections
byte-identical to v6, each core sentence once per phase file, the same line count as v6, every restored unit's v6
wording present, and (v6e) Phase 1 identical to v6. Writes prompts/two_phase_v6d and two_phase_v6e.

  python make_v6de.py            (dry run: prints the plan and the checks, writes nothing)
  python make_v6de.py --write
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CV = HERE.parent
LAB = CV.parents[2]
sys.path.insert(0, str(CV))
sys.path.insert(0, str(LAB))
import assemble_condensed as A  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import chain as CH  # noqa: E402

V6 = LAB / "prompts" / "two_phase_v6"


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def restore(M, acc, ids):
    """acc with the given units put back to v6's wording."""
    out = {"p1": dict(acc["p1"]), "p2": dict(acc["p2"]), "core": dict(acc["core"])}
    orig = {c["id"]: c["text"] for k in ("phase1", "phase2") for c in M["chunks"][k]}
    for u in ids:
        if u.startswith("S"):
            out["core"].pop(u, None)
            continue
        pid, i = u.split(".")
        g = pid[:2]
        if pid not in out[g]:
            continue                                          # that piece already has v6's text
        segs = out[g][pid].split("\n")
        segs[int(i)] = orig[pid].split("\n")[int(i)]
        out[g][pid] = "\n".join(segs)
        if out[g][pid] == orig[pid]:
            del out[g][pid]
    return out


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    M = json.loads((CV / "manifest.json").read_text(encoding="utf-8"))
    acc = json.loads((CV / "accepted_pieces.json").read_text(encoding="utf-8"))
    units = {}
    for block in (HERE / "units.md").read_text(encoding="utf-8").split("\n## ")[1:]:
        lines = block.splitlines()
        units[lines[0].split(" ", 1)[0]] = next(l[6:] for l in lines if l.startswith("- v6: "))
    r6d = json.loads((HERE / "restore_v6d.json").read_text(encoding="utf-8"))["units"]
    r6e = json.loads((HERE / "restore_v6e.json").read_text(encoding="utf-8"))["units"]
    unknown = [u for u in r6d + r6e if u not in units]
    if unknown:
        raise SystemExit(f"unknown unit ids: {unknown}")
    a6d = restore(M, acc, r6d)
    a6e = restore(M, {"p1": {}, "p2": acc["p2"], "core": {}}, r6e)
    v6 = {k: (V6 / f"{k}.md").read_text(encoding="utf-8") for k in ("phase1", "phase2")}
    ok_all = True
    for ver, a, rs in (("two_phase_v6d", a6d, r6d), ("two_phase_v6e", a6e, r6e)):
        texts = A.build(M, a["p1"], a["p2"], a["core"])
        d = LAB / "prompts" / ver
        if write:
            d.mkdir(exist_ok=True)
            for f in ("common.md", "phase1_user.md", "phase2_user.md"):
                shutil.copyfile(V6 / f, d / f)
            for k in ("phase1", "phase2"):
                (d / f"{k}.md").write_bytes(texts[k].replace("\n", "\r\n").encode("utf-8"))
        same_out = all(texts[k][texts[k].index("\nOUTPUT\n"):] == v6[k][v6[k].index("\nOUTPUT\n"):] for k in texts)
        cores = {e["id"]: (a["core"].get(e["id"]) or e["text"]) for e in M["core"]}
        core_ok = all(texts["phase1"].count(s) == 1 and texts["phase2"].count(s) == 1 for s in cores.values())
        lines_ok = all(texts[k].count("\n") == v6[k].count("\n") for k in texts)

        def filled(s):                                        # a segment's placeholders, filled as in this version
            for sid, c in cores.items():
                s = s.replace(f"[[S{sid[1:]}]]", c.strip())
            return s.strip()
        restored_ok = all(filled(units[u]) in texts["phase1"] or filled(units[u]) in texts["phase2"] for u in rs)
        p1_same = texts["phase1"] == v6["phase1"]
        ok = same_out and core_ok and lines_ok and restored_ok and (p1_same if ver.endswith("v6e") else True)
        msg = f"{ver}: restore {len(rs)} units; pieces used p1 {len(a['p1'])}, p2 {len(a['p2'])}, core {len(a['core'])}; " \
              f"words phase1 {len(texts['phase1'].split())} (v6 {len(v6['phase1'].split())}), phase2 {len(texts['phase2'].split())} " \
              f"(v6 {len(v6['phase2'].split())}); OUTPUT same {same_out}; core once {core_ok}; lines {lines_ok}; restored present " \
              f"{restored_ok}; phase1 = v6 {p1_same}"
        if write:
            chk = bool(CK.check(ver, log=lambda *x: None))
            nf = CH.new_format(ver, 1) and CH.new_format(ver, 2)
            ok &= chk and nf
            msg += f"; checker {chk}; new_format {nf}; shas {sha(CK.system(ver, 1))} / {sha(CK.system(ver, 2))}"
        print(msg + f" -> {'OK' if ok else 'FAILED'}")
        ok_all &= ok
    print("ALL CHECKS PASS" if ok_all else "CHECKS FAILED")
    if not ok_all:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
