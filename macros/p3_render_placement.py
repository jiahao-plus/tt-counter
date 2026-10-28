#!/usr/bin/env python3
"""p3_render_placement.py — 生成 P3_MACRO_PLACEMENT.png。

画 die 边界、core 矩形、七个宏的 bbox，并标注结构编号。
同时画 V1 实测的 M4 电源条 x 位置（外推标记），提示潜在的 SEM 遮挡。
"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLAN = os.path.join(ROOT, 'v2_validation', 'p3_placement.json')
OUT = os.path.join(ROOT, 'v2_validation', 'P3_MACRO_PLACEMENT.png')

COLOR_ELEC = '#2a6fdb'
COLOR_NON = '#d9822b'


def main():
    plan = json.load(open(PLAN, encoding='utf-8'))
    die_w, die_h = plan['die_um']
    cx0, cy0, cx1, cy1 = plan['core_rect_um']

    fig, ax = plt.subplots(figsize=(14, 10))

    # die
    ax.add_patch(Rectangle((0, 0), die_w, die_h, fill=False,
                           ec='black', lw=2, label='die (nominal)'))
    # core
    ax.add_patch(Rectangle((cx0, cy0), cx1 - cx0, cy1 - cy0,
                           fill=False, ec='green', lw=1.2, ls='--',
                           label='core (EXTRAPOLATED)'))

    # V1-measured M4 strap x positions, tiled across the 2x2 width by the
    # 27.14 um pitch. These are a guess for 2x2 and are drawn dashed to say so.
    v1_strap_x = [19.08, 22.38, 57.95, 61.25, 96.82, 100.12, 135.69, 138.99]
    pitch = 27.14
    xs = list(v1_strap_x)
    x = v1_strap_x[-1] + pitch
    while x < die_w:
        xs.append(x); x += pitch
    for sx in xs:
        ax.axvline(sx, color='red', lw=0.6, alpha=0.35, ls=':')

    # macros
    for p in plan['placements']:
        c = COLOR_ELEC if p['electrical'] else COLOR_NON
        ax.add_patch(Rectangle((p['x_um'], p['y_um']), p['w_um'], p['h_um'],
                               facecolor=c, alpha=0.55, edgecolor='black', lw=1.2))
        ax.text(p['x_um'] + p['w_um'] / 2, p['y_um'] + p['h_um'] / 2,
                '%s\n%s' % (p['structure_id'],
                            'elec' if p['electrical'] else 'non-elec'),
                ha='center', va='center', fontsize=8, fontweight='bold')

    # logic zone hint
    ax.add_patch(Rectangle((cx0, cy0), cx1 - cx0, 145 - cy0,
                           facecolor='#dddddd', alpha=0.25, edgecolor='none'))
    ax.text(die_w / 2, 70, 'standard cells / functional logic\n(auto-placed by P&R)',
            ha='center', va='center', fontsize=11, color='#555')

    ax.set_xlim(-5, die_w + 5)
    ax.set_ylim(-5, die_h + 5)
    ax.set_aspect('equal')
    ax.set_xlabel('x (µm)')
    ax.set_ylabel('y (µm)')
    ax.set_title('V2 2x2 macro placement — PLAN_ONLY\n'
                 'core rect is extrapolated from V1 margins, NOT measured',
                 fontsize=11)

    handles = [
        Patch(facecolor=COLOR_ELEC, alpha=0.55, label='electrical macro'),
        Patch(facecolor=COLOR_NON, alpha=0.55, label='NON_ELECTRICAL macro'),
        Patch(facecolor='none', ec='green', ls='--', label='core (extrapolated)'),
        Patch(facecolor='none', ec='red', ls=':', label='M4 strap x (V1 guess)'),
        Patch(facecolor='#dddddd', alpha=0.4, label='logic zone'),
    ]
    ax.legend(handles=handles, loc='lower right', fontsize=8, framealpha=0.9)

    fig.tight_layout()
    fig.savefig(OUT, dpi=170)
    print('wrote', OUT)
    print('die %.1f x %.1f, core %.1f x %.1f, %d macros'
          % (die_w, die_h, cx1 - cx0, cy1 - cy0, len(plan['placements'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
