"""Shared set-up for the v10 diagnosis scripts: paths, and the rule-alone variants this study adds to isolation.py at
run time (isolation.py itself is not edited).

Variants (rule-alone format of isolation.py, old reply format, luna run folders under lab/runs/):
  v10e1  already in isolation.py: the E1 status-bits text (rule_texts_v10e1.json) in v10's context (merged procedure).
         Run here on luna for the first time (it ran only on Claude before).
  v10u   the two v10 wordings no rule-alone test read (verify_v10_rules.py): Phase 1 "Held outcomes, addresses and
         settings" (id P1-HO) and the Phase 2 wording of "Requests waiting for a grant" (id P1-26, Phase 2 only).
         Contexts: v10's (context_p1_v10m.md / context_p2_v10m.md) with the wording under test removed, so the rule
         is not also in the background. Built by make_v10u_texts.py.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
ROOT = LAB.parents[2]
ISOD = LAB / "analysis" / "rule_isolation_v9"
for p in (LAB, ISOD):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import isolation as ISO  # noqa: E402

MODEL, EFFORT = "gpt-5.6-luna", "high"
V10 = "two_phase_v10"


def register():
    """Add the study's variants to isolation.VARIANTS (absolute paths: isolation joins HERE / path, and an absolute
    path wins). Idempotent."""
    ISO.VARIANTS["v10u"] = {"run": "rule_isolation_v10u", "texts": str(HERE / "rule_texts_v10u.json"),
                            "ctx": (str(HERE / "context_p1_v10u.md"), str(HERE / "context_p2_v10u.md"))}
    # v11n: the new blind-spot rules (new_rules/), tested alone in v10's context (the E1 test's context, merged procedure)
    ISO.VARIANTS["v11n"] = {"run": "rule_isolation_v11n", "texts": str(HERE / "new_rules" / "rule_texts_v11n.json"),
                            "ctx": (str(ISO.HERE / "context_p1_v10m.md"), str(ISO.HERE / "context_p2_v10m.md"))}
    ISO.VARIANTS["v11n2"] = {"run": "rule_isolation_v11n2", "texts": str(HERE / "new_rules" / "rule_texts_v11n2.json"),
                             "ctx": (str(ISO.HERE / "context_p1_v10m.md"), str(ISO.HERE / "context_p2_v10m.md"))}
    ISO.VARIANTS["v11n3"] = {"run": "rule_isolation_v11n3", "texts": str(HERE / "new_rules" / "rule_texts_v11n3.json"),
                             "ctx": (str(ISO.HERE / "context_p1_v10m.md"), str(ISO.HERE / "context_p2_v10m.md"))}
    # v11p: the Phase 1 fix drafts (P1_FIX_DRAFTS.md): Forwarded transactions as drafted, Build-time values trimmed
    ISO.VARIANTS["v11p"] = {"run": "rule_isolation_v11p", "texts": str(HERE / "new_rules" / "rule_texts_v11p.json"),
                            "ctx": (str(ISO.HERE / "context_p1_v10m.md"), str(ISO.HERE / "context_p2_v10m.md"))}
    return ISO
