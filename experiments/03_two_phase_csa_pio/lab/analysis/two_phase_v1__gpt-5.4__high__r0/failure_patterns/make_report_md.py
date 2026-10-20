"""Builds FAILURE_PATTERNS.md (concise) and FAILURE_PATTERNS_APPENDIX.md (every element) from pack.json and the agents'
results in the workflow journal. Every count is computed here from pack.json and the agents' labels (cluster membership,
concept verdicts). Text columns that come from agents are marked as such; a few factual slips found by the review of
2026-10-11 are corrected in CORRECTIONS below, each checked against the text it replaces. The first version is kept as
make_report_md_v1.py.bak.

  python make_report_md.py <path to the workflow's journal.jsonl>
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE.parent
FOUND = ("found", "found inside a broader model concept", "found split")
MATCHED = ("matches", "broader", "narrower")
VERDICT_MEANING = [
    ("found", "a model concept is the same information"),
    ("found inside a broader model concept", "a model concept covers it together with other information"),
    ("found split", "two or more model concepts together cover it"),
    ("partly found", "model concepts cover only part of it (counted as a failure here)"),
    ("missed: considered, not kept", "the model named it in Phase 1 and then dropped it"),
    ("missed: never a concept", "no model concept covers it, and the model did not consider it"),
]
WH = {"unit port": "port", "unit port field": "port field", "internal signal": "signal", "internal record field": "record field",
      "sub-unit port": "sub-unit port", "sub-unit port field": "sub-unit port field", "absent": "absent"}
ROLE = {"stored (register)": "register", "output, stored (register)": "output register", "input, read only": "input, no use found"}
# factual slips in agents' texts found by the accuracy review; (clustering, cluster name start, field, old, new)
CORRECTIONS = [
    ("cf2", "K4", "pattern", "All three are I, A (", "cache:C3 and imem:C3 are I, A; bus:C15 is C, I, A ("),
    ("cf2", "K1", "pattern", "The attack text leads with snooping", "Four of the seven attack texts lead with snooping"),
    ("sfn", "One-bit handshake", "name", "One-bit handshake and gate flags, folded into what they gate",
     "Handshake, select and gate signals, folded into what they gate"),
    ("cf1", "Bus-request decodes", "pattern",
     "The unit's 'considered, not kept' list drops the whole bus request as ordinary access, and the decode is dropped with it.",
     "In trng, the 'considered, not kept' list drops the whole bus request as ordinary access, and the decode goes with it. "
     "In hwspinlock, the model rejected sel on its own, as only an address decode."),
    ("sfp", "C3.", "why_the_model_listed_them", "a written enable bit, a key or a byte", "a written enable bit, a control value or a byte"),
    ("sfn", "Input pins named", "why_missed", "The two missed control pins only decide their concept.",
     "The two missed control pins only decide their concept. enable_i was an entry port, but the model judged it not primary "
     "because line 129 reduces it with or_reduce_f."),
]


def cell(t):
    return " ".join(str(t if t is not None else "").split()).replace("|", "\\|")


def sent(t, n=200):
    """Whole sentences up to about n characters; a single long first sentence is kept whole up to 3n."""
    t = " ".join(str(t or "").split())
    parts, out = re.split(r"(?<=[.!?])\s+(?=[A-Z'(])", t), ""
    for x in parts:
        if out and len(out) + len(x) > n:
            return cell(out)
        out = (out + " " + x).strip()
    return cell(out if len(out) <= 3 * n else out[: 3 * n].rsplit(" ", 1)[0] + " ... (full text in appendix A6)")


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(cell(x) for x in r) + " |" for r in rows]
    return out + [""]


def journal(path):
    label, res = {}, {}
    for l in open(path, encoding="utf-8"):
        d = json.loads(l)
        if d["type"] == "started":
            label[d["agentId"]] = d["label"]
        elif d["type"] == "result" and d.get("agentId") in label:
            r = d["result"]
            res[label[d["agentId"]]] = json.loads(r) if isinstance(r, str) and r[:1] in "{[" else r
    return res


def short(m):
    return m.replace("neorv32_", "")


def rc(gid):
    return "RC" + gid[1:] if re.fullmatch(r"G\d+", gid or "") else gid


OBJ = {"confidentiality": "C", "integrity": "I", "availability": "A", "c": "C", "i": "I", "a": "A"}


def objs(xs):
    return ", ".join(dict.fromkeys(OBJ.get(x.strip().lower(), x) for x in xs))


def rids(items):
    """Distinct R ids in an agent's list of correct finds, leaving out 'contrast' notes."""
    out = []
    for x in items:
        if re.match(r"\s*(contrast|no correct find)", x, re.I):
            continue
        out += [r for r in re.findall(r"\bR\d{3}\b", x) if r not in out]
    return out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    J = journal(sys.argv[1])
    pack = json.loads((HERE / "pack.json").read_text(encoding="utf-8"))
    blocks = json.loads((HERE / "fp_blocks.json").read_text(encoding="utf-8"))
    table_old = json.loads((ANALYSIS / "table.json").read_text(encoding="utf-8"))
    mods = list(pack["modules"])
    problems = []

    def tx(t, sfp_text=False):
        """Agent text made readable: block ids -> row ids, reference concept ids G -> RC."""
        t = str(t or "")
        t = re.sub(r"\bF(\d{3})\b", lambda m: (blocks.get(m.group(0), ["?"])[0] + (f" (+{len(blocks[m.group(0)]) - 1} copies)"
                                                                                  if len(blocks.get(m.group(0), [])) > 1 else "")), t)
        t = re.sub(r"\bG([1-9]\d?)\b", r"RC\1", t)
        t = t.replace("Measured:", "Agent's check:").replace("Measured over", "Agent's check over")
        if sfp_text:
            t = re.sub(r"stays in C(\d+)", r"stays in S\1", t)
        return t

    # ------------------------------------------------ agents' labels
    gt, match = {}, {}
    for m in mods:
        s = short(m)
        gt[m] = J[f"gt-final:{s}"]
        match[m] = J[f"match-adj:{s}"] if f"match-adj:{s}" in J else J[f"match-1:{s}"]
        names = [e["name"] for e in pack["modules"][m]["reference entries"]]
        homes = Counter(h for c in gt[m]["concepts"] for h in c["home_elements"])
        for n in set(names):
            if homes[n] != names.count(n):
                problems.append(f"{s}: reference element {n} is the home of {homes[n]} concepts (listed {names.count(n)} times)")
        if {c["id"] for c in gt[m]["concepts"]} != {x["id"] for x in match[m]["gt_concepts"]}:
            problems.append(f"{s}: matching does not cover the reference concepts")
        if {c["id"] for c in pack["modules"][m]["model concepts"]} != {x["id"] for x in match[m]["model_concepts"]}:
            problems.append(f"{s}: matching does not cover the model concepts")
    n_adj = sum(f"match-adj:{short(m)}" in J for m in mods)
    sfp, sfn, cf1, cf2 = J["sfp-final"], J["sfn-final"], J["cf1-final"], J["cf2-final"]
    by = {"sfp": sfp, "sfn": sfn, "cf1": cf1, "cf2": cf2}
    for key, start, field, old, new in CORRECTIONS:
        c = next(c for c in by[key]["clusters"] if c["name"].startswith(start))
        assert old in c[field], (key, start, field, old)
        c[field] = c[field].replace(old, new)
    home_of = {}
    for m in mods:
        for c in gt[m]["concepts"]:
            for h in c["home_elements"]:
                home_of.setdefault((m, h), c["id"])
    gverd = {(m, x["id"]): x for m in mods for x in match[m]["gt_concepts"]}
    mverd = {(m, x["id"]): x for m in mods for x in match[m]["model_concepts"]}
    gcon = {(m, c["id"]): c for m in mods for c in gt[m]["concepts"]}
    mcon = {(m, c["id"]): c for m in mods for c in pack["modules"][m]["model concepts"]}
    fp_rows = {x["id"]: (m, x) for m in mods for x in pack["modules"][m]["FP"]}
    fn_rows = {x["entry"]: (m, x) for m in mods for x in pack["modules"][m]["FN"]}
    tp_rows = {x["id"]: (m, x) for m in mods for x in pack["modules"][m]["TP"]}

    def clean(n):
        return re.sub(r"^\s*[A-Z]{1,2}\d+[.:]?\s+", "", n)
    fp_cluster, seen_b = {}, Counter()
    for i, c in enumerate(sfp["clusters"], 1):
        c["cid"], c["name"] = f"S{i}", clean(c["name"])
        for b in c["blocks"]:
            seen_b[b] += 1
            for r in blocks.get(b, []):
                fp_cluster[r] = c["cid"]
        c["rows"] = [r for b in c["blocks"] for r in blocks.get(b, [])]
    for b in blocks:
        if seen_b[b] != 1:
            problems.append(f"structural FP block {b} is in {seen_b[b]} clusters")
    fn_cluster, seen_e = {}, Counter()
    for i, c in enumerate(sfn["clusters"], 1):
        c["cid"], c["name"] = f"M{i}", clean(c["name"])
        for e in c["entries"]:
            seen_e[e] += 1
            fn_cluster[e] = c["cid"]
    for e in fn_rows:
        if seen_e[e] != 1:
            problems.append(f"structural miss {e} is in {seen_e[e]} clusters")
    f1_items = [f"{short(m)}:{x['id']}" for m in mods for x in match[m]["gt_concepts"] if x["verdict"] not in FOUND]
    f2_items = [f"{short(m)}:{x['id']}" for m in mods for x in match[m]["model_concepts"] if x["verdict"] not in MATCHED]
    for tag, cl, items, prefix in (("conceptual miss", cf1, f1_items, "CM"), ("extra concept", cf2, f2_items, "CX")):
        cnt = Counter()
        for i, c in enumerate(cl["clusters"], 1):
            c["cid"], c["name"] = f"{prefix}{i}", clean(c["name"])
            for x in c["members"]:
                cnt[x] += 1
        for x in items:
            if cnt[x] != 1:
                problems.append(f"{tag} {x} is in {cnt[x]} clusters")
        for x in cnt:
            if x not in items:
                problems.append(f"{tag} cluster lists {x}, which is not a failure item")

    # ------------------------------------------------ counts
    T = pack["totals"]
    n_ref, n_abs = T["entries"], T["absent"]
    P, R_all, R_find = T["tp"] / T["listed"], T["tp"] / n_ref, T["tp"] / (n_ref - n_abs)
    old_tp = sum(r["verdict"] == "TP" for r in table_old["rows"])
    old_fp = sum(r["verdict"] == "FP" for r in table_old["rows"])
    gv = Counter(x["verdict"] for x in gverd.values())
    mv = Counter(x["verdict"] for x in mverd.values())
    n_g, n_m = len(gverd), len(mverd)
    g_found = sum(gv[v] for v in FOUND)
    m_match = sum(mv[v] for v in MATCHED)
    extra = {(m, x["id"]) for m in mods for x in match[m]["model_concepts"] if x["verdict"] not in MATCHED}

    def source(m, x):
        cs = [(m, c) for c in x["concepts"]]
        return "only extra concepts" if cs and all(c in extra for c in cs) else "a matching concept" if cs else "no concept"
    fp_from = Counter(source(m, x) for m, x in fp_rows.values())
    tp_from = Counter(source(m, x) for m, x in tp_rows.values())
    fn_concept, fn_from = {}, Counter()
    for e, (m, x) in fn_rows.items():
        h = home_of.get((m, x["name"]))
        v = gverd[(m, h)]["verdict"] if (m, h) in gverd else "?"
        fn_concept[e] = (rc(h), v)
        fn_from["found" if v in FOUND else "partly found" if v == "partly found" else "missed"] += 1
    sig3 = lambda x: (x["signature"]["where"], x["signature"]["role"], x["signature"]["record"])  # noqa: E731
    for c in sfp["clusters"]:
        sigs = {sig3(fp_rows[r][1]) for r in c["rows"]}
        c["tp_mech"] = sorted(t for t, (m, x) in tp_rows.items() if sig3(x) in sigs)
        c["tp_agent"] = rids(c["tp_same_shape"])
    for c in sfn["clusters"]:
        c["tp_agent"] = rids(c["tp_same_shape"])
    for c in cf2["clusters"]:
        cs = {(f"neorv32_{x.split(':')[0]}", x.split(":")[1]) for x in c["members"]}
        touch = [r for r, (m, x) in fp_rows.items() if any((m, k) in cs for k in x["concepts"])]
        c["fp_distinct"] = len(touch)
        c["fp_only_extra"] = sum(1 for r in touch if source(*fp_rows[r]) == "only extra concepts")
    yld = defaultdict(lambda: [0, 0])
    for m, x in tp_rows.values():
        for k in x["concepts"]:
            yld[(m, k)][0] += 1
    for m, x in fp_rows.values():
        for k in x["concepts"]:
            yld[(m, k)][1] += 1

    def breakdown(xs, key):
        c = Counter(key(x) for x in xs)
        return ", ".join(f"{k} {v}" for k, v in c.most_common())

    def role_of(x):
        r = x["signature"]["role"]
        return ROLE.get(r, r)

    def mentioned(seen):
        sec = sorted({s.split()[0] for s in seen if " Phase 2 secondary " in s}, key=lambda c: int(re.sub(r"\D", "", c) or 0))
        pri = [s for s in seen if " Phase 2 primary " in s]
        anc = sorted({s.split()[0] for s in seen if " anchor (" in s})
        p1 = sorted({s.split()[0] for s in seen if "named in its Phase 1 text" in s})
        nk = [s.split(": ", 1)[1] for s in seen if s.startswith("Phase 1 'considered, not kept'")]
        reas = sum(1 for s in seen if "named in the reasoning of point" in s)
        walk = sum(1 for s in seen if "named only in the walk path" in s)
        out = []
        if pri:
            out.append("listed as primary under a related name: " + "; ".join(
                re.sub(r"^(\S+) Phase 2 primary (\S+) \[(.*)\]$", r"\2 (\1, \3)", s) for s in pri[:2]))
        if sec:
            out.append("secondary under " + ", ".join(sec))
        if anc:
            out.append("entry or exit port of " + ", ".join(anc))
        if p1:
            out.append("named in the Phase 1 text of " + ", ".join(p1))
        if nk:
            out.append("in 'considered, not kept' ('" + "', '".join(nk) + "')")
        if reas:
            out.append(f"named in {reas} point reason{'s' if reas > 1 else ''}")
        if walk:
            out.append(f"in {walk} walk path{'s' if walk > 1 else ''} only")
        return "; ".join(out) or "never named"

    # earlier stage labels (PROMPT_FAILURE_DIAGNOSIS.xlsx, Missed entries)
    old_stage = {}
    try:
        from openpyxl import load_workbook
        ws = load_workbook(ANALYSIS / "PROMPT_FAILURE_DIAGNOSIS.xlsx", read_only=True)["Missed entries"]
        rows_ = list(ws.iter_rows(values_only=True))
        h = rows_[0]
        for r in rows_[1:]:
            old_stage[(r[h.index("Module")], r[h.index("Reference entry")])] = r[h.index("Where it was lost")]
    except Exception as ex:  # noqa: BLE001
        problems.append(f"could not read the earlier stage labels: {ex}")

    # ------------------------------------------------ report
    L = ["# Where the two-phase asset prompt fails", "",
         "Prompt `two_phase_v1` (the PIO prompt: Phase 1 finds conceptual assets, Phase 2 finds the RTL elements behind them), "
         "model `gpt-5.4`, high reasoning, run r0, on the 15 tuning modules. Built 2026-10-11 by "
         "[failure_patterns/make_report_md.py](failure_patterns/make_report_md.py). Numbers in number columns, in 'In short', "
         "'Main patterns' and tables 1.1, 2.1, 2.2 and 3.5 are computed by that script. Text columns in section 3 (and the "
         "verdicts and cluster memberships behind the counts) are AI agents' judgements; numbers inside those texts were not "
         "re-checked by the script. Every element is listed in [FAILURE_PATTERNS_APPENDIX.md](FAILURE_PATTERNS_APPENDIX.md).", ""]
    if problems:
        L += ["> **Checks that failed while building this report:** " + "; ".join(problems), ""]
    L += ["## In short", "",
          f"- **Phase 2, structural assets (exact names).** The model named {T['listed']} RTL elements as primary assets. {T['tp']} "
          f"are in the reference (correct finds) and {T['fp']} are not (F2, false positives). Of the {n_ref} reference elements, "
          f"it missed {T['fn']} (F1); {n_abs} of those names do not exist in this RTL, so {n_ref - n_abs} could be found. "
          f"Precision (share of the model's list that is correct) {P:.3f} = {T['tp']}/{T['listed']}. Recall (share of the "
          f"reference found) {R_find:.3f} = {T['tp']}/{n_ref - n_abs} findable ({R_all:.3f} = {T['tp']}/{n_ref} of all).",
          f"- **Phase 1, conceptual assets (judged by AI readers).** The reference implies {n_g} conceptual assets. The model's "
          f"kept concepts cover {g_found} of them (recall {g_found / n_g:.2f}), cover {gv['partly found']} only in part, and miss "
          f"{n_g - g_found - gv['partly found']}. Of the model's {n_m} kept concepts, {m_match} match the reference "
          f"(precision {m_match / n_m:.2f}) and {n_m - m_match} have no reference counterpart. One model concept can cover several "
          f"reference concepts, so {g_found} and {m_match} differ.",
          f"- **The phases are linked.** {fp_from['only extra concepts']} of the {T['fp']} structural false positives come only "
          f"from concepts with no reference counterpart; {fp_from['a matching concept']} come from concepts that match. Every correct "
          f"find comes from a matching concept. Of the {T['fn']} structural misses, {fn_from['found']} belong to a reference concept "
          f"the model found, {fn_from['partly found']} to one it found in part, and {fn_from['missed']} to one it missed.", ""]
    L += ["## Words used", "",
          "- **RTL**: the hardware source code (VHDL). **Module**: one RTL file. **Unit**: the design unit (VHDL entity) being "
          "read. **Sub-unit**: a unit placed inside another one (an instance); its **port map** is the wiring of its pins.",
          "- **Port**: a pin of the unit. **Record**: a bundle of named values, like a struct; `x.f` is **field** f of record x. "
          "A **port field** is one field of a record-typed port.",
          "- **Conceptual asset**: information worth protecting (for example 'watchdog timeout'). **Structural asset**: an RTL "
          "element that holds, carries or controls it. **Primary**: the element that holds the value or makes the decision "
          "(prompt rule 2.6); only primaries are scored. **Secondary**: an element on the path to a primary (rule 2.7); "
          "direction a = it carries the value, direction b = it controls or gates it.",
          "- **Closed set**: a program-made list of every port and signal, with facts per element; the model may only name "
          "these. **Role words** come from it: *register* = held on a clock edge; *carries a value* = copied or used in "
          "arithmetic (called *value used* for inputs); *decides only* = used only in if/case conditions; *computed without a "
          "clock* = combinational logic; *set by an instance* = driven by a sub-unit's output; *no use found* = never read directly.",
          "- **Reference** (ground truth): the LAsset manual asset list. **Reference row**: one line of that list; it can name "
          "several elements. **F1** = something missed (false negative). **F2** = something wrongly listed (false positive).",
          "- **Ids.** RC1, RC2 ... = reference concepts (derived here). C1, C2 ... = the model's Phase 1 concepts (its own ids). "
          "R### = one element in the model's list. S, M, CM, CX = clusters (section 3). C, I, A = confidentiality, integrity, "
          "availability.",
          "- **Kept / considered, not kept**: Phase 1 keeps a concept, or lists it as considered and dropped. **Point**: a block of "
          "the RTL diagram that the Phase 2 walk reached. **FIFO**: a first-in-first-out buffer. **Strobe**: a 'request valid' "
          "bit. **FSM**: a state machine. **CSR**: a control and status register.", ""]

    # main patterns
    nfp = {c["cid"]: len(c["rows"]) for c in sfp["clusters"]}
    by_n = sorted(sfp["clusters"], key=lambda c: -nfp[c["cid"]])
    t0 = [c for c in by_n if not c["tp_agent"] and not c["tp_mech"]]
    t1 = [c for c in by_n if not c["tp_agent"] and c["tp_mech"]]
    t2 = [c for c in by_n if 1 <= len(c["tp_agent"]) <= 4]
    t3 = [c for c in by_n if len(c["tp_agent"]) >= 5]
    assert sum(nfp[c["cid"]] for c in t0 + t1 + t2 + t3) == T["fp"]
    cx = sorted(cf2["clusters"], key=lambda c: -c["fp_only_extra"])
    nm = lambda c: c["name"].rstrip(".")  # noqa: E731
    L += ["## Main patterns", "",
          f"1. **Phase 1 adds concepts the reference does not have** ({n_m - m_match} of {n_m}). Most costly in Phase 2 (false "
          f"positives that come only from these extra concepts): " +
          "; ".join(f"{nm(c)} ({len(c['members'])} concepts, {c['fp_only_extra']})" for c in cx[:3]) + ".",
          f"2. **Phase 1 misses few concepts** ({n_g - g_found - gv['partly found']} missed and {gv['partly found']} partly found, "
          f"of {n_g}). Most are small control signals that the model folded into the information they control: " +
          "; ".join(f"{nm(c)} ({len(c['members'])})" for c in sorted(cf1["clusters"], key=lambda c: -len(c["members"]))) + ".",
          f"3. **Phase 2 false positives, sorted by whether correct finds look the same** (all {T['fp']}):",
          f"   - No correct find has this shape, by the agents' reading and by the coarse role check "
          f"({sum(nfp[c['cid']] for c in t0)}): " + "; ".join(f"{nm(c)} ({nfp[c['cid']]})" for c in t0) + ".",
          f"   - None by the agents' reading, but some correct finds share the coarse role ({sum(nfp[c['cid']] for c in t1)}): " +
          "; ".join(f"{nm(c)} ({nfp[c['cid']]})" for c in t1) + ".",
          f"   - One to four correct finds of the same shape ({sum(nfp[c['cid']] for c in t2)}): " +
          "; ".join(f"{nm(c)} ({nfp[c['cid']]})" for c in t2) + ".",
          f"   - Five or more correct finds of the same shape ({sum(nfp[c['cid']] for c in t3)}): " +
          "; ".join(f"{nm(c)} ({nfp[c['cid']]} false positives; {len(c['tp_agent'])} correct finds)" for c in t3) +
          ". Their role does not separate them from correct finds.",
          f"4. **Structural misses** ({T['fn']}): " + "; ".join(f"{nm(c)} ({len(c['entries'])})" for c in
                                                         sorted(sfn["clusters"], key=lambda c: -len(c["entries"]))) + ".",
          "",
          "Reading (reasoning, not a measurement): the first group of false positives is where a negative rule in the prompt "
          "is safest; the last group cannot be fixed by role alone.", ""]
    L += ["## How this was measured", "",
          "- **Reference**: `data/ground_truth/manual_gt_neorv32.json`. It lists structural assets only, in rows, each with a "
          "'why' text. It has no conceptual assets.",
          "- **Reference conceptual assets were derived.** For each module, two AI readers who did not see the model's output "
          "grouped the reference rows into conceptual assets from the 'why' texts. They used the definition and the merge-and-split "
          "rule the prompt gives the model ([common.md](../../prompts/two_phase_v1/common.md) 2.4; "
          "[phase1.md](../../prompts/two_phase_v1/phase1.md) step 3). A third agent reconciled the two.",
          f"- **Structural matching is exact.** A reference element counts as found only when the model listed the same name. "
          f"The {n_abs} names that do not exist in this RTL are left out of the findable count. An earlier scorer let a field "
          f"count for its whole record (pmp `ctrl_i.cpu_debug` for `ctrl_i`); here it does not. So precision is {P:.3f} "
          f"(was {old_tp / T['listed']:.3f}), recall {R_all:.3f} of {n_ref} (was {old_tp / n_ref:.3f}) and {R_find:.3f} of "
          f"{n_ref - n_abs} (was {old_tp / (n_ref - n_abs):.3f}); {T['fp']} false positives and {T['fn']} misses (were {old_fp} "
          f"and {n_ref - old_tp}).",
          "- **Conceptual matching is a judgement.** Two AI judges compared each module's concepts independently. " +
          (f"They disagreed on found / missed in {n_adj} modules; an adjudicator settled those." if n_adj else
           "They agreed in every module on which reference concepts were found and which model concepts have a counterpart, "
           "so no adjudication was needed."),
          "- **Clusters** were made by AI agents, checked by a critic agent, and revised; the script checks that every failure is "
          "in exactly one cluster. *Same-shape correct finds* (agents) = correct finds with the same role, place and influence. "
          "*Same coarse role* (script) = correct finds with the same place, role and record type as at least one member. Neither "
          "is the earlier workbook's check, which counted correct finds that meet a group's definition; the numbers are not "
          "comparable.", ""]

    # ------------------------------------------------ step 1
    L += ["## Step 1. The reference side", "", "### 1.1 Counts per module", "",
          "A reference row can name several elements; each named element is one structural asset (one reference element).", ""]
    rows = []
    for m in mods:
        d = pack["modules"][m]
        rows.append([short(m), len(d["reference rows"]), len(d["reference entries"]),
                     sum(1 for e in d["reference entries"] if e["absent"]), len(gt[m]["concepts"])])
    rows.append(["**total**"] + [sum(r[i] for r in rows) for i in range(1, 5)])
    L += table(["Module", "Reference rows", "Structural assets", "of which not in this RTL", "Conceptual assets (derived)"], rows)
    sig_of = {(m, x["entry"]): x["signature"] for m in mods for x in pack["modules"][m]["TP"] + pack["modules"][m]["FN"]}

    def elem(m, e, with_role=True):
        if e["absent"]:
            return f"{e['name']} (not in this RTL)"
        g = sig_of.get((m, e["entry"]), {})
        tag = f"{WH.get(g.get('where'), g.get('where'))}, {ROLE.get(g.get('role'), g.get('role'))}" if with_role else ""
        miss = "" if e.get("found as") else "missed"
        inner = ", ".join(x for x in (tag, miss) if x)
        return f"{e['name']} ({inner})" if inner else e["name"]
    L += ["### 1.2 Conceptual assets per module (derived from the 'why' texts)", ""]
    L += table(["Module", "Conceptual assets"], [[short(m), "; ".join(f"{rc(c['id'])} {c['name']}" for c in gt[m]["concepts"])] for m in mods])
    L += ["### 1.3 Structural assets per module (place, role; 'missed' = the model did not list it)", ""]
    L += table(["Module", "Structural assets"], [[short(m), "; ".join(elem(m, e) for e in pack["modules"][m]["reference entries"])] for m in mods])
    L += ["### 1.4 Structural assets per conceptual asset", ""]
    first = {m: {} for m in mods}
    for m in mods:
        for e in pack["modules"][m]["reference entries"]:
            first[m].setdefault(e["name"], e)
    L += table(["Module", "Conceptual asset", "Kind", "Where", "Objective", "Structural assets"],
               [[short(m), f"{rc(c['id'])} {c['name']}", c["kind"], {"both": "unit pins and internal"}.get(c["where"], c["where"]),
                 objs(c["objectives"]), ", ".join(elem(m, first[m][h], False) if h in first[m] else h for h in dict.fromkeys(c["home_elements"]))]
                for m in mods for c in gt[m]["concepts"]])

    # ------------------------------------------------ step 2
    L += ["## Step 2. The model's failures", "", "### 2.1 Phase 1: conceptual assets", ""]
    rows = []
    for m in mods:
        gs, ms = match[m]["gt_concepts"], match[m]["model_concepts"]
        rows.append([short(m), len(gs), sum(x["verdict"] in FOUND for x in gs), sum(x["verdict"] == "partly found" for x in gs),
                     sum(x["verdict"].startswith("missed") for x in gs), len(ms), sum(x["verdict"] not in MATCHED for x in ms)])
    rows.append(["**total**"] + [sum(r[i] for r in rows) for i in range(1, 7)])
    L += table(["Module", "Reference concepts", "Found", "Partly found", "Missed", "Model concepts", "Extra (no counterpart)"], rows)
    L += table(["Verdict on a reference concept", "Meaning", "Count"], [[v, mng, gv[v]] for v, mng in VERDICT_MEANING])
    L += ["**F1: reference concepts missed or partly found**", ""]
    L += table(["Module", "Reference concept", "Kind", "Verdict", "What is not covered, and where it went (judge)"],
               [[short(m), f"{rc(x['id'])} {gcon[(m, x['id'])]['name']}", gcon[(m, x["id"])]["kind"], x["verdict"],
                 sent(tx((x["missing_part"].rstrip(".") + ". " if x["missing_part"] else "") + x["evidence"]), 260)]
                for m in mods for x in match[m]["gt_concepts"] if x["verdict"] not in FOUND])
    L += ["**F2: model concepts with no reference counterpart** (last column: elements it listed as primary; an element listed "
          "under several concepts counts for each)", ""]
    L += table(["Module", "Model concept", "Kind", "What it is (judge)", "Primaries: correct / false"],
               [[short(m), f"{x['id']} {x['name']}", x["kind"], sent(tx(x["what_it_is"]), 180), f"{yld[(m, x['id'])][0]} / {yld[(m, x['id'])][1]}"]
                for m in mods for x in match[m]["model_concepts"] if x["verdict"] not in MATCHED])
    L += ["### 2.2 Phase 2: structural assets (exact names)", ""]
    rows = []
    for m in mods:
        d = pack["modules"][m]
        rows.append([short(m), len(d["reference entries"]), d["listed"], len(d["TP"]), len(d["FP"]), len(d["FN"]),
                     ", ".join(x["name"] + (" (not in RTL)" if x["absent"] else "") for x in d["FN"]) or "-"])
    rows.append(["**total**"] + [sum(r[i] for r in rows) for i in range(1, 6)] + [""])
    L += table(["Module", "Reference elements", "Model listed", "Correct", "F2 false positives", "F1 missed", "Missed elements"], rows)
    L += ["**F1: structural assets missed**", ""]
    L += table(["Module", "Element", "Place", "Role", "Feeds or decides", "Where the model named it", "Its reference concept in Phase 1"],
               [[short(m), x["name"], WH.get(x["signature"]["where"]), role_of(x), sent(x["signature"]["influence"], 100),
                 mentioned(x["seen in model output"]), f"{fn_concept[e][0]}: {fn_concept[e][1]}"] for e, (m, x) in fn_rows.items()])
    L += ["**F2: structural false positives by place and role** (every element is listed in appendix A1)", ""]
    sg = Counter((x["signature"]["where"], x["signature"]["role"]) for m, x in fp_rows.values())
    tg = Counter((x["signature"]["where"], x["signature"]["role"]) for m, x in tp_rows.values())
    L += table(["Place", "Role", "False positives", "Correct finds, same place and role (counted)"],
               [[WH.get(w, w), ROLE.get(r, r), n, tg.get((w, r), 0)] for (w, r), n in sg.most_common()])
    L += [f"Places and roles with no false positive are not shown, so the last column sums to "
          f"{sum(tg.get(k, 0) for k in sg)} of the {T['tp']} correct finds.", ""]

    # ------------------------------------------------ step 3
    L += ["## Step 3. Failure clusters", "",
          "Clusters group failures by their role in the RTL, where they appear and what they influence. Shortened agent texts are "
          "cut at a sentence end; the full texts are in appendix A6.", "", "### 3.1 Conceptual assets missed (F1)", ""]
    L += table(["Cluster", "Members", "Kind", "Where", "Influences", "Why the model missed them (agent)", "Similar concepts it found (agent)"],
               [[f"{c['cid']} {c['name']}", f"{len(c['members'])}: {', '.join(tx(x) for x in c['members'])}", sent(c["kind"], 80),
                 sent(tx(c["where"]), 160), sent(tx(c["influences"]), 160), sent(tx(c["pattern"]), 300), len(c["similar_successes"])]
                for c in cf1["clusters"]])
    L += ["### 3.2 Extra conceptual assets (F2)", ""]
    L += table(["Cluster", "Members", "Kind", "Where", "Influences", "Why the model added them (agent)",
                "False positives: touching / only from extra concepts", "Similar concepts that match (agent)"],
               [[f"{c['cid']} {c['name']}", f"{len(c['members'])}: {', '.join(c['members'])}", sent(c["kind"], 80), sent(tx(c["where"]), 160),
                 sent(tx(c["influences"]), 160), sent(tx(c["pattern"]), 300), f"{c['fp_distinct']} / {c['fp_only_extra']}",
                 len(c["similar_successes"])] for c in cf2["clusters"]])
    L += [f"'Touching' counts each false positive once if any of its concepts is in the cluster; 'only from extra concepts' "
          f"leaves out those also listed under a matching concept. Summed over clusters, the second count is "
          f"{sum(c['fp_only_extra'] for c in cf2['clusters'])}; 'In short' gives {fp_from['only extra concepts']}.", ""]
    L += ["### 3.3 Structural assets missed (F1)", ""]
    L += table(["Cluster", "Entries", "Place (counted)", "Role (counted)", "Influences (agent)", "Where lost (agent)", "Why missed (agent)",
                "Similar correct finds (agent)"],
               [[f"{c['cid']} {c['name']}",
                 f"{len(c['entries'])}: " + ", ".join(f"{fn_rows[e][1]['name']} ({short(fn_rows[e][0])})" for e in c["entries"] if e in fn_rows),
                 breakdown([fn_rows[e][1] for e in c["entries"] if e in fn_rows], lambda x: WH.get(x["signature"]["where"])),
                 breakdown([fn_rows[e][1] for e in c["entries"] if e in fn_rows], role_of),
                 sent(tx(c["influences"]), 160), sent(tx(c["where_lost"]), 200), sent(tx(c["why_missed"]), 420), len(c["tp_agent"])]
                for c in sfn["clusters"]])
    L += ["The earlier workbook labelled where each miss was lost by searching for the exact name; here agents read the replies, "
          "so a few labels differ. Appendix A2 shows both for every miss.", ""]
    L += ["### 3.4 Structural false positives (F2)", ""]
    rows = []
    for c in by_n:
        xs = [fp_rows[r][1] for r in c["rows"]]
        old = Counter(("none (R291, moved by exact matching)" if x["old group"].startswith("none") else x["old group"]) for x in xs)
        rows.append([f"{c['cid']} {c['name']}", len(xs), breakdown([fp_rows[r] for r in c["rows"]], lambda y: short(y[0])),
                     breakdown(xs, lambda x: WH.get(x["signature"]["where"])), breakdown(xs, role_of),
                     sent(tx(c["influences"], True), 160), sent(tx(c["why_the_model_listed_them"], True), 260),
                     len(c["tp_agent"]), len(c["tp_mech"]), ", ".join(f"{k} {v}" for k, v in old.most_common())])
    L += table(["Cluster", "False positives", "Modules", "Place (counted)", "Role (counted)", "Influences (agent)",
                "Why the model listed them (agent's summary; quoted words may be paraphrased)", "Same-shape correct finds (agent)",
                "Correct finds with the same coarse role (counted)", "Earlier groups (workbook)"], rows)
    L += ["'Earlier groups' are the groups G01 to G15 of PROMPT_FAILURE_DIAGNOSIS.xlsx, which sorted the same false positives "
          "by why the model listed them. One judgement changed: the earlier analysis took ctrl.buf_dir (R202) as the likely "
          "counterpart of the missing reference name cache_o.cmd_dir; the clustering agent took the cache-memory command wires "
          "instead (S4) and put R202 in S12. Both are judgements.", ""]
    L += ["### 3.5 How Phase 1 errors flow into Phase 2", ""]
    L += table(["Structural result", "Only from extra concepts", "From a matching concept"],
               [["False positives (F2)", fp_from["only extra concepts"], fp_from["a matching concept"]],
                ["Correct finds", tp_from["only extra concepts"], tp_from["a matching concept"]]])
    L += table(["Structural misses (F1): their reference concept in Phase 1", "Count"],
               [["found", fn_from["found"]], ["partly found", fn_from["partly found"]], ["missed", fn_from["missed"]]])
    L += ["Reading (reasoning, not a measurement): false positives from extra concepts point to Phase 1 (the concept should not "
          "exist). False positives from matching concepts point to Phase 2 (the right concept, the wrong elements). Misses whose "
          "concept was found were mostly lost in Phase 2, but not all: rs3_i was dropped in Phase 1, and ctrl_i was listed as "
          "fields, which exact matching does not credit.", ""]
    (ANALYSIS / "FAILURE_PATTERNS.md").write_text("\n".join(L), encoding="utf-8")

    # ------------------------------------------------ appendix
    A = ["# Failure patterns: appendix (every element)", "", "Companion to [FAILURE_PATTERNS.md](FAILURE_PATTERNS.md).", "",
         "## A1. Structural false positives by cluster", ""]
    for c in sorted(sfp["clusters"], key=lambda c: int(c["cid"][1:])):
        mem = sorted(c["rows"], key=lambda r: (fp_rows[r][0], r))
        A += [f"### {c['cid']} {c['name']} ({len(mem)})", "", f"Definition (agent): {cell(tx(c['definition'], True))}", "",
              f"Same-shape correct finds (agent): {', '.join(c['tp_agent']) or 'none'}. Same coarse role (counted): "
              f"{', '.join(c['tp_mech']) or 'none'}.", ""]
        A += table(["Id", "Module", "Entity", "Element", "Place", "Role", "Listed for", "Model's reason (verbatim, first sentence)", "Earlier group"],
                   [[r, short(fp_rows[r][0]), fp_rows[r][1]["entity"], fp_rows[r][1]["element"], WH.get(fp_rows[r][1]["signature"]["where"]),
                     role_of(fp_rows[r][1]), "; ".join(f"{k} {mcon.get((fp_rows[r][0], k), {}).get('concept', '')}" for k in fp_rows[r][1]["concepts"]),
                     re.split(r"(?<=[.!?])\s", fp_rows[r][1]["model reason"] or "", maxsplit=1)[0], fp_rows[r][1]["old group"]] for r in mem])
    A += ["## A2. Structural misses", ""]
    A += table(["Entry", "Module", "Element", "Cluster", "Reference why", "Where the model named it", "Earlier stage (workbook)"],
               [[e, short(m), x["name"], fn_cluster.get(e, ""),
                 " / ".join(r["why"] for r in pack["modules"][m]["reference rows"] if r["row"] in x["rows"]),
                 "; ".join(x["seen in model output"]) or "nowhere",
                 old_stage.get((short(m), x["name"]), "not missed there (credited through a field of the record)")]
                for e, (m, x) in fn_rows.items()])
    A += ["## A3. Conceptual matching, every concept", ""]
    A += table(["Module", "Reference concept", "Verdict", "Model concept(s)", "Evidence (judge)"],
               [[short(m), f"{rc(x['id'])} {gcon[(m, x['id'])]['name']}", x["verdict"], ", ".join(x["model_ids"]), tx(x["evidence"])]
                for m in mods for x in match[m]["gt_concepts"]])
    A += table(["Module", "Model concept", "Verdict", "Reference concept(s)", "What it is (judge)"],
               [[short(m), f"{x['id']} {x['name']}", x["verdict"], ", ".join(rc(g) for g in x["gt_ids"]), tx(x["what_it_is"])]
                for m in mods for x in match[m]["model_concepts"]])
    A += ["## A4. Reference conceptual assets, full text", ""]
    A += table(["Module", "Id", "Conceptual asset", "Information", "Influences", "Evidence (reference 'why')", "Elements", "Readers"],
               [[short(m), rc(c["id"]), c["name"], c["information"], tx(c["influences"]), c["evidence"], ", ".join(c["elements"]), c["agreement"]]
                for m in mods for c in gt[m]["concepts"]])
    A += ["## A5. Reconciliation notes (where the two readers grouped differently)", ""]
    A += [f"- **{short(m)}**: {cell(tx(gt[m]['disagreements']))}" for m in mods if gt[m]["disagreements"].strip()] + [""]
    A += ["## A6. Every cluster in full (agents' texts)", ""]
    for title, cl, keys, sf in (("Conceptual assets missed", cf1, ("definition", "kind", "where", "influences", "pattern", "similar_successes"), False),
                                ("Extra conceptual assets", cf2, ("definition", "kind", "where", "influences", "pattern", "similar_successes"), False),
                                ("Structural assets missed", sfn, ("definition", "role", "where", "influences", "where_lost", "why_missed", "tp_same_shape", "example"), False),
                                ("Structural false positives", sfp, ("definition", "role", "where", "influences", "why_the_model_listed_them", "tp_same_shape", "example"), True)):
        A += [f"### {title}", ""]
        for c in sorted(cl["clusters"], key=lambda c: int(re.sub(r"\D", "", c["cid"]))):
            mem = c.get("members") or c.get("entries") or c.get("rows")
            A += [f"**{c['cid']} {c['name']}** ({len(mem)}: {', '.join(tx(x) for x in mem)})", ""]
            A += [f"- {k.replace('_', ' ')}: {cell(tx(', '.join(c[k]) if isinstance(c[k], list) else c[k], sf)) or '-'}" for k in keys] + [""]
        A += [f"Notes (the agent's account of the critic's points): {cell(tx(cl.get('notes', ''), sf))}", ""]
    (ANALYSIS / "FAILURE_PATTERNS_APPENDIX.md").write_text("\n".join(A), encoding="utf-8")
    print(f"written; checks failed: {len(problems)}")
    for p in problems:
        print("  ", p)


if __name__ == "__main__":
    main()
