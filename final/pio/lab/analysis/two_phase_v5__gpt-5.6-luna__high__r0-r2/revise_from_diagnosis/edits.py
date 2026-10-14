"""Proposed prompt edits on two_phase_v5, in memory only (nothing is written to the project).
For each edit: anchor found exactly once, project prompt checker on the assembled system prompt, system sha12
(common.md + phase file, as chain.C.system / check_lab_prompt.system build it), net word change (split on spaces)."""
import hashlib, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
LAB = Path(r"E:/jobs/ff/test/Prepoison_subset/final/pio/lab")
sys.path.insert(0, str(LAB))
import check_lab_prompt as CL  # noqa  (sets sys.path for labkit and meta_tools)
K, mt = CL.K, CL.mt
D = LAB / "prompts" / "two_phase_v5"
common = (D / "common.md").read_text(encoding="utf-8")
ph = {1: (D / "phase1.md").read_text(encoding="utf-8"), 2: (D / "phase2.md").read_text(encoding="utf-8")}
sha = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]
sysp = lambda k, p: common.rstrip() + "\n\n" + p
names = K.corpus_names() | mt.corpus_names(str(CL.ROOT))
plant = mt.check_prompt("Report at most 20 signals such as " + sorted(names)[0], names, "plant")
print("checker self-test (3 planted problems caught):", len(plant["problems"]) == 3)
# as-run hashes must match the run files
print("as run: phase1.md alone", sha(ph[1]), "| system 1", sha(sysp(1, ph[1])), "| system 2", sha(sysp(2, ph[2])))
wc = lambda t: len(t.split())

E1 = {
 "U3": ("Do not cite their lines as held lines, except a line assigning an element this rule judges as usual. Judged as usual: the data, chip-select",
        "Do not cite their lines as held lines, except a line assigning an element this rule judges as usual. Their read-back is part of them too: a status bit that software reads and that only reports these flags, or the flags Port buffers covers (whether the engine is busy, whether a FIFO holds data or has room), is not a piece of its own either, although step 1 names status. Do not keep a piece for it, and do not cite its read-back lines as held or exit lines. The read-back of a setting or of a sampled data line is judged as usual. Judged as usual: the data, chip-select"),
 "U4": ("nor is a setting or decision whose only use, apart from a read-back, is to shape that line (its polarity, its phase against the data, or holding it while the peer stretches it), although this rule judges other clock settings as usual. Do not cite their lines as held lines. The link's data and select lines, its rate setting and the unit's clock-enable outputs are judged as usual. Settings or requests controlling a clock (an enable, a rate) are judged as usual,",
        "nor is a setting or decision whose only use, apart from a read-back, is to shape that line: the level it rests at, the edge on which the data is read, or holding it while the peer stretches it. This holds even though a wrong value makes the peer read wrong data, and even when such settings would form a concept of their own: list that concept under \"considered, not kept\". Do not cite their lines as held lines, including the lines where a bus write sets them. Judged as usual: the link's data and select lines, its rate setting (how often the line toggles), and the unit's clock-enable outputs. Other settings or requests controlling a clock (an enable, a rate) are judged as usual,"),
 "U8": ("A decision that a write was refused or carried a wrong value (a write while locked, a wrong password), its gated or registered copies, and a setting choosing only whether such a violation resets are not conceptual assets either when their only uses, apart from a read-back, are to request a reset and record its cause, although step 3 makes a compare of a written value with a fixed value a piece.",
        "A decision that a write was refused or carried a wrong value (a write while locked, a wrong password) and its gated or registered copies are not conceptual assets either when their only uses, apart from a read-back, are to request a reset and record its cause, although step 3 makes a compare of a written value with a fixed value a piece. Nor is a stored setting whose only use, apart from a read-back, is to gate whether such a decision raises a reset (a bit combined with it in an AND), although step 2 names an enable or select deciding whether other information passes."),
 "K1": ("and the read words other instances pass into that instance are not part of it.",
        "and the read words other instances pass into that instance are not part of it. Do not name those read words in the information or cite their lines as held lines."),
 "K2": ("and a count kept only to make it belongs to this piece.",
        "and a count kept only to make it belongs to this piece. Hold it only at that line, not at the port-map lines that wire it on."),
 "U7draft": ("not pieces of their own, although step 2 names a select. Do not list them",
        "not pieces of their own, although step 2 names a select. A setting decoded from them that changes how operands are read (such as signedness) is not such a flag: it is judged as usual, and the lines assigning it are held lines of the piece that holds it. The fields it is decoded from only decide it, so they still do not enter through it. Do not list them"),
 "U7": ("not pieces of their own, although step 2 names a select. Do not list them under \"enters through\" or cite their lines as held lines, except a line assigning an element this rule judges as usual. Judged as usual: a start command or pulse, even one decoded per operation (a multiply start, a divide start), a register access's address and write enable, a completion flag, and a setting decoded from them that changes how operands are read (such as signedness).",
        "not pieces of their own, although step 2 names a select. That does not reach what is decoded from them or travels beside them, which is judged as usual: a start command or pulse, even one decoded per operation (a multiply start, a divide start), a register access's address and write enable, a completion flag, and a setting that changes how operands are read (such as signedness); the lines assigning these are held lines of the piece that holds them. Do not list the fields themselves under \"enters through\" or cite their lines as held lines."),
 "pointer": ("such a decision is information of its own.",
        "such a decision is information of its own. Two rules below, Hand-offs and Register read-back, each make a piece of its own; no other rule removes one, except where Hand-offs itself defers to Port buffers."),
 "HandoffsV4a": ("is its own piece (step 2), unless Port buffers covers it (then this rule does not apply). No step-3 clause or other rule folds it, even when it travels with the data it qualifies, or when it is only one bit of a count: then hold it at the line assigning that bit to the instance output, and a count kept only to make it belongs to this piece.",
        "is its own piece (step 2). No step-3 clause or other rule folds it, even when it travels with the data it qualifies."),
 "dropU10": ("\n- Arbitration bookkeeping. A register that only remembers a request's lock flag while that locked sequence lasts, or the previous grant for round-robin priority, serves the grant or transfer monitor that reads it: it is not a piece of its own, even though step 2 names a lock. Do not cite its lines as held lines. Judged as usual: the current grant, its select and its strobe, requests held until served, a reservation, a lock that software sets to guard later accesses, and a timeout count with its suppression flag.", ""),
 "dropU11": (" Nor is a run-time bit that a statement ANDs with a build-time switch and whose effect includes writing characters to a file or the screen (a simulation-only mode), although a bus write can change it: it belongs to that build choice and is not the run-time decision the next sentence asks for.", ""),
 "dropU12": (" So is a register stage that captures a whole request or response record and passes it on unchanged a cycle later, although it stores the record.", ""),
}
R3P2 = ("A partial result inside a computation of this unit (a partial sum or product, an addend, a subtraction step, a value before the final sign step, or a value computed only to be stored in the register holding the finished result) never qualifies for the result it builds: the element where the finished result is stored, or last computed before it leaves the computation, does. A register or wire that an output port selects among as the finished result qualifies, even when the same register holds operand copies or partial values while the computation runs. An operand register loaded when an operation starts and read only by that operation is a copy kept only while the value moves (2.6), not where the operand is stored.")
R2BP2 = ("A tick, edge pulse or divider count made inside the unit only to pace a step is not primary for any conceptual asset, the rate setting it applies included, unless an output port carries that pulse itself; it can be a secondary (2.7, direction b). A request held until it is served, a start pulse decoded from a received command, and a step counter are not pacing pulses.")
U5P2 = ("In a cache (a unit answering a read from its own copy when a stored tag matches the address, and otherwise fetching the words over a backing bus), the arrays holding the copied words, the tags and the valid bits, and a signal or register that only carries a copied word, tag or valid bit into or out of them, never qualify for any conceptual asset, even where 2.6 makes an element storing the value, or the signal handing it to or from an instance, a primary: the words are copies of data the backing memory holds. They can be secondaries. Judged as usual: the hit, the bytes a write changes, the address, the fill, clear and invalidate commands, and a pending fence or flush. A memory that is itself the store is judged as usual.")
F3A = "even where this step's clause on a decision or setting would make it one."
E2 = {"R3copy": (F3A, F3A + " " + R3P2), "R2Bcopy": (F3A, F3A + " " + R2BP2), "U5copy": (F3A, F3A + " " + U5P2)}

