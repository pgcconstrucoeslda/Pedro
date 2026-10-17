"""Uso: python render.py planta | fotos [nome1 nome2 ...] | lista
Gera vistas em planta (validação) ou imagens fotorrealistas (Cycles) para out/."""
import os, sys, math, time
sys.path.insert(0, os.path.dirname(__file__))
import bpy
from mathutils import Vector
import casa

OUT = os.path.join(os.path.dirname(__file__), '..', 'out')
os.makedirs(OUT, exist_ok=True)
Z = casa.Z

# câmaras: nome -> (piso, (x, y, z_olho), (x, y, z_alvo), lente_mm, exposição)
CAM = {
    # CAVE
    'cave_garagem':     ('cave', (1.0, 10.6, 1.55), (5.0, 2.5, 1.0), 16, 0.6),
    'cave_garagem_b':   ('cave', (6.6, 1.0, 1.6), (2.0, 9.5, 0.9), 16, 0.6),
    'cave_atrio':       ('cave', (2.55, 4.95, 1.55), (0.6, 2.0, 1.4), 14, 1.2),
    # R/C
    'rc_sala':          ('rc', (3.25, 11.2, 1.45), (6.4, 6.0, 1.0), 16, 0.8),
    'rc_sala_b':        ('rc', (6.7, 5.0, 1.5), (3.6, 10.5, 1.0), 16, 0.8),
    'rc_cozinha':       ('rc', (3.3, 4.0, 1.55), (6.6, 0.6, 1.05), 16, 0.8),
    'rc_hall':          ('rc', (2.55, 8.75, 1.55), (0.5, 10.4, 1.1), 14, 1.2),
    'rc_corredor':      ('rc', (2.3, 8.2, 1.55), (2.0, 3.8, 1.2), 16, 1.4),
    'rc_wc':            ('rc', (1.25, 6.3, 1.55), (0.3, 8.2, 0.9), 12, 1.0),
    'rc_despensa':      ('rc', (1.30, 5.05, 1.6), (0.3, 5.9, 1.0), 12, 1.0),
    'rc_escada':        ('rc', (2.45, 3.45, 1.65), (0.8, 1.6, 0.9), 14, 1.2),
    # 1º PISO
    'p1_quarto1':       ('p1', (3.75, 4.9, 1.55), (6.6, 1.0, 0.9), 16, 0.9),
    'p1_quarto2':       ('p1', (3.0, 10.2, 1.55), (0.6, 6.8, 0.9), 15, 0.9),
    'p1_quarto3':       ('p1', (4.5, 7.05, 1.55), (6.6, 10.6, 0.9), 15, 0.9),
    'p1_wc1':           ('p1', (3.3, 3.0, 1.6), (1.8, 5.0, 1.0), 12, 1.0),
    'p1_wc2':           ('p1', (4.95, 6.6, 1.55), (6.9, 4.5, 0.9), 12, 1.0),
    'p1_hall':          ('p1', (0.45, 5.95, 1.55), (4.5, 6.4, 1.1), 14, 1.2),
    'p1_escada':        ('p1', (0.5, 5.9, 1.65), (1.6, 1.2, 0.2), 14, 1.2),
    # EXTERIOR
    'ext_traseira':     ('cave', (2.0, -12.5, 3.0), (3.6, 3.0, 5.0), 22, 0.0),
}


def preparar(qualidade='alta'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    casa.construir()
    casa.luz_natural()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    cy = sc.cycles
    cy.device = 'CPU'
    cy.samples = 64 if qualidade == 'alta' else 24
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    try:
        cy.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    cy.max_bounces = 8
    cy.diffuse_bounces = 4
    cy.glossy_bounces = 3
    cy.transmission_bounces = 6
    cy.transparent_max_bounces = 8
    cy.sample_clamp_indirect = 8
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    sc.render.threads_mode = 'AUTO'
    sc.render.resolution_x = 1280 if qualidade == 'alta' else 800
    sc.render.resolution_y = 853 if qualidade == 'alta' else 533
    sc.render.image_settings.file_format = 'PNG'
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        try:
            sc.view_settings.view_transform = 'Filmic'
        except Exception:
            pass
    return sc


def camara(nome):
    piso, eye, alvo, lente, expo = CAM[nome]
    z0 = Z[piso]
    cd = bpy.data.cameras.new(nome)
    cd.lens = lente
    cd.sensor_width = 36
    cd.clip_start = 0.05
    ob = bpy.data.objects.new(nome, cd)
    ob.location = Vector((eye[0], eye[1], z0 + eye[2]))
    alvo = Vector((alvo[0], alvo[1], z0 + alvo[2]))
    d = alvo - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.scene.camera = ob
    bpy.context.scene.view_settings.exposure = expo
    return ob


def plantas():
    """Vistas em planta (corte a 1,30 m) com Workbench para comparar com o PDF."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    casa.construir()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 12
    sc.cycles.use_denoising = True
    w = bpy.data.worlds.new('branco'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.5
    for o in list(bpy.data.objects):
        if o.type == 'LIGHT':
            bpy.data.objects.remove(o, do_unlink=True)
    sc.render.resolution_x = 900
    sc.render.resolution_y = 1400
    for piso in ('cave', 'rc', 'p1'):
        cd = bpy.data.cameras.new('planta_' + piso)
        cd.type = 'ORTHO'
        cd.ortho_scale = 13.2
        cd.clip_start = 0.001
        cd.clip_end = 3.0
        ob = bpy.data.objects.new('planta_' + piso, cd)
        ob.location = (3.62, 6.1, Z[piso] + 1.30)
        sc.collection.objects.link(ob)
        sc.camera = ob
        corte = Z[piso] + 1.30
        for o in bpy.data.objects:
            if o.type == 'MESH':
                zmin = min((o.matrix_world @ Vector(c)).z for c in o.bound_box)
                o.hide_render = zmin > corte
        sc.render.filepath = os.path.join(OUT, f'planta_{piso}.png')
        bpy.ops.render.render(write_still=True)
        print('ok planta', piso)


def fotos(nomes, qualidade='alta'):
    preparar(qualidade)
    for n in nomes:
        t = time.time()
        camara(n)
        bpy.context.scene.render.filepath = os.path.join(OUT, f'{n}.png')
        bpy.ops.render.render(write_still=True)
        print(f'ok {n} {time.time() - t:.0f}s', flush=True)


if __name__ == '__main__':
    modo = sys.argv[1] if len(sys.argv) > 1 else 'planta'
    if modo == 'planta':
        plantas()
    elif modo == 'lista':
        print(' '.join(CAM))
    else:
        nomes = sys.argv[2:] or list(CAM)
        fotos(nomes, 'alta' if modo == 'fotos' else 'rapida')
