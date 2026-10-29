"""Q11: is 25.76um an INDEPENDENT physical threshold, or a fitted artefact?

The user's objection is sharp and correct: a threshold fitted to the tap
X-gap distribution is not a physical justification. This script separates the
two possible derivations and reports which one actually holds.

Derivation A (FITTED, rejectable):
    "25.76 = 2 * measured tap spacing" -- a statistical fit of observed tap
    positions. If this were the only basis, the threshold would be arbitrary:
    any value between 11.05 and 51.06 gives the same result, so the exact
    number carries no physical meaning.

Derivation B (PHYSICAL, testable):
    A tap cell is a real cell of finite width. For a segment to host at least
    one tap, it must be at least (tap body width) wide, AND the anchor rule
    must place that tap inside the segment. Both are checkable against the
    real 997 taps.

We test B directly: find the NARROWEST segment that actually received a tap.
That width is the empirical minimum viable segment. Any threshold below it is
proven safe; any threshold above it risks deleting a tap-bearing segment.
"""
import collections
import os
import re

from paths import RUN as BASE
STEP, PITCH, Y0 = 0.460, 2.720, 2.720

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
    r['w'] = r['n'] * STEP
    r['x1'] = r['x'] + r['w']

t52 = open(os.path.join(
    BASE, '52-openroad-fillinsertion/tt_um_jiahao_plus_counter.def'),
    encoding='utf-8', errors='replace').read()
cells = []
for m in CELL_RE.finditer(t52):
    cells.append(dict(name=m.group(1), cls=m.group(2),
                      x=int(m.group(3)) / 1000.0, y=int(m.group(4)) / 1000.0))
taps = [c for c in cells if c['cls'] == 'sky130_fd_sc_hd__tapvpwrvgnd_1']


def seg_of(x, y):
    for r in rows:
        if abs(r['y'] - y) < 1e-3 and r['x'] <= x < r['x1']:
            return r
    return None


print('=' * 78)
print('Q11a  THE NARROWEST SEGMENT THAT ACTUALLY RECEIVED A TAP')
print('=' * 78)
seg_taps = collections.Counter()
for t in taps:
    s = seg_of(t['x'], t['y'])
    if s is not None:
        seg_taps[id(s)] += 1

widths_with_tap = sorted({s['w'] for s in rows if seg_taps.get(id(s), 0) > 0})
widths_no_tap = sorted({s['w'] for s in rows if seg_taps.get(id(s), 0) == 0})
print('distinct widths of segments WITH >=1 tap : %s'
      % ', '.join('%.2f' % w for w in widths_with_tap))
print('distinct widths of segments with NO tap  : %s'
      % ', '.join('%.2f' % w for w in widths_no_tap))
print()
if widths_with_tap:
    emp_min = widths_with_tap[0]
    print('EMPIRICAL MINIMUM VIABLE SEGMENT = %.2f um (%d sites)'
          % (emp_min, round(emp_min / STEP)))
if widths_no_tap:
    emp_max_dead = widths_no_tap[-1]
    print('WIDEST SEGMENT THAT GOT NO TAP   = %.2f um (%d sites)'
          % (emp_max_dead, round(emp_max_dead / STEP)))
print()
print('=> Any prune threshold T is SAFE if  T <= %.2f um' % emp_min)
print('   (never deletes a segment that could host a tap)')
print('   and EFFECTIVE if T > %.2f um (does delete the tap-less ones).'
      % emp_max_dead)
print('   The admissible window is therefore  (%.2f , %.2f]'
      % (emp_max_dead, emp_min))

print()
print('=' * 78)
print('Q11b  IS 25.76 INSIDE THE ADMISSIBLE WINDOW?')
print('=' * 78)
for T in (7.82, 10.58, 11.04, 11.05, 20.0, 25.76, 26.22, 30.0, 51.06, 51.07):
    dele = [r for r in rows if r['w'] < T]
    lost = sum(seg_taps.get(id(r), 0) for r in dele)
    print('  T=%6.2f um -> delete %2d segs, taps lost = %3d %s'
          % (T, len(dele), lost, '<-- SAFE' if lost == 0 else '<-- LOSES TAPS'))

print()
print('=' * 78)
print('Q11c  WHAT DOES 25.76 ACTUALLY EQUAL?')
print('=' * 78)
print('  25.76 / 0.460 (site)        = %.4f sites' % (25.76 / 0.460))
print('  13.0 / 0.460 (TAPCELL_DIST)= %.4f sites' % (13.0 / 0.460))
print('  2 * 12.88                   = %.2f' % (2 * 12.88))
print('  56 * 0.460                  = %.2f' % (56 * 0.460))
print('  26.22 (57 sites, min viable)= %.2f' % (57 * 0.460))
print()
print('So 25.76 = 56 sites = 2 x 28 sites = 2 x round(FP_TAPCELL_DIST/site).')
print('It is 46 nm SHORT of the 57-site minimum viable segment, which is why')
print('it is provably safe -- but it is a DERIVED quantity, not an independent')
print('physical constant. The physical constant is the tap anchor rule O=28.')
