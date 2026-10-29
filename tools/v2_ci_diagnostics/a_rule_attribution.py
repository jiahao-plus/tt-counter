"""Q13: per-rule spatial attribution of ALL 669 violations against the
prune decision -- the deliverable table Item A actually asks for.

For each rule name:
  - how many violations
  - how many sit in a segment OPT-A would delete
  - how many sit in a segment OPT-A would keep
  - the coordinate range of each group

This is the "which violations fall in the affected range" table.
"""
import collections
import json
import os

ANA = os.path.dirname(os.path.abspath(__file__))
STEP, PITCH, Y0 = 0.460, 2.720, 2.720
PRUNE = 25.76

viol = json.load(open(os.path.join(ANA, 'magic_violations.json'),
                      encoding='utf-8'))

# Fragment boxes measured from the 18-cutrows DEF (the 26 prunable segments).
import re
from paths import RUN as BASE
ROW_RE = re.compile(
    r'^ROW\s+(\S+)\s+\S+\s+(-?\d+)\s+(-?\d+)\s+\S+\s+'
    r'DO\s+(\d+)\s+BY\s+1\s+STEP\s+(\d+)', re.M)
t18 = open(os.path.join(
    BASE, '18-openroad-cutrows/tt_um_jiahao_plus_counter.def'),
    encoding='utf-8', errors='replace').read()
segs = []
for m in ROW_RE.finditer(t18):
    x, y, n = (int(m.group(2)) / 1000.0, int(m.group(3)) / 1000.0,
               int(m.group(4)))
    segs.append((x, y, x + n * STEP, y + PITCH, n * STEP))

prunable = [s for s in segs if s[4] < PRUNE]
kept = [s for s in segs if s[4] >= PRUNE]


def in_any(x, y, boxes):
    for x0, y0, x1, y1, _ in boxes:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return True
    return False


print('=' * 78)
print('PER-RULE ATTRIBUTION OF ALL 669 VIOLATIONS VS THE PRUNE DECISION')
print('=' * 78)
print()
hdr = ('%-9s %6s %10s %10s %10s' %
       ('rule', 'total', 'in-prunable', 'in-kept', 'unattributed'))
print(hdr)
print('-' * 78)

stats = {}
for cat in ('LU.2', 'LU.3', 'nwell.4', 'via.5a', 'met2.5', 'via2.4a'):
    vs = [v for v in viol if v['category'] == cat]
    a = b = c = 0
    ext_p = [1e9, 1e9, -1e9, -1e9]
    ext_k = [1e9, 1e9, -1e9, -1e9]
    for v in vs:
        if v['cx'] is None:
            c += 1
            continue
        if in_any(v['cx'], v['cy'], prunable):
            a += 1
            ext_p[0] = min(ext_p[0], v['x0'])
            ext_p[1] = min(ext_p[1], v['y0'])
            ext_p[2] = max(ext_p[2], v['x1'])
            ext_p[3] = max(ext_p[3], v['y1'])
        elif in_any(v['cx'], v['cy'], kept):
            b += 1
            ext_k[0] = min(ext_k[0], v['x0'])
            ext_k[1] = min(ext_k[1], v['y0'])
            ext_k[2] = max(ext_k[2], v['x1'])
            ext_k[3] = max(ext_k[3], v['y1'])
        else:
            c += 1
    stats[cat] = (len(vs), a, b, c, ext_p, ext_k)
    print('%-9s %6d %10d %10d %10d' % (cat, len(vs), a, b, c))

tot = sum(s[0] for s in stats.values())
ta = sum(s[1] for s in stats.values())
tb = sum(s[2] for s in stats.values())
tc = sum(s[3] for s in stats.values())
print('-' * 78)
print('%-9s %6d %10d %10d %10d' % ('TOTAL', tot, ta, tb, tc))

print()
print('=' * 78)
print('COORDINATE EXTENT OF EACH GROUP')
print('=' * 78)
for cat in ('LU.2', 'LU.3', 'nwell.4'):
    n, a, b, c, ep, ek = stats[cat]
    print()
    print('%s : %d total' % (cat, n))
    if a:
        print('   in prunable : x[%8.3f .. %8.3f]  y[%8.3f .. %8.3f]'
              % (ep[0], ep[2], ep[1], ep[3]))
    if b:
        print('   in KEPT     : x[%8.3f .. %8.3f]  y[%8.3f .. %8.3f]'
              % (ek[0], ek[2], ek[1], ek[3]))
        print('   *** THESE SURVIVE A PRUNE ***')

print()
print('=' * 78)
print('nwell.4 RULE TEXT AND WHAT IT CONSTRAINS')
print('=' * 78)
s = open(os.path.join(
    BASE, '62-magic-drc/reports/drc.magic.lyrdb'),
    encoding='utf-8', errors='replace').read()
import re as _re
for m in _re.finditer(r"<category><name>([^<]+)</name><description>([^<]+)"
                      r"</description></category>", s):
    print('  %-10s %s' % (m.group(1), m.group(2)))
