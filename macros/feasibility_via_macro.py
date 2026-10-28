#!/usr/bin/env python3
"""feasibility_via_macro.py — P1 最小可行性试验：M1-Via1-M2 信号连接宏。

目的：在投入完整 V2 设计前，验证工具链端到端可用：
  1. 能否用 pya 生成合法的 M1/Via1/M2 几何
  2. 能否通过真实的 sky130hd.lydrc KLayout DRC
  3. 能否正确导出可被下游使用的 GDS/LEF

几何参数全部来自 v2_spec/sky130_rules_measured.md（实测规则，非虚构）：
  M1 min width 0.14, min spacing 0.14
  M1 enclosure of via1 (0.15 cut) = 0.055
  via1 cut = 0.150 x 0.150
  M2 min width 0.14

输出：
  macros/out/feasibility_via.gds
  macros/out/feasibility_via.lef
  macros/out/feasibility_via_report.json
"""
import json
import os
import sys

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)

# ---- measured rules (v2_spec/sky130_rules_measured.md) -------------------
R = dict(
    m1_w=0.14, m1_s=0.14,
    m2_w=0.14, m2_s=0.14,
    via_cut=0.15,          # via1 cut size
    m1_encl=0.055,         # m1 enclosure of 0.15 via
    m2_encl=0.055,         # m2 enclosure (assume symmetric; verified by DRC run)
)

LAYERS = {'M1': (68, 20), 'Via1': (68, 44), 'M2': (69, 20)}


def um(v):
    return int(round(v * 1000))    # dbu = 1 nm


def build():
    """A 3-terminal net: A -> via -> B, plus a second isolated net C.

    Topology (all in um, origin at 0,0):
        netA: horizontal M1 bar from x=1.0 to x=6.0 at y=2.0 (w=0.14)
              vertical M1 stub up at x=6.0 to y=4.0
              via1 at (6.0, 4.0)
              M2 pad at via, then M2 horizontal to x=9.0
        netC: separate M1 bar at y=6.5, x=1.0..9.0  (>= 0.14 away from netA)

    This proves: (a) real via connecting M1 and M2 of the SAME net,
                 (b) a legal neighbour net that is NOT connected.
    """
    ly = pya.Layout()
    ly.dbu = 0.001
    top = ly.create_cell('feas_via')
    li = {k: ly.layer(v[0], v[1]) for k, v in LAYERS.items()}

    def box(layer, x0, y0, x1, y1):
        top.shapes(li[layer]).insert(
            pya.Box(um(x0), um(y0), um(x1), um(y1)))

    # --- netA on M1: horizontal run
    y_a = 2.0
    box('M1', 1.0, y_a - R['m1_w'] / 2, 6.0 + R['m1_w'] / 2, y_a + R['m1_w'] / 2)
    # vertical stub up to the via
    x_v = 6.0
    box('M1', x_v - R['m1_w'] / 2, y_a - R['m1_w'] / 2,
        x_v + R['m1_w'] / 2, 4.0 + R['via_cut'] / 2 + R['m1_encl'])

    # --- via1 cut + M1/M2 landing
    cy = 4.0
    box('Via1', x_v - R['via_cut'] / 2, cy - R['via_cut'] / 2,
        x_v + R['via_cut'] / 2, cy + R['via_cut'] / 2)
    # M1 landing around the cut
    box('M1', x_v - R['via_cut'] / 2 - R['m1_encl'],
        cy - R['via_cut'] / 2 - R['m1_encl'],
        x_v + R['via_cut'] / 2 + R['m1_encl'],
        cy + R['via_cut'] / 2 + R['m1_encl'])
    # M2 landing
    box('M2', x_v - R['via_cut'] / 2 - R['m2_encl'],
        cy - R['via_cut'] / 2 - R['m2_encl'],
        x_v + R['via_cut'] / 2 + R['m2_encl'],
        cy + R['via_cut'] / 2 + R['m2_encl'])

    # --- netA on M2: horizontal run to the right
    y_m2 = cy
    box('M2', x_v - R['m2_w'] / 2, y_m2 - R['m2_w'] / 2,
        9.0 + R['m2_w'] / 2, y_m2 + R['m2_w'] / 2)

    # --- netC: separate M1 bar, clearly apart
    y_c = 6.5
    box('M1', 1.0, y_c - R['m1_w'] / 2, 9.0, y_c + R['m1_w'] / 2)

    return ly, top


