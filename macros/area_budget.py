#!/usr/bin/env python3
"""area_budget.py — 基于 V1 实测几何外推 2×2 可用面积。

数据来源（全部实测，非文档）：
  - V1 routed DEF: DIEAREA, ROW, TRACKS
  - V1 GDS: 实际使用范围
  - 官方 2×2 名义尺寸: 335 x 226 um

输出：可用的行/列数量、核心面积、研究宏可用面积。
"""
import json
import os
import re
import sys

V1_DEF = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '..', 'tt-counter-exp', 'official_ci', 'GDS_logs', 'runs', 'wokwi',
    'final', 'def', 'tt_um_jiahao_plus_counter.def')

# official 2x2 nominal
NOMINAL_W = 335.0
NOMINAL_H = 226.0


def parse_v1(path):
    txt = open(path, encoding='utf-8', errors='replace').read()
    die = re.search(r'DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)', txt)
    die_um = [int(die.group(i)) / 1000.0 for i in (1, 2, 3, 4)] if die else None

    rows = []
    # DEF ROW syntax: ROW <name> <site> <x> <y> <orient> DO <nx> BY <ny>
    #                STEP <dx> <dy> ;   (dy is present, usually 0)
    for m in re.finditer(
            r'^ROW\s+(\S+)\s+(\S+)\s+(-?\d+)\s+(-?\d+)\s+(\S+)\s+'
            r'DO\s+(\d+)\s+BY\s+(\d+)\s+STEP\s+(-?\d+)\s+(-?\d+)',
            txt, re.M):
        rows.append({
            'name': m.group(1), 'site': m.group(2),
            'x': int(m.group(3)) / 1000.0, 'y': int(m.group(4)) / 1000.0,
            'orient': m.group(5),
            'numx': int(m.group(6)), 'numy': int(m.group(7)),
            'stepx': int(m.group(8)) / 1000.0, 'stepy': int(m.group(9)) / 1000.0,
        })
    if not rows:
        raise RuntimeError('no ROW parsed from %s' % path)

    tracks = {}
    for m in re.finditer(r'^TRACKS\s+(\S+)\s+(\d+)\s+DO\s+(\d+)\s+STEP\s+(\d+)\s+LAYER\s+(\S+)',
                         txt, re.M):
        tracks.setdefault(m.group(5), {})[m.group(1)] = {
            'start': int(m.group(2)) / 1000.0,
            'count': int(m.group(3)),
            'step': int(m.group(4)) / 1000.0,
        }
    return die_um, rows, tracks


def main():
    die, rows, tracks = parse_v1(V1_DEF)
    if not rows:
        print('FAILED to parse ROW from', V1_DEF); return 1

    r0 = rows[0]
    col_pitch = r0['stepx']
    # DEF ROW STEP's second component is 0 (a row repeats horizontally); the
    # real row pitch is the y difference between consecutive rows.
    ys = sorted({round(r['y'], 3) for r in rows})
    if len(ys) < 2:
        raise RuntimeError('need >=2 distinct row y values, got %d' % len(ys))
    row_pitch = round(ys[1] - ys[0], 3)
    site_w = r0['numx'] * col_pitch
    site_h = row_pitch

    # V1 core extent implied by rows
    v1_core_x0 = min(r['x'] for r in rows)
    v1_core_y0 = min(r['y'] for r in rows)
    v1_core_x1 = max(r['x'] + r['numx'] * r['stepx'] for r in rows)
    v1_core_y1 = max(r['y'] + r['numy'] * r['stepy'] for r in rows)

    # margins from die edge to core
    mx0 = v1_core_x0
    my0 = v1_core_y0
    mx1 = die[2] - v1_core_x1
    my1 = die[3] - v1_core_y1

    # extrapolate to 2x2: keep the same margins
    core_w_2x2 = NOMINAL_W - mx0 - mx1
    core_h_2x2 = NOMINAL_H - my0 - my1
    n_rows_2x2 = int(core_h_2x2 // row_pitch)
    n_cols_2x2 = int(core_w_2x2 // col_pitch)

    res = {
        'v1': {
            'die_um': die,
            'die_area_um2': round((die[2] - die[0]) * (die[3] - die[1]), 1),
            'core_um': [v1_core_x0, v1_core_y0, v1_core_x1, v1_core_y1],
            'core_area_um2': round((v1_core_x1 - v1_core_x0) * (v1_core_y1 - v1_core_y0), 1),
            'n_rows': len(rows),
            'cols_per_row': r0['numx'],
            'row_pitch_um': row_pitch,
            'col_pitch_um': col_pitch,
            'site_w_um': round(site_w, 3),
            'site_h_um': round(site_h, 3),
            'sites_total': len(rows) * r0['numx'],
            'margins_um': [mx0, my0, round(mx1, 3), round(my1, 3)],
        },
        'v2_2x2_extrapolated': {
            'nominal_um': [NOMINAL_W, NOMINAL_H],
            'nominal_area_um2': NOMINAL_W * NOMINAL_H,
            'core_um': [mx0, my0, round(NOMINAL_W - mx1, 3), round(NOMINAL_H - my1, 3)],
            'core_area_um2': round(core_w_2x2 * core_h_2x2, 1),
            'n_rows': n_rows_2x2,
            'cols_per_row': n_cols_2x2,
            'sites_total': n_rows_2x2 * n_cols_2x2,
            'ratio_vs_v1_area': round((core_w_2x2 * core_h_2x2) /
                                      ((v1_core_x1 - v1_core_x0) * (v1_core_y1 - v1_core_y0)), 2),
            'ratio_vs_v1_sites': round((n_rows_2x2 * n_cols_2x2) /
                                       (len(rows) * r0['numx']), 2),
        },
        'caveat': 'EXTRAPOLATED from V1 margins, not measured on a real 2x2 run. '
                  'The 2x2 PDN template (tt_block_2x2_pg.def) is not available '
                  'locally; official CI is the only authority. Treat core area '
                  'as an upper bound.',
        'tracks_v1': tracks,
    }

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', 'v2_spec', 'area_budget.json')
    json.dump(res, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)

    v = res['v1']; x = res['v2_2x2_extrapolated']
    print('=== V1 (measured) ===')
    print('  die            %.3f x %.3f um  = %.0f um2'
          % (die[2] - die[0], die[3] - die[1], v['die_area_um2']))
    print('  core           %.3f x %.3f um  = %.0f um2'
          % (v['core_um'][2] - v['core_um'][0], v['core_um'][3] - v['core_um'][1],
             v['core_area_um2']))
    print('  rows           %d   cols %d   sites %d'
          % (v['n_rows'], v['cols_per_row'], v['sites_total']))
    print('  row pitch      %.3f um   col pitch %.3f um' % (row_pitch, col_pitch))
    print('  margins (L,B,R,T) %s um' % v['margins_um'])
    print()
    print('=== 2x2 (extrapolated, upper bound) ===')
    print('  nominal        %.0f x %.0f um  = %.0f um2'
          % (NOMINAL_W, NOMINAL_H, x['nominal_area_um2']))
    print('  core           %.0f um2' % x['core_area_um2'])
    print('  rows %d  cols %d  sites %d' % (x['n_rows'], x['cols_per_row'], x['sites_total']))
    print('  ratio vs V1    %.2fx area, %.2fx sites'
          % (x['ratio_vs_v1_area'], x['ratio_vs_v1_sites']))
    print()
    print('CAVEAT:', res['caveat'])
    print('written', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
