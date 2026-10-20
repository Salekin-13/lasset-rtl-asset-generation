"""Evidence packs for the Claude-agent diagnosis of the held-out change (versions v1, v2, v4a, v5, v7, v8; gpt-5.6-luna,
high, r0-r2). Code only, read-only on the runs; writes packs/ and diffs/ next to this file.

  packs/scores.md                 compare_versions.py and transitions.py tables (re-run here)
  packs/lineage.md                what each version changed (EXPERIMENT_LOG.md version table; v8 from its README)
  diffs/<a>_<b>.md                sentence-level diff of common.md, phase1.md, phase2.md between consecutive versions,
                                  each sentence with its file line number (A's for removed, B's for added)
  packs/finds_<a>_<b>.md          every reference occurrence whose runs found differ between a and b, held-out modules
                                  (full detail) and tuning modules (short, for contrast): runs found per version; per
                                  run of a and b, FOUND (concept, justification) or MISSED (where lost, the reply's
                                  reason, Not Kept rows linked to it and the rules they name: attribute.tag, approximate)
  packs/fps_<a>_<b>.md            every held-out false-positive name whose listed runs differ between a and b: runs
                                  listed per version; one listing's concept and justification; one non-listing's reason
  packs/persistent_misses.md      held-out occurrences found in at most 1 run of every version
  packs/persistent_fps.md         held-out FP names listed in 2+ runs of both v7 and v8, with their history
Self-test: the runs-found and FP-run counts written in the packs sum to compare_versions.json's TP and FP totals.

  python make_packs.py
"""
import difflib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import transitions as T  # noqa: E402
import attribute as A  # noqa: E402

CV, CH, K = T.CV, T.CH, T.K
LAB = T.LAB
VERS = CV.VERS
S = lambda v: v.replace("two_phase_", "")  # noqa: E731
PACKS, DIFFS = HERE / "packs", HERE / "diffs"
CUT = 320


def clip(s, n=CUT):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 3] + "..."


def sentences(path):
    out = []
    if not path.exists():
        return out
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for s in re.split(r"(?<=[.:;])\s+(?=[A-Z(\"-])", line.strip()):
            if s.strip():
                out.append((i, s.strip()))
    return out


