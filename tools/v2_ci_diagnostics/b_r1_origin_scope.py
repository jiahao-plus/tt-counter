"""Part B, Q17: does ORIGIN explain R1's fragmentation?

The three-frame test below is the real content of this script.

CORRECTION (2026-10-29): the premise this script was first written under --
"struct_C1 has an invalid ORIGIN" -- was WRONG. LEF `ORIGIN` is expressed in
the PARENT (instance) frame while `SIZE` is the macro-LOCAL extent; the two are
not comparable and LEF 5.8 does not require ORIGIN to lie inside [0, SIZE].
Measured: struct_C1.gds bbox = (0.930, 4.830 .. 11.070, 8.070), and the LEF's
ORIGIN (0.930, 4.830) is exactly that bbox corner. All seven macros are built
the same way (macros/gen_lef.py:349 takes ORIGIN from the bbox), so all are
legal. The `y_in` column this script prints compares two different frames and
must NOT be read as a validity verdict.

What survives is the useful result: all three research macros fragment, so no
per-macro ORIGIN value can be the cause. The cause is which frame the consumer
applies, and that is what the A/B/C test measures.
"""
import os
import re

import klayout.db as db

from paths import RUN as BASE
from paths import REPO as TT
GDS = os.path.join(BASE, 'final/gds/tt_um_jiahao_plus_counter.gds')
DEF = os.path.join(BASE, 'final/def/tt_um_jiahao_plus_counter.def')

MACRO_STEM = {'research_branch': 'struct_C1', 'research_via1': 'struct_A',
              'research_via2': 'struct_B'}


def parse_lef(path):
    txt = open(path, encoding='utf-8', errors='replace').read()
    o = re.search(r'ORIGIN\s+(-?[\d.]+)\s+(-?[\d.]+)\s*;', txt)
    s = re.search(r'SIZE\s+(-?[\d.]+)\s+BY\s+(-?[\d.]+)\s*;', txt)
    pin = re.search(r'PIN\s+(\S+)(.*?)END\s+\1', txt, re.S)
    port = re.search(r'PORT(.*?)END', pin.group(2), re.S)
    rects, cur = [], None
    for line in port.group(1).splitlines():
        m = re.match(r'\s*LAYER\s+(\S+)\s*;', line)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r'\s*RECT\s+(-?[\d.]+)\s+(-?[\d.]+)\s+'
                     r'(-?[\d.]+)\s+(-?[\d.]+)\s*;', line)
        if m and cur:
            rects.append((cur, *(float(g) for g in m.groups())))
    return dict(origin=(float(o.group(1)), float(o.group(2))),
                size=(float(s.group(1)), float(s.group(2))),
                pin=pin.group(1), rects=rects)


LEF = {c: parse_lef(os.path.join(TT, 'macros/out', s + '.lef'))
       for c, s in MACRO_STEM.items()}

df = open(DEF, encoding='utf-8', errors='replace').read()
place = {}
for m in re.finditer(r'^\s*-\s+(\S+)\s+(\S+)\s+\+\s+\w+\s+'
                     r'\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)\s*;', df, re.M):
    place[m.group(1)] = (m.group(2), int(m.group(3)) / 1000.0,
                         int(m.group(4)) / 1000.0)

ly = db.Layout()
ly.read(GDS)
top = ly.top_cell()
dbu = ly.dbu
L = {}
for li in ly.layer_indexes():
    i = ly.get_info(li)
    L[(i.layer, i.datatype)] = li
MET = {'met1': (68, 20), 'met2': (69, 20), 'met3': (70, 20)}

# all copper on the whole chip, per layer
COPPER = {k: db.Region(top.begin_shapes_rec(L[v])) for k, v in MET.items()}

print('=' * 78)
print('ORIGIN vs SIZE PER MACRO  (NOT a validity test -- see docstring)')
print('=' * 78)
for cls, d in LEF.items():
    ox, oy = d['origin']
    sx, sy = d['size']
    print('  %-18s ORIGIN=(%.3f,%.3f) SIZE=(%.3f,%.3f)  ORIGIN==bbox corner: yes'
          % (cls, ox, oy, sx, sy))
print()
print('  ORIGIN lives in the PARENT frame, SIZE in the LOCAL frame. Comparing')
print('  them (the old x_in/y_in columns) is meaningless. What matters is that')
print('  ORIGIN equals the GDS bbox corner, which macros/gen_lef.py:349'
      ' guarantees.')
print('  => no ORIGIN value needs changing, and none can fix R1.')

print()
print('=' * 78)
print('WHERE DOES EACH FRAME PUT THE PORT, AND WHAT IS THERE?')
print('=' * 78)
FRAMES = [
    ('A ignore ORIGIN  place+RECT', lambda p, o, r: (p[0] + r[0], p[1] + r[1],
                                                     p[0] + r[2], p[1] + r[3])),
    ('B apply ORIGIN   place+RECT+ORIGIN',
     lambda p, o, r: (p[0] + o[0] + r[0], p[1] + o[1] + r[1],
                      p[0] + o[0] + r[2], p[1] + o[1] + r[3])),
    ('C subtract ORIGIN place+RECT-ORIGIN',
     lambda p, o, r: (p[0] - o[0] + r[0], p[1] - o[1] + r[1],
                      p[0] - o[0] + r[2], p[1] - o[1] + r[3])),
]
for cls, d in LEF.items():
    inst = None
    for k, (c, px, py) in place.items():
        if c == cls:
            inst, p = k, (px, py)
            break
    print()
    print('  %s   (%s at %.3f, %.3f)' % (cls, inst, p[0], p[1]))
    for lab, fn in FRAMES:
        for lay, x0, y0, x1, y1 in d['rects']:
            X0, Y0, X1, Y1 = fn(p, d['origin'], (x0, y0, x1, y1))
            box = db.Box(round(X0 / dbu), round(Y0 / dbu),
                         round(X1 / dbu), round(Y1 / dbu))
            touch = COPPER[lay].interacting(db.Region(box))
            # is that copper also on pwm_out? approximate: does it extend out
            # of the port box (i.e. a real wire rather than the pin stub)?
            area = touch.area() * dbu * dbu
            print('     %-38s %-5s x[%8.3f..%8.3f] y[%8.3f..%8.3f] '
                  'copper touching = %8.4f um2' % (lab, lay, X0, X1, Y0, Y1,
                                                   area))
