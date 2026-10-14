"""Build prompt version two_phase_v5f = two_phase_v5 with new reply formats for both phases (user, 2026-10-13):
LAsset-style keys that a person can read, every key name once per reply format, each object starting with its own
identifier, rows grouped under their conceptual asset in Phase 2 (no "concept id" in rows), primary or secondary kept
as a "Label" (secondaries are not nested under primaries), free-text notes that matter for debugging turned into
fields ("Merged Into", "Not Reported", "No Primary Reason"), and an instruction to follow the format strictly.
No rule text changes: only the OUTPUT sections and the sentences that name reply fields.

Every edit is an exact string replacement that must match once. Checks after writing: the project prompt checker
(check_lab_prompt.check), every edit present, no old reply-field name left in quotes, every key name once per OUTPUT
template, the rule text outside the edits unchanged (v5 text with the edits undone equals v5), shas and word counts.

  python make_v5f.py            (refuses to overwrite an existing two_phase_v5f unless --force)
"""
import hashlib
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
P = LAB / "prompts"
V5, V5F = P / "two_phase_v5", P / "two_phase_v5f"
FILES = ("common.md", "phase1.md", "phase2.md", "phase1_user.md", "phase2_user.md")

STRICT_COMMON = (" Follow its OUTPUT format strictly: every key it shows, spelled exactly as shown and in the order shown, in "
                 "every object, and no other key; put each value under its own key, and write an empty value as an empty "
                 "list or an empty string.")

EDITS = [  # (id, file, old, new)
    ("strict", "common.md", 'Return only the final JSON object described in "THIS CALL", nothing else.',
     'Return only the final JSON object described in "THIS CALL", nothing else.' + STRICT_COMMON),
    ("c57", "common.md", 'where the RTL disagrees, it wins: say so in "notes".',
     'where the RTL disagrees, it wins: say so in "Notes".'),
    ("c61", "common.md", '("rubric reason" in Phase 1, "reason" in Phase 2)',
     '("Rubric Reason" in Phase 1; in Phase 2, a point\'s "Answer Reason" or an asset\'s "Justification")'),
    ("p1-keep", "phase1.md", 'list the rest under "considered, not kept"', 'list the rest under "Not Kept"'),
    ("p1-anchor-in", "phase1.md", 'List under "enters through" each unit port', 'List under "Enters Through" each unit port'),
    ("p1-anchor-out", "phase1.md", 'and under "leaves through" each unit port', 'and under "Leaves Through" each unit port'),
    ("p1-opsel", "phase1.md", 'Do not list them under "enters through" or cite', 'Do not list them under "Enters Through" or cite'),
    ("p2-concepts", "phase2.md",
     'You receive one more input: CONCEPTS, the "conceptual assets" list of Phase 1. Each entry has an "id" (C1, C2, ...), its '
     '"unit", a short name ("concept"), the "information", the "objectives" at risk (C, I, A), the ports it "enters through" and '
     '"leaves through", and the RTL lines where it enters ("entry lines"), is stored or produced ("held lines") and leaves '
     '("exit lines"). Its "rubric", "rubric reason" and "attack" are Phase 1\'s answers',
     'You receive one more input: CONCEPTS, the "Conceptual Assets" list of Phase 1. Each entry has a "Concept ID" (C1, C2, ...), '
     'a short name ("Concept Name"), its "Unit", the "Information", the "Objectives At Risk" (C, I, A), the ports it "Enters '
     'Through" and "Leaves Through", and the RTL lines where it enters ("Entry Lines"), is stored or produced ("Held Lines") and '
     'leaves ("Exit Lines"). Its "Rubric", "Rubric Reason" and "Attack" are Phase 1\'s answers'),
    ("p2-doubt", "phase2.md", 'If you think one is missing or wrong, say so in "notes"',
     'If you think one is missing or wrong, say so in "Notes"'),
    ("p2-blackbox", "phase2.md", "and say in each point's reason that this is the assumption",
     "and say in each point's \"Answer Reason\" that this is the assumption"),
    ("p2-samerole", "phase2.md", 'list the others in "same role"', 'list the others in "Same Role"'),
    ("p2-anchors", "phase2.md", 'Each port in the conceptual asset\'s "enters through" and "leaves through" lists',
     'Each port in the conceptual asset\'s "Enters Through" and "Leaves Through" lists'),
    ("p2-nopoint", "phase2.md", 'with no point between them, say so in "notes".', 'with no point between them, say so in "Notes".'),
    ("p2-noprimary", "phase2.md", 'If none qualifies for a conceptual asset, say why in "notes".',
     'If none qualifies for a conceptual asset, give the reason in its "No Primary Reason".'),
    ("p2-instance", "phase2.md", "name the instance in the reason.", 'name the instance in its "Justification".'),
    ("p2-links", "phase2.md",
     "Label secondary each one that meets 2.7, and list its links: the primary, that primary's entity, and the direction (a or b).",
     'Label secondary each one that meets 2.7, and list under its "Secondary To" each primary it serves: that primary\'s name '
     'and entity, and the direction (a or b).'),
    ("p2-notreported", "phase2.md",
     'A structural asset of step 3 that is neither primary nor secondary is not reported; name it in "notes".',
     'A structural asset of step 3 that is neither primary nor secondary is not reported in "Assets"; list it under '
     '"Not Reported" with the reason.'),
    ("p2-points", "phase2.md", 'List every point you reach in "points"', 'List every point you reach in "Points"'),
    ("u2-concepts", "phase2_user.md", 'CONCEPTS (the "conceptual assets" list of Phase 1; fixed)',
     'CONCEPTS (the "Conceptual Assets" list of Phase 1; fixed)'),
]

