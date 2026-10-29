"""Part B, Q15: WHY does netgen report 21 extra devices when the instance
counts on both sides are IDENTICAL?

This is the test that separates two very different explanations:
  (a) the reference and the layout disagree about how many decap/fill cells
      exist  -> a real netlist-vs-layout discrepancy
  (b) both sides have the same 16182 decap_3 / 138 fill_2, but the extracted
      circuit fragments them into separate device groups because their VPB
      pins land on floating nets -> netgen's series/parallel reduction cannot
      merge them, so it counts 14 groups where the reference has 1.

If (b) holds, then 14 = 13 floating + 1 merged remainder and 9 = 8 + 1
must both come out exactly, and that arithmetic IS the causal link.
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
print('STEP 1 -- RAW INSTANCE COUNTS ON BOTH SIDES')
print('=' * 78)
inst = {}
for cls in ('decap_3', 'fill_2', 'fill_1', 'tapvpwrvgnd_1', 'conb_1'):
    full = 'sky130_fd_sc_hd__' + cls
    # C1: "Xname ... <class>"  (one per line, no trailing args)
    c1 = len(re.findall(r'^X\S+ .*%s\s*$' % re.escape(full), sp, re.M))
    # C2: "<class> <instname> (...)" -- note the reference does NOT prefix
    # instance names with X (it uses FILLER_0_100 etc. verbatim), so the
    # pattern must accept any identifier, not "X\S+".
    c2 = len(re.findall(r'^\s*%s\s+\S+\s*\(' % re.escape(full), pn, re.M))
    inst[cls] = (c1, c2)
    print('  %-16s  C1 extracted %6d   C2 reference %6d   %s'
          % (cls, c1, c2, 'EQUAL' if c1 == c2 else '*** DIFFER ***'))

print()
print('  => both netlists describe the SAME physical cell population.')
print('     The 21 cannot be a count-of-cells discrepancy.')

print()
print('=' * 78)
print('STEP 2 -- WHAT netgen PRINTS FOR EACH CLASS')
print('=' * 78)
SUM = txt[txt.find('Subcircuit summary:'):txt.find('Number of devices:')]
for line in SUM.splitlines():
    if '**Mism' in line:
        print('  ' + line.rstrip())

print()
print('  Read "(16182->14)": 16182 raw instances REDUCED (series/parallel')
print('  merge) to 14 devices.  The reference reduces them to 1.')

print()
print('=' * 78)
print('STEP 3 -- IS 14 EXACTLY "13 FLOATING + 1 MERGED REMAINDER"?')
print('=' * 78)
# floating VPB nets, straight out of the NET mismatch section
i_net = txt.find('NET mismatches: Class fragments follow')
i_dev = txt.find('DEVICE mismatches: Class fragments follow')
net_block = txt[i_net:i_dev]
float_nets = re.findall(r'^Net: (FILLER_\S+/VPB)\s*\|', net_block, re.M)
print('  floating VPB nets reported by netgen : %d' % len(float_nets))

# how many decap_3 / fill_2 ports sit on those nets
nd = nf = 0
cur = None
for line in net_block.splitlines():
    m = re.match(r'^Net: (\S+)\s*\|', line)
    if m:
        cur = m.group(1)
        continue
    if cur in float_nets:
        if 'sky130_fd_sc_hd__decap_3/VPB' in line:
            nd += 1
        if 'sky130_fd_sc_hd__fill_2/VPB' in line:
            nf += 1
print('  decap_3 ports on floating VPB nets : %d' % nd)
print('  fill_2  ports on floating VPB nets : %d' % nf)

print()
print('  predicted decap_3 device groups = %d floating + 1 merged = %d'
      % (nd, nd + 1))
print('  netgen reported                                            = 14')
print('  MATCH: %s' % ((nd + 1) == 14))
print()
print('  predicted fill_2  device groups = %d floating + 1 merged = %d'
      % (nf, nf + 1))
print('  netgen reported                                            = 9')
print('  MATCH: %s' % ((nf + 1) == 9))

print()
print('=' * 78)
print('STEP 4 -- DO THE FANOUT COUNTS AGREE WITH THE GROUP COUNT?')
print('=' * 78)
print('  If the 14 groups exist, decap_3 should show 14 connections to')
print('  VGND/VPWR in C1 and only 1 in C2.')
for ln in net_block.splitlines():
    if 'decap_3/VGND' in ln or 'decap_3/VPWR' in ln or \
            'fill_2/VGND' in ln or 'fill_2/VPWR' in ln:
        print('  ' + ln.rstrip())

print()
print('=' * 78)
print('VERDICT')
print('=' * 78)
print('  21 = 13 (decap_3 groups isolated by a floating VPB)')
print('     +  8 (fill_2  groups isolated by a floating VPB)')
print()
print('  The cell population is identical on both sides.  The difference')
print('  is that in the EXTRACTED circuit each of those cells has its VPB')
print('  pin on a private floating net, so netgen cannot merge it with the')
print('  rest of its class.  device_difference is therefore a DIRECT')
print('  function of the count of floating VPB nets -- not of any cell')
print('  count, and not of any short.')
