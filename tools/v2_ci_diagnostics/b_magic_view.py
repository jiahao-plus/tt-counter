"""Part B, Q11: WHY did Magic extract 4 separate nets where the DEF has 1?

Magic's flow (confirmed from magic-spiceextraction.log lines 58-95):
  lef read  techlef, sky130_ef_sc_hd.lef, sky130_fd_sc_hd.lef, then
            macros/out/struct_*.lef   (the AUTHORING LEFs, with their ORIGINs)
  def read  53-odb-cellfrequencytables/*.def -noblockage
  extract   exttospice

Magic builds a LEF-derived abstract view for each macro.  The DEF then places
instances at the COMPONENTS coordinates.  So the question is: where does Magic
put the abstract-view PORT relative to the placed instance?

We can answer this without Magic by checking one thing: the extracted SPICE
declares the macros as EMPTY black boxes:
    .subckt research_branch net
    .ends
so every macro pin becomes its own net with NO device.  netgen then cannot
match those nets to anything in the reference (which ALSO has them empty), and
the router's wire endpoints are not what netgen sees anyway.

The real question is why FOUR nets instead of ONE.  Let's check whether the
macro cells in Magic's abstract view even SPAN the wire endpoints.
"""
import os
import re

from paths import RUN as BASE
from paths import REPO as TT
DEF = os.path.join(BASE, 'final/def/tt_um_jiahao_plus_counter.def')

df = open(DEF, encoding='utf-8', errors='replace').read()

COMP = re.compile(r'^\s*-\s+(\S+)\s+(\S+)\s+\+\s+\w+\s+'
                  r'\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)\s*;', re.M)
place = {}
for m in COMP.finditer(df):
    place[m.group(1)] = (m.group(2), int(m.group(3)) / 1000.0,
                         int(m.group(4)) / 1000.0)

LEFINFO = {
    'u_rs_branch': ('struct_C1', 'research_branch', (0.930, 4.830),
                    (10.140, 3.240)),
    'u_rs_via1': ('struct_A', 'research_via1', (0.930, 1.930),
                  (8.140, 4.940)),
    'u_rs_via2': ('struct_B', 'research_via2', (0.930, 1.930),
                  (10.220, 3.265)),
}

print('=' * 78)
print('MAGIC ABSTRACT VIEW: where does the ORIGIN place the macro box?')
print('=' * 78)
print('  If Magic honours ORIGIN, the box is at  place + ORIGIN .. +SIZE.')
print('  If Magic ignores it, the box is at  place .. place+SIZE.')
print()
for inst, (stem, cls, origin, size) in LEFINFO.items():
    _, px, py = place[inst]
    print('  %-12s %-18s placed (%.3f, %.3f)' % (inst, cls, px, py))
    for lab, dx, dy in (('ORIGIN honoured', origin[0], origin[1]),
                        ('ORIGIN ignored', 0.0, 0.0)):
        print('     %-16s box x[%7.2f..%7.2f]  y[%7.2f..%7.2f]'
              % (lab, px + dx, px + dx + size[0],
                 py + dy, py + dy + size[1]))

print()
print('=' * 78)
print('ROUTER WIRE ENDPOINTS AT THE MACROS (from the DEF)')
print('=' * 78)
m = re.search(r'^\s*-\s+pwm_out\s+(.*?);\s*$', df, re.M | re.S)
rec = m.group(1)
SEG = re.compile(
    r'(?P<layer>met[1-5]|li1)\s+'
    r'\(\s*(?P<ax>-?\d+)\s+(?P<ay>-?\d+)(?:\s+0)?\s*\)\s*'
    r'\(\s*(?P<bx>-?\d+|\*)\s+(?P<by>-?\d+|\*)(?:\s+0)?\s*\)')
ends = {}
for s in SEG.finditer(rec):
    ax, ay = int(s.group('ax')) / 1000.0, int(s.group('ay')) / 1000.0
    bx = ax if s.group('bx') == '*' else int(s.group('bx')) / 1000.0
    by = ay if s.group('by') == '*' else int(s.group('by')) / 1000.0
    ends.setdefault((round(ax, 3), round(ay, 3)), 0)
    ends[(round(ax, 3), round(ay, 3))] += 1
    ends.setdefault((round(bx, 3), round(by, 3)), 0)
    ends[(round(bx, 3), round(by, 3))] += 1
dang = sorted(p for p, c in ends.items() if c == 1)
for p in dang:
    print('     (%8.3f, %8.3f)' % p)

print()
print('=' * 78)
print('WHICH BOX CONTAINS EACH DANGLING ENDPOINT?')
print('=' * 78)
for (ex, ey) in dang:
    tag = []
    for inst, (stem, cls, origin, size) in LEFINFO.items():
        _, px, py = place[inst]
        for lab, dx, dy in (('ORIGIN-honoured', origin[0], origin[1]),
                            ('ORIGIN-ignored', 0.0, 0.0)):
            x0, y0 = px + dx, py + dy
            x1, y1 = x0 + size[0], y0 + size[1]
            if x0 - 0.01 <= ex <= x1 + 0.01 and y0 - 0.01 <= ey <= y1 + 0.01:
                tag.append('%s (%s)' % (cls, lab))
    print('     (%8.3f,%8.3f)  %s' % (ex, ey, ', '.join(tag) if tag else '--'))

print()
print('=' * 78)
print('THE EXTRACTED MACRO SUBCIRCUITS')
print('=' * 78)
sp = open(os.path.join(BASE, '64-magic-spiceextraction/'
                             'tt_um_jiahao_plus_counter.spice'),
          encoding='utf-8', errors='replace').read()
for cls in ('research_branch', 'research_via1', 'research_via2'):
    m = re.search(r'^\.subckt %s\b(.*?)^\.ends' % cls, sp, re.M | re.S)
    body = m.group(1).strip()
    print('  .subckt %s' % body)
    print('  .ends      <- %d device lines' % len([
        l for l in body.splitlines() if l and not l.startswith('.') and
        not l.startswith('+')]))
