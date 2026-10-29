"""Part B, Q8: the exact decomposition of device_difference = 21, and the
research-macro LEF/GDS frame inconsistency.

(1) device_difference = 21  ->  per-net attribution from the Subcircuit
    summary's INSTANCE deltas and from the DEVICE-mismatch rows.

(2) The research-macro LEFs declare ORIGIN values that do not put the LEF
    frame's (0,0) at the bbox corner.  Check whether ORIGIN is INSIDE the
    SIZE box -- the standard requirement -- and whether the authoring GDS
    content sits at the LEF frame or at the LEF frame shifted by ORIGIN.
"""
import os
import re

from paths import RUN as BASE
from paths import REPO as TT
RPT = os.path.join(BASE, '66-netgen-lvs/reports/lvs.netgen.rpt')
txt = open(RPT, encoding='utf-8', errors='replace').read()

# ------------------------------------------------------------------ (1)
print('=' * 78)
print('(1)  device_difference = 21  --  exact attribution')
print('=' * 78)

i = txt.find('Subcircuit summary:')
j = txt.find('NET mismatches', i)
summary = txt[i:j]
deltas = {}
for line in summary.splitlines():
    if '|' not in line:
        continue
    a, b = line.split('|', 1)
    ma = re.match(r'^(sky130_fd_sc_hd__\w+|research_\w+)\s+\((\d+)->(\d+)\)',
                  a.strip())
    mb = re.match(r'^(sky130_fd_sc_hd__\w+|research_\w+)\s+\((\d+)->(\d+)\)',
                  b.strip())
    if ma and mb:
        deltas[ma.group(1)] = (int(ma.group(3)), int(mb.group(3)))

print('  classes whose INSTANCE COUNT differs (C1 vs C2):')
tot_extra = 0
for k, (c1, c2) in deltas.items():
    if c1 != c2:
        print('    %-34s C1=%-4d C2=%-4d  extra=%+d' % (k, c1, c2, c1 - c2))
        tot_extra += c1 - c2
print('  sum of extra instances = %d  (must equal device_difference = 21)'
      % tot_extra)

# DEVICE rows
i2 = txt.find('DEVICE mismatches: Class fragments follow')
j2 = txt.rfind('Final result:')
dev = txt[i2:j2]
rows = re.findall(r'^Instance: (\S+)\s*\|(.*)$', dev, re.M)
un = {}
for a, b in rows:
    m = re.match(r'^(sky130_fd_sc_hd__\w+|research_\w+):', a)
    if m and 'no matching instance' in b:
        un[m.group(1)] = un.get(m.group(1), 0) + 1
print()
print('  DEVICE rows with "no matching instance":')
s = 0
for k, v in sorted(un.items()):
    print('    %-34s %d' % (k, v))
    s += v
print('  sum = %d  (device_difference = 21)' % s)

# cross-check: which floating VPB net carries which cell class
print()
print('=' * 78)
print('  every floating VPB net, and the cell classes attached to it')
print('=' * 78)
net_block = txt[txt.find('NET mismatches'):i2]
cur = None
carry = {}
for line in net_block.splitlines():
    m = re.match(r'^Net: (\S+)\s*\|\s*(.*)$', line)
    if m:
        cur = m.group(1)
        carry[cur] = []
        continue
    if cur and '|' in line:
        left = line.split('|')[0].strip()
        g = re.match(r'^(sky130_fd_sc_hd__\w+)/\w+\s*=', left)
        if g:
            carry[cur].append(g.group(1))

n_dec = n_fill = 0
for nm, classes in carry.items():
    if nm.startswith('FILLER_') and nm.endswith('/VPB'):
        hasdec = 'sky130_fd_sc_hd__decap_3' in classes
        hasfill = 'sky130_fd_sc_hd__fill_2' in classes
        tag = []
        if hasdec:
            tag.append('decap_3')
        if hasfill:
            tag.append('fill_2')
        if 'sky130_fd_sc_hd__conb_1' in classes:
            tag.append('conb_1')
        print('    %-20s %s' % (nm, ' + '.join(tag)))
        n_dec += 1 if hasdec else 0
        n_fill += 1 if hasfill else 0
