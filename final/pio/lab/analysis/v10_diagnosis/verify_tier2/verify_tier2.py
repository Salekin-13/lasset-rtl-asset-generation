"""Rebuild check of the r0 Phase 1 records of the tier-2 arms (2026-10-19).

For each arm and each heldout module: rebuild the system message (common.md.rstrip() + two newlines + phase1.md), the
user message (phase1_user.md with module, rtl, diagram, closed_set filled) and the request key, and compare their sha12
with the stored record. Also: model and effort of each record, whether the raw reply parses to a "Conceptual Assets"
list, the LOCATED rule (re-implemented here) against the reference, and the Phase 1 title order ("- " lines of
phase1.md up to the first period) of each arm against two_phase_p1o_first2.

Self-tests run first; if one fails the script stops and reports nothing. No API call is made.
    python -B verify_tier2.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
LAB = Path(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab")
ROOT = Path(r"E:\jobs\ff\test\Prepoison_subset")
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
HELDOUT = LAB / "inputs" / "v1" / "heldout"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))
import chain  # noqa: E402  (only chain.closed_names and chain.run_dir are used)

ARMS = ["two_phase_p1o_first", "two_phase_p1o_first2", "two_phase_p1t2_O1", "two_phase_p1t2_O2",
        "two_phase_p1t2_O3", "two_phase_p1t2_O4", "two_phase_p1t2_O5"]
REBUILD_ARMS = ARMS[1:]            # the six arms the task asks about; p1o_first is run too and reported as extra
BASE = "two_phase_p1o_first2"
MODEL, EFFORT = "gpt-5.6-luna", "high"
LOC_KEYS = ("gets value from", "decided by", "reset by", "clocked by")


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def parse_json(text: str):
    """Same steps as labkit.parse_json: strip a code fence, take the outermost braces, json.loads."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


# ---------------------------------------------------------------------------------------------- messages ---
def system_message(version: str) -> str:
    d = LAB / "prompts" / version
    return read(d / "common.md").rstrip() + "\n\n" + read(d / "phase1.md")


def user_message(version: str, m: str) -> str:
    d = HELDOUT / m
    t = read(LAB / "prompts" / version / "phase1_user.md")
    cs = json.dumps(json.loads(read(d / "closed_set.json")), separators=(",", ":"))
    return t.format(module=m, rtl=read(d / "rtl.txt"), diagram=read(d / "diagram.txt"), closed_set=cs)


# ---------------------------------------------------------------------------------------------- LOCATED ---
def _ints(xs) -> set[int]:
    out = set()
    for x in (xs if isinstance(xs, list) else []):
        if isinstance(x, bool):
            continue
        if isinstance(x, int):
            out.add(x)
        elif isinstance(x, str) and x.isdigit():
            out.add(int(x))
    return out


def assignment_lines(m: str) -> tuple[set[str], dict[str, set[int]]]:
    """(closed-set names of any entity, name -> union of assignment lines over every entity carrying the name)."""
    cn = chain.closed_names(m)
    names = {x for (_, x) in cn}
    assign: dict[str, set[int]] = {}
    for (_, x), fx in cn.items():
        ls = assign.setdefault(x, set())
        for key in LOC_KEYS:
            for c in ((fx.get("counterparts") or {}).get(key) or []):
                if isinstance(c, dict):
                    ls |= _ints(c.get("lines"))
    return names, assign


def _lst(v) -> list:
    return v if isinstance(v, list) else ([v] if isinstance(v, str) else [])


def located_names(names: set[str], assign: dict[str, set[int]], concepts) -> set[str]:
    """Union over the reply's entries of the LOCATED set of each entry."""
    out: set[str] = set()
    for c in concepts or []:
        if not isinstance(c, dict):
            continue
        ports = [p for p in _lst(c.get("Enters Through")) + _lst(c.get("Leaves Through")) if isinstance(p, str)]
        held = _ints(_lst(c.get("Held Lines")))
        out |= {p for p in ports if p in names}
        out |= {x for x, ls in assign.items() if ls & held}
    return out


def reference_rows(m: str, names: set[str]) -> list[str]:
    g = json.loads(read(GT))["modules"][m]["assets"]
    return [r["element"] for r in g if r.get("element") in names]


