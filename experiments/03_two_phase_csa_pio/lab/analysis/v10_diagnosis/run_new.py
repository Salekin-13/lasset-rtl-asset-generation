"""Rule-alone test of the new blind-spot rules on luna (variant v11n; round 2 v11n2): every wording, all 41 modules,
repeats 0-1, v10's context, old reply format, max_tokens 64,000 (as the other v10 rule-alone runs).

  python -B run_new.py preview <variant> [all|P2|P1]   gates + cost estimate (sends nothing)
  <conda python> run_new.py send <variant> [all|P2|P1] sends, if spent + estimate stays within CAP
  (decision D15: P2 = every Phase 2 wording on the 41; P1 = Phase 1 wordings where the Phase 2 wording decided something)

Estimate: isolation.preview's input tokens, and output at the measured mean of the v10u run (the closest earlier rules:
narrow, mostly "applies: no"), with the v10r mean per request as the upper figure.
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import run_a  # noqa: E402

CAP = 20.5


def mean_cost(run):
    root = LAB / "runs" / run / f"{MODEL}__{EFFORT}"
    cs = [run_a.usd(json.loads(f.read_text(encoding="utf-8"))["usage"]) for f in root.glob("r*/P*/*/*.json")]
    return sum(cs) / len(cs)


def applied_modules(variant, rid):
    """Modules where the rule's Phase 2 wording decided something (barred or spared) in either repeat."""
    out = set()
    for rep in (0, 1):
        for f in (ISO.run_root(rep=rep) / "P2" / rid).glob("*.json"):
            rp = json.loads(f.read_text(encoding="utf-8")).get("reply") or {}
            if (rp.get("barred") or rp.get("spared")):
                out.add(f.stem)
    return out


def jobs(variant, part="all"):
    """part: "all" (both wordings, 41 modules), "P2" (Phase 2 wordings, 41 modules), "P1" (Phase 1 wordings on the
    modules where the same rule's Phase 2 wording decided something; a rule with no Phase 2 wording: all 41)."""
    ISO.use(variant)
    if part == "all":
        return ISO.jobs(None, reps=(0, 1))
    if part == "P2":
        return ISO.jobs(None, reps=(0, 1), phases=("P2",))
    jl, tx = ISO.jobs(None, reps=(0, 1), phases=("P1",))
    keep = []
    for j in jl:
        if tx[j[0]].get("P2"):
            if j[2] in applied_modules(variant, j[0]):
                keep.append(j)
        else:
            keep.append(j)
    return keep, tx


def preview(variant, part="all"):
    ISO.use(variant)
    if not ISO.selftest(log=print):
        sys.exit("self-test failed")
    jl, tx = jobs(variant, part)
    left = [j for j in jl if not ISO.path(*j, MODEL, EFFORT).exists()]
    first = LAB / "runs" / "rule_isolation_v11n" / f"{MODEL}__{EFFORT}"
    base = "rule_isolation_v11n" if variant != "v11n" and any(first.glob("r*/P*/*/*.json")) else "rule_isolation_v10u"
    lo, hi = mean_cost(base) * len(left), mean_cost("rule_isolation_v10r") * len(left)   # D23: the same rules' own first round
    spent = run_a.spent(log=lambda *a: None)
    print(f"{variant}: {len(jl)} requests, {len(left)} to send; estimate USD {lo:.2f} ({base} mean) to {hi:.2f} (v10r mean); "
          f"spent so far USD {spent:.2f}; cap {CAP}")
    ISO.use("v9")
    return len(left), lo, hi, spent


def send(variant, part="all"):
    n, lo, hi, spent = preview(variant, part)
    if spent + lo > CAP:
        sys.exit(f"over the cap: {spent:.2f} + {lo:.2f} > {CAP}; nothing sent")
    ex = json.loads((HERE / "spent_extra_folders.json").read_text(encoding="utf-8")) if (HERE / "spent_extra_folders.json").exists() else []
    p = str(LAB / "runs" / ISO.VARIANTS[variant]["run"] / f"{MODEL}__{EFFORT}")
    if p not in ex:
        ex.append(p)
        (HERE / "spent_extra_folders.json").write_text(json.dumps(ex, indent=1), encoding="utf-8")
    jl, tx = jobs(variant, part)
    ISO.run(jl, tx, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5, max_tokens=64000), MODEL, EFFORT, workers=32)
    ISO.measured(jl, MODEL, EFFORT)
    ISO.use("v9")
    print(f"spent after: USD {run_a.spent(log=lambda *a: None):.2f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"preview": preview, "send": send}[sys.argv[1]](*sys.argv[2:4])
