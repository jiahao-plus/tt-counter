"""Part B, Q10 -- THE DECISIVE GEOMETRIC TEST FOR R1.

The extracted SPICE splits the reference's `pwm_out` into FOUR nets:
    _214_/X, u_rs_branch/net, u_rs_via1/net, u_rs_via2/net
while the DEF declares them ONE net.

Test: for each research macro, compute where the LEF pin lands under
  (a) ORIGIN ignored      abs = place + lef_rect
  (b) ORIGIN applied      abs = place + ORIGIN + lef_rect
and measure the distance from each pwm_out wire ENDPOINT to (a) and (b).

If every wire endpoint coincides with (b) and not (a), then the router used
the ORIGIN-adjusted pin. Magic's extraction did not connect, so Magic's
black-box port is NOT at (b).
"""
import os
import re

from paths import RUN as BASE
from paths import REPO as TT
DEF = os.path.join(BASE, 'final/def/tt_um_jiahao_plus_counter.def')

df = open(DEF, encoding='utf-8', errors='replace').read()
m = re.search(r'^\s*-\s+pwm_out\s+(.*?);\s*$', df, re.M | re.S)
rec = m.group(1)

# ---- parse every wire segment (2-pt or 3-number extension form)
SEG = re.compile(
    r'(?P<layer>met[1-5]|li1)\s+'
    r'\(\s*(?P<ax>-?\d+)\s+(?P<ay>-?\d+)(?:\s+0)?\s*\)\s*'
    r'\(\s*(?P<bx>-?\d+|\*)\s+(?P<by>-?\d+|\*)(?:\s+0)?\s*\)')
segs = []
for s in SEG.finditer(rec):
    ax, ay = int(s.group('ax')) / 1000.0, int(s.group('ay')) / 1000.0
    bx = ax if s.group('bx') == '*' else int(s.group('bx')) / 1000.0
    by = ay if s.group('by') == '*' else int(s.group('by')) / 1000.0
    segs.append((s.group('layer'), ax, ay, bx, by))

print('=' * 78)
print('pwm_out wire segments parsed from the final DEF')
print('=' * 78)
print('  count: %d' % len(segs))
for sg in segs:
    print('    %-5s (%8.3f,%8.3f) -> (%8.3f,%8.3f)'
          % (sg[0], sg[1], sg[2], sg[3], sg[4]))

# endpoints = vertices that appear once
from collections import Counter
pts = Counter()
for lay, ax, ay, bx, by in segs:
    pts[(round(ax, 3), round(ay, 3))] += 1
    pts[(round(bx, 3), round(by, 3))] += 1
ends = [p for p, c in pts.items() if c == 1]
print()
print('  dangling endpoints: %d' % len(ends))
for p in sorted(ends):
    print('    (%8.3f, %8.3f)' % p)

# ---- macro pin predictions
MACROS = [
    ('u_rs_branch', 'research_branch', (79.320, 208.000), (0.930, 4.830),
     ('met1', (0.000, 0.100, 0.140, 0.240))),
    ('u_rs_via1', 'research_via1', (33.500, 208.000), (0.930, 1.930),
     ('met1', (0.000, 0.000, 0.140, 0.140))),
    ('u_rs_via2', 'research_via2', (64.000, 208.000), (0.930, 1.930),
     ('met2', (0.000, 0.000, 0.140, 0.140))),
]


def dist_to_rect(px, py, x0, y0, x1, y1):
    dx = max(x0 - px, 0.0, px - x1)
    dy = max(y0 - py, 0.0, py - y1)
    return (dx * dx + dy * dy) ** 0.5


print()
print('=' * 78)
print('WIRE ENDPOINT vs MACRO PIN, BOTH ORIGIN CONVENTIONS')
print('=' * 78)
for inst, cls, (px, py), (ox, oy), (lay, r) in MACROS:
    x0, y0 = px + r[0], py + r[1]
    x1, y1 = px + r[2], py + r[3]
    ax0, ay0 = x0 + ox, y0 + oy
    ax1, ay1 = x1 + ox, y1 + oy
    print()
    print('  %s (%s) placed (%.3f, %.3f) ORIGIN (%.3f, %.3f)'
          % (inst, cls, px, py, ox, oy))
    print('     pin IGNORING origin : %s (%.3f,%.3f)-(%.3f,%.3f)'
          % (lay, x0, y0, x1, y1))
    print('     pin APPLYING origin : %s (%.3f,%.3f)-(%.3f,%.3f)'
          % (lay, ax0, ay0, ax1, ay1))
    best_ign = min((dist_to_rect(ex, ey, x0, y0, x1, y1), ex, ey)
                   for ex, ey in ends)
    best_org = min((dist_to_rect(ex, ey, ax0, ay0, ax1, ay1), ex, ey)
                   for ex, ey in ends)
    print('     nearest wire endpoint, IGNORING origin: d=%.3f um at (%.3f,%.3f)'
          % best_ign)
    print('     nearest wire endpoint, APPLYING origin: d=%.3f um at (%.3f,%.3f)'
          % best_org)
    verdict = 'APPLYING' if best_org[0] < best_ign[0] - 0.05 else 'IGNORING'
    print('     => router used ORIGIN-%s convention' % verdict)

print()
print('=' * 78)
print('SAME TEST FOR THE TWO STDCEL ENDS (controls)')
print('=' * 78)
for nm, (cx, cy) in (('_214_ X pin', (172.04, 217.60)),
                     ('_218_ B1 pin', (101.66, 214.88))):
    best = min((dist_to_rect(cx, cy, ex, ey, ex, ey), ex, ey) for ex, ey in ends)
    print('  %-14s nearest wire endpoint d=%.3f um at (%.3f, %.3f)'
          % (nm, best[0], best[1], best[2]))
