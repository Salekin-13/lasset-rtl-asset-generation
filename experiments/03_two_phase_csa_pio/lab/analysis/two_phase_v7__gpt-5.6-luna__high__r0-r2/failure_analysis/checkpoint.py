"""Usage checkpoints of the v7 failure analysis (RUN BUDGET section of the task).

Tokens still to come = the high end of budget_full.py (8 groups, 17 patterns + 8 unexplained lists, 15 fixes, every
re-check fires) for the stages not yet run. budget_full.py is executed as it is (its own self-tests run) and its
per-role means are reused; nothing is re-estimated here.

  python checkpoint.py <stage> <points_5h_before> <points_5h_now> <points_wk_before> <points_wk_now> <tokens_measured> [done stages...]
Stages: B, C1, C2, D, E, F.
"""
import io
import contextlib
import sys
from pathlib import Path

BF = Path(__file__).resolve().parent.parent / "budget" / "budget_full.py"
ANCHOR_WK, ANCHOR_5H = 0.48, 1.78          # map A/B 2026-10-10: points per million tokens (the higher anchor)


def budget():
    g = {"__name__": "budget_full"}
    with contextlib.redirect_stdout(io.StringIO()) as out:
        exec(compile(BF.read_text(encoding="utf-8"), str(BF), "exec"), g)
    R, B_tok, E_tok = g["R"], g["B_tok"], g["E_tok"]
    sk, rv, an, dr = R["skeptic"]["tok"], R["reviser"]["tok"], R["analyst"]["tok"], R["drafter"]["tok"]
    G, P, Fx = 8, 17 + 8, 15
    hi = {"B": B_tok[1] * 1e6,
          "C1": G * an + G * sk + 2 * P * sk + G * rv + 2 * P * sk,
          "C2": Fx * dr + 2 * Fx * sk + Fx * rv + 2 * Fx * sk,
          "D": R["conflict"]["tok"],
          "E": E_tok * 1e6,
          "F": rv + sk}
    return hi, out.getvalue()


def main():
    stage = sys.argv[1]
    p5a, p5b, pwa, pwb, tok = map(float, sys.argv[2:7])
    done = set(sys.argv[7:]) | {stage}
    hi, txt = budget()
    assert "self-tests passed" in txt, "budget_full.py self-test failed"
    total_hi = sum(hi.values())
    print(f"budget_full.py high end by stage (M tokens): " + ", ".join(f"{k} {v / 1e6:.1f}" for k, v in hi.items()) + f"; total {total_hi / 1e6:.1f}")
    d5, dw = p5b - p5a, pwb - pwa
    r5 = d5 / (tok / 1e6) if d5 >= 3 else ANCHOR_5H
    rw = dw / (tok / 1e6) if dw >= 3 else ANCHOR_WK
    print(f"measured: 5-hour moved {d5:+.0f} points, weekly {dw:+.0f} points over {tok / 1e6:.2f}M tokens")
    print(f"rate 5-hour {r5:.2f} pts/M ({'measured' if d5 >= 3 else 'below the meter resolution: higher anchor 1.78'}); "
          f"weekly {rw:.2f} pts/M ({'measured' if dw >= 3 else 'below the meter resolution: higher anchor 0.48'})")
    left = sum(v for k, v in hi.items() if k not in done) / 1e6
    print(f"tokens still to come (high end, stages not run: {', '.join(k for k in hi if k not in done)}): {left:.1f}M")
    print(f"projection 5-hour: {p5b:.0f} + {r5:.2f} x {left:.1f} = {p5b + r5 * left:.1f}% (stop line 90%)")
    print(f"projection weekly: {pwb:.0f} + {rw:.2f} x {left:.1f} = {pwb + rw * left:.1f}% (stop line 70%)")


if __name__ == "__main__":
    main()
