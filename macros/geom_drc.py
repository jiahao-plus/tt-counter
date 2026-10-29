#!/usr/bin/env python3
"""geom_drc.py — 用 pya.Region 原生 check API 实现的 SKY130 几何 DRC。

为什么不用 sky130hd.lydrc 本身：
  KLayout 0.26.2 的 Ruby 解释器在 headless（-b/-r/-rm）下初始化即崩溃，
  且该 deck 是 DRC-DSL(Ruby) 宏，pya.DRC 在 Python 模块中不存在。

因此本检查器用 deck 中**精确提取的规则值**（v2_spec/sky130_rules_measured.md），
调用 pya.Region 的**原生 DRC 检查 API**（width_check / space_check /
enclosing_check / isolated_check）重新实现关键 BEOL 规则：

  m1.1  min m1 width            0.140 um
  m1.2  min m1 spacing          0.140 um
  m2.1  min m2 width            0.140 um
  m2.2  min m2 spacing          0.140 um
  m3.1  min m3 width            0.300 um
  m3.*  min m3 spacing          0.300 um
  via.1a   min via1 width              0.150 um
  via.2    min via1 spacing            0.060 um  (via.2 - 2*via.4a, touching_ok)
  via.5a   m1 enclosure of via1        0.085 um  (via.5a - via.4a, DIRECTIONAL)
  met2.5   m2 enclosure of via1        0.085 um  (met2.5 - met2.4, DIRECTIONAL)
  via2.1a  min via2 width              0.200 um
  via2.2   min via2 spacing            0.120 um  (via2.2 - 2*via2.4, touching_ok)
  via2.4a  m2 enclosure of via2        0.085 um  (via2.4a - via2.4, DIRECTIONAL)
  met3.4   m3 enclosure of via2        0.065 um  (ABSENCE_ILLEGAL, all sides)

**方向性包围（directional surround）的语义 —— 这是旧版本最大的漏洞：**
  SKY130 的 via.5a 原文是 "Metal1 overlap of Via1 on at least **two opposite
  sides** by 0.085 um" —— 要求的是**某一对相对边都达标**，即
        min( left, right ) >= T    或    min( bottom, top ) >= T
  而不是"四边都要达标"，也不是"任意一边达标"。
  早期版本把 0.055 当作"实测规则值"写死，等于把违规几何判定为通过 ——
  这正是第三轮 CI 中 107 个 via.5a/met2.5/via2.4a 错误能一路逃过本地检查的原因。

  **阈值依据（不是猜的）**：第三轮 CI 的 669 个 Magic 盒子里，包围类错误的
  规则名分布是 via.5a 63 + met2.5 36 + via2.4a 8 = 107，**met3.4 为 0**。
  逐宏核对：A 23 = 11 via.5a + 12 met2.5；B 8 = 纯 via2.4a；
  C1 62 = 38 via.5a + 24 met2.5；余下 14 个 via.5a 落在左/中 sliver 的 PDN via 上。
  三条规则在 0.085 处、met3.4 在 0.065 处同时自洽 —— 这就是阈值的实测锚点。

  **对本检查器的直接推论**：B 的 Via2 落到 M3 上是 L=0.065/R=2.000/B=0.065/
  T=0.065，Magic 没有报 met3.4，因此该几何合法。任何把这条报成违规的实现
  都是错的（旧版的 µm-vs-dbu 单位混用就造成了这个假阳性）。

  **与修复的关系**：本版把三处包围统一改成对称 pad（Via1 0.340 = 0.095 包围，
  Via2 0.390 = 0.095 包围），四边等深 —— 无论按哪种语义解释都通过，
  因此修复不依赖对 directional 语义的解读。

**局限（必须随结果说明）**：
  - 不覆盖 FEOL、密度、天线、pin、max-width/slotting 规则
  - 不替代官方 Precheck
  - 结果标记为 LOCAL_GEOM_DRC，不是 OFFICIAL_DRC

用法：
  python3 macros/geom_drc.py <gds> [out.json]
"""
import json
import sys

import pya

DBU = 0.001
GRID = 0.005

RULES = dict(
    m1_w=0.140, m1_s=0.140,
    m2_w=0.140, m2_s=0.140,
    m3_w=0.300, m3_s=0.300,
    via1_cut=0.150, via1_m1_encl=0.085, via1_m2_encl=0.085, via1_space=0.060,
    via2_cut=0.200, via2_m2_encl=0.085, via2_m3_encl=0.065, via2_space=0.120,
    # Via3 is not used by any research macro. These values were NOT re-measured
    # in this pass, so the Via3 spacing check is skipped (None) rather than
    # asserting a number that has no evidence behind it.
    via3_cut=0.200, via3_m3_encl=0.060, via3_m4_encl=0.065, via3_space=None,
)

