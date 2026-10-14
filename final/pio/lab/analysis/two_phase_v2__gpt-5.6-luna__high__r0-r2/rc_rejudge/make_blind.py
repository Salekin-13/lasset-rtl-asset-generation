"""Blind six-run views for re-judging reference concepts across two_phase_v1 and two_phase_v2 (gpt-5.6-luna, r0-r2).

For each module, the three v1 runs and the three v2 runs are relabelled A-F in a fixed shuffled order (sha1 of module and run),
with no version named. The key goes to _key.json, which the judges are told not to open.
Self-test: every concept heading and not-kept line of the six source sections appears once in the blind view, relabelled.

  python make_blind.py bus trng ...
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
V1 = V2.parent / "two_phase_v1__gpt-5.6-luna__high__r0-r2"
LETTERS = "ABCDEF"


def sections(path):
    t = path.read_text(encoding="utf-8")
    parts = re.split(r"^## Run (r[012])\b.*$", t, flags=re.M)
    return {parts[i]: parts[i + 1].strip("\n") for i in range(1, len(parts), 2)}


def main(mods):
    out = HERE / "views"
    out.mkdir(exist_ok=True)
    key = json.loads((HERE / "_key.json").read_text(encoding="utf-8")) if (HERE / "_key.json").exists() else {}
    for s in mods:
        src = {("v1", k): body for k, body in sections(V1 / "views" / f"runs_{s}.md").items()}
        src.update({("v2", k): body for k, body in sections(V2 / "views" / f"runs_{s}.md").items()})
        assert len(src) == 6, (s, sorted(src))
        order = sorted(src, key=lambda vk: hashlib.sha1(f"{s}|{vk[0]}|{vk[1]}".encode()).hexdigest())
        lab = {vk: LETTERS[i] for i, vk in enumerate(order)}
        L = [f"# Six runs on neorv32_{s} (labels A-F; judge each run on its own)", ""]
        for vk in order:
            body = re.sub(rf"\b{vk[1]}:", f"{lab[vk]}:", src[vk])
            L += [f"## Run {lab[vk]}", "", body, ""]
        text = "\n".join(L)
        # self-test: each source heading and bullet line appears relabelled exactly as often as in its source
        for vk, body in src.items():
            for line in body.splitlines():
                if line.startswith("### ") or line.startswith("- "):
                    want = re.sub(rf"\b{vk[1]}:", f"{lab[vk]}:", line)
                    assert want in text, (s, vk, line[:80])
            assert not re.search(r"\br[012]:", text), (s, "unrelabelled run id")
        assert "two_phase_v" not in text and "same prompt" not in text, s
        (out / f"{s}.md").write_text(text, encoding="utf-8")
        key[s] = {lab[vk]: f"{vk[0]} {vk[1]}" for vk in order}
        print(s, key[s])
    (HERE / "_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
