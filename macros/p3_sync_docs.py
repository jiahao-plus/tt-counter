#!/usr/bin/env python3
"""p3_sync_docs.py — 让 P3_MACRO_PLACEMENT_PLAN.md 的坐标表与 p3_placement.json 同步。

背景：手写 Markdown 与机器生成的 JSON/CSV 会漂移。第一次审查就发现 MD 里
还是旧坐标（A=(40,198)、D=(20,155,N)），而 JSON/CSV/config 已经是
A=(31,204)、D=(25,150,E)。

本脚本用 p3_placement.json 作为**唯一数据源**重写 MD 的坐标表段落，
并在其它文件里插一个自动生成标记。配合 p3_assert_consistency.py 使用。

用法：python3 macros/p3_sync_docs.py [--check]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLAN = os.path.join(ROOT, 'v2_validation', 'p3_placement.json')
MD = os.path.join(ROOT, 'v2_spec', 'P3_MACRO_PLACEMENT_PLAN.md')

BEGIN = '<!-- BEGIN AUTO-GENERATED PLACEMENT TABLE -->'
END = '<!-- END AUTO-GENERATED PLACEMENT TABLE -->'

DESC = {
    'A': 'M1–Via1–M2 信号连接',
    'B': 'M2–Via2–M3 信号连接',
    'C1': '单 Net 多分支',
    'C3': '不同间距的邻近金属线',
    'C4': '跨层交叉但无 Via（负样本）',
    'D': '线宽/密度阶梯',
    'E': '多层配准标记',
}


def render_table(plan):
    lines = [BEGIN, '',
             '| Tag | 宏 | 实例名 | 位置 (µm) | 尺寸 (µm) | 朝向 | 电气 | PIN | 说明 |',
             '|---|---|---|---|---|---|---|---|---|']
    for p in plan['placements']:
        # Report the real placement, i.e. design-intent + whatever the cell
        # frame needs.  For the four geometry-only macros the two coincide; for
        # the three normalised macros they differ by `local_origin`, and the
        # documented position must be where the metal actually sits.
        px = p.get('place_x_um', p['x_um'])
        py = p.get('place_y_um', p['y_um'])
        lines.append('| %s | `%s` | `%s` | (%.2f, %.2f) | %.2f × %.2f | `%s` | %s | %d | %s |'
                     % (p['structure_id'], p['macro_name'], p['instance'],
                        px, py, p['w_um'], p['h_um'],
                        p['orientation'],
                        '✓' if p['electrical'] else '✗',
                        p['n_pins'],
                        DESC.get(p['structure_id'], '')))
    lines += ['', END]
    return '\n'.join(lines)


def main():
    check_only = '--check' in sys.argv
    plan = json.load(open(PLAN, encoding='utf-8'))
    table = render_table(plan)
    md = open(MD, encoding='utf-8').read()

    if BEGIN in md and END in md:
        new = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END), table,
                     md, flags=re.S)
    else:
        # first run: replace the hand-written table block
        pat = re.compile(r'(\| Tag \| 宏 \|.*?\n)(\n)', re.S)
        if pat.search(md):
            new = pat.sub(table + '\n\n', md, count=1)
        else:
            print('FAIL: could not find the placement table in', MD)
            return 1

    changed = (new != md)
    if check_only:
        print('MD in sync:', not changed)
        if changed:
            print('  run without --check to rewrite')
        return 0 if not changed else 1

    if changed:
        open(MD, 'w', encoding='utf-8', newline='\n').write(new)
        print('rewrote', MD)
    else:
        print('MD already in sync')
    print(table.split('\n')[2])
    for p in plan['placements']:
        print('  %-3s (%7.2f, %7.2f) %s'
              % (p['structure_id'],
                 p.get('place_x_um', p['x_um']),
                 p.get('place_y_um', p['y_um']),
                 p['orientation']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
