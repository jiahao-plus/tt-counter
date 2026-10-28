#!/usr/bin/env python3
"""gen_lef.py — 为每个研究结构生成 LEF MACRO。

关键约束（任务书 §4.3）：
  LEF MACRO 名 == GDS cell 名 == Verilog 模块/实例名
  LEF SIZE == GDS bbox
  每个电气结构必须有 PIN，非电结构不伪造 PIN

结构 = 电气（有 PIN）/ 非电（NON_ELECTRICAL，无 PIN）：
  A research_via1     ELECTRICAL  PIN A(met1) B(met2)
  B research_via2     ELECTRICAL  PIN A(met2) B(met3)
  C1 research_branch  ELECTRICAL  PIN IN(met1)
  C3 research_near    ELECTRICAL  P/Q per pair -> 用 4 对 -> PIN P0..P3,Q0..Q3
  C4 research_cross   NON_ELECTRICAL（交叉不连接，无端点）
  D research_dense    NON_ELECTRICAL（几何试片）
  E research_fiducial NON_ELECTRICAL（配准标记）
"""
import json
import os
import sys

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
DBU = 0.001
L = {'M1': (68, 20), 'Via1': (68, 44), 'M2': (69, 20),
     'Via2': (69, 44), 'M3': (70, 20), 'M4': (71, 20)}
LEF_LAYER = {'M1': 'met1', 'M2': 'met2', 'M3': 'met3', 'M4': 'met4'}

# hand-declared pins, matched to the builder geometry in gen_v2_macros.py.
# Coordinates are the *wire centreline* in the structure's own coordinate frame;
# emit() shrinks the endpoint into a legal landing size.
PINS = {
    'A': [('A', 'M1', 1.0, 2.0), ('B', 'M2', 9.0, 4.0)],
    'B': [('A', 'M2', 1.0, 2.0), ('B', 'M3', 11.0, 5.0)],
    # C1: trunk input on the left; TAP is the top of the middle M2 branch stub.
    # Measured from struct_C1.gds: the stub at x 5.93..6.07 runs to y 7.57, so
    # the pin rect (height 0.14, centred on y) must sit fully below 7.57.
    # y = 7.50 gives 7.43..7.57 — flush with the stub top, fully on metal.
    'C1': [('IN', 'M1', 1.0, 5.0), ('TAP', 'M2', 6.0, 7.50)],
    # C3: 4 independent pairs. Wire centre y values measured from the generated
    # GDS (struct_C3.gds): each pair is (P, Q); P is the left end, Q the right.
    'C3': [('P0', 'M1', 1.0, 1.00), ('Q0', 'M1', 10.0, 1.28),
           ('P1', 'M1', 1.0, 3.42), ('Q1', 'M1', 10.0, 3.76),
           ('P2', 'M1', 1.0, 5.90), ('Q2', 'M1', 10.0, 6.32),
           ('P3', 'M1', 1.0, 8.46), ('Q3', 'M1', 10.0, 9.10)],
    'C4': [],
    'D': [],
    'E': [],
}


def pin_rect(layer, x, y):
    """A small legal landing at the endpoint, sized to the layer min width."""
    w = 0.14 if layer in ('M1', 'M2') else 0.30
    return (x - w / 2, y - w / 2, x + w / 2, y + w / 2)


def verify_pin_on_metal(ly, top, layer, px, py):
    """A LEF PIN is only honest if its landing actually sits on this layer's
    drawn geometry.

    (probe - metal).is_empty() is True when the probe point is fully covered by
    metal — that is the PASS condition. An earlier version of this function
    returned `not (...).is_empty()`, which inverted the test and reported every
    valid pin as missing; the geometry itself was always correct.
    """
    li = ly.find_layer(*L[layer])
    if li is None:
        return False
    r = pya.Region()
    it = top.begin_shapes_rec(li)
    while not it.at_end():
        s = it.shape(); t = it.trans()
        if s.is_box():
            r.insert(s.box.transformed(t))
        elif s.is_polygon():
            r.insert(s.polygon.transformed(t))
        elif s.is_path():
            r.insert(s.path.transformed(t).simple_polygon())
        it.next()
    x = int(round(px / DBU)); y = int(round(py / DBU))
    probe = pya.Region(pya.Box(x, y, x + 1, y + 1))
    return (probe - r).is_empty()


