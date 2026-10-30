#!/usr/bin/env python3
"""gen_v2_macros.py — 生成 V2 研究结构宏（A/B/C/D/E）。

规则来源：v2_spec/sky130_rules_measured.md（从真实 PDK 提取）
所有几何参数都是实测规则值，不是虚构。

生成的结构：
  A  research_via1  : M1 -> Via1 -> M2 信号连接（已验证）
  B  research_via2  : M2 -> Via2 -> M3 信号连接
  C1 research_branch: 单 Net 多分支（3 端点）
  C3 research_near  : 近邻不同 Net 平行对（间距阶梯）
  C4 research_cross : 跨层投影交叉但无 via（负样本）
  D  research_dense : 线宽/间距阶梯阵列
  E  research_fiducial : 多层配准标记

输出：macros/out/v2_structures.gds（单文件多 cell）+ 每结构 LEF + manifest

--------------------------------------------------------------------------------
VIA ENCLOSURE —— 2026-10-29 修订（第三轮 CI 的 107 个 Magic DRC 错误的根因）
--------------------------------------------------------------------------------
Sky130 Magic DRC deck（sky130.tech，blob 2fdf72416c5f5384415269436878940b27112409）
中的原文是：

    surround v1/m1  *m1,rm1  30 directional  "Metal1 overlap of Via1 < %d ..."
    surround v1/m2  *m2,rm2  30 directional  "Metal2 overlap of Via1 < %d ..."
    surround v2/m2  *m2,rm2  45 directional  "Metal2 overlap of via2 < %d ..."
    surround v2/m3  *m3,rm3  25 absence_illegal "Metal3 overlap of via2 < %d ..."

该 deck 以 5 nm 为单位，故打印值为 6/6/9/5，真实阈值是
    via1 -> met1 = 0.085 um   （via.5a - via.4a）
    via1 -> met2 = 0.085 um   （met2.5 - met2.4）
    via2 -> met2 = 0.085 um   （via2.4a - via2.4）
    via2 -> met3 = 0.065 um   （met3.4，absence_illegal，四边都需满足）

旧版此处写的是 v1_m1=0.055 / v1_m2=0.055 / v2_m2=0.040 —— 三个值都低于规则。
对 0.150 um 的 Via1，对称方形 pad 至少需要 0.150 + 2*0.085 = 0.320 um；
对 0.200 um 的 Via2 落到 M2 上，至少需要 0.200 + 2*0.085 = 0.370 um。

这里取 0.095 的包围（比 0.085 多 10 nm 余量）：
    Via1 pad = 0.150 + 2*0.095 = 0.340 um      （met1 与 met2 两侧同尺寸）
    Via2 pad = 0.200 + 2*0.095 = 0.390 um      （met2 与 met3 两侧同尺寸）
met3.4 只要求 0.065，本可以只给 0.330 的 pad；选择 0.390 是为了让两个 landing
都是**对称正方形**、四边等深，既留 30 nm 余量，也使修复不依赖任何
"directional 到底怎么解释"的争议 —— 四边等深时按哪种语义都通过。
该值与 OpenROAD 自己在最终 GDS 里为 1018 个 via1 使用的 0.320 pad
（正好 0.085 包围、DRC 干净）保持同一量级，并留出加工余量。

**不变的量**（科研真值的前提）：via cut 尺寸仍是 0.150 / 0.200，
所有 via 的**中心坐标与数量**完全未动 —— 只有 landing pad 变大。
"""
import json
import os
import sys

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)

DBU = 0.001
L = {
    'M1': (68, 20), 'Via1': (68, 44),
    'M2': (69, 20), 'Via2': (69, 44),
    'M3': (70, 20),
    'M4': (71, 20),
    # prBoundary. Tiny Tapeout's macro guide: "Your macro GDS must also include
    # a PR boundary rectangle on a dedicated layer (prBoundary). ... it tells the
    # tools the legal footprint of your macro ... It is not decorative art; the
    # LEF SIZE should match this rectangle." For SKY130 the layer is 235/4
    # (the guide's own crossstitching01 example uses exactly this).
    'prB': (235, 4),
}
# measured rules — see module docstring for the enclosure revision
ENCL = 0.095          # >= 0.085 required for all three 0.085 rules, +10 nm margin
ENCL_M3 = 0.095       # met3.4 only needs 0.065; keep the pad square and add margin
R = dict(
    m1_w=0.14, m1_s=0.14,
    m2_w=0.14, m2_s=0.14,
    m3_w=0.30, m3_s=0.30,
    v1=0.15, v1_m1=ENCL, v1_m2=ENCL,          # via1 -> m1/m2 : rule 0.085
    v2=0.20, v2_m2=ENCL, v2_m3=ENCL_M3,       # via2 -> m2 : 0.085 ; via2 -> m3 : 0.065
    via_space=0.20,
)


