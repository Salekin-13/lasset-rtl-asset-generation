"""Side check: in v9h, compare each of the four inserted blocks between
phase1.md and phase2.md, line by line, by its label (Scope, Criteria,
Exceptions, Outcome, Evidence). No lab code imported."""
import os

NEW = r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab\prompts\two_phase_v9h"
PREFIXES = ["- Done and wait inputs.", "- Count increment inputs.",
            "- Link handshake ports.", "- Busy locks."]


def blocks(path):
    with open(path, "rb") as f:
        lines = f.read().decode("utf-8").splitlines()
    out = {}
    for p in PREFIXES:
        starts = [k for k, l in enumerate(lines) if l.startswith(p)]
        assert len(starts) == 1, (path, p, starts)
        k = starts[0]
        body = [lines[k]]
        k += 1
        while k < len(lines) and lines[k].startswith((" ", "\t")):
            body.append(lines[k])
            k += 1
        out[p] = {l.strip().split(":")[0]: l.strip() for l in body[1:]}
        out[p]["_n_lines"] = len(body)
    return out


b1 = blocks(os.path.join(NEW, "phase1.md"))
b2 = blocks(os.path.join(NEW, "phase2.md"))
for p in PREFIXES:
    labels = [x for x in ("Scope", "Criteria", "Exceptions", "Outcome", "Evidence")]
    same = [x for x in labels if b1[p].get(x) == b2[p].get(x) and x in b1[p]]
    diff = [x for x in labels if x in b1[p] and x in b2[p] and b1[p][x] != b2[p][x]]
    only1 = [x for x in labels if x in b1[p] and x not in b2[p]]
    only2 = [x for x in labels if x in b2[p] and x not in b1[p]]
    print("%-28s phase1 %d lines, phase2 %d lines | same: %s | differ: %s | phase1 only: %s | phase2 only: %s"
          % (p, b1[p]["_n_lines"], b2[p]["_n_lines"], same, diff, only1, only2))
