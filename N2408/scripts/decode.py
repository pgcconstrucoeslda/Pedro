# Descodifica os downloads do Google Drive (JSON base64) para N2408/dwg/<pasta>/<ficheiro>
import json, base64, glob, os, csv
root = '/home/user/Pedro/N2408'
man = {r['id']: r for r in csv.DictReader(open(f'{root}/manifesto.tsv'), delimiter='\t')}
src = '/root/.claude/projects/-home-user-Pedro/69ff8397-9341-55b6-92a6-0ceef2c871bf/tool-results'
n = 0
for f in sorted(glob.glob(f'{src}/mcp-Google_Drive-download_file_content-*.txt')):
    d = json.load(open(f))
    r = man.get(d['id'])
    if not r: continue
    out = f"{root}/dwg/{r['pasta']}/{r['ficheiro']}"
    if os.path.exists(out) and os.path.getsize(out) == int(r['tamanho']): continue
    os.makedirs(os.path.dirname(out), exist_ok=True)
    data = base64.b64decode(d['content'])
    open(out, 'wb').write(data)
    n += 1
    print(('OK ' if len(data) == int(r['tamanho']) else 'TAMANHO DIFERENTE ') + out[len(root)+1:])
print(n, 'novos')
