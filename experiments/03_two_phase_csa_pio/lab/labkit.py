"""The lab kit's bridge to the rest of the project: everything chain.py, check_lab_prompt.py and cost_estimate.py need
besides the prompt files, the built inputs and two shared modules (src/eval_assets.py, assetgen_meta/meta_tools.py).
It does not import the graph code, so the kit (experiments/03_two_phase_csa_pio/lab/ plus pio_pilot.ipynb) runs in any checkout that has
src/, assetgen_meta/ and data/. Facts that come from the graph code are read from kit_data/<input version>.json
(build_kit_data.py, worktree only), which is refused if the inputs changed since it was built.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[2]
for p in (LAB, ROOT / "src", ROOT / "assetgen_meta", ROOT / "bahavioral_patterns_of_assets"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import os  # noqa: E402

# The built inputs to use: v1 (default) or another folder under lab/inputs/ with its own kit_data/<version>.json, e.g.
# v1k (v1 with an exact diagram key line). Set the environment variable PIO_INPUT_VERSION before importing labkit and
# chain (the notebook's cell 1 does this). Runs go to runs/<prompt version>__<input version>/, so inputs never mix.
INPUT_VERSION = os.environ.get("PIO_INPUT_VERSION", "v1")
INPUTS = LAB / "inputs" / INPUT_VERSION
if not (INPUTS / "manifest.json").exists():
    raise RuntimeError(f"no built inputs at {INPUTS} (PIO_INPUT_VERSION={INPUT_VERSION!r})")
_DATA = None


def data() -> dict:
    global _DATA
    if _DATA is None:
        d = json.loads((LAB / "kit_data" / f"{INPUT_VERSION}.json").read_text(encoding="utf-8"))
        man = (INPUTS / "manifest.json").read_text(encoding="utf-8")
        if hashlib.sha256(man.encode()).hexdigest()[:12] != d["inputs manifest sha"]:
            raise RuntimeError("kit_data was built for other inputs; rebuild it with build_kit_data.py")
        _DATA = d
    return _DATA


def gt_modules() -> dict:
    """{"tuning": [...], "heldout": [...]}: the modules with reference entries (15 + 26)."""
    return {"tuning": list(data()["tuning modules"]), "heldout": list(data()["heldout modules"])}


def corpus_names() -> set[str]:
    """The names no prompt may contain: those of the reference, the parsed closed sets and the module names."""
    import meta_tools as mt
    names = set(data()["corpus names"]) | mt.corpus_names(str(ROOT))
    return {n for n in names if n and len(n) >= 4 and ("_" in n or "." in n)}


def unit_entities(m: str) -> dict[str, set[str]]:
    return {u: set(es) for u, es in data()["modules"][m]["unit entities"].items()}


def top_level_port_fields(m: str) -> dict[str, str]:
    """'entity:field' -> port, for the fields of each top-level record port."""
    return dict(data()["modules"][m]["top-level port fields"])


def collapse_port_fields(run_dir) -> dict:
    """Evaluation-layer row only (a reference convention, not a method rule): fields of a top-level record port are
    reported as the whole port, once. Same rule as pio_run.collapse_port_fields."""
    out = {}
    for f in sorted(Path(run_dir).glob("*.json")):
        if f.name.startswith("_"):
            continue
        m = f.stem
        pf = top_level_port_fields(m)
        seen, rows = set(), []
        for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]:
            name = pf.get(f"{x['Entity']}:{x['Asset RTL']}", x["Asset RTL"])
            if (x["Entity"], name) not in seen:
                seen.add((x["Entity"], name))
                rows.append((x["Entity"], name, x["Security Objective"]))
        out[m] = rows
    return out


def parse_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n|\n```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


def sha12(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


class NeedReply(Exception):
    """file_call has saved a request that has no reply yet."""


def file_call(reply_dir):
    """An executor that is a person or an agent: f(system, user) returns the reply stored at <reply_dir>/<key>.json,
    where key = sha12(system + "\\n\\n" + user). If it is missing, the request is saved as <key>.system.md /
    <key>.user.txt and NeedReply is raised; write the reply file and run again."""
    reply_dir = Path(reply_dir)
    reply_dir.mkdir(parents=True, exist_ok=True)

    def f(system, user):
        key = sha12(system + "\n\n" + user)
        r = reply_dir / f"{key}.json"
        if r.exists():
            return r.read_text(encoding="utf-8"), {"executor": "file", "key": key}
        (reply_dir / f"{key}.system.md").write_text(system, encoding="utf-8")
        (reply_dir / f"{key}.user.txt").write_text(user, encoding="utf-8")
        raise NeedReply(key)
    return f
