"""Part B, Q13: do the research macro cells in the FINAL GDS actually carry
their geometry, and are the 93 enclosure violations inside that geometry?

Fixes the earlier DBox-vs-Box transform bug: use cell.bbox() (dbu ints) and
convert once at the end.
"""
import os

import klayout.db as db

from paths import RUN as BASE
GDS = os.path.join(BASE, 'final/gds/tt_um_jiahao_plus_counter.gds')
from paths import REPO as TT

ly = db.Layout()
ly.read(GDS)
top = ly.top_cell()
dbu = ly.dbu

MACROS = ['research_branch', 'research_via1', 'research_via2',
          'research_near', 'research_cross', 'research_dense',
          'research_fiducial']

print('=' * 78)
print('MACRO CELLS IN THE FINAL STREAMED GDS -- shape inventory')
print('=' * 78)
for cls in MACROS:
    cell = ly.cell(cls)
    if cell is None:
        print('  %-18s ABSENT' % cls)
        continue
    b = cell.bbox()                 # db.Box in dbu
    bu = b.to_dtype(dbu)
    tot = 0
    per = []
    for li in ly.layer_indexes():
        sh = cell.shapes(li)
        n = sh.size()
        if n:
            tot += n
            per.append('%s/%s:%d' % (ly.get_info(li).layer,
                                     ly.get_info(li).datatype, n))
    print('  %-18s shapes=%-5d local bbox=(%.3f,%.3f)-(%.3f,%.3f)'
          % (cls, tot, bu.left, bu.bottom, bu.right, bu.top))
    print('       %s' % ' '.join(per[:14]))

print()
print('=' * 78)
print('ABSOLUTE FOOTPRINT OF EACH INSTANCE (fixed transform)')
print('=' * 78)
for cls in MACROS:
    cell = ly.cell(cls)
    if cell is None:
        continue
    b = cell.bbox()
    for i in top.each_inst():
        if i.cell.name != cls:
            continue
        ab = (i.trans * b).to_dtype(dbu)
        print('  %-18s trans=%-22s ABS (%.3f,%.3f)-(%.3f,%.3f)'
              % (cls, str(i.trans), ab.left, ab.bottom, ab.right, ab.top))
        break

print()
print('=' * 78)
print('THE AUTHORING GDS vs THE STREAMED INSTANCE')
print('=' * 78)
STEM = {'research_branch': 'struct_C1', 'research_via1': 'struct_A',
        'research_via2': 'struct_B'}
for cls, stem in STEM.items():
    p = os.path.join(TT, 'macros/out', stem + '.gds')
    ly2 = db.Layout()
    ly2.read(p)
    t2 = ly2.top_cell()
    b2 = t2.bbox().to_dtype(ly2.dbu)
    n2 = sum(ly2.top_cell().shapes(li).size()
             for li in ly2.layer_indexes())
    cell = ly.cell(cls)
    n1 = sum(cell.shapes(li).size() for li in ly.layer_indexes()) if cell else -1
    print('  %-18s authoring: %-5d shapes bbox=(%.3f,%.3f)-(%.3f,%.3f)'
          % (cls, n2, b2.left, b2.bottom, b2.right, b2.top))
    print('       streamed: %-5d shapes' % n1)

print()
print('=' * 78)
print('ARE THE VIOLATIONS INSIDE THE *STREAMED INSTANCE* BBOX?')
print('=' * 78)
import json
ANA = os.path.dirname(os.path.abspath(__file__))
viol = json.load(open(os.path.join(ANA, 'magic_violations.json'),
                      encoding='utf-8'))
ENC = ('via.5a', 'met2.5', 'via2.4a')
enc = [v for v in viol if v['category'] in ENC]

boxes = []
for cls in MACROS:
    cell = ly.cell(cls)
    if cell is None:
        continue
    b = cell.bbox()
    for i in top.each_inst():
        if i.cell.name != cls:
            continue
        ab = (i.trans * b).to_dtype(dbu)
        boxes.append((cls, ab.left, ab.bottom, ab.right, ab.top))
        break

import collections
inside = collections.Counter()
out = 0
for v in enc:
    hit = None
    for (cls, x0, y0, x1, y1) in boxes:
        if x0 - 0.02 <= v['cx'] <= x1 + 0.02 and \
                y0 - 0.02 <= v['cy'] <= y1 + 0.02:
            hit = cls
            break
    if hit:
        inside[hit] += 1
    else:
        out += 1
print('  inside a streamed macro instance bbox: %d / %d' % (sum(inside.values()),
                                                            len(enc)))
for k, v in inside.most_common():
    print('     %-18s %d' % (k, v))
print('  outside every macro: %d' % out)
