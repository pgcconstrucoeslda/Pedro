"""Imagem de verificação: hatches com legenda (verde) vs sem legenda (vermelho) + handles."""
import sys, json, ezdxf
from ezdxf import path as P
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MP
dxf, js, out = sys.argv[1:4]
d = json.load(open(js)); info = {e['handle']: e for e in d['entidades']}
doc = ezdxf.readfile(dxf); msp = doc.modelspace(); s = d['escala_m']
fig, ax = plt.subplots(figsize=(24, 14), dpi=110)
for e in msp.query('LINE'):
    if e.dxf.layer in ('arquitectura', 'estrutura'):
        ax.plot([e.dxf.start.x*s, e.dxf.end.x*s], [e.dxf.start.y*s, e.dxf.end.y*s], color='#888', lw=0.3)
for h in msp.query('HATCH'):
    r = info.get(h.dxf.handle)
    if not r or r['legenda'] or (h.dxf.pattern_name == 'SOLID' and r['cor'] in ('ACI7', 'ByLayer')):
        continue
    cor = '#2e9b3e' if r['descricao'] else ('#d62728' if r['area_m2'] > 1 else None)
    if not cor or r['area_m2'] > 600:
        continue
    for p in P.from_hatch(h):
        v = [(q.x*s, q.y*s) for q in p.flattening(0.01)]
        if len(v) > 2:
            ax.add_patch(MP(v, closed=True, fc=cor, ec='k', lw=0.2, alpha=0.45))
    if not r['descricao']:
        ax.text(r['x'], r['y'], f"{r['handle']}\n{r['area_m2']:.1f}m²", fontsize=7, color='#8b0000', ha='center')
ax.set_aspect('equal'); ax.autoscale(); ax.axis('off')
ax.set_title(f"{d['ficheiro'].split('/')[-1]} — verde: com legenda · vermelho: SEM legenda (handle / área)", fontsize=14)
plt.savefig(out, bbox_inches='tight'); print('ok', out)
