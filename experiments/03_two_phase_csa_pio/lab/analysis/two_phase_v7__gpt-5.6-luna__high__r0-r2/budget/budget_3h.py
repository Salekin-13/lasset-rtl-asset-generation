# Budget for the 3-hour, lower-cost plan of the v7 failure analysis (estimates from past workflow run records).
# Run: python budget_3h.py   (reads ~/.claude/projects/*/*/workflows/wf_*.json; no network, no writes)
import json, glob, os, statistics as st
root = os.path.expanduser('~/.claude/projects')
wf = {}
for f in glob.glob(os.path.join(root, '*/*/workflows/wf_*.json')):
    try: d = json.load(open(f, encoding='utf-8'))
    except Exception: continue
    wf[d['runId']] = d
def agents(rid): return [a for a in wf[rid]['workflowProgress'] if a['type'] == 'workflow_agent' and a.get('state') == 'done']
# self-tests against figures hand-read from the run records
assert len(agents('wf_ce0308e1-806')) == 61 and wf['wf_ce0308e1-806']['totalTokens'] == 14993613
assert round(wf['wf_318b1752-7e8']['durationMs'] / 60000, 1) == 29.0
# 1) tokens per agent vs tool calls (same 14 workflows as calls_vs_tokens.py)
RIDS = ['wf_8c08ab5b-fa8','wf_60ff96f7-019','wf_74edb89b-4cb','wf_ec4c65b4-268','wf_be9f2b3f-beb','wf_6a4e92b2-c2b',
        'wf_9c7700ae-02e','wf_155b9394-6bb','wf_ce0308e1-806','wf_859ba8d0-07c','wf_b1d6d6cc-c10','wf_c35177e8-849',
        'wf_318b1752-7e8','wf_91fa05de-dcc']
pts = [(a['toolCalls'], a['tokens']) for r in RIDS for a in agents(r) if a.get('tokens') is not None]
mx = st.mean(c for c, _ in pts); my = st.mean(t for _, t in pts)
b = sum((c-mx)*(t-my) for c, t in pts) / sum((c-mx)**2 for c, _ in pts); a0 = my - b*mx
print(f"self-tests passed; fit over {len(pts)} agents: tokens ~ {a0/1e3:.0f}k + {b/1e3:.1f}k per tool call")
def tok(calls): return a0 + b*calls
# 2) the plan (protection first). Agent counts are planning assumptions.
#    Pack-fed agents (judges, analysts, revisers) are expected near CALLS_PACK tool calls: past agents that got complete
#    packs used a median of 5-6 calls (concept matching, v5g failures). Skeptics are NOT limited: they are costed at the
#    measured mean of the v6 rules skeptics, since they may read any file to refute.
CALLS_PACK = 10
groups, unique_fixes = 8, (6, 8)   # assumptions: pattern groups; fixes left after merging duplicates
cm = ['wf_8c08ab5b-fa8','wf_60ff96f7-019','wf_31e339e0-945','wf_74edb89b-4cb','wf_ec4c65b4-268']
bl = ['wf_859ba8d0-07c','wf_b1d6d6cc-c10','wf_c35177e8-849']
v6r = {}
for x in agents('wf_ce0308e1-806'): v6r.setdefault(x['phaseTitle'], []).append(x)
sk_tok = st.mean(x['tokens'] for x in v6r['Challenge'])
B_tok = (min(wf[r]['totalTokens'] for r in cm)/1e6, max(wf[r]['totalTokens'] for r in cm)/1e6)   # measured; stage unchanged
E_meas = (min(wf[r]['totalTokens'] for r in bl)/1e6, max(wf[r]['totalTokens'] for r in bl)/1e6)
E_pack = 30 * tok(CALLS_PACK) / 1e6
# C: analysis+draft per group; 2 skeptics + 1 revision per fix; a second skeptic pair for every fix a skeptic refuted
# (upper bound here: every fix re-checked)
C_agents = [groups + 5*u for u in unique_fixes]
C_pack = [(groups*tok(CALLS_PACK) + u*(4*sk_tok + tok(CALLS_PACK)))/1e6 for u in unique_fixes]
C_old = [(groups*st.mean(x['tokens'] for x in v6r['Draft']) + u*(4*sk_tok + st.mean(x['tokens'] for x in v6r['Revise'])))/1e6 for u in unique_fixes]
DF = 2 * tok(20) / 1e6   # conflict check + report writer, assumed 20 calls each
lo_pack = B_tok[0] + C_pack[0] + E_pack + DF; hi_pack = B_tok[1] + C_pack[1] + E_pack + DF
lo_old = B_tok[0] + C_old[0] + E_meas[0] + DF; hi_old = B_tok[1] + C_old[1] + E_meas[1] + DF
n_agents = (35 + C_agents[0] + 30 + 2, 35 + C_agents[1] + 30 + 2)
print(f"skeptic tokens (v6 rules mean): {sk_tok/1e3:.0f}k; pack-fed agent at {CALLS_PACK} calls: {tok(CALLS_PACK)/1e3:.0f}k")
print(f"agents {n_agents[0]}-{n_agents[1]}  (C: {C_agents[0]}-{C_agents[1]})")
print(f"tokens if packs hold pack-fed agents near {CALLS_PACK} calls: {lo_pack:.1f}-{hi_pack:.1f}M")
print(f"tokens if every agent costs what past agents of its kind did: {lo_old:.1f}-{hi_old:.1f}M")
# 3) time: v6 rules phase medians / slowest for the C chain; measured B and E; A, D, F not measured (estimates)
med = {p: st.median(x['durationMs']/60000 for x in xs) for p, xs in v6r.items()}
mxm = {p: max(x['durationMs']/60000 for x in xs) for p, xs in v6r.items()}
B_min = max(wf[r]['durationMs'] for r in cm)/60000; E_min = max(wf[r]['durationMs'] for r in bl)/60000
A_min, D_min, F_min, DEDUP = 35, 15, 15, 5
# the barrier waits for the slowest analysis agent; then skeptics, revision, re-check skeptics
C_med = mxm['Draft'] + DEDUP + med['Challenge'] + med['Revise'] + med['Challenge']
C_max = mxm['Draft'] + DEDUP + mxm['Challenge'] + mxm['Revise'] + mxm['Challenge']
print(f"C chain: {C_med:.0f} min (median agents after the barrier) / {C_max:.0f} min (slowest agents)")
print(f"total: {A_min + B_min + C_med + D_min + E_min + F_min:.0f} min / {A_min + B_min + C_max + D_min + E_min + F_min:.0f} min")
# 4) usage, two anchors (see budget_calc.py): 2026-10-10 map A/B, and this week's weekly ratio
r5_mab, rw_mab = 26/14.6, 7/14.6
wk_tok = sum(d.get('totalTokens') or 0 for d in wf.values() if '2026-10-09T21:00' <= (d.get('timestamp') or '') <= '2026-10-13T13:50') / 1e6
rw_wk = 40 / wk_tok; r5_wk = r5_mab * rw_wk / rw_mab   # assumes both limits scale together
for name, lo, hi in [('packs hold', lo_pack, hi_pack), ('no saving', lo_old, hi_old)]:
    print(f"{name:10s}: weekly {lo*rw_wk:.1f}-{hi*rw_wk:.1f} pts (this-week rate) / {lo*rw_mab:.1f}-{hi*rw_mab:.1f} (2026-10-10 rate); "
          f"5-hour {lo*r5_wk:.0f}-{hi*r5_wk:.0f} / {lo*r5_mab:.0f}-{hi*r5_mab:.0f} pts")
