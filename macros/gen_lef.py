#!/usr/bin/env python3
"""gen_lef.py — 为每个研究结构生成 LEF MACRO（α′ 接口 + OBS）。

## α′ 是什么，为什么要这样

A/B/C1 的物理事实是：两个金属接入点被宏内部的 Via 连成 **同一个节点**
（实测见 v2_validation/P4_PIN_COMPONENT_AUDIT.json）。因此它们必须被表达成
**一个逻辑 PIN**，否则网表里会出现两个 net 而物理上只有一个节点 —— 这正是
第三轮 CI 之前的核心矛盾。

LEF/DEF 里，同一个 PIN 下：
  * 多个 PORT 之间是**弱连接** —— 路由器不保证它们连通，信号路由不适用；
  * 同一个 PORT 内多个几何图形是**强连接** —— 视为同一个接入点。

所以 α′ 用一个 PIN、**一个 PORT**、PORT 内列多个跨层 LAYER/RECT：

    PIN net
      DIRECTION INOUT ;
      USE SIGNAL ;
      PORT
        LAYER met1 ;
          RECT ... ;        # M1 侧
        LAYER met2 ;
          RECT ... ;        # M2 侧（与 M1 侧经宏内 Via1 相连）
      END
    END net

方向统一用 INOUT：这些是被动金属，没有方向语义。用 INPUT/OUTPUT 会暗示
有源器件，在连续网表里引入不必要的约束。

## 结构分类（路线 D）

  A  research_via1     电气被动宏   PIN net (1 PORT, met1+met2)
  B  research_via2     电气被动宏   PIN net (1 PORT, met2+met3)
  C1 research_branch   电气被动宏   PIN net (1 PORT, met1+met2 x3 分支)
  C3 research_near     无端口几何宏  0 PIN（8 条独立导体，只提供几何真值）
  C4 research_cross    无端口几何宏  0 PIN
  D  research_dense    无端口几何宏  0 PIN
  E  research_fiducial 无端口几何宏  0 PIN

C3 的 8 条线技术上可以有 8 个 PIN（8 个独立 net 是自洽的）。选择无端口是
**科研决定**：给端口会让路由器在间距阶梯附近布线加 via，污染
0.14/0.20/0.28/0.50 µm 的间距测量。若将来需要 net 真值，加回 PIN 即可，
物理结构不用改。

## OBS 规则（本轮新增）

两条规则，按宏需要保护什么来选。两条都有交付物的实证依据，不是臆造：

  参照物：V1 的官方 LEF
    .../tt-counter-exp/official_ci/GDS_logs/runs/wokwi/final/lef/
        tt_um_jiahao_plus_counter.lef
  该文件由 Magic 在 Precheck 15/15 通过的那次 CI 中写出。实测：
  li1/met1/met2/met3/nwell 每层各 **一个** OBS 矩形覆盖整层绘制范围
  （这些层没有 pin）；met4 有 50 个 OBS 矩形与 51 个 pin 共存，
  **同层 pin/obs 重叠为 0**。OBS 写作 `OBS` … `END`，坐标为宏局部。

  **关于头部语句**：V1 的 LEF 是 VERSION 5.7，带 `NOWIREEXTENSIONATPIN ON`。
  该语句在 LEF 5.6 已被移除，OpenROAD 会警告
  "NOWIREEXTENSIONATPIN statement is obsolete in version 5.6 or later" 并忽略它。
  我们输出 VERSION 5.8，因此**不写**这条语句，而不是交付一个必然报警的 LEF。

**规则 E（电气宏 A/B/C1）：OBS = 绘制金属 − PIN 图形**

  这是 V1 规则在有 PIN 的宏上的推广。LEF 路由器不能穿过 OBS，若 OBS 盖上
  PIN，PIN 就废了；减去 PIN 正是让 A/B/C1 保持可布线的同时把其余图形对
  路由器隐藏。当前几何实测：每个 PIN 至少保留三个自由接近方向。

**规则 G（几何宏 C3/C4/D/E）：OBS = 整个 prBoundary 矩形**

  这些宏没有 PIN，所以没有任何理由让内部空间保持可布。放任它可布反而有害：
  C3 的对间间隙实测 **2.000 µm**，是 met1 线宽 0.14 µm 的十四倍 —— 足够
  路由器在一对线之间穿一条线，或在 0.28/0.50 µm 阶梯旁落一个 via。
  整块阻挡使"最终 GDS 里的结构就是我们画的结构"成为输入的属性，
  而不是对路由器的期望。

  规则 G **只施加于该宏真正绘制了图形的层**。刻意不用于 met4/met5：
  这些宏没有 met4 图形，挡它没有意义；而 M4 是 PDN stripe 层
  （V1 流程里 PDN_VERTICAL_LAYER = met4，1.6 µm stripe 贯穿 core 高度）。
  在没有证据表明 stripe 会避开该宏的情况下挡 M4，会冒
  ERROR_ON_PDN_VIOLATIONS 的风险（该键在本流程中为 True）。

宏下方的行由 LibreLane 自己切掉：V1 flow.log 第 18 步是
`cut_rows -halo_width_x 10.0 -halo_width_y 10.0`，早于第 21 步的 PDN 生成，
所以宏内部及其 10 µm halo 内不会生成 met1 电源轨。

## 关键约束

  LEF MACRO 名 == GDS cell 名 == Verilog 模块名
  LEF PIN 名 == Verilog 端口名（逐字符，区分大小写）
  LEF SIZE == GDS prBoundary
  同一 PIN 的所有 PORT 几何必须在同一个 GDS 连通分量上

运行（WSL）：python3 macros/gen_lef.py
"""
import json
import os
import sys

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
DBU = 0.001
L = {'M1': (68, 20), 'Via1': (68, 44), 'M2': (69, 20),
     'Via2': (69, 44), 'M3': (70, 20), 'M4': (71, 20)}
