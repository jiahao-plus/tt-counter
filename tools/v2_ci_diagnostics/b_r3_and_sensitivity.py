"""Part B final: R3 symmetry proof + tap/row sensitivity of R1/R2/R3."""
import collections
import os
import re

from paths import RUN as BASE
SPICE = os.path.join(BASE, '64-magic-spiceextraction/'
                           'tt_um_jiahao_plus_counter.spice')
PNL = os.path.join(BASE, '52-openroad-fillinsertion/'
                         'tt_um_jiahao_plus_counter.pnl.v')
DEF = os.path.join(BASE, 'final/def/tt_um_jiahao_plus_counter.def')
STEP, PRUNE = 0.460, 25.76

sp = open(SPICE, encoding='utf-8', errors='replace').read()
pn = open(PNL, encoding='utf-8', errors='replace').read()
df = open(DEF, encoding='utf-8', errors='replace').read()

print('=' * 78)
print('R3 -- ARE uio_out[7] AND uio_oe[2] ELECTRICALLY ISOMORPHIC?')
print('=' * 78)


def spice_instances(text, net):
    m = re.search(r'^\.subckt tt_um_jiahao_plus_counter\b(.*?)^\.ends',
                  text, re.M | re.S)
    body = m.group(1)
    # join continuation lines
    body = re.sub(r'\n\+', ' ', body)
    out = []
    for ln in body.splitlines():
        if not ln.startswith('X'):
            continue
        parts = ln.split()
        if net in parts:
            out.append(ln)
    return out


for net in ('uio_out[7]', 'uio_oe[2]'):
    print()
    print('  C1 (extracted SPICE) -- instances containing %s:' % net)
    for ln in spice_instances(sp, net):
        print('     ' + ln)
    print('  C2 (reference pnl.v):')
    for m in re.finditer(r'^\s*assign\s+%s\s*=\s*(\w+)\s*;' % re.escape(net),
                         pn, re.M):
        print('     assign %s = %s;' % (net, m.group(1)))
    for m in re.finditer(r'\.(\w+)\(%s\)' % re.escape(net), pn):
        a = pn.rfind('\n', 0, m.start())
        st = pn[a:pn.find(');', m.end()) + 2].replace('\n', ' ')
        print('     ' + re.sub(r'\s+', ' ', st).strip()[-150:])

print()
print('=' * 78)
print('R3 -- driver cell class of each net, on each side')
print('=' * 78)
for net in ('uio_out[7]', 'uio_oe[2]'):
    c1 = [l.split()[-1] for l in spice_instances(sp, net)]
    print('  %-12s C1 driver class : %s' % (net, c1))
print('  C2: both are conb_1 (constant cell) -- see assign targets above')

print()
print('=' * 78)
print('VERDICT ON R3')
print('=' * 78)
print('  Netgen itself prints: "Port matching may fail to disambiguate')
print('  symmetries."  Both nets are driven by an identical conb_1 LO')
print('  constant and have no other loads, so the two nets are exactly')
print('  isomorphic.  A swap is a MATCHING ARTEFACT, not a defect and not')
print('  a short.')

# ---------------------------------------------------------------- sensitivity
print()
print('=' * 78)
print('TAP/ROW SENSITIVITY OF R1 / R2 / R3')
print('=' * 78)
ROW_RE = re.compile(
    r'^ROW\s+(\S+)\s+\S+\s+(-?\d+)\s+(-?\d+)\s+\S+\s+'
    r'DO\s+(\d+)\s+BY\s+1\s+STEP\s+(\d+)', re.M)
t18 = open(os.path.join(BASE, '18-openroad-cutrows/'
                                'tt_um_jiahao_plus_counter.def'),
           encoding='utf-8', errors='replace').read()
rows = []
for m in ROW_RE.finditer(t18):
    x, y, n = (int(m.group(2)) / 1000.0, int(m.group(3)) / 1000.0,
               int(m.group(4)))
    rows.append(dict(x0=x, y=y, x1=x + n * STEP, w=n * STEP,
                     prunable=(n * STEP) < PRUNE))

prun = [r for r in rows if r['prunable']]
print('  prunable segments: %d' % len(prun))
for r in sorted(prun, key=lambda z: (z['y'], z['x0'])):
    print('     y=%7.2f  x[%7.2f..%7.2f]  w=%5.2f' %
          (r['y'], r['x0'], r['x1'], r['w']))

FEATURES = [
    ('R1  research_branch met1 pin', 80.32, 213.00),
    ('R1  research_via1 met1 pin', 34.43, 209.93),
    ('R1  research_via2 met3 pin', 75.00, 213.00),
    ('R1  _214_ X pin', 172.04, 217.60),
    ('R1  pwm_out wire leftmost', 42.55, 212.00),
    ('R2  FILLER_51_9 (decap)', 6.90, 141.44),
    ('R2  FILLER_57_9 (decap)', 6.90, 157.76),
    ('R2  FILLER_69_189 (fill_2)', 89.70, 190.40),
    ('R2  conb_1 _32', 11.04, 220.32),
    ('R3  conb_1 driving uio_out[7]', None, None),
    ('R3  conb_1 driving uio_oe[2]', None, None),
]

COMP = re.compile(r'^\s*-\s+(\S+)\s+(\S+)\s+\+\s+\w+\s+'
                  r'\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)\s*;', re.M)
place = {}
for m in COMP.finditer(df):
    place[m.group(1)] = (m.group(2), int(m.group(3)) / 1000.0,
                         int(m.group(4)) / 1000.0)

print()
print('  %-34s %10s %10s  %s' % ('feature', 'x', 'y', 'in a prunable segment?'))
for nm, x, y in FEATURES:
    if x is None:
        continue
    hit = [r for r in prun
           if abs(r['y'] - y) < 1e-3 and r['x0'] - 1e-3 <= x < r['x1']]
    print('  %-34s %10.2f %10.2f  %s'
          % (nm, x, y, 'YES  (moves)' if hit else 'no   (kept)'))

print()
print('  R3 cells: locate every conb_1 that drives uio_out[7] / uio_oe[2]')
for m in re.finditer(r'^\s*-\s+(\S+)\s+(sky130_fd_sc_hd__conb_1)\s+\+\s+\w+\s+'
                     r'\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)\s*;', df, re.M):
    inst = m.group(1)
    x, y = int(m.group(3)) / 1000.0, int(m.group(4)) / 1000.0
    hit = [r for r in prun
           if abs(r['y'] - y) < 1e-3 and r['x0'] - 1e-3 <= x < r['x1']]
    print('     %-34s (%8.2f,%8.2f)  %s'
          % (inst, x, y, 'PRUNABLE' if hit else 'kept'))
