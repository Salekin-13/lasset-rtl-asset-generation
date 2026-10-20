"""Split a prompt file into numbered clauses (one sentence or one bullet item each) for clause-by-clause meaning checks.

Clause id: <file stem>:<line>.<k> (1-based line of the file, k-th sentence on that line). Sentences split after ". ",
"? " or "! " when the next character starts a new sentence (capital letter, quote or bracket). Self-test: the clauses of each
line, joined with single spaces, give back the line with its whitespace collapsed.

  python clauses.py <prompt dir> <out.json>
"""
import json
import re
import sys
from pathlib import Path

SPLIT = re.compile(r'(?<=[.?!])\s+(?=[A-Z"\'(\[])')


def split_file(path):
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        t = " ".join(line.split())
        if not t:
            continue
        parts = SPLIT.split(t)
        assert " ".join(parts) == t, (path.name, i)
        for k, p in enumerate(parts, 1):
            out.append({"id": f"{path.stem}:{i}.{k}", "line": i, "text": p})
    return out


def main(d, out):
    d = Path(d)
    res = {f: split_file(d / f) for f in ("common.md", "phase1.md")}
    Path(out).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for f, cl in res.items():
        print(f, len(cl), "clauses,", sum(len(c["text"].split()) for c in cl), "words")


if __name__ == "__main__":
    main(*sys.argv[1:3])
