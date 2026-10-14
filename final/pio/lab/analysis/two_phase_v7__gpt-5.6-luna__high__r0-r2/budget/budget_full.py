# Budget for the FULL-PROTECTION plan of the v7 failure analysis (estimates from past workflow run records).
# Run: python budget_full.py   (reads ~/.claude/projects/*/*/workflows/wf_*.json; no network, no writes)
# Per-role tokens and minutes are measured on past agents of the same role; agent counts are planning scenarios.
import json, glob, os, statistics as st
root = os.path.expanduser('~/.claude/projects')
wf = {}
for f in glob.glob(os.path.join(root, '*/*/workflows/wf_*.json')):
    try: d = json.load(open(f, encoding='utf-8'))
    except Exception: continue
    wf[d['runId']] = d
def ag(rid, phase=None):
    return [a for a in wf[rid]['workflowProgress'] if a['type'] == 'workflow_agent' and a.get('state') == 'done'
            and a.get('tokens') is not None and (phase is None or a.get('phaseTitle') == phase)]
# self-tests against figures hand-read from the run records this session
assert len(ag('wf_ce0308e1-806')) == 61 and wf['wf_ce0308e1-806']['totalTokens'] == 14993613
assert st.median(a['toolCalls'] for a in ag('wf_ce0308e1-806', 'Draft')) == 63
assert len(ag('wf_b1d6d6cc-c10')) == 30
print('self-tests passed')
def role(pairs):
    xs = [a for rid, ph in pairs for a in ag(rid, ph)]
    return dict(n=len(xs), tok=st.mean(a['tokens'] for a in xs), calls=st.median(a['toolCalls'] for a in xs),
                med=st.median(a['durationMs']/60000 for a in xs), mx=max(a['durationMs']/60000 for a in xs))
R = {
 'analyst':  role([('wf_6a4e92b2-c2b','Structural clusters'),('wf_6a4e92b2-c2b','Concept clusters'),
                   ('wf_be9f2b3f-beb','Structural clusters'),('wf_be9f2b3f-beb','Concept clusters')]),
 'skeptic':  role([('wf_ce0308e1-806','Challenge')]),
 'reviser':  role([('wf_ce0308e1-806','Revise')]),
 'drafter':  role([('wf_ce0308e1-806','Draft')]),
 'conflict': role([('wf_ce0308e1-806','Integrate')]),
 'blind':    role([('wf_b1d6d6cc-c10', None)]),
}
for k, v in R.items():
    print(f"{k:9s} n={v['n']:2d} calls median {v['calls']:5.1f}  tokens mean {v['tok']/1e3:4.0f}k  minutes median {v['med']:4.1f} max {v['mx']:4.1f}")
cm = ['wf_8c08ab5b-fa8','wf_60ff96f7-019','wf_31e339e0-945','wf_74edb89b-4cb','wf_ec4c65b4-268']
B_tok = (min(wf[r]['totalTokens'] for r in cm)/1e6, max(wf[r]['totalTokens'] for r in cm)/1e6)
B_min = max(wf[r]['durationMs'] for r in cm)/60000
E_tok = 30 * R['blind']['tok'] / 1e6
# critic costed as a skeptic; report writer as a reviser; report skeptic as a skeptic (assumptions)
def plan(G, P, F, recheck):
    sk, rv, an, dr = R['skeptic']['tok'], R['reviser']['tok'], R['analyst']['tok'], R['drafter']['tok']
    P = P + G   # each group's 'unexplained' list is checked like one more pattern
    c1 = G*an + G*sk + 2*P*sk + G*rv + (2*P*sk if recheck else 0)
    c2 = F*dr + 2*F*sk + F*rv + (2*F*sk if recheck else 0)
    n1 = G + G + 2*P + G + (2*P if recheck else 0); n2 = F + 2*F + F + (2*F if recheck else 0)
    df = R['conflict']['tok'] + rv + sk
    return 35 + n1 + n2 + 1 + 30 + 2, (c1 + c2 + df)/1e6
lo_n, lo_t = plan(8, 10, 6, False); hi_n, hi_t = plan(8, 17, 15, True)
lo_t += B_tok[0] + E_tok; hi_t += B_tok[1] + E_tok
print(f"agents {lo_n}-{hi_n}; tokens {lo_t:.0f}-{hi_t:.0f}M "
      f"(low: 8 groups, 10 patterns + 8 unexplained lists, 6 fixes, no re-check fires; high: 8 groups, 17 patterns + 8 lists, 15 fixes, every re-check fires)")
# time: barriers after C1 (merge) and after C2; chains in sequence; A, B2, D, F are estimates
A, B2, D, Fw, DEDUP = 25, 10, 25, 15, 5
c1 = lambda k: R['analyst'][k] + R['skeptic'][k] + R['reviser'][k] + R['skeptic'][k]   # analyst, critic||skeptics, revision, re-check
c2 = lambda k: R['drafter'][k] + R['skeptic'][k] + R['reviser'][k] + R['skeptic'][k]   # drafter, skeptics, revision, re-check
E_min = R['blind']['mx']
typ = A + B_min + B2 + c1('med') + DEDUP + c2('med') + D + E_min + Fw + R['skeptic']['med']
slow = A + B_min + B2 + c1('mx') + DEDUP + c2('mx') + D + E_min + Fw + R['skeptic']['mx']
print(f"C1 chain {c1('med'):.0f}/{c1('mx'):.0f} min, C2 chain {c2('med'):.0f}/{c2('mx'):.0f} min (typical/slowest agents)")
print(f"total {typ:.0f} min ({typ/60:.1f} h) with typical agents, {slow:.0f} min ({slow/60:.1f} h) with the slowest")
# usage: two anchors. This week's sum ends at the 40% reading (2026-10-13 13:50 UTC) so later workflows do not move it.
r5_mab, rw_mab = 26/14.6, 7/14.6
wk = sum(d.get('totalTokens') or 0 for d in wf.values() if '2026-10-09T21:00' <= (d.get('timestamp') or '') <= '2026-10-13T13:50')/1e6
rw_wk = 40/wk; r5_wk = r5_mab * rw_wk / rw_mab
print(f"this week: {wk:.0f}M workflow tokens to the 40% reading -> {rw_wk:.3f} weekly pts/M (upper bound); ratio to 2026-10-10: {rw_mab/rw_wk:.1f}x")
print(f"weekly: {lo_t*rw_wk:.0f}-{hi_t*rw_wk:.0f} pts (this-week rate) / {lo_t*rw_mab:.0f}-{hi_t*rw_mab:.0f} pts (2026-10-10 rate)")
print(f"5-hour: {lo_t*r5_wk:.0f}-{hi_t*r5_wk:.0f} pts (scaled, assumption) / {lo_t*r5_mab:.0f}-{hi_t*r5_mab:.0f} pts (2026-10-10 direct rate), spread over the run's windows")
print(f"each extra fix adds {(R['drafter']['tok']+4*R['skeptic']['tok']+R['reviser']['tok'])/1e6:.2f}M tokens with re-check, 6 agents")
