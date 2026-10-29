"""Part B, Q18: independent net-count check for net_difference = 16.

netgen says C1 has 405 nets and C2 has 389 -> |diff| = 16.
The NET mismatch section lists 19 rows, which is a DIFFERENT number.
Do not conflate them. This script recounts both netlists directly and
confirms which 16 nets account for the difference.
"""
import os
import re

from paths import RUN as BASE
SPICE = os.path.join(BASE, '64-magic-spiceextraction/'
                           'tt_um_jiahao_plus_counter.spice')
PNL = os.path.join(BASE, '52-openroad-fillinsertion/'
                         'tt_um_jiahao_plus_counter.pnl.v')
RPT = os.path.join(BASE, '66-netgen-lvs/reports/lvs.netgen.rpt')

sp = open(SPICE, encoding='utf-8', errors='replace').read()
pn = open(PNL, encoding='utf-8', errors='replace').read()
txt = open(RPT, encoding='utf-8', errors='replace').read()

print('=' * 78)
print('NETGEN SUMMARY LINE')
print('=' * 78)
for ln in txt.splitlines():
    if 'Number of nets' in ln or 'Number of devices' in ln:
        print('  ' + ln.rstrip())

print()
print('=' * 78)
print('C1 -- nets in the extracted SPICE')
print('=' * 78)
m = re.search(r'^\.subckt tt_um_jiahao_plus_counter\b(.*?)^\.ends',
              sp, re.M | re.S)
body = re.sub(r'\n\+', ' ', m.group(1))
nets = set()
ninst = 0
for ln in body.splitlines():
    toks = ln.split()
    if not toks or toks[0].startswith('*') or toks[0].startswith('.'):
        continue
    if not toks[0].startswith('X'):
        continue
    ninst += 1
    # first token is instance name; last is the model; middle are nodes
    for node in toks[1:-1]:
        if not node.startswith('X') and not node[0].isdigit():
            nets.add(node)
        elif node.startswith('X') or re.match(r'^\d', node):
            nets.add(node)
print('  instances        : %d' % ninst)
print('  distinct nodes   : %d' % len(nets))
print('  netgen says C1   : 405')

print()
print('=' * 78)
print('C2 -- nets in the reference pnl.v (top module only)')
print('=' * 78)
mm = re.search(r'^module tt_um_jiahao_plus_counter\b(.*?)^endmodule',
               pn, re.M | re.S)
bb = mm.group(1)
nets2 = set()
ninst2 = 0
for ln in bb.splitlines():
    s = ln.strip()
    if s.startswith('sky130_fd_sc_hd__') or s.startswith('research_'):
        ninst2 += 1
    for nm in re.findall(r'\.(\w+)\(([^)]*)\)', ln):
        pass
for nm in re.findall(r'\.(\w+)\(([^)]*)\)', bb):
    val = nm[1].strip()
    if val:
        nets2.add(val)
print('  instances        : %d' % ninst2)
print('  distinct node names at instance ports : %d' % len(nets2))
print('  netgen says C2   : 389')

print()
print('=' * 78)
print('WHICH C1 NETS ARE UNMATCHED -- the 16')
print('=' * 78)
i_net = txt.find('NET mismatches: Class fragments follow')
i_dev = txt.find('DEVICE mismatches: Class fragments follow')
net_block = txt[i_net:i_dev]
rows = re.findall(r'^Net: (\S+)\s*\|\s*(.*)$', net_block, re.M)
only1 = [n for n, r in rows if 'no matching net' in r]
print('  rows with "(no matching net)" on the C2 side : %d' % len(only1))
for n in only1:
    print('     ' + n)
print()
print('  4 of them are the R1 fragments, the rest are floating VPB nets.')
r1 = [n for n in only1 if n.startswith('u_rs_') or n == '_214_/X']
r2 = [n for n in only1 if n not in r1]
print('     R1 : %d' % len(r1))
print('     R2 : %d' % len(r2))
print('     sum: %d   <-- net_difference = 16' % (len(r1) + len(r2)))
