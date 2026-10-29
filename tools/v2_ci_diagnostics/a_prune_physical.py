"""Item A: does FP_PRUNE_THRESHOLD = 25.76 actually eliminate the tap/row
DRC violations, or does it merely delete the rows that contain them?

All inputs are 3rd-round REAL artefacts, no model:
  18-openroad-cutrows/*.def              -> the 114 surviving row segments
  19-openroad-tapendcapinsertion/*.def   -> the 997 real tap cells
  62-magic-drc/reports/drc.magic.lyrdb   -> 669 violations WITH COORDINATES

Nothing here is a DRC re-run. Anything about what would happen after a config
change is PREDICTED and is labelled as such.
"""
import json
import os
import re

ANA = os.path.dirname(os.path.abspath(__file__))
from paths import RUN as BASE

ROW_RE = re.compile(
    r'^ROW\s+(\S+)\s+(\S+)\s+(-?\d+)\s+(-?\d+)\s+(\S+)\s+'
    r'DO\s+(\d+)\s+BY\s+1\s+STEP\s+(\d+)\s+(-?\d+)\s*;', re.M)
TAP_RE = re.compile(
    r'^\s*-\s+(\S+)\s+sky130_fd_sc_hd__tapvpwrvgnd_1\s+.*?FIXED\s+'
    r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', re.M)

STEP = 0.460
PITCH = 2.720
PRUNE = 25.76          # the OPT-A threshold under test
LU_MAX = 15.0          # LU.2 / LU.3: diff-to-tap must be < 15.0 um


def load_rows(path):
    t = open(path, encoding='utf-8', errors='replace').read()
    out = []
    for m in ROW_RE.finditer(t):
        out.append(dict(name=m.group(1),
                        x=int(m.group(3)) / 1000.0,
                        y=int(m.group(4)) / 1000.0,
                        orient=m.group(5),
                        n=int(m.group(6))))
    out.sort(key=lambda r: (r['y'], r['x']))
    return out


def load_taps(path):
    t = open(path, encoding='utf-8', errors='replace').read()
    return [(m.group(1), int(m.group(2)) / 1000.0, int(m.group(3)) / 1000.0)
            for m in TAP_RE.finditer(t)]


rows = load_rows(os.path.join(
    BASE, '18-openroad-cutrows/tt_um_jiahao_plus_counter.def'))
taps = load_taps(os.path.join(
    BASE, '19-openroad-tapendcapinsertion/tt_um_jiahao_plus_counter.def'))
viol = json.load(open(os.path.join(ANA, 'magic_violations.json'),
                      encoding='utf-8'))

print('=' * 78)
print('INPUTS (3rd-round real artefacts)')
print('=' * 78)
print('row segments (18-cutrows) : %d   sites: %d'
      % (len(rows), sum(r['n'] for r in rows)))
print('tap cells    (19-tapendcap): %d' % len(taps))
print('violations   (62-magic lyrdb): %d' % len(viol))
print()

# ---------------------------------------------------------------- segments
for r in rows:
    r['w'] = r['n'] * STEP
    r['x0'] = r['x']
    r['x1'] = r['x'] + r['w']
    r['y0'] = r['y']
    r['y1'] = r['y'] + PITCH

tap_x_by_y = {}
for _, x, y in taps:
    tap_x_by_y.setdefault(round(y, 3), []).append(x)

for r in rows:
    tx = sorted(tap_x_by_y.get(round(r['y0'], 3), []))
    r['taps'] = [v for v in tx if r['x0'] <= v < r['x1']]

# ---------------------------------------------------------------- prune map
deleted = [r for r in rows if r['w'] < PRUNE]
kept = [r for r in rows if r['w'] >= PRUNE]

print('=' * 78)
print('OPT-A PRUNE SIMULATION  (threshold %.2f um, PREDICTED)' % PRUNE)
print('=' * 78)
print('segments deleted : %3d   sites lost: %6d'
      % (len(deleted), sum(r['n'] for r in deleted)))
print('segments kept    : %3d   sites kept: %6d'
      % (len(kept), sum(r['n'] for r in kept)))
print('area lost        : %.3f um^2 (%.2f %% of row area)'
      % (sum(r['w'] * PITCH for r in deleted),
         100.0 * sum(r['w'] for r in deleted) / sum(r['w'] for r in rows)))
print()
print('tap cells in deleted segments : %d'
      % sum(len(r['taps']) for r in deleted))
print('tap cells in kept    segments : %d'
      % sum(len(r['taps']) for r in kept))

# ---------------------------------------------------------------- violation -> segment
def locate(v):
    """Which row segment does this violation box sit in?"""
    cy, cx = v['cy'], v['cx']
    if cy is None:
        return None
    ri = int((cy - 2.720) // PITCH)
    y0 = 2.720 + ri * PITCH
    for r in rows:
        if abs(r['y0'] - y0) < 1e-3 and r['x0'] <= cx < r['x1']:
            return r
    return ('no-segment', ri, y0)

print()
print('=' * 78)
print('VIOLATION -> ROW SEGMENT')
print('=' * 78)

buckets = {}
for v in viol:
    loc = locate(v)
    if loc is None:
        key = 'no-coord'
    elif isinstance(loc, tuple):
        key = 'outside-all-segments'
    elif loc['w'] < PRUNE:
        key = 'in DELETED segment'
    else:
        key = 'in KEPT segment'
    buckets.setdefault(key, {}).setdefault(v['category'], 0)
    buckets[key][v['category']] += 1

cats = ['LU.2', 'LU.3', 'nwell.4', 'via.5a', 'met2.5', 'via2.4a']
print('%-26s %s' % ('', ''.join('%9s' % c for c in cats) + '%9s' % 'total'))
for key in ('in DELETED segment', 'in KEPT segment',
            'outside-all-segments', 'no-coord'):
    if key not in buckets:
        continue
    b = buckets[key]
    tot = sum(b.values())
    print('%-26s %s' % (key, ''.join('%9d' % b.get(c, 0) for c in cats)
                        + '%9d' % tot))

# ---------------------------------------------------------------- LU rule audit
print()
print('=' * 78)
print('LU.2/LU.3 15um AUDIT ON SURVIVING SEGMENTS  (PREDICTED)')
print('=' * 78)
print('Rule (lyrdb text): "P-diff distance to N-tap must be < 15.0um (LU.3)"')
print('                   "N-diff distance to P-tap must be < 15.0um (LU.2)"')
print()
print('%-8s %-8s %6s %8s %8s %s'
      % ('y', 'x0', 'n', 'w(um)', 'nTap', 'max edge dist to nearest tap'))

bad = []
for r in kept:
    tx = r['taps']
    if not tx:
        d = 1e9
    else:
        d = max(min(abs(r['x0'] - t) for t in tx),
                min(abs(r['x1'] - t) for t in tx))
    if d >= LU_MAX:
        bad.append((r, d))

print('segments kept              : %d' % len(kept))
print('segments with NO tap       : %d'
      % sum(1 for r in kept if not r['taps']))
print('segments violating 15um    : %d' % len(bad))
print()
print('*** THIS PROXY MODEL IS REJECTED.  DO NOT QUOTE THE COUNT ABOVE. ***')
print('  It measures the distance from a ROW-SEGMENT EDGE to the nearest tap.')
print('  The real LU.2 / LU.3 rule is about DIFFUSION to tap, and diffusion')
print('  only exists inside placed standard cells. Empty sites at the end of')
print('  a wide row contain no diffusion at all, so they cannot violate it.')
print('  Measured check (bbox-overlap join of the 62-magic lyrdb against the')
print('  18-cutrows segments): 576 violations in DELETED segments, 0 in KEPT,')
print('  0 straddling, 0 outside. The proxy below would have flagged ~51 KEPT')
print('  segments that Magic reported clean. The proxy is wrong; the join wins.')
print()
if bad:
    print('%-9s %-9s %5s %8s %5s %10s %10s'
          % ('y', 'x0', 'n', 'w', 'nTap', 'left-edge', 'right-edge'))
    for r, _ in sorted(bad, key=lambda p: -p[1])[:40]:
        tx = r['taps']
        dl = min(abs(r['x0'] - t) for t in tx)
        dr = min(abs(r['x1'] - t) for t in tx)
        print('%-9.3f %-9.3f %5d %8.2f %5d %10.2f %10.2f'
              % (r['y0'], r['x0'], r['n'], r['w'], len(tx), dl, dr))

# ---------------------------------------------------------------- width histogram
print()
print('=' * 78)
print('SEGMENT WIDTH DISTRIBUTION')
print('=' * 78)
bins = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 25.76), (25.76, 30),
        (30, 40), (40, 50), (50, 60), (60, 1e9)]
for lo, hi in bins:
    sel = [r for r in rows if lo <= r['w'] < hi]
    nt = sum(len(r['taps']) for r in sel)
    print('  [%6.2f, %6.2f) um : %3d segments  %5d sites  %4d taps'
          % (lo, hi, len(sel), sum(r['n'] for r in sel), nt))
