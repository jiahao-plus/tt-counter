#!/usr/bin/env python3
"""p3_pdn_conflict_check.py — 宏 bbox 与假定 M4 strap 的冲突分析。

背景：2×2 的真实 PDN 布局未知。本脚本用 V1 实测的 M4 strap 参数外推，
给出"如果 2×2 沿用同样 pitch，宏会被哪些 strap 穿过"的估计。

明确标注：这是**估计**，不是实测。首次官方 CI 的 DEF 才有真实 strap 位置。

为什么重要：
  * M4 strap 在宏的 M1/M2/M3 几何之上，不构成电气短路
  * 但 M4 是不透明的顶层金属，会**遮挡 SEM 成像**——
    这直接损害 V2 的核心研究目的
  * 所以必须量化遮挡程度

输出：v2_validation/P3_PDN_CONFLICT.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLAN = os.path.join(ROOT, 'v2_validation', 'p3_placement.json')

# V1 measured M4 strap geometry (from tt-counter-exp routed DEF SPECIALNETS)
V1_STRAP_X = [19.08, 22.38, 57.95, 61.25, 96.82, 100.12, 135.69, 138.99]
V1_STRAP_W = 1.600
V1_PITCH = 27.14


def extend_straps(die_w):
    """Tile the V1 strap pattern across the 2x2 width using its own pitch."""
    xs = list(V1_STRAP_X)
    x = V1_STRAP_X[-1] + V1_PITCH
    while x < die_w:
        xs.append(round(x, 3)); x += V1_PITCH
    return xs


def main():
    plan = json.load(open(PLAN, encoding='utf-8'))
    die_w = plan['die_um'][0]
    straps = extend_straps(die_w)

    print('assumed M4 straps (V1 pattern tiled): %d' % len(straps))
    print('   ', [round(s, 1) for s in straps])
    print()

    rows = []
    for p in plan['placements']:
        x0, x1 = p['x_um'], p['x1_um']
        y0, y1 = p['y_um'], p['y1_um']
        hit = []
        covered_w = 0.0
        for sx in straps:
            s0, s1 = sx - V1_STRAP_W / 2, sx + V1_STRAP_W / 2
            if s1 <= x0 or s0 >= x1:
                continue
            ov = min(x1, s1) - max(x0, s0)
            if ov > 0:
                hit.append({'strap_x': round(sx, 3),
                            'overlap_um': round(ov, 3)})
                covered_w += ov
        frac = covered_w / (x1 - x0) if (x1 - x0) > 0 else 0.0
        rows.append({
            'structure_id': p['structure_id'],
            'macro_name': p['macro_name'],
            'x_range_um': [round(x0, 3), round(x1, 3)],
            'n_straps_crossing': len(hit),
            'straps': hit,
            'width_fraction_covered': round(frac, 4),
            'obstruction': ('NONE' if not hit else
                            'LOW' if frac < 0.10 else
                            'MEDIUM' if frac < 0.25 else 'HIGH'),
        })

    res = {
        'status': 'ESTIMATE_ONLY',
        'caveat': 'The 2x2 PDN layout is unknown. These straps are the V1 '
                  'measured pattern tiled across the 2x2 width by its own '
                  '27.14 um pitch. The real 2x2 strap positions must be read '
                  'from the first official CI DEF before any conclusion.',
        'v1_strap_x_um': V1_STRAP_X,
        'v1_strap_width_um': V1_STRAP_W,
        'v1_pitch_um': V1_PITCH,
        'assumed_2x2_strap_x_um': straps,
        'macros': rows,
        'note': 'M4 sits above the macro M1/M2/M3 geometry, so a crossing is '
                'NOT an electrical short. It matters because M4 is opaque and '
                'would obscure SEM imaging of the structures underneath.',
    }
    out = os.path.join(ROOT, 'v2_validation', 'P3_PDN_CONFLICT.json')
    json.dump(res, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)

    print('%-3s %-20s %-18s %5s %8s  %s'
          % ('tag', 'macro', 'x_range', 'n', 'covered', 'obstruction'))
    for r in rows:
        print('%-3s %-20s %-18s %5d %7.1f%%  %s'
              % (r['structure_id'], r['macro_name'],
                 '%.1f-%.1f' % tuple(r['x_range_um']),
                 r['n_straps_crossing'],
                 r['width_fraction_covered'] * 100,
                 r['obstruction']))

    worst = max(rows, key=lambda r: r['width_fraction_covered'])
    print()
    print('worst: %s (%s) %.1f%% of its width under an assumed strap'
          % (worst['structure_id'], worst['macro_name'],
             worst['width_fraction_covered'] * 100))
    print('written', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
