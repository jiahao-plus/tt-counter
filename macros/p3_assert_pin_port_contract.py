#!/usr/bin/env python3
"""p3_assert_pin_port_contract.py — 五视图链断言（α′ 接口）。

## 它保护什么

用户的判据是五视图链：

    ① 物理连通分量（GDS） → ② LEF PIN → ③ Verilog 端口
       → ④ 综合网表 Net → ⑤ 最终 GDS（CI 产物，本地不可验）

本脚本在本地能验的范围内，逐宏检查这条链的每一跳是否语义一致。

**判据纠错记录。** 早先版本把"所有 PIN 位于同一 GDS 连通分量"当作电气宏的
准入条件。这是错的：普通多 Net 宏的 PIN 本来就分别位于不同连通分量；真正
要警惕的是反过来的情形——同一个连通分量上挂着属于不同逻辑 Net 的 PIN，
那才是物理短接与网表不一致。本脚本因此检查的是：

  * 同一个 PIN 下的全部 PORT 几何 → 必须落在**同一个**分量（α′ 的强连接
    语义，也是"这个 PIN 代表一个节点"的物理依据）；
  * 该分量必须含至少一个真实 via cut（证明它真的是跨层连通的节点，而不是
    一段孤立的单层金属）；
  * 不含 PIN 的分量必须**是空的**——不能有 PIN 误落到邻近的独立金属上
    （A 的 netC 邻居线就是这种情况）。

**LEF/DEF 规范要点。** 同一个 PIN 下，不同 PORT 之间是**弱连接**；同一个
PORT 内多个几何图形是**强连接**。信号路由需要强连接，所以 α′ 要求
**一个 PIN 恰好一个 PORT**。本脚本断言 PORT 数 == 1，防止有人"顺手"拆成
多个 PORT 而悄悄退回弱连接。

## 检查项

  C1  LEF PIN 名 == Verilog 端口名（逐字符，区分大小写）
  C2  LEF PIN 数 == Verilog 端口数
  C3  一个 PIN 恰好一个 PORT（α′ 强连接）
  C4  同一 PIN 的全部 PORT 几何在同一 GDS 连通分量
  C5  该分量含 ≥1 个 via cut（真的跨层连通）
  C6  LEF DIRECTION == Verilog 方向（INOUT / inout）
  C7  无端口宏：LEF PIN 数 == 0
  C8  无 PIN 的分量数符合物理预期（A 的 netC；B/C1 为 0）
  C9  综合网表：每个实例的端口名集合 == LEF PIN 名集合
  C10 综合网表：每个端口接且仅接一个非常量 net
  C11 综合网表：A/B/C1 三个实例接在同一个 net 上（设计意图：都接 pwm_out）

**C9–C11 需要 v2_validation/synth_netlist.v 存在。** 缺失时该项记为 SKIP，
SKIP 不算通过——总体结论只有在全部检查实际运行后才可能是 PASS。

用法（WSL，cwd 为仓库根）：python3 macros/p3_assert_pin_port_contract.py
"""
import json
import os
import re
import sys

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'out')
VAL = os.path.join(ROOT, 'v2_validation')
NETLIST = os.path.join(VAL, 'synth_netlist.v')

# tag -> (LEF/GDS cell name, expected number of components WITHOUT a pin)
#
# A is the only macro with an un-pinned component: netC, the neighbour wire
# that must stay electrically separate from the via-joined net.
EXPECTED = {
    'A':  ('research_via1',     1),
    'B':  ('research_via2',     0),
    'C1': ('research_branch',   0),
    'C3': ('research_near',     None),   # geometry-only; see C7
    'C4': ('research_cross',    None),
    'D':  ('research_dense',    None),
    'E':  ('research_fiducial', None),
}

ELECTRICAL = ['A', 'B', 'C1']

PI_LAYERS = {'M1': (68, 20), 'M2': (69, 20), 'M3': (70, 20), 'M4': (71, 20)}
VIA_LAYERS = {'Via1': (68, 44), 'Via2': (69, 44), 'Via3': (70, 44)}
LEF2INT = {'met1': 'M1', 'met2': 'M2', 'met3': 'M3', 'met4': 'M4'}


