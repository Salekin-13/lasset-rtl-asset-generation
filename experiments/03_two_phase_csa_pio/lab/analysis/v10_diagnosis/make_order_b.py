"""Stage C, second cell: the order test (PLAN_ISOLATE_CLUSTER_ORDER.md section 8). Order A = the source version as built
(each keep block right after the bar it overrides). Order B = the same text with every keep block moved to the end of its
step: Phase 1 after the last rule (before OUTPUT), Phase 2 at the end of step 4, in the same relative order. Nothing else
changes. Builds <src>_orderB; sends nothing.

  python -B make_order_b.py <src version>            (dry run)
  python -B make_order_b.py <src version> --write
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
import make_v10 as M  # noqa: E402

CK, CH = M.CK, M.CH
KEEP_HEADS = ["- Control record ports.", "- Access command ports.", "- Entry selects and register addresses.", "- Coprocessor progress state.",
              "- Boundary outputs.", "- Done and wait inputs.", "- Link handshake ports.", "- Busy locks.", "- Count increment inputs."]
P1_END = "Judge what a field tells from port field names and their uses; say so."
P2_END_MARK = "\n\n5. Secondary."


def block_at(text, head):
    i = text.find(head)
    if i < 0:
        return None
    j = text.find("\n- ", i + 1)
    k = text.find("\n\n", i + 1)
    end = min(x for x in (j, k, len(text)) if x > 0)
    return text[i:end]


def build(src, log):
    files = M.FILES
    orig = {f: (LAB / "prompts" / src / f).read_text(encoding="utf-8").replace("\r\n", "\n") for f in files}
    new = {"common.md": orig["common.md"]}
    moved = {}
    for f in ("phase1.md", "phase2.md"):
        body = orig[f]
        blocks = []
        for head in KEEP_HEADS:
            b = block_at(body, head)
            if b is None:
                continue
            if body.count(b + "\n") != 1:
                log.append(f"{f} {head}: block occurs {body.count(b)} times")
                continue
            body = body.replace(b + "\n", "", 1)
            blocks.append(b)
        moved[f] = [b.split("\n")[0] for b in blocks]
        if f == "phase1.md":
            if body.count(P1_END) != 1:
                log.append("phase1.md: end anchor not found once")
            else:
                i = body.index(P1_END) + len(P1_END)
                body = body[:i] + "\n" + "\n".join(blocks) + body[i:]
        else:
            if body.count(P2_END_MARK) != 1:
                log.append("phase2.md: step 5 mark not found once")
            else:
                i = body.index(P2_END_MARK)
                body = body[:i] + "\n" + "\n".join(blocks) + body[i:]
        if sorted(body.split("\n")) != sorted(orig[f].split("\n")):
            log.append(f"{f}: the set of lines changed (only the order may change)")
        if body[body.index("\nOUTPUT\n"):] != orig[f][orig[f].index("\nOUTPUT\n"):]:
            log.append(f"{f}: the OUTPUT section changed")
        new[f] = body
    return not log, orig, new, moved


def main(src, write):
    sys.stdout.reconfigure(encoding="utf-8")
    dst = src + "_orderB"
    log = []
    ok, orig, new, moved = build(src, log)
    print("\n".join(log) if log else f"plan: no problems found; moved {moved}")
    if write and ok:
        d = LAB / "prompts" / dst
        d.mkdir(exist_ok=True)
        for f in ("phase1_user.md", "phase2_user.md"):
            shutil.copyfile(LAB / "prompts" / src / f, d / f)
        crlf = b"\r\n" in (LAB / "prompts" / src / "phase1.md").read_bytes()
        for f in M.FILES:
            (d / f).write_bytes((new[f].replace("\n", "\r\n") if crlf else new[f]).encode("utf-8"))
        (d / "README.md").write_text(f"# {dst}: {src} with every keep block moved to the end of its step (order B of the Stage C order test; "
                                     "analysis/v10_diagnosis/make_order_b.py)\n", encoding="utf-8")
        chk = bool(CK.check(dst, log=print))
        nf = CH.new_format(dst, 1) and CH.new_format(dst, 2)
        ok &= chk and nf
        print(f"checker {chk}; new_format {nf}; sha12 {M.sha(CK.system(dst, 1))[:12]} / {M.sha(CK.system(dst, 2))[:12]}")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1], "--write" in sys.argv)