def run(k, edits, label):
    t = ph[k]
    for nm in edits:
        old, new = (E1 if k == 1 else E2)[nm]
        n = t.count(old)
        if n != 1:
            print(f"  {label}: anchor for {nm} found {n} times"); return
        t = t.replace(old, new)
    s = sysp(k, t)
    r = mt.check_prompt(s, names, label)
    probs = r["problems"] + ([] if "only the final json object" in s.lower() else ["no final-JSON phrase"])
    print(f"{label:28s} system{k} sha12 {sha(s)}  words phase{k}.md {wc(ph[k])} -> {wc(t)} ({wc(t)-wc(ph[k]):+d})  checker {'clean' if not probs else probs}")

for nm in E1: run(1, [nm], nm)
run(1, ["U3", "U4", "U8", "U7", "K1", "K2", "pointer"], "all Phase 1 edits")
run(1, ["U3", "U4", "U8", "U7", "K1", "K2", "pointer", "dropU10"], "all P1 edits, U10 text dropped")
for nm in E2: run(2, [nm], nm)
run(2, ["R3copy", "R2Bcopy", "U5copy"], "all Phase 2 copies")
print("rule text words now (split on spaces): U10", wc(E1["dropU10"][0]), "U11", wc(E1["dropU11"][0]), "U12", wc(E1["dropU12"][0]))
NOPRIM = ("A conceptual asset may end with no primary, when 2.6 or this step bars every candidate: then report none of its structural assets, the ports step 3 names included, and name them in \"notes\".")
E2["noPrimary"] = (F3A, F3A + " " + NOPRIM)
run(2, ["noPrimary"], "noPrimary")
run(2, ["R3copy", "R2Bcopy", "U5copy", "noPrimary"], "all Phase 2 edits")
