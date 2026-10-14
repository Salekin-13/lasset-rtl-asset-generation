"""Code check of the drafted negative constraints (mechanical versions only), independent of the agent judges.

1. On this run's listed rows: which FPs and TPs each rule's mechanical test removes, and the score if the stored
   output were filtered (post hoc, a filter on stored replies, not a prompt re-run).
2. Reference exposure: every reference entry of the 15 tuning and 26 held-out modules is tested as if it were listed;
   a rule that hits a reference entry would hide a TP whenever the model finds that entry.
Self-test first, on hand-read rows.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402

TX = {"bus_req_t", "bus_rsp_t", "dmi_req_t", "dmi_rsp_t", "icc_t", "if_bus_t"}   # transaction records (code only)
REQ_OUT = {"bus_req_t", "dmi_req_t"}
DECIDE_ONLY = {"condition", "selector", "index", "read"}


def facts(m):
    """(entity, name) -> features; plus per-entity port record types by direction and output port names."""
    cs = json.loads(CH.inputs(m)["closed_set.json"])
    units = set(CH.diagram_names(m))
    f, ent_ports = {}, {}
    for e in cs["entity list"]:
        ent = e["entity name"]
        ports = [(p.get("direction"), p.get("record type"), p["port"]) for p in e["port list"]]
        ent_ports[ent] = ports
        for lst, kind in (("port list", "port"), ("signal list", "signal")):
            for x in e[lst]:
                name = x.get(kind)
                top = kind == "port" and ent in units
                base = {"entity": ent, "name": name, "record type": x.get("record type"), "tags": set(x.get("role in RTL", [])),
                        "lines": set(x.get("occurrence lines", [])), "direction": x.get("direction"), "type": x.get("type")}
                f[(ent, name)] = {**base, "kind": ("top-level port" if top else "child port") if kind == "port" else "signal",
                                  "whole record": "fields" in x}
                for fl in x.get("fields", []):
                    f[(ent, fl["field"])] = {"entity": ent, "name": fl["field"], "record type": x.get("record type"),
                                             "tags": set(fl.get("role in RTL", [])), "lines": set(fl.get("occurrence lines", [])),
                                             "direction": fl.get("direction"), "type": fl.get("type"),
                                             "kind": ("top-level port field" if top else "child port field") if kind == "port" else "signal field",
                                             "whole record": False, "record tags": base["tags"], "record lines": base["lines"]}
    return f, ent_ports


def tests(x, ent_ports, listed_names):
    """Rule id -> True when the rule's mechanical test removes element x."""
    ports = ent_ports.get(x["entity"], [])
    forwards = any(d == "out" and rt in REQ_OUT for d, rt, _ in ports)
    ends_bus = any(d == "in" and rt == "bus_req_t" for d, rt, _ in ports) and not any(d == "out" and rt == "bus_req_t" for d, rt, _ in ports)
    field = x["name"].split(".", 1)[1] if "." in x["name"] else ""
    pf = x["kind"] == "top-level port field"
    t = {}
    t["NC-B01"] = x["whole record"] and x["record type"] in TX
    t["NC-B02"] = pf and (x["tags"] <= DECIDE_ONLY or (x["direction"] == "out" and "set to constants only" in x["tags"])
                          or (x["record type"] in TX and field == "stb" and "copied" not in x["tags"]))
    t["NC-B03"] = pf and x["record type"] in TX and forwards and not t["NC-B02"]
    t["NC-B15"] = pf and x["record type"] in {"bus_req_t", "bus_rsp_t"} and ends_bus and not t["NC-B02"]
    t["NC-B04"] = "_nxt" in x["name"] and x["name"].replace("_nxt", "") in listed_names
    t["NC-B05"] = "fifo" in (x["record type"] or "") and "data" in field
    t["NC-B07"] = (x["kind"] == "signal field" and "set by an instance" in x.get("record tags", set())
                   and bool(x["lines"]) and x["lines"] <= x.get("record lines", set()))
    t["E-B06"] = x["kind"] == "signal field" and x["type"] == "reg" and field.startswith("irq_")
    outs = [n for d, _, n in ports if d == "out"]
    t["E-B09"] = bool(outs) and all("rst" in n for n in outs)
    return t