def write_diffs():
    DIFFS.mkdir(exist_ok=True)
    for a, b in T.PAIRS:
        lines = [f"# Prompt diff {S(a)} -> {S(b)} (sentence level; '-' = only in {S(a)} with its line there, '+' = only in {S(b)} "
                 f"with its line there)\n"]
        for f in ("common.md", "phase1.md", "phase2.md"):
            sa, sb = sentences(LAB / "prompts" / a / f), sentences(LAB / "prompts" / b / f)
            ta, tb = [x[1] for x in sa], [x[1] for x in sb]
            sm = difflib.SequenceMatcher(a=ta, b=tb, autojunk=False)
            lines.append(f"\n## {f}  ({len(' '.join(ta).split())} -> {len(' '.join(tb).split())} words)\n")
            n = 0
            for op, i1, i2, j1, j2 in sm.get_opcodes():
                if op == "equal":
                    continue
                for i in range(i1, i2):
                    lines.append(f"- [{S(a)} {f}:{sa[i][0]}] {sa[i][1]}")
                    n += 1
                for j in range(j1, j2):
                    lines.append(f"+ [{S(b)} {f}:{sb[j][0]}] {sb[j][1]}")
                    n += 1
            if not n:
                lines.append("(no change)")
        (DIFFS / f"{S(a)}_{S(b)}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def lineage():
    log = (LAB / "EXPERIMENT_LOG.md").read_text(encoding="utf-8")
    rows = [l for l in log.splitlines() if re.match(r"\| v(1|2|2a|3|4|4a|5|5f|5g|6|6d|7) \|", l)]
    out = ["# Version lineage (EXPERIMENT_LOG.md version table, 'What changed' column; per-run tuning numbers omitted)\n",
           "Build order: v1 -> v2 -> v2a -> v3 -> v4 -> v4a -> v5 -> v5f -> v5g -> v6 -> v6abc -> v6d -> v7 -> v8. "
           "Held-out runs exist for v1, v2, v4a, v5, v7, v8 only, so the steps v2 -> v4a (v2a, v3, v4 in between) and v5 -> v7 "
           "(v5f, v5g, v6, v6abc, v6d in between) each bundle several changes.\n"]
    for l in rows:
        c = [x.strip() for x in l.strip("|").split("|")]
        if len(c) >= 5:                                   # the version table, not the checksum table
            out.append(f"- {c[0]}: {c[1]}")
    out.append("- v8: v7 + seven prompt rules from the v7 failure analysis (B1, R1-R6; new Phase 1 rule titles include "
               "'Decided-on instance outputs', 'Memory access address', 'Requests waiting for a grant'); its README's 'not run' "
               "status predates the runs used here")
    (PACKS / "lineage.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    PACKS.mkdir(exist_ok=True)
    groups, ref = CV.groups_and_ref()
    the12 = set(groups["held-out: the 12"])
    sc = subprocess.run([sys.executable, str(HERE / "compare_versions.py")], capture_output=True, text=True, encoding="utf-8")
    tr = subprocess.run([sys.executable, str(HERE / "transitions.py")], capture_output=True, text=True, encoding="utf-8")
    if sc.returncode or tr.returncode or "FAIL" in sc.stdout + tr.stdout:
        sys.exit("compare_versions.py or transitions.py failed: nothing written")
    (PACKS / "scores.md").write_text("# Scores (compare_versions.py)\n\n```\n" + sc.stdout + "```\n\n# Where held-out misses are lost "
                                     "(transitions.py)\n\n```\n" + tr.stdout + "```\n", encoding="utf-8")
    lineage()
    write_diffs()
    allm = groups["tuning"] + groups["held-out"]
    listed = {(v, r, m): [x["Asset RTL"] for x in json.loads((CH.run_dir(v, T.MODEL, r, T.EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]]
              for v in VERS for r in T.REPS for m in allm}
    cons = {}

    def concepts(v, r, m):
        if (v, r, m) not in cons:
            cons[(v, r, m)] = {CH._key(c.get("id")): c for c in CH.phase1_concepts(T.load(v, r, m, 1)["reply"]) or []}
        return cons[(v, r, m)]

    def primary_rows(v, r, m, n):
        cs = concepts(v, r, m)
        out = []
        for a in (T.load(v, r, m, 2)["reply"] or {}).get("structural assets") or []:
            if isinstance(a, dict) and a.get("label") == "primary" and (a.get("element") == n or n in CH.as_list(a.get("same role"))):
                c = cs.get(CH._key(a.get("concept id")), {})
                out.append(f"{a.get('concept id')} '{clip(c.get('concept'), 80)}': {clip(a.get('justification') or a.get('reason'), 240)}")
        return out

    def missed(v, r, m, n):
        st, why = T.where_lost(v, r, m, n, listed[(v, r, m)])
        rules = A.tag(v, r, m, n, why)
        linked = [row for row in A.not_kept_rows(v, r, m) if T.has(n, row)][:2]
        s = f"MISSED ({st})"
        if why:
            s += ": " + " || ".join(clip(w, 260) for w in why[:2])
        if linked and st != "Not Kept":
            s += " | Not Kept rows naming it: " + " || ".join(clip(x, 220) for x in linked)
        if rules:
            s += f" | rules named (code tag): {sorted(rules)}"
        return s

    def occs(m):
        k, out = Counter(), []
        for n in ref[m]:
            k[n] += 1
            out.append((n, k[n]))
        return out

    def found_runs(v, m, n, k):
        return [r for r in T.REPS if Counter(listed[(v, r, m)])[n] >= k]

    tp_total = Counter()
    fp_total = Counter()
    for a, b in T.PAIRS:
        L = [f"# Finds that change between {S(a)} and {S(b)}\n",
             f"Per reference occurrence (module:name#k) whose runs found (of 3) differ between {S(a)} and {S(b)}. 'found per version' "
             f"lists runs found in {', '.join(S(v) for v in VERS)}. '*' marks the 12 held-out modules that cause v7's drop. For each run "
             f"of {S(a)} and {S(b)}: FOUND with the concept it was primary for and the justification, or MISSED with where it was lost "
             f"and the reply's own words. 'rules named (code tag)' is a keyword match on the linked reply text (approximate).\n"]
        for s in ("held-out", "tuning"):
            L.append(f"\n## {s} modules\n")
            for m in groups[s]:
                rows = []
                kinds, _ = T.kinds(m)
                for n, k in occs(m):
                    f = {v: found_runs(v, m, n, k) for v in VERS}
                    if len(f[a]) == len(f[b]):
                        continue
                    hist = " ".join(f"{S(v)}:{len(f[v])}" for v in VERS)
                    rows.append(f"\n### {'*' if m in the12 else ''}{m[8:]}:{n}#{k} ({kinds.get(n, '?')}) found per version {hist}")
                    if s == "tuning":
                        lose = b if len(f[b]) < len(f[a]) else a
                        r = [r for r in T.REPS if r not in f[lose]][0]
                        rows.append(f"- {S(lose)} r{r} {missed(lose, r, m, n)}")
                        continue
                    for v in (a, b):
                        for r in T.REPS:
                            rows.append(f"- {S(v)} r{r} " + (("FOUND: " + " || ".join(primary_rows(v, r, m, n)[:2])) if r in f[v] else missed(v, r, m, n)))
                if rows:
                    L.append(f"\n## module {m[8:]}{' (*)' if m in the12 else ''}")
                    L += rows
        (PACKS / f"finds_{S(a)}_{S(b)}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
        # FPs, held-out
        F = [f"# Held-out false positives that change between {S(a)} and {S(b)}\n",
             f"Per module, each listed name that is not a reference find and whose runs listed (of 3) differ between {S(a)} and {S(b)}. "
             f"'listed per version' covers {', '.join(S(v) for v in VERS)}. For the version listing it more often: one listing's concept and "
             f"justification. For the other: one run's reason it is not listed (where it went, the reply's words, rules named by code "
             f"tag). Kind: closed-set kind; 'bus record port field' = a field of a bus request or response record port.\n"]
        for m in groups["held-out"]:
            kd, par = T.kinds(m)
            fpc = {}
            for v in VERS:
                for r in T.REPS:
                    left = Counter(ref[m])
                    for x in listed[(v, r, m)]:
                        if left[x] > 0:
                            left[x] -= 1
                        else:
                            fpc.setdefault(x, Counter())[v] += 1
            rows = []
            for x in sorted(fpc):
                c = fpc[x]
                if c[a] == c[b]:
                    continue
                kind = kd.get(x, "not in closed set")
                if kind == "port field":
                    kind = "bus record port field" if (par.get(x, (None, None))[1] or "").startswith(("bus_req", "bus_rsp")) else "other record port field"
                more, less = (a, b) if c[a] > c[b] else (b, a)
                rm = [r for r in T.REPS if x in listed[(more, r, m)]][0]
                rl = [r for r in T.REPS if x not in listed[(less, r, m)]]
                why_less = (f"\n    {S(less)} r{rl[0]} NOT LISTED: " + missed(less, rl[0], m, x).replace("MISSED", "", 1)) if rl else \
                    f"\n    {S(less)}: listed in every run, fewer times (a duplicate listing under a second entity counts as an extra FP)"
                rows.append(f"- {x} ({kind}) listed per version " + " ".join(f"{S(v)}:{c[v]}" for v in VERS)
                            + f"\n    {S(more)} r{rm} LISTED: " + " || ".join(primary_rows(more, rm, m, x)[:1]) + why_less)
            if rows:
                F.append(f"\n## module {m[8:]}{' (*)' if m in the12 else ''}: FP runs {S(a)} {sum(fpc[x][a] for x in fpc)} -> {S(b)} {sum(fpc[x][b] for x in fpc)}")
                F += rows
        (PACKS / f"fps_{S(a)}_{S(b)}.md").write_text("\n".join(F) + "\n", encoding="utf-8")
    # persistent misses and FPs (held-out), and the self-test totals
    P = ["# Held-out reference occurrences found in at most 1 run of every version\n",
         "Per occurrence: runs found per version; per version one missing run's reason (where lost, reply's words, rules named).\n"]
    Q = ["# Held-out false positives listed in 2+ runs of both v7 and v8\n",
         "Per name: kind, runs listed per version, and the v7 and v8 concept and justification of one listing.\n"]
    for m in groups["held-out"]:
        kd, par = T.kinds(m)
        for n, k in occs(m):
            f = {v: found_runs(v, m, n, k) for v in VERS}
            for v in VERS:
                tp_total[v] += len(f[v])
            if all(len(f[v]) <= 1 for v in VERS):
                P.append(f"\n### {'*' if m in the12 else ''}{m[8:]}:{n}#{k} ({kd.get(n, '?')}) found per version " + " ".join(f"{S(v)}:{len(f[v])}" for v in VERS))
                for v in VERS:
                    r = [r for r in T.REPS if r not in f[v]][0]
                    P.append(f"- {S(v)} r{r} {missed(v, r, m, n)}")
        fpc = {}
        for v in VERS:
            for r in T.REPS:
                left = Counter(ref[m])
                for x in listed[(v, r, m)]:
                    if left[x] > 0:
                        left[x] -= 1
                    else:
                        fpc.setdefault(x, Counter())[v] += 1
                        fp_total[v] += 1
        for x in sorted(fpc):
            c = fpc[x]
            if c["two_phase_v7"] >= 2 and c["two_phase_v8"] >= 2:
                kind = kd.get(x, "not in closed set")
                if kind == "port field":
                    kind = "bus record port field" if (par.get(x, (None, None))[1] or "").startswith(("bus_req", "bus_rsp")) else "other record port field"
                Q.append(f"\n- {'*' if m in the12 else ''}{m[8:]}:{x} ({kind}) listed per version " + " ".join(f"{S(v)}:{c[v]}" for v in VERS))
                for v in ("two_phase_v7", "two_phase_v8"):
                    r = [r for r in T.REPS if x in listed[(v, r, m)]][0]
                    Q.append(f"    {S(v)} r{r}: " + " || ".join(primary_rows(v, r, m, x)[:1]))
    (PACKS / "persistent_misses.md").write_text("\n".join(P) + "\n", encoding="utf-8")
    (PACKS / "persistent_fps.md").write_text("\n".join(Q) + "\n", encoding="utf-8")
    cvj = json.loads((HERE / "compare_versions.json").read_text(encoding="utf-8"))
    ok = all(tp_total[v] == cvj["versions"][S(v)]["held-out"]["TP"] and fp_total[v] == cvj["versions"][S(v)]["held-out"]["FP"] for v in VERS)
    print("self-test (pack TP and FP run totals = compare_versions.json, held-out):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    for p in sorted(PACKS.glob("*.md")) + sorted(DIFFS.glob("*.md")):
        print(f"  {p.relative_to(HERE)}: {len(p.read_text(encoding='utf-8')):,} chars")


if __name__ == "__main__":
    main()
