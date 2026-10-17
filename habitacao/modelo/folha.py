"""Gera folha de contactos com todas as vistas (out/folha_vistas.png)."""
import os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
OUT = os.path.join(os.path.dirname(__file__), '..', 'out')
NOMES = {
 'cave_garagem':'Cave – Garagem/arrumos','cave_garagem_b':'Cave – Garagem (vista 2)','cave_atrio':'Cave – Átrio',
 'rc_sala':'R/C – Sala','rc_sala_b':'R/C – Sala (vista 2)','rc_cozinha':'R/C – Cozinha','rc_hall':'R/C – Hall de entrada',
 'rc_corredor':'R/C – Corredor','rc_wc':'R/C – WC social','rc_despensa':'R/C – Despensa','rc_escada':'R/C – Escada',
 'p1_quarto1':'1º – Quarto 1 (suite)','p1_quarto2':'1º – Quarto 2','p1_quarto3':'1º – Quarto 3','p1_wc1':'1º – WC suite',
 'p1_wc2':'1º – WC 2','p1_hall':'1º – Hall','p1_escada':'1º – Escada','ext_traseira':'Exterior – Alçado traseiro'}
fs = [n for n in NOMES if os.path.exists(os.path.join(OUT, n + '.png'))]
W, H, C = 640, 427, 3
rows = (len(fs) + C - 1) // C
sheet = Image.new('RGB', (C * W, rows * (H + 34)), 'white')
try: f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
except Exception: f = ImageFont.load_default()
d = ImageDraw.Draw(sheet)
for i, n in enumerate(fs):
    im = Image.open(os.path.join(OUT, n + '.png')).convert('RGB').resize((W - 8, H - 8))
    x, y = (i % C) * W, (i // C) * (H + 34)
    sheet.paste(im, (x + 4, y + 4))
    d.text((x + 8, y + H + 4), NOMES[n], fill='black', font=f)
sheet.save(os.path.join(OUT, 'folha_vistas.png'))
print(len(fs), 'vistas')
