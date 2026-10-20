import json, re, os
mods=['bus','cache','cpu','cpu_cp_cfu','cpu_cp_muldiv','cpu_pmp','debug_dtm','hwspinlock','imem','spi','sys','trng','twi','uart','wdt']
base='inputs/v1/tuning'
pack='analysis/two_phase_v7__gpt-5.6-luna__high__r0-r2/failure_analysis/packs/module'
tot=0; inref=0
for m in mods:
    cs=json.load(open(f'{base}/neorv32_{m}/closed_set.json'))
    ref=open(f'{pack}/ref_{m}.md',encoding='utf-8').read()
    rows=[l for l in ref.split('\n') if l.startswith('- ') and '| objectives' in l]
    names=set()
    for l in rows:
        for n in l[2:].split('|')[0].split(','):
            n=n.strip()
            if n: names.add(n)
    for e in cs['entity list']:
        for p in e['port list']:
            tags=p.get('role in RTL',[])
            if 'not used in this module' in tags or ('not read' in tags and p['direction']=='in'):
                tot+=1
                hit=p['port'] in names
                inref+=hit
                print(m, e['entity name'], p['port'], p['direction'], tags, 'IN_REF' if hit else '-')
print('total unused/not-read input ports', tot, 'in reference', inref)
print('--- every element (port, signal, field) tagged not used in this module, 15 modules')
c=0; r=0
for m in mods:
    cs=json.load(open(f'{base}/neorv32_{m}/closed_set.json'))
    ref=open(f'{pack}/ref_{m}.md',encoding='utf-8').read()
    rows=[l for l in ref.split('\n') if l.startswith('- ') and '| objectives' in l]
    names=set(n.strip() for l in rows for n in l[2:].split('|')[0].split(',') if n.strip())
    for e in cs['entity list']:
        for kind in ('port list','signal list'):
            for p in e.get(kind,[]):
                items=[p]+p.get('fields',[])
                for q in items:
                    nm=q.get('port') or q.get('signal') or q.get('field')
                    if 'not used in this module' in q.get('role in RTL',[]):
                        c+=1; r+= nm in names
                        if nm in names: print('  in ref:', m, nm)
print('elements tagged not used:', c, 'listed by reference:', r)
