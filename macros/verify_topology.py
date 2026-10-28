#!/usr/bin/env python3
"""verify_topology.py — 验证每个研究结构的电气拓扑是否与设计意图一致。

DRC 通过只说明几何合法；本脚本验证**拓扑语义**：
  A  : M1 与 M2 必须通过 Via1 真正连成一个分量
  B  : M2 与 M3 必须通过 Via2 真正连通
  C1 : 单 net 三分支 -> 合并后应为 1 个连通分量，且含 3 个 via
  C3 : 平行线对必须两两分离（4 对 = 8 个分量）
  C4 : M1 与 M2 交叉但无 via -> 两层的分量必须分离，且 via1 计数 = 0
  D  : 纯几何，无 via；检查每档宽度实测值
  E  : M1 与 M2 图样必须在同一 XY 位置（配准用途）

关键方法：**跨层连通必须经真实 via cut 建立**，不能对平面投影做 2D 并集。
本脚本用一个显式的 (layer, shape) 图：同层内相交即连边；跨层只在
"该位置存在对应 via cut 且 cut 被上下两层金属同时覆盖" 时连边。
"""
import json
import os
import sys

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
DBU = 0.001
L = {'M1': (68, 20), 'Via1': (68, 44), 'M2': (69, 20),
     'Via2': (69, 44), 'M3': (70, 20), 'Via3': (70, 44), 'M4': (71, 20)}


def load(path):
    ly = pya.Layout()
    ly.read(path)
    top = ly.top_cell()
    shapes = {k: [] for k in L}
    for k, (ln, dt) in L.items():
        li = ly.find_layer(ln, dt)
        if li is None:
            continue
        it = top.begin_shapes_rec(li)
        while not it.at_end():
            s = it.shape(); t = it.trans()
            if s.is_box():
                b = s.box.transformed(t)
                shapes[k].append((b.left, b.bottom, b.right, b.top))
            elif s.is_polygon():
                b = s.polygon.transformed(t).bbox()
                shapes[k].append((b.left, b.bottom, b.right, b.top))
            elif s.is_path():
                b = s.path.transformed(t).simple_polygon().bbox()
                shapes[k].append((b.left, b.bottom, b.right, b.top))
            it.next()
    return shapes


def overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def contains(outer, inner):
    return (outer[0] <= inner[0] and outer[1] <= inner[1]
            and outer[2] >= inner[2] and outer[3] >= inner[3])


class UF:
    def __init__(self):
        self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra
    def groups(self):
        g = {}
        for x in self.p:
            g.setdefault(self.find(x), []).append(x)
        return g


def build_graph(shapes):
    """Nodes: (layer, index) for metals only. Via cuts act as edges."""
    uf = UF()
    metals = ['M1', 'M2', 'M3', 'M4']
    for m in metals:
        for i in range(len(shapes[m])):
            uf.find((m, i))
        # same-layer connectivity
        for i in range(len(shapes[m])):
            for j in range(i + 1, len(shapes[m])):
                if overlap(shapes[m][i], shapes[m][j]):
                    uf.union((m, i), (m, j))
    # cross-layer: a via of type V connects layer_lo and layer_hi when the cut
    # is covered by a shape in BOTH layers
    via_pairs = {'Via1': ('M1', 'M2'), 'Via2': ('M2', 'M3'), 'Via3': ('M3', 'M4')}
    for vkind, (lo, hi) in via_pairs.items():
        for cut in shapes[vkind]:
            lo_hits = [i for i, s in enumerate(shapes[lo]) if contains(s, cut)]
            hi_hits = [i for i, s in enumerate(shapes[hi]) if contains(s, cut)]
            for a in lo_hits:
                for b in hi_hits:
                    uf.union((lo, a), (hi, b))
    return uf


def comps_of(uf):
    return [sorted(g) for g in uf.groups().values()]


