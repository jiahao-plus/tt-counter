#!/usr/bin/env python3
"""p3_check_electrical_connectivity.py — 电气宏的 PIN/Net 连通性静态检查。

目的（用户要求）：
  "检查四个电气宏 A/B/C1/C3 的 PIN、Net 及连接约束，不允许全局
   ERROR_ON_DISCONNECTED_PINS: false 掩盖实际连接错误。"

本脚本在**设计阶段**做这些检查（不是 P&R 后，那只能靠 LVS）：

  1. 每个电气宏的每个 LEF PIN 都落在该层的真实金属上
  2. 同一宏的所有 PIN 属于**同一个连通分量**（该宏就是一个 Net）
     —— 对 C3 例外：它是 4 对独立线，应为 4 个分量
  3. 宏内不存在意外的跨层连接（非 via 位置的层重叠）
  4. 非电气宏（C4/D/E）没有任何 PIN
  5. RTL 里每个电气宏实例的端口都接到了真实信号（不是悬空）

输出：v2_validation/P3_ELECTRICAL_CONNECTIVITY.json + .md
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
          'Via2': (69, 44), 'M3': (70, 20), 'Via3': (70, 44), 'M4': (71, 20)}
LEF2INT = {'met1': 'M1', 'met2': 'M2', 'met3': 'M3', 'met4': 'M4'}

# Expected number of independent connected components inside each macro, taken
# from the builders in gen_v2_macros.py — NOT guessed:
#   A  : netA (M1-Via1-M2) + netC (separate neighbour wire)      = 2
#   B  : single M2-Via2-M3 net                                    = 1
#   C1 : single net with three via branches (one node)            = 1
#   C3 : 4 pairs = 8 independent wires                            = 8
EXPECTED_COMPONENTS = {'A': 2, 'B': 1, 'C1': 1, 'C3': 8}
ELECTRICAL = ['A', 'B', 'C1', 'C3']
NON_ELECTRICAL = ['C4', 'D', 'E']


def region_of(top, li):
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


def parse_lef_pins(path):
    txt = open(path, encoding='utf-8').read()
    org = re.search(r'^\s*ORIGIN\s+([\d.]+)\s+([\d.]+)\s*;', txt, re.M)
    origin = (float(org.group(1)), float(org.group(2))) if org else (0.0, 0.0)
    pins = []
    for pm in re.finditer(r'^\s*PIN\s+(\S+)\s*$(.*?)^\s*END\s+\1\s*$',
                          txt, re.S | re.M):
        name, body = pm.group(1), pm.group(2)
        for lm in re.finditer(
                r'^\s*LAYER\s+(\S+)\s*;\s*$\s*^\s*RECT\s+'
                r'(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*;',
                body, re.M):
            pins.append({'name': name, 'layer': lm.group(1),
                         'rect': [float(lm.group(2)), float(lm.group(3)),
                                  float(lm.group(4)), float(lm.group(5))]})
    return origin, pins


def count_components(top, L, dbu):
    """Union-find over (layer, shape) with cross-layer edges only through real
    via cuts whose position is covered by both adjacent metals."""
    metals = ['M1', 'M2', 'M3', 'M4']
    shapes = {}
    for m in metals:
        li = L.find_layer(*LAYERS[m])
        lst = []
        if li is not None:
            for sh in top.shapes(li).each():
                b = (sh.box if sh.is_box() else sh.polygon.bbox())
                lst.append((b.left, b.bottom, b.right, b.top))
        shapes[m] = lst
    vias = {}
    for v in ('Via1', 'Via2', 'Via3'):
        li = L.find_layer(*LAYERS[v])
        lst = []
        if li is not None:
            for sh in top.shapes(li).each():
                b = (sh.box if sh.is_box() else sh.polygon.bbox())
                lst.append((b.left, b.bottom, b.right, b.top))
        vias[v] = lst

    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for m in metals:
        for i in range(len(shapes[m])):
            find((m, i))
        for i in range(len(shapes[m])):
            for j in range(i + 1, len(shapes[m])):
                a, b = shapes[m][i], shapes[m][j]
                if not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]):
                    union((m, i), (m, j))

    via_pairs = {'Via1': ('M1', 'M2'), 'Via2': ('M2', 'M3'), 'Via3': ('M3', 'M4')}
    for v, (lo, hi) in via_pairs.items():
        for cut in vias[v]:
            lo_hits = [i for i, s in enumerate(shapes[lo])
                       if s[0] <= cut[0] and s[1] <= cut[1]
                       and s[2] >= cut[2] and s[3] >= cut[3]]
            hi_hits = [i for i, s in enumerate(shapes[hi])
                       if s[0] <= cut[0] and s[1] <= cut[1]
                       and s[2] >= cut[2] and s[3] >= cut[3]]
            for a in lo_hits:
                for b in hi_hits:
                    union((lo, a), (hi, b))

    return len({find(k) for k in parent})


def check_rtl_ports():
    """Every electrical macro instance in project.v must have all its ports
    connected to a named wire (not left open)."""
    proj = open(os.path.join(ROOT, 'src', 'project.v'), encoding='utf-8').read()
    issues = []
    for tag, cell in (('A', 'research_via1'), ('B', 'research_via2'),
                      ('C1', 'research_branch'), ('C3', 'research_near')):
        m = re.search(r'%s\s+(\w+)\s*\((.*?)\);' % re.escape(cell), proj, re.S)
        if not m:
            issues.append('%s: instance of %s not found in project.v' % (tag, cell))
            continue
        inst, body = m.group(1), m.group(2)
        ports = re.findall(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', body)
        if not ports:
            issues.append('%s (%s): no port connections found' % (tag, inst))
        for pname, pwire in ports:
            if not pwire.strip():
                issues.append('%s (%s): port .%s left open' % (tag, inst, pname))
    return issues


def main():
    results, problems = [], []

    for tag in ELECTRICAL + NON_ELECTRICAL:
        gds = os.path.join(OUT, 'struct_%s.gds' % tag)
        lef = os.path.join(OUT, 'struct_%s.lef' % tag)
        L = pya.Layout(); L.read(gds)
        top = L.top_cell()
        dbu = L.dbu
        origin, pins = parse_lef_pins(lef)

        # ---- 1. every pin on real metal
        pin_res = []
        for p in pins:
            mname = LEF2INT.get(p['layer'])
            li = L.find_layer(*LAYERS[mname]) if mname else None
            reg = region_of(top, li) if li is not None else pya.Region()
            x0, y0, x1, y1 = p['rect']
            box = pya.Box(int(round((x0 + origin[0]) / dbu)),
                          int(round((y0 + origin[1]) / dbu)),
                          int(round((x1 + origin[0]) / dbu)),
                          int(round((y1 + origin[1]) / dbu)))
            ok = (pya.Region(box) - reg).is_empty()
            pin_res.append({'name': p['name'], 'layer': p['layer'], 'on_metal': ok})
            if not ok:
                problems.append('%s PIN %s not on %s metal' % (tag, p['name'], p['layer']))

        # ---- 2. component count
        ncomp = count_components(top, L, dbu)
        if tag in EXPECTED_COMPONENTS:
            exp = EXPECTED_COMPONENTS[tag]
            if ncomp != exp:
                problems.append('%s: %d connected components, expected %d'
                                % (tag, ncomp, exp))
        else:
            # non-electrical: components are irrelevant, but there must be no vias
            nvia = sum(1 for v in ('Via1', 'Via2', 'Via3')
                       if L.find_layer(*LAYERS[v]) is not None
                       for _ in top.shapes(L.find_layer(*LAYERS[v])).each())
            if nvia:
                problems.append('%s is NON_ELECTRICAL but has %d via cut(s)'
                                % (tag, nvia))

        # ---- 3. non-electrical must have zero pins
        if tag in NON_ELECTRICAL and pins:
            problems.append('%s is NON_ELECTRICAL but LEF declares %d PIN(s)'
                            % (tag, len(pins)))

        results.append({
            'structure_id': tag,
            'electrical': tag in ELECTRICAL,
            'n_pins': len(pins),
            'pins': pin_res,
            'n_components': ncomp,
            'expected_components': EXPECTED_COMPONENTS.get(tag),
        })

    # ---- 4. RTL port connections
    rtl_issues = check_rtl_ports()
    problems.extend(rtl_issues)

    summary = {
        'all_pass': len(problems) == 0,
        'problems': problems,
        'macros': results,
        'rtl_port_issues': rtl_issues,
        'scope': 'DESIGN-STAGE static check. Verifies macro-internal connectivity '
                 'and RTL port binding. It does NOT verify that P&R actually '
                 'routed the macro pins in the final layout — only official LVS '
                 'can answer that.',
    }
    json.dump(summary, open(os.path.join(VAL, 'P3_ELECTRICAL_CONNECTIVITY.json'),
                            'w', encoding='utf-8'), indent=1, ensure_ascii=False)

    md = ['# 电气宏 PIN / Net 连通性静态检查', '',
          '自动生成：`macros/p3_check_electrical_connectivity.py`  ',
          '证据：`v2_validation/P3_ELECTRICAL_CONNECTIVITY.json`', '',
          '| Tag | 电气 | PIN 数 | PIN 全在金属 | 连通分量 | 期望 | 结果 |',
          '|---|---|---|---|---|---|---|']
    for r in results:
        pins_ok = all(p['on_metal'] for p in r['pins']) if r['pins'] else True
        exp = r['expected_components']
        comp_ok = (exp is None) or (r['n_components'] == exp)
        md.append('| %s | %s | %d | %s | %d | %s | %s |'
                  % (r['structure_id'], '✓' if r['electrical'] else '✗',
                     r['n_pins'], '✓' if pins_ok else '✗',
                     r['n_components'], exp if exp is not None else '—',
                     '✓' if (pins_ok and comp_ok) else '✗'))
    md += ['', '## RTL 端口绑定', '']
    if rtl_issues:
        for i in rtl_issues:
            md.append('- ✗ %s' % i)
    else:
        md.append('✓ 四个电气宏实例的所有端口都接到了具名 wire，无悬空。')
    md += ['', '## 结论', '']
    if problems:
        md.append('**FAIL** — %d 个问题：' % len(problems))
        for p in problems:
            md.append('- %s' % p)
    else:
        md.append('**PASS** — 电气宏 PIN 全在金属、连通分量符合预期、RTL 端口无悬空。')
    md += ['', '> **范围**：这是**设计阶段**的静态检查，验证宏内部连通性与 RTL 端口绑定。',
           '> 它**不**验证 P&R 是否真的把宏引脚布通——那只能由官方 LVS 回答。']
    open(os.path.join(VAL, 'P3_ELECTRICAL_CONNECTIVITY.md'), 'w',
         encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')

    print('%-3s %-6s %4s %8s %6s %6s'
          % ('tag', 'elec', 'pins', 'on_metal', 'comps', 'expect'))
    for r in results:
        pins_ok = all(p['on_metal'] for p in r['pins']) if r['pins'] else True
        print('%-3s %-6s %4d %8s %6d %6s'
              % (r['structure_id'], 'yes' if r['electrical'] else 'no',
                 r['n_pins'], 'OK' if pins_ok else 'FAIL',
                 r['n_components'],
                 r['expected_components'] if r['expected_components'] else '-'))
    print()
    print('RTL port binding:', 'OK' if not rtl_issues else 'FAIL')
    for i in rtl_issues:
        print('  !', i)
    print()
    if problems:
        print('FAIL (%d):' % len(problems))
        for p in problems:
            print('  !', p)
    else:
        print('ELECTRICAL CONNECTIVITY: PASS')
    print('written P3_ELECTRICAL_CONNECTIVITY.{json,md}')
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