PROMPT_RULES = ["NC-B01", "NC-B02", "NC-B03", "NC-B15", "NC-B04", "NC-B05", "NC-B07"]
EVAL_RULES = ["E-B06", "E-B09"]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import eval_assets as ea
    t = json.loads((HERE / "table.json").read_text(encoding="utf-8"))
    cache = {}

    def F(m):
        if m not in cache:
            cache[m] = facts(m)
        return cache[m]
    # self-test on hand-read rows
    def hit(m, ent, name, listed=()):
        f, ep = F(m)
        return {k for k, v in tests(f[(ent, name)], ep, set(listed)).items() if v}
    w, b, c = "neorv32_wdt", "neorv32_bus", "neorv32_cpu"
    st = [("wdt bus_req_i.data (shared write word of a bus-ending unit) -> NC-B15", "NC-B15" in hit(w, w, "bus_req_i.data")),
          ("wdt ctrl.enable (a setting register) -> no rule", hit(w, w, "ctrl.enable") == set()),
          ("bus switch a_req_i (whole request record port) -> NC-B01", "NC-B01" in hit(b, "neorv32_bus_switch", "a_req_i")),
          ("cpu ctrl.cpu_priv (field of an instance-set record, no line of its own) -> NC-B07", "NC-B07" in hit(c, c, "ctrl.cpu_priv")),
          ("cpu ctrl.pc_ret (has a line of its own, 330) -> not NC-B07", "NC-B07" not in hit(c, c, "ctrl.pc_ret"))]
    ok = all(v for _, v in st)
    for lab, v in st:
        print(f"   {'ok  ' if v else 'FAIL'} {lab}")
    if not ok:
        sys.exit("self-test failed")
    # 1. this run's rows
    listed = defaultdict(set)
    for r in t["rows"]:
        listed[(r["module"], r["entity"])].add(r["element"])
    removed = defaultdict(lambda: {"FP": set(), "TP": set()})
    for r in t["rows"]:
        f, ep = F(r["module"])
        x = f.get((r["entity"], r["element"]))
        if x is None:
            continue
        for k, v in tests(x, ep, listed[(r["module"], r["entity"])]).items():
            if v:
                removed[k][r["verdict"]].add(r["id"])
    fp_n = sum(r["verdict"] == "FP" for r in t["rows"]); tp_n = sum(r["verdict"] == "TP" for r in t["rows"])
    print(f"\n1. this run ({tp_n} TP, {fp_n} FP): rows each mechanical test removes")
    for k in PROMPT_RULES + EVAL_RULES:
        print(f"   {k:7s} FP {len(removed[k]['FP']):3d}   TP {len(removed[k]['TP']):2d} {sorted(removed[k]['TP'])}")
    def score_without(rule_set):
        drop = set().union(*(removed[k]["FP"] | removed[k]["TP"] for k in rule_set))
        run = defaultdict(list)
        for r in t["rows"]:
            if r["id"] not in drop:
                run[r["module"]].append((r["entity"], r["element"], r["objective listed"]))
        with CH.at_root():
            s = ea.score(dict(run), ea.load_refs()["gt"], strict=True, only=set(K.gt_modules()["tuning"]))
        return s, len(drop)
    for lab, rs in (("prompt rules", PROMPT_RULES), ("prompt rules + evaluation-layer filters", PROMPT_RULES + EVAL_RULES)):
        s, n = score_without(rs)
        print(f"   post hoc, stored output filtered by {lab}: {n} rows removed -> P {s['precision']:.3f} R {s['recall']:.3f} "
              f"({s['tp']}/{s['ref']}, {s['emit']} listed)")
    # 2. reference exposure
    print("\n2. reference entries each test would remove if the model listed them")
    with CH.at_root():
        refs = ea.load_refs()["gt"]
    g = K.gt_modules()
    for split in ("tuning", "heldout"):
        hits, n, unresolved = Counter(), 0, 0
        detail = defaultdict(list)
        for m in g[split]:
            f, ep = F(m)
            names_all = {(e, nm) for (e, nm) in f}
            for rname, _ in refs.get(m, []):
                n += 1
                cands = [f[k] for k in f if k[1] == rname]
                if not cands:
                    unresolved += 1
                    continue
                for k in PROMPT_RULES + EVAL_RULES:
                    if any(tests(x, ep, {nm for (e, nm) in names_all if e == x["entity"]})[k] for x in cands):
                        hits[k] += 1
                        detail[k].append(f"{m}:{rname}")
        print(f"   {split}: {n} entries ({unresolved} not in the closed sets)")
        for k in PROMPT_RULES + EVAL_RULES:
            print(f"     {k:7s} {hits[k]:2d} {detail[k][:6]}")


if __name__ == "__main__":
    main()
