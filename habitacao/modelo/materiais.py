"""Materiais procedurais (Cycles) — sem texturas externas."""
import bpy

_cache = {}


def _new(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return m, nt, bsdf, out


def srgb(r, g, b):
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (f(r), f(g), f(b), 1.0)


def coord(nt, escala=(1, 1, 1), rot=(0, 0, 0)):
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = escala
    mp.inputs['Rotation'].default_value = rot
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    return mp


def simples(name, cor, rough=0.5, metal=0.0, coat=0.0):
    if name in _cache:
        return _cache[name]
    m, nt, b, _ = _new(name)
    b.inputs['Base Color'].default_value = cor
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if coat:
        b.inputs['Coat Weight'].default_value = coat
    _cache[name] = m
    return m


def reboco(name, cor, rough=0.85, bump=0.02, escala=40):
    """Paredes pintadas / capoto: cor + ligeira irregularidade."""
    if name in _cache:
        return _cache[name]
    m, nt, b, _ = _new(name)
    b.inputs['Base Color'].default_value = cor
    b.inputs['Roughness'].default_value = rough
    mp = coord(nt)
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = escala
    nz.inputs['Detail'].default_value = 8
    nt.links.new(mp.outputs['Vector'], nz.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = bump
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    _cache[name] = m
    return m


def soalho(name='Soalho carvalho', ao_longo='y'):
    """Soalho de carvalho natural: tábuas 1.2 x 0.19 m com veio e variação por tábua."""
    key = name + ao_longo
    if key in _cache:
        return _cache[key]
    m, nt, b, _ = _new(name)
    rot = (0, 0, 1.5708) if ao_longo == 'y' else (0, 0, 0)
    mp = coord(nt, rot=rot)
    br = nt.nodes.new('ShaderNodeTexBrick')
    br.offset = 0.37
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = 0.0015
    br.inputs['Brick Width'].default_value = 1.2
    br.inputs['Row Height'].default_value = 0.19
    br.inputs['Bias'].default_value = 0.0
    br.inputs['Color1'].default_value = srgb(0.80, 0.63, 0.44)
    br.inputs['Color2'].default_value = srgb(0.72, 0.55, 0.37)
    br.inputs['Mortar'].default_value = srgb(0.35, 0.26, 0.17)
    nt.links.new(mp.outputs['Vector'], br.inputs['Vector'])
    # veio: ruído esticado ao longo da tábua
    mp2 = coord(nt, escala=(1.5, 40, 1), rot=rot)
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 3.0
    nz.inputs['Detail'].default_value = 10
    nz.inputs['Distortion'].default_value = 0.6
    nt.links.new(mp2.outputs['Vector'], nz.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.78, 0.78, 0.78, 1)
    ramp.color_ramp.elements[1].color = (1.08, 1.08, 1.08, 1)
    nt.links.new(nz.outputs['Fac'], ramp.inputs['Fac'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    nt.links.new(br.outputs['Color'], mix.inputs['A'])
    nt.links.new(ramp.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.38
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 0.15
    bp.invert = True
    nt.links.new(br.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    _cache[key] = m
    return m


def ladrilho(name, cor1, cor2, junta, larg=0.6, alt=0.3, offset=0.0, rough=0.18, vertical=False):
    """Cerâmica: peças larg x alt com junta; vertical=True para revestimento de parede."""
    key = name + str(vertical)
    if key in _cache:
        return _cache[key]
    m, nt, b, _ = _new(name)
    rot = (1.5708, 0, 0) if vertical else (0, 0, 0)
    mp = coord(nt, rot=rot)
    br = nt.nodes.new('ShaderNodeTexBrick')
    br.offset = offset
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = 0.003
    br.inputs['Mortar Smooth'].default_value = 0.2
    br.inputs['Brick Width'].default_value = larg
    br.inputs['Row Height'].default_value = alt
    br.inputs['Color1'].default_value = cor1
    br.inputs['Color2'].default_value = cor2
    br.inputs['Mortar'].default_value = junta
    nt.links.new(mp.outputs['Vector'], br.inputs['Vector'])
    if vertical:
        # paredes verticais em X e Y: usa coordenadas triplanares simples via Box projection
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        sepn = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(geo.outputs['Normal'], sepn.inputs['Vector'])
        absn = nt.nodes.new('ShaderNodeMath'); absn.operation = 'ABSOLUTE'
        nt.links.new(sepn.outputs['X'], absn.inputs[0])
        gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = 0.5
        nt.links.new(absn.outputs[0], gt.inputs[0])
        mixu = nt.nodes.new('ShaderNodeMix'); mixu.data_type = 'FLOAT'
        nt.links.new(gt.outputs[0], mixu.inputs['Factor'])
        nt.links.new(sep.outputs['X'], mixu.inputs['A'])
        nt.links.new(sep.outputs['Y'], mixu.inputs['B'])
        comb = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(mixu.outputs['Result'], comb.inputs['X'])
        nt.links.new(sep.outputs['Z'], comb.inputs['Y'])
        nt.links.new(comb.outputs['Vector'], br.inputs['Vector'])
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 6
    nt.links.new(mp.outputs['Vector'], nz.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'OVERLAY'
    mix.inputs['Factor'].default_value = 0.12
    nt.links.new(br.outputs['Color'], mix.inputs['A'])
    nt.links.new(nz.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 0.3
    bp.invert = True
    nt.links.new(br.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    _cache[key] = m
    return m


def vidro():
    if 'Vidro' in _cache:
        return _cache['Vidro']
    m, nt, b, out = _new('Vidro')
    nt.nodes.remove(b)
    glass = nt.nodes.new('ShaderNodeBsdfGlass')
    glass.inputs['Roughness'].default_value = 0.0
    glass.inputs['IOR'].default_value = 1.45
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    # raios de sombra e difusos atravessam o vidro (luz natural entra no interior)
    mx = nt.nodes.new('ShaderNodeMath'); mx.operation = 'MAXIMUM'
    nt.links.new(lp.outputs['Is Shadow Ray'], mx.inputs[0])
    nt.links.new(lp.outputs['Is Diffuse Ray'], mx.inputs[1])
    nt.links.new(mx.outputs[0], mix.inputs['Fac'])
    nt.links.new(glass.outputs['BSDF'], mix.inputs[1])
    nt.links.new(tr.outputs['BSDF'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    _cache['Vidro'] = m
    return m


def emissor(name, cor=(1.0, 0.85, 0.65, 1), forca=8):
    if name in _cache:
        return _cache[name]
    m, nt, b, _ = _new(name)
    b.inputs['Base Color'].default_value = (1, 1, 1, 1)
    b.inputs['Emission Color'].default_value = cor
    b.inputs['Emission Strength'].default_value = forca
    _cache[name] = m
    return m


def pedra():
    if 'Granito' in _cache:
        return _cache['Granito']
    m, nt, b, _ = _new('Granito')
    mp = coord(nt)
    br = nt.nodes.new('ShaderNodeTexBrick')
    br.offset = 0.5
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = 0.012
    br.inputs['Brick Width'].default_value = 0.55
    br.inputs['Row Height'].default_value = 0.28
    br.inputs['Color1'].default_value = srgb(0.62, 0.60, 0.57)
    br.inputs['Color2'].default_value = srgb(0.52, 0.50, 0.47)
    br.inputs['Mortar'].default_value = srgb(0.40, 0.39, 0.37)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(sep.outputs['X'], comb.inputs['X']); nt.links.new(sep.outputs['Z'], comb.inputs['Y'])
    nt.links.new(comb.outputs['Vector'], br.inputs['Vector'])
    vor = nt.nodes.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 300
    nt.links.new(mp.outputs['Vector'], vor.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 0.35
    nt.links.new(br.outputs['Color'], mix.inputs['A']); nt.links.new(vor.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.75
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.6; bp.invert = True
    nt.links.new(br.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    _cache['Granito'] = m
    return m


def telha():
    if 'Telha' in _cache:
        return _cache['Telha']
    m, nt, b, _ = _new('Telha')
    mp = coord(nt)
    br = nt.nodes.new('ShaderNodeTexBrick')
    br.offset = 0.5
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = 0.006
    br.inputs['Brick Width'].default_value = 0.21
    br.inputs['Row Height'].default_value = 0.33
    br.inputs['Color1'].default_value = srgb(0.68, 0.30, 0.18)
    br.inputs['Color2'].default_value = srgb(0.60, 0.26, 0.16)
    br.inputs['Mortar'].default_value = srgb(0.30, 0.13, 0.08)
    nt.links.new(mp.outputs['Vector'], br.inputs['Vector'])
    nt.links.new(br.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.6
    wav = nt.nodes.new('ShaderNodeTexWave'); wav.inputs['Scale'].default_value = 1.0
    wav.inputs['Distortion'].default_value = 0.0
    mpw = coord(nt, escala=(4.76, 1, 1))
    nt.links.new(mpw.outputs['Vector'], wav.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.8
    nt.links.new(wav.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    _cache['Telha'] = m
    return m


def tecido(name, cor, rough=0.9):
    if name in _cache:
        return _cache[name]
    m, nt, b, _ = _new(name)
    b.inputs['Base Color'].default_value = cor
    b.inputs['Roughness'].default_value = rough
    b.inputs['Sheen Weight'].default_value = 0.6
    mp = coord(nt, escala=(1, 1, 1))
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 400
    nt.links.new(mp.outputs['Vector'], nz.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.08
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    _cache[name] = m
    return m


def madeira_bancada():
    """Madeira de carvalho para bancada / mobiliário (veio contínuo)."""
    if 'Madeira mobiliario' in _cache:
        return _cache['Madeira mobiliario']
    m, nt, b, _ = _new('Madeira mobiliario')
    mp = coord(nt, escala=(1, 18, 1))
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 4
    nz.inputs['Detail'].default_value = 12; nz.inputs['Distortion'].default_value = 0.8
    nt.links.new(mp.outputs['Vector'], nz.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = srgb(0.62, 0.45, 0.28)
    ramp.color_ramp.elements[1].color = srgb(0.82, 0.65, 0.45)
    nt.links.new(nz.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.35
    _cache['Madeira mobiliario'] = m
    return m


def todos():
    """Dicionário com os materiais do projeto."""
    return {
        'parede': reboco('Parede branca', srgb(0.93, 0.93, 0.91), 0.85, 0.01, 30),
        'teto': reboco('Teto branco', srgb(0.95, 0.95, 0.94), 0.9, 0.005, 30),
        'capoto': reboco('Capoto amarelo claro (Fassa Bartolo)', srgb(0.95, 0.86, 0.58), 0.9, 0.06, 60),
        'reboco_viz': reboco('Reboco vizinhos', srgb(0.86, 0.85, 0.82), 0.9, 0.05, 60),
        'embasamento': reboco('Embasamento', srgb(0.58, 0.57, 0.55), 0.95, 0.3, 120),
        'granito': pedra(),
        'soalho': soalho('Soalho carvalho', 'y'),
        'soalho_x': soalho('Soalho carvalho X', 'x'),
        'cer_wc_chao': ladrilho('Cerâmica bege chão', srgb(0.84, 0.77, 0.66), srgb(0.81, 0.74, 0.63), srgb(0.70, 0.66, 0.60), 0.6, 0.6, 0.0, 0.2),
        'cer_wc_parede': ladrilho('Cerâmica bege parede', srgb(0.88, 0.82, 0.72), srgb(0.86, 0.80, 0.70), srgb(0.80, 0.77, 0.72), 0.6, 0.3, 0.0, 0.12, vertical=True),
        'cer_coz': ladrilho('Cerâmica cozinha', srgb(0.86, 0.84, 0.80), srgb(0.83, 0.81, 0.77), srgb(0.70, 0.69, 0.66), 0.6, 0.3, 0.5, 0.2),
        'cer_cave': ladrilho('Cerâmica cave', srgb(0.70, 0.70, 0.69), srgb(0.66, 0.66, 0.65), srgb(0.55, 0.55, 0.54), 0.3, 0.3, 0.0, 0.35),
        'azulejo_coz': ladrilho('Azulejo cozinha', srgb(0.95, 0.95, 0.93), srgb(0.93, 0.93, 0.91), srgb(0.82, 0.82, 0.80), 0.15, 0.075, 0.5, 0.08, vertical=True),
        'caixilho': simples('Caixilharia antracite', srgb(0.23, 0.24, 0.25), 0.4, 0.3),
        'vidro': vidro(),
        'porta': simples('Porta lacada branca', srgb(0.92, 0.92, 0.90), 0.3),
        'branco_lacado': simples('Lacado branco', srgb(0.94, 0.94, 0.93), 0.25, 0.0, 0.3),
        'madeira': madeira_bancada(),
        'inox': simples('Inox', srgb(0.75, 0.75, 0.75), 0.25, 1.0),
        'preto': simples('Preto', srgb(0.03, 0.03, 0.03), 0.4),
        'cromado': simples('Cromado', srgb(0.9, 0.9, 0.9), 0.05, 1.0),
        'loica': simples('Loiça sanitária', srgb(0.96, 0.96, 0.96), 0.08, 0.0, 0.8),
        'espelho': simples('Espelho', srgb(0.95, 0.95, 0.95), 0.0, 1.0),
        'sofa': tecido('Tecido sofá', srgb(0.55, 0.53, 0.50)),
        'manta': tecido('Tecido manta', srgb(0.80, 0.70, 0.58)),
        'lencol': tecido('Roupa de cama', srgb(0.95, 0.95, 0.93)),
        'tapete': tecido('Tapete', srgb(0.78, 0.75, 0.70)),
        'almofada_azul': tecido('Almofada azul', srgb(0.35, 0.45, 0.55)),
        'cortina': tecido('Cortina linho', srgb(0.92, 0.90, 0.86)),
        'planta': simples('Folhagem', srgb(0.18, 0.35, 0.15), 0.6),
        'vaso': simples('Vaso cerâmico', srgb(0.85, 0.83, 0.80), 0.5),
        'telha': telha(),
        'quadro1': simples('Quadro 1', srgb(0.30, 0.42, 0.50), 0.6),
        'quadro2': simples('Quadro 2', srgb(0.75, 0.55, 0.35), 0.6),
        'luz': emissor('Luz quente', (1.0, 0.82, 0.62, 1), 12),
        'carro': simples('Carro', srgb(0.15, 0.20, 0.28), 0.15, 0.6, 1.0),
        'pneu': simples('Pneu', srgb(0.04, 0.04, 0.04), 0.8),
        'relva': simples('Relva', srgb(0.25, 0.40, 0.17), 0.9),
        'calcada': ladrilho('Calçada', srgb(0.70, 0.69, 0.66), srgb(0.62, 0.61, 0.58), srgb(0.40, 0.40, 0.38), 0.4, 0.4, 0.5, 0.8),
    }
