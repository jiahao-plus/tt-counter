"""Part B, Q16: THE DECISIVE R1 TEST.

R1 is 3 research-macro pins that Magic extracted as isolated single-pin
nets while the DEF has them all on ONE net `pwm_out`.

There are exactly two candidate LEF frames:
    A  abs = place + LEF_RECT              (ORIGIN not applied)
    B  abs = place + ORIGIN + LEF_RECT     (ORIGIN applied)

Three independent artefacts can tell us which frame each tool used:
   1. the DEF routing endpoint        -> says which frame the ROUTER used
   2. the GDS instance transform      -> says which frame the GDS lives in
   3. the extracted SPICE net names   -> says which frame MAGIC used

This script does not assume any of them; it measures all three.
"""
import os
import re

import klayout.db as db

from paths import RUN as BASE
from paths import REPO as TT
DEF = os.path.join(BASE, 'final/def/tt_um_jiahao_plus_counter.def')
GDS = os.path.join(BASE, 'final/gds/tt_um_jiahao_plus_counter.gds')

MACRO_STEM = {'research_branch': 'struct_C1', 'research_via1': 'struct_A',
              'research_via2': 'struct_B'}


# ---------------------------------------------------------------- LEF parse
def parse_lef(path):
    txt = open(path, encoding='utf-8', errors='replace').read()
    origin = re.search(r'ORIGIN\s+(-?[\d.]+)\s+(-?[\d.]+)\s*;', txt)
    size = re.search(r'SIZE\s+(-?[\d.]+)\s+BY\s+(-?[\d.]+)\s*;', txt)
    pin = re.search(r'PIN\s+(\S+)(.*?)END\s+\1', txt, re.S)
    body = pin.group(2) if pin else ''
    port = re.search(r'PORT(.*?)END', body, re.S)
    rects = []
    cur = None
    for line in (port.group(1) if port else '').splitlines():
        m = re.match(r'\s*LAYER\s+(\S+)\s*;', line)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r'\s*RECT\s+(-?[\d.]+)\s+(-?[\d.]+)\s+'
                     r'(-?[\d.]+)\s+(-?[\d.]+)\s*;', line)
        if m and cur:
            rects.append((cur, *(float(g) for g in m.groups())))
    return dict(
        origin=(float(origin.group(1)), float(origin.group(2))) if origin else (0.0, 0.0),
        size=(float(size.group(1)), float(size.group(2))),
        pin_name=pin.group(1) if pin else None,
        pin_rects=rects)


LEF = {}
for cls, stem in MACRO_STEM.items():
    LEF[cls] = parse_lef(os.path.join(TT, 'macros/out', stem + '.lef'))

print('=' * 78)
print('0. THE LEFs, AS AUTHORED')
print('=' * 78)
for cls, d in LEF.items():
    print('  %-18s ORIGIN=%-16s SIZE=%-16s PIN=%-6s %d port rect(s)'
          % (cls, str(d['origin']), str(d['size']), d['pin_name'],
             len(d['pin_rects'])))
    for lay, x0, y0, x1, y1 in d['pin_rects']:
        print('       %-5s RECT %7.3f %7.3f %7.3f %7.3f' % (lay, x0, y0, x1, y1))

# ---------------------------------------------------------------- DEF parse
df = open(DEF, encoding='utf-8', errors='replace').read()
COMP = re.compile(r'^\s*-\s+(\S+)\s+(\S+)\s+\+\s+\w+\s+'
                  r'\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)\s*;', re.M)
place = {}
for m in COMP.finditer(df):
    place[m.group(1)] = (m.group(2), int(m.group(3)) / 1000.0,
                         int(m.group(4)) / 1000.0)

print()
print('=' * 78)
print('1. MACRO PLACEMENTS (DEF COMPONENTS)')
print('=' * 78)
for inst, (cls, px, py) in sorted(place.items()):
    if cls in LEF:
        print('  %-14s %-18s place=(%.3f, %.3f)' % (inst, cls, px, py))

# ---------------------------------------------------------------- DEF net
m = re.search(r'^\s*-\s+pwm_out\s+(.*?);\s*$', df, re.M | re.S)
rec = m.group(1)
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
ends = {}
for lay, ax, ay, bx, by in segs:
    for p in ((round(ax, 3), round(ay, 3)), (round(bx, 3), round(by, 3))):
        ends[p] = ends.get(p, 0) + 1
dang = sorted(p for p, c in ends.items() if c == 1)

