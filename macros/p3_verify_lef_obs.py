#!/usr/bin/env python3
"""p3_verify_lef_obs.py — 独立复核七个 LEF 的 OBS，不依赖 gen_lef.py。

## 为什么要独立写一遍

`gen_lef.py` 在写文件前会自检 OBS 不变量，但那用的是**它自己构造 OBS 时
用的同一批 Region**。如果它的金属提取或坐标平移有 bug，自检会跟着一起错。
这和验收报告 §3 对"自己写的 LEF 解析器验自己"的批评是同一类问题。

本脚本因此：

  * 用**独立的 LEF 文本解析器**（不 import gen_lef），从派生 LEF 读回
    PIN 与 OBS 的实际矩形；
  * 用**独立重建**的 GDS 金属 Region（同样不 import gen_lef）作为真值；
  * 再用 **OpenROAD ODB**（第三方读取器）确认它读到的 OBS 矩形数与层
    与 LEF 文本一致 —— 三方一致才算数。

## 检查项

  O1  OBS ∩ PIN = ∅（同层）。OBS 盖住 PIN 就等于废掉这个 PIN。
  O2  PIN 仍有合法接近方向：每个 PIN 矩形在同层四个方向各取 1.0 µm 走廊，
      要求至少 3 个走廊**完全**不被 OBS 占据。用"完全"而不是"部分"是因为
      路由器需要一条能整条走出的通道，被 OBS 咬掉一半的走廊不算通道。
  O3  OBS 矩形互不重叠（它们是平铺，不是叠加）。
  O4  OBS 全部落在宏 footprint 内。
  O5  任何层都不得有 OBS，除非该层真的有绘制金属（防止挡住空层）。
  O6  met4 / met5 上**不得**出现任何 OBS —— 这两层是 PDN 层。
      本流程 PDN_VERTICAL_LAYER = met4、ERROR_ON_PDN_VIOLATIONS = True，
      未经核查就挡 M4 会直接制造 PDN 违规。

  规则 E（A/B/C1 电气宏）
      E1  绘制金属 ⊆ OBS ∪ PIN  —— 不能留下路由器看不见的金属
      E2  OBS ⊆ 绘制金属        —— 不能挡住空白区域
  规则 G（C3/C4/D/E 几何宏）
      G1  绘制金属 ⊆ OBS
      G2  OBS 面积 == footprint 面积，且恰好 1 个矩形

规则取自 `macros/out/macro_index.json` 的 `obs_rule` 字段，因此改了源规则
而忘了重跑 gen_lef 会被这里抓到。

## 输出

  v2_validation/P5_LEF_OBS.json
  v2_validation/P5_LEF_OBS.md
  stdout                          逐宏一行 + ODB 对照

用法（WSL，cwd 为仓库根）：python3 macros/p3_verify_lef_obs.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'out')
VAL = os.path.join(ROOT, 'v2_validation')
DBU = 0.001

# GDS layer map, restated here rather than imported: the whole point of this
# script is not to inherit gen_lef's view of the world.
GDS_LAYERS = {'met1': (68, 20), 'met2': (69, 20), 'met3': (70, 20),
              'met4': (71, 20), 'met5': (72, 20)}
PRB = (235, 4)
PDN_LAYERS = ('met4', 'met5')

TAGS = ['A', 'B', 'C1', 'C3', 'C4', 'D', 'E']
CORRIDOR_UM = 1.0
MIN_FREE_SIDES = 3

# A minimal tech LEF so ODB can keep met1..met4 geometry. It declares layer
# names, direction, pitch and width only — no MACRO, nothing from our designs.
# Without it ODB silently drops geometry on layers it does not know, which
# would make the cross-check vacuous.
MIN_TECH_LEF = """VERSION 5.8 ;
BUSBITCHARS "[]" ;
DIVIDERCHAR "/" ;
UNITS
  DATABASE MICRONS 1000 ;
END UNITS
MANUFACTURINGGRID 0.005 ;
LAYER met1
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
  PITCH 0.46 ;
  WIDTH 0.14 ;
END met1
LAYER via1
  TYPE CUT ;
END via1
LAYER met2
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
  PITCH 0.68 ;
  WIDTH 0.14 ;
END met2
LAYER via2
  TYPE CUT ;
END via2
LAYER met3
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
  PITCH 0.68 ;
  WIDTH 0.30 ;
