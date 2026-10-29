#!/usr/bin/env python3
"""p5_intrusion_negative.py — 侵入检测器的负向对照。

一个只会在真实数据上说 PASS 的检查器没有价值。这里构造 4 个已知答案的
合成用例，证明检查器确实能分辨"共存"与"污染"：

  N1 干净          宏足迹内只有宏自己            -> PASS,  clean
  N2 共存          足迹内有一条离得很远的外来线   -> PASS,  COEXIST (gap>0)
  N3 短路污染      外来线接到宏的非 PIN 金属      -> FAIL,  POLLUTED
  N4 PIN 合法连接  外来线接到宏的 PIN 几何        -> PASS,  contact on PIN
  N5 缺图          最终 GDS 少了宏的一段金属      -> 报告 missing（不是污染）

用法：
  python3 macros/p5_intrusion_negative.py
"""
import json
import os
import shutil
import sys
import tempfile

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '.v2ana'))

import p5_intrusion_check as P

DBU = P.DBU
M1 = (68, 20)
M2 = (69, 20)


def build_case(tmp, name, macro_shapes, top_shapes, pins_m1):
    """Write struct_T.gds + struct_T.lef + final.gds + final.def for one case.

    macro_shapes / top_shapes: list of (layer, x0, y0, x1, y1) in um.
    Macro sits at placement (10, 10); its prBoundary is (1,1)-(5,4) local,
    so its footprint is (11,11)-(15,14).
    """
    md = os.path.join(tmp, name)
    os.makedirs(md, exist_ok=True)

    mly = pya.Layout()
    mly.dbu = DBU
    mt = mly.create_cell('research_via1')
    for layer, x0, y0, x1, y1 in macro_shapes:
        mt.shapes(mly.layer(*layer)).insert(
            pya.Box(int(x0 / DBU), int(y0 / DBU), int(x1 / DBU), int(y1 / DBU)))
    mt.shapes(mly.layer(235, 4)).insert(
        pya.Box(int(1 / DBU), int(1 / DBU), int(5 / DBU), int(4 / DBU)))
    mly.write(os.path.join(md, 'struct_A.gds'))

    lef = ['VERSION 5.8 ;', 'MACRO research_via1', '  CLASS BLOCK ;',
           '  ORIGIN 1.000 1.000 ;', '  SIZE 4.000 BY 3.000 ;',
           '  PIN net', '    DIRECTION INOUT ;', '    USE SIGNAL ;',
           '    PORT']
    for x0, y0, x1, y1 in pins_m1:
        lef.append('      LAYER met1 ;')
        lef.append('        RECT %.3f %.3f %.3f %.3f ;' % (x0, y0, x1, y1))
    lef += ['    END', '  END net', 'END research_via1', 'END LIBRARY']
    open(os.path.join(md, 'struct_A.lef'), 'w').write('\n'.join(lef) + '\n')

    fly = pya.Layout()
    fly.dbu = DBU
    ft = fly.create_cell('top')
    for layer, x0, y0, x1, y1 in top_shapes:
        ft.shapes(fly.layer(*layer)).insert(
            pya.Box(int(x0 / DBU), int(y0 / DBU), int(x1 / DBU), int(y1 / DBU)))
    gds = os.path.join(md, 'final.gds')
    fly.write(gds)

    d = ['VERSION 5.8 ;', 'UNITS DISTANCE MICRONS 1000 ;',
         'COMPONENTS 1 ;',
         '    - u_rs_via1 research_via1 + FIXED ( 10000 10000 ) N ;',
         'END COMPONENTS', 'NETS 0 ;', 'END NETS']
    dp = os.path.join(md, 'final.def')
    open(dp, 'w').write('\n'.join(d) + '\n')
    return gds, dp, md


