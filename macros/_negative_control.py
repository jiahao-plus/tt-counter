"""Negative control: deliberately illegal geometry MUST fail the DRC checker.
If this passes, the checker is broken (not the design)."""
import pya, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom_drc

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')

def make(name, build):
    ly = pya.Layout(); ly.dbu = 0.001
    top = ly.create_cell(name)
    build(ly, top)
    p = os.path.join(OUT, name + '.gds')
    ly.write(p)
    return p

def um(v): return int(round(v*1000))

def too_narrow(ly, top):
    li = ly.layer(68,20)
    top.shapes(li).insert(pya.Box(um(0), um(0), um(5), um(0.10)))   # 0.10 < 0.14

def too_close(ly, top):
    li = ly.layer(68,20)
    top.shapes(li).insert(pya.Box(um(0), um(0), um(5), um(0.14)))
    top.shapes(li).insert(pya.Box(um(0), um(0.20), um(5), um(0.34)))  # gap 0.06 < 0.14

def bad_enclosure(ly, top):
    m1 = ly.layer(68,20); v = ly.layer(68,44); m2 = ly.layer(69,20)
    top.shapes(v).insert(pya.Box(um(5), um(5), um(5.15), um(5.15)))
    # landing much smaller than cut+2*0.055
    top.shapes(m1).insert(pya.Box(um(5), um(5), um(5.15), um(5.15)))
    top.shapes(m2).insert(pya.Box(um(4), um(4), um(6), um(6)))

cases = [('neg_too_narrow', too_narrow),
         ('neg_too_close', too_close),
         ('neg_bad_enclosure', bad_enclosure)]

ok = True
for name, fn in cases:
    p = make(name, fn)
    r = geom_drc.run(p, verbose=False)
    caught = not r['pass']
    print('%-20s violations=%-3d  caught=%s' % (name, r['n_violations'], caught))
    if not caught: ok = False
print()
print('NEGATIVE CONTROL:', 'PASS (checker detects violations)' if ok else 'FAIL (checker misses violations)')
sys.exit(0 if ok else 1)