OUT1 = '''OUTPUT

Return one JSON object:
{
 "IP": "<the module name given in the input>",
 "Conceptual Assets": [
  {
   "Concept ID": "C1",
   "Concept Name": "<short name of the information>",
   "Unit": "<the UNIT's entity name>",
   "Information": "<one or two sentences: what the information or state is, and which use of the IP depends on it; if it has no entry port and no exit port, say why>",
   "Rubric": {
    "Confidentiality": "yes" | "no",
    "Integrity": "yes" | "no",
    "Availability": "yes" | "no",
    "Undermined Expected Behavior": "yes" | "no"
   },
   "Rubric Reason": "<for each yes, one sentence: the judgement and the mechanism, with line numbers>",
   "Objectives At Risk": ["C" | "I" | "A", ...],
   "Attack": "<one sentence: a plausible way an attacker could violate these objectives>",
   "Enters Through": ["<port or port field>", ...],
   "Leaves Through": ["<port or port field>", ...],
   "Entry Lines": [<RTL line numbers where it enters>],
   "Held Lines": [<RTL line numbers where it is stored or produced>],
   "Exit Lines": [<RTL line numbers where it leaves>]
  }
 ],
 "Not Kept": [
  {
   "Candidate Name": "<short name of the information>",
   "Candidate Unit": "<the UNIT's entity name>",
   "Merged Into": "<the kept Concept ID it was merged into, or an empty string>",
   "Why Not Kept": "<one sentence: which part of which question failed, or which part of the asset test; an empty string for a merged piece>"
  }
 ],
 "Notes": ["<one sentence each: an RTL fact that contradicts the closed set or the diagram, with its line>"]
}
Follow this format strictly: write every key shown, spelled and ordered as shown, in every object, and no other key. Each object starts with its own identifier: "Concept ID" in a conceptual asset, "Candidate Name" in a not-kept entry.
Number the Concept IDs C1, C2, ... across the whole module.
Each objective in "Objectives At Risk" comes from a "yes": confidentiality gives C, integrity gives I, availability gives A, and undermined expected behavior gives the objective the behavior breaks (I when it makes the output incorrect, A when it stops the function).
'''

