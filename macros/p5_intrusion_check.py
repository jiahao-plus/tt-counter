#!/usr/bin/env python3
"""p5_intrusion_check.py — 独立检测外部布线侵入研究结构的宏内区域。

**为什么必须独立做**：
  `route__drc_errors = 0` 只说明"没有违反间距规则"。它**不能**说明
  "宏内部没有被路由器塞进额外的 wire/via" —— 路由器完全可以在宏的 OBS
  之外、或在 PIN 的接近走廊里放合法间距的图形，这不产生 DRC 错误。

**判据分三层，不能混为一谈**：
  1. `foreign`  = 最终 GDS 在宏足迹内、且不属于宏自身 GDS 的图形
                  → 只说明"有别人在这个矩形里画了东西"，不等于结构被改坏
  2. `gap`      = 该层 foreign 与宏自身同层金属的最小间距（µm）
                  → gap > 0 表示物理上不接触，宏的几何是完整的
  3. `contact`  = gap ≈ 0，即外来图形**电气接触**宏金属
                  → 再分：接触点落在 LEF PIN 内 = 设计意图内的网络连接
                    （例如 `pwm_out` 连到 A/B/C1 的 `net`），不算污染；
                    接触点落在非 PIN 金属上 = 结构被外来网线改接 = 污染

  最终判据 `pass` 只看第 3 层的污染项。这是"科研真值是否被破坏"的判据，
  与 `route__drc_errors` 无关，也与宏内"是否出现别的图形"无关。

方法：
  1. 读最终 GDS + 每个研究宏自己的 GDS
  2. 足迹取自宏 GDS 自己的 prBoundary (235/4)，不用 LEF、不用 config
     —— 这样对"旧几何"和"新几何"都成立
  3. 取足迹内最终 GDS 各层 Region，减去宏自身 GDS 平移 (placement) 后的同层
  4. 逐层算 gap，并把 gap≈0 的接触点按 LEF PIN 分类

**不做的事**：不改任何设计文件，只读。

用法：
  python3 macros/p5_intrusion_check.py <final.gds> <final.def> [out.json] [macro_gds_dir]
    macro_gds_dir 默认 macros/out（当前几何）；基准用 .v2ana/head
    （`git cat-file HEAD:` 取出的原始字节）。**不要用 .v2ana/old** ——
    那是修复后用旧规则重新生成的副本，几何等价但字节不同，不是权威基准。
"""
import json
import os
import re
import sys

import pya

DBU = 0.001
PRB = (235, 4)
LAYERS = {
    'M1': (68, 20), 'Via1': (68, 44), 'M2': (69, 20), 'Via2': (69, 44),
    'M3': (70, 20), 'Via3': (70, 44), 'M4': (71, 20), 'Via4': (71, 44),
    'M5': (72, 20), 'M6': (73, 20),
    'li1': (67, 20), 'licon1': (66, 44), 'nwell': (64, 20),
    'diff': (65, 20), 'poly': (66, 20), 'nsdm': (93, 44), 'psdm': (94, 20),
}
TOUCH_TOL_UM = 0.005     # <= 5 nm gap counts as electrical contact
# LEF spells the layers met1..met6; the rest of this script keys by GDS names.
LEF_TO_GDS = {'met1': 'M1', 'met2': 'M2', 'met3': 'M3', 'met4': 'M4',
              'met5': 'M5', 'met6': 'M6', 'li1': 'li1', 'licon1': 'licon1'}

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MACRO_DIR = os.path.join(HERE, 'out')
TAG_OF_CELL = {
    'research_via1': 'A', 'research_via2': 'B', 'research_branch': 'C1',
    'research_near': 'C3', 'research_cross': 'C4',
    'research_dense': 'D', 'research_fiducial': 'E',
}


def collect(ly, cell, layer_map, clip=None):
    out = {}
    for name, (ln, dt) in layer_map.items():
        li = ly.find_layer(ln, dt)
        r = pya.Region()
        if li is not None:
            it = cell.begin_shapes_rec(li)
            while not it.at_end():
                s = it.shape()
                t = it.trans()
                if s.is_box():
                    r.insert(s.box.transformed(t))
                elif s.is_polygon():
                    r.insert(s.polygon.transformed(t))
                elif s.is_path():
                    r.insert(s.path.transformed(t).simple_polygon())
                it.next()
            r.merge()
        if clip is not None:
            r = r & clip
        out[name] = r
    return out


def prboundary_box(ly, cell):
    """Macro footprint in local coordinates, from its own prBoundary layer."""
    li = ly.find_layer(*PRB)
    if li is None:
        return None
    r = pya.Region()
    it = cell.begin_shapes_rec(li)
    while not it.at_end():
        r.insert(it.shape().box.transformed(it.trans()))
        it.next()
    r.merge()
    return None if r.is_empty() else r.bbox()


