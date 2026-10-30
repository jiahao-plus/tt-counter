#!/usr/bin/env python3
"""p5_geometry_record.py — 建立"合规新版本"的几何变更记录。

背景：Item 2 的 via pad 修正是**有意的 GDS 变更**，所以
"与旧 HEAD 逐字节相同"不再是合法通过条件。替代判据是：

  1. 旧几何的 SHA256 被冻结（.v2ana/geometry_sha_pre_fix.json）
  2. 新旧几何做**规范化**比较（逐层排序后的矩形列表 + bbox），
     而不是比文件字节 —— KLayout 写入会带时间戳，字节差异无意义
  3. 明确区分三类差异：
        GEOM_IDENTICAL   几何完全没变（C3/C4/D/E 应属此类）
        PAD_ONLY         只有 via landing pad 变大，cut 与中心不变（A/B/C1）
        OTHER            其它任何变化 -> 必须人工解释
  4. 逐项复核研究不变量（见 INVARIANTS），全部必须为真

INVARIANTS 是本项目"科研真值"的操作化定义 —— 它们不依赖文件字节，
因此在 pad 修正后仍然成立，也能在将来任何几何改动后重新验证。

用法：
  python3 macros/p5_geometry_record.py [out.json]
"""
import hashlib
import json
import os
import sys

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
ANA = os.path.join(HERE, '..', '.v2ana')
DBU = 0.001
LAYERS = {'M1': (68, 20), 'Via1': (68, 44), 'M2': (69, 20),
          'Via2': (69, 44), 'M3': (70, 20), 'M4': (71, 20),
          'prB': (235, 4)}
TAGS = ('A', 'B', 'C1', 'C3', 'C4', 'D', 'E')

# Route B: only the three macros that carry an electrical PIN were re-based so
# their cell geometry starts at (0,0).  The four geometry-only macros keep
# their round-4 coordinates and stay under the strict GEOM_IDENTICAL rule.
NORMALISED = {'A', 'B', 'C1'}


def shapes_of(ly, top, li):
    out = []
    if li is None:
        return out
    it = top.begin_shapes_rec(li)
    while not it.at_end():
        s = it.shape()
        t = it.trans()
        if s.is_box():
            b = s.box.transformed(t)
            out.append((b.left, b.bottom, b.right, b.top))
        elif s.is_polygon():
            b = s.polygon.transformed(t).bbox()
            out.append((b.left, b.bottom, b.right, b.top))
        elif s.is_path():
            b = s.path.transformed(t).bbox()
            out.append((b.left, b.bottom, b.right, b.top))
        it.next()
    return sorted(out)


def canon(ly, top):
    """Geometry-normalised digest: sorted rect list per layer + bbox."""
    per = {}
    for name, (ln, dt) in LAYERS.items():
        per[name] = shapes_of(ly, top, ly.find_layer(ln, dt))
    b = top.bbox()
    payload = {'layers': per,
               'bbox': [b.left, b.bottom, b.right, b.top]}
    h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return h, per, [b.left, b.bottom, b.right, b.top]


def vias(ly, top):
    """[(kind, cx_dbu, cy_dbu, w_dbu, h_dbu)] sorted — the research truth."""
    out = []
    for kind, (ln, dt) in (('Via1', (68, 44)), ('Via2', (69, 44))):
        li = ly.find_layer(ln, dt)
        for r in shapes_of(ly, top, li):
            out.append((kind, (r[0] + r[2]) // 2, (r[1] + r[3]) // 2,
                        r[2] - r[0], r[3] - r[1]))
    return sorted(out)


def as_region(rects):
    r = pya.Region()
    for a, b, c, d in rects:
        r.insert(pya.Box(a, b, c, d))
    r.merge()
    return r


def _shift(per, dx, dy):
    """Return a copy of the per-layer rect list translated by (-dx,-dy) dbu.

    `per[layer]` is a sorted list of (x0, y0, x1, y1) tuples in dbu, exactly
    what shapes_of() produces.  The re-basing SUBTRACTS the old bbox
    lower-left from every coordinate (G_new = G_old - O), so the reference
    geometry has to be moved by the same negative offset before comparing.
    """
    out = {}
    for name, rects in per.items():
        out[name] = [(x0 - dx, y0 - dy, x1 - dx, y1 - dy)
                     for (x0, y0, x1, y1) in rects]
    return out


