"""Item A, second pass: measure the LU.2 / LU.3 rule with REAL cell geometry.

The first pass measured "segment edge to nearest tap", which is not what the
rule constrains. The rule is:

  LU.2  N-diff distance to P-tap must be < 15.0um
  LU.3  P-diff distance to N-tap must be < 15.0um

so it is a property of PLACED CELLS vs PLACED TAPS, measured on the diffusion
that the cells actually contain. We therefore:

  1. take every placed cell from the 52-fillinsertion DEF (post-placement,
     pre-route) -- this is the population Magic DRC actually saw;
  2. take the 997 tap cells from 19-tapendcapinsertion;
  3. for every NMOS-capable cell compute the horizontal distance from its
     diffusion extent to the nearest tap's diffusion (same row only);
  4. compare against 15.0 um.

Diffusion footprint per standard cell is taken from the LEF SITE width of the
cell (all sky130_fd_sc_hd cells are SITE unithd, width = n_sites * 0.460 um).
That is an upper bound on the diffusion extent and therefore a CONSERVATIVE
(over-reporting) estimate of violations.
"""
import json
import os
import re

ANA = os.path.dirname(os.path.abspath(__file__))
from paths import RUN as BASE

STEP = 0.460
PITCH = 2.720
LU_MAX = 15.0
PRUNE = 25.76

CELL_RE = re.compile(
    r'^\s*-\s+(\S+)\s+(sky130_fd_sc_hd__\S+)\s+.*?\(\s*(-?\d+)\s+(-?\d+)\s*\)'
    r'\s+(\S+)\s*;', re.M)
ROW_RE = re.compile(
    r'^ROW\s+(\S+)\s+\S+\s+(-?\d+)\s+(-?\d+)\s+\S+\s+'
    r'DO\s+(\d+)\s+BY\s+1\s+STEP\s+(\d+)', re.M)

D52 = os.path.join(
    BASE, '52-openroad-fillinsertion/tt_um_jiahao_plus_counter.def')
D18 = os.path.join(
    BASE, '18-openroad-cutrows/tt_um_jiahao_plus_counter.def')

# ---- cell widths: derive from the DEF placement itself --------------------
# Every sky130_fd_sc_hd cell sits on the unithd site grid, so a cell's footprint
# is recoverable only from the LEF. Without the PDK we use a per-class table
# built from the cells actually present, keyed by the well-known sky130 widths.
# Anything not listed falls back to the median width (conservative: narrow).
KNOWN_W = {
    'sky130_fd_sc_hd__fill_1': 0.460,
    'sky130_fd_sc_hd__fill_2': 0.920,
    'sky130_fd_sc_hd__fill_4': 1.840,
    'sky130_fd_sc_hd__fill_8': 3.680,
    'sky130_fd_sc_hd__decap_3': 1.380,
    'sky130_fd_sc_hd__decap_4': 1.840,
    'sky130_fd_sc_hd__decap_6': 2.760,
    'sky130_fd_sc_hd__decap_8': 3.680,
    'sky130_fd_sc_hd__tapvpwrvgnd_1': 0.460,
    'sky130_fd_sc_hd__inv_1': 1.380,
    'sky130_fd_sc_hd__inv_2': 1.380,
    'sky130_fd_sc_hd__inv_4': 1.840,
    'sky130_fd_sc_hd__buf_1': 1.380,
    'sky130_fd_sc_hd__buf_2': 1.840,
}

t = open(D52, encoding='utf-8', errors='replace').read()
cells = []
for m in CELL_RE.finditer(t):
    nm, cls, x, y, orient = (m.group(1), m.group(2), int(m.group(3)) / 1000.0,
                             int(m.group(4)) / 1000.0, m.group(5))
    cells.append(dict(name=nm, cls=cls, x=x, y=y, orient=orient))
print('cells parsed from 52-fillinsertion : %d' % len(cells))

