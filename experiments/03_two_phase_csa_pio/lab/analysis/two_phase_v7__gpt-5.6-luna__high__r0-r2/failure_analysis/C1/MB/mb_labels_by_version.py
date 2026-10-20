import os
import json, glob, sys
targets={'neorv32_wdt':['reset_wdt'],'neorv32_cache':['cache_i.sta_hit','addr_i'],'neorv32_cpu':['lsu_mar','alu_add'],'neorv32_cpu_cp_muldiv':['ctrl.rs1_is_signed','ctrl.rs2_is_signed'],'neorv32_cpu_cp_cfu':['active_i','rs3_i']}
for v in ['two_phase_v5f__v1','two_phase_v6__v1','two_phase_v6d__v1','two_phase_v7__v1']:
    for mod,els in targets.items():
        for el in els:
            res=[]
            for f in sorted(glob.glob(f'{v}/gpt-5.6-luna__high/r*/phase2/{mod}.json')):
                r=os.path.normpath(f).split(os.sep)[-3]
                try:
                    d=json.load(open(f,encoding='utf-8')); d=d['raw'] if 'raw' in d else d; d=json.loads(d[d.find('{'):d.rfind('}')+1]) if isinstance(d,str) else d
                except Exception as e: res.append(r+':ERR'); continue
                labs=set()
                for w in d.get('Concept Walks',[]):
                    for a in w.get('Assets',[]):
                        if a.get('Asset RTL')==el: labs.add(a.get('Label'))
                res.append(r+':'+('P' if 'primary' in labs else ('s' if labs else '-')))
            print(v, mod, el, ' '.join(res))
