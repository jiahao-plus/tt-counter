"""Q12: independent KLayout inspection of the prunable fragments.

The LU.2/LU.3 violations are attributed to fragments. This script verifies,
WITHOUT trusting the lyrdb or my own model, what GDS geometry actually exists
inside those fragments in the final streamed GDS.

Layers (verified map):
  64/20 nwell   65/20 diff   66/20 poly   67/20 li1
  93/44 nsdm    94/20 psdm   68/20 met1   69/20 met2
"""
import json
import os
import sys

import klayout.db as db

ANA = os.path.dirname(os.path.abspath(__file__))
from paths import RUN as BASE
GDS = os.path.join(BASE, 'final/gds/tt_um_jiahao_plus_counter.gds')

LAYERS = {'nwell': (64, 20), 'diff': (65, 20), 'poly': (66, 20),
          'li1': (67, 20), 'nsdm': (93, 44), 'psdm': (94, 20),
          'met1': (68, 20), 'met2': (69, 20)}

if not os.path.exists(GDS):
    print('MISSING', GDS)
    sys.exit(1)

ly = db.Layout()
ly.read(GDS)
top = ly.top_cell()
dbu = ly.dbu
print('GDS      :', GDS)
print('top cell :', top.name, ' dbu =', dbu)

# Fragment boxes from the cut_rows DEF (x0, x1, y0) plus row height.
FRAGS = [
    (2.76, 13.34, 138.72, 163.20),   # left fragment A, rows 51..59 window
    (2.76, 13.80, 195.84, 220.32),   # left fragment B
    (84.18, 92.00, 179.52, 193.12),  # middle fragment
]

print()
print('=' * 78)
print('GEOMETRY INSIDE THE PRUNABLE FRAGMENTS (final GDS)')
print('=' * 78)
for (x0, x1, y0, y1) in FRAGS:
    print()
    print('fragment x=[%.2f..%.2f]  y=[%.2f..%.2f]' % (x0, x1, y0, y1))
    box = db.DBox(int(round(x0 / dbu)), int(round(y0 / dbu)),
                  int(round(x1 / dbu)), int(round(y1 / dbu)))
    for nm, (l, d) in LAYERS.items():
        if not ly.layer(l, d):
            continue
        li = ly.layer(l, d)
        try:
            reg = db.Region(top.begin_shapes_rec(li))
        except Exception as e:
            print('   %-6s ERROR %s' % (nm, e))
            continue
        reg.merge()
        clip = reg & db.Region(box)
        if clip.is_empty():
            continue
        n = clip.count()
        area = sum(p.area() for p in clip.each())
        print('   %-6s %3d shapes   area=%10.0f dbu^2 (%.4f um^2)'
              % (nm, n, area, area * dbu * dbu))
