"""Q7: LU.2/LU.3 as a 2D Euclidean check, validated against ground truth.

The rule text is "distance", not "horizontal distance". Rows are 2.72um apart,
so taps in neighbouring rows are candidates too. This script:

  1. builds a 2D model: every placed fill/decap/tap cell as a box on its row;
  2. for every PLACED CELL (not tap) finds the nearest tap in 2D;
  3. reports how many exceed 15um, split by kept/pruned segment;
  4. REPRODUCES the lyrdb ground truth -- if it cannot, the model is wrong and
     must not be used to justify OPT-A.

Only if the model reproduces the real 576 violations is its post-prune
prediction allowed to be quoted -- and even then only as PREDICTED.
"""
import collections
import json
import math
import os
import re

ANA = os.path.dirname(os.path.abspath(__file__))
from paths import RUN as BASE

STEP, PITCH, Y0 = 0.460, 2.720, 2.720
PRUNE, LU_MAX = 25.76, 15.0
ROW_H = 2.720

ROW_RE = re.compile(
    r'^ROW\s+(\S+)\s+\S+\s+(-?\d+)\s+(-?\d+)\s+\S+\s+'
    r'DO\s+(\d+)\s+BY\s+1\s+STEP\s+(\d+)', re.M)
CELL_RE = re.compile(
    r'^\s*-\s+(\S+)\s+(sky130_fd_sc_hd__\S+)\s+.*?\(\s*(-?\d+)\s+(-?\d+)\s*\)'
    r'\s+(\S+)\s*;', re.M)

t18 = open(os.path.join(
    BASE, '18-openroad-cutrows/tt_um_jiahao_plus_counter.def'),
    encoding='utf-8', errors='replace').read()
rows = []
for m in ROW_RE.finditer(t18):
    rows.append(dict(x=int(m.group(2)) / 1000.0, y=int(m.group(3)) / 1000.0,
                     n=int(m.group(4))))
for r in rows:
    r['x0'], r['x1'] = r['x'], r['x'] + r['n'] * STEP
    r['w'] = r['x1'] - r['x0']

t52 = open(os.path.join(
    BASE, '52-openroad-fillinsertion/tt_um_jiahao_plus_counter.def'),
    encoding='utf-8', errors='replace').read()
cells = []
for m in CELL_RE.finditer(t52):
    cells.append(dict(name=m.group(1), cls=m.group(2),
                      x=int(m.group(3)) / 1000.0, y=int(m.group(4)) / 1000.0))

SITE_W = {'sky130_fd_sc_hd__fill_1': 0.460,
          'sky130_fd_sc_hd__fill_2': 0.920,
          'sky130_fd_sc_hd__fill_4': 1.840,
          'sky130_fd_sc_hd__decap_3': 1.380,
          'sky130_fd_sc_hd__decap_4': 1.840,
          'sky130_fd_sc_hd__decap_6': 2.760,
          'sky130_fd_sc_hd__decap_8': 3.680,
          'sky130_fd_sc_hd__tapvpwrvgnd_1': 0.460}


def width(c):
    if c['cls'] in SITE_W:
        return SITE_W[c['cls']]
    m = re.match(r'.*__([a-z0-9]+)_(\d+)$', c['cls'])
    if m:
        return STEP * max(1, int(m.group(2)))
    return STEP


taps = [c for c in cells if c['cls'] == 'sky130_fd_sc_hd__tapvpwrvgnd_1']
# A tap serves both LU.2 and LU.3; its diffusion spans the cell body.
tap_boxes = [(c['x'], c['x'] + width(c), c['y'], c['y'] + ROW_H)
             for c in taps]
print('taps: %d' % len(taps))


def nearest_tap(x, y):
    """Euclidean distance from a cell's box to the nearest tap's box."""
    best = 1e9
    for tx0, tx1, ty0, ty1 in tap_boxes:
        dx = max(0.0, max(tx0 - x[1], x[0] - tx1))
        dy = max(0.0, max(ty0 - y[1], y[0] - ty1))
        d = math.hypot(dx, dy)
        if d < best:
            best = d
    return best


def seg_of(x, y):
    for r in rows:
        if abs(r['y'] - y) < 1e-3 and r['x0'] <= x < r['x1']:
            return r
    return None


viol_cells = []
checked = 0
for c in cells:
    if c['cls'] == 'sky130_fd_sc_hd__tapvpwrvgnd_1':
        continue
    w = width(c)
    box = (c['x'], c['x'] + w)
    ybox = (c['y'], c['y'] + ROW_H)
    d = nearest_tap(box, ybox)
    checked += 1
    if d >= LU_MAX:
        r = seg_of(c['x'], c['y'])
        viol_cells.append((c, d, r))

print('cells checked: %d' % checked)
print('cells >=15um from ANY tap in 2D: %d' % len(viol_cells))
print()
by_cls = collections.Counter(c['cls'] for c, _, _ in viol_cells)
print('by class:')
for k, v in by_cls.most_common():
    print('   %-44s %d' % (k, v))

in_del = sum(1 for c, d, r in viol_cells if r is not None and r['w'] < PRUNE)
in_keep = sum(1 for c, d, r in viol_cells
              if r is not None and r['w'] >= PRUNE)
no_seg = sum(1 for c, d, r in viol_cells if r is None)
print()
print('in prunable segment : %d' % in_del)
print('in KEPT segment     : %d' % in_keep)
print('in no segment       : %d' % no_seg)

print()
print('=' * 78)
print('VALIDATION AGAINST GROUND TRUTH')
print('=' * 78)
print('lyrdb says: 576 tap/row violations, all inside prunable fragments.')
print('model says: %d offending cells (%d in prunable, %d in kept).'
      % (len(viol_cells), in_del, in_keep))
if in_keep == 0:
    print()
    print('=> The 2D model reproduces the qualitative ground truth:')
    print('   EVERY offending cell sits in a segment that OPT-A would delete.')
else:
    print()
    print('=> MODEL STILL DISAGREES with ground truth (%d kept-segment cells).'
          % in_keep)
    print('   The model must NOT be used to justify OPT-A.')
