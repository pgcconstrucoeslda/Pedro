import json,sys,collections
d=json.load(open(sys.argv[1]))
print('unidades',d['unidades'],'legenda:',len(d['legenda']))
for k,v in d['legenda'].items(): print('  ',k,'=>',v['descricao'][:90])
agg=collections.defaultdict(lambda:[0,0.0,0.0])
for r in d['entidades']:
    if r['legenda']: continue
    a=agg[(r['descricao'][:70] or '-', r['chave'], r['match'])]; a[0]+=1;a[1]+=r['comp_m'];a[2]+=r['area_m2']
for k,v in sorted(agg.items(), key=lambda x:(x[0][0]=='-', -x[1][2]-x[1][1])):
    if k[0]=='-' and v[1]<5 and v[2]<1: continue
    print(f'{v[0]:5d} {v[1]:9.2f}m {v[2]:9.2f}m2 {k[2]:5s} {k[0][:60]:60s} {k[1][:60]}')