LEF_LAYER = {'M1': 'met1', 'M2': 'met2', 'M3': 'met3', 'M4': 'met4'}
OBS_LAYER_ORDER = ('met1', 'met2', 'met3', 'met4')

# One PIN per electrical macro. Each entry is a list of (layer, x, y) access
# points; all of them land in the SAME LEF PORT and the SAME GDS component.
# Coordinates are wire centrelines in the structure's own frame; pin_rect()
# turns each into a legal landing.
#
# The pin name is exactly "net", matching the Verilog port name character for
# character. An earlier revision used A/B/IN/TAP against Verilog a/b/in/tap,
# which OpenROAD cannot match.
PINS = {
    # A: M1 far end + M2 far end, joined inside the macro by Via1.
    'A': [('net', [('M1', 1.0, 2.0), ('M2', 9.0, 4.0)])],
    # B: M2 far end + M3 far end, joined by Via2.
    'B': [('net', [('M2', 1.0, 2.0), ('M3', 11.0, 5.0)])],
    # C1: the M1 trunk end plus the three M2 branch stubs. Measured from
    # struct_C1.gds: stubs at x 1.93..2.07, 5.93..6.07, 9.93..10.07, tops at
    # y 7.07 / 7.57 / 8.07. Pin rects are 0.14 tall, so centre each 0.07 below
    # its stub top to stay fully on metal.
    'C1': [('net', [('M1', 1.0, 5.0),
                    ('M2', 2.0, 7.00),
                    ('M2', 6.0, 7.50),
                    ('M2', 10.0, 8.00)])],
    # C3 / C4 / D / E carry no pins.
    'C3': [],
    'C4': [],
    'D': [],
    'E': [],
}

# Which OBS rule each macro uses. 'E' = electrical (metal minus pins),
# 'G' = geometry-only (whole footprint). Keeping this table explicit means a
# future structure cannot silently inherit the wrong rule.
OBS_RULE = {'A': 'E', 'B': 'E', 'C1': 'E',
            'C3': 'G', 'C4': 'G', 'D': 'G', 'E': 'G'}


