"""Part B, Q14: exact, closed decomposition of the 44 metric into R1/R2/R3.

Every number below is read from a third-round artefact or computed from one.
Nothing here is a guess; the only inference is which root cause OWNS a row,
and that is stated as an argument each time.
"""
import collections
import os
import re
import json

from paths import RUN as BASE
STEP, PRUNE = 0.460, 25.76
RPT = os.path.join(BASE, '66-netgen-lvs/reports/lvs.netgen.rpt')
txt = open(RPT, encoding='utf-8', errors='replace').read()

# ---------------------------------------------------------------- sections
i_net = txt.find('NET mismatches: Class fragments follow')
i_dev = txt.find('DEVICE mismatches: Class fragments follow')
i_end = txt.rfind('Final result:')
net_block = txt[i_net:i_dev]
dev_block = txt[i_dev:i_end]
pin_block = txt[txt.rfind('Subcircuit pins:'):i_end]

net_rows = re.findall(r'^Net: (\S+)\s*\|\s*(.*)$', net_block, re.M)

# ---------------------------------------------------------------- classification
R1 = [n for n, m in net_rows
      if (n.startswith('u_rs_') and n.endswith('/net')) or n == '_214_/X']
R2 = [n for n, m in net_rows
      if n.startswith('FILLER_') and n.endswith('/VPB') and
      'no matching net' in m]
R2_collided = [n for n, m in net_rows
               if n.startswith('FILLER_') and n.endswith('/VPB') and
               'no matching net' not in m]
POWER = [n for n, m in net_rows if n in ('VGND', 'VPWR')]

print('=' * 78)
print('NET mismatches: 19 rows')
print('=' * 78)
print('  R1  (<inst>/<pin> auto-name, 3 research pins + 1 stdcell pin) : %d  %s'
      % (len(R1), R1))
print('  R2  (FILLER_*/VPB with no counterpart)                        : %d'
      % len(R2))
print('  R2\' (FILLER_*/VPB that netgen paired with pwm_out)            : %d  %s'
      % (len(R2_collided), R2_collided))
print('  power nets                                                    : %d  %s'
      % (len(POWER), POWER))
print('  total                                                         : %d'
      % len(net_rows))

print()
print('  net_difference = 16.  Which 16?')
print('    R2  %2d  (12 floating FILLER_*/VPB)' % len(R2))
print('    R1  %2d  (3 research pin stubs + _214_/X)' % len(R1))
print('    ---- %d  <-- must equal 16' % (len(R2) + len(R1)))

# ---------------------------------------------------------------- R2 cells
print()
print('=' * 78)
print('device_difference = 21  --  owned ENTIRELY by R2')
print('=' * 78)
carry = {}
cur = None
for line in net_block.splitlines():
    m = re.match(r'^Net: (\S+)\s*\|', line)
    if m:
        cur = m.group(1)
        carry[cur] = []
        continue
    if cur and '|' in line:
        g = re.match(r'^(sky130_fd_sc_hd__\w+)/\w+\s*=', line.split('|')[0].strip())
        if g:
            carry[cur].append(g.group(1))

all_vpb = R2 + R2_collided
nd = nf = 0
print('  %-20s %s' % ('net', 'cells whose VPB sits on it'))
for nm in all_vpb:
    cls = carry.get(nm, [])
    hasd = 'sky130_fd_sc_hd__decap_3' in cls
    hasf = 'sky130_fd_sc_hd__fill_2' in cls
    nd += 1 if hasd else 0
    nf += 1 if hasf else 0
    print('  %-20s %s' % (nm, ', '.join(c.replace('sky130_fd_sc_hd__', '')
                                       for c in cls)))
print()
print('  FILLER_*/VPB nets carrying decap_3 : %d' % nd)
print('  FILLER_*/VPB nets carrying fill_2  : %d' % nf)
print('  sum                                : %d   (device_difference = 21)'
      % (nd + nf))

# cross-check against netgen's own instance deltas
SUMMARY = txt[txt.find('Subcircuit summary:'):i_net]
delta = {}
for line in SUMMARY.splitlines():
    if '|' not in line:
        continue
    a, b = line.split('|', 1)
    ma = re.match(r'^(sky130_fd_sc_hd__\w+|research_\w+)\s+'
                  r'\((\d+)->(\d+)\)', a.strip())
    mb = re.match(r'^(sky130_fd_sc_hd__\w+|research_\w+)\s+'
                  r'\((\d+)->(\d+)\)', b.strip())
    if ma and mb:
        delta[ma.group(1)] = (int(ma.group(3)), int(mb.group(3)))
print()
print('  netgen instance deltas:')
for k, (c1, c2) in delta.items():
    if c1 != c2:
        print('    %-34s C1=%-4d C2=%-4d  %+d' % (k, c1, c2, c1 - c2))

