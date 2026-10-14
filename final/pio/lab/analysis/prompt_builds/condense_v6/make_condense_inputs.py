"""Split two_phase_v6's phase1.md and phase2.md into non-overlapping pieces for three condensing tracks (user request
2026-10-13), so that no merge or integration agent is needed:
  v6a  the phase1.md text outside the core sentences      -> chunks/p1_NN.md
  v6b  the phase2.md text outside the core sentences      -> chunks/p2_NN.md
  v6c  the core sentences: every sentence of 6+ words that occurs word for word in BOTH phase bodies -> core/S_NN.md
Frozen (never sent to a condenser): the OUTPUT sections (reply format), common.md, the user templates. In the chunks,
each core sentence is replaced by a placeholder [[S07]] that must come back unchanged and in order.
manifest.json records, per chunk, its text, the line structure needed to reassemble it, and the tokens a code check
requires afterwards: placeholders (same order), bullet or step head, quoted strings, step/section references, and the
rule names other text refers to. Self-test: reassembling the unchanged chunks gives v6's phase files byte for byte (as
text with LF line ends).

  python make_condense_inputs.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
V6 = LAB / "prompts" / "two_phase_v6"
SPL = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\-\[])")
TARGET = 520                       # words per chunk (guide for splitting long text)


def body_and_output(t):
    i = t.index("\nOUTPUT\n")
    return t[:i], t[i:]


def sentences(line):
    return [s for s in SPL.split(line) if s.strip()]


def shared_sentences(b1, b2):
    s1 = [s.strip() for l in b1.split("\n") for s in sentences(l)]
    s2 = {s.strip() for l in b2.split("\n") for s in sentences(l)}
    out = []
    for s in dict.fromkeys(s1):
        if s in s2 and len(s.split()) >= 6:
            out.append(s)
    return out


def tokens(text, names):
    return {
        "quoted": sorted(set(re.findall(r'"[^"\n]{1,80}"', text))),
        "refs": sorted(set(re.findall(r"\b(?:\d\.\d(?:\.\d)?|\d\([a-c]\)|step \d|steps \d(?: and \d)?|section \d|Phase [12])\b", text))),
        "names": sorted(n for n in names if n in text),
        "placeholders": re.findall(r"\[\[S\d\d\]\]", text),
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    raw = {k: (V6 / f"{k}.md").read_text(encoding="utf-8") for k in ("phase1", "phase2")}
    bodies = {k: body_and_output(raw[k]) for k in raw}
    core = shared_sentences(bodies["phase1"][0], bodies["phase2"][0])
    # rule names other text points to: the bullet heads of phase1.md ("- Port buffers.") and step heads
    names = sorted(set(re.findall(r"^- ([A-Z][^.\n]{2,40})\.", bodies["phase1"][0], re.M)))
    marked = {}
    for k in ("phase1", "phase2"):
        b = bodies[k][0]
        for i, s in enumerate(core, 1):
            assert b.count(s) == 1, f"{k}: core sentence {i} occurs {b.count(s)} times"
            b = b.replace(s, f"[[S{i:02d}]]")
        marked[k] = b
    (HERE / "chunks").mkdir(exist_ok=True)
    (HERE / "core").mkdir(exist_ok=True)
    manifest = {"core": [], "chunks": {"phase1": [], "phase2": []}, "names": names}
    for k, tag in (("phase1", "p1"), ("phase2", "p2")):
        lines = marked[k].split("\n")
        pieces = []                 # each piece: list of (line index, segment index, text)
        cur, words = [], 0
        for li, line in enumerate(lines):
            segs = [line] if len(line.split()) <= TARGET else None
            if segs is None:        # a very long line: split at sentence ends into segments of about TARGET words
                segs, acc = [], ""
                for s in sentences(line):
                    if acc and len((acc + " " + s).split()) > TARGET:
                        segs.append(acc)
                        acc = s
                    else:
                        acc = (acc + " " + s).strip() if acc else s
                if acc:
                    segs.append(acc)
            for si, seg in enumerate(segs):
                n = len(seg.split())
                if cur and words + n > TARGET:
                    pieces.append(cur)
                    cur, words = [], 0
                cur.append((li, si, len(segs), seg))
                words += n
        if cur:
            pieces.append(cur)
        for pi, piece in enumerate(pieces, 1):
            cid = f"{tag}_{pi:02d}"
            text = "\n".join(seg for _, _, _, seg in piece)
            entry = {"id": cid, "file": f"{k}.md", "layout": [[li, si, ns] for li, si, ns, _ in piece], "text": text,
                     "words": len(text.split()), "required": tokens(text, names),
                     "heads": [seg.split(". ", 1)[0] + "." for _, si, _, seg in piece
                               if si == 0 and re.match(r"(\s*\d\. [A-Z]|- [A-Z][^.]{2,40}\.|\s*[A-Z][a-z ]+\. |Rules:)", seg)]}
            manifest["chunks"][k].append(entry)
            (HERE / "chunks" / f"{cid}.md").write_text(text, encoding="utf-8")
        manifest["lines"] = manifest.get("lines", {})
        manifest["lines"][k] = len(lines)
    for i, s in enumerate(core, 1):
        ctx = {}
        for k in ("phase1", "phase2"):
            b = bodies[k][0]
            j = b.index(s)
            ctx[k] = {"before": b[max(0, j - 400):j].split("\n")[-1][-400:], "after": b[j + len(s):j + len(s) + 300].split("\n")[0][:300]}
        entry = {"id": f"S{i:02d}", "text": s, "words": len(s.split()), "context": ctx, "required": tokens(s, names)}
        manifest["core"].append(entry)
        (HERE / "core" / f"S{i:02d}.md").write_text(
            f"CORE SENTENCE S{i:02d} (word for word the same in phase1.md and phase2.md):\n{s}\n\n"
            f"In phase1.md it sits after: ...{ctx['phase1']['before']}\nand before: {ctx['phase1']['after']}...\n\n"
            f"In phase2.md it sits after: ...{ctx['phase2']['before']}\nand before: {ctx['phase2']['after']}...\n", encoding="utf-8")
    manifest["output_sections"] = {k: bodies[k][1] for k in bodies}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    # self-test: reassemble unchanged pieces and compare with v6
    ok = True
    for k in ("phase1", "phase2"):
        lines = [[] for _ in range(manifest["lines"][k])]
        for c in manifest["chunks"][k]:
            for (li, si, ns), seg in zip(c["layout"], c["text"].split("\n")):
                lines[li].append(seg)
        b = "\n".join(" ".join(x) for x in lines)
        for e in manifest["core"]:
            b = b.replace(f"[[S{e['id'][1:]}]]", e["text"])
        same = b + bodies[k][1] == raw[k]
        print(f"{k}: {len(manifest['chunks'][k])} chunks, words outside core {sum(c['words'] for c in manifest['chunks'][k]) - 0} (incl. placeholders); reassembly equals v6: {same}")
        ok &= same
    print(f"core sentences: {len(core)}, {sum(e['words'] for e in manifest['core'])} words each phase; rule names tracked: {len(names)}")
    print("self-test:", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