def pin_rect(layer, x, y):
    """A small legal landing at the endpoint, sized to the layer min width."""
    w = 0.14 if layer in ('M1', 'M2') else 0.30
    return (x - w / 2, y - w / 2, x + w / 2, y + w / 2)


def clean(v):
    """Round to LEF precision and kill negative zero.

    Subtracting the bbox origin produces values such as -6.9e-17, which
    formats as "-0.000". It is numerically zero, but a delivered LEF should
    not carry it.
    """
    return round(v, 3) + 0.0


def layer_region(top, li):
    r = pya.Region()
    if li is None:
        return r
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


def metal_regions(ly, top, ox, oy):
    """{lef layer name: merged Region of drawn metal}, shifted to macro-local.

    Shifting here means every downstream check and the emitted RECTs use the
    same coordinate frame as the LEF, so no later `- ORIGIN` can drift.
    """
    out = {}
    for k, (ln, dt) in L.items():
        if k not in LEF_LAYER:
            continue                      # skip Via* / prB
        li = ly.find_layer(ln, dt)
        if li is None:
            continue
        r = layer_region(top, li)
        if not r.is_empty():
            out[LEF_LAYER[k]] = r.moved(-ox, -oy)
    return out


def verify_pin_on_metal(metal_by_layer, layer, local_x, local_y, dbu):
    """True when a 1 nm probe at a MACRO-LOCAL um point is fully covered by
    this layer's drawn metal. (probe - metal).is_empty() is the PASS test."""
    reg = metal_by_layer.get(LEF_LAYER[layer])
    if reg is None:
        return False
    x = int(round(local_x / dbu)); y = int(round(local_y / dbu))
    return (pya.Region(pya.Box(x, y, x + 1, y + 1)) - reg).is_empty()


# ---------------------------------------------------------------- OBS rules
def obs_rule_e(metal_local, pin_boxes):
    """Rule E: rectangles tiling (drawn metal - pins), in dbu, macro-local.

    `metal_local` merged Region of drawn metal on that layer, macro-local
    `pin_boxes`   list of pya.Box that are PIN geometry on that layer
    """
    region = metal_local
    for b in pin_boxes:
        region = region - pya.Region(b)
    region = region.merged()
    if region.is_empty():
        return []
    # decompose_trapezoids_to_region yields real rectangles only for
    # rectilinear input, which SKY130 metal always is.
    pieces = region.decompose_trapezoids_to_region()
    return [p.bbox() for p in pieces.each() if not p.is_empty()]


def obs_rule_g(size_dbu):
    """Rule G: a single rectangle covering the macro's whole prBoundary."""
    return [pya.Box(0, 0, size_dbu[0], size_dbu[1])]