END met3
LAYER via3
  TYPE CUT ;
END via3
LAYER met4
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
  PITCH 0.92 ;
  WIDTH 0.30 ;
END met4
LAYER met5
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
  PITCH 1.60 ;
  WIDTH 1.60 ;
END met5
END LIBRARY
"""

ODB_TCL = """read_lef %(tech)s
%(lefs)s
set db [ord::get_db]
set out {}
foreach m {%(masters)s} {
  set ma ""
  foreach lib [$db getLibs] {
    set cand [$lib findMaster $m]
    if {$cand != "NULL"} { set ma $cand ; break }
  }
  if {$ma == ""} {
    lappend out "$m MISSING 0 0"
    continue
  }
  set npins [llength [$ma getMTerms]]
  set nport 0
  foreach mt [$ma getMTerms] { incr nport [llength [$mt getMPins]] }
  set nobs 0
  # `array set perlayer {}` does NOT clear an existing array — it is only a
  # bulk assignment, so counts leak from the previous master into every later
  # one. `unset -nocomplain` is the actual reset.
  unset -nocomplain perlayer
  array set perlayer {}
  foreach b [$ma getObstructions] {
    incr nobs
    set ln [[$b getTechLayer] getName]
    if {[info exists perlayer($ln)]} { incr perlayer($ln) } else { set perlayer($ln) 1 }
  }
  set pl {}
  foreach k [lsort [array names perlayer]] { lappend pl "$k=$perlayer($k)" }
  lappend out "$m OK $npins $nport $nobs [join $pl ,]"
}
puts "ODB_BEGIN"
foreach line $out { puts $line }
puts "ODB_END"
exit
"""


# ------------------------------------------------------------------ LEF parse
def parse_lef(path):
    """Independent parse: {macro, origin, size, pins, obs}.

    pins: [{name, direction, ports: [[(layer, (x0,y0,x1,y1))]]}]
    obs:  {layer: [(x0,y0,x1,y1)]}
    All coordinates in micrometres, macro-local.

    OBS block syntax is `OBS` … `END` (a bare END, unlike `PIN x` … `END x`),
    so it is matched separately after the PIN blocks.
    """
    txt = open(path, encoding='utf-8').read()
    macro = re.search(r'^\s*MACRO\s+(\S+)', txt, re.M).group(1)
    o = re.search(r'^\s*ORIGIN\s+(-?[\d.]+)\s+(-?[\d.]+)\s*;', txt, re.M)
    origin = (float(o.group(1)), float(o.group(2))) if o else (0.0, 0.0)
    sz = re.search(r'^\s*SIZE\s+([\d.]+)\s+BY\s+([\d.]+)\s*;', txt, re.M)
    size = (float(sz.group(1)), float(sz.group(2)))

    rect_re = re.compile(r'^RECT\s+(-?[\d.]+)\s+(-?[\d.]+)\s+'
                         r'(-?[\d.]+)\s+(-?[\d.]+)\s*;')

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
                rm = rect_re.match(s)
                if rm and cur:
                    geoms.append((cur, tuple(float(rm.group(i))
                                             for i in range(1, 5))))
            ports.append(geoms)
        pins.append({'name': name,
                     'direction': d.group(1) if d else None,
                     'ports': ports})

    # The OBS block, if any. Search from after the last PIN block so a
    # `PORT`-less macro cannot accidentally match an inner END.
    obs = {}
    om = re.search(r'^\s*OBS\s*$(.*?)^\s*END\s*$', txt, re.S | re.M)
    if om:
        cur = None
        for line in om.group(1).splitlines():
            s = line.strip()
            lm = re.match(r'LAYER\s+(\S+)\s*;', s)
            if lm:
                cur = lm.group(1)
                obs.setdefault(cur, [])
                continue
            rm = rect_re.match(s)
            if rm and cur:
                obs[cur].append(tuple(float(rm.group(i)) for i in range(1, 5)))
    return {'macro': macro, 'origin': origin, 'size': size,
            'pins': pins, 'obs': obs}


# ------------------------------------------------------------------ GDS truth
def gds_metal(path):
    """{lef_layer: merged Region in MACRO-LOCAL dbu} + footprint size in dbu.

    Rebuilt from scratch here (no import of gen_lef), starting from the
    prBoundary rectangle so the local frame is anchored on the GDS itself
    rather than on whatever gen_lef decided ORIGIN should be.
    """
    ly = pya.Layout()
    ly.read(path)
    top = ly.top_cell()
    dbu = ly.dbu

    prb_li = ly.find_layer(*PRB)
    prb = pya.Region()
    if prb_li is not None:
        for sh in top.shapes(prb_li).each():
            prb.insert(sh.box if sh.is_box() else sh.polygon)
    if prb.is_empty():
        # No prBoundary: fall back to the metal bbox, and say so via 'anchored'
        bb = top.bbox()
        prb = pya.Region(pya.Box(bb.left, bb.bottom, bb.right, bb.top))
        anchored = False
    else:
        anchored = True
    fpb = prb.bbox()

    metal = {}
    for name, (ln, dt) in GDS_LAYERS.items():
        li = ly.find_layer(ln, dt)
        if li is None:
            continue
        r = pya.Region()
        it = top.begin_shapes_rec(li)
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
        if not r.is_empty():
            metal[name] = r.moved(-fpb.left, -fpb.bottom).merged()

    footprint = pya.Region(pya.Box(0, 0, fpb.right - fpb.left,
                                   fpb.top - fpb.bottom))
    return {'metal': metal, 'footprint': footprint, 'dbu': dbu,
            'prboundary_anchored': anchored}


def to_dbu(rect):
    """LEF micrometre rect -> pya.Box in dbu, macro-local."""
    x0, y0, x1, y1 = rect
    return pya.Box(int(round(x0 / DBU)), int(round(y0 / DBU)),
                   int(round(x1 / DBU)), int(round(y1 / DBU)))


# --------------------------------------------------------------------- checks
def verify_macro(tag, rule, lef_path=None, gds_path=None):
    """Run every OBS invariant for one macro.

    `lef_path` / `gds_path` default to macros/out/struct_<tag>.*; the negative
    control overrides them to point at deliberately-corrupted copies, which is
    how we prove these checks have discriminating power.
    """
    lef_path = lef_path or os.path.join(OUT, 'struct_%s.lef' % tag)
    gds_path = gds_path or os.path.join(OUT, 'struct_%s.gds' % tag)
    lef = parse_lef(lef_path)
    g = gds_metal(gds_path)
    metal, footprint, dbu = g['metal'], g['footprint'], g['dbu']
    problems, info = [], {'layers': {}}

    if abs(lef['size'][0] * 1000 - (footprint.bbox().right)) > 1 or \
       abs(lef['size'][1] * 1000 - (footprint.bbox().top)) > 1:
        problems.append('SIZE %.3fx%.3f != prBoundary %.3fx%.3f um'
                        % (lef['size'][0], lef['size'][1],
                           footprint.bbox().right * dbu,
                           footprint.bbox().top * dbu))

    # ---- pins, per layer in dbu
    pin_by_layer = {}
    pin_list = []
    for p in lef['pins']:
        n_ports = len(p['ports'])
        if n_ports != 1:
            problems.append('%s.%s: %d PORT blocks (alpha-prime needs exactly 1)'
                            % (tag, p['name'], n_ports))
        rects = []
        for geoms in p['ports']:
            for lay, rc in geoms:
                b = to_dbu(rc)
                pin_by_layer.setdefault(lay, []).append(b)
                rects.append({'layer': lay,
                              'rect_um': [round(v, 3) for v in rc]})
        pin_list.append({'name': p['name'], 'n_ports': n_ports,
                         'geometries': rects})

    # ---- O5: OBS on a layer with no drawn metal
    for lay in lef['obs']:
        if lay not in metal:
            problems.append('O5 %s: OBS on %s, which draws no metal' % (tag, lay))
        if lay not in GDS_LAYERS:
            problems.append('O5 %s: OBS on unknown layer %s' % (tag, lay))

    # ---- O6: PDN layers must stay clear
    for lay in PDN_LAYERS:
        if lef['obs'].get(lay):
            problems.append('O6 %s: %d OBS rect(s) on %s — that is a PDN layer '
                            '(PDN_VERTICAL_LAYER / HORIZONTAL_LAYER) and '
                            'ERROR_ON_PDN_VIOLATIONS is True'
                            % (tag, len(lef['obs'][lay]), lay))

    all_layers = sorted(set(metal) | set(lef['obs']) | set(pin_by_layer))
    free_sides_all = []
    for lay in all_layers:
        obs_rects = lef['obs'].get(lay, [])
        pins_here = pin_by_layer.get(lay, [])
        reg = metal.get(lay)

        obs = pya.Region()
        for rc in obs_rects:
            obs.insert(to_dbu(rc))
        obs = obs.merged()
        pins = pya.Region()
        for b in pins_here:
            pins.insert(b)
        pins = pins.merged()

        raw = sum((to_dbu(r).right - to_dbu(r).left)
                  * (to_dbu(r).top - to_dbu(r).bottom) for r in obs_rects)
        self_ov = raw - obs.area()
        ov = (obs & pins).area()
        outside = (obs - footprint).area()

        entry = {'n_obs': len(obs_rects), 'n_pins': len(pins_here),
                 'obs_area': obs.area(),
                 'metal_area': reg.area() if reg is not None else 0,
                 'obs_pin_overlap': ov, 'obs_self_overlap': self_ov,
                 'obs_outside_footprint': outside}

        if ov:
            problems.append('O1 %s %s: OBS overlaps a PIN by %d dbu^2 — the PIN '
                            'becomes unusable' % (tag, lay, ov))
        if self_ov:
            problems.append('O3 %s %s: OBS rects overlap by %d dbu^2 — they '
                            'should tile, not stack' % (tag, lay, self_ov))
        if outside:
            problems.append('O4 %s %s: OBS extends %d dbu^2 outside the footprint'
                            % (tag, lay, outside))

        if reg is not None:
            if rule == 'E':
                uncovered = (reg - obs - pins).area()
                extra = (obs - reg).area()
                entry['metal_uncovered'] = uncovered
                entry['obs_not_metal'] = extra
                if uncovered:
                    problems.append('E1 %s %s: %d dbu^2 of drawn metal is neither '
                                    'OBS nor PIN — invisible to the router'
                                    % (tag, lay, uncovered))
                if extra:
                    problems.append('E2 %s %s: OBS covers %d dbu^2 that is not '
                                    'drawn metal — it blocks empty space'
                                    % (tag, lay, extra))
            else:
                missing = (reg - obs).area()
                entry['metal_uncovered'] = missing
                if missing:
                    problems.append('G1 %s %s: %d dbu^2 of drawn metal is not '
                                    'covered by OBS' % (tag, lay, missing))
                if lay in lef['obs'] and obs.area() != footprint.area():
                    problems.append('G2 %s %s: OBS area %d != footprint %d'
                                    % (tag, lay, obs.area(), footprint.area()))
                if lay in lef['obs'] and len(obs_rects) != 1:
                    problems.append('G2 %s %s: %d blocking rects for a '
                                    'geometry-only macro, expected 1'
                                    % (tag, lay, len(obs_rects)))

            if not obs_rects and not pins_here:
                problems.append('O2 %s %s: metal drawn but neither OBS nor PIN — '
                                'the router cannot see it' % (tag, lay))

        # ---- O2 free approach sides for every PIN rectangle on this layer
        d = int(round(CORRIDOR_UM / DBU))
        for b in pins_here:
            sides = {
                'left': pya.Box(b.left - d, b.bottom, b.left, b.top),
                'right': pya.Box(b.right, b.bottom, b.right + d, b.top),
                'below': pya.Box(b.left, b.bottom - d, b.right, b.bottom),
                'above': pya.Box(b.left, b.top, b.right, b.top + d),
            }
            free = []
            for name, cr in sides.items():
                crr = pya.Region(cr)
                # "fully free" = the whole corridor is outside OBS
                if (crr & obs).is_empty():
                    free.append(name)
            entry.setdefault('pins_free_sides', []).append(len(free))
            free_sides_all.append((tag, lay, len(free), free))
            if len(free) < MIN_FREE_SIDES:
                problems.append('O2 %s %s: a PIN rectangle has only %d free '
                                'approach side(s) (%s); need >= %d'
                                % (tag, lay, len(free), ','.join(free) or 'none',
                                   MIN_FREE_SIDES))

        info['layers'][lay] = entry

    info['cell'] = lef['macro']
    info['rule'] = rule
    info['n_pins'] = len(lef['pins'])
    info['n_ports'] = sum(len(p['ports']) for p in lef['pins'])
    info['n_obs'] = sum(len(v) for v in lef['obs'].values())
    info['pins'] = pin_list
    info['free_sides'] = [{'tag': t, 'layer': l, 'n_free': n, 'free': f}
                          for t, l, n, f in free_sides_all]
    info['prboundary_anchored'] = g['prboundary_anchored']
    return info, problems


def odb_crosscheck(expect):
    """Run OpenROAD ODB over the same LEFs; return per-master counts or None.

    `expect` is {cell: (n_pins, n_ports, n_obs)} from the text parse. ODB is a
    third-party reader, so agreement means the numbers are not an artefact of
    our own parser.
    """
    exe = shutil.which('openroad')
    if exe is None:
        return None, 'openroad not on PATH'
    tmp = tempfile.mkdtemp(prefix='lefobs_')
    try:
        tech = os.path.join(tmp, 'min_tech.lef')
        open(tech, 'w', newline='\n').write(MIN_TECH_LEF)
        lefs = '\n'.join('read_lef %s' % os.path.join(OUT, 'struct_%s.lef' % t)
                         for t in TAGS)
        script = os.path.join(tmp, 'q.tcl')
        open(script, 'w', newline='\n').write(
            ODB_TCL % {'tech': tech, 'lefs': lefs,
                       'masters': ' '.join(expect.keys())})
        r = subprocess.run([exe, '-no_init', '-exit', script],
                           cwd=ROOT, capture_output=True)
        out = r.stdout.decode('utf-8', 'replace')
        if 'ODB_BEGIN' not in out:
            return None, 'openroad produced no ODB_BEGIN marker: %s' % (
                r.stderr.decode('utf-8', 'replace')[-300:])
        body = out.split('ODB_BEGIN', 1)[1].split('ODB_END', 1)[0]
        got = {}
        for line in body.splitlines():
            f = line.split()
            if len(f) < 5 or f[1] != 'OK':
                continue
            # field 5 is "met1=4,met2=3" — a comma-joined layer=count list.
            # An earlier version joined f[5:] with spaces, which silently
            # collapsed a two-layer macro to its first layer.
            per_layer = {}
            if len(f) > 5:
                for item in ' '.join(f[5:]).strip('{}').split(','):
                    if '=' in item:
                        k, v = item.split('=', 1)
                        per_layer[k] = int(v)
            got[f[0]] = {'n_pins': int(f[2]), 'n_ports': int(f[3]),
                         'n_obs': int(f[4]), 'obs_per_layer': per_layer,
                         'obs_layers': sorted(per_layer)}
        return got, None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    idx = json.load(open(os.path.join(OUT, 'macro_index.json'),
                         encoding='utf-8'))
    rows, problems = [], []
    for tag in TAGS:
        rule = idx[tag]['obs_rule']
        info, probs = verify_macro(tag, rule)
        problems.extend(probs)
        rows.append({'tag': tag, 'cell': info.get('cell', idx[tag]['cell']),
                     'rule': rule, 'n_pins': info['n_pins'],
                     'n_ports': info['n_ports'], 'n_obs': info['n_obs'],
                     'layers': info['layers'], 'pins': info['pins'],
                     'free_sides': info['free_sides'],
                     'prboundary_anchored': info['prboundary_anchored'],
                     'verdict': 'PASS' if not probs else 'FAIL'})

    # ---- ODB cross-check
    # Totals alone are a weak check: a reader that puts every obstruction on
    # the wrong layer still reports the right total. So the per-layer OBS
    # histogram is compared too.
    text_rows = {r['cell']: r for r in rows}
    expect = {}
    for r in rows:
        expect[r['cell']] = (r['n_pins'], r['n_ports'], r['n_obs'])
    odb, odb_err = odb_crosscheck(expect)
    odb_rows, odb_status = [], ('SKIP' if odb is None else 'RUN')
    if odb is not None:
        for cell, (np_, npo, nob) in expect.items():
            g = odb.get(cell)
            if g is None:
                problems.append('ODB: master %s not found' % cell)
                odb_rows.append({'cell': cell, 'verdict': 'MISSING'})
                continue
            text_pl = {lay: v['n_obs']
                       for lay, v in text_rows[cell]['layers'].items()
                       if v.get('n_obs')}
            ok = (g['n_pins'] == np_ and g['n_ports'] == npo
                  and g['n_obs'] == nob
                  and g.get('obs_per_layer') == text_pl)
            if not ok:
                problems.append(
                    'ODB %s: reader sees pins=%d ports=%d obs=%d per-layer=%s, '
                    'LEF text has pins=%d ports=%d obs=%d per-layer=%s'
                    % (cell, g['n_pins'], g['n_ports'], g['n_obs'],
                       g.get('obs_per_layer'), np_, npo, nob, text_pl))
            odb_rows.append({'cell': cell, 'odb': g,
                             'text': {'n_pins': np_, 'n_ports': npo,
                                      'n_obs': nob, 'obs_per_layer': text_pl},
                             'verdict': 'PASS' if ok else 'FAIL'})
        if any(o.get('verdict') != 'PASS' for o in odb_rows):
            odb_status = 'FAIL'

    # ---- output
    os.makedirs(VAL, exist_ok=True)
    summary = {
        'method': 'Independent re-derivation: LEF text parsed by this script, '
                  'GDS metal rebuilt by this script, and a third-party reader '
                  '(OpenROAD ODB) used as a cross-check. gen_lef.py is not '
                  'imported, so a bug in its region construction cannot hide '
                  'behind its own self-test.',
        'rules': {'E': 'A/B/C1 electrical: OBS = drawn metal - PIN shapes',
                  'G': 'C3/C4/D/E geometry-only: one OBS rect over prBoundary'},
        'min_free_sides': MIN_FREE_SIDES,
        'corridor_um': CORRIDOR_UM,
        'pdn_layers_must_stay_clear': list(PDN_LAYERS),
        'all_pass': not problems,
        'odb_status': odb_status,
        'odb_error': odb_err,
        'problems': problems,
        'macros': rows,
        'odb': odb_rows,
        'scope': 'Local LEF/GDS consistency only. Nothing here shows that a '
                 'router honours the OBS, that pin access succeeds, or that '
                 'DRC/LVS pass — all three need the official CI.',
    }
    json.dump(summary, open(os.path.join(VAL, 'P5_LEF_OBS.json'), 'w',
                            encoding='utf-8'), indent=1, ensure_ascii=False)

    print('%-4s %-20s %-5s %-5s %-6s %-8s %-12s %s'
          % ('tag', 'cell', 'rule', 'pins', 'ports', 'obs_rect', 'free_sides',
             'verdict'))
    print('-' * 78)
    for r in rows:
        fs = [f['n_free'] for f in r['free_sides']]
        print('%-4s %-20s %-5s %-5d %-6d %-8d %-12s %s'
              % (r['tag'], r['cell'], r['rule'], r['n_pins'], r['n_ports'],
                 r['n_obs'], ('min %d' % min(fs)) if fs else '-', r['verdict']))
    print()
    if odb is None:
        print('ODB cross-check: SKIP — %s' % odb_err)
        print('  (not a pass; rerun where openroad is available to close it)')
    else:
        print('ODB cross-check: %s' % odb_status)
        for o in odb_rows:
            if o.get('verdict') == 'MISSING':
                print('  %-20s missing' % o['cell'])
                continue
            d, t = o['odb'], o['text']
            print('  %-20s ODB pins=%d ports=%d obs=%d | text pins=%d ports=%d '
                  'obs=%d  %s'
                  % (o['cell'], d['n_pins'], d['n_ports'], d['n_obs'],
                     t['n_pins'], t['n_ports'], t['n_obs'], o['verdict']))
    print()

    md = ['# LEF OBS 独立复核', '',
          '自动生成：`macros/p3_verify_lef_obs.py`  ',
          '方法：**不 import `gen_lef.py`**。LEF 文本由本脚本自己的解析器读，'
          'GDS 金属由本脚本自己重建，再用 OpenROAD ODB（第三方读取器）对照。', '',
          '> 之所以要独立写一遍：`gen_lef.py` 写文件前的自检用的是它构造 OBS 时'
          '同一批 Region，若金属提取或坐标平移有 bug，自检会跟着一起错。', '',
          '## 规则', '',
          '- **规则 E**（A/B/C1 电气宏）：`OBS = 绘制金属 − PIN 图形`',
          '- **规则 G**（C3/C4/D/E 几何宏）：整个 prBoundary 一个 OBS 矩形，'
          '只加在该宏真正绘制了图形的层上', '',
          'met4/met5 一律不加 OBS：这两层是 PDN 层，'
          '`ERROR_ON_PDN_VIOLATIONS = True`。', '',
          '## 结果', '',
          '| 宏 | cell | 规则 | PIN | PORT | OBS 矩形 | 最少自由接近方向 | 判定 |',
          '|---|---|---|---|---|---|---|---|']
    for r in rows:
        fs = [f['n_free'] for f in r['free_sides']]
        md.append('| %s | `%s` | %s | %d | %d | %d | %s | **%s** |'
                  % (r['tag'], r['cell'], r['rule'], r['n_pins'], r['n_ports'],
                     r['n_obs'], ('%d' % min(fs)) if fs else '—', r['verdict']))
    md += ['', '## 逐宏逐层明细', '']
    for r in rows:
        md.append('### %s — `%s`（规则 %s）' % (r['tag'], r['cell'], r['rule']))
        md.append('')
        md.append('| 层 | OBS | PIN | OBS∩PIN | OBS 自重叠 | 金属未覆盖 | 判定 |')
        md.append('|---|---|---|---|---|---|---|')
        for lay, e in sorted(r['layers'].items()):
            md.append('| %s | %d | %d | %d | %d | %s | %s |'
                      % (lay, e['n_obs'], e['n_pins'], e['obs_pin_overlap'],
                         e['obs_self_overlap'],
                         e.get('metal_uncovered', '—'),
                         'PASS' if (e['obs_pin_overlap'] == 0
                                    and e['obs_self_overlap'] == 0
                                    and e.get('metal_uncovered', 0) == 0)
                         else 'FAIL'))
        if r['free_sides']:
            md.append('')
            md.append('PIN 接近方向：' + '；'.join(
                '%s/%s → %d 个自由方向 (%s)'
                % (f['tag'], f['layer'], f['n_free'], ', '.join(f['free']))
                for f in r['free_sides']))
        md.append('')
    md += ['## ODB 第三方对照', '']
    if odb is None:
        md += ['**SKIP** — %s。' % odb_err, '',
               '这不是通过，是没跑。在有 `openroad` 的环境重跑即可闭合。', '']
    else:
        md += ['| cell | ODB PIN | ODB PORT | ODB OBS | ODB 逐层 | 文本 PIN | 文本 PORT | 文本 OBS | 文本逐层 | 判定 |',
               '|---|---|---|---|---|---|---|---|---|---|']
        for o in odb_rows:
            if o.get('verdict') == 'MISSING':
                md.append('| `%s` | — | — | — | — | — | — | — | — | MISSING |'
                          % o['cell'])
                continue
            d, t = o['odb'], o['text']
            fmt = lambda pl: ', '.join('%s=%d' % (k, v)
                                       for k, v in sorted((pl or {}).items())) or '—'
            md.append('| `%s` | %d | %d | %d | %s | %d | %d | %d | %s | %s |'
                      % (o['cell'], d['n_pins'], d['n_ports'], d['n_obs'],
                         fmt(d.get('obs_per_layer')),
                         t['n_pins'], t['n_ports'], t['n_obs'],
                         fmt(t.get('obs_per_layer')), o['verdict']))
        md.append('')
        md += ['> 逐层列是比较的关键。只对总数是弱检查：一个把全部 OBS 都挂到',
               '> 错误层上的读取器，总数仍然完全正确。', '']
    md += ['## 结论', '']
    if problems:
        md.append('**FAIL** — %d 个问题：' % len(problems))
        for p in problems:
            md.append('- %s' % p)
    else:
        md.append('**PASS** — 七个 LEF 的 OBS 满足 O1–O6 与规则 E/G；'
                  'A/B/C1 的每个 PIN 至少保留 %d 个完全自由的接近方向。'
                  % MIN_FREE_SIDES)
        md.append('')
        md.append('> 本检查只覆盖 LEF/GDS 的一致性。它**不**证明路由器会遵守 '
                  'OBS，也不证明 pin access、DRC 或 LVS 通过——那三项需要官方 CI。')
    open(os.path.join(VAL, 'P5_LEF_OBS.md'), 'w',
         encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')

    print('written v2_validation/P5_LEF_OBS.{json,md}')
    if problems:
        print()
        print('FAIL — %d problem(s):' % len(problems))
        for p in problems:
            print('  !', p)
        return 1
    print('PASS — OBS satisfies O1-O6 and rule E/G for all seven macros')
    if odb is None:
        print('NOTE — ODB cross-check was SKIPPED, not passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
