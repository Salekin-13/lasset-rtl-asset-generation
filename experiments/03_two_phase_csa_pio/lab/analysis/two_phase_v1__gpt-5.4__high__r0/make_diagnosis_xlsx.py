"""Build PROMPT_FAILURE_DIAGNOSIS.xlsx for the two-phase PIO run: one record per failure (FP and FN) with the fields
MODEL, PROMPT, INPUT, CONTEXT, TOOLS, RUNTIME, EXPECTED, OBSERVED, plus the diagnosis from the error analysis.

Exact texts (system prompts, user messages, raw replies) do not fit in one Excel cell (32,767 characters), so they
are stored in chunks on the sheet 'Exact text'. A self-test reassembles every one of them and compares its sha12 with
the sha recorded by the run (system sha, user sha) before the workbook is written.

  python make_diagnosis_xlsx.py
"""
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
import chain as CH  # noqa: E402
import check_lab_prompt as C  # noqa: E402
import cost_estimate as CE  # noqa: E402
import labkit as K  # noqa: E402

VERSION, MODEL, EFFORT, REP = "two_phase_v1", "gpt-5.4", "high", 0
OUT = CH.run_dir(VERSION, MODEL, REP, EFFORT)
CHUNK = 30000
TOOLS = "None. No tool definitions were sent and no tool was called. Output format: text.format = json_object (JSON mode, no JSON schema)."
CONTEXT_NONE = "No retrieved documents, no conversation history (one single-turn call), no memory, no few-shot examples."