def lef_pins(lef_path, layer_map):
    """({gds_layer_key: [Box,...]}, (origin_x, origin_y)) from the macro LEF.

    LEF `RECT` coordinates are **relative to ORIGIN**, not to the macro
    placement. Adding only `placement` (without ORIGIN) shifts every PIN by
    ~1 um and turns a legitimate PIN connection into a false "pollution".
    """
    out = {}
    if not os.path.exists(lef_path):
        return out, (0.0, 0.0)
    txt = open(lef_path, encoding='utf-8').read()
    cur_layer, in_pin, pin_name = None, False, None
    for ln in txt.splitlines():
        s = ln.strip()
        if s.startswith('PIN '):
            in_pin, pin_name, cur_layer = True, s.split()[1], None
            continue
        if in_pin and pin_name and s == 'END %s' % pin_name:
            in_pin, pin_name, cur_layer = False, None, None
            continue
        if in_pin and s == 'END' and cur_layer is None:
            continue                      # END of the PORT block
        m = re.match(r'LAYER\s+(\S+)\s*;', s)
        if m and in_pin:
            cur_layer = LEF_TO_GDS.get(m.group(1), m.group(1))
            continue
        m = re.match(r'RECT\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+'
                     r'(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*;', s)
        if m and in_pin and cur_layer in layer_map:
            x0, y0, x1, y1 = (float(m.group(i)) for i in (1, 2, 3, 4))
            out.setdefault(cur_layer, []).append(
                pya.Box(int(round(x0 / DBU)), int(round(y0 / DBU)),
                        int(round(x1 / DBU)), int(round(y1 / DBU))))
    orgn = re.search(r'ORIGIN\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*;', txt)
    origin = ((float(orgn.group(1)), float(orgn.group(2)))
              if orgn else (0.0, 0.0))
    return out, origin


def lef_origin_size(lef_path):
    if not os.path.exists(lef_path):
        return None, None
    txt = open(lef_path, encoding='utf-8').read()
    o = re.search(r'ORIGIN\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*;', txt)
    s = re.search(r'SIZE\s+(\d+\.\d+)\s+BY\s+(\d+\.\d+)\s*;', txt)
    if not o or not s:
        return None, None
    return ((float(o.group(1)), float(o.group(2))),
            (float(s.group(1)), float(s.group(2))))


def def_placements(def_path):
    dtxt = open(def_path, encoding='utf-8', errors='replace').read()
    comp = dtxt.split('COMPONENTS')[1].split('END COMPONENTS')[0]
    place = {}
    for ln in comp.splitlines():
        m = re.match(r'\s*-\s+(\S+)\s+(research_\S+)\s+\+\s+.*?'
                     r'\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*(\S+)\s*;', ln)
        if m:
            place[m.group(2)] = (int(m.group(3)) / 1000.0,
                                 int(m.group(4)) / 1000.0, m.group(5))
    return place


def min_gap(foreign, self_r):
    """Smallest distance (um) between two disjoint Regions; None if one is empty.

    Search range is 0..20 um. A cap that the true gap can reach makes the
    result saturate silently — B's real 5.000 um gap initially looked
    identical to ">= 5 um" because 5.0 was also the search ceiling.
    """
    if foreign.is_empty() or self_r.is_empty():
        return None
    lo, hi = 0.0, 20.0
    tol = int(round(TOUCH_TOL_UM / DBU))
    if not (foreign.sized(tol) & self_r).is_empty():
        return 0.0
    for _ in range(24):
        mid = (lo + hi) / 2.0
        if (foreign.sized(int(round(mid / DBU))) & self_r).is_empty():
            lo = mid
        else:
            hi = mid
    return hi