def verify_obs(tag, rule, obs_by_layer, pin_boxes_by_layer, metal_local,
               size_dbu, problems):
    """Re-derive the OBS invariants independently of how the rects were built.

    Checked on every layer:
      O1  no OBS rectangle overlaps a PIN rectangle
      O3  the OBS rectangles do not overlap each other (they tile, not stack)
      O4  the OBS stays inside the macro footprint
    Plus one rule-specific exactness condition:
      E   OBS + PIN covers the drawn metal exactly. Less would leave invisible
          metal the router can neither see nor avoid; more would block empty
          space and could cut a pin approach corridor.
      G   OBS covers all the drawn metal, equals the footprint, one rectangle.

    Returns a per-layer report for macro_index.json.
    """
    report = {'rule': rule, 'n_rects': {}, 'area_obs': {}, 'area_metal': {},
              'obs_pin_overlap': {}, 'obs_not_metal': {},
              'obs_self_overlap': {}, 'all_ok': True}

    footprint = pya.Region(pya.Box(0, 0, size_dbu[0], size_dbu[1]))

    for lay in OBS_LAYER_ORDER:
        obs_boxes = obs_by_layer.get(lay, [])
        pin_boxes = pin_boxes_by_layer.get(lay, [])
        reg = metal_local.get(lay)

        if reg is None:
            if obs_boxes:
                problems.append('%s %s: OBS emitted for a layer with no metal'
                                % (tag, lay))
                report['all_ok'] = False
            continue
        if not obs_boxes:
            if not pin_boxes:
                problems.append('%s %s: metal drawn but no OBS and no PIN — the '
                                'router cannot see it' % (tag, lay))
                report['all_ok'] = False
            continue

        obs = pya.Region()
        for b in obs_boxes:
            obs.insert(b)
        obs = obs.merged()
        pins = pya.Region()
        for b in pin_boxes:
            pins.insert(b)
        pins = pins.merged()

        ov = (obs & pins).area()
        raw = sum((b.right - b.left) * (b.top - b.bottom) for b in obs_boxes)
        self_ov = raw - obs.area()
        outside_fp = (obs - footprint).area()

        report['n_rects'][lay] = len(obs_boxes)
        report['area_obs'][lay] = obs.area()
        report['area_metal'][lay] = reg.area()
        report['obs_pin_overlap'][lay] = ov
        report['obs_not_metal'][lay] = (obs - reg).area()
        report['obs_self_overlap'][lay] = self_ov

        if ov:
            problems.append('O1 %s %s: OBS overlaps a PIN by %d dbu^2'
                            % (tag, lay, ov))
            report['all_ok'] = False
        if self_ov:
            problems.append('O3 %s %s: OBS rectangles overlap each other by '
                            '%d dbu^2' % (tag, lay, self_ov))
            report['all_ok'] = False
        if outside_fp:
            problems.append('O4 %s %s: OBS extends %d dbu^2 outside the macro '
                            'footprint' % (tag, lay, outside_fp))
            report['all_ok'] = False

        if rule == 'E':
            uncovered = (reg - obs - pins).area()
            if uncovered:
                problems.append('E %s %s: %d dbu^2 of drawn metal is neither OBS '
                                'nor PIN — an invisible obstacle'
                                % (tag, lay, uncovered))
                report['all_ok'] = False
            extra = (obs - reg).area()
            if extra:
                problems.append('E %s %s: OBS covers %d dbu^2 that is not drawn '
                                'metal — it would block empty space'
                                % (tag, lay, extra))
                report['all_ok'] = False
        else:
            missing = (reg - obs).area()
            if missing:
                problems.append('G %s %s: %d dbu^2 of drawn metal is not covered '
                                'by OBS' % (tag, lay, missing))
                report['all_ok'] = False
            if obs.area() != footprint.area():
                problems.append('G %s %s: OBS area %d != footprint %d'
                                % (tag, lay, obs.area(), footprint.area()))
                report['all_ok'] = False
            if len(obs_boxes) != 1:
                problems.append('G %s %s: expected 1 blocking rectangle for a '
                                'geometry-only macro, got %d'
                                % (tag, lay, len(obs_boxes)))
                report['all_ok'] = False

    return report