def sha12(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def clip(t, n=30000):
    t = "" if t is None else str(t)
    return t if len(t) <= n else t[:n] + f" [... clipped, {len(t):,} characters in all]"


def runtime_text(u, status="completed"):
    return (f"reasoning.effort = high; max_output_tokens = 128000; text.format = json_object; background = true (polled); "
            f"temperature/top_p not sent (not used by this reasoning model); truncation not sent (API default: disabled, "
            f"so nothing was cut); store = default. Status {status}. Tokens: input {u.get('in'):,} "
            f"(cached {u.get('cached') or 0:,}), output {u.get('out'):,} (reasoning field {u.get('reasoning'):,}: equal to "
            f"output in every call, an API reporting oddity; billing uses output). Response id {u.get('response id')}.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import eval_assets as ea
    t = json.loads((HERE / "table.json").read_text(encoding="utf-8"))
    wf = json.loads((HERE / "fp_analysis_workflow.json").read_text(encoding="utf-8"))
    code_of = {c["id"]: c for c in wf["codes"]}
    bucket_of, bucket_info = {}, {}
    for b in wf["clustering"]["buckets"]:
        bucket_info[b["bucket_id"]] = b
        for i in b["member_ids"]:
            bucket_of[i] = b["bucket_id"]
    rule_of = defaultdict(list)
    for r in wf["rules"]["rules"]:
        for b in r["bucket_ids"]:
            rule_of[b].append(f"{r['rule_id']} ({r['where_it_belongs']})")
    mods = K.gt_modules()["tuning"]
    with CH.at_root():
        refs = ea.load_refs()["gt"]
    sys1, sys2 = C.system(VERSION, 1), C.system(VERSION, 2)

    # ---------------------------------------------------------------- calls, exact texts, self-test
    calls, exact, problems = [], [], []
    recs = {}
    for m in mods:
        for ph in (1, 2):
            r = json.loads((OUT / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))
            recs[(m, ph)] = r
    p1_concepts = {m: recs[(m, 1)]["reply"]["conceptual assets"] for m in mods}
    for ph, s in ((1, sys1), (2, sys2)):
        for k in range(0, len(s), CHUNK):
            exact.append([f"system prompt phase {ph}", "system", k // CHUNK + 1, s[k:k + CHUNK], len(s), sha12(s)])
    for m in mods:
        for ph in (1, 2):
            r = recs[(m, ph)]
            sysx = sys1 if ph == 1 else sys2
            user = CH.user_message(VERSION, ph, m, p1_concepts[m] if ph == 2 else None)
            if sha12(sysx) != r["system sha"]:
                problems.append(f"{m} phase {ph}: system prompt sha {sha12(sysx)} != recorded {r['system sha']}")
            if sha12(user) != r["user sha"]:
                problems.append(f"{m} phase {ph}: user message sha {sha12(user)} != recorded {r['user sha']}")
            cid = f"{m}/phase{ph}"
            for part, txt in (("user message", user), ("raw reply", r["raw"])):
                for k in range(0, len(txt), CHUNK):
                    exact.append([cid, part, k // CHUNK + 1, txt[k:k + CHUNK], len(txt), sha12(txt)])
            u = r["usage"]
            reply = r.get("reply") or {}
            if ph == 1:
                obs = (f"{len(reply.get('conceptual assets', []))} conceptual assets kept, "
                       f"{len(reply.get('considered, not kept', []))} considered and not kept; {len(r['problems'])} check problems")
                exp = "A JSON object in the Phase 1 schema: the conceptual assets of each unit, kept by the rubric and the asset test."
                ctx = CONTEXT_NONE
            else:
                pr = [a for a in reply.get("structural assets", []) if a.get("label") == "primary"]
                obs = (f"{len(reply.get('points', []))} points; {len(reply.get('structural assets', []))} structural-asset rows "
                       f"({len(pr)} primary); {len(reply.get('notes', []))} notes; {len(r['problems'])} check problems")
                exp = (f"A JSON object in the Phase 2 schema; its primary rows should match the reference list "
                       f"({len(refs.get(m, []))} entries for this module).")
                ctx = (CONTEXT_NONE + f" Phase 1's 'conceptual assets' list ({len(p1_concepts[m])} concepts, sha "
                       f"{sha12(json.dumps(p1_concepts[m], indent=1, ensure_ascii=False))}) is part of the user message as CONCEPTS.")
            calls.append([cid, m, ph, u.get("model"), f"{VERSION}, phase {ph}; system prompt sha {r['system sha']} "
                          f"({len(sysx):,} chars) = common.md + phase{ph}.md; user template phase{ph}_user.md",
                          f"user message sha {r['user sha']} ({len(user):,} chars): rtl.txt + closed_set.json (compact) + diagram.txt"
                          + (" + CONCEPTS" if ph == 2 else "") + f" of inputs v1/{m}", ctx, TOOLS, runtime_text(u), exp, obs,
                          u.get("in"), u.get("cached") or 0, u.get("out"), round(CE.usd(u), 4)])
    if problems:
        sys.exit("exactness self-test failed:\n" + "\n".join(problems))
    # reassembly check of the stored chunks
    by = defaultdict(list)
    for row in exact:
        by[(row[0], row[1])].append(row)
    for key, rows in by.items():
        whole = "".join(r[3] for r in sorted(rows, key=lambda r: r[2]))
        assert sha12(whole) == rows[0][5] and len(whole) == rows[0][4], key
        if key[1] == "raw reply":
            m_, ph_ = key[0].split("/phase")
            assert whole == recs[(m_, int(ph_))]["raw"], key
    print(f"exactness self-test: {len(by)} texts reassemble to their recorded sha (system x2, user x30, reply x30)")

    # ---------------------------------------------------------------- per-element helpers
    def rtl_text(m):
        return {int(mm.group(1)): l for l in CH.inputs(m)["rtl.txt"].splitlines() if (mm := re.match(r"\s*(\d+) \|", l))}
    rtl_cache, cs_cache, dg_cache = {}, {}, {}

    def unit_sections(m):
        secs, cur = defaultdict(list), None
        for l in CH.inputs(m)["diagram.txt"].splitlines():
            if l.startswith("UNIT "):
                cur = l[5:].strip()
            if cur:
                secs[cur].append(l)
        return secs

    def tokens(line):
        line = re.sub(r"([\w.()]+?)\.\{([^}]*)\}", lambda mm: " ".join(f"{mm.group(1)}.{f.strip()}" for f in mm.group(2).split(",")), line)
        return set(re.findall(r"[\w.]+", line))

    def input_excerpt(m, ent, el, model_lines, same_role=False):
        if m not in rtl_cache:
            rtl_cache[m], cs_cache[m], dg_cache[m] = rtl_text(m), CH.closed_names(m), unit_sections(m)
        x = cs_cache[m].get((ent, el)) or next((v for (e, n), v in cs_cache[m].items() if n == el), None)
        entry = json.dumps({k: v for k, v in (x or {}).items() if k != "fields"}, separators=(",", ":"))
        own = sorted((x or {}).get("occurrence lines", []))
        rl = "\n".join(rtl_cache[m][l].strip() for l in own[:15] if l in rtl_cache[m])
        txt = f"CLOSED SET ENTRY ({ent}): {clip(entry, 6000)}\n\nRTL LINES OF THE ELEMENT (its occurrence lines):\n{rl}"
        cited = [l for l in model_lines if l not in own]
        if cited and not same_role:
            txt += "\n\nOTHER RTL LINES THE MODEL CITED:\n" + "\n".join(rtl_cache[m][l].strip() for l in cited[:12] if l in rtl_cache[m])
        units = [u for u, es in K.unit_entities(m).items() if ent in es]
        base = el.split(".")[0]
        dg = []
        for u in units:
            ports = {p for l in dg_cache[m][u] if l.strip().startswith(("INPUTS:", "OUTPUTS:")) for p in re.findall(r"[\w.]+", l.split(":", 1)[1])}
            for l in dg_cache[m][u]:
                tk = tokens(l)
                if el in tk or (base != el and base in ports and base in tk):
                    dg.append(f"[{u}] " + l.strip())
        return clip(txt + "\n\nDIAGRAM LINES (its unit only):\n" + "\n".join(dg)[:3000], 30000)

    def concept_text(m, cids):
        cs = {c["id"]: c for c in p1_concepts[m]}
        out = []
        for c in cids:
            x = cs.get(c, {})
            out.append(f"{c} '{x.get('concept')}': {x.get('information')} Objectives {x.get('objectives')}; enters "
                       f"{x.get('enters through')}; leaves {x.get('leaves through')}; held lines {x.get('held lines')}.")
        return clip(CONTEXT_NONE + " Phase 1 concept(s) given to Phase 2: " + " | ".join(out))

    # ---------------------------------------------------------------- failure rows
    head = ["case id", "case", "module", "entity", "element", "bucket", "failure mode (open coding)",
            "MODEL", "PROMPT", "INPUT (relevant excerpt; full text: sheet Exact text)", "CONTEXT", "TOOLS", "RUNTIME (call)",
            "EXPECTED (reference list)", "EXPECTED (the prompt's own rules)", "OBSERVED", "follows the prompt?",
            "diagnosis", "drafted rule", "calls (sheet Calls)"]
    fail_rows, tp_rows = [], []
    model_name = calls[0][3]
    credited = {(r["module"], r["matched reference entry"]): r["element"] for r in t["rows"] if r["verdict"] == "TP"}

    def ref_view(m, el):
        base = el.split(".")[0]
        whole = [rn for rn, _ in refs.get(m, []) if "." not in rn and rn == base and rn != el]
        if whole:
            return (f"The reference lists the whole record '{whole[0]}' once; under the strict scorer its one credit went to "
                    f"'{credited.get((m, whole[0]), '?')}', so this further field counts as FP (a matching convention, not a "
                    f"different asset).")
        return "Not listed: the reference for this module has no such entry."
    for r in t["rows"]:
        m, ent, el = r["module"], r["entity"], r["element"]
        rec2 = recs[(m, 2)]
        code = code_of.get(r["id"], {})
        b = bucket_of.get(r["id"], "")
        src = [a for a in rec2["reply"]["structural assets"] if a.get("label") == "primary" and a.get("entity") == ent
               and (a.get("element") == el or el in (a.get("same role") or []))]
        pts = list(dict.fromkeys(p for a in src for p in (a.get("points") or []) if isinstance(p, str)))
        pts_txt = ", ".join(pts[:40]) + (f" ... and {len(pts) - 40} more" if len(pts) > 40 else "")
        fp_obs = (f"Listed as PRIMARY for {', '.join(c['id'] for c in r['concepts']) or '?'}"
                  + (f" (from a 'same role' expansion of {', '.join(sorted({a.get('element') for a in src if a.get('element') != el}))})"
                     if r["from 'same role' expansion"] else "")
                  + f". Points ({len(pts)}): {pts_txt}. Cited lines: {r['phase 2 lines']}. Model's reason(s): "
                  + " || ".join(x or "" for x in r["phase 2 reasons"]))
        fprompt = code.get("follows_prompt", "")
        exp_prompt = {"yes": f"Primary: the prompt's own rules make it primary ({code.get('prompt_rule', '')}). Failure of the prompt definition or of the reference.",
                      "no": f"Not primary: the model broke a rule ({code.get('prompt_rule', '')}). Failure of model compliance.",
                      "partly": f"Ambiguous: the rules can be read both ways ({code.get('prompt_rule', '')}).",
                      }.get(fprompt, "")
        row = [r["id"], r["verdict"], m, ent, el, b, code.get("failure_mode", ""), model_name,
               f"{VERSION} phase 2 (system sha {rec2['system sha']}); rule involved: {code.get('prompt_rule', '')}",
               input_excerpt(m, ent, el, r["phase 2 lines"], r["from 'same role' expansion"]), concept_text(m, [c["id"] for c in r["concepts"]]), TOOLS,
               f"see Calls row {m}/phase2: " + runtime_text(rec2["usage"])[:220] + " ...",
               (ref_view(m, el) if r["verdict"] == "FP" else f"Listed (reference entry '{r['matched reference entry']}')."),
               exp_prompt, clip(fp_obs), fprompt,
               clip((code.get("why_flagged", "") + " " + code.get("detail", "")).strip()),
               "; ".join(rule_of.get(b, [])), f"{m}/phase1; {m}/phase2"]
        (fail_rows if r["verdict"] == "FP" else tp_rows).append(row)
    # false negatives: where each was lost (measured from the replies)
    def rel(a, b):
        return a == b or a.startswith(b + ".") or b.startswith(a + ".")
    for k, f in enumerate(t["false negatives"]):
        m, rn = f["module"], f["reference entry"]
        p1, p2 = recs[(m, 1)]["reply"], recs[(m, 2)]["reply"]
        sa = [a for a in p2["structural assets"] if rel(a.get("element", ""), rn) or any(rel(x, rn) for x in (a.get("same role") or []))]
        pat = re.compile(r"(?<![\w.])" + re.escape(rn) + r"(?![\w])")
        dropped = [x.get("concept") for x in p1.get("considered, not kept", []) if pat.search(json.dumps(x))]
        in_pts = [p["concept id"] + ":" + p["point"] for p in p2["points"] if pat.search(json.dumps(p))]
        in_p1 = [c["id"] for c in p1["conceptual assets"] if pat.search(json.dumps(c))]
        listed = {(x["entity"], x["element"]) for x in t["rows"] if x["module"] == m}
        x_in = CH.inputs(m)
        absent = not any(re.search(r"(?<![\w.])" + re.escape(rn) + r"(?![\w])", x_in[k]) for k in x_in)
        parent = sorted({f"{e}:{n}" for (e, n), v in CH.closed_names(m).items() for grp in (v.get("counterparts") or {}).values()
                         for q in grp if q.get("port") == rn and (e, n) in listed})
        stage = ("reference name absent from the inputs (not a prompt failure)" if absent else
                 f"listed under the parent-side name of the port map ({', '.join(parent)})" if parent else
                 "reached, labelled secondary" if sa and all(a["label"] != "primary" for a in sa) else
                 "listed under another name" if sa else
                 "named in a point's reasoning, not listed" if in_pts else
                 "only in Phase 1 concept text" if in_p1 else
                 "dropped in Phase 1 (considered, not kept)" if dropped else "never named")
        obs = (f"{stage}. Phase 2 rows: " + " || ".join(f"{a['label']} for {a['concept id']}: {a.get('reason', '')}" for a in sa[:4])
               + (f" Points whose reasoning names it: {in_pts[:6]}." if in_pts else "")
               + (f" Phase 1 'considered, not kept': {dropped}." if dropped else ""))
        ent = next((e for (e, n) in CH.closed_names(m) if n == rn), "")
        lines = sorted({l for a in sa for l in (a.get("lines") or []) if isinstance(l, int)})[:15]
        if not lines:
            lines = sorted((CH.closed_names(m).get((ent, rn)) or {}).get("occurrence lines", []))[:15]
        cids = sorted({a["concept id"] for a in sa} | set(in_p1))
        fail_rows.append([f"FN{k:02d}", "FN", m, ent, rn, "", "", model_name,
                          f"{VERSION} phase 1 and phase 2 (system shas {recs[(m, 1)]['system sha']}, {recs[(m, 2)]['system sha']})",
                          input_excerpt(m, ent, rn, lines), concept_text(m, cids) if cids else CONTEXT_NONE, TOOLS,
                          f"see Calls rows {m}/phase1 and {m}/phase2",
                          f"Listed as primary (reference entry '{rn}', objective {f['reference objective']}).",
                          "Not read case by case for misses: the stage where it was lost is in 'diagnosis'.", clip(obs), "", stage, "", f"{m}/phase1; {m}/phase2"])

    # ---------------------------------------------------------------- workbook
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    readme = [
        ["Prompt-failure diagnosis: two-phase PIO prompt (two_phase_v1), gpt-5.4, 15 test modules, built 2026-10-11"],
        [""],
        ["Field", "Meaning in this workbook"],
        ["MODEL", "The exact model snapshot the API returned for the call (usage.model): " + model_name + " for all 30 calls."],
        ["PROMPT", "The exact system prompt (common.md + phase<k>.md) and user template; full text on sheet 'Exact text', identified by sha12. Failure rows name the prompt rule involved."],
        ["INPUT", "The exact user message of each call (rtl.txt + compact closed_set.json + diagram.txt, plus CONCEPTS in Phase 2) on sheet 'Exact text'. Failure rows show the relevant excerpt: the element's closed-set entry, the RTL lines involved and the diagram lines naming it."],
        ["CONTEXT", CONTEXT_NONE + " Phase 2 also receives Phase 1's 'conceptual assets' list inside its user message; failure rows show the concept(s) involved."],
        ["TOOLS", TOOLS],
        ["RUNTIME", "Per call on sheet 'Calls': reasoning effort, output limit, output format, background mode, sampling and truncation settings, status, token usage, response id, cost."],
        ["EXPECTED", "What the reference list says (listed or not; for a field of a whole-record entry, how the one credit was used). For the false positives also what the prompt's own rules say (from reading each case: does the prompt make it primary, or did the model break a rule). For the misses, 'diagnosis' gives the stage where the entry was lost instead."],
        ["OBSERVED", "What the model did: label, concept, points, cited lines and its own reason; for a miss, the stage where the entry was lost."],
        [""],
        ["Sheet", "Contents"],
        ["Failures", f"{len(fail_rows)} rows: {sum(r[1] == 'FP' for r in fail_rows)} false positives (listed, not in the reference) and {sum(r[1] == 'FN' for r in fail_rows)} false negatives (in the reference, not listed)."],
        ["TP contrast", f"{len(tp_rows)} true positives with the same fields, to compare with failures of the same shape."],
        ["Calls", "30 rows, one per model call (15 modules x 2 phases), with all eight fields at call level."],
        ["Buckets", "The 15 failure buckets of the error analysis and the drafted rules for them."],
        ["Exact text", "System prompts, user messages and raw replies, in chunks of up to 30,000 characters; concatenate the chunks of one text in order. System prompts and user messages: their sha12 equals the sha the run recorded (checked when this file was built; the user messages were rebuilt from the input files and match). Raw replies: the run recorded no sha; each reassembled reply was compared character for character with the run's stored reply."],
        [""],
        ["Sources", f"Run folder {OUT}; analysis folder {HERE}; scorer src/eval_assets.py (strict); error analysis ERROR_ANALYSIS.md."],
    ]
    for row in readme:
        ws.append(row)
    ws["A1"].font = Font(bold=True, size=13)
    for rr in (3, 13):
        for c in ws[rr]:
            c.font = Font(bold=True)
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 140
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    def sheet(title, header, rows, widths):
        s = wb.create_sheet(title)
        s.append(header)
        for row in rows:
            s.append([clip(v, 32000) if isinstance(v, str) else v for v in row])
        fill = PatternFill("solid", fgColor="DDE6F0")
        for c in s[1]:
            c.font = Font(bold=True)
            c.fill = fill
            c.alignment = Alignment(wrap_text=True, vertical="top")
        for i, w in enumerate(widths, 1):
            s.column_dimensions[get_column_letter(i)].width = w
        for row in s.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        s.freeze_panes = "F2" if title in ("Failures", "TP contrast") else "B2"
        s.auto_filter.ref = s.dimensions
        return s
    widths = [8, 6, 20, 22, 24, 7, 26, 18, 40, 70, 50, 24, 30, 34, 44, 70, 9, 50, 22, 22]
    sheet("Failures", head, fail_rows, widths)
    sheet("TP contrast", head, tp_rows, widths)
    sheet("Calls", ["call", "module", "phase", "MODEL", "PROMPT", "INPUT", "CONTEXT", "TOOLS", "RUNTIME", "EXPECTED",
                    "OBSERVED", "input tokens", "cached input tokens", "output tokens", "USD"], calls,
          [26, 20, 6, 18, 40, 46, 50, 30, 70, 40, 50, 11, 11, 11, 8])
    brows = []
    for b in wf["clustering"]["buckets"]:
        brows.append([b["bucket_id"], b["name"], len(b["member_ids"]), b["cause"], b["definition"], b["mechanical_test"],
                      b["why_the_model_flags_these"], "; ".join(rule_of.get(b["bucket_id"], []))])
    sheet("Buckets", ["bucket", "name", "FPs", "cause", "definition", "mechanical test", "why the model flags these", "drafted rule"],
          brows, [8, 34, 6, 18, 60, 50, 60, 26])
    sheet("Exact text", ["text", "part", "chunk", "content", "characters in the whole text", "sha12 of the whole text"],
          exact, [26, 14, 6, 120, 12, 14])
    dest = HERE / "PROMPT_FAILURE_DIAGNOSIS_v1_layout.xlsx"   # superseded by make_diagnosis_readable.py
    wb.save(dest)
    print(f"{dest} | failures {len(fail_rows)} (FP {sum(r[1] == 'FP' for r in fail_rows)}, FN {sum(r[1] == 'FN' for r in fail_rows)}) "
          f"| TP {len(tp_rows)} | calls {len(calls)} | exact-text chunks {len(exact)}")


if __name__ == "__main__":
    main()