def emit(tag, cell_name, bbox, layer_counts, pins):
    """LEF coordinates are measured from the MACRO's own ORIGIN, which we set to
    the GDS bbox lower-left. The structure GDS is drawn in absolute coordinates
    that do NOT start at (0,0) (e.g. struct_A spans x 0.93..9.07), so every pin
    coordinate must be shifted by the bbox origin before emit."""
    lines = []
    lines.append('VERSION 5.7 ;')
    lines.append('BUSBITCHARS "[]" ;')
    lines.append('DIVIDERCHAR "/" ;')
    lines.append('MACRO %s' % cell_name)
    lines.append('  CLASS BLOCK ;')
    lines.append('  ORIGIN %.3f %.3f ;' % (bbox[0], bbox[1]))
    lines.append('  SIZE %.3f BY %.3f ;' % (bbox[2] - bbox[0], bbox[3] - bbox[1]))
    lines.append('  SYMMETRY X Y ;')
    for name, layer, x, y in pins:
        # shift absolute -> macro-local
        lx, ly_ = x - bbox[0], y - bbox[1]
        x0, y0, x1, y1 = pin_rect(layer, lx, ly_)
        lines.append('  PIN %s' % name)
        lines.append('    DIRECTION INOUT ;')
        lines.append('    USE SIGNAL ;')
        lines.append('    PORT')
        lines.append('      LAYER %s ;' % LEF_LAYER[layer])
        lines.append('        RECT %.3f %.3f %.3f %.3f ;' % (x0, y0, x1, y1))
        lines.append('    END')
        lines.append('  END %s' % name)
    lines.append('END %s' % cell_name)
    lines.append('END LIBRARY')
    return '\n'.join(lines) + '\n'


def main():
    man = json.load(open(os.path.join(OUT, 'v2_structures_manifest.json'),
                         encoding='utf-8'))
    idx = {}
    for tag, m in man['structures'].items():
        p = m['gds']
        ly = pya.Layout()
        ly.read(p)
        top = ly.top_cell()
        bb = top.bbox()
        bbox = [bb.left * DBU, bb.bottom * DBU, bb.right * DBU, bb.top * DBU]
        counts = {}
        for k, (ln, dt) in L.items():
            li = ly.find_layer(ln, dt)
            if li is None:
                counts[k] = 0
                continue
            n = sum(1 for _ in top.shapes(li).each())
            counts[k] = n
        pins = PINS.get(tag, [])
        # every declared PIN must sit on real geometry of its own layer
        pin_checks = []
        for name, layer, x, y in pins:
            ok = verify_pin_on_metal(ly, top, layer, x, y)
            pin_checks.append({'name': name, 'layer': layer,
                               'x': x, 'y': y, 'on_metal': ok})
        bad_pins = [p for p in pin_checks if not p['on_metal']]
        if bad_pins:
            print('WARNING %s: %d PIN(s) not on drawn metal: %s'
                  % (tag, len(bad_pins), [p['name'] for p in bad_pins]))

        lef = emit(tag, m['cell'], bbox, counts, pins)
        lp = os.path.join(OUT, 'struct_%s.lef' % tag)
        open(lp, 'w', encoding='utf-8', newline='\n').write(lef)
        idx[tag] = {
            'cell': m['cell'],
            'lef': lp,
            'gds': p,
            'bbox_um': [round(v, 3) for v in bbox],
            'size_um': [round(bbox[2] - bbox[0], 3), round(bbox[3] - bbox[1], 3)],
            'layers': counts,
            'pins': pin_checks,
            'pins_all_on_metal': len(bad_pins) == 0,
            'electrical': bool(pins),
        }

    out = os.path.join(OUT, 'macro_index.json')
    json.dump(idx, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('%-4s %-20s %-22s %-8s %s' % ('tag', 'cell', 'size_um', 'pins', 'elec'))
    for tag in sorted(idx):
        e = idx[tag]
        print('%-4s %-20s %-22s %-8d %s'
              % (tag, e['cell'], e['size_um'], len(e['pins']),
                 'YES' if e['electrical'] else 'NO (NON_ELECTRICAL)'))
    print('written', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
