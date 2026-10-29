"""Decisive cross-check for Item A.

Q1: where are the 576 tap/row violations, in (row, x) space?
Q2: do the 26 prunable segments geometrically cover them?
Q3: is the left edge of a full-width row really >15um from its first tap?
    (if so the LU rule as modelled is wrong, and OPT-A's premise is wrong)

Everything is measured on 3rd-round real artefacts.
"""
import collections
import json
import os
import re

ANA = os.path.dirname(os.path.abspath(__file__))
from paths import RUN as BASE

STEP, PITCH, Y0 = 0.460, 2.720, 2.720
PRUNE = 25.76

viol = json.load(open(os.path.join(ANA, 'magic_violations.json'),
                      encoding='utf-8'))

ROW_RE = re.compile(
    r'^ROW\s+(\S+)\s+\S+\s+(-?\d+)\s+(-?\d+)\s+\S+\s+'
    r'DO\s+(\d+)\s+BY\s+1\s+STEP\s+(\d+)', re.M)
t18 = open(os.path.join(
    BASE, '18-openroad-cutrows/tt_um_jiahao_plus_counter.def'),
    encoding='utf-8', errors='replace').read()
rows = []
for m in ROW_RE.finditer(t18):
    rows.append(dict(name=m.group(1), x=int(m.group(2)) / 1000.0,
                     y=int(m.group(3)) / 1000.0, n=int(m.group(4))))
for r in rows:
    r['x0'], r['x1'] = r['x'], r['x'] + r['n'] * STEP
    r['w'] = r['x1'] - r['x0']

print('=' * 78)
print('Q1  WHERE ARE THE TAP/ROW VIOLATIONS?')
print('=' * 78)
tapcats = ('LU.2', 'LU.3', 'nwell.4')
rows_hit = collections.Counter()
for v in viol:
    if v['category'] in tapcats and v['cy'] is not None:
        ri = int(round((v['cy'] - Y0) / PITCH))
        rows_hit[ri] += 1
print('distinct rows carrying tap/row violations: %d' % len(rows_hit))
print('violations per row (top 12):')
for ri, n in rows_hit.most_common(12):
    print('   row %3d  y=%8.3f  count=%3d' % (ri, Y0 + ri * PITCH, n))

print()
print('rows with tap/row violations, in order:')
for ri in sorted(rows_hit):
    segs = sorted([r for r in rows if abs(r['y'] - (Y0 + ri * PITCH)) < 1e-3],
                  key=lambda r: r['x0'])
    desc = ', '.join('[%.2f..%.2f w=%.2f%s]'
                     % (s['x0'], s['x1'], s['w'],
                        ' DEL' if s['w'] < PRUNE else ' keep')
                     for s in segs)
    print('  row %3d  y=%8.3f  n=%3d   %s'
          % (ri, Y0 + ri * PITCH, rows_hit[ri], desc))

print()
print('=' * 78)
print('Q2  ARE THE 26 PRUNABLE SEGMENTS EXACTLY THE VIOLATION CARRIERS?')
print('=' * 78)
dele = [r for r in rows if r['w'] < PRUNE]
print('prunable segments (%d):' % len(dele))
for r in sorted(dele, key=lambda r: (r['y'], r['x0'])):
    print('   y=%8.3f  x=[%8.3f .. %8.3f]  w=%6.2f  n=%3d'
          % (r['y'], r['x0'], r['x1'], r['w'], r['n']))

print()
print('=' * 78)
print('Q3  DISTINCT-ROW COUNT VS SEGMENT COUNT')
print('=' * 78)
print('rows total (from DEF)      : %d' % len({round(r['y'], 3) for r in rows}))
print('row lines with any segment : %d'
      % len({round(r['y'], 3) for r in rows}))
print('prunable segments          : %d' % len(dele))
print('rows that KEEP a segment   : %d'
      % len({round(r['y'], 3) for r in rows if r['w'] >= PRUNE}))
print('rows where ALL segments are prunable: %d'
      % len({round(r['y'], 3) for r in rows}
            - {round(r['y'], 3) for r in rows if r['w'] >= PRUNE}))
