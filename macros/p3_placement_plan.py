#!/usr/bin/env python3
"""p3_placement_plan.py — P3-B 宏放置规划（v3：5 µm 最小间距 + 全 N 朝向）。

变更历史：
  v1  只看"在 core 内 + 不重叠"  -> research_fiducial 有 40% 宽度在假定 strap 下
  v2  改为避开 strap 空档        -> 但把最小间距从 5 µm 静默降到 3 µm，且 D 旋转 90°
  v3  （本版，按用户决定）
      * 最小间距恢复为 **5.00 µm**，并写入自动断言
      * 全部宏 **orientation N**（D 不再旋转；LEF SIZE 与实例占用一致）
      * 接受 D 可能的假定 PDN 遮挡，但标注为 UNKNOWN 而非实测

约束（全部自动验证）：
  C1  所有宏在规划 Core 内
  C2  两两不重叠
  C3  任意两宏最小边到边间距 >= 5.00 µm
  C4  朝向全部为 N
  C5  strap 穿越数尽量为 0（基于外推 PDN，非实测）

输出：
  v2_validation/P3_MACRO_BBOX.csv
  v2_validation/p3_placement.json
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IDX = os.path.join(ROOT, 'macros', 'out', 'macro_index.json')

DIE_W, DIE_H = 335.0, 226.0
MARGIN_L, MARGIN_B, MARGIN_R, MARGIN_T = 2.76, 2.72, 2.76, 5.44

MIN_GAP_UM = 5.00          # hard requirement, asserted below (was 3.00 in v2)

V1_STRAP_X = [19.08, 22.38, 57.95, 61.25, 96.82, 100.12, 135.69, 138.99]
V1_STRAP_W = 1.600
V1_PITCH = 27.14

# ---- placement ------------------------------------------------------------
# All N. Rows are stacked in y; each row keeps >= 5 um between neighbours.
#
# Free x gaps between assumed straps:
#   23.20..57.20 (34.00)   62.00..96.00 (34.00)   100.90..134.90 (34.00)
#   139.80..165.30 (25.50) 166.90..192.50 (25.60) 194.10..219.60 (25.50) ...
#
# research_dense is 35.00 um wide, which does NOT fit any 34 um gap. It is
# therefore placed at N and allowed to cross one assumed strap; the resulting
# PDN opacity is UNKNOWN (the strap positions themselves are extrapolated).
PLAN = [
    # (tag, instance, x_um, y_um, orientation, note)
    # x_um / y_um below are the DESIGN-INTENT position of the macro's lower-left
    # corner on the die.  It is the same number for every structure regardless
    # of how its cell happens to be drawn, because the plan is about where the
    # silicon goes, not about the internal coordinate frame of the cell.
    ('E',  'u_rs_fiducial',  24.00, 208.00, 'N', 'gap 23.20-57.20'),
    ('A',  'u_rs_via1',      33.50, 208.00, 'N', 'gap 23.20-57.20, 5.5 um from E'),
    # B and C1 share the next gap, 5.1 um apart in x
    ('B',  'u_rs_via2',      64.00, 208.00, 'N', 'gap 62.00-96.00'),
    ('C1', 'u_rs_branch',    79.32, 208.00, 'N', 'gap 62.00-96.00, 5.1 um from B'),
    # C3 below B/C1, at least 5.2 um of clear y
    ('C3', 'u_rs_near',      64.00, 191.57, 'N', 'gap 62.00-96.00, below B'),
    # C4 in the next gap
    ('C4', 'u_rs_cross',    102.00, 188.00, 'N', 'gap 100.90-134.90'),
    # D at N, 35 um wide, crosses one assumed strap; opacity UNKNOWN
    ('D',  'u_rs_dense',     23.50, 150.00, 'N', '35 um, crosses ~1 assumed strap'),
]


def straps_for(die_w):
    xs = list(V1_STRAP_X)
    x = V1_STRAP_X[-1] + V1_PITCH
    while x < die_w:
        xs.append(round(x, 3))
        x += V1_PITCH
    return xs


def main():
    idx = json.load(open(IDX, encoding='utf-8'))
    straps = straps_for(DIE_W)
    core_x0, core_y0 = MARGIN_L, MARGIN_B
    core_x1, core_y1 = DIE_W - MARGIN_R, DIE_H - MARGIN_T

    rows, problems = [], []
    for tag, inst, x, y, orient, note in PLAN:
        m = idx[tag]
        w, h = m['size_um']
        if orient in ('E', 'W'):
            w, h = h, w
        # Route B: the three electrical macros had their cell geometry shifted
        # so its bbox starts at (0,0), and their LEF ORIGIN is now zero.  The
        # offset that was removed from the cell has to come back into the
        # instance placement, otherwise the macro lands `local_origin` too far
        # down-left on the die.  The four geometry-only macros were not
        # touched, so their local_origin is (0,0) and this is a no-op for them.
        #
        # `x, y` stays the design-intent lower-left on the die; the emitted
        # placement is that value plus whatever the cell's own frame needs.
        lo = m.get('local_origin_um', [0.0, 0.0])
        place_x, place_y = round(x + lo[0], 3), round(y + lo[1], 3)
        # The footprint on the die starts at the PLACEMENT, not at the
        # design-intent coordinate -- they differ by exactly `lo` for a
        # normalised macro.  Everything below (gaps, core containment, straps)
        # must use the real footprint or a normalised macro would be checked
        # against a box shifted by -lo and a real overlap could be missed.
        x1, y1 = place_x + w, place_y + h
        inside = (x >= core_x0 and y >= core_y0
                  and x1 <= core_x1 and y1 <= core_y1)
        if not inside:
            problems.append('C1 FAIL: %s outside core (%.2f,%.2f)-(%.2f,%.2f)'
                            % (tag, x, y, x1, y1))
        if orient != 'N':
            problems.append('C4 FAIL: %s orientation %s != N' % (tag, orient))

        hits, covered = [], 0.0
        for sx in straps:
            s0, s1 = sx - V1_STRAP_W / 2, sx + V1_STRAP_W / 2
            if s1 <= x or s0 >= x1:
                continue
            ov = min(x1, s1) - max(x, s0)
            if ov > 0:
                hits.append(round(sx, 2)); covered += ov

        rows.append({
            'structure_id': tag, 'macro_name': m['cell'], 'instance': inst,
            # design-intent lower-left on the die
            'x_um': x, 'y_um': y,
            # what actually goes into the DEF/config placement
            'place_x_um': place_x, 'place_y_um': place_y,
            'local_origin_um': list(lo),
            'w_um': w, 'h_um': h,
            'x1_um': round(x1, 3), 'y1_um': round(y1, 3),
            'orientation': orient,
            'electrical': m['electrical'],
            'n_pins': len(m['pins']),
            'inside_core': inside,
            'strap_crossings': len(hits),
            'strap_x_hit': hits,
            'strap_width_fraction_ESTIMATE': round(covered / w, 4) if w else 0.0,
            'note': note,
        })

    # ---- C2 overlap
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            ox = min(a['x1_um'], b['x1_um']) - max(a['place_x_um'], b['place_x_um'])
            oy = min(a['y1_um'], b['y1_um']) - max(a['place_y_um'], b['place_y_um'])
            if ox > 0 and oy > 0:
                problems.append('C2 FAIL: overlap %s/%s %.2fx%.2f um'
                                % (a['structure_id'], b['structure_id'], ox, oy))

    # ---- C3 min gap (the requirement the user restored to 5 um)
    # Use the REAL footprint (place_*) throughout.  x_um/y_um is the
    # design-intent coordinate and differs from the placement by `local_origin`
    # for a normalised macro, so mixing the two would measure a gap against a
    # box that is not where the metal actually is.
    gaps = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            ax0, ay0 = a['place_x_um'], a['place_y_um']
            bx0, by0 = b['place_x_um'], b['place_y_um']
            dx = max(ax0 - b['x1_um'], bx0 - a['x1_um'], 0.0)
            dy = max(ay0 - b['y1_um'], by0 - a['y1_um'], 0.0)
            gaps.append(((dx * dx + dy * dy) ** 0.5,
                         a['structure_id'], b['structure_id'], dx, dy))
    gaps.sort()
    for g in gaps:
        if g[0] < MIN_GAP_UM - 1e-6:
            problems.append('C3 FAIL: gap %.3f um < %.2f between %s and %s '
                            '(dx=%.2f dy=%.2f)'
                            % (g[0], MIN_GAP_UM, g[1], g[2], g[3], g[4]))

    # ---- write
    csv_p = os.path.join(ROOT, 'v2_validation', 'P3_MACRO_BBOX.csv')
    os.makedirs(os.path.dirname(csv_p), exist_ok=True)
    cols = ['structure_id', 'macro_name', 'instance', 'x_um', 'y_um',
            'place_x_um', 'place_y_um', 'local_origin_x_um', 'local_origin_y_um',
            'w_um', 'h_um', 'x1_um', 'y1_um', 'orientation', 'electrical',
            'n_pins', 'inside_core', 'strap_crossings', 'strap_x_hit',
            'strap_width_fraction_ESTIMATE', 'note']
    with open(csv_p, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            r2 = dict(r)
            r2['strap_x_hit'] = ';'.join(str(v) for v in r['strap_x_hit'])
            lo = r2.pop('local_origin_um', [0.0, 0.0])
            r2['local_origin_x_um'], r2['local_origin_y_um'] = lo[0], lo[1]
            w.writerow(r2)

    out = {
        'status': 'PLAN_ONLY',
        'version': 3,
        'caveat': '2x2 PDN and core are UNKNOWN. Strap positions are the V1 '
                  'measured pattern tiled by its 27.14 um pitch; the core rect '
                  'is extrapolated from V1 margins. Every check here is a '
                  'PLANNING-stage check, not a verified physical result.',
        'min_gap_required_um': MIN_GAP_UM,
        'die_um': [DIE_W, DIE_H],
        'margins_um': [MARGIN_L, MARGIN_B, MARGIN_R, MARGIN_T],
        'core_rect_um': [core_x0, core_y0, round(core_x1, 3), round(core_y1, 3)],
        'core_area_um2': round((core_x1 - core_x0) * (core_y1 - core_y0), 1),
        'assumed_strap_x_um': straps,
        'placements': rows,
        'all_gaps_um': [[round(g[0], 3), g[1], g[2]] for g in gaps],
        'min_gap_um': round(gaps[0][0], 3) if gaps else 0.0,
        'min_gap_pair': [gaps[0][1], gaps[0][2]] if gaps else ['-', '-'],
        'problems': problems,
        'ok': len(problems) == 0,
    }
    json.dump(out, open(os.path.join(ROOT, 'v2_validation', 'p3_placement.json'),
                        'w', encoding='utf-8'), indent=1, ensure_ascii=False)

    print('core (PLANNED): (%.2f,%.2f)-(%.2f,%.2f) = %.0f um2'
          % (core_x0, core_y0, core_x1, core_y1, out['core_area_um2']))
    print('min gap requirement: %.2f um (asserted)' % MIN_GAP_UM)
    print()
    print('%-3s %-20s %8s %8s %8s %8s %6s %6s'
          % ('tag', 'macro', 'x', 'y', 'w', 'h', 'o', 'strap'))
    for r in rows:
        print('%-3s %-20s %8.2f %8.2f %8.2f %8.2f %6s %6d'
              % (r['structure_id'], r['macro_name'], r['x_um'], r['y_um'],
                 r['w_um'], r['h_um'], r['orientation'], r['strap_crossings']))
    print()
    print('all %d pairwise gaps (closest first):' % len(gaps))
    for g in gaps[:6]:
        print('   %.2f um  %s-%s' % (g[0], g[1], g[2]))
    print()
    if problems:
        print('PROBLEMS (%d):' % len(problems))
        for p in problems:
            print('  !', p)
    else:
        print('ALL CONSTRAINTS PASS: inside core, no overlap, '
              'min gap >= %.2f um, all N' % MIN_GAP_UM)
    print('written', csv_p)
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
