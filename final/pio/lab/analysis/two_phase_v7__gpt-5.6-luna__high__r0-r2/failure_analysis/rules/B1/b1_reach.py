"""B1 reach: where does the rule's condition fire, and what would it change in the v7 replies?
Condition: a non-record output port of an [inst] block marked '(entity, this file)' drives a unit
signal whose closed-set entry lists 'decides' partners (this unit tests it in a condition)."""
import json, re, os, glob
BASE = 'E:/jobs/ff/test/Prepoison_subset/final/pio/lab'
FA = BASE + '/analysis/two_phase_v7__gpt-5.6-luna__high__r0-r2/failure_analysis'

def elems(ent):
    for p in ent.get('port list', []):
        yield p['port'], p, 'port'
    for s in ent.get('signal list', []):
        yield s['signal'], s, 'signal'
        for f in s.get('fields', []) or []:
            yield f['field'], f, 'field'

def rtl_line(mdir, n):
    for l in open(mdir + '/rtl.txt', encoding='utf-8'):
        m = re.match(r'\s*(\d+) \|(.*)', l)
        if m and int(m.group(1)) == n:
            return m.group(2)
    return None

def fires(mdir):
    diag = open(mdir + '/diagram.txt', encoding='utf-8').read()
    insts = re.findall(r'\[inst\] (\S+) \((\S+), this file\)', diag)
    cs = json.load(open(mdir + '/closed_set.json', encoding='utf-8'))
    ents = {e['entity name']: e for e in cs['entity list']}
    unit = re.search(r'^UNIT (\S+)', diag, re.M).group(1)
    out = []
    for inst, ent in insts:
        for pn, p, k in elems(ents[ent]):
            if k != 'port' or p['direction'] != 'out' or 'record type' in p:
                continue
            for en, x, kk in elems(ents[unit]):
                for c in x.get('counterparts', {}).get('gets value from', []):
                    if c.get('instance') == inst and c.get('port') == pn:
                        dec = x.get('counterparts', {}).get('decides', [])
                        out.append(dict(inst=inst, child_entity=ent, port=pn, signal=en, unit=unit,
                                        fires=bool(dec), decides=[(d.get('element'), d.get('lines')) for d in dec]))
    return out

# ---- self-test against hand-read lines (read this session) ----
cache = BASE + '/inputs/v1/tuning/neorv32_cache'
trng = BASE + '/inputs/v1/tuning/neorv32_trng'
assert "cache_i.sta_hit = '1'" in rtl_line(cache, 189)          # rtl.txt:129
assert 'hit_o   => cache_i.sta_hit' in rtl_line(cache, 286)       # rtl.txt:206
assert 'rdata_o => cache_i.data' in rtl_line(cache, 291)          # rtl.txt:210
assert 'wdata_i => fifo.wdata' in rtl_line(trng, 161)             # rtl.txt:111
assert 'data_o   => fifo.wdata' in rtl_line(trng, 139)            # rtl.txt:95
fc = {(r['port'], r['signal']): r for r in fires(cache)}
assert fc[('hit_o', 'cache_i.sta_hit')]['fires'] and any(189 in (l or []) for _, l in fc[('hit_o', 'cache_i.sta_hit')]['decides'])
assert not fc[('rdata_o', 'cache_i.data')]['fires']
ft = {(r['port'], r['signal']): r for r in fires(trng)}
assert not ft[('data_o', 'fifo.wdata')]['fires'] and not ft[('valid_o', 'fifo.we')]['fires']
print('SELF-TEST PASS')

for split in ('tuning', 'heldout'):
    n_cand = n_fire = 0
    for mdir in sorted(glob.glob(f'{BASE}/inputs/v1/{split}/*')):
        for r in fires(mdir):
            n_cand += 1
            n_fire += r['fires']
            print(split, os.path.basename(mdir), r['inst'], r['port'], '->', r['signal'], 'FIRES' if r['fires'] else 'no')
    print(f'{split}: non-record outputs of this-file instances wired to a unit signal = {n_cand}; condition true = {n_fire}')

# ---- v7 labels of the elements it touches ----
tun = {os.path.basename(m): m for m in glob.glob(BASE + '/inputs/v1/tuning/*')}
for run in ('r0', 'r1', 'r2'):
    for mod, mdir in tun.items():
        hits = [r for r in fires(mdir) if r['fires']]
        if not hits:
            continue
        rep = json.load(open(f'{FA}/raw/{run}/phase2/{mod}.json', encoding='utf-8'))
        for h in hits:
            for w in rep['Concept Walks']:
                for a in w.get('Assets', []):
                    if (a['Asset RTL'], a['Entity']) in ((h['port'], h['child_entity']), (h['signal'], h['unit'])):
                        print(run, mod, w['Concept ID'], a['Asset RTL'], a['Entity'], a['Label'])

# ---- expected scores if the rule is followed (reasoning: hit_o -> cache_i.sta_hit in each run) ----
S = json.load(open(FA + '/scores.json', encoding='utf-8'))['per run']['v7']
C = L = 0
for run in ('r0', 'r1', 'r2'):
    c, l = S[run]['correct'] + 1, S[run]['listed']
    C += c; L += l
    print(run, f'correct {S[run]["correct"]}->{c}, listed {l}, P {S[run]["precision"]}->{c/l:.3f}, R {S[run]["recall"]}->{c/109:.3f}')
print(f'pooled P {C}/{L} = {C/L:.4f}; R {C}/327 = {C/327:.4f}')