# ----------------------------------------------------------------- LEF parse
def parse_lef(path):
    """Return {macro, origin, size, pins:[{name, direction, ports:[[geom]]}]}.

    A PIN block is delimited by `PIN <name>` … `END <name>`; inside it, each
    `PORT` … `END` block groups LAYER/RECT pairs. Keeping the PORT grouping is
    the whole point — a flat list of rects could not distinguish one PORT with
    four geometries (strong) from four PORTs (weak).
    """
    txt = open(path, encoding='utf-8').read()
    macro = re.search(r'^\s*MACRO\s+(\S+)', txt, re.M).group(1)
    o = re.search(r'^\s*ORIGIN\s+(-?[\d.]+)\s+(-?[\d.]+)\s*;', txt, re.M)
    origin = (float(o.group(1)), float(o.group(2))) if o else (0.0, 0.0)
    sz = re.search(r'^\s*SIZE\s+([\d.]+)\s+BY\s+([\d.]+)\s*;', txt, re.M)
    size = (float(sz.group(1)), float(sz.group(2)))

    pins = []
    for pm in re.finditer(r'^\s*PIN\s+(\S+)\s*$(.*?)^\s*END\s+\1\s*$',
                          txt, re.S | re.M):
        name, body = pm.group(1), pm.group(2)
        d = re.search(r'DIRECTION\s+(\w+)', body)
        ports = []
        for ptm in re.finditer(r'^\s*PORT\s*$(.*?)^\s*END\s*$', body,
                               re.S | re.M):
            geoms, cur = [], None
            for line in ptm.group(1).splitlines():
                s = line.strip()
                lm = re.match(r'LAYER\s+(\S+)\s*;', s)
                if lm:
                    cur = lm.group(1)
                    continue
                rm = re.match(r'RECT\s+(-?[\d.]+)\s+(-?[\d.]+)\s+'
                              r'(-?[\d.]+)\s+(-?[\d.]+)\s*;', s)
                if rm and cur:
                    geoms.append((cur, tuple(float(rm.group(i))
                                             for i in range(1, 5))))
            ports.append(geoms)
        pins.append({'name': name,
                     'direction': d.group(1) if d else None,
                     'ports': ports})
    return {'macro': macro, 'origin': origin, 'size': size, 'pins': pins}


# ------------------------------------------------------------- Verilog parse
def parse_verilog_ports(path):
    """Return {module: [(direction, port_name), ...]}.

    All seven modules are ANSI-style and body-less, so a single regex over
    `module <name> ( ... );` is enough. Body-less matters: a module with a body
    would be inlined by write_verilog and never reach the netlist.
    """
    txt = open(path, encoding='utf-8').read()
    txt = re.sub(r'//[^\n]*', '', txt)
    txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.S)
    out = {}
    for m in re.finditer(r'\bmodule\s+(\w+)\s*\(([^;]*?)\)\s*;', txt, re.S):
        name, body = m.group(1), m.group(2)
        ports = []
        for pm in re.finditer(r'\b(inout|input|output)\b\s+(?:wire\s+|reg\s+)?'
                              r'(\w+)', body):
            ports.append((pm.group(1), pm.group(2)))
        out[name] = ports
    return out


# ------------------------------------------------------------- GDS components
def build_components(layout, top, dbu):
    """Union-find over drawn metal; cross-layer edges only through real via
    cuts covered by both adjacent metals.

    Returns (find, shapes_by_layer, vias_by_layer) where each shape entry is
    (left, bottom, right, top) in dbu and find() maps a (layer, index) key to a
    component root.
    """
    shapes, vias = {}, {}
    for m, (ln, dt) in PI_LAYERS.items():
        li = layout.find_layer(ln, dt)
        lst = []
        if li is not None:
            for sh in top.shapes(li).each():
                b = sh.box if sh.is_box() else sh.polygon.bbox()
                lst.append((b.left, b.bottom, b.right, b.top))
        shapes[m] = lst
    for v, (ln, dt) in VIA_LAYERS.items():
        li = layout.find_layer(ln, dt)
        lst = []
        if li is not None:
            for sh in top.shapes(li).each():
                b = sh.box if sh.is_box() else sh.polygon.bbox()
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

    def overlaps(a, b):
        return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    def contains(outer, inner):
        return (outer[0] <= inner[0] and outer[1] <= inner[1]
                and outer[2] >= inner[2] and outer[3] >= inner[3])

    for m in PI_LAYERS:
        for i in range(len(shapes[m])):
            find((m, i))
            for j in range(i + 1, len(shapes[m])):
                if overlaps(shapes[m][i], shapes[m][j]):
                    union((m, i), (m, j))

    via_pairs = {'Via1': ('M1', 'M2'), 'Via2': ('M2', 'M3'), 'Via3': ('M3', 'M4')}
    for v, (lo, hi) in via_pairs.items():
        for cut in vias.get(v, []):
            lo_hits = [i for i, s in enumerate(shapes[lo]) if contains(s, cut)]
            hi_hits = [i for i, s in enumerate(shapes[hi]) if contains(s, cut)]
            for a in lo_hits:
                for b in hi_hits:
                    union((lo, a), (hi, b))

    return find, shapes, vias


