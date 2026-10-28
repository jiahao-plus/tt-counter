#!/usr/bin/env python3
"""_neg_gds_identity.py — p3_gds_identity 的负向对照。

证明摘要真的能识别几何变化。三个扰动都**不改变图形数量**，所以上一轮那种
"只比每层图形数"的检查会全部漏掉。

Three perturbations of one macro's GDS, each of which a shape-COUNT check
would miss:
  1. translate one wire by 1 dbu      (count unchanged)
  2. add then remove nothing -- swap a box for an identical polygon (count same)
  3. widen one wire by 1 dbu          (count unchanged)
"""
import sys, os, shutil, subprocess, importlib.util
import pya

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("gi", os.path.join(ROOT, "macros", "p3_gds_identity.py"))
gi = importlib.util.module_from_spec(spec); spec.loader.exec_module(gi)

SRC = os.path.join(ROOT, 'macros', 'out', 'struct_A.gds')
WORK = os.path.join(ROOT, 'macros', '_tmp_neg_identity')
os.makedirs(WORK, exist_ok=True)

base = gi.macro_digest(SRC)
print("baseline digest:", base['digest'][:16], " shapes:", sum(v['n_shapes'] for v in base['layers'].values()))

# A control for the raw-byte check as well: the UNPERTURBED file, re-written by
# pya, must differ from the original only inside date records. Without this,
# "outside dates = NONE" below could just mean the byte check never fires.
_base_bytes = open(SRC, 'rb').read()
_rt = os.path.join(WORK, 'roundtrip.gds')
_ly = pya.Layout(); _ly.read(SRC); _ly.write(_rt)
_rb = gi.raw_byte_diff(_base_bytes, open(_rt, 'rb').read())
print("  %-18s diffbytes=%s outside_dates=%s  %s"
      % ('pya roundtrip', _rb.get('n_diff'), _rb['outside'] or 'NONE',
         'OK' if _rb['ok'] else 'UNEXPECTED'))

def perturb(name, fn):
    p = os.path.join(WORK, 'neg_%s.gds' % name)
    ly = pya.Layout(); ly.read(SRC)
    fn(ly, ly.top_cell())
    ly.write(p)
    d = gi.macro_digest(p)
    n = sum(v['n_shapes'] for v in d['layers'].values())
    caught = d['digest'] != base['digest']
    # the byte-level check must fire on a real geometry change too
    rb = gi.raw_byte_diff(_base_bytes, open(p, 'rb').read())
    print("  %-18s shapes=%d (base %d)  digest=%-16s  CAUGHT=%-5s bytes_outside_dates=%s"
          % (name, n, sum(v['n_shapes'] for v in base['layers'].values()),
             d['digest'][:16], caught,
             rb.get('reason') or len(rb['outside'])))
    return caught

def move_one(ly, top):
    li = ly.find_layer(68, 20)
    sh = list(top.shapes(li).each())[0]
    b = sh.box
    top.shapes(li).erase(sh)
    top.shapes(li).insert(pya.Box(b.left, b.bottom+1, b.right, b.top+1))

def widen_one(ly, top):
    li = ly.find_layer(68, 20)
    sh = list(top.shapes(li).each())[0]
    b = sh.box
    top.shapes(li).erase(sh)
    top.shapes(li).insert(pya.Box(b.left, b.bottom, b.right, b.top+1))

def flip_symmetry(ly, top):
    # change SYMMETRY-ish: mirror the whole cell in X (transforms, same count)
    top.transform(pya.Trans(pya.Trans.M0))

results = [perturb('translate_1dbu', move_one),
           perturb('widen_1dbu', widen_one),
           perturb('mirror_x', flip_symmetry)]
print()
print("NEGATIVE CONTROL:", "PASS (all perturbations detected)" if all(results) else "FAIL")
sys.exit(0 if all(results) else 1)