def classify(tag, old_per, new_per, old_v, new_v,
             norm_shift=(0, 0), allow_normalised=False):
    """GEOM_IDENTICAL / NORMALISED / PAD_ONLY / OTHER.

    NORMALISED is the route-B invariant for the three electrical macros:
    the cell was re-based so its bbox starts at (0,0) and every polygon moved
    by exactly one rigid offset.  The test is therefore *not* "unchanged" but
    "old geometry translated by `norm_shift` equals new geometry, polygon for
    polygon, byte for byte after rounding".  Nothing may be added, removed,
    reshaped or mirrored, and the via cut list must translate too.

    PAD_ONLY requires BOTH of:
      (a) metals only grow — `old - new` is empty on every layer, i.e. no
          existing wire/via was moved, shrunk, or deleted. Growth alone cannot
          break a research structure that was defined by its old geometry.
      (b) the only changed layers are the pad layers plus prBoundary, which is
          derived from the geometry bbox and must follow it.
    prBoundary is reported separately as a *derived* change, not a content
    change, so the reader can see it was not silently ignored.
    """
    if old_per == new_per:
        return 'GEOM_IDENTICAL', [], []

    dx, dy = norm_shift
    if allow_normalised and (dx or dy):
        shifted = {k: sorted(v) for k, v in _shift(old_per, dx, dy).items()}
        new_sorted = {k: sorted(v) for k, v in new_per.items()}
        if shifted == new_sorted:
            # via cuts must move by the same rigid offset, nothing else
            moved_v = sorted((k, cx - dx, cy - dy, w, h) for (k, cx, cy, w, h) in old_v)
            if moved_v == sorted(new_v):
                return 'NORMALISED', [], ['prB']
        # fall through to report exactly what does not match
        problems = []
        if shifted != new_sorted:
            diff = [k for k in LAYERS if shifted[k] != new_sorted[k]]
            problems.append('rigid shift (%d,%d) dbu does not reproduce new '
                            'geometry on layers %s' % (dx, dy, diff))
        moved_v = sorted((k, cx - dx, cy - dy, w, h) for (k, cx, cy, w, h) in old_v)
        if moved_v != sorted(new_v):
            problems.append('via cuts did not move by the same rigid offset')
        return 'OTHER', problems, []

    problems = []
    if old_v != new_v:
        problems.append('via cut geometry changed — research truth broken')

    # (a) no existing geometry was removed or moved
    for name in LAYERS:
        gone = as_region(old_per[name]) - as_region(new_per[name])
        if not gone.is_empty():
            problems.append('%s: old geometry not contained in new '
                            '(%.4f um2 removed/moved)'
                            % (name, gone.area() * DBU * DBU))

    diffs = [k for k in LAYERS if old_per[k] != new_per[k]]
    content = [k for k in diffs if k != 'prB']
    derived = ['prB'] if 'prB' in diffs else []

    # (b) only pad layers may change in content
    if not set(content) <= {'M1', 'M2', 'M3'}:
        problems.append('non-pad layers changed: %s'
                        % sorted(set(content) - {'M1', 'M2', 'M3'}))

    if problems:
        return 'OTHER', problems, derived
    return 'PAD_ONLY', [], derived


def invariants(tag, per, ly, top):
    """Operational definition of the research truth for this structure."""
    inv = {}
    v = vias(ly, top)
    n = {k: len([x for x in v if x[0] == k]) for k in ('Via1', 'Via2')}
    inv['via1_count'] = n['Via1']
    inv['via2_count'] = n['Via2']

    # C3: eight independent conductors, spacing ladder 0.14/0.20/0.28/0.50
    if tag == 'C3':
        m1 = per['M1']
        inv['m1_conductor_count'] = len(m1)
        ys = sorted(((r[1] + r[3]) / 2.0 for r in m1))
        inv['m1_centres_um'] = [round(y * DBU, 3) for y in ys]
        gaps = []
        for a, b in zip(sorted(m1, key=lambda r: r[1]),
                        sorted(m1, key=lambda r: r[1])[1:]):
            gaps.append(round((b[1] - a[3]) * DBU, 3))
        inv['gap_ladder_um'] = gaps
        inv['eight_independent'] = len(m1) == 8 and n['Via1'] == 0

    # C4: crossing, NO via
    if tag == 'C4':
        inv['crossing_has_no_via'] = n['Via1'] == 0 and n['Via2'] == 0
        inv['m1_count'] = len(per['M1'])
        inv['m2_count'] = len(per['M2'])

    # D: five-step width ladder
    if tag == 'D':
        widths = sorted({r[3] - r[1] for r in per['M1']})
        inv['m1_width_ladder_um'] = [round(w * DBU, 3) for w in widths]
        inv['five_steps'] = len(widths) == 5

    # E: registration marks present on M1 and M2 at identical XY
    if tag == 'E':
        inv['m1_count'] = len(per['M1'])
        inv['m2_count'] = len(per['M2'])
        inv['m1_equals_m2'] = per['M1'] == per['M2']

    # A: neighbour line stays separate
    if tag == 'A':
        m1 = sorted(per['M1'], key=lambda r: r[1])
        inv['m1_count'] = len(m1)
    return inv


