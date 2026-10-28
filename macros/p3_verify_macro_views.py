#!/usr/bin/env python3
"""p3_verify_macro_views.py — 逐宏验证 prBoundary / LEF SIZE / GDS bbox 三者一致。

用户要求："重新检查七个宏的 prBoundary（235/4）与 LEF SIZE 是否真实匹配，
并保存自动验证证据。"

对每个宏检查：
  1. GDS 里有且仅有 1 个 prBoundary (235/4) 矩形
  2. prBoundary 尺寸 == GDS 金属 bbox 尺寸
  3. LEF SIZE == prBoundary 尺寸
  4. LEF ORIGIN == GDS bbox 左下角
  5. 每个 LEF PIN 的 RECT 在该层 GDS 金属内（电气宏）
  6. 非电气宏（C4/D/E）没有任何 PIN，也没有 wire 行为

输出：v2_validation/P3_MACRO_VIEW_CONSISTENCY.json + .md
"""
import json
import os
import re
import sys

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'macros', 'out')
VAL = os.path.join(ROOT, 'v2_validation')

LAYERS = {'M1': (68, 20), 'Via1': (68, 44), 'M2': (69, 20),
          'Via2': (69, 44), 'M3': (70, 20), 'M4': (71, 20)}
PRB = (235, 4)
LEF_LAYER = {'M1': 'met1', 'M2': 'met2', 'M3': 'met3', 'M4': 'met4'}

TAGS = ['A', 'B', 'C1', 'C3', 'C4', 'D', 'E']
NON_ELEC = {'C3', 'C4', 'D', 'E'}


def shape_bbox(sh):
    if sh.is_box():
        return sh.box
    return sh.polygon.bbox()


def layer_region(top, li):
    r = pya.Region()
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
    return r


def parse_lef(path):
    """Parse a LEF MACRO block.

    NOTE: an earlier version used one big regex requiring PIN/DIRECTION/USE/
    PORT/LAYER/RECT to appear in an exact adjacency; it silently matched only
    the first pin of multi-pin macros (A/B reported 1 instead of 2, C3 4
    instead of 8). This version walks the PIN blocks individually.
    """
    txt = open(path, encoding='utf-8').read()
    macro = re.search(r'^MACRO\s+(\S+)', txt, re.M)
    size = re.search(r'^\s*SIZE\s+([\d.]+)\s+BY\s+([\d.]+)\s*;', txt, re.M)
    origin = re.search(r'^\s*ORIGIN\s+([\d.]+)\s+([\d.]+)\s*;', txt, re.M)

    pins = []
    # each PIN block runs from "PIN <name>" to the matching "END <name>"
    for pm in re.finditer(r'^\s*PIN\s+(\S+)\s*$(.*?)^\s*END\s+\1\s*$',
                          txt, re.S | re.M):
        name, body = pm.group(1), pm.group(2)
        for lm in re.finditer(
                r'^\s*LAYER\s+(\S+)\s*;\s*$\s*^\s*RECT\s+'
                r'(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*;',
                body, re.M):
            pins.append({
                'name': name,
                'layer': lm.group(1),
                'rect': [float(lm.group(2)), float(lm.group(3)),
                         float(lm.group(4)), float(lm.group(5))],
            })
    return {
        'macro': macro.group(1) if macro else None,
        'size': [float(size.group(1)), float(size.group(2))] if size else None,
        'origin': [float(origin.group(1)), float(origin.group(2))] if origin else None,
        'pins': pins,
        'has_symmetry': 'SYMMETRY' in txt,
        'has_obs': bool(re.search(r'^\s*OBS\s*$', txt, re.M)),
    }