def um(v):
    return int(round(v * 1000))


class Builder:
    def __init__(self, name):
        self.ly = pya.Layout()
        self.ly.dbu = DBU
        self.top = self.ly.create_cell(name)
        self.li = {k: self.ly.layer(*v) for k, v in L.items()}
        self.net_meta = []          # (net_name, layer, bbox_um, kind)

    def box(self, layer, x0, y0, x1, y1):
        self.top.shapes(self.li[layer]).insert(
            pya.Box(um(x0), um(y0), um(x1), um(y1)))

    def wire(self, layer, x0, y0, x1, y1, w):
        self.box(layer, x0 - w / 2, y0 - w / 2, x1 + w / 2, y1 + w / 2)

    def via(self, kind, cx, cy):
        """kind in ('Via1','Via2'); emits cut + both metal landings."""
        if kind == 'Via1':
            cut, m_lo, m_hi = R['v1'], 'M1', 'M2'
            e_lo, e_hi = R['v1_m1'], R['v1_m2']
        else:
            cut, m_lo, m_hi = R['v2'], 'M2', 'M3'
            e_lo, e_hi = R['v2_m2'], R['v2_m3']
        self.box(kind, cx - cut / 2, cy - cut / 2, cx + cut / 2, cy + cut / 2)
        for m, e in ((m_lo, e_lo), (m_hi, e_hi)):
            self.box(m, cx - cut / 2 - e, cy - cut / 2 - e,
                     cx + cut / 2 + e, cy + cut / 2 + e)

    def save(self):
        return self


def build_A():
    """M1 -> Via1 -> M2, single net, with a legal neighbour."""
    b = Builder('research_via1')
    y = 2.0
    b.wire('M1', 1.0, y, 6.0, y, R['m1_w'])
    b.wire('M1', 6.0, y, 6.0, 4.0, R['m1_w'])
    b.via('Via1', 6.0, 4.0)
    b.wire('M2', 6.0, 4.0, 9.0, 4.0, R['m2_w'])
    # neighbour net, 0.28 apart (> 0.14)
    b.wire('M1', 1.0, 6.8, 9.0, 6.8, R['m1_w'])
    return b


def build_B():
    """M2 -> Via2 -> M3, single net."""
    b = Builder('research_via2')
    y = 2.0
    b.wire('M2', 1.0, y, 6.0, y, R['m2_w'])
    b.wire('M2', 6.0, y, 6.0, 5.0, R['m2_w'])
    b.via('Via2', 6.0, 5.0)
    b.wire('M3', 6.0, 5.0, 11.0, 5.0, R['m3_w'])
    return b


def build_C1():
    """Single net with 3 branches through vias."""
    b = Builder('research_branch')
    cx, cy = 6.0, 5.0
    # trunk
    b.wire('M1', 1.0, cy, 11.0, cy, R['m1_w'])
    # three vias up to M2, each ending in a short M2 stub
    for i, x in enumerate((2.0, 6.0, 10.0)):
        b.via('Via1', x, cy)
        b.wire('M2', x, cy, x, cy + 2.0 + i * 0.5, R['m2_w'])
    return b


def build_C3():
    """Parallel wires at legal gap ladder: 0.14 / 0.20 / 0.28 / 0.50."""
    b = Builder('research_near')
    gaps = [0.14, 0.20, 0.28, 0.50]
    y = 1.0
    for g in gaps:
        b.wire('M1', 1.0, y, 11.0, y, R['m1_w'])          # net P
        y2 = y + R['m1_w'] + g
        b.wire('M1', 1.0, y2, 11.0, y2, R['m1_w'])        # net Q
        y = y2 + R['m1_w'] + 2.0                          # spacing between pairs
    return b


def build_C4():
    """M1 and M2 cross in projection, NO via -> not connected."""
    b = Builder('research_cross')
    b.wire('M1', 1.0, 5.0, 11.0, 5.0, R['m1_w'])    # horizontal M1
    b.wire('M2', 6.0, 1.0, 6.0, 9.0, R['m2_w'])     # vertical M2 crosses at (6,5)
    # deliberately NO via at (6,5)
    return b


def build_D():
    """Width / pitch ladder on M1, M2, M3."""
    b = Builder('research_dense')
    widths = [0.14, 0.20, 0.30, 0.50, 1.00]
    y = 1.0
    for w in widths:
        b.wire('M1', 1.0, y, 11.0, y, w)
        y += w + 1.0
    y = 1.0
    for w in widths:
        b.wire('M2', 13.0, y, 23.0, y, w)
        y += w + 1.0
    y = 1.0
    for w in [0.30, 0.50, 1.00]:
        b.wire('M3', 25.0, y, 35.0, y, w)
        y += w + 1.0
    return b


