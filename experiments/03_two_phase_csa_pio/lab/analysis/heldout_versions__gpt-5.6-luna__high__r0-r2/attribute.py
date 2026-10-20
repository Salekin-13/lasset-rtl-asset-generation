"""Which prompt rules go with the change of TPs and FPs between versions (held-out and tuning modules; v1 -> v2 -> v4a
-> v5 -> v7 -> v8; gpt-5.6-luna, high, r0-r2). Read-only; writes attribute.json.

For each version pair A -> B:
  - lost find-runs: per reference occurrence found in fewer runs of B than of A, each run of B that misses it;
    gained find-runs the reverse (runs of A that miss it);
  - removed FP-runs: per false-positive name listed in fewer runs of B than of A, each run of B that does not list it;
    new FP-runs the reverse.
Each such run of B (or A for gains) is tagged with the Phase 1 rules its reply invokes for that element, read from:
  - the reply's own rows naming the element (Phase 2 secondary or Not Reported rows, Phase 1 Not Kept rows), and
  - Phase 1 Not Kept rows naming it (for a record field, also its field name when that has an underscore or digit), or
    citing one of its RTL occurrence lines while citing at most 30 lines; a row linked by lines only does not count for
    Clocks and resets or Build-time values (such rows cite the clocked lines of every register).
A rule counts when a linked text uses one of its key phrases (RULE_KEYS; approximate, a lower bound: a merged row
or a one-sentence Phase 2 justification usually names no rule) and the version's phase1.md has the rule's title.
"First in" = the first version folder (prompts/two_phase_v*, in build order) whose phase1.md has the title.
Self-test: hand-read cases (HAND) whose reply rows were read in this session; every one must get its rule.

  python attribute.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import transitions as T  # noqa: E402  (sets the paths; T.CH, T.C8, T.CV, T.K)

CH, C8, CV, K = T.CH, T.C8, T.CV, T.K
LAB = T.LAB
VERS = CV.VERS
BUILD_ORDER = ["two_phase_v1", "two_phase_v2", "two_phase_v2a", "two_phase_v3", "two_phase_v4", "two_phase_v4a", "two_phase_v5",
               "two_phase_v5f", "two_phase_v5g", "two_phase_v6", "two_phase_v6d", "two_phase_v7", "two_phase_v8"]
RULE_KEYS = {
    "Clocks and resets": ["clock/reset", "clock-and-reset", "clock and reset rule", "clock and reset exclusion", "clock/reset exclusion",
                          "clock rule", "reset rule", "reset-path", "excluded from conceptual assets", "excluded as conceptual assets"],
    "Clocks and resets (serial clock line)": ["serial link clock", "serial-link clock", "link's clock line", "clock line is"],
    "Build-time values": ["build-time", "build time"],
    "Pacing pulses": ["pacing"],
    "Forwarded transactions": ["forwarded", "forwarding rule"],
    "Second copies": ["second cop"],
    "Bus handshake copies": ["handshake cop", "handshake-cop", "bus-handshake", "bus handshake"],
    "Working values": ["working value", "partial result", "working copy"],
    "Slices": ["slice"],
    "Hand-offs": ["hand-off", "handoff"],
    "Instance-driven records": ["instance-driven", "driven whole"],
    "Register read-back": ["read-back rule", "register read-back", "readback rule"],
    "Port buffers": ["port-buffer", "port buffer", "fifo-buffer", "only buffers", "only buffer"],
    "Serial engines": ["serial engine", "serial-engine"],
    "Sequencing state": ["sequencing"],
    "Serial shift registers": ["serial shift", "shift-register rule", "shift register rule"],
    "Buffer and engine status bits": ["engine status", "engine-status", "buffer-status", "buffer status", "buffer and engine", "status-copy"],
    "Port options": ["port option", "port-option"],
    "Cached copies": ["cached cop", "cache rule", "cached-cop"],
    "Held addresses": ["held address", "held-address"],
    "Operation selectors": ["operation selector", "operation-selector", "selector rule"],
    "Access command fields": ["access-command", "access command", "command field", "command-field"],
    "Per-region checks": ["per-region"],
    "Arbitration bookkeeping": ["bookkeeping"],
    "Processor context fields": ["processor-context", "processor context"],
    "Precedence": ["precedence"],
    "Decided-on instance outputs": ["decided-on"],
    "Memory access address": ["memory access address", "memory-access address"],
    "Requests waiting for a grant": ["waiting for a grant", "waiting request"],
}
HAND = [  # (version, run, module, element, rule): reply rows read in this session (Not Kept reasons naming the rule)
    ("two_phase_v7", 2, "neorv32_cpu_counters", "cnt_en", "Pacing pulses"),
    ("two_phase_v7", 0, "neorv32_onewire", "ctrl.clear", "Port buffers"),
    ("two_phase_v7", 1, "neorv32_cpu_cp_shifter", "shifter.done_ff", "Sequencing state"),
    ("two_phase_v7", 0, "neorv32_cpu_cp_shifter", "shifter.done_ff", "Sequencing state"),
    ("two_phase_v7", 2, "neorv32_cpu_lsu", "wait_o", "Bus handshake copies"),
    ("two_phase_v7", 1, "neorv32_twd", "twd_scl_i", "Clocks and resets (serial clock line)"),
    ("two_phase_v2", 1, "neorv32_xbus", "xbus_dat_i", "Forwarded transactions"),
    ("two_phase_v7", 1, "neorv32_cpu_counters", "cnt_we", "Access command fields"),
    ("two_phase_v7", 0, "neorv32_cpu_regfile", "rf_we", "Access command fields"),
]
MAX_CITED = 30
LINE_LINK_SKIP = {"Clocks and resets", "Build-time values"}   # rows on clocks, resets or generics cite the clocked lines of
#                                                              every register: such a row links by name only


def titles(v):
    p = LAB / "prompts" / v / "phase1.md"
    return set(re.findall(r"^- ([A-Z][A-Za-z -]*)\.", p.read_text(encoding="utf-8"), re.M)) if p.exists() else set()


def first_in():
    out = {}
    for t in RULE_KEYS:
        for v in BUILD_ORDER:
            if t.split(" (")[0] in titles(v) and (" (" not in t or "clock line" in (LAB / "prompts" / v / "phase1.md").read_text(encoding="utf-8")):
                out[t] = v.replace("two_phase_", "")
                break
    return out


def cited_lines(text):
    out = set()
    segs = re.findall(r"\blines?\b([^.;]*)", text) + re.findall(r"\(([\d,\s\-–and]+)\)", text)
    for s in segs:
        for a, b in re.findall(r"(\d+)\s*(?:[-–]\s*(\d+))?", s):
            a = int(a)
            b = int(b) if b else a
            if 0 <= b - a <= 60:
                out |= set(range(a, b + 1))
    return out


def occ_lines(m, n):
    s = set()
    for (e, x), fx in CH.closed_names(m).items():
        if x == n:
            s |= set(fx.get("occurrence lines") or [])
    return s


_cache = {}


def not_kept_rows(v, r, m):
    k = (v, r, m)
    if k not in _cache:
        raw = K.parse_json(T.load(v, r, m, 1)["raw"])
        rows = raw.get("Not Kept") if isinstance(raw, dict) and "Not Kept" in raw else (T.load(v, r, m, 1)["reply"] or {}).get("considered, not kept")
        _cache[k] = [json.dumps(x, ensure_ascii=False) for x in rows or [] if isinstance(x, dict)]
    return _cache[k]


def tag(v, r, m, n, own_texts):
    """Rules the reply of (v, r, m) invokes for element n, and the texts that name them."""
    texts = [(t, True) for t in own_texts]
    lines = occ_lines(m, n)
    last = n.rsplit(".", 1)[-1]
    for row in not_kept_rows(v, r, m):
        c = cited_lines(row)
        named = T.has(n, row) or ("." in n and re.search(r"[_\d]", last) is not None and T.has(last, row))
        if named or (lines & c and len(c) <= MAX_CITED):
            texts.append((row, named))
    have = titles(v)
    rules = defaultdict(list)
    for t, named in texts:
        low = t.lower()
        for rule, keys in RULE_KEYS.items():
            base = rule.split(" (")[0]
            if base in have and any(k in low for k in keys) and (named or rule not in LINE_LINK_SKIP):
                rules[rule].append(t[:300])
    return dict(rules)


def own_texts(v, r, m, n, listed_names):
    st, why = T.where_lost(v, r, m, n, listed_names)
    return st, why


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, ref = CV.groups_and_ref()
    fv = first_in()
    listed = {}
    for s in ("tuning", "held-out"):
        for m in groups[s]:
            for v in VERS:
                for r in T.REPS:
                    listed[(v, r, m)] = [x["Asset RTL"] for x in json.loads((CH.run_dir(v, T.MODEL, r, T.EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]]
    # self-test
    ok = True
    for v, r, m, n, rule in HAND:
        st, why = own_texts(v, r, m, n, listed[(v, r, m)])
        got = tag(v, r, m, n, why)
        hit = rule in got
        ok &= hit
        print(f"  self-test {v[10:]} r{r} {m[8:]}:{n} -> {rule}: {'ok' if hit else 'MISSED'} (stage {st}; tagged {sorted(got)})")
    print("self-test (hand-read cases get their rule):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    out = {"rule first in": fv, "pairs": {}}
    for a, b in T.PAIRS:
        res = {}
        for s in ("tuning", "held-out"):
            agg = {k: Counter() for k in ("lost find-runs", "gained find-runs", "removed FP-runs", "new FP-runs")}
            elems = {k: defaultdict(set) for k in agg}
            tot = Counter()
            ex = defaultdict(list)
            for m in groups[s]:
                mm = m.replace("neorv32_", "")
                for want_v, other_v, kind in ((b, a, "lost find-runs"), (a, b, "gained find-runs")):
                    # occurrences found in fewer runs of want_v than of other_v; runs of want_v missing them
                    k = Counter()
                    for n in ref[m]:
                        k[n] += 1
                        f = {vv: sum(1 for r in T.REPS if Counter(listed[(vv, r, m)])[n] >= k[n]) for vv in (a, b)}
                        if f[want_v] >= f[other_v]:
                            continue
                        for r in T.REPS:
                            if Counter(listed[(want_v, r, m)])[n] >= k[n]:
                                continue
                            st, why = own_texts(want_v, r, m, n, listed[(want_v, r, m)])
                            rules = tag(want_v, r, m, n, why)
                            tot[kind] += 1
                            for rule in rules or {"(no rule named)": []}:
                                agg[kind][rule] += 1
                                elems[kind][rule].add(f"{mm}:{n}")
                                if len(ex[(kind, rule)]) < 3 and rules:
                                    ex[(kind, rule)].append(f"{want_v[10:]} r{r} {mm}:{n}: {rules[rule][0][:240]}")
                for want_v, other_v, kind in ((b, a, "removed FP-runs"), (a, b, "new FP-runs")):
                    # removed: FP names listed in fewer runs of b than a; runs of b not listing them (tag b's reply)
                    # new: FP names listed in more runs of b than a; runs of a not listing them (tag a's reply)
                    fps = Counter()
                    for vv in (a, b):
                        for r in T.REPS:
                            left = Counter(ref[m])
                            for x in listed[(vv, r, m)]:
                                if left[x] > 0:
                                    left[x] -= 1
                                else:
                                    fps[(vv, x)] += 1
                    names = {x for (_, x) in fps}
                    for x in names:
                        if fps[(want_v, x)] >= fps[(other_v, x)]:
                            continue
                        for r in T.REPS:
                            if x in listed[(want_v, r, m)]:
                                continue
                            st, why = own_texts(want_v, r, m, x, listed[(want_v, r, m)])
                            rules = tag(want_v, r, m, x, why)
                            tot[kind] += 1
                            for rule in rules or {"(no rule named)": []}:
                                agg[kind][rule] += 1
                                elems[kind][rule].add(f"{mm}:{x}")
                                if len(ex[(kind, rule)]) < 3 and rules:
                                    ex[(kind, rule)].append(f"{want_v[10:]} r{r} {mm}:{x}: {rules[rule][0][:240]}")
            res[s] = {k: {"total runs": tot[k], "by rule (runs; a run can name several)": dict(agg[k].most_common()),
                          "elements by rule": {r_: sorted(e) for r_, e in elems[k].items()}} for k in agg}
            res[s]["examples"] = {f"{k} | {r_}": v_ for (k, r_), v_ in ex.items()}
        out["pairs"][f"{a[10:]} -> {b[10:]}"] = res
    print("\nrule first in:", fv)
    for p, res in out["pairs"].items():
        print(f"\n===== {p}")
        for k in ("lost find-runs", "gained find-runs", "removed FP-runs", "new FP-runs"):
            for s in ("tuning", "held-out"):
                z = res[s][k]
                top = {r_: c for r_, c in z["by rule (runs; a run can name several)"].items() if r_ != "(no rule named)" and c >= 2}
                print(f"  {k:16s} {s:8s} total {z['total runs']:4d}; no rule named {z['by rule (runs; a run can name several)'].get('(no rule named)', 0):4d}; "
                      f"named: {top}")
    (HERE / "attribute.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nwritten attribute.json")


if __name__ == "__main__":
    main()