def main():
    checks = []
    detail = {}

    # ---- A
    s = load(os.path.join(OUT, 'struct_A.gds'))
    uf = build_graph(s)
    comps = comps_of(uf)
    a_ok = (len(comps) == 2 and len(s['Via1']) == 1)     # netA + neighbour
    checks.append(('A: M1-Via1-M2 forms one component, neighbour separate',
                   a_ok, 'comps=%d via1=%d' % (len(comps), len(s['Via1']))))
    detail['A'] = {'components': comps, 'via1': len(s['Via1'])}

    # ---- B
    s = load(os.path.join(OUT, 'struct_B.gds'))
    uf = build_graph(s)
    comps = comps_of(uf)
    b_ok = (len(comps) == 1 and len(s['Via2']) == 1)
    checks.append(('B: M2-Via2-M3 forms one component',
                   b_ok, 'comps=%d via2=%d' % (len(comps), len(s['Via2']))))
    detail['B'] = {'components': comps, 'via2': len(s['Via2'])}

    # ---- C1
    s = load(os.path.join(OUT, 'struct_C1.gds'))
    uf = build_graph(s)
    comps = comps_of(uf)
    n_v1 = len(s['Via1'])
    c1_ok = (len(comps) == 1 and n_v1 == 3)
    checks.append(('C1: single net with 3 via branches -> 1 component',
                   c1_ok, 'comps=%d via1=%d' % (len(comps), n_v1)))
    detail['C1'] = {'components': comps, 'via1': n_v1}

    # ---- C3
    s = load(os.path.join(OUT, 'struct_C3.gds'))
    uf = build_graph(s)
    comps = comps_of(uf)
    c3_ok = (len(comps) == len(s['M1']))     # every M1 bar isolated
    checks.append(('C3: all parallel wires electrically separate',
                   c3_ok, 'comps=%d m1=%d' % (len(comps), len(s['M1']))))
    detail['C3'] = {'components': comps, 'm1_shapes': len(s['M1'])}

    # ---- C4
    s = load(os.path.join(OUT, 'struct_C4.gds'))
    uf = build_graph(s)
    comps = comps_of(uf)
    c4_ok = (len(comps) == 2 and len(s['Via1']) == 0)
    checks.append(('C4: M1/M2 cross in projection but NOT connected (no via)',
                   c4_ok, 'comps=%d via1=%d' % (len(comps), len(s['Via1']))))
    detail['C4'] = {'components': comps, 'via1': len(s['Via1'])}

    # ---- D
    s = load(os.path.join(OUT, 'struct_D.gds'))
    uf = build_graph(s)
    comps = comps_of(uf)
    # NOTE: bbox width is not the drawn line width. Each wire is a box of
    # length (x1-x0 + w) and height w, so the *height* is the true width for a
    # horizontal wire. Report heights, and also the unique heights (= widths).
    widths_m1 = sorted({round((b[3] - b[1]) * DBU, 3) for b in s['M1']})
    widths_m2 = sorted({round((b[3] - b[1]) * DBU, 3) for b in s['M2']})
    widths_m3 = sorted({round((b[3] - b[1]) * DBU, 3) for b in s['M3']})
    expect_m1 = [0.14, 0.20, 0.30, 0.50, 1.00]
    d_ok = (len(s['Via1']) == 0 and len(s['M1']) == 5 and len(s['M3']) == 3
            and all(abs(a - b) < 0.002 for a, b in zip(widths_m1, expect_m1)))
    checks.append(('D: width ladder matches designed widths, no vias',
                   d_ok, 'm1 widths=%s (want %s)' % (widths_m1, expect_m1)))
    detail['D'] = {'m1': len(s['M1']), 'm2': len(s['M2']), 'm3': len(s['M3']),
                   'm1_widths_um': widths_m1, 'm2_widths_um': widths_m2,
                   'm3_widths_um': widths_m3,
                   'expected_m1': expect_m1}

    # ---- E
    s = load(os.path.join(OUT, 'struct_E.gds'))
    m1 = sorted(s['M1']); m2 = sorted(s['M2'])
    e_ok = (m1 == m2 and len(m1) == 3)
    checks.append(('E: M1 and M2 fiducial patterns at identical XY',
                   e_ok, 'm1_shapes=%d m2_shapes=%d identical=%s'
                   % (len(m1), len(m2), m1 == m2)))
    detail['E'] = {'m1': m1, 'm2': m2, 'identical': m1 == m2}

    print('%-62s %-5s %s' % ('check', 'PASS', 'detail'))
    print('-' * 100)
    for name, ok, d in checks:
        print('%-62s %-5s %s' % (name, 'YES' if ok else 'NO', d))
    allok = all(c[1] for c in checks)
    print()
    print('TOPOLOGY VERIFY:', 'PASS' if allok else 'FAIL')

    json.dump({'checks': [{'name': n, 'pass': o, 'detail': d} for n, o, d in checks],
               'detail': detail, 'all_pass': allok},
              open(os.path.join(OUT, 'topology_verify.json'), 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False, default=str)
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
