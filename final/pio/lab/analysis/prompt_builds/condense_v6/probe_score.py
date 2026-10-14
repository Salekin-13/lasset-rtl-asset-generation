"""Score the debug_dtm tap_reg.dmi probe (workflow wf_8205f6b6-468; result saved as probe_judges.json).

Two arms, two blind judges each, debug_dtm only, the same judge prompt as the v6abc test:
  control_v6     v6's own text (prompts/two_phase_v6), diff in the v6abc format (no draft rule ids)
  probe_v6abc_p  v6abc with one Phase 1 sentence back in v6's wording ("name its information under the piece of the
                 register it copies" instead of "under the copied register's piece")
Each arm's two judges replace the debug_dtm judges of a full 30-judge set (control: judges_v6.json; probe:
judges_v6abc.json), the set is scored by score_v6.py, and the debug_dtm false positives added are printed next to
v6's own test. Writes probe_<arm>_judges.json and probe_<arm>_result.json.

  python probe_score.py [probe_judges.json] [out_dir]

Self-test (python probe_score.py --selftest): feeding each base set's own debug_dtm judges back in must reproduce
that set's own debug_dtm lists (v6: none added; v6abc: tap_reg.dmi in r1 and r2).
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BND = HERE.parents[1] / "two_phase_v5g__gpt-5.6-luna__high__r0-r2" / "boundary"
BASE = {"control_v6": BND / "judges_v6.json", "probe_v6abc_p": HERE / "judges_v6abc.json",
        "control2_v6": BND / "judges_v6.json"}
# control2_v6 (wf_62445470-54d): v6's text, but its Second-copies change is shown inside the unchanged neighbour
# sentences of phase2.md (the "Judged as usual" lists), as the v6abc diff shows it. Inputs: probe/.


def dtm(result, mode, lst):
    return sorted(x for x in result[mode][lst] if "debug_dtm:" in x)


def main(P, out):
    sys.stdout.reconfigure(encoding="utf-8")
    v6 = json.loads((BND / "boundary_result_v6.json").read_text(encoding="utf-8"))
    for arm, base in BASE.items():
        new = {r["judge"]: {k: v for k, v in r.items() if k != "arm"} for r in P if r["arm"] == arm}
        if not new:
            continue
        assert sorted(new) == [1, 2], (arm, sorted(new))
        J = json.loads(base.read_text(encoding="utf-8"))
        J2 = [new[j["judge"]] if j["module"] == "debug_dtm" else j for j in J]
        assert len(J2) == 30 and sum(j["module"] == "debug_dtm" for j in J2) == 2
        jp, rp = out / f"probe_{arm}_judges.json", out / f"probe_{arm}_result.json"
        jp.write_text(json.dumps(J2, indent=1, ensure_ascii=False), encoding="utf-8")
        subprocess.run([sys.executable, str(BND / "score_v6.py"), str(jp), str(rp)], check=True, capture_output=True)
        R = json.loads(rp.read_text(encoding="utf-8"))
        for mode in ("both", "either"):
            for lst in ("false positives added", "correct lost", "correct gained"):
                print(f"{arm} {mode:6s} {lst}: debug_dtm {dtm(R, mode, lst)} | v6's own test {dtm(v6, mode, lst)}")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        import tempfile
        own = [dict(j, arm=arm) for arm, base in BASE.items()
               for j in json.loads(base.read_text(encoding="utf-8")) if j["module"] == "debug_dtm"]
        main(own, Path(tempfile.mkdtemp()))
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        main(json.loads(Path(args[0] if args else HERE / "probe_judges.json").read_text(encoding="utf-8")),
             Path(args[1]) if len(args) > 1 else HERE)