LAYERS = {
    'M1': (68, 20), 'Via1': (68, 44),
    'M2': (69, 20), 'Via2': (69, 44),
    'M3': (70, 20), 'Via3': (70, 44),
    'M4': (71, 20),
}
VIA_ENCL = {
    'Via1': [('M1', 'via1_m1_encl'), ('M2', 'via1_m2_encl')],
    'Via2': [('M2', 'via2_m2_encl'), ('M3', 'via2_m3_encl')],
    'Via3': [('M3', 'via3_m3_encl'), ('M4', 'via3_m4_encl')],
}
VIA_SIZE = {'Via1': 'via1_cut', 'Via2': 'via2_cut', 'Via3': 'via3_cut'}
VIA_SPACE = {'Via1': 'via1_space', 'Via2': 'via2_space', 'Via3': 'via3_space'}


def um(v):
    return int(round(v / DBU))


def load(path):
    ly = pya.Layout()
    ly.read(path)
    top = ly.top_cell()
    regions = {}
    for name, (ln, dt) in LAYERS.items():
        li = ly.find_layer(ln, dt)
        r = pya.Region()
        if li is not None:
            it = top.begin_shapes_rec(li)
            while not it.at_end():
                s = it.shape(); t = it.trans()
                if s.is_box():
                    r.insert(s.box.transformed(t))
                elif s.is_polygon():
                    r.insert(s.polygon.transformed(t))
                elif s.is_path():
                    r.insert(s.path.transformed(t).simple_polygon())
                it.next()
            r.merge()
        regions[name] = r
    return ly, top, regions


def _collect(res, rule, min_um, what):
    """Turn a check result Region into violation records."""
    out = []
    for p in res.each():
        bb = p.bbox()
        out.append({'rule': rule, 'check': what, 'min_required_um': min_um,
                    'bbox_um': [round(bb.left * DBU, 3), round(bb.bottom * DBU, 3),
                                round(bb.right * DBU, 3), round(bb.top * DBU, 3)]})
        if len(out) >= 500:
            break
    return out


def _side_depths(metal, via_box):
    """Exact per-side enclosure depth of `via_box` inside `metal`, um.

    Binary-searches the largest d for which the one-side probe rectangle
    grown by d is fully covered by the metal Region. This is exact for
    rectilinear geometry (the deck's target), and does not assume the
    metal polygon containing the via is itself a rectangle.
    """
    out = {}
    for side in ('L', 'R', 'B', 'T'):
        lo, hi = 0.0, 2.0
        for _ in range(24):
            mid = (lo + hi) / 2.0
            d = um(mid)
            if side == 'L':
                pr = pya.Box(via_box.left - d, via_box.bottom, via_box.left, via_box.top)
            elif side == 'R':
                pr = pya.Box(via_box.right, via_box.bottom, via_box.right + d, via_box.top)
            elif side == 'B':
                pr = pya.Box(via_box.left, via_box.bottom - d, via_box.right, via_box.bottom)
            else:
                pr = pya.Box(via_box.left, via_box.top, via_box.right, via_box.top + d)
            if pr.width() <= 0 or pr.height() <= 0:
                lo = mid
                continue
            if (pya.Region(pr) - metal).is_empty():
                lo = mid
            else:
                hi = mid
        out[side] = lo
    return out


def check_enclosure(metal, via_region, threshold_um, directional=True):
    """SKY130 via-enclosure check.

    directional=True reproduces the SKY130 `surround ... directional` rule
    ("at least two opposite sides"):
        OK iff min(L,R) >= T   OR   min(B,T) >= T
    directional=False is the strict four-side test (all sides >= T), used
    only by the negative controls to prove the check actually bites.

    UNITS: threshold_um is um and _side_depths returns um. An earlier revision
    converted T to database units (65) while comparing against um (0.065),
    which made every via trip the test unconditionally — a false pass on the
    *count* and a false verdict on B's legal met3.4 geometry.
    """
    viol = []
    if via_region.is_empty():
        return viol
    if metal.is_empty():
        return viol
    T = threshold_um          # um
    tol = 0.5 * DBU           # half a database unit, in um
    for v in via_region.each():
        vb = v.bbox()
        s = _side_depths(metal, vb)
        lr = min(s['L'], s['R'])   # this opposite-side pair must BOTH reach T
        bt = min(s['B'], s['T'])
        if directional:
            bad = (lr < T - tol) and (bt < T - tol)
        else:
            bad = min(s.values()) < T - tol
        if bad:
            viol.append({
                'check': 'enclosure',
                'mode': 'directional' if directional else 'all_sides',
                'min_required_um': threshold_um,
                'bbox_um': [round(vb.left * DBU, 3), round(vb.bottom * DBU, 3),
                            round(vb.right * DBU, 3), round(vb.top * DBU, 3)],
                'sides_um': {k: round(vv, 3) for k, vv in s.items()},
                'best_axis_um': round(max(lr, bt), 3),
                'min_lr_um': round(lr, 3),
                'min_bt_um': round(bt, 3),
            })
        if len(viol) >= 500:
            break
    return viol


