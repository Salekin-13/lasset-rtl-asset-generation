# Budget estimate for the v7 failure analysis, from measured past workflows (read from their run records).
import json, glob, os
root = os.path.expanduser('~/.claude/projects')
wf = {}
for f in glob.glob(os.path.join(root, '*/*/workflows/wf_*.json')):
    try: d = json.load(open(f, encoding='utf-8'))
    except Exception: continue
    wf[d['runId']] = d
stages = {  # stage -> past workflows of the same kind
 'B concept judges': ['wf_8c08ab5b-fa8','wf_60ff96f7-019','wf_31e339e0-945','wf_74edb89b-4cb','wf_ec4c65b4-268'],
 'C analysis (steps 2-4)': ['wf_be9f2b3f-beb','wf_6a4e92b2-c2b'],
 'D fixes (draft, 2 skeptics, revise)': ['wf_9c7700ae-02e','wf_155b9394-6bb','wf_ce0308e1-806'],
 'E blind check': ['wf_859ba8d0-07c','wf_b1d6d6cc-c10','wf_c35177e8-849'],
}
# self-test: two figures hand-read from the run records earlier in this turn
assert wf['wf_ce0308e1-806']['agentCount'] == 61 and wf['wf_ce0308e1-806']['totalTokens'] == 14993613
assert round(wf['wf_318b1752-7e8']['durationMs']/60000, 1) == 29.0
print('self-test passed')
lo_t = hi_t = lo_m = hi_m = 0
for s, ids in stages.items():
    toks = [wf[i]['totalTokens']/1e6 for i in ids]; mins = [wf[i]['durationMs']/60000 for i in ids]
    ags = [wf[i]['agentCount'] for i in ids]
    print(f"{s:38s} n={len(ids)} agents {min(ags)}-{max(ags)}  tokens {min(toks):.1f}-{max(toks):.1f}M  minutes {min(mins):.0f}-{max(mins):.0f}")
    lo_t += min(toks); hi_t += max(toks); lo_m += min(mins); hi_m += max(mins)
print(f"SUM workflow stages: tokens {lo_t:.1f}-{hi_t:.1f}M; minutes {lo_m:.0f}-{hi_m:.0f} (plus stage A code and the orchestrator's own turns)")
# usage anchors
# 1) map A/B 2026-10-10 (usage read before/after in session 780689ab): 63 agents, 14.6M tokens, 5h 2->28, weekly 3->10
mab_tok = 14.6; r5_mab = (28-2)/mab_tok; rw_mab = (10-3)/mab_tok
# 2) this week: all workflow tokens since the weekly reset (2026-10-09T21:00Z) vs weekly 40% now (upper bound on rate)
wk_tok = sum(d.get('totalTokens') or 0 for d in wf.values() if '2026-10-09T21:00' <= (d.get('timestamp') or '') <= '2026-10-13T13:50')/1e6
rw_week = 40/wk_tok
print(f"anchor map A/B: {r5_mab:.2f} 5h-pts/M, {rw_mab:.3f} weekly-pts/M")
print(f"anchor this week: {wk_tok:.0f}M workflow tokens -> {rw_week:.3f} weekly-pts/M (ratio to map A/B: {rw_mab/rw_week:.1f}x)")
r5_week = r5_mab * rw_week / rw_mab   # assumes the 5h and weekly limits scale together (an assumption)
for name, r5, rw in [('map A/B rate', r5_mab, rw_mab), ('this-week rate', r5_week, rw_week)]:
    print(f"{name:15s}: 5h window {lo_t*r5:.0f}-{hi_t*r5:.0f} pts; weekly {lo_t*rw:.1f}-{hi_t*rw:.1f} pts")