def main():
    os.makedirs(VAL, exist_ok=True)
    results, problems = [], []

    for tag in TAGS:
        gds = os.path.join(OUT, 'struct_%s.gds' % tag)
        lef = os.path.join(OUT, 'struct_%s.lef' % tag)
        L = pya.Layout(); L.read(gds)
        top = L.top_cell()
        dbu = L.dbu

        # ---- prBoundary
        prb_li = L.find_layer(*PRB)
        prb_shapes = ([s for s in top.shapes(prb_li).each()]
                      if prb_li is not None else [])
        n_prb = len(prb_shapes)
        if n_prb != 1:
            problems.append('%s: prBoundary count %d != 1' % (tag, n_prb))
        prb_box = shape_bbox(prb_shapes[0]) if prb_shapes else None
        prb_um = ([round(prb_box.width() * dbu, 4),
                   round(prb_box.height() * dbu, 4)] if prb_box else None)

        # ---- metal bbox (excluding prBoundary)
        mbb = None
        for name, (ln, dt) in LAYERS.items():
            li = L.find_layer(ln, dt)
            if li is None:
                continue
            for sh in top.shapes(li).each():
                b = shape_bbox(sh)
                if mbb is None:
                    mbb = b
                else:
                    mbb = pya.Box(min(mbb.left, b.left), min(mbb.bottom, b.bottom),
                                  max(mbb.right, b.right), max(mbb.top, b.top))
        mbb_um = ([round(mbb.width() * dbu, 4), round(mbb.height() * dbu, 4)]
                  if mbb else None)

        # ---- LEF
        lf = parse_lef(lef)

        # ---- compare
        ok_prb_vs_metal = (prb_um and mbb_um
                           and abs(prb_um[0] - mbb_um[0]) < 0.002
                           and abs(prb_um[1] - mbb_um[1]) < 0.002)
        ok_lef_vs_prb = (lf['size'] and prb_um
                         and abs(lf['size'][0] - prb_um[0]) < 0.002
                         and abs(lf['size'][1] - prb_um[1]) < 0.002)
        gds_ll = [round(mbb.left * dbu, 4), round(mbb.bottom * dbu, 4)] if mbb else None
        ok_origin = (lf['origin'] and gds_ll
                     and abs(lf['origin'][0] - gds_ll[0]) < 0.002
                     and abs(lf['origin'][1] - gds_ll[1]) < 0.002)

        if not ok_prb_vs_metal:
            problems.append('%s: prBoundary %s != metal bbox %s'
                            % (tag, prb_um, mbb_um))
        if not ok_lef_vs_prb:
            problems.append('%s: LEF SIZE %s != prBoundary %s'
                            % (tag, lf['size'], prb_um))
        if not ok_origin:
            problems.append('%s: LEF ORIGIN %s != GDS bbox ll %s'
                            % (tag, lf['origin'], gds_ll))

        # ---- PINs
        pin_checks = []
        for p in lf['pins']:
            lay = p['layer']
            mname = {'met1': 'M1', 'met2': 'M2', 'met3': 'M3', 'met4': 'M4'}[lay]
            li = L.find_layer(*LAYERS[mname])
            reg = layer_region(top, li) if li is not None else pya.Region()
            # PIN rect is macro-local; add ORIGIN to get absolute
            ox, oy = lf['origin'] if lf['origin'] else (0.0, 0.0)
            x0, y0, x1, y1 = p['rect']
            box = pya.Box(int(round((x0 + ox) / dbu)), int(round((y0 + oy) / dbu)),
                          int(round((x1 + ox) / dbu)), int(round((y1 + oy) / dbu)))
            covered = (pya.Region(box) - reg).is_empty()
            pin_checks.append({'name': p['name'], 'layer': lay,
                               'covered_by_metal': covered})
            if not covered:
                problems.append('%s PIN %s (%s) not covered by drawn metal'
                                % (tag, p['name'], lay))

        # ---- non-electrical must have zero pins
        if tag in NON_ELEC and lf['pins']:
            problems.append('%s is NON_ELECTRICAL but LEF declares %d PIN(s)'
                            % (tag, len(lf['pins'])))

        results.append({
            'structure_id': tag,
            'cell': top.name,
            'lef_macro': lf['macro'],
            'name_match': top.name == lf['macro'],
            'prboundary_count': n_prb,
            'prboundary_um': prb_um,
            'gds_metal_bbox_um': mbb_um,
            'lef_size_um': lf['size'],
            'lef_origin': lf['origin'],
            'gds_bbox_ll_um': gds_ll,
            'prb_equals_metal': ok_prb_vs_metal,
            'lef_equals_prb': ok_lef_vs_prb,
            'origin_match': ok_origin,
            'n_pins': len(lf['pins']),
            'pins': pin_checks,
            'electrical': tag not in NON_ELEC,
            'lef_has_symmetry': lf['has_symmetry'],
            'lef_has_obs': lf['has_obs'],
        })

    summary = {
        'all_pass': len(problems) == 0,
        'problems': problems,
        'macros': results,
        'note': 'PLANNING-stage check on the macro views themselves. This does '
                'NOT verify placement in a real 2x2 layout, PDN interaction, '
                'or LVS.',
    }
    json.dump(summary, open(os.path.join(VAL, 'P3_MACRO_VIEW_CONSISTENCY.json'),
                            'w', encoding='utf-8'), indent=1, ensure_ascii=False)

    # ---- markdown
    md = ['# 宏视图一致性验证（prBoundary / LEF SIZE / GDS bbox / PIN）', '',
          '自动生成：`macros/p3_verify_macro_views.py`  ',
          '证据：`v2_validation/P3_MACRO_VIEW_CONSISTENCY.json`', '',
          '| Tag | cell==lef | prB 数 | prBoundary (µm) | GDS metal bbox (µm) | '
          'LEF SIZE (µm) | prB=metal | LEF=prB | ORIGIN ok | PIN 数 | PIN 全在金属 |',
          '|---|---|---|---|---|---|---|---|---|---|']
    for r in results:
        pins_ok = all(p['covered_by_metal'] for p in r['pins']) if r['pins'] else True
        md.append('| %s | %s | %d | %.3f × %.3f | %.3f × %.3f | %.3f × %.3f | '
                  '%s | %s | %s | %d | %s |'
                  % (r['structure_id'], '✓' if r['name_match'] else '✗',
                     r['prboundary_count'],
                     r['prboundary_um'][0], r['prboundary_um'][1],
                     r['gds_metal_bbox_um'][0], r['gds_metal_bbox_um'][1],
                     r['lef_size_um'][0], r['lef_size_um'][1],
                     '✓' if r['prb_equals_metal'] else '✗',
                     '✓' if r['lef_equals_prb'] else '✗',
                     '✓' if r['origin_match'] else '✗',
                     r['n_pins'], '✓' if pins_ok else '✗'))
    md += ['', '## 结论', '']
    if problems:
        md.append('**FAIL** — %d 个问题：' % len(problems))
        for p in problems:
            md.append('- %s' % p)
    else:
        md.append('**PASS** — 七个宏的 prBoundary / LEF SIZE / GDS bbox / ORIGIN '
                  '/ PIN 全部一致。')
    md += ['', '> 这是**规划阶段**的宏视图自洽检查。它不验证宏在真实 2×2 版图中的',
           '> 放置、PDN 交互或 LVS。']
    open(os.path.join(VAL, 'P3_MACRO_VIEW_CONSISTENCY.md'), 'w',
         encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')

    print('%-3s %-8s %5s %-16s %-16s %-16s %7s %7s %7s %5s'
          % ('tag', 'name', 'prB', 'prBoundary', 'metal_bbox', 'LEF_SIZE',
             'prB=mtl', 'lef=prB', 'origin', 'pins'))
    for r in results:
        print('%-3s %-8s %5d %-16s %-16s %-16s %7s %7s %7s %5d'
              % (r['structure_id'], 'ok' if r['name_match'] else 'BAD',
                 r['prboundary_count'],
                 '%.3fx%.3f' % tuple(r['prboundary_um']),
                 '%.3fx%.3f' % tuple(r['gds_metal_bbox_um']),
                 '%.3fx%.3f' % tuple(r['lef_size_um']),
                 'OK' if r['prb_equals_metal'] else 'FAIL',
                 'OK' if r['lef_equals_prb'] else 'FAIL',
                 'OK' if r['origin_match'] else 'FAIL',
                 r['n_pins']))
    print()
    if problems:
        print('FAIL (%d):' % len(problems))
        for p in problems:
            print('  !', p)
    else:
        print('ALL MACRO VIEWS CONSISTENT')
    print('written P3_MACRO_VIEW_CONSISTENCY.{json,md}')
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
