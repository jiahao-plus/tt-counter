"""Part B, Q12: ARE THE 93 ENCLOSURE VIOLATIONS INSIDE THE RESEARCH MACROS?

Item A claimed they were "in the macros". The earlier check used a bbox that
was not converted from dbu, so it was wrong. Redo it properly.

Boxes to test:
  (a) LEF bbox, ORIGIN honoured  -> place + ORIGIN .. + SIZE
  (b) LEF bbox, ORIGIN ignored   -> place .. + SIZE
  (c) actual GDS content bbox of the instance, transformed
"""
import collections
import json
import os
import re

import klayout.db as db

from paths import RUN as BASE
ANA = os.path.dirname(os.path.abspath(__file__))
DEF = os.path.join(BASE, 'final/def/tt_um_jiahao_plus_counter.def')
GDS = os.path.join(BASE, 'final/gds/tt_um_jiahao_plus_counter.gds')

viol = json.load(open(os.path.join(ANA, 'magic_violations.json'),
                      encoding='utf-8'))
ENC = ('via.5a', 'met2.5', 'via2.4a')
enc = [v for v in viol if v['category'] in ENC]

df = open(DEF, encoding='utf-8', errors='replace').read()
COMP = re.compile(r'^\s*-\s+(\S+)\s+(\S+)\s+\+\s+\w+\s+'
                  r'\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)\s*;', re.M)
place = {}
for m in COMP.finditer(df):
    place[m.group(1)] = (m.group(2), int(m.group(3)) / 1000.0,
                         int(m.group(4)) / 1000.0)

ORIG = {'research_branch': (0.930, 4.830, 10.140, 3.240),
        'research_via1': (0.930, 1.930, 8.140, 4.940),
        'research_via2': (0.930, 1.930, 10.220, 3.265),
        'research_near': (0.930, 0.930, 10.140, 8.240),
        'research_cross': (0.930, 0.930, 10.140, 8.140),
        'research_dense': (0.500, 0.850, 35.000, 5.790),
        'research_fiducial': (3.000, 3.000, 4.000, 4.000)}

ly = db.Layout()
ly.read(GDS)
top = ly.top_cell()
dbu = ly.dbu

# ---- build the three box families
boxes = {'ORIGIN honoured': [], 'ORIGIN ignored': [], 'GDS content': []}
for inst, (cls, px, py) in place.items():
    if cls not in ORIG:
        continue
    ox, oy, sw, sh = ORIG[cls]
    boxes['ORIGIN honoured'].append((cls, px + ox, py + oy,
                                     px + ox + sw, py + oy + sh))
    boxes['ORIGIN ignored'].append((cls, px, py, px + sw, py + sh))
    cell = ly.cell(cls)
    if cell is None:
        continue
    gb = cell.dbbox()
    for i in top.each_inst():
        if i.cell.name != cls:
            continue
        ab = (i.trans * gb).to_dtype(dbu)
        boxes['GDS content'].append((cls, ab.left, ab.bottom,
                                     ab.right, ab.top))
        break

print('=' * 78)
print('THE 93 ENCLOSURE VIOLATIONS vs EACH BOX FAMILY')
print('=' * 78)
print('  total enclosure violations: %d' % len(enc))
print()
for fam, bl in boxes.items():
    inside = collections.Counter()
    out = 0
    for v in enc:
        hit = None
        for (cls, x0, y0, x1, y1) in bl:
            if x0 - 0.02 <= v['cx'] <= x1 + 0.02 and \
                    y0 - 0.02 <= v['cy'] <= y1 + 0.02:
                hit = cls
                break
        if hit:
            inside[hit] += 1
        else:
            out += 1
    print('  %-18s inside=%3d  outside=%3d   %s'
          % (fam, sum(inside.values()), out,
             dict(inside) if inside else ''))

print()
print('=' * 78)
print('BOX TABLE')
print('=' * 78)
for fam, bl in boxes.items():
    print('  %s:' % fam)
    for (cls, x0, y0, x1, y1) in bl:
        print('     %-18s x[%7.2f..%7.2f] y[%7.2f..%7.2f]'
              % (cls, x0, x1, y0, y1))

print()
print('=' * 78)
print('WHERE ARE THE VIOLATIONS, CLUSTERED?')
print('=' * 78)
pts = sorted((round(v['cx'], 1), round(v['cy'], 1), v['category']) for v in enc)
cl = collections.Counter((round(v['cx'] / 2) * 2, round(v['cy'] / 2) * 2)
                         for v in enc)
for (x, y), n in sorted(cl.items()):
    print('     x~%6.1f y~%6.1f  %3d %s' % (x, y, n, '#' * min(n, 40)))

print()
print('=' * 78)
print('RULE TEXT')
print('=' * 78)
s = open(os.path.join(BASE, '62-magic-drc/reports/drc.magic.lyrdb'),
         encoding='utf-8', errors='replace').read()
for m in re.finditer(r"<category><name>([^<]+)</name><description>([^<]+)"
                     r"</description></category>", s):
    if m.group(1) in ENC:
        print('  %-10s %s' % (m.group(1), m.group(2)))