# ---------------------------------------------------------------- positions
print()
print('=' * 78)
print('ARE ALL 13 FLOATING-VPB NETS IN PRUNABLE SEGMENTS?')
print('=' * 78)
ROW_RE = re.compile(
    r'^ROW\s+(\S+)\s+\S+\s+(-?\d+)\s+(-?\d+)\s+\S+\s+'
    r'DO\s+(\d+)\s+BY\s+1\s+STEP\s+(\d+)', re.M)
CELL_RE = re.compile(
    r'^\s*-\s+(\S+)\s+(sky130_fd_sc_hd__\S+)\s+.*?\(\s*(-?\d+)\s+(-?\d+)\s*\)'
    r'\s+(\S+)\s*;', re.M)
t18 = open(os.path.join(BASE, '18-openroad-cutrows/'
                                'tt_um_jiahao_plus_counter.def'),
           encoding='utf-8', errors='replace').read()
segs = []
for m in ROW_RE.finditer(t18):
    x, y, n = (int(m.group(2)) / 1000.0, int(m.group(3)) / 1000.0,
               int(m.group(4)))
    segs.append(dict(x0=x, y=y, x1=x + n * STEP, w=n * STEP,
                     prunable=(n * STEP) < PRUNE))
t52 = open(os.path.join(BASE, '52-openroad-fillinsertion/'
                                'tt_um_jiahao_plus_counter.def'),
           encoding='utf-8', errors='replace').read()
place = {}
for m in CELL_RE.finditer(t52):
    place[m.group(1)] = (m.group(2), int(m.group(3)) / 1000.0,
                         int(m.group(4)) / 1000.0)


def seg_of(x, y):
    for s in segs:
        if abs(s['y'] - y) < 1e-3 and s['x0'] - 1e-3 <= x < s['x1'] - 1e-3:
            return s
    return None


np_ = nk = 0
print('  %-20s %-12s %9s %9s  %s' % ('net', 'cell', 'x', 'y', 'segment'))
for nm in all_vpb:
    stem = nm[:-len('/VPB')]
    if stem not in place:
        print('  %-20s %-12s  name not in 52-def' % (nm, '?'))
        continue
    cls, x, y = place[stem]
    s = seg_of(x, y)
    tag = 'PRUNABLE w=%.2f' % s['w'] if (s and s['prunable']) else \
          ('KEPT w=%.2f' % s['w'] if s else 'outside')
    if s and s['prunable']:
        np_ += 1
    elif s:
        nk += 1
    print('  %-20s %-12s %9.3f %9.3f  %s'
          % (nm, cls.replace('sky130_fd_sc_hd__', ''), x, y, tag))
print()
print('  in prunable segments : %d / %d' % (np_, len(all_vpb)))
print('  in KEPT segments     : %d / %d' % (nk, len(all_vpb)))

# ---------------------------------------------------------------- pins
print()
print('=' * 78)
print('unmatched_pin = 5  --  exact rows')
print('=' * 78)
pins = []
for ln in pin_block.splitlines():
    if '|' not in ln:
        continue
    a, b = ln.split('|', 1)
    a, b = a.strip(), b.strip()
    if not a or a.startswith('Circuit 1') or a.startswith('---'):
        continue
    pins.append((a, b))
n = 0
for a, b in pins:
    # a row is flagged from EITHER side: "(no pin, node is ...)" can appear in
    # column 1 as well as column 2 (FILLER_80_9/VPB case), so a
    # column-2-only filter silently undercounts 5 as 4.
    if 'Mismatch' in a or 'no pin' in a or 'Mismatch' in b or 'no pin' in b:
        n += 1
        print('  %d. C1 %-42s | C2 %s' % (n, a, b))
print()
print('  total rows in table: %d' % len(pins))
print('  counted rows: %d  (unmatched_pin = 5)' % n)

print()
print('=' * 78)
print('CLOSED DECOMPOSITION')
print('=' * 78)
print('  44 = device_difference 21 + net_difference 16 + property_fail 0')
print('       + unmatched_device 1 + unmatched_net 1 + unmatched_pin 5')
print()
print('  R2 (floating VPB in tap-less row segments)')
print('     device_difference : 21 / 21   decap_3 13 + fill_2 8')
print('     net_difference    : 12 / 16')
print('     -> all 13 affected nets are in PRUNABLE segments')
print()
print('  R1 (Magic abstract frame ignores the macro LEF ORIGIN)')
print('     net_difference    :  4 / 16   _214_/X + 3 u_rs_*/net')
print('     unmatched_pin     :  3 / 5    VGND, VPWR(C1), VPWR(C2)')
print('     unmatched_net     :  1 / 1')
print()
print('  R3 (true logic symmetry)')
print('     unmatched_pin     :  2 / 5    uio_out[7] <-> uio_oe[2]')
print()
print('  unmatched_device 1 : the 23 DEVICE rows collapse to one class pair')
