# -*- coding: utf-8 -*-
import json, sys, traceback
try:
    import typologies as T
    out = []
    for s in T.generate_all():
        r = T.judge_scheme(s)
        out.append({'name': s.name, 'typology': s.typology, 'gfa': round(s.gfa),
            'height': round(s.height,1), 'sellable': round(T.YIELD.sellable(s.gfa)),
            'coverage': round(s.coverage(T.SITE),3), 'ok': r.ok, 'report': str(r),
            'blocks': [{'cx': b.cx, 'cy': b.cy, 'length': b.length, 'width': b.width,
                'rot': b.rot_deg, 'floors': int(b.floors), 'fh': b.floor_height,
                'program': b.program, 'z0': b.z0} for b in s.blocks]})
    open('typology_schemes.json','w').write(json.dumps(out))
    print('OK', len(out))
except Exception:
    traceback.print_exc()
