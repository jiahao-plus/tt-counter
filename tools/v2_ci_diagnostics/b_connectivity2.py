"""Part B, Q6b: via-aware connectivity, CORRECT shape selection.

The earlier attempt intersected (which returns only the overlap, not the
whole shape) and so never grew.  Here we use Region.interacting(), which
selects every polygon of a layer that touches the current frontier.

Ground truth = final streamed GDS.  No Magic, no netgen.
"""
import os
import sys

import klayout.db as db

from paths import RUN as BASE
GDS = os.path.join(BASE, 'final/gds/tt_um_jiahao_plus_counter.gds')

ly = db.Layout()
ly.read(GDS)
top = ly.top_cell()
dbu = ly.dbu

LAYERS = [('li1', (67, 20)), ('mcon', (67, 44)),
          ('met1', (68, 20)), ('via1', (68, 44)),
          ('met2', (69, 20)), ('via2', (69, 44)),
          ('met3', (70, 20))]

R = {}
for nm, (l, d) in LAYERS:
    li = ly.layer(l, d)
    if li is None:
        continue
    reg = db.Region(top.begin_shapes_rec(li))
    reg.merge()
    R[nm] = reg

# (lower metal, via, upper metal)
STACK = [('li1', 'mcon', 'met1'), ('met1', 'via1', 'met2'),
         ('met2', 'via2', 'met3')]
ORDER = [n for n, _ in LAYERS if n in R]


def box(x, y, tol):
    return db.DBox(int(round((x - tol) / dbu)), int(round((y - tol) / dbu)),
                   int(round((x + tol) / dbu)), int(round((y + tol) / dbu)))


def grow(seeds, maxiter=200):
    """seeds: [(layer, x, y)].  Returns {layer: Region} reachable."""
    cur = {k: db.Region() for k in R}
    for lay, x, y in seeds:
        if lay not in R:
            continue
        hit = R[lay].interacting(db.Region(box(x, y, 0.05)))
        if not hit.is_empty():
            cur[lay] = (cur[lay] + hit).merge()
    for it in range(maxiter):
        before = sum(cur[k].area() for k in cur)
        # propagate through vias, then expand metals inside owned vias
        for lo, vi, up in STACK:
            if vi not in R:
                continue
            frontier = db.Region()
            for m in (lo, up):
                if cur[m].area() > 0:
                    frontier += cur[m]
            if frontier.area() > 0:
                nv = R[vi].interacting(frontier)
                if not nv.is_empty():
                    cur[vi] = (cur[vi] + nv).merge()
            if cur[vi].area() > 0:
                for m in (lo, up):
                    nm = R[m].interacting(cur[vi])
                    if not nm.is_empty():
                        cur[m] = (cur[m] + nm).merge()
        after = sum(cur[k].area() for k in cur)
        if abs(after - before) < 1.0:
            break
    return cur, it


def touches(cur, lay, x, y, tol=0.06):
    if lay not in cur or cur[lay].area() == 0:
        return False
    return not (cur[lay] & db.Region(box(x, y, tol))).is_empty()


SEED = [('met1', 172.73, 218.11)]
cur, iters = grow(SEED)

print('=' * 78)
print('VIA-AWARE CONNECTIVITY FROM _214_ OUTPUT WIRE (final GDS)')
print('=' * 78)
print('  seed   : met1 (172.73, 218.11)   iterations=%d' % iters)
tot = 0.0
for lay in ORDER:
    b = cur[lay].bbox()
    a = cur[lay].area() * dbu * dbu
    tot += a
    print('     %-5s area=%12.3f um^2  bbox_um=%s'
          % (lay, a, b.to_dtype(dbu) if not cur[lay].is_empty() else '-'))
print('  total copper area reachable: %.3f um^2' % tot)

TARGETS = [
    ('_218_ output met1',        'met1', 104.190, 216.070),
    ('u_rs_via1 met1 pin',       'met1',  34.500, 210.000),
    ('u_rs_via1 met2 pin',       'met2',  42.500, 212.000),
    ('u_rs_via2 met2 pin',       'met2',  65.000, 210.000),
    ('u_rs_via2 met3 pin',       'met3',  75.000, 213.000),
    ('u_rs_branch met1 pin',     'met1',  80.320, 213.000),
    ('u_rs_branch met2 pin#1',   'met2',  81.320, 215.000),
    ('u_rs_branch met2 pin#2',   'met2',  85.320, 215.500),
    ('u_rs_branch met2 pin#3',   'met2',  89.320, 216.000),
]
print()
print('  reachable from the _214_ output?')
for nm, lay, x, y in TARGETS:
    print('     %-26s %s' % (nm, 'YES  connected' if touches(cur, lay, x, y)
                             else 'NO   DISCONNECTED'))

print()
print('=' * 78)
print('CONTROL: grow from a VGND strap point -- must be a different net')
print('=' * 78)
# find a met1 shape far away and use it as a control
ctl = R['met1'].bbox()
cx = ctl.left * dbu + 5.0
cy = ctl.bottom * dbu + 5.0
c2, it2 = grow([('met1', cx, cy)])
a2 = sum(c2[k].area() * dbu * dbu for k in c2)
print('  control seed met1 (%.2f, %.2f): total area %.3f um^2, iters=%d'
      % (cx, cy, a2, it2))
print('  control reaches _214_ output? %s'
      % ('YES (suspicious)' if touches(c2, 'met1', 172.73, 218.11)
         else 'no (expected)'))