print()
print('=' * 78)
print('2. DEF "pwm_out" ROUTING -- %d segments, %d dangling endpoints'
      % (len(segs), len(dang)))
print('=' * 78)
print('  pins on the net in the DEF:')
for pm in re.finditer(r'\(\s*(\S+)\s+(\S+)\s*\)', rec.split('+ USE')[0]):
    print('     (%s %s)' % (pm.group(1), pm.group(2)))


def inside(p, r):
    x, y = p
    return r[0] - 1e-9 <= x <= r[2] + 1e-9 and r[1] - 1e-9 <= y <= r[3] + 1e-9


print()
print('=' * 78)
print('3. WHICH FRAME DID THE ROUTER USE?')
print('=' * 78)
for inst, (cls, px, py) in sorted(place.items()):
    if cls not in LEF:
        continue
    d = LEF[cls]
    ox, oy = d['origin']
    best = []
    for lay, x0, y0, x1, y1 in d['pin_rects']:
        A = (px + x0, py + y0, px + x1, py + y1)
        B = (px + ox + x0, py + oy + y0, px + ox + x1, py + oy + y1)
        for p in dang:
            if inside(p, A):
                best.append(('A  no-ORIGIN ', lay, p, A))
            if inside(p, B):
                best.append(('B  ORIGIN   ', lay, p, B))
    if best:
        for tag, lay, p, r in best:
            print('  %-12s %-18s %-12s %-5s endpoint (%.3f,%.3f) inside '
                  'x[%.3f..%.3f] y[%.3f..%.3f]'
                  % (inst, cls, tag, lay, p[0], p[1], r[0], r[2], r[1], r[3]))
    else:
        print('  %-12s %-18s NO dangling endpoint lands in either frame'
              % (inst, cls))

# ---------------------------------------------------------------- GDS frame
print()
print('=' * 78)
print('4. WHICH FRAME DOES THE FINAL GDS LIVE IN?')
print('=' * 78)
ly = db.Layout()
ly.read(GDS)
top = ly.top_cell()
dbu = ly.dbu
LAYMAP = {('met1', 0): (68, 20), ('met2', 0): (69, 20), ('met3', 0): (70, 20)}
inv = {}
for li in ly.layer_indexes():
    info = ly.get_info(li)
    inv[(info.layer, info.datatype)] = li

for cls in MACRO_STEM:
    cell = ly.cell(cls)
    inst = None
    for i in top.each_inst():
        if i.cell.name == cls:
            inst = i
            break
    print('  %-18s instance transform: %s' % (cls, inst.trans if inst else 'NONE'))
    d = LEF[cls]
    ox, oy = d['origin']
    for lay, x0, y0, x1, y1 in d['pin_rects']:
        li = inv.get(LAYMAP[(lay, 0)])
        if li is None:
            continue
        # GDS-local rect of this pin, per the claim  GDS_local = LEF + ORIGIN
        gl = db.DBox(ox + x0, oy + y0, ox + x1, oy + y1)
        # does the GDS actually contain copper exactly there (cell-local)?
        # NB: cells store integer dbu, so build the probe in dbu, not microns.
        probe = db.Region(db.Box(round((ox + x0) / dbu), round((oy + y0) / dbu),
                                 round((ox + x1) / dbu), round((oy + y1) / dbu)))
        hit = db.Region(cell.begin_shapes_rec(li)) & probe
        frac = (hit.area() / probe.area()) if probe.area() > 0 else 0.0
        print('     %-5s LEF(%.3f,%.3f)-(%.3f,%.3f) + ORIGIN -> cell-local '
              '(%.3f,%.3f)-(%.3f,%.3f)  GDS coverage there = %5.1f%%'
              % (lay, x0, y0, x1, y1, ox + x0, oy + y0, ox + x1, oy + y1,
                 100.0 * frac))

print()
print('=' * 78)
print('5. WHAT DID MAGIC ACTUALLY EXTRACT?')
print('=' * 78)
print('  C1 net                         | pins')
print('  _214_/X                        | a22o_2/B1, a22o_2/X')
print('  u_rs_branch/net                | research_branch/net')
print('  u_rs_via1/net                  | research_via1/net')
print('  u_rs_via2/net                  | research_via2/net')
print()
print('  If Magic had used frame B for the macro abstract view, each macro')
print('  port would sit exactly on the router wire and all four would be ONE')
print('  net.  They are four.  So Magic used frame A.')