def roots_containing(find, shapes, layer, rect):
    """Component roots of shapes on `layer` that fully cover `rect`.

    A pin rect is a landing pad; it must sit ON metal, so full coverage is the
    right relation. `roots_in_rect` (mere intersection) would also match a
    metal shape that only grazes a corner, which is not a legal landing.
    """
    keys = []
    for i, s in enumerate(shapes[layer]):
        if (s[0] <= rect[0] and s[1] <= rect[1]
                and s[2] >= rect[2] and s[3] >= rect[3]):
            keys.append((layer, i))
    return {find(k) for k in keys}


# --------------------------------------------------------- synthesized netlist
def parse_synth_instances(path, cells):
    txt = open(path, encoding='utf-8', errors='replace').read()
    found = {}
    for cell in cells:
        for m in re.finditer(r'\b%s\s+(\w+)\s*\((.*?)\)\s*;'
                             % re.escape(cell), txt, re.S):
            inst, body = m.group(1), m.group(2)
            ports = dict((k, v.strip()) for k, v in
                         re.findall(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', body))
            found[inst] = {'cell': cell, 'ports': ports}
    return found


# --------------------------------------------------------------------- checks
def main():
    problems, checks, rows = [], [], []

    vports = parse_verilog_ports(os.path.join(ROOT, 'src', 'research_macros.v'))

    print('%-4s %-20s %-6s %-6s %-8s %-8s %s'
          % ('tag', 'cell', 'pins', 'vs', 'ports', 'comps', 'verdict'))
    print('-' * 74)

    for tag in sorted(EXPECTED):
        cell, exp_unpinned = EXPECTED[tag]
        lef = parse_lef(os.path.join(OUT, 'struct_%s.lef' % tag))
        gds = os.path.join(OUT, 'struct_%s.gds' % tag)

        L = pya.Layout()
        L.read(gds)
        top = L.top_cell()
        dbu = L.dbu
        find, shapes, vias = build_components(L, top, dbu)

        # all component roots, and which carry a via cut
        all_shapes = [k for layer in PI_LAYERS for k in
                      [(layer, i) for i in range(len(shapes[layer]))]]
        roots = {}
        for k in all_shapes:
            roots.setdefault(find(k), []).append(k)
        via_roots = set()
        for v, (lo, hi) in (('Via1', ('M1', 'M2')), ('Via2', ('M2', 'M3')),
                            ('Via3', ('M3', 'M4'))):
            for cut in vias.get(v, []):
                for i, s in enumerate(shapes[lo]):
                    if (s[0] <= cut[0] and s[1] <= cut[1]
                            and s[2] >= cut[2] and s[3] >= cut[3]):
                        via_roots.add(find((lo, i)))
                for i, s in enumerate(shapes[hi]):
                    if (s[0] <= cut[0] and s[1] <= cut[1]
                            and s[2] >= cut[2] and s[3] >= cut[3]):
                        via_roots.add(find((hi, i)))

        # ---- C1/C2: names and counts against the Verilog view
        vp = vports.get(cell)
        if vp is None:
            problems.append('C1 %s: module %s missing from research_macros.v'
                            % (tag, cell))
            vp = []
        lef_names = [p['name'] for p in lef['pins']]
        ver_names = [n for _, n in vp]

        if lef_names != ver_names:
            problems.append('C1 %s: LEF PIN names %s != Verilog port names %s'
                            % (tag, lef_names, ver_names))
        if len(lef['pins']) != len(vp):
            problems.append('C2 %s: %d LEF PIN(s) != %d Verilog port(s)'
                            % (tag, len(lef['pins']), len(vp)))

        # ---- C3/C4/C5/C6/C8: per-PIN physical contract
        pin_roots = set()
        per_pin = []
        for p in lef['pins']:
            n_ports = len(p['ports'])
            if n_ports != 1:
                problems.append('C3 %s.%s: %d PORT block(s); alpha-prime requires '
                                'exactly 1 (multiple PORTs are only weak connectivity)'
                                % (tag, p['name'], n_ports))
            proots, rows_g = set(), []
            for geoms in p['ports']:
                for lay, (x0, y0, x1, y1) in geoms:
                    mname = LEF2INT.get(lay)
                    if mname is None:
                        problems.append('C3 %s.%s: unknown LEF layer %s'
                                        % (tag, p['name'], lay))
                        continue
                    rect = (int(round((x0 + lef['origin'][0]) / dbu)),
                            int(round((y0 + lef['origin'][1]) / dbu)),
                            int(round((x1 + lef['origin'][0]) / dbu)),
                            int(round((y1 + lef['origin'][1]) / dbu)))
                    rs = roots_containing(find, shapes, mname, rect)
                    if not rs:
                        problems.append('C4 %s.%s: %s geometry at (%.3f, %.3f) is '
                                        'not inside any drawn metal shape'
                                        % (tag, p['name'], lay, x0, y0))
                    proots |= rs
                    rows_g.append({'layer': lay, 'rect': [x0, y0, x1, y1],
                                   'n_roots': len(rs)})
            if len(proots) != 1:
                problems.append('C4 %s.%s: geometries span %d distinct GDS '
                                'components; a single PIN must be one node'
                                % (tag, p['name'], len(proots)))
            elif proots and next(iter(proots)) not in via_roots:
                problems.append('C5 %s.%s: the component carrying this PIN has no '
                                'via cut — it is not a cross-layer node'
                                % (tag, p['name']))
            pin_roots |= proots
            per_pin.append({'name': p['name'], 'n_ports': n_ports,
                            'geometries': rows_g})

        # ---- C6 direction
        for p, (vd, vn) in zip(lef['pins'], vp):
            if p['direction'] != vd.upper():
                problems.append('C6 %s.%s: LEF DIRECTION %s != Verilog %s'
                                % (tag, p['name'], p['direction'], vd))

        # ---- C7 zero-port macros must have zero PINs
        if tag not in ELECTRICAL and lef['pins']:
            problems.append('C7 %s: geometry-only macro declares %d PIN(s)'
                            % (tag, len(lef['pins'])))

        # ---- C8 un-pinned component count
        unpinned = set(roots) - pin_roots
        if exp_unpinned is not None and len(unpinned) != exp_unpinned:
            problems.append('C8 %s: %d component(s) carry no PIN, expected %d'
                            % (tag, len(unpinned), exp_unpinned))
        # the un-pinned ones must be via-free single-layer neighbours
        for r in unpinned:
            if r in via_roots:
                problems.append('C8 %s: an un-pinned component contains a via cut — '
                                'a cross-layer node is left electrically floating'
                                % tag)

        verdict = 'OK'
        rows.append({'tag': tag, 'cell': cell, 'n_pins': len(lef['pins']),
                     'n_verilog_ports': len(vp), 'n_components': len(roots),
                     'n_unpinned': len(unpinned), 'pins': per_pin})
        print('%-4s %-20s %-6d %-6d %-8d %-8d %s'
              % (tag, cell, len(lef['pins']), len(vp), len(roots), len(unpinned),
                 verdict))

    # ---- C9/C10/C11: the synthesized netlist
    synth_status = 'SKIP'
    synth_rows = []
    if not os.path.exists(NETLIST):
        problems.append('C9–C11 NOT RUN: %s missing — run '
                        'macros/p3_synth_netlist_check.py first' % NETLIST)
    else:
        synth_status = 'RUN'
        cells = {c for c, _ in EXPECTED.values()}
        insts = parse_synth_instances(NETLIST, cells)
        inst_map = {'u_rs_via1': 'A', 'u_rs_via2': 'B', 'u_rs_branch': 'C1',
                    'u_rs_near': 'C3', 'u_rs_cross': 'C4',
                    'u_rs_dense': 'D', 'u_rs_fiducial': 'E'}
        net_of = {}
        for inst, tag in inst_map.items():
            cell = EXPECTED[tag][0]
            got = insts.get(inst)
            if got is None:
                problems.append('C9 %s (%s): instance missing from the '
                                'synthesized netlist' % (inst, cell))
                continue
            lef_names = [p['name'] for p in
                         parse_lef(os.path.join(OUT, 'struct_%s.lef' % tag))['pins']]
            got_names = sorted(got['ports'])
            if got_names != sorted(lef_names):
                problems.append('C9 %s: netlist ports %s != LEF PINs %s'
                                % (inst, got_names, sorted(lef_names)))
            for pname, pnet in got['ports'].items():
                # a constant or empty connection is not a net
                if not pnet or pnet in ('1\'b0', '1\'b1', "1'b0", "1'b1") \
                        or re.fullmatch(r"\d+'[bdh][0-9a-fA-FxXzZ_]+", pnet):
                    problems.append('C10 %s.%s: port is tied to %r, not a net'
                                    % (inst, pname, pnet))
                elif tag in ELECTRICAL:
                    net_of[tag] = pnet
            synth_rows.append({'instance': inst, 'tag': tag, 'cell': cell,
                               'ports': got['ports']})

        if len(set(net_of.values())) > 1:
            problems.append('C11: A/B/C1 land on different nets %s; they were all '
                            'tied to pwm_out in project.v' % net_of)

    # ------------------------------------------------------------------ output
    os.makedirs(VAL, exist_ok=True)
    summary = {
        'interface': 'alpha-prime: one PIN, one PORT, several cross-layer '
                     'geometries in the same GDS component',
        'all_pass': len(problems) == 0,
        'synth_status': synth_status,
        'problems': problems,
        'macros': rows,
        'synth': synth_rows,
        'scope': 'DESIGN-STAGE five-view contract. Covers views 1-4 '
                 '(GDS component, LEF PIN, Verilog port, synthesized net). '
                 'View 5 (final GDS) requires the official CI and is NOT '
                 'verified here. Nothing in this file demonstrates pin access, '
                 'routing, or LVS.',
        'checks': [
            'C1 LEF PIN name == Verilog port name (character-exact)',
            'C2 LEF PIN count == Verilog port count',
            'C3 exactly one PORT per PIN (strong connectivity)',
            'C4 all PORT geometries of a PIN in one GDS component',
            'C5 that component contains at least one via cut',
            'C6 LEF DIRECTION matches Verilog direction',
            'C7 geometry-only macros declare zero PINs',
            'C8 un-pinned component count matches physics; none holds a via',
            'C9 synthesized instance port names == LEF PIN names',
            'C10 every port connects to exactly one non-constant net',
            'C11 A/B/C1 land on the same net',
        ],
    }
    json.dump(summary, open(os.path.join(VAL, 'P4_PIN_PORT_CONTRACT.json'), 'w',
                            encoding='utf-8'), indent=1, ensure_ascii=False)

    md = ['# 五视图链断言（α′ 接口）', '',
          '自动生成：`macros/p3_assert_pin_port_contract.py`  ',
          '接口：**一个 PIN、一个 PORT、PORT 内含多个跨层几何**（强连接）', '',
          '| ID | 宏 | LEF PIN | Verilog 端口 | GDS 分量 | 无 PIN 分量 |',
          '|---|---|---|---|---|---|']
    for r in rows:
        md.append('| %s | `%s` | %d | %d | %d | %d |'
                  % (r['tag'], r['cell'], r['n_pins'], r['n_verilog_ports'],
                     r['n_components'], r['n_unpinned']))
    md += ['', '## 检查项', '']
    for c in summary['checks']:
        md.append('- %s' % c)
    md += ['', '## 综合网表视图', '']
    if synth_status == 'SKIP':
        md.append('**未运行** —— 缺少 `v2_validation/synth_netlist.v`。')
        md.append('这不是通过，是没跑。先运行 `macros/p3_synth_netlist_check.py`。')
    else:
        md += ['| 实例 | 宏 | 端口连接 |', '|---|---|---|']
        for r in synth_rows:
            conn = ', '.join('%s=%s' % (k, v) for k, v in r['ports'].items()) or '—'
            md.append('| `%s` | `%s` | %s |' % (r['instance'], r['cell'], conn))
    md += ['', '## 结论', '']
    if problems:
        md.append('**FAIL** — %d 个问题：' % len(problems))
        for p in problems:
            md.append('- %s' % p)
    else:
        md.append('**PASS** — 五视图链的前四视图逐宏一致。')
        md.append('')
        md.append('> 第五视图（最终 GDS）需要官方 CI，本地未验证。')
        md.append('> 本断言**不**证明 pin access、布线或 LVS 通过。')
    open(os.path.join(VAL, 'P4_PIN_PORT_CONTRACT.md'), 'w',
         encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')

    print()
    print('synth netlist view:', synth_status)
    if problems:
        print('FAIL — %d problem(s):' % len(problems))
        for p in problems:
            print('  !', p)
        return 1
    print('PASS — pin/port contract holds for all seven structures')
    print('written v2_validation/P4_PIN_PORT_CONTRACT.{json,md}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
