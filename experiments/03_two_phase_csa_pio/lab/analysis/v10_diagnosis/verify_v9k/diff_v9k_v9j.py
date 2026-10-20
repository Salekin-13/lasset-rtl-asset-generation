"""File-by-file comparison of prompts/two_phase_v9k against prompts/two_phase_v9j.

Reads the files only. No API calls. No imports from the run/score scripts.
"""
import difflib
import json
import os
import sys

LAB = r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab"
A = os.path.join(LAB, "prompts", "two_phase_v9k")   # new
B = os.path.join(LAB, "prompts", "two_phase_v9j")   # working version
EXPECTED_SAME = ["common.md", "phase1.md", "phase1_user.md", "phase2_user.md"]


def read_bytes(p):
    with open(p, "rb") as f:
        return f.read()


def main():
    out = {}
    files_a = sorted(os.listdir(A))
    files_b = sorted(os.listdir(B))
    out["files_v9k"] = files_a
    out["files_v9j"] = files_b
    out["only_in_v9k"] = sorted(set(files_a) - set(files_b))
    out["only_in_v9j"] = sorted(set(files_b) - set(files_a))

    per_file = {}
    for name in sorted(set(files_a) | set(files_b)):
        pa, pb = os.path.join(A, name), os.path.join(B, name)
        if not (os.path.isfile(pa) and os.path.isfile(pb)):
            per_file[name] = {"present_in_both": False}
            continue
        ba, bb = read_bytes(pa), read_bytes(pb)
        per_file[name] = {
            "present_in_both": True,
            "bytes_v9k": len(ba),
            "bytes_v9j": len(bb),
            "byte_identical": ba == bb,
        }
    out["per_file"] = per_file

    out["expected_same_check"] = {
        n: per_file.get(n, {}).get("byte_identical") for n in EXPECTED_SAME
    }

    # --- phase2.md: structure of the difference ---
    ta = read_bytes(os.path.join(A, "phase2.md")).decode("utf-8")
    tb = read_bytes(os.path.join(B, "phase2.md")).decode("utf-8")
    la = ta.splitlines(keepends=True)
    lb = tb.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(a=lb, b=la, autojunk=False)
    opcodes = [op for op in sm.get_opcodes() if op[0] != "equal"]
    out["phase2_line_count_v9j"] = len(lb)
    out["phase2_line_count_v9k"] = len(la)
    out["phase2_opcodes_nonequal"] = [
        {"op": tag, "v9j_lines": [i1 + 1, i2], "v9k_lines": [j1 + 1, j2]}
        for tag, i1, i2, j1, j2 in opcodes
    ]
    p2 = {}
    p2["single_insert"] = len(opcodes) == 1 and opcodes[0][0] == "insert"
    if p2["single_insert"]:
        tag, i1, i2, j1, j2 = opcodes[0]
        block_lines = la[j1:j2]
        block = "".join(block_lines)
        p2["block_text"] = block
        p2["block_first_line"] = block_lines[0].rstrip("\n")
        p2["block_line_count"] = len(block_lines)
        p2["block_nonblank_line_count"] = sum(1 for l in block_lines if l.strip())
        p2["block_word_count_whitespace_split"] = len(block.split())
        p2["block_char_count"] = len(block)
        p2["inserted_after_v9j_line"] = i1   # 1-based line number in v9j it follows
        p2["inserted_at_v9k_lines"] = [j1 + 1, j2]
        # Also confirm: removing the block from v9k gives v9j exactly.
        p2["v9k_minus_block_equals_v9j"] = "".join(la[:j1] + la[j2:]) == tb

        # Position checks (in v9k, 1-based)
        def first_line_starting(prefix, lines):
            return [k + 1 for k, l in enumerate(lines) if l.startswith(prefix)]
        pos = {}
        pos["4. Primary."] = first_line_starting("4. Primary.", la)
        pos["5. Secondary."] = first_line_starting("5. Secondary.", la)
        pos["- Processor control-unit state."] = first_line_starting("- Processor control-unit state.", la)
        pos["- Control record ports."] = first_line_starting("- Control record ports.", la)
        pos["- Walk-found internals."] = first_line_starting("- Walk-found internals.", la)
        p2["line_positions_v9k"] = pos
        ins_start, ins_end = j1 + 1, j2
        # The block in v9k spans ins_start..ins_end. Previous non-blank line before it, next after it.
        prev_nb = next((la[k].rstrip("\n") for k in range(j1 - 1, -1, -1) if la[k].strip()), None)
        next_nb = next((la[k].rstrip("\n") for k in range(j2, len(la)) if la[k].strip()), None)
        p2["line_before_block_nonblank"] = prev_nb
        p2["line_after_block_nonblank"] = next_nb
        # Which block does the previous non-blank line belong to? Walk back to the nearest "- " bullet head.
        def bullet_head_before(idx):
            for k in range(idx, -1, -1):
                if la[k].startswith("- "):
                    return k + 1, la[k].rstrip("\n")
            return None
        p2["bullet_head_before_block"] = bullet_head_before(j1 - 1)
        p2["bullet_head_at_or_after_block"] = next(
            ((k + 1, la[k].rstrip("\n")) for k in range(j2, len(la)) if la[k].startswith("- ")), None)
        p4 = pos["4. Primary."]
        p5 = pos["5. Secondary."]
        p2["inside_step4"] = bool(p4 and p5 and p4[0] < ins_start and ins_end < p5[0])
        pcs = pos["- Processor control-unit state."]
        crp = pos["- Control record ports."]
        p2["after_processor_control_unit_state"] = bool(pcs and pcs[0] < ins_start)
        p2["before_control_record_ports"] = bool(crp and ins_end < crp[0])
        # No other bullet head between "Processor control-unit state." block head and the insert?
        heads_between = [(k + 1, la[k].rstrip("\n")) for k in range(pcs[0], j1) if la[k].startswith("- ")] if pcs else None
        p2["bullet_heads_between_pcs_and_block"] = heads_between
        heads_after = [(k + 1, la[k].rstrip("\n")) for k in range(j2, crp[0] - 1) if la[k].startswith("- ")] if crp else None
        p2["bullet_heads_between_block_and_crp"] = heads_after
    out["phase2"] = p2

    # README.md difference, full text of both (small files)
    if per_file.get("README.md", {}).get("present_in_both"):
        out["readme_v9k"] = read_bytes(os.path.join(A, "README.md")).decode("utf-8")
        out["readme_v9j"] = read_bytes(os.path.join(B, "README.md")).decode("utf-8")

    # Unified diff of phase2 for the record
    out["phase2_unified_diff"] = "".join(difflib.unified_diff(lb, la, "v9j/phase2.md", "v9k/phase2.md", n=2))

    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