def build_E():
    """Multi-layer fiducial: identical cross pattern on M1 and M2.

    NON_ELECTRICAL. The same geometry is drawn on M1 and M2 at the same XY so a
    delayered SEM pair can be aligned by cross-correlation.
    """
    b = Builder('research_fiducial')
    arm, wid, c = 2.0, 0.5, 5.0
    for layer in ('M1', 'M2'):
        b.box(layer, c - arm, c - wid / 2, c + arm, c + wid / 2)   # horizontal
        b.box(layer, c - wid / 2, c - arm, c + wid / 2, c + arm)   # vertical
        b.box(layer, c - arm, c - arm, c - arm + 0.6, c - arm + 0.6)  # corner key
    return b


BUILDERS = [('A', build_A), ('B', build_B), ('C1', build_C1),
            ('C3', build_C3), ('C4', build_C4), ('D', build_D), ('E', build_E)]


# Structures whose cell geometry is re-based so its bbox starts at (0,0).
# Only the three macros that carry an electrical PIN need this: their LEF PIN
# rectangles are read by both OpenROAD (place + ORIGIN + RECT) and Magic
# (place + RECT - ORIGIN), and the two only agree when ORIGIN is zero.  The
# four geometry-only macros have no PIN, never enter the netlist, and keep the
# round-4 coordinates byte-for-byte, so they are deliberately NOT normalised.
NORMALISE = {'A', 'B', 'C1'}


def main():
    # one layout holding every structure as its own cell
    master = pya.Layout()
    master.dbu = DBU
    meta = {}
    for tag, fn in BUILDERS:
        b = fn()
        # ---- prBoundary -------------------------------------------------
        # Required by the Tiny Tapeout macro flow. Emitted AFTER all geometry
        # so it covers the full metal extent. Without it the placer has no
        # legal footprint for the macro and the build fails.
        metal_bb = b.top.bbox()
        b.top.shapes(b.li['prB']).insert(metal_bb)
        bb = b.top.bbox()           # now equal to the prBoundary

        # ---- re-base the cell so its bbox starts at (0,0) ---------------
        # The offset removed here is handed to the placer through
        # `local_origin_um`, which p3_placement_plan.py adds back to the
        # instance placement, so the macro does not move on the die.
        origin_um = (0.0, 0.0)
        if tag in NORMALISE:
            origin_um = (round(bb.left * DBU, 3), round(bb.bottom * DBU, 3))
            if bb.left or bb.bottom:
                b.top.transform(
                    pya.ICplxTrans(1.0, 0, False, -bb.left, -bb.bottom))
                bb = b.top.bbox()
            assert bb.left == 0 and bb.bottom == 0, \
                '%s: normalisation failed, bbox starts at %d,%d' % (tag, bb.left, bb.bottom)

        cell = master.create_cell(b.top.name)
        cell.copy_tree(b.top)
        meta[tag] = {
            'cell': b.top.name,
            'size_um': [round(bb.width() * DBU, 3), round(bb.height() * DBU, 3)],
            'bbox_um': [round(bb.left * DBU, 3), round(bb.bottom * DBU, 3),
                        round(bb.right * DBU, 3), round(bb.top * DBU, 3)],
            'prboundary_um': [round(metal_bb.left * DBU, 3),
                              round(metal_bb.bottom * DBU, 3),
                              round(metal_bb.right * DBU, 3),
                              round(metal_bb.top * DBU, 3)],
            # Offset removed from the cell geometry (0,0 for the geometry-only
            # macros).  p3_placement_plan.py adds it back to the placement.
            'local_origin_um': list(origin_um),
        }
        # also write an individual GDS for isolated DRC
        p = os.path.join(OUT, 'struct_%s.gds' % tag)
        b.ly.write(p)
        meta[tag]['gds'] = p

    out_gds = os.path.join(OUT, 'v2_structures.gds')
    master.write(out_gds)

    man = {
        'master_gds': out_gds,
        'rules': R,
        'layer_map': {k: list(v) for k, v in L.items()},
        'structures': meta,
    }
    json.dump(man, open(os.path.join(OUT, 'v2_structures_manifest.json'), 'w',
                        encoding='utf-8'), indent=1, ensure_ascii=False)

    print('master:', out_gds)
    for tag in sorted(meta):
        m = meta[tag]
        print('  %-3s %-22s %s um' % (tag, m['cell'], m['size_um']))
    print('written manifest')
    return 0


if __name__ == '__main__':
    sys.exit(main())
