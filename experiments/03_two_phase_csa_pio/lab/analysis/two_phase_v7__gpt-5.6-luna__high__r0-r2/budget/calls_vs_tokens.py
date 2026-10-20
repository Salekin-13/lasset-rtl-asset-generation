# How agent tokens grow with tool calls, from past workflow run records (per-agent 'tokens' and 'toolCalls').
import json, glob, os, statistics as st
root = os.path.expanduser('~/.claude/projects')
wf = {}
for f in glob.glob(os.path.join(root, 'E--jobs-ff-test-Prepoison-subset*/*/workflows/wf_*.json')):
    try: d = json.load(open(f, encoding='utf-8'))
    except Exception: continue
    wf[d['runId']] = d
pts = []
for rid in ['wf_8c08ab5b-fa8','wf_60ff96f7-019','wf_74edb89b-4cb','wf_ec4c65b4-268','wf_be9f2b3f-beb','wf_6a4e92b2-c2b',
            'wf_9c7700ae-02e','wf_155b9394-6bb','wf_ce0308e1-806','wf_859ba8d0-07c','wf_b1d6d6cc-c10','wf_c35177e8-849',
            'wf_318b1752-7e8','wf_91fa05de-dcc']:
    for a in wf[rid]['workflowProgress']:
        if a['type'] != 'workflow_agent' or a.get('state') != 'done': continue
        if a.get('tokens') is None or a.get('toolCalls') is None: continue
        pts.append((a['toolCalls'], a['tokens'], rid, a.get('phaseTitle')))
# self-test: the per-agent tokens of the v6 diagnosis must sum to its recorded total (within 1%)
s = sum(t for c, t, r, p in pts if r == 'wf_318b1752-7e8')
assert abs(s - wf['wf_318b1752-7e8']['totalTokens']) / wf['wf_318b1752-7e8']['totalTokens'] < 0.01, s
print('self-test passed; agents:', len(pts))
bins = [(0,2),(3,5),(6,10),(11,20),(21,40),(41,999)]
for lo, hi in bins:
    xs = [t for c, t, r, p in pts if lo <= c <= hi]
    if xs: print(f"tool calls {lo:2d}-{hi:3d}: n={len(xs):3d}  tokens/agent median {st.median(xs)/1e3:6.0f}k  mean {st.mean(xs)/1e3:6.0f}k")
# least squares tokens = a + b*calls
n = len(pts); mx = st.mean(c for c, *_ in pts); my = st.mean(t for _, t, *_ in pts)
b = sum((c-mx)*(t-my) for c, t, *_ in pts) / sum((c-mx)**2 for c, *_ in pts); a = my - b*mx
print(f"fit: tokens ~ {a/1e3:.0f}k + {b/1e3:.1f}k per tool call")
for rid in ['wf_318b1752-7e8','wf_6a4e92b2-c2b','wf_ce0308e1-806','wf_b1d6d6cc-c10','wf_ec4c65b4-268']:
    cs = [c for c, t, r, p in pts if r == rid]
    print(f"{rid} {wf[rid]['workflowName']}: tool calls per agent median {st.median(cs)}")
