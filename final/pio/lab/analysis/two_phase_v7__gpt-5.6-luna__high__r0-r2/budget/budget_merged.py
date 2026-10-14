# Merged plan: the analysis agent for a pattern group also drafts its fix; 2 skeptics + 1 revision check both.
import json, glob, os, statistics as st
root = os.path.expanduser('~/.claude/projects')
def rec(rid): return json.load(open(glob.glob(os.path.join(root, '*/*/workflows/'+rid+'.json'))[0], encoding='utf-8'))
v6r = rec('wf_ce0308e1-806')
ags = [a for a in v6r['workflowProgress'] if a['type'] == 'workflow_agent']
assert len(ags) == 61  # self-test against the hand-read agent count
ph = {}
for a in ags: ph.setdefault(a['phaseTitle'], []).append(a)
per = {}
for p, xs in ph.items():
    mins = sorted(x['durationMs']/60000 for x in xs); toks = [x['tokens'] for x in xs]
    per[p] = (st.median(mins), max(mins), st.mean(toks))
    print(f"v6 rules {p:10s} n={len(xs):2d} minutes median {st.median(mins):.1f} max {max(mins):.1f}  tokens/agent mean {st.mean(toks)/1e3:.0f}k")
groups = 8   # pattern groups (assumption: about as many as the v5g failure report's 6 structural + concept clusters)
c_agents = groups * (1 + 2 + 1)
c_tok = groups * (per['Draft'][2] + 2*per['Challenge'][2] + per['Revise'][2]) / 1e6
c_min_med = per['Draft'][0] + per['Challenge'][0] + per['Revise'][0]
c_min_max = per['Draft'][1] + per['Challenge'][1] + per['Revise'][1]
cm = [rec(r) for r in ['wf_8c08ab5b-fa8','wf_60ff96f7-019','wf_31e339e0-945','wf_74edb89b-4cb','wf_ec4c65b4-268']]
bl = [rec(r) for r in ['wf_859ba8d0-07c','wf_b1d6d6cc-c10','wf_c35177e8-849']]
b_tok = (min(r['totalTokens'] for r in cm)/1e6, max(r['totalTokens'] for r in cm)/1e6)
b_min = max(r['durationMs'] for r in cm)/60000
e_tok = (min(r['totalTokens'] for r in bl)/1e6, max(r['totalTokens'] for r in bl)/1e6)
e_min = max(r['durationMs'] for r in bl)/60000
a_min, d_min, f_min = 15, 12, 10   # code stage, conflict check by file paths, report: NOT measured (estimates)
misc_tok = 2 * 0.25                # conflict check + report writer, ~250k each (estimate)
lo = b_tok[0] + c_tok + e_tok[0] + misc_tok; hi = b_tok[1] + c_tok + e_tok[1] + misc_tok
agents = 35 + c_agents + 30 + 2
print(f"C chain: {c_agents} agents, {c_tok:.1f}M tokens, {c_min_med:.0f} min (medians) / {c_min_max:.0f} min (slowest)")
print(f"agents ~{agents}; tokens {lo:.1f}-{hi:.1f}M")
t_med = a_min + b_min + c_min_med + d_min + e_min + f_min
t_max = a_min + b_min + c_min_max + d_min + e_min + f_min
print(f"critical path: {t_med:.0f} min with median agents, {t_max:.0f} min with the slowest agents")
for name, r5, rw in [('map A/B rate', 26/14.6, 7/14.6), ('this-week rate', 26/14.6/3.6, 7/14.6/3.6)]:
    print(f"{name:15s}: 5h window {lo*r5:.0f}-{hi*r5:.0f} pts; weekly {lo*rw:.1f}-{hi*rw:.1f} pts")
