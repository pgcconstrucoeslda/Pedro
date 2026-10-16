import ezdxf, collections, sys
for f in sys.argv[1:]:
    doc=ezdxf.readfile(f); msp=doc.modelspace()
    print('==',f, 'INSUNITS',doc.header.get('$INSUNITS'), 'ext', doc.header.get('$EXTMIN'), doc.header.get('$EXTMAX'))
    c=collections.Counter((e.dxftype(), e.dxf.layer, e.dxf.get('color',256), e.dxf.get('true_color',None)) for e in msp)
    for k,v in c.most_common(25): print(' ',v,k)
    ins=collections.Counter(e.dxf.name for e in msp.query('INSERT'))
    print('  blocks:',ins.most_common(12))
    print('  layouts:', [(l.name, len(l)) for l in doc.layouts])