def main():
    tmp = tempfile.mkdtemp(prefix='intr_neg_')
    results = {}

    # macro: M1 wire 2..4 um at y=2 (macro-local), so abs x 12..14, y 12
    macro = [(M1, 1.5, 1.9, 4.5, 2.1)]
    pin = [(0.5, 0.9, 0.64, 1.04)]        # macro-local -> abs (11.5,11.9)-(11.64,12.04)

    cases = {}
    # N1 clean
    cases['N1_clean'] = (macro, list(macro), pin)
    # N2 coexist: foreign M1 far inside the footprint but not touching
    cases['N2_coexist'] = (macro, list(macro) + [(M1, 11.2, 13.5, 12.2, 13.64)], pin)
    # N3 pollution: foreign M1 touching the macro wire at its middle
    cases['N3_pollute'] = (macro, list(macro) + [(M1, 12.9, 12.1, 13.1, 13.0)], pin)
    # N4 legal PIN connection: foreign wire lands on the PIN rect
    cases['N4_on_pin'] = (macro, list(macro) + [(M1, 11.2, 11.9, 12.9, 12.04)], pin)
    # N5 missing: final GDS lacks the macro wire entirely
    cases['N5_missing'] = (macro, [(M1, 11.2, 13.5, 12.2, 13.64)], pin)

    print('=' * 96)
    print('NEGATIVE / BOUNDARY CONTROLS FOR THE INTRUSION DETECTOR')
    print('=' * 96)
    for name, (msh, tsh, p) in cases.items():
        gds, dp, md = build_case(tmp, name, msh, tsh, p)
        # the detector reads macro GDS from the dir we pass; LEF from macros/out
        # -> temporarily point it at this case by copying the LEF over is not
        #    acceptable (it would touch the real tree). Instead run the lower
        #    level functions directly.
        place = P.def_placements(dp)
        fly = pya.Layout(); fly.read(gds)
        ftop = fly.top_cell()
        mly = pya.Layout(); mly.read(os.path.join(md, 'struct_A.gds'))
        mtop = mly.top_cell()
        bb = P.prboundary_box(mly, mtop)
        px, py, _o = place['research_via1']
        ax0, ay0 = px + bb.left * DBU, py + bb.bottom * DBU
        clip = pya.Region(pya.Box(int(round(ax0 / DBU)), int(round(ay0 / DBU)),
                                  int(round((ax0 + bb.width() * DBU) / DBU)),
                                  int(round((ay0 + bb.height() * DBU) / DBU))))
        final_r = P.collect(fly, ftop, P.LAYERS, clip=clip)
        self_r = {k: (v.moved(int(round(px / DBU)), int(round(py / DBU))) & clip)
                  for k, v in P.collect(mly, mtop, P.LAYERS).items()}
        pins, org = P.lef_pins(os.path.join(md, 'struct_A.lef'), P.LAYERS)
        pins_abs = {k: [b.moved(int(round((px + org[0]) / DBU)),
                                int(round((py + org[1]) / DBU))) for b in v]
                    for k, v in pins.items()}
        extra = final_r['M1'] - self_r['M1']
        missing = self_r['M1'] - final_r['M1']
        gap = P.min_gap(extra, self_r['M1'])
        tol = int(round(P.TOUCH_TOL_UM / DBU))
        pin_reg = pya.Region()
        for b in pins_abs.get('M1', []):
            pin_reg.insert(b)
        pin_reg.merge()
        pin_dil = pin_reg.sized(tol) if not pin_reg.is_empty() else pya.Region()
        sdil = self_r['M1'].sized(tol)
        on_pin = off_pin = 0
        for poly in extra.each():
            pr = pya.Region(poly)
            if sdil.is_empty() or (pr & sdil).is_empty():
                continue
            if not pin_dil.is_empty() and not (pr & pin_dil).is_empty():
                on_pin += 1
            else:
                off_pin += 1
        results[name] = {
            'foreign_polys': len(list(extra.each())),
            'missing_polys': len(list(missing.each())),
            'gap_um': None if gap is None else round(gap, 3),
            'contact_on_pin': on_pin,
            'contact_off_pin': off_pin,
            'polluted': off_pin > 0,
        }
        r = results[name]
        print('%-14s foreign=%d missing=%d gap=%-8s onPIN=%d offPIN=%d %s'
              % (name, r['foreign_polys'], r['missing_polys'],
                 ('n/a' if r['gap_um'] is None else '%.3f' % r['gap_um']),
                 r['contact_on_pin'], r['contact_off_pin'],
                 'POLLUTED' if r['polluted'] else 'ok'))

    # ---- assertions ----------------------------------------------------
    exp = {
        'N1_clean':     dict(foreign_polys=0, polluted=False),
        'N2_coexist':   dict(foreign_polys=1, polluted=False),
        'N3_pollute':   dict(polluted=True, contact_off_pin=1),
        'N4_on_pin':    dict(polluted=False, contact_on_pin=1),
        'N5_missing':   dict(foreign_polys=1, missing_polys=1, polluted=False),
    }
    print()
    ok = True
    for name, want in exp.items():
        got = results[name]
        for k, v in want.items():
            good = got[k] == v
            ok = ok and good
            print('  %-14s %-16s expect %-6s got %-6s %s'
                  % (name, k, v, got[k], 'PASS' if good else 'FAIL'))
    # N2 gap must be a real positive number, not saturated at the search cap
    g2 = results['N2_coexist']['gap_um']
    good = g2 is not None and 0.5 < g2 < 2.5
    ok = ok and good
    print('  %-14s %-16s expect %-6s got %-6s %s'
          % ('N2_coexist', 'gap in (0.5,2.5)', 'yes', g2,
             'PASS' if good else 'FAIL'))
    print()
    print('ALL CONTROLS:', 'PASS' if ok else 'FAIL')
    json.dump(results, open(os.path.join(HERE, 'out', 'intrusion_neg_controls.json'),
                            'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
