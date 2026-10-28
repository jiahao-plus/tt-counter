#!/usr/bin/env python3
"""geom_drc.py — 用 pya.Region 原生 check API 实现的 SKY130 几何 DRC。

为什么不用 sky130hd.lydrc 本身：
  KLayout 0.26.2 的 Ruby 解释器在 headless（-b/-r/-rm）下初始化即崩溃
  （backtrace 见 v2_validation/klayout_headless_crash.txt），且该 deck 是
  DRC-DSL(Ruby) 宏，pya.DRC 在 Python 模块中不存在。

因此本检查器用 deck 中**精确提取的规则值**（v2_spec/sky130_rules_measured.md），
调用 pya.Region 的**原生 DRC 检查 API**（width_check / space_check /
enclosing_check / isolated_check）重新实现关键 BEOL 规则：

  m1.1  min m1 width            0.140 um
  m1.2  min m1 spacing          0.140 um
  m2.1  min m2 width            0.140 um
  m2.2  min m2 spacing          0.140 um
  m3.1  min m3 width            0.300 um
  m3.*  min m3 spacing          0.300 um
  via.4a/b  m1 enclosure of via1  0.055 um
  via2.4/5  m2 enclosure of via2  0.040 um
  m3.4      m3 enclosure of via2  0.065 um
  m3.4/13   m3 enclosure of via3  0.060 um
  m4.3/15   m4 enclosure of via3  0.065 um
  via2.2/12 via2 spacing          0.200 um
  via3.2/12 via3 spacing          0.200 um
  x.1b      on-grid 0.005 um

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
    via1_cut=0.150, via1_m1_encl=0.055, via1_m2_encl=0.055,
    via2_cut=0.200, via2_m2_encl=0.040, via2_m3_encl=0.065,
    via3_cut=0.200, via3_m3_encl=0.060, via3_m4_encl=0.065,
    via_spacing=0.200,
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

    # ---- via enclosure by both metals (native enclosing_check)
    for v, pairs in VIA_ENCL.items():
        rv = R[v]
        if rv.is_empty():
            continue
        for mname, key in pairs:
            rm = R[mname]
            need = um(RULES[key])
            if rm.is_empty():
                viol.append({'rule': '%s.%s.enclosure' % (v, mname),
                             'check': 'enclosure', 'error': 'metal layer empty'})
                continue
            # KLayout: enclosing_check(other, d) -> places where `other` (the via)
            # is not enclosed by `self` (the metal) with distance d.
            viol += _collect(rm.enclosing_check(rv, need),
                             '%s.%s.enclosure' % (v, mname), RULES[key], 'enclosure')

    # ---- via spacing
    for v in ('Via1', 'Via2', 'Via3'):
        r = R[v]
        if r.is_empty() or r.count() < 2:
            continue
        viol += _collect(r.isolated_check(um(RULES['via_spacing'])),
                         '%s.min_space' % v, RULES['via_spacing'], 'space')

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