print()
print('    floating VPB nets containing decap_3 : %d  -> +%d classes (+1 tied)'
      % (n_dec, n_dec))
print('    floating VPB nets containing fill_2  : %d  -> +%d classes (+1 tied)'
      % (n_fill, n_fill))
print('    predicted device_difference = %d + %d = %d'
      % (n_dec, n_fill, n_dec + n_fill))

# ------------------------------------------------------------------ (2)
print()
print('=' * 78)
print('(2)  RESEARCH-MACRO LEF: is ORIGIN inside the SIZE box?')
print('=' * 78)
print('  LEF spec: ORIGIN gives the position of the macro-internal origin')
print('  INSIDE the macro bbox, whose extent is (0,0)-(SIZE). An ORIGIN')
print('  outside that box makes the LEF self-inconsistent.')
print()
for stem in ('struct_A', 'struct_B', 'struct_C1', 'struct_C3', 'struct_C4',
             'struct_D', 'struct_E'):
    p = os.path.join(TT, 'macros/out', stem + '.lef')
    if not os.path.exists(p):
        continue
    t = open(p, encoding='utf-8', errors='replace').read()
    macro = re.search(r'^\s*MACRO\s+(\S+)', t, re.M).group(1)
    o = re.search(r'^\s*ORIGIN\s+(-?[\d.]+)\s+(-?[\d.]+)\s*;', t, re.M)
    s = re.search(r'^\s*SIZE\s+(-?[\d.]+)\s+BY\s+(-?[\d.]+)\s*;', t, re.M)
    if not (o and s):
        continue
    ox, oy = float(o.group(1)), float(o.group(2))
    sw, sh = float(s.group(1)), float(s.group(2))
    ok_x = -1e-9 <= ox <= sw + 1e-9
    ok_y = -1e-9 <= oy <= sh + 1e-9
    flag = 'OK' if (ok_x and ok_y) else 'ORIGIN OUTSIDE SIZE BOX  <-- invalid'
    print('  %-8s %-18s ORIGIN=(%6.3f,%6.3f) SIZE=%.3f x %.3f  x_in=%-5s '
          'y_in=%-5s  %s'
          % (stem, macro, ox, oy, sw, sh, ok_x, ok_y, flag))

print()
print('  Where does the AUTHORING GDS place its content?')
import klayout.db as db
for stem in ('struct_A', 'struct_B', 'struct_C1'):
    p = os.path.join(TT, 'macros/out', stem + '.gds')
    ly = db.Layout()
    ly.read(p)
    top = ly.top_cell()
    b = top.dbbox()
    t = open(p.replace('.gds', '.lef'), encoding='utf-8',
             errors='replace').read()
    o = re.search(r'^\s*ORIGIN\s+(-?[\d.]+)\s+(-?[\d.]+)\s*;', t, re.M)
    ox, oy = float(o.group(1)), float(o.group(2))
    print('  %-8s GDS content bbox = (%.3f,%.3f)-(%.3f,%.3f)   ORIGIN=(%.3f,%.3f)'
          % (stem, b.left, b.bottom, b.right, b.top, ox, oy))
    print('           content starts at ORIGIN ?  dx=%.3f dy=%.3f'
          % (b.left - ox, b.bottom - oy))

# ------------------------------------------------------------------ (3)
print()
print('=' * 78)
print('(3)  Was Magic reading a STALE DEF?')
print('=' * 78)
DEF53 = os.path.join(BASE,
                     '53-odb-cellfrequencytables/'
                     'tt_um_jiahao_plus_counter.def')
DEFF = os.path.join(BASE, 'final/def/tt_um_jiahao_plus_counter.def')


def netrec(path, name):
    t = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'^\s*-\s+%s\s+(.*?);\s*$' % re.escape(name), t, re.M | re.S)
    return ' '.join(m.group(1).split()) if m else None


for nm in ('pwm_out', 'uio_out[7]', 'uio_oe[2]'):
    a = netrec(DEF53, nm)
    b = netrec(DEFF, nm)
    print('  net %-12s' % nm)
    print('    stage53 : %s' % (a[:110] if a else '(absent)'))
    print('    final   : %s' % (b[:110] if b else '(absent)'))
    print('    IDENTICAL: %s' % (a == b))
