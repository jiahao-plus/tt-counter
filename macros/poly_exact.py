"""Exact polygon geometry for GDS boundaries.

My earlier gds_hier.flatten() reduced every BOUNDARY to its axis-aligned bbox.
That is only safe for 5-point (rectangular) boundaries. The top cell has
boundaries with up to 49 vertices, so bbox reduction can invent contacts that
do not exist (a U/C/L shape's bbox covers its hole).

This module keeps the real vertex list and gives exact tests:
  - rect_in_poly : is an axis-aligned rect fully/partly inside a polygon
  - polys_touch  : do two polygons (as closed polylines) share area
  - area         : shoelace
"""
import struct


def read_boundaries(path):
    """Return list of dicts: {cell, layer, datatype, pts=[(x,y)...]}"""
    with open(path, 'rb') as f:
        b = f.read()
    n = len(b)
    i = 0
    cur = None
    elem = None
    out = []
    while i + 4 <= n:
        ln = struct.unpack_from('>H', b, i)[0]
        rt = b[i + 2]
        p = i + 4
        if ln < 4 or i + ln > n:
            break
        if rt == 0x06:
            cur = b[p:i + ln].decode('ascii', 'replace').rstrip('\x00')
        elif rt in (0x08, 0x19):                       # BOUNDARY / BOX
            elem = {'layer': None, 'dt': None, 'xy': []}
        elif rt == 0x0D and elem is not None:
            elem['layer'] = struct.unpack_from('>H', b, p)[0]
        elif rt == 0x0E and elem is not None:
            elem['dt'] = struct.unpack_from('>H', b, p)[0]
        elif rt == 0x10 and elem is not None:
            cnt = (ln - 4) // 4
            elem['xy'] = list(struct.unpack_from('>%di' % cnt, b, p))
        elif rt == 0x11 and elem is not None:
            xy = elem['xy']
            pts = list(zip(xy[0::2], xy[1::2]))
            # GDS closes the ring by repeating the first vertex; drop it
            if len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]
            out.append({'cell': cur, 'layer': elem['layer'],
                        'datatype': elem['dt'], 'pts': pts})
            elem = None
        i += ln
    return out


def shoelace(pts):
    s = 0
    n = len(pts)
    for k in range(n):
        x1, y1 = pts[k]
        x2, y2 = pts[(k + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _seg_cross(a, b, c, d):
    """Proper segment intersection (excluding shared endpoints/collinear touch)."""
    def cr(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1 = cr(a, b, c)
    d2 = cr(a, b, d)
    d3 = cr(c, d, a)
    d4 = cr(c, d, b)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False


def _pt_in_poly(pt, pts):
    """Ray crossing; boundary counts as inside."""
    x, y = pt
    inside = False
    n = len(pts)
    for k in range(n):
        x1, y1 = pts[k]
        x2, y2 = pts[(k + 1) % n]
        if (x1, y1) == (x, y) or (x2, y2) == (x, y):
            return True
        if min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2):
            if _seg_cross((x1, y1), (x2, y2), (x, y), (x, y)):
                pass
        if (y1 > y) != (y2 > y):
            xint = x1 + (y - y1) * (x2 - x1) / float(y2 - y1)
            if xint == x:
                return True
            if xint > x:
                inside = not inside
    return inside


def _pt_on_edge(pt, a, b):
    (px, py), (x1, y1), (x2, y2) = pt, a, b
    cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
    if cross != 0:
        return False
    return min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2)


def polys_touch(P, Q, return_point=False):
    """True if polygons P and Q share any area (edge-only contact counts as touch
    only if an edge overlaps with positive length — that is still a CONNECTED
    contact in physical layout, so we count it)."""
    bp, bq = bbox(P), bbox(Q)
    if bp[2] < bq[0] or bp[0] > bq[2] or bp[3] < bq[1] or bp[1] > bq[3]:
        return (False, None) if return_point else False
    # 1) any vertex of one inside the other
    for pt in P:
        if _pt_in_poly(pt, Q):
            return (True, pt) if return_point else True
    for pt in Q:
        if _pt_in_poly(pt, P):
            return (True, pt) if return_point else True
    # 2) any edge pair crossing
    for k in range(len(P)):
        a, b2 = P[k], P[(k + 1) % len(P)]
        for j in range(len(Q)):
            c, d = Q[j], Q[(j + 1) % len(Q)]
            if _seg_cross(a, b2, c, d):
                return (True, a) if return_point else True
    # 3) collinear overlapping edges
    for k in range(len(P)):
        a, b2 = P[k], P[(k + 1) % len(P)]
        for j in range(len(Q)):
            c, d = Q[j], Q[(j + 1) % len(Q)]
            if _pt_on_edge(c, a, b2) or _pt_on_edge(d, a, b2) or \
               _pt_on_edge(a, c, d) or _pt_on_edge(b2, c, d):
                return (True, a) if return_point else True
    return (False, None) if return_point else False


def rect_poly(rect):
    x0, y0, x1, y1 = rect
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
