#!/usr/bin/env python3
"""p3_assert_consistency.py — 断言放置方案的五个数据源彼此一致。

单一日程数据源：v2_validation/p3_placement.json（由 p3_placement_plan.py 生成）

必须一致的副本：
  1. src/config.json               的 MACROS[*].instances[*].location / orientation
  2. v2_validation/P3_MACRO_BBOX.csv
  3. v2_spec/P3_MACRO_PLACEMENT_PLAN.md 的自动生成表格
  4. v2_validation/p3_placement.json  自身（自洽检查）

失败时逐条列出差异并返回非零退出码。
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLAN = os.path.join(ROOT, 'v2_validation', 'p3_placement.json')
CFG = os.path.join(ROOT, 'src', 'config.json')
CSV = os.path.join(ROOT, 'v2_validation', 'P3_MACRO_BBOX.csv')
MD = os.path.join(ROOT, 'v2_spec', 'P3_MACRO_PLACEMENT_PLAN.md')

TOL = 0.011       # um; JSON/CSV round to 2-3 dp
MIN_GAP_UM = 5.00  # hard requirement restored by the user; asserted here so it
                   # cannot be silently relaxed again


def fail(msgs, msg):
    msgs.append(msg)


def check_placement_constraints(plan, msgs):
    """C1 inside core / C2 no overlap / C3 min gap >= MIN_GAP_UM / C4 all N."""
    cx0, cy0, cx1, cy1 = plan['core_rect_um']
    ps = plan['placements']

    for p in ps:
        if not (p['x_um'] >= cx0 and p['y_um'] >= cy0
                and p['x1_um'] <= cx1 and p['y1_um'] <= cy1):
            fail(msgs, 'C1: %s outside core' % p['structure_id'])
        if p['orientation'] != 'N':
            fail(msgs, 'C4: %s orientation %s != N'
                 % (p['structure_id'], p['orientation']))

    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            a, b = ps[i], ps[j]
            ox = min(a['x1_um'], b['x1_um']) - max(a['x_um'], b['x_um'])
            oy = min(a['y1_um'], b['y1_um']) - max(a['y_um'], b['y_um'])
            if ox > 0 and oy > 0:
                fail(msgs, 'C2: overlap %s/%s %.2fx%.2f'
                     % (a['structure_id'], b['structure_id'], ox, oy))
            dx = max(a['x_um'] - b['x1_um'], b['x_um'] - a['x1_um'], 0.0)
            dy = max(a['y_um'] - b['y1_um'], b['y_um'] - a['y1_um'], 0.0)
            d = (dx * dx + dy * dy) ** 0.5
            if d < MIN_GAP_UM - 1e-6:
                fail(msgs, 'C3: gap %.3f um < %.2f between %s and %s'
                     % (d, MIN_GAP_UM, a['structure_id'], b['structure_id']))

    declared = plan.get('min_gap_required_um')
    if declared is None or abs(declared - MIN_GAP_UM) > 1e-6:
        fail(msgs, 'C3: plan declares min_gap_required_um=%s, assertion '
                   'requires %.2f' % (declared, MIN_GAP_UM))


def main():
    plan = json.load(open(PLAN, encoding='utf-8'))
    cfg = json.load(open(CFG, encoding='utf-8'))
    md = open(MD, encoding='utf-8').read()
    rows = list(csv.DictReader(open(CSV, encoding='utf-8')))

    msgs = []
    by_tag = {p['structure_id']: p for p in plan['placements']}
    tags = sorted(by_tag)
    print('plan tags: %s' % ', '.join(tags))

    # ---- 0. placement constraints (C1..C4), including the 5 um minimum
    check_placement_constraints(plan, msgs)

    # ---- 1. self-consistency of the plan
    for p in plan['placements']:
        exp_x1 = round(p['x_um'] + p['w_um'], 3)
        exp_y1 = round(p['y_um'] + p['h_um'], 3)
        if abs(p['x1_um'] - exp_x1) > TOL:
            fail(msgs, 'plan self: %s x1 %.3f != x+w %.3f'
                 % (p['structure_id'], p['x1_um'], exp_x1))
        if abs(p['y1_um'] - exp_y1) > TOL:
            fail(msgs, 'plan self: %s y1 %.3f != y+h %.3f'
                 % (p['structure_id'], p['y1_um'], exp_y1))

    # ---- 2. config.json
    macros = cfg.get('MACROS', {})
    if len(macros) != len(tags):
        fail(msgs, 'config MACROS count %d != plan %d' % (len(macros), len(tags)))
    for p in plan['placements']:
        name = p['macro_name']
        m = macros.get(name)
        if not m:
            fail(msgs, 'config: missing MACROS["%s"]' % name); continue
        inst = p['instance']
        if inst not in m.get('instances', {}):
            fail(msgs, 'config: %s missing instance "%s"' % (name, inst)); continue
        loc = m['instances'][inst]['location']
        if abs(loc[0] - p['x_um']) > TOL or abs(loc[1] - p['y_um']) > TOL:
            fail(msgs, 'config: %s loc [%.2f,%.2f] != plan [%.2f,%.2f]'
                 % (name, loc[0], loc[1], p['x_um'], p['y_um']))
        orient = m['instances'][inst]['orientation']
        if orient != p['orientation']:
            fail(msgs, 'config: %s orientation %s != plan %s'
                 % (name, orient, p['orientation']))

    # ---- 3. CSV
    csv_by_tag = {r['structure_id']: r for r in rows}
    if set(csv_by_tag) != set(tags):
        fail(msgs, 'CSV tags %s != plan tags %s'
             % (sorted(csv_by_tag), tags))
    for p in plan['placements']:
        r = csv_by_tag.get(p['structure_id'])
        if not r:
            fail(msgs, 'CSV: missing %s' % p['structure_id']); continue
        for key, pk in (('x_um', 'x_um'), ('y_um', 'y_um'),
                        ('w_um', 'w_um'), ('h_um', 'h_um')):
            if abs(float(r[key]) - p[pk]) > TOL:
                fail(msgs, 'CSV: %s %s %.3f != plan %.3f'
                     % (p['structure_id'], key, float(r[key]), p[pk]))
        if r['orientation'] != p['orientation']:
            fail(msgs, 'CSV: %s orientation %s != plan %s'
                 % (p['structure_id'], r['orientation'], p['orientation']))

    # ---- 4. Markdown auto-generated table
    for p in plan['placements']:
        pat = r'\|\s*%s\s*\|[^\n]*?\(\s*([\d.]+),\s*([\d.]+)\s*\)' % p['structure_id']
        m = re.search(pat, md)
        if not m:
            fail(msgs, 'MD: no row for %s' % p['structure_id']); continue
        mx, my = float(m.group(1)), float(m.group(2))
        if abs(mx - p['x_um']) > TOL or abs(my - p['y_um']) > TOL:
            fail(msgs, 'MD: %s (%.2f,%.2f) != plan (%.2f,%.2f)'
                 % (p['structure_id'], mx, my, p['x_um'], p['y_um']))

    # ---- report
    print()
    if msgs:
        print('CONSISTENCY: FAIL (%d)' % len(msgs))
        for m in msgs:
            print('  !', m)
        return 1
    print('CONSISTENCY: PASS — plan / config.json / CSV / MD all agree')
    print('  checked %d structures across 4 sources' % len(tags))
    return 0


if __name__ == '__main__':
    sys.exit(main())