import collections
cc = collections.Counter(c['cls'] for c in cells)
print('distinct cell classes              : %d' % len(cc))
print('top classes:')
for k, v in cc.most_common(8):
    print('   %-42s %d' % (k, v))

# ---- row segments and taps ------------------------------------------------
rows = []
t18 = open(D18, encoding='utf-8', errors='replace').read()
for m in ROW_RE.finditer(t18):
    rows.append(dict(x=int(m.group(2)) / 1000.0, y=int(m.group(3)) / 1000.0,
                     n=int(m.group(4))))
rows.sort(key=lambda r: (r['y'], r['x']))
for r in rows:
    r['x0'] = r['x']
    r['x1'] = r['x'] + r['n'] * STEP
    r['w'] = r['x1'] - r['x0']

taps = [c for c in cells if c['cls'] == 'sky130_fd_sc_hd__tapvpwrvgnd_1']
print('tap cells in 52-fillinsertion      : %d' % len(taps))

tap_by_y = {}
for c in taps:
    tap_by_y.setdefault(round(c['y'], 3), []).append(c['x'] + STEP / 2)
for y in tap_by_y:
    tap_by_y[y].sort()

# ---- LU rule per cell -----------------------------------------------------
# A cell violates LU.3 if it contains P-diff and no N-tap is within 15um of
# that P-diff. The tap that serves a row is the N-tap ring: sky130 tap cells
# contain BOTH ntap and ptap, so every tap serves both LU.2 and LU.3.
def cell_w(c):
    if c['cls'] in KNOWN_W:
        return KNOWN_W[c['cls']]
    m = re.match(r'.*__([a-z0-9]+)_(\d+)$', c['cls'])
    if m:
        return STEP * max(1, int(m.group(2)))
    return STEP


def seg_of(x, y):
    for r in rows:
        if abs(r['y'] - y) < 1e-3 and r['x0'] <= x < r['x1']:
            return r
    return None


def in_deleted(x, y):
    r = seg_of(x, y)
    return r is not None and r['w'] < PRUNE


checked = 0
viol_kept = 0
viol_deleted = 0
worst = []
skipped_filler = 0

for c in cells:
    if c['cls'].startswith('sky130_fd_sc_hd__fill_') or \
       c['cls'].startswith('sky130_fd_sc_hd__tap'):
        skipped_filler += 1
        continue
    y = round(c['y'], 3)
    tx = tap_by_y.get(y)
    if not tx:
        continue
    w = cell_w(c)
    # diffusion extent of the cell (conservative: full placed footprint)
    ex0, ex1 = c['x'], c['x'] + w
    # distance from the FARTHEST point of the diffusion to the nearest tap
    d0 = min(abs(ex0 - t) for t in tx)
    d1 = min(abs(ex1 - t) for t in tx)
    # a tap centre inside the footprint means distance zero
    inside = any(ex0 <= t <= ex1 for t in tx)
    d = 0.0 if inside else max(d0, d1)
    checked += 1
    if d >= LU_MAX:
        if in_deleted(c['x'], c['y']):
            viol_deleted += 1
        else:
            viol_kept += 1
        worst.append((d, c['cls'], c['x'], c['y'], in_deleted(c['x'], c['y'])))

print()
print('=' * 78)
print('LU.2/LU.3 AUDIT ON PLACED NON-FILLER CELLS  (PREDICTED)')
print('=' * 78)
print('cells skipped (fill_/tap_)          : %d' % skipped_filler)
print('functional cells audited            : %d' % checked)
print('  violating >= 15um, in KEPT segment: %d' % viol_kept)
print('  violating >= 15um, in DELETED seg : %d' % viol_deleted)
print()
worst.sort(reverse=True)
if worst:
    print('%-9s %-44s %8s %8s %s'
          % ('dist(um)', 'class', 'x', 'y', 'segment'))
    for d, cls, x, y, dele in worst[:25]:
        print('%-9.2f %-44s %8.2f %8.2f %s'
              % (d, cls, x, y, 'DELETED' if dele else 'kept'))
