"""Q4: the x-distribution of tap/row violations inside each affected row.

This is the question the whole Item A decision turns on:
  - if violations cluster at x < 14um  -> they live in the narrow left fragments,
    and deleting those fragments genuinely removes the violating geometry;
  - if violations spread across the full row width -> deleting the fragment does
    NOT remove them, and OPT-A is cosmetic.
"""
import collections
import json
import os

ANA = os.path.dirname(os.path.abspath(__file__))

STEP, PITCH, Y0 = 0.460, 2.720, 2.720
viol = json.load(open(os.path.join(ANA, 'magic_violations.json'),
                      encoding='utf-8'))

tapcats = ('LU.2', 'LU.3', 'nwell.4')

by_row = collections.defaultdict(list)
for v in viol:
    if v['category'] in tapcats and v['cy'] is not None:
        ri = int(round((v['cy'] - Y0) / PITCH))
        by_row[ri].append(v)

print('=' * 78)
print('Q4  PER-ROW x-DISTRIBUTION OF TAP/ROW VIOLATIONS')
print('=' * 78)
for ri in sorted(by_row):
    vs = by_row[ri]
    xs = sorted(v['cx'] for v in vs)
    print()
    print('row %2d  y=%8.3f  n=%d   x range [%.3f .. %.3f]'
          % (ri, Y0 + ri * PITCH, len(vs), xs[0], xs[-1]))
    # bucket into 10um bins
    bins = collections.Counter(int(x // 10) * 10 for x in xs)
    line = '   '
    for b in range(0, 340, 10):
        c = bins.get(b, 0)
        line += '.' if c == 0 else ('%X' % min(c, 15))
    print(line + '   (each char = 10um, hex count)')
    print('   detail: %s' % ', '.join('%.2f' % x for x in xs))

print()
print('=' * 78)
print('Q5  HOW MANY VIOLATIONS SIT INSIDE A PRUNABLE FRAGMENT (x<14 or x in 84..92)?')
print('=' * 78)
FRAG = [(2.76, 13.34), (84.18, 92.00), (2.76, 13.80)]


def in_frag(x):
    return any(a <= x <= b for a, b in FRAG)


inf = sum(1 for ri in by_row for v in by_row[ri] if in_frag(v['cx']))
tot = sum(len(by_row[ri]) for ri in by_row)
print('tap/row violations total   : %d' % tot)
print('inside a prunable fragment : %d' % inf)
print('OUTSIDE (on kept rows/area): %d' % (tot - inf))

# cross-tab by category
print()
print('%-9s %10s %10s' % ('category', 'in-frag', 'outside'))
for c in tapcats:
    a = sum(1 for ri in by_row for v in by_row[ri]
            if v['category'] == c and in_frag(v['cx']))
    b = sum(1 for ri in by_row for v in by_row[ri]
            if v['category'] == c and not in_frag(v['cx']))
    print('%-9s %10d %10d' % (c, a, b))
