"""Q6: reconcile the lyrdb ground truth with the tap-anchor model.

The model audit (a_lu_audit.py) claimed hundreds of 15um violations inside
KEPT segments, while the lyrdb says there are ZERO there. One of the two is
wrong. This script measures the REAL tap positions per row segment and
computes the actual worst-case diffusion-to-tap distance implied by them.
"""
import collections
import json
import os
import re

ANA = os.path.dirname(os.path.abspath(__file__))
from paths import RUN as BASE

STEP, PITCH, Y0 = 0.460, 2.720, 2.720
PRUNE, LU_MAX = 25.76, 15.0

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
taps = [c for c in cells if c['cls'] == 'sky130_fd_sc_hd__tapvpwrvgnd_1']
tap_by_y = collections.defaultdict(list)
for c in taps:
    tap_by_y[round(c['y'], 3)].append(c['x'])

print('=' * 78)
print('Q6a  REAL TAP OFFSETS INSIDE EACH KEPT SEGMENT')
print('=' * 78)
print('(offset = tap_x - segment_left, in um and in sites)')
print()
kept = [r for r in rows if r['w'] >= PRUNE]
offs = collections.Counter()
first_offs = collections.Counter()
for r in kept:
    tx = sorted(v for v in tap_by_y.get(round(r['y'], 3), [])
                if r['x0'] <= v < r['x1'])
    if not tx:
        continue
    for v in tx:
        offs[round((v - r['x0']) / STEP)] += 1
    first_offs[round((tx[0] - r['x0']) / STEP)] += 1

print('first-tap offset (sites) histogram over %d kept segments:' % len(kept))
for k in sorted(first_offs):
    print('   +%3d sites = %7.3f um : %3d segments'
          % (k, k * STEP, first_offs[k]))

print()
print('all-tap offset (sites) histogram, top 20:')
for k, v in sorted(offs.items())[:20]:
    print('   +%3d sites = %7.3f um : %3d taps' % (k, k * STEP, v))

print()
print('=' * 78)
print('Q6b  IMPLIED WORST-CASE DIFFUSION-TO-TAP DISTANCE, PER SEGMENT')
print('=' * 78)
print('For a segment with taps at t_1<...<t_k the worst legal position is the')
print('largest gap between consecutive taps, or the two end overhangs.')
print()
bad = []
for r in kept:
    tx = sorted(v for v in tap_by_y.get(round(r['y'], 3), [])
                if r['x0'] <= v < r['x1'])
    if not tx:
        bad.append((r, 1e9, 'no tap'))
        continue
    gaps = []
    gaps.append(tx[0] - r['x0'])            # left overhang
    for a, b in zip(tx, tx[1:]):
        gaps.append((b - a) / 2.0)          # half-span, worst point mid-way
    gaps.append(r['x1'] - tx[-1])           # right overhang
    w = max(gaps)
    if w >= LU_MAX:
        bad.append((r, w, 'overhang/gap'))

print('kept segments                        : %d' % len(kept))
print('kept segments whose worst point >=15um: %d' % len(bad))
if bad:
    print()
    print('%-9s %-9s %7s %5s %10s %s'
          % ('y', 'x0', 'w', 'nTap', 'worst(um)', 'reason'))
    for r, w, why in sorted(bad, key=lambda p: -p[1])[:30]:
        tx = [v for v in tap_by_y.get(round(r['y'], 3), [])
              if r['x0'] <= v < r['x1']]
        print('%-9.3f %-9.3f %7.2f %5d %10.2f %s'
              % (r['y'], r['x0'], r['w'], len(tx), w, why))

print()
print('=' * 78)
print('Q6c  TAP SPACING GLOBAL DISTRIBUTION (per row)')
print('=' * 78)
sp = collections.Counter()
for y, xs in tap_by_y.items():
    xs = sorted(xs)
    for a, b in zip(xs, xs[1:]):
        sp[round(b - a, 2)] += 1
print('%-10s %s' % ('gap(um)', 'count'))
for k, v in sorted(sp.items()):
    print('%-10.2f %d' % (k, v))
