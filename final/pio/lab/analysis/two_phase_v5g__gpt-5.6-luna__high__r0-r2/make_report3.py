"""Builds THREE_RUN_FAILURES.md (concise) and THREE_RUN_FAILURES_APPENDIX.md (every element) for two_phase_v5g, gpt-5.6-luna runs r0-r2.
Copied from ../two_phase_v1__gpt-5.6-luna__high__r0-r2/make_report3.py; v1-specific corrections and texts removed.

Inputs: pack3.json (build_pack3.py: self-tested element facts, exact verdicts, malformed rows) and the agents' labels in
the workflow journal (concept verdicts per run, extra-concept groups across runs, cluster memberships). Every number in a
table column is computed here. Agent texts are marked '(agent)'; numbers inside them were not re-checked (Unverified).
Factual slips the review of 2026-10-12 found in agent texts are corrected in CORRECTIONS, each checked against its text.
The first version is kept as make_report3_v1.py.bak.

  python make_report3.py <path to the workflow's journal.jsonl>
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "two_phase_v1__gpt-5.4__high__r0" / "failure_patterns"))
from make_report_md import cell, journal, objs, sent, table  # noqa: E402
import build_pack as BP  # noqa: E402

RUNS = ("r0", "r1", "r2")
FOUND = ("found", "found inside a broader model concept", "found split")
MATCHED = ("matches", "broader", "narrower")
VERDICTS = [("found", "a model concept is the same information", "found"),
            ("found inside a broader model concept", "a model concept covers it together with other information", "found"),
            ("found split", "two or more model concepts together cover it", "found"),
            ("partly found", "model concepts cover only part of it", "miss"),
            ("missed: considered, not kept", "the run named it in its 'considered, not kept' list and dropped it", "miss"),
            ("missed: never a concept", "no concept covers it and the run did not consider it", "miss")]
WH = {"unit port": "port", "unit port field": "port field", "internal signal": "signal", "internal record field": "record field",
      "sub-unit port": "sub-unit port", "sub-unit port field": "sub-unit port field", "absent": "absent"}
ROLE = {"stored (register)": "register", "output, stored (register)": "output register", "input, read only": "input, no use found"}
CORRECTIONS = []  # (clustering, field, old, new); v1's corrections do not apply to v5g


def short(m):
    return m.replace("neorv32_", "")


def consistency(n):
    return {3: "consistent (3/3)", 2: "frequent (2/3)", 1: "intermittent (1/3)"}.get(n, "-")


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def split_obs(t):
    """Agent text -> (observed part, hypothesis part); the hypothesis starts at the first 'Reasoning'/'Hypothesis' marker."""
    t = " ".join(str(t or "").split())
    m = re.search(r"(Reasoning[^:]*:|Hypothesis[^:]*:|Reasoning, not measured)", t)
    return (t[:m.start()].strip(), t[m.start():].strip()) if m else (t, "")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    J = journal(sys.argv[1])
    pack = json.loads((HERE / "pack3.json").read_text(encoding="utf-8"))
    blocks = json.loads((HERE / "fp_blocks3.json").read_text(encoding="utf-8"))
    mods = list(pack["modules"])
    problems = []

    def tx(t):
        t = str(t or "").replace("Measured:", "Agent's check:").replace("Measured over", "Agent's check over")
        return re.sub(r"\bB(\d{3})\b", lambda mm: (lambda b: f"{b[0]['element']}" + (f" (+{len(b) - 1})" if len(b) > 1 else ""))(
            blocks.get(mm.group(0), [{"element": mm.group(0)}])), t)

    # ------------------------------------------------ concept verdicts (agents), checked here
    match, adjudicated = {}, {}
    cls = lambda v: "missed" if v.startswith("missed") else "partly" if v == "partly found" else "found"  # noqa: E731
    judge_items = judge_dis = 0
    for m in mods:
        s = short(m)
        j1, j2 = J[f"match3-1:{s}"], J[f"match3-2:{s}"]
        for k in RUNS:
            a = next((r for r in j1["runs"] if r["run"] == k), {"gt_concepts": [], "model_concepts": []})
            b = next((r for r in j2["runs"] if r["run"] == k), {"gt_concepts": [], "model_concepts": []})
            ga, gb = {x["id"]: cls(x["verdict"]) for x in a["gt_concepts"]}, {x["id"]: cls(x["verdict"]) for x in b["gt_concepts"]}
            ma = {x["id"]: x["verdict"] in MATCHED for x in a["model_concepts"]}
            mb = {x["id"]: x["verdict"] in MATCHED for x in b["model_concepts"]}
            ids, mids = set(ga) | set(gb), set(ma) | set(mb)
            judge_items += len(ids) + len(mids)
            judge_dis += sum(ga.get(i) != gb.get(i) for i in ids) + sum(ma.get(i) != mb.get(i) for i in mids)
        if f"match3-adj:{s}" in J:
            match[m] = J[f"match3-adj:{s}"]
            adjudicated[s] = True
        else:
            match[m] = j1
        runs = {r["run"]: r for r in match[m]["runs"]}
        rcs = {c["id"] for c in pack["modules"][m]["reference concepts"]}
        for k in RUNS:
            if k not in runs:
                problems.append(f"{s} {k}: no concept verdicts")
                continue
            if {x["id"] for x in runs[k]["gt_concepts"]} != rcs:
                problems.append(f"{s} {k}: reference concepts covered differ")
            if {x["id"] for x in runs[k]["model_concepts"]} != {c["id"] for c in pack["modules"][m]["runs"][k]["concepts"]}:
                problems.append(f"{s} {k}: model concepts covered differ")
        match[m]["by_run"] = runs
        extra = {f"{k}:{x['id']}" for k in RUNS for x in runs.get(k, {}).get("model_concepts", []) if x["verdict"] not in MATCHED}
        grouped = Counter(x for g in match[m]["extra_groups"] for x in g["members"])
        for x in extra:
            if grouped[x] != 1:
                problems.append(f"{s}: extra concept {x} is in {grouped[x]} extra groups")
    gver = {(m, k, x["id"]): x for m in mods for k in RUNS for x in match[m]["by_run"].get(k, {}).get("gt_concepts", [])}
    mver = {(m, k, x["id"]): x for m in mods for k in RUNS for x in match[m]["by_run"].get(k, {}).get("model_concepts", [])}
    group_of = {(m, x.split(":")[0], x.split(":")[1]): g["name"] for m in mods for g in match[m]["extra_groups"] for x in g["members"]}
    rcon = {(m, c["id"]): c for m in mods for c in pack["modules"][m]["reference concepts"]}
    mcon = {(m, k, c["id"]): c for m in mods for k in RUNS for c in pack["modules"][m]["runs"][k]["concepts"]}
    n_rc = len(rcon)
    rc_found = {key: [k for k in RUNS if gver.get((key[0], k, key[1]), {}).get("verdict") in FOUND] for key in rcon}
    absent_names = {(m, e["name"]) for m in mods for e in pack["modules"][m]["reference entries"] if e["absent"]}
    rc_all_absent = [key for key, c in rcon.items() if c["home_elements"] and all((key[0], h) in absent_names for h in c["home_elements"])]

    # ------------------------------------------------ Phase 1 per run
    p1 = {}
    no3 = [key for key in rcon if key not in rc_all_absent]
    for k in RUNS:
        gv = [(key, x) for key, x in gver.items() if key[1] == k]
        mv = [(key, x) for key, x in mver.items() if key[1] == k]
        tp_ref = sum(x["verdict"] in FOUND for _, x in gv)
        tp_mod = sum(x["verdict"] in MATCHED for _, x in mv)
        P, R = tp_mod / len(mv), tp_ref / n_rc
        amb_ref_found = sum(1 for _, x in gv if x.get("ambiguous") and x["verdict"] in FOUND)
        amb_ref_miss = sum(1 for _, x in gv if x.get("ambiguous") and x["verdict"] not in FOUND)
        amb_mod_m = sum(1 for _, x in mv if x.get("ambiguous") and x["verdict"] in MATCHED)
        amb_mod_x = sum(1 for _, x in mv if x.get("ambiguous") and x["verdict"] not in MATCHED)
        only_partly = sum(1 for (mm, kk, cid), x in mv if x["verdict"] in MATCHED and x["gt_ids"]
                          and all(gver.get((mm, kk, g), {}).get("verdict") == "partly found" for g in x["gt_ids"]))
        p1[k] = {"tp_ref": tp_ref, "partly": sum(x["verdict"] == "partly found" for _, x in gv), "fn": n_rc - tp_ref,
                 "concepts": len(mv), "tp_model": tp_mod, "fp": len(mv) - tp_mod, "P": P, "R": R, "F1": 2 * P * R / (P + R),
                 "R_range": ((tp_ref - amb_ref_found) / n_rc, (tp_ref + amb_ref_miss) / n_rc),
                 "P_range": ((tp_mod - amb_mod_m) / len(mv), (tp_mod + amb_mod_x) / len(mv)),
                 "P_partly_strict": (tp_mod - only_partly) / len(mv),
                 "R_without_absent": sum(1 for key in no3 if k in rc_found[key]) / len(no3),
                 "ambiguous": sum(1 for _, x in gv + mv if x.get("ambiguous")), "verdicts": len(gv) + len(mv)}

    # ------------------------------------------------ Phase 2 per run (exact names), as scored and as intended
    entries = [(m, e) for m in mods for e in pack["modules"][m]["reference entries"]]
    NF = pack["entries"] - pack["absent"]

    def score(k, intended=False):
        L, found = 0, set()
        for m in mods:
            r = pack["modules"][m]["runs"][k]
            names = [(x["entity"], x["element"]) for x in r["listed"]]
            if intended:
                names += [(x["entity"], x["element"]) for x in r["malformed rows"] if x["label"] == "primary" and (x["entity"], x["element"]) not in names]
            L += len(names)
            used = set()
            for e in pack["modules"][m]["reference entries"]:
                if e["absent"]:
                    continue
                i = next((j for j, (ent, n) in enumerate(names) if n == e["name"] and j not in used), None)
                if i is not None:
                    used.add(i)
                    found.add(e["entry"])
        return L, len(found), found
    p2 = {}
    for k in RUNS:
        L, T, _ = score(k)
        assert (L, T) == (pack["totals"][k]["listed"], pack["totals"][k]["tp"])
        P, R, F = prf(T, L - T, NF - T)
        p2[k] = {"listed": L, "tp": T, "fp": L - T, "fn": NF - T, "P": P, "R": R, "F1": F}
    n_malformed = {k: sum(1 for m in mods for x in pack["modules"][m]["runs"][k]["malformed rows"] if x["label"] == "primary") for k in RUNS}
    intended = {}
    for k in RUNS:
        if n_malformed[k]:
            L, T, _ = score(k, True)
            P, R, F = prf(T, L - T, NF - T)
            intended[k] = {"listed": L, "tp": T, "fp": L - T, "fn": NF - T, "P": P, "R": R, "F1": F}
    ent_tp = {}        # entity-aware check: an element only counts in an entity that declares the name
    for k in RUNS:
        T = 0
        for m in mods:
            listed = [(x["entity"], x["element"]) for x in pack["modules"][m]["runs"][k]["listed"]]
            used = set()
            for e in pack["modules"][m]["reference entries"]:
                if e["absent"]:
                    continue
                ents = {f["entity"] for f in e["facts"]}
                i = next((j for j, (ent, n) in enumerate(listed) if n == e["name"] and ent in ents and j not in used), None)
                if i is not None:
                    used.add(i)
                    T += 1
        ent_tp[k] = T
    e_found = {e["entry"]: [k for k in RUNS if e["entry"] in pack["modules"][m]["runs"][k]["tp"]] for m, e in entries}
    fp_runs = defaultdict(list)
    for m in mods:
        for k in RUNS:
            for x in pack["modules"][m]["runs"][k]["fp"]:
                fp_runs[(m, x["entity"], x["element"])].append(k)
    malformed_keys = {(m, x["entity"], x["element"]): k for m in mods for k in RUNS for x in pack["modules"][m]["runs"][k]["malformed rows"]
                      if x["label"] == "primary"}

    def sig(m, ent, el):
        f = pack["modules"][m]["facts"].get(f"{ent}|{el}")
        return (f or {}).get("signature", {"where": "?", "role": "?", "record": "?", "influence": "?"}), (f or {}).get("facts")

    def place(m, ent, el):
        return WH.get(sig(m, ent, el)[0]["where"], sig(m, ent, el)[0]["where"])

    def role(m, ent, el):
        r = sig(m, ent, el)[0]["role"]
        return ROLE.get(r, r)

    def lines_of(fx, n=3):
        ls = (fx or {}).get("lines", [])
        return (", ".join(str(l) for l in ls[:n]) + (f" (of {len(ls)})" if len(ls) > n else "")) or "-"

    # ------------------------------------------------ disagreements between runs, on the same element
    status, target, objs_of, pts_of = defaultdict(dict), defaultdict(dict), defaultdict(dict), defaultdict(dict)
    for m in mods:
        for k in RUNS:
            r = pack["modules"][m]["runs"][k]
            listed = {(x["entity"], x["element"]): x for x in r["listed"]}
            for key, lv in r["labels"].items():
                ent, el = key.split("|", 1)
                status[(m, ent, el)][k] = "primary" if (ent, el) in listed or lv["primary"] else "secondary"
                if lv["primary"]:
                    tgt = set()
                    for c in lv["primary"]:
                        v = mver.get((m, k, c))
                        if v and v["verdict"] in MATCHED:
                            tgt |= set(v["gt_ids"])
                        elif v:
                            tgt.add("extra: " + group_of.get((m, k, c), c))
                    target[(m, ent, el)][k] = tgt
            for (ent, el), x in listed.items():
                status[(m, ent, el)][k] = "primary"
                objs_of[(m, ent, el)][k] = frozenset(x["objectives"])
                pts_of[(m, ent, el)][k] = frozenset(x["points"])
    for key, k in malformed_keys.items():
        status[key][k] = "primary (row skipped: malformed)"
    refnames = {(m, e["name"]) for m, e in entries}
    order = ["identification (named in some runs, not in others)", "classification (primary in some runs, secondary in others)",
             "identification and classification", "structural mapping (linked to different reference concepts or extra groups)",
             "security relevance (different C/I/A objectives)", "RTL placement (different diagram points)",
             "other: reply format (the run named it as primary in a row the converter skipped)"]
    cats = defaultdict(list)
    for key, st in status.items():
        vals = [st.get(k, "not named") for k in RUNS]
        if any(v.startswith("primary (row skipped") for v in vals):
            cats[order[6]].append(key)
            continue
        if len(set(vals)) > 1:
            if "not named" in vals and len({v for v in vals if v != "not named"}) > 1:
                cats[order[2]].append(key)
            elif "not named" in vals:
                cats[order[0]].append(key)
            else:
                cats[order[1]].append(key)
    prim2 = [key for key, st in status.items() if sum(st.get(k) == "primary" for k in RUNS) >= 2]
    for key in prim2:
        ks = [k for k in RUNS if status[key].get(k) == "primary"]
        if len({frozenset(target[key].get(k, set())) for k in ks if k in target[key]}) > 1:
            cats[order[3]].append(key)
        if len({objs_of[key].get(k) for k in ks if k in objs_of[key]}) > 1:
            cats[order[4]].append(key)
        if len({pts_of[key].get(k) for k in ks if k in pts_of[key]}) > 1:
            cats[order[5]].append(key)
    denom = {order[0]: len(status), order[1]: len(status), order[2]: len(status), order[3]: len(prim2), order[4]: len(prim2),
             order[5]: len(prim2), order[6]: len(status)}
    c_some = [key for key, v in rc_found.items() if 0 < len(v) < 3]
    c_verdict = [key for key in rcon if len({gver.get((key[0], k, key[1]), {}).get("verdict") for k in RUNS}) > 1]
    c_kept = [key for key in rcon if any(gver.get((key[0], k, key[1]), {}).get("verdict") == "missed: considered, not kept" for k in RUNS)
              and any(gver.get((key[0], k, key[1]), {}).get("verdict") in FOUND for k in RUNS)]
    c_obj = []
    for key in rcon:
        sets = []
        for k in RUNS:
            v = gver.get((key[0], k, key[1]), {})
            if v.get("verdict") in FOUND and v.get("model_ids"):
                sets.append(frozenset(o for cid in v["model_ids"] for o in mcon.get((key[0], k, cid), {}).get("objectives", [])))
        if len(set(sets)) > 1:
            c_obj.append(key)

    # ------------------------------------------------ clusters (agents), corrected, checked, renumbered in table order
    sfp, sfn, cf1, cf2 = J["sfp3-final"], J["sfn3-final"], J["cf1-3-final"], J["cf2-3-final"]
    by = {"sfp": sfp, "sfn": sfn, "cf1": cf1, "cf2": cf2}
    for key, field, old, new in CORRECTIONS:
        if field == "notes":
            assert old in by[key]["notes"], (key, old)
            by[key]["notes"] = by[key]["notes"].replace(old, new)
            continue
        hits = [c for c in by[key]["clusters"] if old in c.get(field, "")]
        assert len(hits) == 1, (key, field, old, len(hits))
        hits[0][field] = hits[0][field].replace(old, new)

    def clean(n):
        return re.sub(r"^\s*[A-Z]{1,2}\d+[.:]?\s+", "", n)
    seen = Counter()
    for c in sfp["clusters"]:
        c["name"] = clean(c["name"])
        c["rows"] = [(b["module"], b["entity"], b["element"], tuple(b["runs"])) for bid in c["blocks"] for b in blocks.get(bid, [])]
        for bid in c["blocks"]:
            seen[bid] += 1
    for bid in blocks:
        if seen[bid] != 1:
            problems.append(f"FP block {bid} is in {seen[bid]} clusters")
    sfp["clusters"].sort(key=lambda c: -len(c["rows"]))
    for i, c in enumerate(sfp["clusters"], 1):
        c["cid"] = f"S{i}"
    ent_by_id = {e["entry"]: (m, e) for m, e in entries}
    fn_entries = [e["entry"] for m, e in entries if len(e_found[e["entry"]]) < 3]
    seen = Counter(x for c in sfn["clusters"] for x in c["entries"])
    for x in fn_entries:
        if seen[x] != 1:
            problems.append(f"missed entry {x} is in {seen[x]} clusters")
    absent_cluster = [c for c in sfn["clusters"] if c["entries"] and all(ent_by_id[x][1]["absent"] for x in c["entries"] if x in ent_by_id)]
    sfn["clusters"] = [c for c in sfn["clusters"] if c not in absent_cluster]
    for c in sfn["clusters"] + absent_cluster:
        c["name"] = re.sub(r"^\[[^\]]*\]\s*", "", clean(c["name"]))
        c["all3"] = sum(1 for x in c["entries"] if x in ent_by_id and not e_found[x] and not ent_by_id[x][1]["absent"])
        c["missed_any"] = sum(1 for x in c["entries"] if x in ent_by_id)
    sfn["clusters"].sort(key=lambda c: (-c["all3"], -c["missed_any"]))
    for i, c in enumerate(sfn["clusters"], 1):
        c["cid"] = f"M{i}"
    for c in absent_cluster:
        c["cid"] = "absent"
    f1_items = sorted({f"{short(m)}:{rid}" for (m, rid) in rcon if len(rc_found[(m, rid)]) < 3})
    f2_items = sorted({f"{short(m)}:{g['name']}" for m in mods for g in match[m]["extra_groups"]})
    gmem = {f"{short(m)}:{g['name']}": g["members"] for m in mods for g in match[m]["extra_groups"]}
    for tag, cl, items, prefix in (("missed concept", cf1, f1_items, "CM"), ("extra concept group", cf2, f2_items, "CX")):
        cnt = Counter(x for c in cl["clusters"] for x in c["members"])
        for x in items:
            if cnt[x] != 1:
                problems.append(f"{tag} {x} is in {cnt[x]} clusters")
        for c in cl["clusters"]:
            c["name"] = re.sub(r"\s*\((missed|partly found)[^)]*\)\s*$", "", clean(c["name"]))
        cl["clusters"].sort(key=lambda c: -len(c["members"]))
        for i, c in enumerate(cl["clusters"], 1):
            c["cid"] = f"{prefix}{i}"

    def lookalikes(items):
        ids = []
        for x in items:
            if re.match(r"\s*(contrast|no correct find)", x, re.I):
                continue
            ids += [i for i in re.findall(r"\b[a-z_]+-e\d+\b", x) if i not in ids]
        a3 = sum(1 for i in ids if len(e_found.get(i, [])) == 3)
        return ids, f"{a3} / {len(ids) - a3}"

    def extra_source(m, k, concepts):
        vs = [mver.get((m, k, c), {}).get("verdict") for c in concepts]
        return "extra" if vs and all(v not in MATCHED for v in vs) else "matching"
    fpx = {(m, k, x["entity"], x["element"]): extra_source(m, k, x["concepts"]) for m in mods for k in RUNS for x in pack["modules"][m]["runs"][k]["fp"]}

    # ------------------------------------------------ Phase 1 - Phase 2 associations
    assoc = {k: Counter() for k in RUNS}
    assoc_ex = {k: defaultdict(list) for k in RUNS}
    nk2 = {k: Counter() for k in RUNS}
    for m, e in entries:
        if e["absent"] or not e["home concept"]:
            continue
        pat = re.compile(r"(?<![\w.])" + re.escape(e["name"]) + r"(?!\w)(?!\.\w)")
        for k in RUNS:
            cv = gver.get((m, k, e["home concept"]), {}).get("verdict", "?")
            found = k in e_found[e["entry"]]
            key = ("concept found, element found" if cv in FOUND and found else "concept found, element missed" if cv in FOUND else
                   "concept missed or partly, element found" if found else "concept missed or partly, element missed")
            assoc[k][key] += 1
            assoc_ex[k][key].append(f"{short(m)}:{e['name']} ({e['home concept']})")
            named_nk = any(pat.search(json.dumps(x)) for x in pack["modules"][m]["runs"][k]["not kept"])
            nk2[k][("in" if named_nk else "out", "found" if found else "missed")] += 1
    fp_src = {k: Counter(v for (m, kk, _, _), v in fpx.items() if kk == k) for k in RUNS}
    rc_mixed = []
    for (m, rid), fr in rc_found.items():
        els = [e for mm, e in entries if mm == m and e["home concept"] == rid and not e["absent"]]
        pat = {e["name"]: len(e_found[e["entry"]]) for e in els}
        if 0 < len(fr) < 3 or any(0 < v < 3 for v in pat.values()):
            rc_mixed.append((m, rid, fr, pat))

    # ------------------------------------------------ main report
    a3 = sum(1 for v in e_found.values() if len(v) == 3)
    never = sum(1 for m, e in entries if not e["absent"] and not e_found[e["entry"]])
    fpc = Counter(len(set(v)) for v in fp_runs.values())
    retried = [f"{k} {short(m)}" for m in mods for k in RUNS if pack["modules"][m]["runs"][k]["retried"]]
    top_all3 = sorted(sfp["clusters"], key=lambda c: -sum(1 for r in c["rows"] if len(set(r[3])) == 3))
    c2c = Counter(len({x.split(":")[0] for x in g["members"]}) for m in mods for g in match[m]["extra_groups"])
    c1c = Counter(3 - len(rc_found[k]) for k in rcon if len(rc_found[k]) < 3)
    fnc = Counter(3 - len(e_found[e["entry"]]) for m, e in entries if not e["absent"] and len(e_found[e["entry"]]) < 3)
    L = ["# Failure analysis of the PIO prompt across three runs", "",
         f"The PIO prompt (`two_phase_v5g`, after IEEE P3164's points of influence and observation) on `{pack['model']}`, reasoning "
         f"effort {pack['effort']}: three independent runs (r0, r1, r2) over the 15 tuning modules, with the same prompt, inputs and "
         "settings. Built 2026-10-13 by [make_report3.py](make_report3.py). Every element is listed in "
         "[THREE_RUN_FAILURES_APPENDIX.md](THREE_RUN_FAILURES_APPENDIX.md).", "",
         "**Measured or judged.** Phase 2 (structural assets) is measured: exact name matching against the reference. Phase 1 "
         "(conceptual assets) is judged: the reference has no conceptual assets, so they were derived from its 'why' texts by AI "
         "readers in the earlier analysis, and two AI judges matched each run's concepts to them. Numbers in table columns are "
         "computed by the script. Texts marked '(agent)' are AI agents' readings; numbers and claims inside them were not "
         "re-checked and count as Unverified.", ""]
    if problems:
        L += ["> **Checks that failed while building this report:** " + "; ".join(problems), ""]
    L += ["## In short", "",
          f"- **About 4 of every 5 listed elements are not in the reference.** Structural precision is "
          f"{min(v['P'] for v in p2.values()):.3f}–{max(v['P'] for v in p2.values()):.3f} (of {min(v['listed'] for v in p2.values())}–"
          f"{max(v['listed'] for v in p2.values())} elements listed per run). Recall is {min(v['R'] for v in p2.values()):.3f}–"
          f"{max(v['R'] for v in p2.values()):.3f} (of the {NF} reference elements that exist in this RTL).",
          f"- **Errors are mostly extras:** {min(v['fp'] for v in p2.values())}–{max(v['fp'] for v in p2.values())} false positives per "
          f"run against {min(v['fn'] for v in p2.values())}–{max(v['fn'] for v in p2.values())} misses.",
          f"- **The same extras come back.** {fpc[3]} of the {len(fp_runs)} distinct false-positive elements appear in all three runs. "
          "Biggest repeaters: " + "; ".join(f"{c['name'].rstrip('.')} ({sum(1 for r in c['rows'] if len(set(r[3])) == 3)})" for c in top_all3[:3]) + ".",
          "- **Most misses sit under a concept the model found** (an observed association, not a measured cause): " +
          ", ".join(f"{k} {assoc[k]['concept found, element missed']} of {p2[k]['fn']}" for k in RUNS) +
          ". The concept was there; the element was not listed as primary.",
          f"- **Which reference elements are found varies more than the totals.** {a3} of {NF} are found in all three runs, {never} in "
          f"none, {NF - a3 - never} in one or two.",
          f"- **Phase 1 (judged):** {p1['r0']['tp_ref']} of {n_rc} reference concepts are found in every run (recall {p1['r0']['R']:.3f}); "
          f"{min(v['fp'] for v in p1.values())}–{max(v['fp'] for v in p1.values())} of the {min(v['concepts'] for v in p1.values())}–"
          f"{max(v['concepts'] for v in p1.values())} model concepts per run have no reference counterpart.",
          f"- **Reply format:** the model left out the structural-assets list in {len(retried)} Phase 2 replies ({', '.join(retried)}; "
          f"each asked again once). In r1, cache, it wrote {n_malformed['r1']} primary rows with the element name in the wrong field, "
          "so they were not scored" + (f"; read as intended, r1 lists {intended['r1']['listed']} elements, precision {intended['r1']['P']:.3f}, "
                                        f"recall {intended['r1']['R']:.3f}." if "r1" in intended else "."), ""]
    L += ["## Words used", "",
          "- **Conceptual asset**: a piece of information worth protecting (for example a watchdog timeout value). **Structural asset**: "
          "the RTL port, signal or register that holds or carries it. **Reference** (ground truth): the hand-made LAsset list of "
          f"structural assets. **Findable**: a reference name that exists in this RTL ({NF} of {pack['entries']}).",
          "- **Primary**: the element that holds the value or makes the decision (prompt rule 2.6); only primaries are scored. "
          "**Secondary**: an element on the path to a primary (rule 2.7).",
          "- **F1** = an asset missed (false negative); **F2** = an asset listed that the reference does not support (false "
          "positive). **F1 score** = one number that balances precision and recall (their harmonic mean); it is not a count.",
          "- **Consistent / frequent / intermittent** = a failure in 3 / 2 / 1 of the 3 runs.",
          "- **RC1, RC2 ...** = reference conceptual assets (derived). **C1, C2 ...** = a run's own concept ids (they differ between "
          "runs); **r0:C3** = concept C3 of run r0. **Absent** = a reference name that does not occur in this RTL.",
          "- **What a reply contains.** Phase 1: concepts, each with an information text and the ports it enters and leaves "
          "through (entry and exit ports), plus a 'considered, not kept' list. Phase 2: points (diagram blocks it walked) and one "
          "row per element, labelled primary or secondary, with a reason. **Parent-side name**: the name of the same wire in the "
          "enclosing unit. **Check warning**: an automatic format check on a reply (for example a point that is not a block of "
          "that unit); warnings do not change the score (appendix A8 breaks them down).",
          "- **Places**: port (a pin of the unit), port field (one field of a record-typed pin; a record is a bundle of named "
          "values, `x.f` is field f), signal, record field, sub-unit port (a pin of a unit placed inside this one). **Roles** come "
          "from the closed set (a program-made list of every port and signal): *register* = held on a clock edge; *carries a value* "
          "= copied or used in arithmetic; *decides only* = used only in conditions; *computed without a clock* = combinational; "
          "*set by an instance* = driven by a sub-unit's output; *set only to literal values* = every assignment is a literal 0 or "
          "1, though which one can depend on conditions.",
          "- **C, I, A** = confidentiality (kept secret), integrity (not altered), availability (keeps working). **Kind** = a category "
          "the AI readers gave each concept. Acronyms in names: LSU load-store unit, CSR control and status register, PMP memory "
          "protection, TAP/JTAG debug port, DMI debug module interface, FIFO first-in-first-out buffer, AMO atomic memory operation.", ""]

    # 1
    L += ["## 1. The reference (ground truth)", "", "### 1.1 Counts", "",
          "One reference row can name several elements, so structural assets outnumber rows.", ""]
    rows = [[short(m), len(pack["modules"][m]["reference rows"]), len(pack["modules"][m]["reference entries"]),
             sum(e["absent"] for e in pack["modules"][m]["reference entries"]), len(pack["modules"][m]["reference concepts"])] for m in mods]
    rows.append(["**total**"] + [sum(r[i] for r in rows) for i in range(1, 5)])
    L += table(["Module", "Reference rows", "Structural assets", "Absent from current RTL", "Conceptual assets (derived)"], rows)
    L += ["### 1.2 Conceptual assets per module (derived)", ""]
    L += table(["Module", "Conceptual assets"], [[short(m), "; ".join(f"{c['id']} {c['name']}" for c in pack["modules"][m]["reference concepts"])] for m in mods])
    L += ["### 1.3 Structural assets per module, grouped by conceptual asset", "", "Each element with its place and role. A repeated name shows its entity.", ""]
    namecount = Counter((m, e["name"]) for m, e in entries)

    def eldesc(m, e):
        if e["absent"]:
            return f"{e['name']} (absent from current RTL)"
        fx = e["facts"][0] if e["facts"] else None
        g = BP.role_signature(fx) if fx else {}
        ent = ""
        if namecount[(m, e["name"])] > 1 and e["facts"]:
            idx = [x["entry"] for mm, x in entries if mm == m and x["name"] == e["name"]].index(e["entry"])
            ent = sorted(f["entity"] for f in e["facts"])[min(idx, len(e["facts"]) - 1)].replace("neorv32_", "") + ", "
        return f"{e['name']} ({ent}{WH.get(g.get('where'), g.get('where'))}, {ROLE.get(g.get('role'), g.get('role'))})"
    rows = []
    for m in mods:
        for c in pack["modules"][m]["reference concepts"]:
            es = [eldesc(m, e) for mm, e in entries if mm == m and e["home concept"] == c["id"]]
            note = " (its elements are absent from this RTL; judged on substitutes)" if (m, c["id"]) in rc_all_absent else ""
            rows.append([short(m), f"{c['id']} {c['name']}{note}", c["kind"], objs(c["objectives"]), "; ".join(es) or "-"])
    L += table(["Module", "Conceptual asset", "Kind (agent)", "Objective", "Structural assets (place, role)"], rows)

    # 2
    L += ["## 2. Phase 1: conceptual asset failures by run", "",
          "A model concept matches a reference concept when it is the same information (same values, same use). Verdicts on each "
          "reference concept:", ""]
    L += table(["Verdict", "Meaning", "Counts as"], [[v, mng, c] for v, mng, c in VERDICTS])
    L += [f"Two judges worked independently; they agreed on {judge_items - judge_dis} of {judge_items} found/missed and "
          f"counterpart decisions ({(judge_items - judge_dis) / judge_items:.0%}). A third agent settled the disagreements in "
          f"{', '.join(adjudicated)}, and its verdicts replace the first two. The judges flagged {sum(v['ambiguous'] for v in p1.values())} of "
          f"{sum(v['verdicts'] for v in p1.values())} verdicts as ambiguous; section 8.1 shows how far they could move the scores.", ""]
    rows = []
    for m in mods:
        row = [short(m), len(pack["modules"][m]["reference concepts"])]
        for k in RUNS:
            fnn = sum(1 for (mm, kk, _), x in gver.items() if mm == m and kk == k and x["verdict"] not in FOUND)
            ex = sum(1 for (mm, kk, _), x in mver.items() if mm == m and kk == k and x["verdict"] not in MATCHED)
            nm = sum(1 for (mm, kk, _) in mver if mm == m and kk == k)
            row.append(f"missed {fnn}; extra {ex} of {nm}")
        rows.append(row)
    L += table(["Module", "Reference concepts", "r0", "r1", "r2"], rows)
    L += ["**F1: reference concepts missed or partly found in at least one run** (* = a judge flagged the verdict as ambiguous)", ""]

    def elshort(e):
        if not e["facts"]:
            return f"{e['name']} (absent)"
        g = BP.role_signature(e["facts"][0])
        return f"{e['name']} ({WH.get(g['where'])}, {ROLE.get(g['role'], g['role'])}; lines {lines_of(e['facts'][0])})"
    L += table(["Module", "Reference concept", "Its structural assets (place, role; first RTL lines)", "r0", "r1", "r2", "Consistency"],
               [[short(m), f"{rid} {rcon[(m, rid)]['name']}", "; ".join(elshort(e) for mm, e in entries if mm == m and e["home concept"] == rid),
                 *[gver.get((m, k, rid), {}).get("verdict", "?") + ("*" if gver.get((m, k, rid), {}).get("ambiguous") else "") for k in RUNS],
                 consistency(3 - len(rc_found[(m, rid)]))] for (m, rid) in rcon if len(rc_found[(m, rid)]) < 3])
    L += [f"**F2: extra model concepts** (no reference counterpart), aligned across runs into {sum(c2c.values())} groups: {c2c[3]} in "
          f"all three runs, {c2c[2]} in two, {c2c[1]} in one. Each group, with its runs, concept ids, primaries and anchor ports, is "
          "in appendix A3; section 5.2 clusters them.", ""]

    # 3
    L += ["## 3. Phase 2: structural asset failures by run", "",
          "Exact names; each listed element counts once. Absent reference names are not counted as misses. Matching is by name; "
          f"also requiring the element's entity gives the same correct finds ({', '.join(f'{k} {ent_tp[k]}' for k in RUNS)}).", ""]
    rows = []
    for m in mods:
        d = pack["modules"][m]
        nf = sum(not e["absent"] for e in d["reference entries"])
        rows.append([short(m), nf, " / ".join(str(len(d["runs"][k]["listed"])) for k in RUNS), " / ".join(str(len(d["runs"][k]["tp"])) for k in RUNS),
                     " / ".join(str(len(d["runs"][k]["fp"])) for k in RUNS), " / ".join(str(nf - len(d["runs"][k]["tp"])) for k in RUNS)])
    L += table(["Module", "Findable reference elements", "Listed r0 / r1 / r2", "Correct (TP)", "False positives (F2)", "Missed (F1)"], rows)
    L += ["**F1: reference elements missed in at least one run** (RTL lines = line numbers printed in the RTL the model read; first 3 shown)", ""]
    L += table(["Module", "Element", "Place", "Role", "RTL lines", "Reference concept", "Missed in", "Consistency"],
               [[short(m), e["name"], place(m, e["facts"][0]["entity"], e["name"]), role(m, e["facts"][0]["entity"], e["name"]),
                 lines_of(e["facts"][0]), e["home concept"], ", ".join(k for k in RUNS if k not in e_found[e["entry"]]),
                 consistency(3 - len(e_found[e["entry"]]))] for m, e in entries if not e["absent"] and len(e_found[e["entry"]]) < 3])
    L += [f"**F2: false positives.** {len(fp_runs)} distinct elements over the three runs ({fpc[3]} in all three, {fpc[2]} in two, "
          f"{fpc[1]} in one). Section 6.1 clusters them; appendix A1 lists each with its runs, place, role and RTL lines; A2 lists "
          "them per module and run; A9 counts them per run by place and role.", ""]

    # 4
    L += ["## 4. Cross-run consistency and instability", "", "### A. How often each failure recurs", ""]
    L += table(["Failure", "Consistent (3/3)", "Frequent (2/3)", "Intermittent (1/3)", "Distinct items"],
               [["Phase 1 F1, reference concepts missed (judged)", c1c[3], c1c[2], c1c[1], sum(c1c.values())],
                ["Phase 1 F2, extra concept groups (judged)", c2c[3], c2c[2], c2c[1], sum(c2c.values())],
                ["Phase 2 F1, reference elements missed", fnc[3], fnc[2], fnc[1], sum(fnc.values())],
                ["Phase 2 F2, false-positive elements", fpc[3], fpc[2], fpc[1], sum(fpc.values())]])
    if "r1" in intended:
        moved = sum(1 for key in malformed_keys if len(set(fp_runs.get(key, []))) == 2 and malformed_keys[key] not in fp_runs.get(key, []))
        L += [f"With r1's {n_malformed['r1']} skipped cache rows read as intended, {moved} false-positive elements move from frequent to "
              f"consistent ({fpc[3]} → {fpc[3] + moved}, {fpc[2]} → {fpc[2] - moved}).", ""]
    cs = Counter(len(v) for v in rc_found.values())
    ss = Counter(len(e_found[e["entry"]]) for m, e in entries if not e["absent"])
    L += ["### B. How stably each reference asset is found", ""]
    L += table(["Reference assets", "Found in 3 runs", "2 runs", "1 run", "0 runs", "Total"],
               [["Conceptual (derived; judged)", cs[3], cs[2], cs[1], cs[0], n_rc], ["Structural (findable; measured)", ss[3], ss[2], ss[1], ss[0], NF]])
    L += ["The assets found in all three runs are listed in appendix A7.", "", "### C. Run-to-run disagreement on the same element", ""]
    notes = {order[3]: "compared across the runs where it is primary", order[5]: "a proxy for how the run read the element's RTL role: the diagram blocks it was reached at"}

    def examples(keys):
        out, seen_m = [], set()
        for m, ent, el in sorted(keys):
            if m not in seen_m:
                out.append(f"{short(m)}:{el}")
                seen_m.add(m)
            if len(out) == 5:
                break
        return ", ".join(out)
    L += table(["Kind of disagreement", "Elements", "Of", "Of which reference elements", "Examples (one per module)", "Note"],
               [[k, len(cats[k]), denom[k], sum(1 for (m, ent, el) in cats[k] if (m, el) in refnames), examples(cats[k]), notes.get(k, "")] for k in order])
    L += [f"'Of': the first three rows and the last count all {len(status)} elements named in at least one run's Phase 2 rows; "
          f"the mapping, security and placement rows count the {len(prim2)} elements that were primary in at least two runs. An "
          "element can appear in more than one row.", "",
          f"Concept level (judged): {len(c_some)} reference concepts are found in some runs and missed in others; {len(c_verdict)} get "
          f"different verdicts across runs (for example found in one run and found split in another); {len(c_kept)} are found in one "
          f"run and dropped as 'considered, not kept' in another; for {len(c_obj)} the model concepts that cover them carry different "
          "C/I/A objectives in different runs (appendix A5).", ""]

    # 5
    L += ["## 5. Recurring failure clusters: conceptual assets", "",
          "Clusters group failures that share a kind of information, a place, or what they influence. 'Observed (agent)' is what "
          "the agent read in the replies; 'Hypothesis (agent)' is its untested explanation. Full texts: appendix A6.", "",
          "### 5.1 Missed reference concepts (F1)", ""]
    rows = []
    for c in cf1["clusters"]:
        per = Counter(k for x in c["members"] for k in RUNS if k not in rc_found.get(("neorv32_" + x.split(":")[0], x.split(":")[1]), RUNS))
        o, h = split_obs(tx(c["why"]))
        rows.append([f"{c['cid']} {c['name']}", f"{len(c['members'])}: {', '.join(c['members'])}", " / ".join(str(per[k]) for k in RUNS),
                     sent(tx(c["failure_type"]), 180), sent(tx(c["rtl_characteristic"]), 160), sent(o, 220) or "-", sent(h, 200) or "-"])
    L += table(["Cluster", "Members", "Missed in r0 / r1 / r2", "Failure type (agent)", "What they share (agent)", "Observed (agent)", "Hypothesis (agent)"], rows)
    L += ["### 5.2 Extra concepts (F2)", ""]
    rows = []
    for c in cf2["clusters"]:
        per = Counter(x.split(":")[0] for it in c["members"] for x in gmem.get(it, []))
        n3 = sum(1 for it in c["members"] if len({x.split(":")[0] for x in gmem.get(it, [])}) == 3)
        o, h = split_obs(tx(c["why"]))
        rows.append([f"{c['cid']} {c['name']}", len(c["members"]), n3, " / ".join(str(per[k]) for k in RUNS),
                     sent(tx(c["failure_type"]), 160), sent(tx(c["rtl_characteristic"]), 160), sent(o, 200) or "-", sent(h, 200) or "-"])
    L += table(["Cluster", "Groups", "Groups in all 3 runs", "Concepts in r0 / r1 / r2", "Failure type (agent)", "What they share (agent)",
                "Observed (agent)", "Hypothesis (agent)"], rows)

    # 6
    L += ["## 6. Recurring failure clusters: structural assets", "",
          "'Look-alike correct finds (agent)' counts correct reference elements the agent judged to share the cluster's RTL pattern, "
          "split into those found in all three runs and those found in only some. Many look-alikes mean the pattern alone does not "
          "separate errors from correct finds. Counted places, roles, record types and influence per cluster: appendix A1.", "",
          "### 6.1 False positives (F2)", ""]
    rows = []
    for c in sfp["clusters"]:
        per = Counter(k for r in c["rows"] for k in r[3])
        all3 = [r for r in c["rows"] if len(set(r[3])) == 3]
        fam3 = sum(1 for bid in c["blocks"] if all(len(set(b["runs"])) == 3 for b in blocks.get(bid, [])))
        roles = Counter(role(r[0], r[1], r[2]) for r in c["rows"])
        src = Counter(fpx[(r[0], k, r[1], r[2])] for r in c["rows"] for k in r[3])
        rows.append([f"{c['cid']} {c['name']}", f"{len(c['rows'])} ({len(c['blocks'])})", " / ".join(str(per[k]) for k in RUNS),
                     f"{len(all3)} ({fam3})", ", ".join(f"{k} {v}" for k, v in Counter(short(r[0]) for r in c["rows"]).most_common(3)),
                     ", ".join(f"{k} {v}" for k, v in roles.most_common(2)),
                     f"{src['extra'] / (src['extra'] + src['matching']):.0%}" if src else "-",
                     sent(tx(c["failure_type"]), 150), lookalikes(c["same_shape_correct"])[1]])
    L += table(["Cluster", "Elements (index families)", "False positives r0 / r1 / r2", "In all 3 runs (families)", "Top modules", "Top roles",
                "Share listed only under extra concepts", "Failure type (agent)", "Look-alike correct finds: all 3 / some (agent)"], rows)
    L += ["An index family is one element repeated per index (for example dev_00_req_o ... dev_31_req_o).", "", "### 6.2 Misses (F1)", "",
          f"The two absent cache names ({', '.join(sorted(n for m, n in absent_names))}) are not misses and are left out here.", ""]
    rows = []
    for c in sfn["clusters"]:
        mem = [ent_by_id[x] for x in c["entries"] if x in ent_by_id]
        per = Counter(k for m, e in mem for k in RUNS if k not in e_found[e["entry"]])
        hv = Counter(cls(gver.get((m, k, e["home concept"]), {}).get("verdict", "missed")) for m, e in mem for k in RUNS if k not in e_found[e["entry"]])
        rows.append([f"{c['cid']} {c['name']}", f"{len(mem)}: " + ", ".join(f"{e['name']} ({short(m)})" for m, e in mem),
                     " / ".join(str(per[k]) for k in RUNS), c["all3"], ", ".join(f"concept {k} {v}" for k, v in hv.most_common()),
                     sent(tx(c["failure_type"]), 160), sent(tx(c["where_lost"]), 180), lookalikes(c["same_shape_correct"])[1]])
    L += table(["Cluster", "Entries", "Missed r0 / r1 / r2", "Missed in all 3", "Its reference concept in the missed runs (counted)",
                "Failure type (agent)", "Where it appears in each phase (agent)", "Look-alike correct finds: all 3 / some (agent)"], rows)

    # 7
    L += ["## 7. Phase 1 – Phase 2 associations (observed, not causal)", "",
          "Each findable reference element is paired with its reference concept (section 1.3).", ""]
    o4 = ["concept found, element found", "concept found, element missed", "concept missed or partly, element missed", "concept missed or partly, element found"]
    L += table(["Run"] + o4, [[k] + [assoc[k][o] for o in o4] for k in RUNS])
    L += table(["Run", "Element named in the Phase 1 not-kept list: found / missed", "Not named there: found / missed"],
               [[k, f"{nk2[k][('in', 'found')]} / {nk2[k][('in', 'missed')]}", f"{nk2[k][('out', 'found')]} / {nk2[k][('out', 'missed')]}"] for k in RUNS])
    L += table(["Run", "False positives listed only under extra concepts", "Listed under a concept that matches the reference"],
               [[k, fp_src[k]["extra"], fp_src[k]["matching"]] for k in RUNS])
    L += [f"Reference concepts whose verdict, or whose elements' results, change between runs: {len(rc_mixed)} (appendix A4).", ""]

    # 8
    L += ["## 8. Per-run performance and overall findings", "", "### 8.1 Phase 1 (conceptual, judged)", "",
          "Recall = reference concepts found / all reference concepts. Precision = model concepts with a counterpart / all model "
          "concepts; the two sides are counted separately, so both TPs are given. On the precision side a model concept whose only "
          "counterpart is 'partly found' still counts as matched; '(strict)' counts those as extra. 'Without RC3' leaves out cache "
          "RC3, whose elements are absent from this RTL.", ""]
    L += table(["Run", "Found (TP, reference side)", "Partly found", "Missed (FN, incl. partly)", "Model concepts", "With a counterpart (TP, model side)",
                "Extra (FP)", "Precision (strict)", "Recall", "F1 score", "If ambiguous verdicts flip: precision / recall", "Recall without RC3"],
               [[k, v["tp_ref"], v["partly"], v["fn"], v["concepts"], v["tp_model"], v["fp"], f"{v['P']:.3f} ({v['P_partly_strict']:.3f})",
                 f"{v['R']:.3f}", f"{v['F1']:.3f}", f"{v['P_range'][0]:.3f}–{v['P_range'][1]:.3f} / {v['R_range'][0]:.3f}–{v['R_range'][1]:.3f}",
                 f"{v['R_without_absent']:.3f}"] for k, v in p1.items()])
    L += ["### 8.2 Phase 2 (structural, exact names)", ""]
    rows = [[k, v["listed"], v["tp"], v["fp"], v["fn"], f"{v['P']:.3f}", f"{v['R']:.3f}", f"{v['F1']:.3f}"] for k, v in p2.items()]
    rows += [[f"{k}, with its skipped rows read as intended", v["listed"], v["tp"], v["fp"], v["fn"], f"{v['P']:.3f}", f"{v['R']:.3f}", f"{v['F1']:.3f}"]
             for k, v in intended.items()]
    L += table(["Run", "Listed", "TP", "FP", f"FN (of {NF} findable)", "Precision", "Recall", "F1 score"], rows)
    L += ["### 8.3 Modules with the most failures", "",
          "Sorted by structural misses plus false positives over the three runs (raw counts); the rate columns compare modules of different size.", ""]
    rows = []
    for m in mods:
        d = pack["modules"][m]
        nf = sum(not e["absent"] for e in d["reference entries"])
        fn = sum(nf - len(d["runs"][k]["tp"]) for k in RUNS)
        fp = sum(len(d["runs"][k]["fp"]) for k in RUNS)
        lst = sum(len(d["runs"][k]["listed"]) for k in RUNS)
        cm = sum(1 for (mm, k, _), x in gver.items() if mm == m and x["verdict"] not in FOUND)
        nrc = len(d["reference concepts"])
        ex = sum(1 for (mm, k, _), x in mver.items() if mm == m and x["verdict"] not in MATCHED)
        nmc = sum(1 for (mm, k, _) in mver if mm == m)
        rows.append([short(m), fn, f"{fn / (3 * nf):.2f}" if nf else "-", fp, f"{fp / lst:.2f}" if lst else "-", cm, f"{cm / (3 * nrc):.2f}", ex, f"{ex / nmc:.2f}"])
    rows.sort(key=lambda r: -(r[1] + r[3]))
    L += table(["Module", "Structural misses (3 runs)", "Miss rate (of 3 × findable)", "False positives (3 runs)", "Share of listed that are false",
                "Concept misses (3 runs)", "Concept miss rate", "Extra concepts (3 runs)", "Share of model concepts that are extra"], rows)
    L += ["### 8.4 Most repeatable failure patterns to investigate", ""]
    fp_line = [f"{c['cid']} {c['name'].rstrip('.')} ({sum(1 for r in c['rows'] if len(set(r[3])) == 3)})" for c in top_all3
               if any(len(set(r[3])) == 3 for r in c["rows"])]
    fn_line = [f"{c['cid']} {c['name'].rstrip('.')} ({c['all3']})" for c in sfn["clusters"] if c["all3"]]
    L += [f"- **False positives in all three runs** ({fpc[3]} elements), by cluster: " + "; ".join(fp_line) + ".",
          f"- **Misses in all three runs** ({fnc[3]} elements), by cluster: " + "; ".join(fn_line) + ".",
          "- **Reference concepts missed or only partly found in all three runs:** " +
          (", ".join(f"{short(m)}:{rid} {rcon[(m, rid)]['name']}" for (m, rid), v in rc_found.items() if not v) or "none") + ".",
          f"- **Extra concepts in all three runs:** {c2c[3]} groups (section 2, F2; clusters in section 5.2).",
          f"- **Reply format:** {len(retried)} Phase 2 replies without the structural-assets list, and {sum(n_malformed.values())} primary "
          "rows with the element name in the wrong field. One more Phase 2 reply (r0, bus) wrote all its asset rows inside its points "
          "(a format slip the scorer cannot read); its 11 reference elements count as missed in r0 (8.5).", ""]
    L += ["### 8.5 Limitations", "",
          "- The reference lists structural assets only. Its conceptual assets were derived by AI readers for the earlier gpt-5.4 "
          "analysis (workflow wf_de8dccf3-92a) and reused here unchanged.",
          f"- {pack['absent']} reference names are absent from the current RTL (cache `cache_o.cmd_dir`, `inval_i`). They are left out of "
          "the structural counts, but their reference concept (cache RC3) stays in the Phase 1 count, judged on substitutes (8.1 "
          "also gives recall without it).",
          "- Concept matching and all clusters are AI judgements; the script checks coverage, not correctness. The judges read all "
          "three runs side by side, so their per-run verdicts are not fully independent.",
          "- A reference name that occurs twice (bus `state`) takes its reference concepts in order (the switch's state → RC2, the "
          "reservation unit's state → RC6). Matching is by name; the entity-aware check gives the same totals.",
          (f"- Phase 2 replies that left out the structural-assets list were asked once more ({', '.join(retried)}); the first replies "
           f"are kept in each run's `_schema_failed/`." if retried else
           "- No Phase 2 reply left out its structural-assets list, so none was asked again."),
          "- **Format slip, r0 bus.** The Phase 2 reply wrote all 72 asset rows inside its points instead of in each walk's Assets "
          "list, so the scorer read none (0 listed, 0 of 11 correct). Read with a repair that takes those rows as walk rows, bus r0 "
          "has 9 of 11 correct of 17 listed, and r0 overall has precision 0.481 and recall 0.835 (repair_and_targets.py). The "
          "strict numbers stay the main ones.",
          "- Role words come from the program-made closed set and are only as good as its tags.",
          "- Scope: 15 tuning modules, one model, one reasoning effort, three runs. Three runs show variation but give no tight interval.", ""]
    (HERE / "THREE_RUN_FAILURES.md").write_text("\n".join(L), encoding="utf-8")

    # ------------------------------------------------ appendix
    A = ["# Three-run failure analysis: appendix", "", "Companion to [THREE_RUN_FAILURES.md](THREE_RUN_FAILURES.md). Agent texts are "
         "unverified; statements about the prompt, or about what a prompt change would do, are untested.", "",
         "## A1. Structural false positives, by cluster, with runs", ""]

    def infl(r):
        s = sig(r[0], r[1], r[2])[0]["influence"]
        return ("gives value and decides" if "gives value" in s and "decides" in s else "gives value" if "gives value" in s else
                "decides only" if "decides" in s else "none")
    for c in sfp["clusters"]:
        rws = sorted(c["rows"])
        cnt = lambda f: ", ".join(f"{k} {v}" for k, v in Counter(f(r) for r in rws).most_common())  # noqa: E731
        A += [f"### {c['cid']} {c['name']} ({len(rws)})", "", f"Definition (agent): {cell(tx(c['definition']))}", "",
              f"Failure type (agent): {cell(tx(c['failure_type']))}", "", f"What they share in the RTL (agent): {cell(tx(c['rtl_characteristic']))}", "",
              f"Counted: places — {cnt(lambda r: place(r[0], r[1], r[2]))}; roles — {cnt(lambda r: role(r[0], r[1], r[2]))}; record types — "
              f"{cnt(lambda r: sig(r[0], r[1], r[2])[0]['record'])}; influence — {cnt(infl)}.", "",
              f"Look-alike correct finds (agent): {', '.join(lookalikes(c['same_shape_correct'])[0]) or 'none'}", ""]
        A += table(["Module", "Entity", "Element", "Place", "Role", "RTL lines", "False positive in", "Consistency"],
                   [[short(m), ent, el, place(m, ent, el), role(m, ent, el), lines_of(sig(m, ent, el)[1]), ", ".join(rs), consistency(len(set(rs)))]
                    for m, ent, el, rs in rws])
    A += ["## A2. Structural false positives per module and run", ""]
    A += table(["Module", "Run", "False positives"],
               [[short(m), k, ", ".join(sorted(x["element"] + (f" ({x['entity'].replace('neorv32_', '')})" if x["entity"] != m else "")
                                               for x in pack["modules"][m]["runs"][k]["fp"]))] for m in mods for k in RUNS])
    A += ["## A2b. Structural misses, by cluster", ""]
    for c in sfn["clusters"] + absent_cluster:
        A += [f"### {c['cid']} {c['name']}", "", f"Definition (agent): {cell(tx(c['definition']))}", "", f"Why (agent): {cell(tx(c['why']))}", ""]
        A += table(["Entry", "Module", "Element", "Found in", "Reference concept", "Per run (Phase 2 rows)"],
                   [[x, short(ent_by_id[x][0]), ent_by_id[x][1]["name"], ", ".join(e_found[x]) or "none", ent_by_id[x][1]["home concept"],
                     " | ".join(f"{k}: " + ("; ".join(f"{lab} under {', '.join(cs)}" for key, lv in pack["modules"][ent_by_id[x][0]]["runs"][k]["labels"].items()
                                                       if key.split("|", 1)[1] == ent_by_id[x][1]["name"] for lab, cs in lv.items() if cs) or "not in Phase 2 rows")
                                for k in RUNS)] for x in c["entries"] if x in ent_by_id])
    A += ["## A3. Concept verdicts per run (judges)", ""]
    A += table(["Module", "Reference concept", "r0", "r1", "r2", "Model concepts (r0 | r1 | r2)", "Ambiguous in", "Evidence r0", "Evidence r1", "Evidence r2"],
               [[short(m), f"{rid} {rcon[(m, rid)]['name']}", *[gver.get((m, k, rid), {}).get("verdict", "?") for k in RUNS],
                 " | ".join(", ".join(gver.get((m, k, rid), {}).get("model_ids", [])) for k in RUNS),
                 ", ".join(k for k in RUNS if gver.get((m, k, rid), {}).get("ambiguous")) or "-",
                 *[gver.get((m, k, rid), {}).get("evidence", "") for k in RUNS]] for (m, rid) in rcon])
    A += ["### Extra concept groups (aligned across runs)", ""]
    A += table(["Module", "Group (agent)", "Kind (agent)", "Runs (concept ids)", "Consistency", "Primaries listed", "Anchor ports", "What it is (agent)"],
               [[short(m), g["name"], g["kind"], ", ".join(g["members"]), consistency(len({x.split(':')[0] for x in g['members']})),
                 "; ".join(f"{x}: " + ", ".join(sorted({y['element'] for y in pack['modules'][m]['runs'][x.split(':')[0]]['listed'] if x.split(':')[1] in y['concepts']}))
                           for x in g["members"]),
                 "; ".join(f"{x}: " + ", ".join(mcon.get((m, x.split(':')[0], x.split(':')[1]), {}).get('enters through', []) +
                                                mcon.get((m, x.split(':')[0], x.split(':')[1]), {}).get('leaves through', [])) for x in g["members"]),
                 g["what_it_is"]] for m in mods for g in match[m]["extra_groups"]])
    A += table(["Module", "Run", "Model concept", "Verdict", "Reference concept(s)", "What it is (judge)", "Ambiguous"],
               [[short(m), k, f"{cid} {x['name']}", x["verdict"], ", ".join(x["gt_ids"]), x["what_it_is"], "yes" if x.get("ambiguous") else ""]
                for (m, k, cid), x in mver.items()])
    A += ["### Where the runs differ (judges)", ""] + [f"- **{short(m)}**: {cell(match[m]['run_differences'])}" for m in mods] + [""]
    A += ["## A4. Phase 1 – Phase 2: reference concepts and elements that change between runs", ""]
    A += table(["Module", "Reference concept", "Concept found in", "Its elements: runs found (of 3)"],
               [[short(m), f"{rid} {rcon[(m, rid)]['name']}", ", ".join(fr) or "none", ", ".join(f"{k} {v}" for k, v in pat.items())] for m, rid, fr, pat in rc_mixed])
    for k in RUNS:
        A += [f"**{k}**: concept found but element missed: {', '.join(assoc_ex[k]['concept found, element missed']) or 'none'}. "
              f"Concept missed or partly but element found: {', '.join(assoc_ex[k]['concept missed or partly, element found']) or 'none'}.", ""]
    A += ["## A5. Elements and concepts whose treatment differs between runs", ""]
    for kind in order:
        A += [f"### {kind} ({len(cats[kind])})", ""]
        A += table(["Module", "Entity", "Element", "r0", "r1", "r2"],
                   [[short(m), ent, el] + [status[(m, ent, el)].get(k, "not named") +
                                           (f" → {', '.join(sorted(target[(m, ent, el)].get(k, [])))}" if target[(m, ent, el)].get(k) else "") +
                                           (f"; {''.join(sorted(objs_of[(m, ent, el)][k]))}" if k in objs_of[(m, ent, el)] else "") for k in RUNS]
                    for m, ent, el in sorted(cats[kind])])
    A += ["### Reference concepts with different verdicts, kept/not-kept decisions or objectives across runs", ""]
    A += table(["Module", "Reference concept", "r0", "r1", "r2", "Found in some runs only", "Kept in one run, not kept in another", "Objectives differ"],
               [[short(m), f"{rid} {rcon[(m, rid)]['name']}", *[gver.get((m, k, rid), {}).get("verdict", "?") for k in RUNS],
                 "yes" if (m, rid) in c_some else "", "yes" if (m, rid) in c_kept else "", "yes" if (m, rid) in c_obj else ""]
                for (m, rid) in rcon if (m, rid) in set(c_verdict) | set(c_obj)])
    A += ["## A6. Cluster texts (agents)", ""]
    for title, cl in (("Missed reference concepts", cf1), ("Extra concepts", cf2), ("Structural misses", sfn), ("Structural false positives", sfp)):
        A += [f"### {title}", ""]
        for c in cl["clusters"]:
            mem = c.get("members") or c.get("entries") or c.get("blocks")
            A += [f"**{c['cid']} {c['name']}** ({len(mem)})", ""] + [
                f"- {k.replace('_', ' ')}: {cell(tx(', '.join(c[k]) if isinstance(c[k], list) else c[k]))}" for k in
                ("definition", "failure_type", "rtl_characteristic", "role", "where", "influences", "why", "example") if k in c] + [""]
        A += [f"Notes: {cell(tx(cl.get('notes', '')))}", ""]
    A += ["## A7. Reference assets found in all three runs", ""]
    A += table(["Module", "Structural (findable) found in all 3 runs", "Conceptual found in all 3 runs"],
               [[short(m), ", ".join(e["name"] for mm, e in entries if mm == m and len(e_found[e["entry"]]) == 3),
                 ", ".join(f"{rid} {rcon[(m, rid)]['name']}" for (mm, rid) in rcon if mm == m and len(rc_found[(mm, rid)]) == 3)] for m in mods])
    A += ["## A8. Check warnings per run, module and type", ""]
    wr = Counter()
    for m in mods:
        for k in RUNS:
            for ph, ws in pack["modules"][m]["runs"][k]["warnings"].items():
                for w in ws:
                    wr[(k, short(m), re.sub(r"'[^']*'", "'…'", re.sub(r"\bC\d+\b|point \S+", "#", w))[:80])] += 1
    A += table(["Run", "Module", "Warning type", "Count"], [[k, mm, t, n] for (k, mm, t), n in sorted(wr.items())])
    A += ["## A9. False positives per run, by place and role", ""]
    sgs = {k: Counter() for k in RUNS}
    for m in mods:
        for k in RUNS:
            for x in pack["modules"][m]["runs"][k]["fp"]:
                sgs[k][(place(m, x["entity"], x["element"]), role(m, x["entity"], x["element"]))] += 1
    keys = sorted(set().union(*sgs.values()), key=lambda x: -sum(sgs[k][x] for k in RUNS))
    A += table(["Place", "Role", "r0", "r1", "r2"], [[w, r] + [sgs[k][(w, r)] for k in RUNS] for w, r in keys])
    (HERE / "THREE_RUN_FAILURES_APPENDIX.md").write_text("\n".join(A), encoding="utf-8")
    print(f"written; checks failed: {len(problems)}")
    for p in problems:
        print("  ", p)


if __name__ == "__main__":
    main()
