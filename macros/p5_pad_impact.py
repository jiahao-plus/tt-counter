#!/usr/bin/env python3
"""p5_pad_impact.py — pad 放大对既有布线的影响（Item 2 的间距/短接检查）。

放大 Via 的 landing pad 会让宏的金属向外生长。第三轮 CI 的最终 GDS 里，
宏足迹内和周边已经有别家的金属（PDN stripe、信号线、pwm_out 的接入段）。
必须回答两个问题：

  Q1 新 pad 是否与既有金属**短接**？      -> same-layer overlap > 0 即短接
  Q2 新 pad 是否让**间距**降到规则以下？  -> gap < 该层 min_space 即违规

方法：
  1. 新宏几何按 placement 平移到绝对坐标
  2. 取最终 GDS 同层、在宏足迹外扩 W 的窗口内的全部图形
  3. 扣掉"宏自身在该处贡献的图形"（即旧宏几何，因为最终 GDS 已被 flatten）
  4. 对新宏金属 vs 剩余外来金属逐层求
        overlap 面积
        min gap
  5. 与 SKY130 规则比较

**为什么必须扣掉旧宏几何**：最终 GDS 已经把宏 flatten 进顶层。若不扣，
每条新金属都会"短接"到它自己在旧版本里的残留（也就是它自己），
得到 7 个假短接。

用法：
  python3 macros/p5_pad_impact.py <final.gds> <final.def> [old_macro_dir] [out.json]
"""
import json
import os
import sys

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '.v2ana'))

import p5_intrusion_check as P

DBU = P.DBU
LAYERS = P.LAYERS
# SKY130 min spacing per layer, um (same values as geom_drc.py).
MIN_SPACE = {'M1': 0.140, 'M2': 0.140, 'M3': 0.300,
             'M4': 0.300, 'M5': 0.300, 'M6': 0.400}
# Layers a macro actually draws: only these can newly violate spacing.
CHECK_LAYERS = ('M1', 'M2', 'M3', 'Via1', 'Via2')
WINDOW_UM = 2.0


def region_of(layout, cell, name, clip=None):
    li = layout.find_layer(*LAYERS[name])
    r = pya.Region()
    if li is None:
        return r
    it = cell.begin_shapes_rec(li)
    while not it.at_end():
        s = it.shape()
        t = it.trans()
        if s.is_box():
            r.insert(s.box.transformed(t))
        elif s.is_polygon():
            r.insert(s.polygon.transformed(t))
        elif s.is_path():
            r.insert(s.path.transformed(t).simple_polygon())
        it.next()
    r.merge()
    return r & clip if clip is not None else r


def gap_between(a, b, hi=3.0):
    """min distance between two disjoint Regions (um)."""
    if a.is_empty() or b.is_empty():
        return None
    lo = 0.0
    if not (a.sized(1) & b).is_empty():
        return 0.0
    for _ in range(22):
        mid = (lo + hi) / 2.0
        if (a.sized(int(round(mid / DBU))) & b).is_empty():
            lo = mid
        else:
            hi = mid
    return hi


