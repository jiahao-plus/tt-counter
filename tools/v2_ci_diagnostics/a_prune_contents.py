"""Q9: what actually lives in the 26 prunable fragments, and what is lost?

If the fragments hold only fill/decap (dummies), pruning loses nothing real.
If they hold functional logic, pruning forces re-placement and may perturb
the research macros' surroundings -- which Item 4 requires to stay traceable.
"""
import collections
import json
import os
import re

from paths import RUN as BASE
STEP, PITCH, Y0 = 0.460, 2.720, 2.720
PRUNE = 25.76

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


def load_cells(stage):
    p = os.path.join(BASE, stage, 'tt_um_jiahao_plus_counter.def')
    t = open(p, encoding='utf-8', errors='replace').read()
    out = []
    for m in CELL_RE.finditer(t):
        out.append(dict(name=m.group(1), cls=m.group(2),
                        x=int(m.group(3)) / 1000.0,
                        y=int(m.group(4)) / 1000.0))
    return out


def seg_of(x, y):
    for r in rows:
        if abs(r['y'] - y) < 1e-3 and r['x0'] <= x < r['x1']:
            return r
    return None


STAGES = [
    ('19-openroad-tapendcapinsertion', 'post-tap insertion'),
    ('52-openroad-fillinsertion', 'post-fill'),
]

for stage, label in STAGES:
    try:
        cs = load_cells(stage)
    except FileNotFoundError:
        print('%-32s MISSING' % stage)
        continue
    in_frag = collections.Counter()
    for c in cs:
        r = seg_of(c['x'], c['y'])
        if r is not None and r['w'] < PRUNE:
            in_frag[c['cls']] += 1
    print('=' * 78)
    print('%s  (%s)  total cells=%d' % (stage, label, len(cs)))
    print('=' * 78)
    tot = sum(in_frag.values())
    print('cells inside prunable fragments: %d' % tot)
    for k, v in in_frag.most_common():
        print('   %-46s %d' % (k, v))
    nonfill = {k: v for k, v in in_frag.items()
               if not (k.startswith('sky130_fd_sc_hd__fill_') or
                       k.startswith('sky130_fd_sc_hd__decap') or
                       k.startswith('sky130_fd_sc_hd__tap'))}
    print()
    print('NON-filler / NON-decap cells in prunable fragments: %d'
          % sum(nonfill.values()))
    for k, v in sorted(nonfill.items(), key=lambda p: -p[1]):
        print('   %-46s %d' % (k, v))
    print()

# which rows lose ALL their segments
print('=' * 78)
print('ROWS THAT LOSE EVERY SEGMENT (row disappears entirely)')
print('=' * 78)
byrow = collections.defaultdict(list)
for r in rows:
    byrow[round(r['y'], 3)].append(r)
gone = [y for y, ss in byrow.items() if all(s['w'] < PRUNE for s in ss)]
print('rows disappearing: %d of %d' % (len(gone), len(byrow)))
if gone:
    print('  y = %s' % ', '.join('%.3f' % y for y in sorted(gone)))
print()
print('rows that keep at least one segment: %d'
      % (len(byrow) - len(gone)))
