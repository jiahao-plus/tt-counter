"""Q6: does every cell that actually carries a floating bulk pin sit inside a
prunable row segment?

This is the precondition that decides whether OPT-A can work at all.  It is
NOT enough that "some narrow segments exist": the cells whose VPB is floating
must be exactly the cells that get deleted.  If even one floating-VPB cell
lives in a segment that survives, `device_difference` cannot reach 0 and the
21 -> 0 prediction is void.

Method
------
1. Read the post-layout extracted SPICE (step 64) and find every instance whose
   VPB pin is not tied to VPWR.  Continuation lines ('+ ...') are joined first:
   `conb_1` lines wrap, and a token-count filter that ignores the wrap silently
   reports 0.
2. Map the instance name to its DEF placement from the final DEF, and that
   placement to a row segment from the 18-cutrows DEF.
3. Classify the segment as PRUNABLE (width < 26.22 um) or KEPT.

Coordinates: DEF `ROW <name> <site> <X> <Y> ...` -- the FIRST coordinate is X.
Getting this backwards silently crosses every geometric predicate.
"""
import re

from paths import RUN as BASE
STEP = 0.460
PRUNE = 26.22
PRUNE_DBU = int(round(PRUNE * 1000))     # segment widths are kept in dbu

# pin count per class, NOT counting the instance name and the model name
PINS = {'decap_3': 4, 'fill_2': 4, 'fill_1': 4, 'conb_1': 6,
        'tapvpwrvgnd_1': 4}
# pin order is  X<inst> VGND VNB VPB VPWR [HI LO] <model>
I_VPB, I_VPWR = 3, 4


def join_continuations(text):
    out, buf = [], ''
    for ln in text.splitlines():
        if ln.startswith('+'):
            buf += ' ' + ln[1:].strip()
        else:
            if buf:
                out.append(buf)
            buf = ln
    if buf:
        out.append(buf)
    return out


spice = join_continuations(open(
    BASE + '/64-magic-spiceextraction/tt_um_jiahao_plus_counter.spice',
    encoding='utf-8', errors='replace').read())

final_def = open(BASE + '/final/def/tt_um_jiahao_plus_counter.def',
                 encoding='utf-8', errors='replace').read()
comps = re.search(r'COMPONENTS\s+\d+\s*;(.*?)END COMPONENTS',
                  final_def, re.S).group(1)
pos = {}
for m in re.finditer(r'^\s*-\s+(\S+)\s+sky130_fd_sc_hd__\S+\s+\+[^;]*?'
                     r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', comps, re.M):
    pos[m.group(1)] = (int(m.group(2)), int(m.group(3)))   # dbu, (x, y)

cut_def = open(BASE + '/18-openroad-cutrows/'
                      'tt_um_jiahao_plus_counter.def',
               encoding='utf-8', errors='replace').read()
segs = []
for m in re.finditer(r'^ROW\s+\S+\s+\S+\s+(-?\d+)\s+(-?\d+)\s+\S+\s+'
                     r'DO\s+(\d+)', cut_def, re.M):
    x0, y0, n = int(m.group(1)), int(m.group(2)), int(m.group(3))
    segs.append(dict(y=y0, x0=x0, x1=x0 + n * int(STEP * 1000),
                     w=n * int(STEP * 1000)))


def prunable(inst):
    """True / False for in-PRUNABLE / in-KEPT; None if unmapped."""
    if inst not in pos:
        return None
    x, y = pos[inst]
    for s in segs:
        if s['y'] == y and s['x0'] <= x < s['x1']:
            return s['w'] < PRUNE_DBU
    return False


print('=' * 78)
print('CELLS WITH A FLOATING BULK PIN vs THE PRUNE MAP')
print('=' * 78)
print('%-16s %8s %8s %8s %8s' % ('class', 'floating', 'inPRUNE', 'outside', 'unmapped'))
tot = dict(floating=0, inpr=0, out=0, unm=0)
detail = []
for cls, npins in PINS.items():
    fl = []
    for ln in spice:
        p = ln.split()
        if len(p) == npins + 2 and p[-1] == 'sky130_fd_sc_hd__' + cls:
            if p[I_VPB] != p[I_VPWR]:
                fl.append((p[0][1:], p[I_VPB]))
    inpr = sum(1 for i, _ in fl if prunable(i) is True)
    out = sum(1 for i, _ in fl if prunable(i) is False)
    unm = sum(1 for i, _ in fl if prunable(i) is None)
    print('%-16s %8d %8d %8d %8d' % (cls, len(fl), inpr, out, unm))
    tot['floating'] += len(fl); tot['inpr'] += inpr
    tot['out'] += out; tot['unm'] += unm
    detail.append((cls, fl))

print('-' * 78)
print('%-16s %8d %8d %8d %8d'
      % ('TOTAL', tot['floating'], tot['inpr'], tot['out'], tot['unm']))

print()
print('=' * 78)
print('THE 13 FLOATING NETS (a net != a cell: many cells share one net)')
print('=' * 78)
nets = {}
for cls, fl in detail:
    for i, n in fl:
        nets.setdefault(n, []).append((cls, i))
print('  distinct floating bulk nets : %d' % len(nets))
print('  cells attached to them      : %d'
      % sum(len(v) for v in nets.values()))
for n, cells in sorted(nets.items(), key=lambda kv: -len(kv[1])):
    classes = sorted({c for c, _ in cells})
    print('    %-22s %3d cells  (%s)' % (n, len(cells), ', '.join(classes)))

print()
print('=' * 78)
print('VERDICT')
print('=' * 78)
if tot['out'] == 0 and tot['unm'] == 0:
    print('  Every cell whose bulk pin is floating lies inside a PRUNABLE')
    print('  segment, and none lies outside one. Deleting those segments')
    print('  therefore removes every source of the device-group mismatch.')
    print()
    print('  This is a NECESSARY condition for the 21 -> 0 prediction, and it')
    print('  is satisfied. It is NOT sufficient: netgen must still be re-run,')
    print('  and the result stays PREDICTED until it is.')
else:
    print('  *** OPT-A CANNOT WORK AS PREDICTED ***')
    print('  %d floating-bulk cells survive the prune.' % tot['out'])
    print('  Withdraw the candidate change before writing the threshold.')
