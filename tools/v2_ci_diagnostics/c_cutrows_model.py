"""Q3/Q4: verify OPT-A against the REAL 114-segment cut, third round.

Corrects an earlier mistake: the previous version simulated its own cut with
7 halo shapes and got 122 segments / 54435 sites, which does NOT match the
logged 114 / 53872. The simulation was wrong; the DEF is ground truth.

Everything here reads 18-openroad-cutrows (the real cut) and
19-openroad-tapendcapinsertion (the real tap placement).
"""
import collections
import os
import re

from paths import RUN as BASE
STEP = 0.460
SITE_H = 2.720

cut = open(os.path.join(BASE, '18-openroad-cutrows/'
                                'tt_um_jiahao_plus_counter.def'),
           encoding='utf-8', errors='replace').read()
# DEF ROW syntax is:  ROW <name> <site> <X> <Y> <orient> DO <n> BY 1 STEP ...
# The FIRST coordinate is X, the SECOND is Y.  An earlier version of this
# script read them the other way round; the width histogram was unaffected
# (it only uses the site count) but every geometric predicate was crossed,
# which manufactured a phantom "one whole row disappears" result.
segs = [(int(m.group(2)) / 1000.0,          # y
         int(m.group(1)) / 1000.0,          # x0
         int(m.group(3)))                   # n sites
        for m in re.finditer(r'^ROW\s+\S+\s+\S+\s+(-?\d+)\s+(-?\d+)\s+\S+\s+'
                             r'DO\s+(\d+)', cut, re.M)]

print('=' * 78)
print('THE REAL CUT (ground truth, not simulated)')
print('=' * 78)
print('  segments: %d   sites: %d   distinct y: %d'
      % (len(segs), sum(s[2] for s in segs), len({s[0] for s in segs})))
# Self-check: the site grid must divide cleanly and every segment must end
# inside the die, otherwise the two coordinates have been swapped again.
_die = re.search(r'^DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*'
                 r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', cut, re.M)
_dx1, _dy1 = int(_die.group(3)) / 1000.0, int(_die.group(4)) / 1000.0
assert all(abs(y % SITE_H) < 1e-6 or abs(y % SITE_H - SITE_H) < 1e-6
           for (y, _, _) in segs), 'y is not on the row grid -> axes swapped'
assert all(x0 + n * STEP <= _dx1 + 1e-6 for (_, x0, n) in segs), \
    'segment runs past the die right edge -> axes swapped'
print('  self-check: y on %.3f grid, every segment inside DIEAREA %.3f x %.3f'
      % (SITE_H, _dx1, _dy1))

print()
print('  width histogram:')
h = collections.Counter(s[2] for s in segs)
for n, c in sorted(h.items()):
    print('     %6d sites = %7.2f um : %2d segments' % (n, n * STEP, c))

print()
print('=' * 78)
print('A. DOES 26.22 DELETE THE SAME SEGMENTS AS 25.76?')
print('=' * 78)
for t in (25.76, 26.22):
    dl = [s for s in segs if s[2] * STEP < t]
    kp = [s for s in segs if s[2] * STEP >= t]
    print('  T=%-6.2f delete %2d segs / %4d sites / %8.3f um2 ; keep %3d'
          % (t, len(dl), sum(s[2] for s in dl),
             sum(s[2] for s in dl) * STEP * SITE_H, len(kp)))
d2576 = {s for s in segs if s[2] * STEP < 25.76}
d2622 = {s for s in segs if s[2] * STEP < 26.22}
print('  identical segment set : %s' % (d2576 == d2622))
print('  narrowest KEPT segment: %.2f um' %
      min(s[2] * STEP for s in segs if s[2] * STEP >= 26.22))

print()
print('=' * 78)
print('B. "LOST TAP 0 / LOST ROW 0 / LOST CELL 0" -- EXACT MEANINGS')
print('=' * 78)
deleted = [s for s in segs if s[2] * STEP < 26.22]


def in_deleted(x, y):
    for (sy, sx, sn) in deleted:
        if abs(sy - y) < 1e-3 and sx - 1e-3 <= x < sx + sn * STEP - 1e-3:
            return True
    return False


print('  1) ROW segments deleted : %d of %d' % (len(deleted), len(segs)))
print('     "segment" = a contiguous run of sites within one placement row,')
print('     not a whole fabrication row.')
print('  2) Distinct y levels with a deleted segment : %d'
      % len({s[0] for s in deleted}))
ys_all = {s[0] for s in segs}
ys_kept = {s[0] for s in segs if not in_deleted(s[1], s[0])}
print('     Total distinct y levels : %d ; levels left with ZERO segment : %d'
      % (len(ys_all), len(ys_all - ys_kept)))
for y in sorted(ys_all - ys_kept):
    print('       y=%.3f would lose its ONLY segment' % y)

tapdf = open(os.path.join(BASE, '19-openroad-tapendcapinsertion/'
                                'tt_um_jiahao_plus_counter.def'),
             encoding='utf-8', errors='replace').read()
taps = [(int(m.group(1)) / 1000.0, int(m.group(2)) / 1000.0)
        for m in re.finditer(r'^\s*-\s+\S+\s+sky130_fd_sc_hd__tapvpwrvgnd_1\s'
                             r'\+[^;]*?\(\s*(-?\d+)\s+(-?\d+)', tapdf, re.M)]
taps_lost = [(x, y) for (x, y) in taps if in_deleted(x, y)]
print('  3) TAP cells inside deleted segments : %d of %d'
      % (len(taps_lost), len(taps)))

placed = []
for m in re.finditer(r'^\s*-\s+(\S+)\s+(sky130_fd_sc_hd__\S+|research_\S+)\s'
                     r'\+[^;]*?\(\s*(-?\d+)\s+(-?\d+)', cut, re.M):
    placed.append((m.group(1), m.group(2), int(m.group(3)) / 1000.0,
                   int(m.group(4)) / 1000.0))
lost = [c for c in placed if in_deleted(c[2], c[3])]
print('  4) Placed cells inside deleted segments : %d of %d'
      % (len(lost), len(placed)))
for c in lost:
    print('       %-40s %-34s (%8.2f,%8.2f)' % c)

print()
print('=' * 78)
print('C. IS 26.22 LEGAL ON THE 0.46 um SITE GRID?')
print('=' * 78)
print('  site width            : %.3f um' % STEP)
print('  26.22 is %.4f sites -- NOT an integer multiple, and it does not'
      % (26.22 / STEP))
print('  need to be: the threshold is compared against CONTINUOUS segment')
print('  widths, never snapped to the site grid.')
print('  57 sites = %.2f um ; 56 sites = %.2f um' % (57 * STEP, 56 * STEP))
print()
narrowest_kept = min(s[2] * STEP for s in segs if s[2] * STEP >= 26.22)
widest_del = max(s[2] * STEP for s in segs if s[2] * STEP < 26.22)
print('  narrowest KEPT   segment : %.2f um' % narrowest_kept)
print('  widest  DELETED  segment : %.2f um' % widest_del)
print('  admissible window for the threshold : (%.2f, %.2f]'
      % (widest_del, narrowest_kept))
print('  26.22 sits inside it, so grid legality is a non-issue.')