OUT2 = '''OUTPUT

Return one JSON object:
{
 "IP": "<the module name given in the input>",
 "Concept Walks": [
  {
   "Concept ID": "<an id from CONCEPTS, e.g. C1>",
   "Points": [
    {
     "Point": "<a block name as the ARROWS lines write it (with any ' (line N)' suffix; for an [inst] block, the label without the part in parentheses), or, for a concurrent assignment to an output port, that port's name>",
     "Reached By": "<one sentence: the arrow you followed to this point, or 'holding block', or 'held line'>",
     "Point Answers": {
      "Confidentiality": "yes" | "no",
      "Integrity": "yes" | "no",
      "Availability": "yes" | "no",
      "Undermined Expected Behavior": "yes" | "no"
     },
     "Answer Lines": [<RTL line numbers that show each yes>],
     "Answer Reason": "<one sentence: the mechanism behind each yes, or why none applies>"
    }
   ],
   "Assets": [
    {
     "Asset RTL": "<exact closed-set name>",
     "Entity": "<the entity name that declares it, copied verbatim>",
     "Label": "primary" | "secondary",
     "Same Role": ["<exact closed-set names of the same field of other ports of one role; empty if none>"],
     "Found At": ["<the points where it was found; empty for an element found only as a direct counterpart of a primary>"],
     "Security Objectives": ["C" | "I" | "A", ...],
     "Secondary To": [{"Primary RTL": "<a primary's exact closed-set name>", "Primary Entity": "<its entity>", "Direction": "a" | "b"}],
     "Functionality": "<one sentence: what the element stores, carries, produces or controls for this conceptual asset>",
     "Justification": "<one sentence: why that gives it this label>",
     "Asset Lines": [<RTL line numbers>]
    }
   ],
   "Not Reported": [
    {"Element RTL": "<exact closed-set name>", "Element Entity": "<the entity name that declares it>", "Why Not Reported": "<one sentence: why it is neither primary nor secondary>"}
   ],
   "No Primary Reason": "<one sentence: why no structural asset qualifies as primary; an empty string when one does>"
  }
 ],
 "Notes": ["<one sentence each: an RTL fact that contradicts the inputs, a doubt about CONCEPTS, or a port-to-port path with no point>"]
}
Follow this format strictly: write every key shown, spelled and ordered as shown, in every object, and no other key. Each object starts with its own identifier: "Concept ID" in a walk, "Point" in a point, "Asset RTL" in an asset, "Element RTL" in a not-reported entry.
Give one entry in "Concept Walks" for each conceptual asset in CONCEPTS, in the order CONCEPTS gives, even when its lists are empty.
For a primary, "Secondary To" is an empty list, and "Security Objectives" are those of the "yes" answers at its points (confidentiality gives C, integrity I, availability and undermined expected behavior A). For a secondary, "Security Objectives" are the ones its "Secondary To" entries threaten: C for direction a; for direction b, the objective 2.7 gives it among the conceptual asset's objectives.
'''

# the v5 OUTPUT blocks must be exactly these (checked by sha before they are replaced)
OLD_OUT_SHA = {"phase1.md": None, "phase2.md": None}

# old reply-field names that must not stay in quotes; allowed: closed-set field names common.md uses for its input
OLD_QUOTED = ["module name", "conceptual assets", "considered, not kept", "rubric reason", "enters through",
              "leaves through", "entry lines", "held lines", "exit lines", "concept id", "structural assets", "same role",
              "reached by", "links", "notes", "points", "point", "label", "objectives", "reason", "lines", "element",
              "id", "unit", "concept", "information", "rubric", "attack"]


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def nl(t):
    return "\r\n" if "\r\n" in t else "\n"


def apply(text, old, new, rid):
    n = text.count(old)
    assert n == 1, f"{rid}: expected the old text once, found {n}: {old[:80]}"
    return text.replace(old, new)


