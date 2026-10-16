#!/bin/bash
# Extrai medições de todos os DXF para json/
cd /home/user/Pedro/N2408
find dxf -name '*.dxf' | sort | while read f; do
  o="json/${f#dxf/}"; o="${o%.dxf}.json"; mkdir -p "$(dirname "$o")"
  timeout 900 python3 scripts/extrair.py "$f" > "$o" 2>/dev/null || echo "FALHOU $f"
done