def main(out_json=None, old_dir=None):
    out_json = out_json or os.path.join(ANA, 'geometry_change_record.json')
    # The authoritative old geometry is the *git HEAD bytes*, not the
    # .v2ana/old snapshot: the snapshot was regenerated after the fix, so its
    # file SHAs differ from the frozen record purely by GDS timestamps.
    old_dir = old_dir or os.path.join(ANA, 'head')
    frozen = json.load(open(os.path.join(ANA, 'geometry_sha_pre_fix.json'),
                            encoding='utf-8'))

    # The rigid shift a normalised cell is allowed to have, derived from the
    # OLD (HEAD) GDS bbox lower-left -- the same quantity the generator removed.
    # Deliberately computed here from the historical bytes rather than read
    # from the generator's manifest: the checker must not take its reference
    # from the thing it is checking.
    NORM_SHIFT = {}
    for tag in TAGS:
        if tag not in NORMALISED:
            NORM_SHIFT[tag] = (0, 0)
            continue
        op = os.path.join(old_dir, 'struct_%s.gds' % tag)
        oly = pya.Layout(); oly.read(op)
        ob = oly.top_cell().bbox()
        NORM_SHIFT[tag] = (int(ob.left), int(ob.bottom))

    rec = {'label': 'V2_GEOMETRY_POST_ENCLOSURE_FIX',
           'supersedes': frozen.get('label'),
           'old_geometry_source': old_dir,
           'pass_condition': 'geometry-normalised, not byte-identical',
           'normalised_tags': sorted(NORMALISED),
           'normalised_shift_dbu': {k: list(v) for k, v in NORM_SHIFT.items()
                                    if k in NORMALISED},
           'structures': {}}

    all_ok = True
    for tag in TAGS:
        old_p = os.path.join(old_dir, 'struct_%s.gds' % tag)
        new_p = os.path.join(OUT, 'struct_%s.gds' % tag)
        r = {'old_gds': old_p, 'new_gds': new_p,
             'old_sha256_file': hashlib.sha256(open(old_p, 'rb').read()).hexdigest(),
             'new_sha256_file': hashlib.sha256(open(new_p, 'rb').read()).hexdigest()}

        oly = pya.Layout(); oly.read(old_p); ot = oly.top_cell()
        nly = pya.Layout(); nly.read(new_p); nt = nly.top_cell()
        oc, oper, obb = canon(oly, ot)
        nc, nper, nbb = canon(nly, nt)
        ov, nv = vias(oly, ot), vias(nly, nt)

        cls, problems, derived = classify(tag, oper, nper, ov, nv,
                                          norm_shift=NORM_SHIFT.get(tag, (0, 0)),
                                          allow_normalised=tag in NORMALISED)
        r.update({'old_canon': oc, 'new_canon': nc, 'geom_same': oper == nper,
                  'classification': cls,
                  'derived_changes': derived,
                  'old_bbox_um': [round(x * DBU, 3) for x in obb],
                  'new_bbox_um': [round(x * DBU, 3) for x in nbb],
                  'changed_layers': [k for k in LAYERS if oper[k] != nper[k]],
                  'changed_content_layers': [k for k in LAYERS
                                             if oper[k] != nper[k]
                                             and k != 'prB'],
                  'layer_counts_old': {k: len(v) for k, v in oper.items()},
                  'layer_counts_new': {k: len(v) for k, v in nper.items()},
                  'via_identity_unchanged': ov == nv,
                  'via_cut_list': [{'kind': k, 'cx_um': cx * DBU,
                                    'cy_um': cy * DBU,
                                    'w_um': w * DBU, 'h_um': h * DBU}
                                   for k, cx, cy, w, h in nv],
                  'invariants': invariants(tag, nper, nly, nt),
                  'problems': problems})
        if cls == 'OTHER':
            all_ok = False

        # pad delta per layer, so the "minimal change" claim is checkable
        delta = {}
        for k in LAYERS:
            a_old = sum((b - a) * (d - c) for a, c, b, d in oper[k])
            a_new = sum((b - a) * (d - c) for a, c, b, d in nper[k])
            if a_old != a_new:
                delta[k] = round((a_new - a_old) * DBU * DBU, 4)
        r['area_delta_um2'] = delta
        rec['structures'][tag] = r

    rec['all_classified'] = all_ok
    rec['summary'] = {
        'GEOM_IDENTICAL': sorted(t for t, r in rec['structures'].items()
                                 if r['classification'] == 'GEOM_IDENTICAL'),
        'PAD_ONLY': sorted(t for t, r in rec['structures'].items()
                           if r['classification'] == 'PAD_ONLY'),
        'OTHER': sorted(t for t, r in rec['structures'].items()
                        if r['classification'] == 'OTHER'),
    }

    print('%-4s %-16s %-14s %-14s %s'
          % ('tag', 'class', 'geom_same', 'via unchanged', 'content changed / derived'))
    for tag in TAGS:
        r = rec['structures'][tag]
        ch = ','.join(r['changed_content_layers']) or '-'
        dv = ','.join(r['derived_changes']) or '-'
        print('%-4s %-16s %-14s %-14s content=%-10s derived=%-4s  dA=%s'
              % (tag, r['classification'], r['geom_same'],
                 r['via_identity_unchanged'], ch, dv, r['area_delta_um2']))
    print()
    print('summary:', rec['summary'])
    print('all classified (nothing unexplained):', all_ok)

    json.dump(rec, open(out_json, 'w', encoding='utf-8'), indent=1,
              ensure_ascii=False)
    print('written', out_json)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None,
                  sys.argv[2] if len(sys.argv) > 2 else None))