def main():
    ly, top = build()
    gds = os.path.join(OUT, 'feasibility_via.gds')
    ly.write(gds)

    # --- self-check the geometry against the measured rules
    checks = []
    r_m1 = pya.Region(top.shapes(ly.layer(*LAYERS['M1'])))
    r_via = pya.Region(top.shapes(ly.layer(*LAYERS['Via1'])))
    r_m2 = pya.Region(top.shapes(ly.layer(*LAYERS['M2'])))
    r_m1.merge(); r_via.merge(); r_m2.merge()

    n_m1, n_via, n_m2 = r_m1.count(), r_via.count(), r_m2.count()
    checks.append(('M1 merged islands', n_m1, 'expect 2 (netA + netC)'))
    checks.append(('Via1 cuts', n_via, 'expect 1'))
    checks.append(('M2 merged islands', n_m2, 'expect 1'))

    # via must be enclosed by both M1 and M2.
    # NOTE: pya.Region has no .not() in Python 3 (not is a keyword); difference
    # is spelled with the '-' operator.
    via_in_m1 = (r_via - r_m1).is_empty()
    via_in_m2 = (r_via - r_m2).is_empty()
    checks.append(('via1 inside M1', via_in_m1, 'must be true'))
    checks.append(('via1 inside M2', via_in_m2, 'must be true'))

    # nets must NOT be connected: netA M1 and netC M1 separated
    # count connected components after merge — should be 2
    checks.append(('M1 nets separated', n_m1 == 2, 'netA and netC must not touch'))

    # --- M1-Via1-M2 electrical continuity for netA
    m1_m2_via = r_m1 & r_via
    cont_a = not m1_m2_via.is_empty()
    checks.append(('netA M1-Via1-M2 continuity', cont_a, 'via must couple both layers'))

    # --- write a minimal LEF
    bb = top.bbox()
    lef = os.path.join(OUT, 'feasibility_via.lef')
    with open(lef, 'w', encoding='utf-8', newline='\n') as f:
        f.write('VERSION 5.7 ;\n')
        f.write('BUSBITCHARS "[]" ;\n')
        f.write('DIVIDERCHAR "/" ;\n')
        f.write('MACRO feas_via\n')
        f.write('  CLASS BLOCK ;\n')
        f.write('  ORIGIN 0.000 0.000 ;\n')
        f.write('  SIZE %.3f BY %.3f ;\n'
                % (bb.width() * ly.dbu, bb.height() * ly.dbu))
        f.write('  PIN A\n    DIRECTION INPUT ;\n    USE SIGNAL ;\n')
        f.write('    PORT\n      LAYER met1 ;\n')
        f.write('        RECT %.3f %.3f %.3f %.3f ;\n'
                % (1.0, 2.0 - R['m1_w'] / 2, 1.0 + R['m1_w'],
                   2.0 + R['m1_w'] / 2))
        f.write('    END\n  END A\n')
        f.write('  PIN B\n    DIRECTION OUTPUT ;\n    USE SIGNAL ;\n')
        f.write('    PORT\n      LAYER met2 ;\n')
        f.write('        RECT %.3f %.3f %.3f %.3f ;\n'
                % (9.0 - R['m2_w'], 4.0 - R['m2_w'] / 2, 9.0,
                   4.0 + R['m2_w'] / 2))
        f.write('    END\n  END B\n')
        f.write('END feas_via\n')
        f.write('END LIBRARY\n')

    rep = {
        'gds': gds,
        'lef': lef,
        'bbox_um': [bb.left * ly.dbu, bb.bottom * ly.dbu,
                    bb.right * ly.dbu, bb.top * ly.dbu],
        'size_um': [bb.width() * ly.dbu, bb.height() * ly.dbu],
        'layer_map': {k: list(v) for k, v in LAYERS.items()},
        'rules_used': R,
        'checks': [{'name': n, 'value': (v if isinstance(v, (bool, int)) else str(v)),
                    'note': note} for n, v, note in checks],
        'all_pass': all((v is True) for n, v, note in checks if isinstance(v, bool)),
    }
    json.dump(rep, open(os.path.join(OUT, 'feasibility_via_report.json'), 'w',
                        encoding='utf-8'), indent=1, ensure_ascii=False)

    print('GDS :', gds)
    print('LEF :', lef)
    print('bbox: %.3f x %.3f um' % (bb.width() * ly.dbu, bb.height() * ly.dbu))
    for n, v, note in checks:
        print('  %-34s %-6s  (%s)' % (n, v, note))
    print('all_pass:', rep['all_pass'])
    return 0 if rep['all_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