# ---------------------------------------------------------------------------------------------- titles ---
def titles(version: str) -> list[str]:
    return [l[2:].split(".")[0] for l in read(LAB / "prompts" / version / "phase1.md").splitlines() if l.startswith("- ")]


def lcs(a: list[str], b: list[str]) -> list[str]:
    n, k = len(a), len(b)
    dp = [[0] * (k + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(k - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if a[i] == b[j] else max(dp[i + 1][j], dp[i][j + 1])
    out, i, j = [], 0, 0
    while i < n and j < k:
        if a[i] == b[j]:
            out.append(a[i]); i += 1; j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


def order_diff(arm: list[str], base: list[str]) -> dict:
    common_arm = [t for t in arm if t in base]
    common_base = [t for t in base if t in arm]
    keep = set(lcs(common_arm, common_base))
    moved = [t for t in common_arm if t not in keep]
    return {"titles": len(arm), "added (not in base)": [t for t in arm if t not in base],
            "removed (in base, not here)": [t for t in base if t not in arm],
            "same order as base": common_arm == common_base,
            "moved blocks (outside the longest common subsequence)":
                [{"title": t, "base position": base.index(t) + 1, "position here": arm.index(t) + 1} for t in moved]}


# ---------------------------------------------------------------------------------------------- self-tests ---
def selftest() -> None:
    # 1. sha12 against a hand-known value: sha256("") = e3b0c44298fc1c14...
    assert sha12("") == "e3b0c44298fc", sha12("")
    # 2. LOCATED on neorv32_gpio, hand-read from inputs/v1/heldout/neorv32_gpio/closed_set.json:
    #    port_in: gets value from gpio_i [103], clocked by clk_i [102], reset by rstn_i [99], no "decided by"
    #    port_out: gets value from bus_req_i.data [74], decided by [73, 72, 71], clocked [64], reset [57]
    names, assign = assignment_lines("neorv32_gpio")
    assert assign["port_in"] == {103, 102, 99}, assign["port_in"]
    assert assign["port_out"] == {74, 73, 72, 71, 64, 57}, assign["port_out"]
    loc = located_names(names, assign, [{"Concept ID": "X", "Enters Through": ["gpio_i", "not_a_name"],
                                         "Leaves Through": "gpio_o", "Held Lines": [103]}])
    assert {"gpio_i", "gpio_o", "port_in"} <= loc and "not_a_name" not in loc and "port_out" not in loc, loc
    loc2 = located_names(names, assign, [{"Concept ID": "Y", "Held Lines": ["74"]}])
    assert "port_out" in loc2 and "port_in" not in loc2, loc2
    assert located_names(names, assign, [{"Concept ID": "Z", "Held Lines": [True]}]) == set()
    # 3. parse_json on a fenced reply
    assert parse_json('```json\n{"a": [1]}\n```') == {"a": [1]}
    # 4. titles: first2 line 25 is "- Debug module registers." (hand-read); the first three are the general lines
    t = titles(BASE)
    assert t[:4] == ["Describe a conceptual asset by what the information is, not an element name", "Precedence",
                     "Reading a rule", "Debug module registers"], t[:4]
    # 5. lcs / order_diff on a toy case
    d = order_diff(["a", "c", "b", "d"], ["a", "b", "c", "d"])
    assert len(d["moved blocks (outside the longest common subsequence)"]) == 1, d
    assert order_diff(["a", "b"], ["a", "b"])["same order as base"]
    # 6. one stored record rebuilds by hand-known shas (O1 gpio: system 7620a54a30db, user 44588a2b9271, key ef13ede06025)
    s, u = system_message("two_phase_p1t2_O1"), user_message("two_phase_p1t2_O1", "neorv32_gpio")
    assert (sha12(s), sha12(u), sha12(s + "\n\n" + u)) == ("7620a54a30db", "44588a2b9271", "ef13ede06025")


# ---------------------------------------------------------------------------------------------- main ---
def check_arm(version: str, modules: list[str], gt_rows: dict[str, list[str]], loc_inputs: dict) -> dict:
    out = chain.run_dir(version, MODEL, 0, EFFORT)
    meta = json.loads(read(out / "_run_meta.json")) if (out / "_run_meta.json").exists() else {}
    sys_txt = system_message(version)
    ss = sha12(sys_txt)
    tmpl_sha = sha12(read(LAB / "prompts" / version / "phase1_user.md"))
    present, rebuilt, mismatches, parsed, parsed_stored, models, efforts = [], 0, [], 0, 0, {}, {}
    located, located_modules, problems_unparseable, gt_parsed = 0, 0, 0, 0
    for m in modules:
        p = out / "phase1" / f"{m}.json"
        if not p.exists():
            continue
        present.append(m)
        rec = json.loads(read(p))
        u = user_message(version, m)
        us, key = sha12(u), sha12(sys_txt + "\n\n" + u)
        usage = rec.get("usage") or {}
        stored = (rec.get("system sha"), rec.get("user sha"), usage.get("request key"), rec.get("prompt version"),
                  rec.get("module"), rec.get("phase"))
        want = (ss, us, key, version, m, 1)
        if stored == want:
            rebuilt += 1
        else:
            mismatches.append({"module": m, "stored": stored, "rebuilt": want})
        models[usage.get("model")] = models.get(usage.get("model"), 0) + 1
        efforts[usage.get("effort")] = efforts.get(usage.get("effort"), 0) + 1
        try:
            obj = parse_json(rec.get("raw") or "")
        except ValueError:
            obj = None
        ca = obj.get("Conceptual Assets") if isinstance(obj, dict) else None
        ok = isinstance(ca, list) and all(isinstance(c, dict) for c in ca)
        if ok:
            parsed += 1
            names, assign = loc_inputs[m]
            loc = located_names(names, assign, ca)
            located += sum(1 for e in gt_rows[m] if e in loc)
            located_modules += 1
            gt_parsed += len(gt_rows[m])
        r = rec.get("reply")
        if isinstance(r, dict) and isinstance(r.get("conceptual assets"), list):
            parsed_stored += 1
        if any(str(x).startswith("unparseable reply") for x in rec.get("problems") or []):
            problems_unparseable += 1
    missing = [m for m in modules if m not in present]
    keys = {}
    kp = out / "_keys.jsonl"
    if kp.exists():
        for l in read(kp).splitlines():
            if l.strip():
                x = json.loads(l)
                keys[x["key"]] = (x.get("module"), x.get("phase"))
    pending = sorted(f.stem for f in (out / "_pending").glob("*.json")) if (out / "_pending").exists() else []
    abandoned = sorted(f.name for f in (out / "_pending_abandoned").iterdir()) if (out / "_pending_abandoned").exists() else []
    return {
        "run folder": str(out),
        "records present": len(present), "modules missing": missing,
        "rebuilt (system sha, user sha, request key, version, module, phase all equal)": rebuilt,
        "mismatches": mismatches,
        "meta model/effort": (meta.get("model"), meta.get("effort")),
        "meta system sha phase 1 == rebuilt": meta.get("system sha phase 1") == ss,
        "meta user template sha phase 1 == rebuilt": meta.get("user template sha phase 1") == tmpl_sha,
        "rebuilt system sha": ss, "rebuilt user template sha": tmpl_sha,
        "model per record": models, "effort per record": efforts,
        "parsed replies (raw -> Conceptual Assets list of objects)": parsed,
        "stored 'reply' has conceptual assets list": parsed_stored,
        "records with an unparseable-reply problem": problems_unparseable,
        "located reference rows (modules with a parsed reply)": located,
        "reference rows in modules with a parsed reply (exact)": gt_parsed,
        "modules with a parsed reply": located_modules,
        "pending requests": [{"key": k, "attributed to": keys.get(k)} for k in pending],
        "abandoned pending files": abandoned,
        "failed calls log present": (out / "_failed_calls.jsonl").exists(),
    }


def main() -> None:
    selftest()
    modules = sorted(d.name for d in HELDOUT.iterdir() if d.is_dir())
    assert len(modules) == 26, len(modules)
    loc_inputs = {m: assignment_lines(m) for m in modules}
    gt_rows = {m: reference_rows(m, loc_inputs[m][0]) for m in modules}
    base = titles(BASE)
    report = {"self-test": "PASS", "modules": len(modules),
              "reference rows in the closed set over the 26 modules": sum(len(v) for v in gt_rows.values()),
              "arms": {}, "title order": {}}
    for v in ARMS:
        r = check_arm(v, modules, gt_rows, loc_inputs)
        r["required by the task"] = v in REBUILD_ARMS
        report["arms"][v] = r
        report["title order"][v] = {"order": titles(v), **order_diff(titles(v), base)}
    (HERE / "verify_tier2_result.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
