"""Part B, second pass: the three decisive structural questions.

Q1. Why is pwm_out split into 4 nets on the C1 side?
    Is it a NAME problem (MAGIC_DEF_LABELS) or a GEOMETRY/CONNECTION problem?

Q2. Are `uio_out[7]` and `uio_oe[2]` genuinely isomorphic on BOTH sides?

Q3. Where do _214_ / _218_ sit, i.e. does a Row prune move them?
"""
import os
import re

from paths import RUN as BASE
SPICE = os.path.join(BASE, '64-magic-spiceextraction/'
                           'tt_um_jiahao_plus_counter.spice')
PNL = os.path.join(BASE, '52-openroad-fillinsertion/'
                         'tt_um_jiahao_plus_counter.pnl.v')
DEF = os.path.join(BASE, 'final/def/tt_um_jiahao_plus_counter.def')

sp = open(SPICE, encoding='utf-8', errors='replace').read()
pn = open(PNL, encoding='utf-8', errors='replace').read()
df = open(DEF, encoding='utf-8', errors='replace').read()


def top_subckt(text):
    m = re.search(r'^\.subckt tt_um_jiahao_plus_counter\b(.*?)^\.ends',
                  text, re.M | re.S)
    return m.group(1) if m else ''


body = top_subckt(sp)
lines = [l for l in body.splitlines() if l.startswith('X')]
print('=' * 78)
print('Q1  C1 (extracted SPICE) instances touching the pwm_out cluster')
print('=' * 78)
for l in lines:
    if 'pwm_out' in l or '_214_' in l or 'u_rs_' in l or '_218_' in l:
        print('   ' + l)

print()
print('=' * 78)
print('Q1  C2 (reference pnl.v) the same cluster')
print('=' * 78)
for m in re.finditer(r'pwm_out', pn):
    a = pn.rfind('\n', 0, max(0, m.start() - 200))
    seg = pn[a:m.start() + 200].strip().splitlines()
    print('   ... ' + ' / '.join(x.strip() for x in seg[-4:]))

print()
print('=' * 78)
print('Q1  Does the SPICE declare research_* as BLACK BOXES (no devices)?')
print('=' * 78)
for m in re.finditer(r'^\* Black-box entry subcircuit for (\S+).*?^\.ends',
                     sp, re.M | re.S):
    blk = m.group(0)
    dev = [l for l in blk.splitlines()
           if re.match(r'^[MRCDXQ]', l) and not l.startswith('.subckt')]
    print('   %-18s body-device-lines=%d  %s'
          % (m.group(1), len(dev), dev[:2]))

print()
print('=' * 78)
print('Q2  uio_out[7] / uio_oe[2] : C1 (extracted)')
print('=' * 78)
for l in lines:
    if re.search(r'\buio_out\[7\]\b', l) or re.search(r'\buio_oe\[2\]\b', l):
        print('   ' + l)

print()
print('=' * 78)
print('Q2  uio_out[7] / uio_oe[2] : C2 (reference pnl.v)')
print('=' * 78)
for nm in ('uio_out[7]', 'uio_oe[2]'):
    print('   --- net %s ---' % nm)
    for m in re.finditer(r'\.(\w+)\(%s\)' % re.escape(nm), pn):
        a = pn.rfind('\n', 0, m.start())
        stmt_end = pn.find(');', m.end())
        stmt = pn[a:stmt_end + 2].replace('\n', ' ').strip()
        print('      ' + re.sub(r'\s+', ' ', stmt)[-160:])

print()
print('=' * 78)
print('Q2  conb_1 instance count on each side')
print('=' * 78)
print('   C1 conb_1 instances: %d'
      % len([l for l in lines if l.rstrip().endswith('sky130_fd_sc_hd__conb_1')]))
print('   C2 conb_1 instances: %d'
      % len(re.findall(r'sky130_fd_sc_hd__conb_1\s+\w+\s*\(', pn)))

print()
print('=' * 78)
print('Q3  positions of _214_ / _218_ / the two conb_1 cells')
print('=' * 78)
COMP = re.compile(r'^\s*-\s+(\S+)\s+(\S+)\s+\+\s+\w+\s+'
                  r'\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)\s*;', re.M)
pos = {}
for m in COMP.finditer(df):
    pos[m.group(1)] = (m.group(2), int(m.group(3)) / 1000.0,
                       int(m.group(4)) / 1000.0, m.group(5))
for nm in ('_214_', '_218_', 'u_rs_branch', 'u_rs_via1', 'u_rs_via2',
           'tt_um_jiahao_plus_counter', 'tt_um_jiahao_plus_counter_40',
           'tt_um_jiahao_plus_counter_32', 'tt_um_jiahao_plus_counter_33',
           'tt_um_jiahao_plus_counter_34'):
    if nm in pos:
        c = pos[nm]
        print('   %-38s %-32s (%8.2f, %8.2f) %s'
              % (nm, c[0], c[1], c[2], c[3]))
    else:
        print('   %-38s NOT FOUND' % nm)
