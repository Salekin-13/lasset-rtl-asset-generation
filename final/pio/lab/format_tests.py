"""Tests of chain.py's 2026-10-13 reply format (two_phase_v5f and later). No model call.

  python final/pio/lab/format_tests.py

T1  the format key lists in chain.py equal the keys of prompts/two_phase_v5f's OUTPUT templates, in order;
T2  new_format: true for two_phase_v5f, false for every earlier version;
T3  round trip on the 90 stored two_phase_v5 replies (r0-r2, 15 modules, both phases): each reply is rewritten in the
    new format by a test-only inverse, mapped back by chain.from_format_phase1/2, and must give the same mapped fields,
    the same check_phase1/check_phase2 problems and the same scorer rows (to_assets); the only format problems allowed
    are keys the stored reply itself lacked. Rows whose "concept id" names no Phase 1 concept (the slip) cannot be
    placed in a walk and are set apart first; their count is printed;
T4  hand-made replies on wdt (names hand-read from its closed set and RTL, as chain.selftest uses): a clean reply has no
    format problem; each planted error gives its problem;
T5  run_module on two_phase_v5f with a stub executor: Phase 2 receives Phase 1's list as written, assets are written,
    stored replies are not asked again, a reply without its top-level list is a schema failure, a row without
    "Asset RTL" is reported and left out of the assets.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402

OK = True


def check(label, cond):
    global OK
    OK &= bool(cond)
    print(f"   {'ok  ' if cond else 'FAIL'} {label}")


# ---------------- test-only inverse: v5 keys -> the 2026-10-13 format (only the keys the stored reply has)
def _put(src, pairs):
    return {new: src[old] for new, old in pairs if old in src}


def to_f1(old):
    ca = []
    for c in old["conceptual assets"]:
        d = {}
        for new in CH.F1_CONCEPT:
            if new == "Rubric":
                if "rubric" in c:
                    r = c["rubric"]
                    d["Rubric"] = {Q: r[q] for q, Q in zip(CH.QUESTIONS, CH.F_ANSWERS) if q in r} if isinstance(r, dict) else r
                continue
            old_k = dict(CH.F1_CONCEPT_V5).get(new)
            if old_k in c:
                d[new] = c[old_k]
        ca.append(d)
    nk = []
    for x in old.get("considered, not kept", []):
        reason = x.get("reason", "")
        mm = re.fullmatch(r"merged into (C\d+)", reason.strip()) if isinstance(reason, str) else None
        nk.append({"Candidate Name": x.get("concept"), "Candidate Unit": x.get("unit"),
                   "Merged Into": mm.group(1) if mm else "", "Why Not Kept": "" if mm else reason})
    return {"IP": old.get("module name"), "Conceptual Assets": ca, "Not Kept": nk, "Notes": old.get("notes", [])}


def to_f2(old, ids):
    walks = []
    for cid in ids:
        pts = []
        for p in old["points"]:
            if p.get("concept id") != cid:
                continue
            d = {"Point": p["point"]} if "point" in p else {}
            if "reached by" in p:
                d["Reached By"] = p["reached by"]
            d["Point Answers"] = {Q: p[q] for q, Q in zip(CH.QUESTIONS, CH.F_ANSWERS) if q in p}
            d.update(_put(p, (("Answer Lines", "lines"), ("Answer Reason", "reason"))))
            pts.append(d)
        assets = []
        for a in old["structural assets"]:
            if a.get("concept id") != cid:
                continue
            d = _put(a, (("Asset RTL", "element"), ("Entity", "entity"), ("Label", "label"), ("Same Role", "same role"),
                         ("Found At", "points"), ("Security Objectives", "objectives")))
            if "links" in a:
                d["Secondary To"] = [_put(l, (("Primary RTL", "primary"), ("Primary Entity", "entity"), ("Direction", "direction")))
                                     if isinstance(l, dict) else l for l in a["links"]] if isinstance(a["links"], list) else a["links"]
            if "reason" in a:
                d["Functionality"], d["Justification"] = "", a["reason"]
            d.update(_put(a, (("Asset Lines", "lines"),)))
            assets.append(d)
        prim = any(a.get("Label") == "primary" for a in assets)
        walks.append({"Concept ID": cid, "Points": pts, "Assets": assets, "Not Reported": [],
                      "No Primary Reason": "" if prim else "converted: no primary in the stored reply"})
    return {"IP": old.get("module name"), "Concept Walks": walks, "Notes": old.get("notes", [])}


def canon(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


P1_KEYS = [o for _, o in CH.F1_CONCEPT_V5] + ["rubric"]
P2_POINT_KEYS = ["concept id", "point", "reached by", "lines", "reason", *CH.QUESTIONS]
P2_ASSET_KEYS = ["concept id", "element", "entity", "same role", "points", "label", "objectives", "lines", "reason", "links"]


def restrict(d, keys):
    out = {k: d[k] for k in keys if k in d}
    if isinstance(out.get("rubric"), dict):
        out["rubric"] = {q: v for q, v in out["rubric"].items() if q in CH.QUESTIONS}
    if isinstance(out.get("links"), list):
        out["links"] = [{k: l[k] for k in ("primary", "entity", "direction") if k in l} if isinstance(l, dict) else l
                        for l in out["links"]]
    if out.get("reason") == "" and "reason" not in d:
        out.pop("reason")
    return out


def assets_key(a):
    return sorted((x["Entity"], x["Asset RTL"], x["Security Objective"], tuple(sorted(x["Objectives"])),
                   tuple(sorted(x["Concepts"])), tuple(sorted(x["Points"]))) for x in a["Assets"])


def main():
    print("T1 format keys = the v5f OUTPUT templates")
    for ph, want in ((1, ["IP", "Conceptual Assets", *CH.F1_CONCEPT[:5], *CH.F_ANSWERS, *CH.F1_CONCEPT[5:],
                          "Not Kept", *CH.F1_NOT_KEPT, "Notes"]),
                     (2, ["IP", "Concept Walks", "Concept ID", "Points", "Point", "Reached By", "Point Answers",
                          *CH.F_ANSWERS, "Answer Lines", "Answer Reason", "Assets", *CH.F2_ASSET[:7], *CH.F2_LINK,
                          *CH.F2_ASSET[7:], "Not Reported", *CH.F2_NOT_REPORTED, "No Primary Reason", "Notes"])):
        t = (LAB / "prompts" / "two_phase_v5f" / f"phase{ph}.md").read_text(encoding="utf-8")
        got = re.findall(r'"([A-Z][A-Za-z ]*)"\s*:', t[t.rfind("\nOUTPUT"):])
        check(f"phase {ph}: {len(got)} template keys equal chain.py's lists in order", got == want)

    print("T2 new_format detection")
    old = ["two_phase_v1", "two_phase_v2", "two_phase_v2a", "two_phase_v3", "two_phase_v4", "two_phase_v4a", "two_phase_v5"]
    check("false for v1 to v5, both phases", not any(CH.new_format(v, p) for v in old for p in (1, 2)))
    check("true for v5f, both phases", CH.new_format("two_phase_v5f", 1) and CH.new_format("two_phase_v5f", 2))

    print("T3 round trip on the stored two_phase_v5 replies (r0-r2)")
    n1 = n2 = same_fields1 = same_fields2 = same_chk1 = same_chk2 = same_assets = 0
    fmt_kinds, set_apart = Counter(), Counter()
    for r in (0, 1, 2):
        for m in CH.tuning_modules():
            out = CH.run_dir("two_phase_v5", "gpt-5.6-luna", r, "high")
            p1 = json.loads((out / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["reply"]
            p2 = json.loads((out / "phase2" / f"{m}.json").read_text(encoding="utf-8"))["reply"]
            concepts = CH.phase1_concepts(p1)
            ids = [c["id"] for c in concepts]
            f1 = to_f1(p1)
            back1, pr1 = CH.from_format_phase1(f1, json.dumps(f1))
            n1 += 1
            same_fields1 += [canon(restrict(c, P1_KEYS)) for c in concepts] == [canon(restrict(c, P1_KEYS)) for c in back1["conceptual assets"]] \
                and [canon(restrict(x, ["unit", "concept", "reason"])) for x in p1.get("considered, not kept", [])] == \
                    [canon(restrict(x, ["unit", "concept", "reason"])) for x in back1["considered, not kept"]]
            same_chk1 += CH.check_phase1(m, p1) == CH.check_phase1(m, back1)
            fmt_kinds.update("lacks" if " lacks " in x else x for x in pr1)
            # Phase 2: rows that cannot be placed in a walk (unknown concept id) and items that are not objects set apart
            clean = {**p2, "points": [x for x in p2["points"] if isinstance(x, dict) and x.get("concept id") in ids],
                     "structural assets": [x for x in p2["structural assets"] if isinstance(x, dict) and x.get("concept id") in ids]}
            set_apart["points"] += len(p2["points"]) - len(clean["points"])
            set_apart["rows"] += len(p2["structural assets"]) - len(clean["structural assets"])
            f2 = to_f2(clean, ids)
            back2, pr2 = CH.from_format_phase2(f2, json.dumps(f2), ids)
            n2 += 1
            same_fields2 += Counter(canon(restrict(x, P2_POINT_KEYS)) for x in clean["points"]) == \
                Counter(canon(restrict(x, P2_POINT_KEYS)) for x in back2["points"]) and \
                Counter(canon(restrict(x, P2_ASSET_KEYS)) for x in clean["structural assets"]) == \
                Counter(canon(restrict(x, P2_ASSET_KEYS)) for x in back2["structural assets"])
            same_chk2 += Counter(CH.check_phase2(m, clean, concepts)) == Counter(CH.check_phase2(m, back2, concepts))
            same_assets += assets_key(CH.to_assets(m, clean, concepts)) == assets_key(CH.to_assets(m, back2, concepts))
            fmt_kinds.update("lacks" if " lacks " in x else x for x in pr2)
    check(f"phase 1: mapped fields equal in {same_fields1} of {n1}", same_fields1 == n1)
    check(f"phase 1: check_phase1 problems equal in {same_chk1} of {n1}", same_chk1 == n1)
    check(f"phase 2: mapped points and rows equal in {same_fields2} of {n2}", same_fields2 == n2)
    check(f"phase 2: check_phase2 problems equal in {same_chk2} of {n2}", same_chk2 == n2)
    check(f"scorer rows (to_assets) equal in {same_assets} of {n2}", same_assets == n2)
    check(f"format problems only for keys the stored replies lacked ({dict(fmt_kinds)})", set(fmt_kinds) <= {"lacks"})
    print(f"   (set apart before the Phase 2 round trip, unknown concept id: {set_apart['rows']} rows, {set_apart['points']} points)")

    print("T4 hand-made replies on wdt")
    w = "neorv32_wdt"
    ans = lambda i: dict(zip(CH.F_ANSWERS, ["no", i, "no", "no"]))
    c1 = {"Concept ID": "C1", "Concept Name": "watchdog enable", "Unit": w, "Information": "x", "Rubric": ans("yes"),
          "Rubric Reason": "r", "Objectives At Risk": ["I"], "Attack": "a", "Enters Through": ["bus_req_i.data"],
          "Leaves Through": ["clkgen_en_o"], "Entry Lines": [94], "Held Lines": [94], "Exit Lines": [140]}
    g1 = {"IP": w, "Conceptual Assets": [c1], "Not Kept": [{"Candidate Name": "y", "Candidate Unit": w, "Merged Into": "C1",
                                                            "Why Not Kept": ""}], "Notes": []}
    v, pr = CH.from_format_phase1(g1, json.dumps(g1))
    check(f"phase 1 clean reply: no format problem ({pr})", pr == [])
    check("phase 1 mapping: id, objectives, lower-case rubric, merged reason",
          v["conceptual assets"][0]["id"] == "C1" and v["conceptual assets"][0]["objectives"] == ["I"]
          and v["conceptual assets"][0]["rubric"]["integrity"] == "yes" and v["considered, not kept"][0]["reason"] == "merged into C1")
    swap = {"Concept ID": "C1", "Unit": w, "Concept Name": "x", **{k: c1[k] for k in CH.F1_CONCEPT[3:]}}
    nobj = {k: c1[k] for k in CH.F1_CONCEPT if k != "Objectives At Risk"}
    extra = {**c1, "objectives": ["I"]}
    norub = {**c1, "Rubric": {k: c1["Rubric"][k] for k in CH.F_ANSWERS[:2] + CH.F_ANSWERS[3:]}}
    bad1 = {"IP": w, "Conceptual Assets": [swap, {**nobj, "Concept ID": "C2"}, {**extra, "Concept ID": "C3"}, {**norub, "Concept ID": "C4"}],
            "Not Kept": [{"Candidate Name": "a", "Candidate Unit": w, "Merged Into": "C9", "Why Not Kept": ""},
                         {"Candidate Name": "b", "Candidate Unit": w, "Merged Into": "C1", "Why Not Kept": "z"},
                         {"Candidate Name": "c", "Candidate Unit": w, "Merged Into": "", "Why Not Kept": ""}], "Notes": []}
    text = json.dumps(bad1).replace('"Concept Name": "x"', '"Concept Name": "x", "Concept Name": "x2"', 1)
    v, pr = CH.from_format_phase1(json.loads(text), text)
    want = {"out of order": "conceptual asset C1 keys out of order", "lacks objectives": "conceptual asset C2 lacks ['Objectives At Risk']",
            "extra key": "conceptual asset C3 has keys the format does not show ['objectives']",
            "rubric lacks": "conceptual asset C4 Rubric lacks ['Availability']", "twice": "key 'Concept Name' written twice",
            "unknown merge": "Merged Into 'C9' is not a kept Concept ID", "both": "both Merged Into and Why Not Kept",
            "neither": "neither Merged Into nor Why Not Kept"}
    for lab, s in want.items():
        check(f"phase 1 planted error found: {lab}", any(s in x for x in pr))
    check("phase 1 missing key stays missing for the v5 check ('objectives None')",
          any("C2: objectives None" in x for x in CH.check_phase1(w, v)))
    v, _ = CH.from_format_phase1({"IP": w, "conceptual assets": [], "Notes": []}, "")
    check("phase 1 without 'Conceptual Assets': schema failure as before", CH.phase1_concepts(v) is None)

    pt = {"Point": "bus_access", "Reached By": "holding block", "Point Answers": ans("yes"), "Answer Lines": [94],
          "Answer Reason": "r"}
    prim = {"Asset RTL": "ctrl.enable", "Entity": w, "Label": "primary", "Same Role": [], "Found At": ["bus_access"],
            "Security Objectives": ["I"], "Secondary To": [], "Functionality": "f", "Justification": "j", "Asset Lines": [94]}
    sec = {"Asset RTL": "clkgen_en_o", "Entity": w, "Label": "secondary", "Same Role": [], "Found At": [],
           "Security Objectives": ["I"], "Secondary To": [{"Primary RTL": "ctrl.enable", "Primary Entity": w, "Direction": "a"}],
           "Functionality": "f2", "Justification": "j2", "Asset Lines": [140]}
    walk = lambda cid, assets, npr="", nrep=(): {"Concept ID": cid, "Points": [pt], "Assets": list(assets),
                                                 "Not Reported": list(nrep), "No Primary Reason": npr}
    g2 = {"IP": w, "Concept Walks": [walk("C1", [prim, sec])], "Notes": []}
    v, pr = CH.from_format_phase2(g2, json.dumps(g2), ["C1"])
    check(f"phase 2 clean reply: no format problem ({pr})", pr == [])
    check("phase 2 mapping: concept id from the walk, answers, links, reason = Functionality + Justification",
          v["points"][0]["concept id"] == "C1" and v["points"][0]["integrity"] == "yes" and v["points"][0]["lines"] == [94]
          and v["structural assets"][1]["links"] == [{"primary": "ctrl.enable", "entity": w, "direction": "a"}]
          and v["structural assets"][0]["reason"] == "f j" and v["structural assets"][0]["concept id"] == "C1")
    noname = {k: prim[k] for k in CH.F2_ASSET if k != "Asset RTL"}
    badlink = {**sec, "Secondary To": [{"primary": "ctrl.enable", "Primary Entity": w, "Direction": "a"}]}
    nr = {"Element RTL": "ctrl.enable", "Element Entity": w, "Why Not Reported": "x"}
    badpt = {**pt, "Point Answers": {k: "no" for k in CH.F_ANSWERS[:3]}}
    bad2 = {"IP": w, "Concept Walks": [walk("C2", [noname, prim], npr="none qualifies", nrep=[nr]), walk("C1", [badlink]),
                                       {**walk("C3", [prim]), "Points": [badpt]}], "Notes": []}
    v, pr = CH.from_format_phase2(bad2, json.dumps(bad2), ["C1", "C2", "C4"])
    want = {"row without Asset RTL": "walk C2 asset 1 lacks ['Asset RTL']", "primary and reason": "walk C2 has a primary and a No Primary Reason",
            "no primary, empty reason": "walk C1 has no primary and an empty No Primary Reason",
            "not reported and listed": "is also under Assets in the same walk",
            "link keys": "Secondary To entry 1 has keys the format does not show ['primary']",
            "answers lack": "Point Answers lacks ['Undermined Expected Behavior']",
            "walk missing": "Concept Walks miss ['C4']", "walk unknown": "Concept Walks have ids not in CONCEPTS ['C3']"}
    for lab, s in want.items():
        check(f"phase 2 planted error found: {lab}", any(s in x for x in pr))
    _, pr = CH.from_format_phase2({**g2, "Concept Walks": [walk("C2", [prim]), walk("C1", [prim])]}, "", ["C1", "C2"])
    check("phase 2 planted error found: walks out of CONCEPTS order", any("not in the order CONCEPTS gives" in x for x in pr))
    _, pr = CH.from_format_phase2({**g2, "Concept Walks": [walk("C1", [prim]), walk("C1", [prim])]}, "", ["C1"])
    check("phase 2 planted error found: a walk repeated", any("Concept Walks repeat ['C1']" in x for x in pr))
    v, _ = CH.from_format_phase2({"IP": w, "Concept Walks": {"C1": []}, "Notes": []}, "", ["C1"])
    check("phase 2 without a 'Concept Walks' list: schema failure as before", CH.phase2_lists(v) is None)

    print("T5 run_module on two_phase_v5f with a stub executor")
    sent = []

    def stub(replies):
        def f(system, user):
            ph = 2 if "=== CONCEPTS" in user else 1
            sent.append((ph, user))
            return json.dumps(replies[ph]), {"in": 0, "out": 0}
        return f
    with tempfile.TemporaryDirectory() as td:
        row = CH.run_module("two_phase_v5f", w, stub({1: g1, 2: g2}), Path(td))
        rec1 = json.loads((Path(td) / "phase1" / f"{w}.json").read_text(encoding="utf-8"))
        rec2 = json.loads((Path(td) / "phase2" / f"{w}.json").read_text(encoding="utf-8"))
        a = json.loads((Path(td) / "assets" / f"{w}.json").read_text(encoding="utf-8"))
        n = len(sent)
        again = CH.run_module("two_phase_v5f", w, stub({1: g1, 2: g2}), Path(td))
        asked_again = len(sent) - n
    u2 = sent[1][1] if len(sent) > 1 else ""
    check(f"done; Phase 2 got Phase 1's list as written ('Concept ID' in, 'id' out) ({row['status']})",
          row["status"] == "done" and '"Concept ID": "C1"' in u2 and '"id": "C1"' not in u2)
    check("stored records hold the mapped reply and say so; no format problem in either",
          rec1["reply"]["conceptual assets"][0]["id"] == "C1" and "reply keys" in rec1 and "reply keys" in rec2
          and not any(str(x).startswith(("format:", "consistency:")) for x in rec1["problems"] + rec2["problems"]))
    check("assets in scorer format: ctrl.enable, Integrity; the secondary left out",
          [(x["Asset RTL"], x["Security Objective"]) for x in a["Assets"]] == [("ctrl.enable", "Integrity")])
    check("stored replies are not asked again", again["status"] == "done" and asked_again == 0)
    sent.clear()
    with tempfile.TemporaryDirectory() as td:
        r_c = CH.run_module("two_phase_v5f", w, stub({1: {"IP": w, "conceptual assets": [], "Notes": []}, 2: g2}), Path(td))
    check(f"Phase 1 without 'Conceptual Assets': schema failure, no Phase 2 call ({r_c['status']})",
          r_c["status"] == "phase 1 schema failure" and [s[0] for s in sent] == [1])
    slip = {**g2, "Concept Walks": [walk("C1", [prim, noname])]}
    with tempfile.TemporaryDirectory() as td:
        r_d = CH.run_module("two_phase_v5f", w, stub({1: g1, 2: slip}), Path(td))
        rec2 = json.loads((Path(td) / "phase2" / f"{w}.json").read_text(encoding="utf-8"))
        a = json.loads((Path(td) / "assets" / f"{w}.json").read_text(encoding="utf-8"))
    check(f"a row without 'Asset RTL': reported, skipped by the converter, module done ({r_d['status']}, skipped {a['_skipped']})",
          r_d["status"] == "done" and any("lacks ['Asset RTL']" in x for x in rec2["problems"]) and a["_skipped"] == 1)
    return OK


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ok = main()
    print("ALL FORMAT TESTS PASS" if ok else "FORMAT TESTS FAILED")
    sys.exit(0 if ok else 1)
