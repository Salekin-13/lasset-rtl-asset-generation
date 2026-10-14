"""Which isolation contradictions are a reading difference, and which only a list difference? Code only, read-only on
the runs; writes clause_contradictions.json.

A contradiction (analyze_isolation.py): the same rule wording, the same module, an element on the decision list of one
repeat and on the opposite list of the other. Each side cites "rule words". Both citations are mapped to the clause of the
rule text they quote best (clauses: the text split at '.', ';' and ':'; score = share of the citation's content words
found in the clause; a citation joined with '...' is scored piece by piece and the clause with the highest summed score
wins):
  same clause        both repeats quote the same clause and file the element on opposite lists: a reply-format
                     difference (e.g. an exception of a rule that makes elements primary filed once as "barred" and once
                     as "spared"), not two readings of the rule
  different clauses  one repeat applies the bar's words, the other an exception's (or another bar's): the rule's words are
                     read two ways for the same element
Groups: per (rule, phase, barred-side clause, kept-side clause): count, modules, examples, both clause texts.
Self-test (nothing is written if it fails): 11 contradictions read by hand on 2026-10-14 (4 same clause, 7 different).

  python -B clause_check.py
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402
import analyze_isolation as A  # noqa: E402

STOP = set("the a an and or of to its it is are be by on in at for from with that this these those their its own not no "
           "any as only when which who whose than then there here into onto also even each every one such".split())

HAND = [  # (rule, phase, module, element, expected class) read by hand from the replies on 2026-10-14
    ("P2X-input-port-setting-the-value", "P2", "neorv32_cpu_alu", "clk_i", "same clause"),
    ("P2X-input-port-setting-the-value", "P2", "neorv32_cpu_alu", "ctrl_i", "same clause"),
    ("P1-10", "P2", "neorv32_cpu", "ctrl.csr_we", "same clause"),
    ("P1-14", "P1", "neorv32_neoled", "tx_fifo.rdata", "same clause"),
    ("P1-10", "P2", "neorv32_cpu_frontend", "ipb.avail", "different clauses"),
    ("P1-05", "P1", "neorv32_bus", "int_rsp.data", "different clauses"),
    ("P1-23", "P1", "neorv32_dmem", "bus_req_i.stb", "different clauses"),
    ("P1-22", "P2", "neorv32_cpu", "dbus_req_o.stb", "different clauses"),
    ("P1-07", "P2", "neorv32_bus", "keeper.lock", "different clauses"),
    ("P1-17", "P1", "neorv32_debug_dm", "auth.busy", "different clauses"),
    ("P1-22", "P2", "neorv32_cpu_control", "ctrl.lsu_rw", "different clauses"),
]


def toks(s):
    return {w for w in re.findall(r"[a-z][a-z\-]+", (s or "").lower().replace("’", "'")) if len(w) >= 3 and w not in STOP}


def clauses(text):
    return [c.strip() for c in re.split(r"(?<=[.;:])\s+", text) if len(toks(c)) >= 2]


def best_clause(words, cl):
    pieces = [p for p in re.split(r"\.\.\.|…|\[[^\]]*\]", words or "") if toks(p)]
    if not pieces:
        return None
    ct = [toks(c) for c in cl]
    score = [sum(len(toks(p) & t) / len(toks(p)) for p in pieces) for t in ct]
    i = max(range(len(cl)), key=lambda j: (score[j], -j))
    return i if score[i] > 0 else None


def cited(reply, key, e):
    return [x.get("rule words") or "" for x in reply.get(key) or []
            if isinstance(x, dict) and x.get("element") and A.covered(e, {x["element"]})]


def classify(R, texts, rid, ph, m, e):
    """-> (class, barred-side clause index, kept-side clause index) for one contradiction."""
    dkey, okey = ("spared", "barred") if A.adds(rid) else ("barred", "spared")
    cl = clauses(texts[rid][ph])
    rp = [R[(rid, ph, m, r)] for r in (0, 1)]
    # the repeat that has e on the decision list and the repeat that has it on the opposite list
    for a, b in ((0, 1), (1, 0)):
        if A.covered(e, A.names(rp[a], dkey)) and not A.covered(e, A.names(rp[b], dkey)) and A.covered(e, A.names(rp[b], okey)):
            wd = " ".join(cited(rp[a], dkey, e))
            wo = " ".join(cited(rp[b], okey, e))
            i, j = best_clause(wd, cl), best_clause(wo, cl)
            if i is None or j is None:
                return "unknown", i, j
            # dkey side is "barred" for a bar; report as (barred-side, kept-side)
            bi, ki = (i, j) if dkey == "barred" else (j, i)
            return ("same clause" if i == j else "different clauses"), bi, ki
    return "unknown", None, None


def contradictions(R, rid, ph):
    dkey, okey = ("spared", "barred") if A.adds(rid) else ("barred", "spared")
    have = [{k[2] for k in R if k[0] == rid and k[1] == ph and k[3] == r} for r in (0, 1)]
    out = []
    for m in sorted(have[0] & have[1]):
        rp = [R[(rid, ph, m, r)] for r in (0, 1)]
        _, c = A.flips_of([A.names(x, dkey) for x in rp], [A.names(x, okey) for x in rp])
        out += [(m, e) for e in sorted(c)]
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    R = A.load(lambda r: ISO.run_root(rep=r))
    texts = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    bad = []
    for rid, ph, m, e, want in HAND:
        got = classify(R, texts, rid, ph, m, e)[0]
        if got != want:
            bad.append((rid, ph, m, e, want, got))
    print(f"self-test (11 hand-read contradictions): {'PASS' if not bad else 'FAIL'}")
    for b in bad:
        print("  ", b)
    if bad:
        sys.exit(1)
    rules = sorted({k[0] for k in R})
    out, rows = {}, []
    for rid in rules:
        for ph in ("P1", "P2"):
            if not texts.get(rid, {}).get(ph):
                continue
            cs = contradictions(R, rid, ph)
            if not cs:
                continue
            cl = clauses(texts[rid][ph])
            grp = defaultdict(list)
            n = {"same clause": 0, "different clauses": 0, "unknown": 0}
            mods_diff = set()
            for m, e in cs:
                k, bi, ki = classify(R, texts, rid, ph, m, e)
                n[k] += 1
                if k == "different clauses":
                    grp[(bi, ki)].append(f"{m}:{e}")
                    mods_diff.add(m)
            groups = [{"barred by clause": cl[bi], "kept by clause": cl[ki], "elements": len(v),
                       "modules": len({x.split(':')[0] for x in v}), "examples": v[:6]}
                      for (bi, ki), v in sorted(grp.items(), key=lambda kv: -len(kv[1]))]
            out[f"{rid} {ph}"] = {"title": texts[rid]["title"], **n, "modules with a reading difference": len(mods_diff),
                                  "reading-difference groups": groups}
            rows.append((rid, ph, texts[rid]["title"], n, len(mods_diff), len(groups)))
    (HERE / "clause_contradictions.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    rows.sort(key=lambda x: (-x[4], -x[3]["different clauses"]))
    print(f"{'rule':44s} ph {'title':30s} same diff unk | modules with a reading difference | clause pairs")
    for rid, ph, title, n, md, g in rows:
        print(f"{rid:44s} {ph} {title[:30]:30s} {n['same clause']:4d} {n['different clauses']:4d} {n['unknown']:3d} | {md:3d} | {g}")
    tot = {k: sum(r[3][k] for r in rows) for k in ("same clause", "different clauses", "unknown")}
    print("total:", tot)


if __name__ == "__main__":
    main()