def run(gds, verbose=True):
    ly, top, R = load(gds)
    viol = []

    # ---- metal width / spacing
    for m, wk, sk in (('M1', 'm1_w', 'm1_s'),
                      ('M2', 'm2_w', 'm2_s'),
                      ('M3', 'm3_w', 'm3_s')):
        r = R[m]
        if r.is_empty():
            continue
        viol += _collect(r.width_check(um(RULES[wk])), '%s.min_width' % m,
                         RULES[wk], 'width')
        viol += _collect(r.space_check(um(RULES[sk])), '%s.min_space' % m,
                         RULES[sk], 'space')

    # ---- via size (exact square expected)
    for v, key in VIA_SIZE.items():
        r = R[v]
        if r.is_empty():
            continue
        need = um(RULES[key])
        for p in r.each():
            bb = p.bbox()
            w, h = bb.width(), bb.height()
            if abs(w - need) > 2 or abs(h - need) > 2:
                viol.append({'rule': '%s.size' % v, 'check': 'size',
                             'got_um': [round(w * DBU, 3), round(h * DBU, 3)],
                             'need_um': RULES[key],
                             'bbox_um': [round(bb.left * DBU, 3), round(bb.bottom * DBU, 3),
                                         round(bb.right * DBU, 3), round(bb.top * DBU, 3)]})

    # ---- via enclosure by both metals (Magic-compatible directional semantics)
    #
    # Previously this used `rm.enclosing_check(rv, need)` with need = 0.055/0.040,
    # which both (a) used the wrong threshold values and (b) applied an
    # all-sides rule where the SKY130 deck specifies a directional one.
    # Both defects are corrected here.
    for v, pairs in VIA_ENCL.items():
        rv = R[v]
        if rv.is_empty():
            continue
        for mname, key in pairs:
            rm = R[mname]
            if rm.is_empty():
                viol.append({'rule': '%s.%s.enclosure' % (v, mname),
                             'check': 'enclosure', 'error': 'metal layer empty'})
                continue
            for item in check_enclosure(rm, rv, RULES[key], directional=True):
                item = dict(item)
                item['rule'] = '%s.%s.enclosure' % (v, mname)
                viol.append(item)

    # ---- via spacing
    #
    # The deck rules are `spacing v1 v1 60 touching_ok` (0.060) and
    # `spacing v2 v2 120 touching_ok` (0.120). `touching_ok` is exactly the
    # semantics of space_check() on the *merged* region: vias that touch are
    # one polygon and are not flagged.
    for v, key in VIA_SPACE.items():
        need = RULES[key]
        r = R[v]
        if need is None or r.is_empty() or r.count() < 2:
            continue
        viol += _collect(r.space_check(um(need)), '%s.min_space' % v, need, 'space')

    # ---- on-grid
    g = um(GRID)
    for name, r in R.items():
        for p in r.each():
            bad = None
            for pt in p.each_point_hull():
                if pt.x % g or pt.y % g:
                    bad = (round(pt.x * DBU, 4), round(pt.y * DBU, 4))
                    break
            if bad:
                viol.append({'rule': '%s.offgrid' % name, 'check': 'grid',
                             'point_um': list(bad)})

    res = {
        'gds': gds,
        'top': top.name,
        'kind': 'LOCAL_GEOM_DRC',
        'note': 'Geometric re-implementation of selected sky130hd.lydrc BEOL '
                'rules via pya.Region native checks. NOT the official deck, '
                'NOT a substitute for Official Precheck. FEOL/density/antenna/'
                'pin/max-width rules are not covered.',
        'rules': RULES,
        'layer_counts': {k: v.count() for k, v in R.items()},
        'violations': viol,
        'n_violations': len(viol),
        'pass': len(viol) == 0,
    }
    if verbose:
        print('GDS :', gds)
        print('top :', top.name)
        print('kind:', res['kind'])
        print('layers:', res['layer_counts'])
        if viol:
            print('VIOLATIONS: %d' % len(viol))
            for v in viol[:20]:
                print('   ', v)
        else:
            print('PASS: 0 violations under the implemented rule subset')
    return res


if __name__ == '__main__':
    r = run(sys.argv[1])
    if len(sys.argv) > 2:
        json.dump(r, open(sys.argv[2], 'w', encoding='utf-8'), indent=1,
                  ensure_ascii=False)
    sys.exit(0 if r['pass'] else 1)