def emit(m, bbox, pins, obs_by_layer, dbu, local_origin):
    """Emit the LEF. `pins` is [(name, [(layer, x, y), ...])] — one PORT per
    PIN, listing every access point as a LAYER/RECT pair inside that PORT.

    `obs_by_layer` is {lef_layer_name: [pya.Box in dbu]} for the obstruction
    block, already in macro-local coordinates.

    `local_origin` is the offset that was removed from the cell during
    normalisation (0,0 for the macros that were left alone).  It is used only
    to map the design-coordinate PINS table onto the cell as it sits on disk.

    TWO DIFFERENT THINGS, do not conflate them:
      ORIGIN       written as the cell's own bbox lower-left (`bbox[0:2]`).
                   For a normalised macro that is (0,0); for a geometry-only
                   macro it stays the round-4 value.  This keeps every RECT
                   inside the (0,0)-(SIZE) frame, so SIZE never has to grow.
      local_origin the re-basing shift, only used to convert PINS.
    """
    lines = ['VERSION 5.8 ;',
             'BUSBITCHARS "[]" ;',
             'DIVIDERCHAR "/" ;',
             'MACRO %s' % m['cell'],
             '  CLASS BLOCK ;',
             # ORIGIN follows the cell's own frame.  A PIN under a non-zero
             # ORIGIN is unsafe (OpenROAD adds ORIGIN, Magic subtracts it), so
             # only the macros without a PIN may carry a non-zero ORIGIN --
             # and those are exactly the ones we did not normalise.
             '  ORIGIN %.3f %.3f ;' % (bbox[0], bbox[1]),
             '  SIZE %.3f BY %.3f ;' % (bbox[2] - bbox[0], bbox[3] - bbox[1]),
             '  SYMMETRY X Y ;']
    for name, accesses in pins:
        lines.append('  PIN %s' % name)
        lines.append('    DIRECTION INOUT ;')
        lines.append('    USE SIGNAL ;')
        lines.append('    PORT')
        for layer, x, y in accesses:
            lx, ly_ = clean(x - local_origin[0]), clean(y - local_origin[1])
            x0, y0, x1, y1 = (clean(v) for v in pin_rect(layer, lx, ly_))
            lines.append('      LAYER %s ;' % LEF_LAYER[layer])
            lines.append('        RECT %.3f %.3f %.3f %.3f ;' % (x0, y0, x1, y1))
        lines.append('    END')
        lines.append('  END %s' % name)

    # ---- OBS
    # Emitted in a fixed layer order, rectangles sorted, so re-running produces
    # a byte-identical file — the geometry-digest check depends on that.
    obs_lines = []
    for lay in OBS_LAYER_ORDER:
        boxes = obs_by_layer.get(lay)
        if not boxes:
            continue
        obs_lines.append('      LAYER %s ;' % lay)
        for b in sorted(boxes, key=lambda q: (q.bottom, q.left, q.top, q.right)):
            obs_lines.append('        RECT %.3f %.3f %.3f %.3f ;'
                             % (clean(b.left * dbu), clean(b.bottom * dbu),
                                clean(b.right * dbu), clean(b.top * dbu)))
    if obs_lines:
        lines.append('  OBS')
        lines.extend(obs_lines)
        lines.append('  END')

    lines.append('END %s' % m['cell'])
    lines.append('END LIBRARY')
    return '\n'.join(lines) + '\n'


