"""Protected-word register check of the condensed units (one of the evaluated suggestions, 2026-10-13: a condensed rule
must not lose the words that limit or widen its scope). For each unit of units.md (made by make_trace_inputs.py), the
count of every protected word or phrase in the v6 wording and in the condensed wording; a unit is flagged when any count
falls. Writes register.json. Read-only otherwise.

Protected: words and phrases that set the condition, scope or exception of a rule (only, unless, except, apart from,
even, never, not, no, without, although, regardless, if, when, where, until, while, both, all, any, each, every, own,
other, same, also, still, either, neither, nor, "judged as usual", "not covered", "as usual", "on its own").

  python protected_register.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORDS = ("only", "unless", "except", "even", "never", "not", "no", "without", "although", "though", "regardless", "if",
         "when", "whenever", "where", "until", "while", "both", "all", "any", "each", "every", "own", "other", "same",
         "also", "still", "either", "neither", "nor", "none", "nothing", "cannot")
PHRASES = ("apart from", "judged as usual", "not covered", "as usual", "on its own", "even when", "even if", "even where",
           "only when", "only if", "only while")


def counts(t):
    low = t.lower()
    c = {w: len(re.findall(rf"\b{w}\b", low)) for w in WORDS}
    c.update({p: low.count(p) for p in PHRASES})
    return c


def units():
    out, cur = [], None
    for line in (HERE / "units.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cur = {"id": line[3:].split(" ", 1)[0], "head": line[3:]}
            out.append(cur)
        elif line.startswith("- v6: ") and cur is not None:
            cur["v6"] = line[6:]
        elif line.startswith("- condensed: ") and cur is not None:
            cur["condensed"] = line[13:]
    return out


CLASSES = {                                   # a rewording may swap words within a class ("when" -> "if")
    "condition": ("if", "when", "whenever", "where", "while", "until"),
    "negation": ("not", "no", "never", "none", "nothing", "without", "cannot", "neither", "nor"),
    "only": ("only",),
    "exception": ("except", "unless", "apart from"),
    "concession": ("even", "although", "though", "regardless"),
    "every": ("all", "any", "each", "every", "both"),
    "reference": ("own", "same", "other", "either"),
    "also/still": ("also", "still"),
    "spare list": ("judged as usual", "not covered", "on its own"),
}


def class_counts(t):
    c = counts(t)
    return {k: sum(c[w] for w in ws) for k, ws in CLASSES.items()}


def main():
    U = units()
    flagged = []
    for u in U:
        a, b = class_counts(u["v6"]), class_counts(u["condensed"])
        lost = {k: a[k] - b[k] for k in a if b[k] < a[k]}
        if lost:
            flagged.append({"id": u["id"], "head": u["head"], "lost": lost})
    (HERE / "register.json").write_text(json.dumps({"units": len(U), "flagged": flagged}, indent=1), encoding="utf-8")
    by = {}
    for f in flagged:
        k = "core" if f["id"].startswith("S") else f["id"][:2]
        by[k] = by.get(k, 0) + 1
    print(f"units {len(U)}; flagged (lost a protected word) {len(flagged)}: {by}")
    for f in flagged:
        print(f"  {f['id']:9s} lost {f['lost']}")
    # self-test on hand-made pairs
    assert counts("only when X, not Y")["only when"] == 1 and counts("X")["only"] == 0
    assert not {k for k, v in counts("judged as usual: a, b").items() if v} - {"judged as usual", "as usual"}
    print("self-test PASS")


if __name__ == "__main__":
    main()
