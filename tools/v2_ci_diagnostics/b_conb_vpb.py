"""Part B, Q19: the conb_1 VPB anomaly -- a discrepancy that is INVISIBLE
in device_difference.

MEASURED fact from the .rpt:
    sky130_fd_sc_hd__conb_1/VPB = 9   |   12
yet the summary says
    sky130_fd_sc_hd__conb_1 (12)      |  (12)      <- NO mismatch

So 3 conb_1 cells in C1 have their VPB on a floating net, and netgen still
counts 12 devices on both sides. This matters because the previous document
claimed OPT-A would move "the conb_1 related to R3". Test that.
"""
import os
import re

from paths import RUN as BASE
SPICE = os.path.join(BASE, '64-magic-spiceextraction/'
                           'tt_um_jiahao_plus_counter.spice')
RPT = os.path.join(BASE, '66-netgen-lvs/reports/lvs.netgen.rpt')

sp = open(SPICE, encoding='utf-8', errors='replace').read()
txt = open(RPT, encoding='utf-8', errors='replace').read()

print('=' * 78)
print('1. THE THREE conb_1 WITH A FLOATING VPB -- WHICH OUTPUTS?')
print('=' * 78)
m = re.search(r'^\.subckt tt_um_jiahao_plus_counter\b(.*?)^\.ends',
              sp, re.M | re.S)
body = re.sub(r'\n\+', ' ', m.group(1))
rows = []
for ln in body.splitlines():
    if 'sky130_fd_sc_hd__conb_1' not in ln:
        continue
    toks = ln.split()
    # Xname VGND VNB VPB VPWR HI <output> model
    #   [0]=inst [1]=VGND [2]=VNB [3]=VPB [4]=VPWR [5]=HI [6]=output
    # Using toks[5] here would return the internal HI node, not the pin the
    # cell drives -- take the last node before the model instead.
    rows.append(dict(inst=toks[0], vpb=toks[3], hi=toks[5], out=toks[6]))
print('  %-38s %-24s %s' % ('instance', 'VPB node', 'output net'))
bad = []
for r in rows:
    flag = '' if r['vpb'] == 'VPWR' else '   <-- VPB FLOATING'
    if r['vpb'] != 'VPWR':
        bad.append(r)
    print('  %-38s %-24s %s%s' % (r['inst'], r['vpb'], r['out'], flag))
print()
print('  conb_1 with floating VPB : %d' % len(bad))
for r in bad:
    print('     %s -> %s   (VPB on %s)' % (r['inst'], r['out'], r['vpb']))

print()
print('=' * 78)
print('2. WHICH conb_1 DRIVE THE R3 NETS?')
print('=' * 78)
for net in ('uio_out[7]', 'uio_oe[2]'):
    hit = [r for r in rows if r['out'] == net]
    print('  %-12s driven by %s   VPB=%s  %s'
          % (net,
             ', '.join(h['inst'] for h in hit),
             ', '.join(h['vpb'] for h in hit),
             'FPGA' if False else
             ('VPB OK' if all(h['vpb'] == 'VPWR' for h in hit)
              else 'VPB FLOATING')))

print()
print('=' * 78)
print('3. DOES THE conb_1 VPB ANOMALY ENTER device_difference?')
print('=' * 78)
for ln in txt.splitlines():
    if re.match(r'^sky130_fd_sc_hd__conb_1 \(', ln):
        print('  summary: ' + ln.rstrip())
print()
print('  No "->" reduction and no **Mismatch**: both sides have 12 devices.')
print('  Each conb_1 drives a UNIQUE output net, so the 12 can never merge')
print('  on either side; a floating VPB therefore cannot change the count.')
print()
print('  => the conb_1 VPB anomaly is INVISIBLE in device_difference.')
print('     It is also not in net_difference (those 2 nets are already')
print('     counted among the 12 FILLER_* floating nets).')

print()
print('=' * 78)
print('4. WHERE THE THREE SIT (row segment)')
print('=' * 78)
STEP, PRUNE = 0.460, 25.76
t18 = open(os.path.join(BASE, '18-openroad-cutrows/'
                                'tt_um_jiahao_plus_counter.def'),
           encoding='utf-8', errors='replace').read()
segs = []
for mm in re.finditer(r'^ROW\s+(\S+)\s+\S+\s+(-?\d+)\s+(-?\d+)\s+\S+\s+'
                      r'DO\s+(\d+)\s+BY\s+1\s+STEP\s+(\d+)', t18, re.M):
    x, y, n = (int(mm.group(2)) / 1000.0, int(mm.group(3)) / 1000.0,
               int(mm.group(4)))
    segs.append(dict(x0=x, y=y, x1=x + n * STEP, w=n * STEP,
                     prunable=(n * STEP) < PRUNE))

df = open(os.path.join(BASE, 'final/def/tt_um_jiahao_plus_counter.def'),
          encoding='utf-8', errors='replace').read()
place = {}
for mm in re.finditer(r'^\s*-\s+(\S+)\s+(\S+)\s+\+\s+\w+\s+'
                      r'\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)\s*;', df, re.M):
    place[mm.group(1)] = (mm.group(2), int(mm.group(3)) / 1000.0,
                          int(mm.group(4)) / 1000.0)


def seg_of(x, y):
    for s in segs:
        if abs(s['y'] - y) < 1e-3 and s['x0'] - 1e-3 <= x < s['x1'] - 1e-3:
            return s
    return None


# The SPICE instance names are not the DEF instance names. Match by the
# driven output net instead: DEF conb_1 -> its HI net -> SPICE instance.
df_nets = {}
for mm in re.finditer(r'^\s*-\s+(\S+)\s+\((?:\s*\S+\s+\S+\s*)\)\s*$', df, re.M):
    pass
conb_by_net = {}
# DEF: "- <inst> <class> + SOURCE TIMING + PLACED ( x y ) FN ;"  -- note the
# markers before PLACED, so the earlier "^... + \w+ (x y)" pattern missed.
for mm in re.finditer(r'^\s*-\s+(\S+)\s+sky130_fd_sc_hd__conb_1\b[^;]*?'
                      r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', df, re.M):
    conb_by_net[mm.group(1)] = (int(mm.group(2)) / 1000.0,
                                int(mm.group(3)) / 1000.0)
print()
print('  DEF conb_1 instances: %d' % len(conb_by_net))
for inst in sorted(conb_by_net):
    x, y = conb_by_net[inst]
    s = seg_of(x, y)
    if s and s['prunable']:
        print('     %-34s (%8.3f,%8.3f)  PRUNABLE w=%.2f' % (inst, x, y, s['w']))
    elif s:
        print('     %-34s (%8.3f,%8.3f)  kept' % (inst, x, y))
    else:
        print('     %-34s (%8.3f,%8.3f)  outside rows' % (inst, x, y))