def swap_output(text, block, f):
    e = nl(text)
    head, sep, tail = text.partition(e + "OUTPUT" + e)
    assert sep and "OUTPUT" not in tail, f"{f}: OUTPUT heading not found once"
    assert tail.lstrip().startswith("Return one JSON object:"), f"{f}: unexpected OUTPUT block"
    new = block.replace("\n", e)
    if not tail.endswith(e):
        new = new[: -len(e)]
    return head + e + new, (e + "OUTPUT" + e + tail)


def keys_once(block):
    ks = re.findall(r'"([A-Z][A-Za-z ]*)"\s*:', block)
    return ks, {k: n for k, n in Counter(ks).items() if n > 1}


def main(force=False):
    if V5F.exists() and not force:
        raise SystemExit(f"{V5F} exists; use --force to rebuild")
    V5F.mkdir(exist_ok=True)   # files are overwritten below; the folder is kept (a shell may have it as its working directory)
    T = {f: (V5 / f).read_text(encoding="utf-8") for f in FILES}
    old_out = {}
    for rid, f, old, new in EDITS:
        T[f] = apply(T[f], old, new, rid)
    T["phase1.md"], old_out["phase1.md"] = swap_output(T["phase1.md"], OUT1, "phase1.md")
    T["phase2.md"], old_out["phase2.md"] = swap_output(T["phase2.md"], OUT2, "phase2.md")
    crlf = {f: b"\r\n" in (V5 / f).read_bytes() for f in FILES}      # keep each file's line endings as in v5
    for f, t in T.items():
        (V5F / f).write_bytes((t.replace("\n", "\r\n") if crlf[f] else t).encode("utf-8"))
    print("two_phase_v5f written:", ", ".join(f for f in FILES))

    # ---------------- checks
    ok = True
    import check_lab_prompt as CK
    ok &= bool(CK.check("two_phase_v5f"))
    built = {f: (V5F / f).read_bytes().decode("utf-8") for f in FILES}
    missing = [rid for rid, f, old, new in EDITS if new not in built[f]]
    print("every edit present:", not missing, missing or "")
    ok &= not missing
    # undo the edits and the OUTPUT swap: must give v5 byte for byte (no other text changed)
    for f in FILES:
        t = built[f].replace("\r\n", "\n")          # compare text as read_text gives it; line endings checked below
        if f in old_out:
            e = nl(t)
            t = t.partition(e + "OUTPUT" + e)[0] + old_out[f]
        for rid, ef, old, new in reversed(EDITS):
            if ef == f:
                t = t.replace(new, old)
        same = t == (V5 / f).read_text(encoding="utf-8") and crlf[f] == (b"\r\n" in (V5F / f).read_bytes())
        print(f"  {f}: undoing the edits gives v5 exactly (line endings {'CRLF' if crlf[f] else 'LF'} as in v5): {same}")
        ok &= same
    # old reply-field names left in quotes
    left = []
    for f in ("common.md", "phase1.md", "phase2.md", "phase1_user.md", "phase2_user.md"):
        for i, l in enumerate(built[f].splitlines(), 1):
            for n in OLD_QUOTED:
                if f'"{n}"' in l:
                    left.append(f"{f}:{i} \"{n}\"")
    print("old reply-field names still quoted:", left or "none")
    ok &= not left
    for f, block in (("phase1.md", OUT1), ("phase2.md", OUT2)):
        ks, dup = keys_once(block)
        print(f"  {f} OUTPUT: {len(ks)} keys, repeated: {dup or 'none'}")
        ok &= not dup
    s1, s2 = CK.system("two_phase_v5f", 1), CK.system("two_phase_v5f", 2)
    v1, v2 = CK.system("two_phase_v5", 1), CK.system("two_phase_v5", 2)
    print(f"system sha phase 1: v5 {sha(v1)} -> v5f {sha(s1)}; phase 2: v5 {sha(v2)} -> v5f {sha(s2)}")
    wc = lambda t: len(t.split())
    for f in FILES:
        print(f"  words {f}: v5 {wc((V5 / f).read_text(encoding='utf-8'))} -> v5f {wc(built[f])}")
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main("--force" in sys.argv) else 1)