def main(final_gds, def_path, out_json=None, macro_dir=None):
    macro_dir = macro_dir or DEFAULT_MACRO_DIR
    place = def_placements(def_path)
    # The placements come from the DEF, so the macro GDS they are paired with
    # MUST be the cells that DEF was built from.  Checking the round-4 DEF
    # against round-5 macro cells mixes two coordinate frames and reports the
    # offset as fake "foreign" metal -- that is exactly the 0.0324 um2
    # research_via2 artefact seen when this was first run.  The caller names
    # the matching pair explicitly (see the usage note at the top); the LEF
    # must come from the same directory or PIN classification silently breaks.

    fly = pya.Layout()
    fly.read(final_gds)
    ftop = fly.top_cell()

    results = {}
    total_foreign_layers = 0
    total_pollution = 0
    for cell, (px, py, orient) in sorted(place.items()):
        tag = TAG_OF_CELL.get(cell)
        if tag is None:
            continue
        mgds = os.path.join(macro_dir, 'struct_%s.gds' % tag)
        mly = pya.Layout()
        mly.read(mgds)
        mtop = mly.top_cell()

        bb = prboundary_box(mly, mtop)
        if bb is None:
            results[cell] = {'tag': tag, 'error': 'no prBoundary in %s' % mgds}
            total_pollution += 1
            continue

        ox, oy = bb.left * DBU, bb.bottom * DBU
        sw, sh = bb.width() * DBU, bb.height() * DBU
        ax0, ay0 = px + ox, py + oy
        ax1, ay1 = ax0 + sw, ay0 + sh
        clip = pya.Region(pya.Box(int(round(ax0 / DBU)), int(round(ay0 / DBU)),
                                  int(round(ax1 / DBU)), int(round(ay1 / DBU))))

        final_r = collect(fly, ftop, LAYERS, clip=clip)
        self_r = {k: (v.moved(int(round(px / DBU)), int(round(py / DBU))) & clip)
                  for k, v in collect(mly, mtop, LAYERS).items()}
        pins, lef_or = lef_pins(
            os.path.join(macro_dir, 'struct_%s.lef' % tag), LAYERS)
        # Three situations must not be conflated:
        #   * the macro HAS a PIN and we read it      -> classify on/off PIN
        #   * the macro has NO PIN by design (C3/C4/D/E are geometry-only, the
        #     round-4 LEFs declare no PIN at all)     -> every contact with its
        #     metal is a real intrusion; the off-PIN path is correct
        #   * the LEF is missing or unreadable        -> we cannot tell the two
        #     apart, and silently treating everything as off-PIN produces a
        #     false "polluted" verdict
        # Distinguish the last case by checking whether the LEF exists at all.
        lef_path = os.path.join(macro_dir, 'struct_%s.lef' % tag)
        if not pins and not os.path.exists(lef_path):
            results[cell] = {'tag': tag,
                             'error': 'missing %s -- cannot classify contacts'
                                      % lef_path}
            total_pollution += 1
            continue
        pin_dx = int(round((px + lef_or[0]) / DBU))
        pin_dy = int(round((py + lef_or[1]) / DBU))
        pins_abs = {k: [b.moved(pin_dx, pin_dy) for b in v]
                    for k, v in pins.items()}

        per_layer = {}
        n_foreign = 0
        n_pollute = 0
        for name in LAYERS:
            extra = final_r[name] - self_r[name]
            missing = self_r[name] - final_r[name]
            if extra.is_empty() and missing.is_empty():
                continue
            rec = {}
            if not extra.is_empty():
                eb = extra.bbox()
                rec['foreign_area_um2'] = round(extra.area() * DBU * DBU, 4)
                rec['foreign_bbox_um'] = [round(eb.left * DBU, 3),
                                          round(eb.bottom * DBU, 3),
                                          round(eb.right * DBU, 3),
                                          round(eb.top * DBU, 3)]
                rec['foreign_polys'] = len(list(extra.each()))
                n_foreign += 1
                g = min_gap(extra, self_r[name])
                rec['same_layer_self_shapes'] = self_r[name].count()
                rec['min_gap_to_self_um'] = (None if g is None else round(g, 3))

                # ---- classify each foreign polygon by what it touches -----
                # Working on the whole layer region loses the distinction
                # between "the router connected to my PIN" and "the router
                # shorted into my wire", because both produce a 0 um gap
                # somewhere on the layer. Classify polygon by polygon.
                tol = int(round(TOUCH_TOL_UM / DBU))
                pin_reg = pya.Region()
                for b in pins_abs.get(name, []):
                    pin_reg.insert(b)
                pin_reg.merge()
                pin_dil = pin_reg.sized(tol) if not pin_reg.is_empty() \
                    else pya.Region()
                self_dil = self_r[name].sized(tol) if not self_r[name].is_empty() \
                    else pya.Region()

                n_on_pin = n_off_pin = 0
                cbox = None
                for p in extra.each():
                    pr = pya.Region(p)
                    if self_dil.is_empty() or (pr & self_dil).is_empty():
                        continue                      # merely coexists
                    if not pin_dil.is_empty() and not (pr & pin_dil).is_empty():
                        n_on_pin += 1
                    else:
                        n_off_pin += 1
                    b = p.bbox()
                    if cbox is None:
                        cbox = [b.left, b.bottom, b.right, b.top]
                    else:
                        cbox = [min(cbox[0], b.left), min(cbox[1], b.bottom),
                                max(cbox[2], b.right), max(cbox[3], b.top)]
                rec['n_contact_on_pin'] = n_on_pin
                rec['n_contact_off_pin'] = n_off_pin
                rec['contacts_self'] = (n_on_pin + n_off_pin) > 0
                if cbox is not None:
                    rec['contact_bbox_um'] = [round(cbox[0] * DBU, 3),
                                              round(cbox[1] * DBU, 3),
                                              round(cbox[2] * DBU, 3),
                                              round(cbox[3] * DBU, 3)]
                if n_off_pin:
                    rec['pollutes_structure'] = True
                    n_pollute += 1
            if not missing.is_empty():
                mb = missing.bbox()
                rec['missing_area_um2'] = round(missing.area() * DBU * DBU, 4)
                rec['missing_bbox_um'] = [round(mb.left * DBU, 3),
                                          round(mb.bottom * DBU, 3),
                                          round(mb.right * DBU, 3),
                                          round(mb.top * DBU, 3)]
            per_layer[name] = rec
        total_foreign_layers += n_foreign
        total_pollution += n_pollute
        results[cell] = {
            'tag': tag,
            'macro_gds': mgds,
            'placement_um': [px, py],
            'orient': orient,
            'prboundary_local_um': [round(ox, 3), round(oy, 3),
                                    round(ox + sw, 3), round(oy + sh, 3)],
            'abs_footprint_um': [round(ax0, 3), round(ay0, 3),
                                 round(ax1, 3), round(ay1, 3)],
            'lef_pin_layers': sorted(pins),
            'layers_with_foreign': n_foreign,
            'layers_polluting': n_pollute,
            'detail': per_layer,
            'clean': n_foreign == 0,
            'structure_intact': n_pollute == 0,
        }

    res = {
        'final_gds': final_gds,
        'def': def_path,
        'macro_gds_dir': macro_dir,
        'kind': 'EXTERNAL_ROUTE_INTRUSION_INDEPENDENT',
        'pass_criterion': 'no foreign shape electrically contacts macro metal '
                          'outside a LEF PIN',
        'note': 'Compares final GDS inside each research macro prBoundary against '
                'that macro own GDS translated by its DEF placement. Excess is '
                'externally inserted geometry; it is classified by whether it '
                'touches macro metal, and if so whether the contact is on a PIN '
                '(intended net connection) or elsewhere (structural pollution). '
                'Does NOT use route__drc_errors, LEF OBS, or any router report.',
        'macros': results,
        'layers_with_foreign': total_foreign_layers,
        'layers_polluting': total_pollution,
        'pass': total_pollution == 0,
    }

    print('=' * 108)
    print('INDEPENDENT EXTERNAL-ROUTE INTRUSION CHECK')
    print('  final GDS :', final_gds)
    print('  DEF       :', def_path)
    print('  macro dir :', macro_dir)
    print('=' * 108)
    for cell, r in sorted(results.items()):
        if 'error' in r:
            print('  %-18s ERROR %s' % (cell, r['error']))
            continue
        f = r['abs_footprint_um']
        if r['clean']:
            verdict = 'CLEAN  (no foreign geometry at all)'
        elif r['structure_intact']:
            verdict = 'COEXIST (foreign present, macro metal untouched)'
        else:
            verdict = 'POLLUTED'
        print('  %-16s [%-2s] x[%8.3f..%8.3f] y[%8.3f..%8.3f] %s'
              % (cell, r['tag'], f[0], f[2], f[1], f[3], verdict))
        for lay, d in sorted(r['detail'].items()):
            if 'foreign_area_um2' not in d:
                continue
            gap = d.get('min_gap_to_self_um')
            note = ''
            if d.get('n_contact_off_pin'):
                note = '  CONTACT off-PIN x%d -> POLLUTION' % d['n_contact_off_pin']
            elif d.get('n_contact_on_pin'):
                note = '  CONTACT on PIN x%d (intended net)' % d['n_contact_on_pin']
            elif gap is None:
                note = '  macro has no %s shape (pure coexistence)' % lay
            print('       %-6s foreign %8.4f um2  polys=%d  gap=%s%s'
                  % (lay, d['foreign_area_um2'], d['foreign_polys'],
                     ('n/a' if gap is None else '%.3f um' % gap), note))
    print()
    print('layers with foreign geometry: %d' % total_foreign_layers)
    print('layers polluting structures:  %d' % total_pollution)
    print('VERDICT:', 'PASS - no off-PIN contact' if res['pass']
          else 'FAIL - structure polluted')

    if out_json:
        json.dump(res, open(out_json, 'w', encoding='utf-8'), indent=1,
                  ensure_ascii=False)
        print('written', out_json)
    return res


if __name__ == '__main__':
    _r = main(sys.argv[1], sys.argv[2],
              sys.argv[3] if len(sys.argv) > 3 else None,
              sys.argv[4] if len(sys.argv) > 4 else None)
    sys.exit(0 if _r['pass'] else 1)