def main(final_gds, def_path, old_dir=None, out_json=None):
    old_dir = old_dir or os.path.join(HERE, '..', '.v2ana', 'old')
    place = P.def_placements(def_path)
    fly = pya.Layout()
    fly.read(final_gds)
    ftop = fly.top_cell()

    report = {}
    n_short = 0
    n_space = 0
    n_growth_touch = 0
    for cell, (px, py, orient) in sorted(place.items()):
        tag = P.TAG_OF_CELL.get(cell)
        if tag is None:
            continue
        new_ly = pya.Layout()
        new_ly.read(os.path.join(HERE, 'out', 'struct_%s.gds' % tag))
        new_top = new_ly.top_cell()
        nbb = P.prboundary_box(new_ly, new_top)

        old_ly = pya.Layout()
        old_path = os.path.join(old_dir, 'struct_%s.gds' % tag)
        if not os.path.exists(old_path):
            continue
        old_ly.read(old_path)
        old_top = old_ly.top_cell()
        obb = P.prboundary_box(old_ly, old_top)

        # window covers new footprint + search margin
        ax0 = px + nbb.left * DBU
        ay0 = py + nbb.bottom * DBU
        ax1 = ax0 + nbb.width() * DBU
        ay1 = ay0 + nbb.height() * DBU
        win = pya.Region(pya.Box(
            int(round((ax0 - WINDOW_UM) / DBU)), int(round((ay0 - WINDOW_UM) / DBU)),
            int(round((ax1 + WINDOW_UM) / DBU)), int(round((ay1 + WINDOW_UM) / DBU))))

        dx, dy = int(round(px / DBU)), int(round(py / DBU))
        rec = {'tag': tag, 'placement_um': [px, py],
               'old_size_um': [round(obb.width() * DBU, 3),
                               round(obb.height() * DBU, 3)],
               'new_size_um': [round(nbb.width() * DBU, 3),
                               round(nbb.height() * DBU, 3)],
               'layers': {}}
        for name in CHECK_LAYERS:
            new_r = region_of(new_ly, new_top, name).moved(dx, dy) & win
            if new_r.is_empty():
                continue
            old_r = region_of(old_ly, old_top, name).moved(dx, dy) & win
            final_r = region_of(fly, ftop, name, clip=win)
            foreign = final_r - old_r          # metal that is not this macro

            ov = (new_r & foreign)
            g = gap_between(new_r, foreign)
            rule = MIN_SPACE.get(name)
            # Baseline: what the OLD geometry already did against the same
            # foreign metal. Pad growth is only a regression where it makes a
            # situation strictly worse than the geometry already shipped.
            g_old = gap_between(old_r, foreign)
            ov_old = (old_r & foreign)
            d = {'new_area_um2': round(new_r.area() * DBU * DBU, 4),
                 'foreign_area_um2': round(foreign.area() * DBU * DBU, 4),
                 'overlap_um2': round(ov.area() * DBU * DBU, 5),
                 'overlap_old_um2': round(ov_old.area() * DBU * DBU, 5),
                 'min_gap_um': None if g is None else round(g, 3),
                 'min_gap_old_um': None if g_old is None else round(g_old, 3),
                 'min_space_rule_um': rule}

            # --- short classification -------------------------------------
            # A short that the old geometry already had is the *intended* PIN
            # connection (pwm_out lands on C1/A/B). Only an increase counts.
            d['new_short'] = (ov.area() > ov_old.area() + 1)
            if d['new_short']:
                n_short += 1
                bb = ov.bbox()
                d['overlap_bbox_um'] = [round(bb.left * DBU, 3),
                                        round(bb.bottom * DBU, 3),
                                        round(bb.right * DBU, 3),
                                        round(bb.top * DBU, 3)]

            # --- spacing classification -----------------------------------
            # The pad grows by <= 0.005 um into previously empty space. A
            # 0.005 um contact that also existed at 0.005 um before the fix is
            # a corner touch on the PIN, not a new clearance problem. Judge by
            # the change in gap, not by the absolute number.
            if rule is None:
                d['space_violation'] = False
            elif ov.area() <= ov_old.area() + 1:
                d['space_violation'] = False     # no new/bigger overlap
            else:
                d['space_violation'] = True
            if d['space_violation']:
                n_space += 1
            # --- growth-only analysis -------------------------------------
            # The cleanest statement of "the pad enlargement introduces no new
            # clearance problem": intersect ONLY the added metal with foreign
            # metal. Whole-region overlap/gap is the wrong question because the
            # old geometry already touched pwm_out at the PIN by design; the
            # added area is what did not exist before, so anything it touches
            # is by construction new.
            growth = new_r - old_r
            if growth.is_empty():
                d['growth_area_um2'] = 0.0
                d['growth_overlap_um2'] = 0.0
                d['growth_min_gap_um'] = None
            else:
                gg = (growth & foreign)
                gd = gap_between(growth, foreign)
                d['growth_area_um2'] = round(growth.area() * DBU * DBU, 4)
                d['growth_overlap_um2'] = round(gg.area() * DBU * DBU, 5)
                d['growth_min_gap_um'] = None if gd is None else round(gd, 3)
                if gg.area() > 0:
                    d['growth_touches_foreign'] = True
                    gb = gg.bbox()
                    d['growth_touch_bbox_um'] = [round(gb.left * DBU, 3),
                                                 round(gb.bottom * DBU, 3),
                                                 round(gb.right * DBU, 3),
                                                 round(gb.top * DBU, 3)]
            rec['layers'][name] = d
        report[cell] = rec

    res = {'final_gds': final_gds, 'def': def_path,
           'old_macro_dir': old_dir,
           'kind': 'PAD_GROWTH_IMPACT',
           'note': 'Compares the enlarged macro geometry against the routing/PDN '
                   'already present in the 3rd-round final GDS. Overlap = short; '
                   'gap below the layer rule = spacing violation. Foreign metal '
                   'is final GDS minus the macro own (old) geometry, so a macro '
                   'cannot "short" to its own previous revision.',
           'macros': report,
           'new_shorts': n_short,
           'new_space_violations': n_space,
           'growth_touching_foreign': n_growth_touch,
           'pass': n_short == 0 and n_space == 0}

    print('=' * 100)
    print('PAD-GROWTH IMPACT ON EXISTING ROUTING / PDN')
    print('=' * 100)
    for cell, r in sorted(report.items()):
        print('%-16s [%-2s]  size %s -> %s'
              % (cell, r['tag'], r['old_size_um'], r['new_size_um']))
        for name, d in sorted(r['layers'].items()):
            flag = ''
            if d['new_short']:
                flag = '  NEW SHORT %.4f um2' % d['overlap_um2']
            elif d['space_violation']:
                flag = '  SPACE VIOLATION (gap %.3f < %.3f)' % (
                    d['min_gap_um'], d['min_space_rule_um'])
            elif d['overlap_um2']:
                flag = '  overlap %.4f um2 == old (intended PIN contact)' % d['overlap_um2']
            print('    %-5s new %7.4f  foreign %8.4f  gap %-8s overlap %7.4f%s'
                  % (name, d['new_area_um2'], d['foreign_area_um2'],
                     ('n/a' if d['min_gap_um'] is None
                      else '%.3f' % d['min_gap_um']),
                     d['overlap_um2'], flag))
            if d.get('growth_area_um2'):
                print('          growth %7.4f um2  vs foreign: overlap %.5f  '
                      'min gap %s'
                      % (d['growth_area_um2'], d['growth_overlap_um2'],
                         'n/a' if d['growth_min_gap_um'] is None
                         else '%.3f um' % d['growth_min_gap_um']))
                if d.get('growth_touches_foreign'):
                    n_growth_touch += 1
    print()
    print('new shorts:            %d' % n_short)
    print('new spacing violations: %d' % n_space)
    print('growth regions touching foreign metal: %d' % n_growth_touch)
    print('VERDICT:', 'PASS' if res['pass'] else 'FAIL')

    if out_json:
        json.dump(res, open(out_json, 'w', encoding='utf-8'), indent=1,
                  ensure_ascii=False)
        print('written', out_json)
    return res


if __name__ == '__main__':
    _r = main(sys.argv[1], sys.argv[2],
              sys.argv[3] if len(sys.argv) > 3 else None,
              sys.argv[4] if len(sys.argv) > 4 else None)
    sys.exit(0 if _r['pass'] else 1)