def main():
    man = json.load(open(os.path.join(OUT, 'v2_structures_manifest.json'),
                         encoding='utf-8'))
    idx = {}
    problems = []
    for tag, m in man['structures'].items():
        p = m['gds']
        ly = pya.Layout(); ly.read(p)
        top = ly.top_cell()
        dbu = ly.dbu
        bb = top.bbox()
        bbox = [bb.left * dbu, bb.bottom * dbu, bb.right * dbu, bb.top * dbu]
        size_dbu = (bb.right - bb.left, bb.top - bb.bottom)
        ox, oy = bb.left, bb.bottom        # dbu, macro origin

        counts = {}
        for k, (ln, dt) in L.items():
            li = ly.find_layer(ln, dt)
            counts[k] = 0 if li is None else sum(1 for _ in top.shapes(li).each())

        metal_local = metal_regions(ly, top, ox, oy)

        # ---- pins, and the per-layer pin rectangles they occupy ----------
        # PINS stores the access points in DESIGN coordinates, i.e. the frame
        # the structures were laid out in before any re-basing.  A cell on disk
        # has had `local_origin` subtracted from it, so subtract the same
        # offset to get the cell-local coordinate.  For the normalised macros
        # local_origin == the original bbox lower-left and bbox[0] is now 0;
        # for the untouched geometry macros local_origin is 0 and bbox[0] is
        # that same lower-left.  Using `local_origin` covers both cases.
        lo_um = m.get('local_origin_um', [0.0, 0.0])
        pins = PINS.get(tag, [])
        pin_checks = []
        pin_boxes_by_layer = {}
        for name, accesses in pins:
            for layer, x, y in accesses:
                lx, ly_ = x - lo_um[0], y - lo_um[1]
                ok = verify_pin_on_metal(metal_local, layer, lx, ly_, dbu)
                pin_checks.append({'pin': name, 'layer': layer,
                                   'x': x, 'y': y, 'on_metal': ok})
                if not ok:
                    problems.append('%s: access point %s(%.2f, %.2f) not on metal'
                                    % (tag, layer, x, y))
                # macro-local rect, exactly the RECT that will be emitted
                x0, y0, x1, y1 = pin_rect(layer, lx, ly_)
                pin_boxes_by_layer.setdefault(LEF_LAYER[layer], []).append(
                    pya.Box(int(round(x0 / dbu)), int(round(y0 / dbu)),
                            int(round(x1 / dbu)), int(round(y1 / dbu))))

        # ---- OBS ---------------------------------------------------------
        rule = OBS_RULE[tag]
        obs_by_layer = {}
        if rule == 'E':
            for lay, reg in metal_local.items():
                obs_by_layer[lay] = obs_rule_e(reg, pin_boxes_by_layer.get(lay, []))
        else:
            for lay in metal_local:
                obs_by_layer[lay] = obs_rule_g(size_dbu)

        # ---- verify the invariants before writing ------------------------
        obs_check = verify_obs(tag, rule, obs_by_layer, pin_boxes_by_layer,
                               metal_local, size_dbu, problems)

        lef = emit(m, bbox, pins, obs_by_layer, dbu,
                   local_origin=m.get('local_origin_um', [0.0, 0.0]))
        lp = os.path.join(OUT, 'struct_%s.lef' % tag)
        open(lp, 'w', encoding='utf-8', newline='\n').write(lef)
        idx[tag] = {
            'cell': m['cell'],
            'lef': lp,
            'gds': p,
            'bbox_um': [round(v, 3) for v in bbox],
            # Re-basing shift taken out of the cell (0,0 for the geometry-only
            # macros that were left alone).  p3_placement_plan.py adds this
            # back into the instance placement so the macro does not move.
            'local_origin_um': list(m.get('local_origin_um', [0.0, 0.0])),
            'size_um': [round(bbox[2] - bbox[0], 3), round(bbox[3] - bbox[1], 3)],
            'layers': counts,
            'pins': pin_checks,
            'pin_names': [n for n, _ in pins],
            'n_ports': len(pins),          # one PORT per PIN by construction
            'n_access_points': len(pin_checks),
            'pins_all_on_metal': all(c['on_metal'] for c in pin_checks),
            'electrical': bool(pins),
            'obs_rule': rule,
            'obs': obs_check,
        }

    json.dump(idx, open(os.path.join(OUT, 'macro_index.json'), 'w',
                        encoding='utf-8'), indent=1, ensure_ascii=False)

    print('%-4s %-20s %-18s %-5s %-6s %-7s %-5s %-8s %s'
          % ('tag', 'cell', 'size_um', 'pins', 'ports', 'access',
             'rule', 'obs_rect', 'model'))
    for tag in sorted(idx):
        e = idx[tag]
        n_obs = sum(e['obs']['n_rects'].values())
        print('%-4s %-20s %-18s %-5d %-6d %-7d %-5s %-8d %s'
              % (tag, e['cell'], '%.3fx%.3f' % tuple(e['size_um']),
                 len(e['pin_names']), e['n_ports'], e['n_access_points'],
                 e['obs_rule'], n_obs,
                 'ELECTRICAL' if e['electrical'] else 'geometry-only'))
    print()
    if problems:
        print('PROBLEMS (%d):' % len(problems))
        for p in problems:
            print('  !', p)
        return 1
    print('ALL PIN ACCESS POINTS ON DRAWN METAL')
    print('ALL OBS INVARIANTS HOLD (O1/O3/O4 + rule E or G)')
    print('written macros/out/macro_index.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
