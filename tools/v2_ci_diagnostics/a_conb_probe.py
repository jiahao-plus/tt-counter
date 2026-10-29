"""Q10: the 3 conb_1 cells inside prunable fragments -- what do they drive?

conb_1 is a CONSTANT cell (it drives constant 0/1). It is functional, not a
dummy. If these cells drive uio_out / uio_oe, then R3 (the pin symmetry
mismatch) is NOT independent of a row-pruning change -- which would refute
the claim that R3 can be dismissed as "unaffected by tap work".
"""
import collections
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

t52 = open(os.path.join(
    BASE, '52-openroad-fillinsertion/tt_um_jiahao_plus_counter.def'),
    encoding='utf-8', errors='replace').read()


def seg_of(x, y):
    for r in rows:
        if abs(r['y'] - y) < 1e-3 and r['x0'] <= x < r['x1']:
            return r
    return None


print('=' * 78)
print('ALL conb_1 CELLS AND THEIR SEGMENTS')
print('=' * 78)
all_conb = []
for m in CELL_RE.finditer(t52):
    nm, cls = m.group(1), m.group(2)
    if 'conb_1' not in cls:
        continue
    x, y = int(m.group(3)) / 1000.0, int(m.group(4)) / 1000.0
    s = seg_of(x, y)
    all_conb.append((nm, x, y, s))
    print('%-12s x=%8.3f y=%8.3f  seg=%s'
          % (nm, x, y,
             ('w=%.2f %s' % (s['w'], 'PRUNABLE' if s['w'] < PRUNE else 'kept'))
             if s else 'none'))

print()
print('total conb_1 cells: %d' % len(all_conb))
print('  in prunable fragments: %d'
      % sum(1 for c in all_conb if c[3] and c[3]['w'] < PRUNE))

print()
print('=' * 78)
print('WHAT DO THE conb_1 CELLS DRIVE?  (from the routed DEF)')
print('=' * 78)
dfin = os.path.join(BASE, 'final/def/tt_um_jiahao_plus_counter.def')
tfin = open(dfin, encoding='utf-8', errors='replace').read()

names = [c[0] for c in all_conb]
# DEF net statements list their instance pins: "- name ( inst PIN ) ( inst PIN )"
for nm in names:
    hits = []
    for m in re.finditer(r'^-\s+(\S+)\s+(.*?);', tfin, re.M | re.S):
        body = m.group(2)
        if re.search(r'\(\s*%s\s+\S+\s*\)' % re.escape(nm), body):
            hits.append(m.group(1))
    print('%-12s driven nets: %s' % (nm, ', '.join(hits) if hits else '(none)'))

print()
print('=' * 78)
print('uio_out[7] / uio_oe[2] CONNECTIONS IN THE FINAL DEF')
print('=' * 78)
for target in ('uio_out[7]', 'uio_oe[2]', 'uio_out\\[7\\]', 'uio_oe\\[2\\]'):
    m = re.search(r'^-\s+%s\s+(.*?);' % target, tfin, re.M | re.S)
    if m:
        body = ' '.join(m.group(1).split())
        print()
        print('NET %s:' % target)
        print('   %s' % body[:600])
        break
