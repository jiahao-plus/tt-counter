#!/usr/bin/env python3
"""_neg_obs.py — p3_verify_lef_obs.py 的负向对照。

证明 OBS 检查真的能抓到错误，而不是"因为什么都没查所以通过"。

四种扰动，每一种都对应一条被检查的不变量：

  1. obs_covers_pin   A 的某个 OBS 矩形扩到盖住 PIN  → 必须触发 O1
  2. obs_blocks_pin   A 的 PIN 四侧全被 OBS 围死      → 必须触发 O2
  3. obs_missing      A 少一个 OBS 矩形（留裸金属）   → 必须触发 E1
  4. obs_on_met4      C3 加一个 met4 OBS              → 必须触发 O6

扰动只施加在**副本**上，`macros/out/struct_*.lef` 原文件不动。这与
"OBS 必须由 gen_lef.py 的源规则生成"并不冲突：这是检查器的对照实验，
不是交付物。

用法（WSL，cwd 为仓库根）：python3 macros/_neg_obs.py
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
WORK = os.path.join(HERE, '_tmp_neg_obs')

sys.path.insert(0, HERE)
import p3_verify_lef_obs as V   # noqa: E402  (path set above)


def load(tag):
    return open(os.path.join(OUT, 'struct_%s.lef' % tag),
                encoding='utf-8').read()


def write(name, tag, txt):
    os.makedirs(WORK, exist_ok=True)
    p = os.path.join(WORK, '%s.lef' % name)
    open(p, 'w', encoding='utf-8', newline='\n').write(txt)
    return p, os.path.join(OUT, 'struct_%s.gds' % tag)


def obs_block_span(txt):
    """(start, end) character offsets of the OBS body inside the LEF text.

    `$` in MULTILINE matches *before* the newline, so m.end() would point at
    the '\\n' that terminates the `OBS` line. Starting a replacement there
    welds the injected text onto the OBS keyword ("  OBS      LAYER met1 ;"),
    which no longer parses as an OBS block — and the mutation then looks like
    "OBS disappeared", not like the corruption intended. Advance past the
    newline explicitly.
    """
    m = re.search(r'^  OBS$', txt, re.M)
    if m is None:
        raise RuntimeError('no OBS block')
    start = m.end()
    if txt[start:start + 1] == '\n':
        start += 1
    e = re.search(r'^  END$', txt[start:], re.M)
    if e is None:
        raise RuntimeError('OBS block is not closed')
    return start, start + e.start()


# ------------------------------------------------------------------ mutations
def obs_covers_pin(txt):
    """Grow the first met1 OBS rect until it swallows the met1 PIN rect.

    A's met1 PIN is RECT 0.000 0.000 0.140 0.140 (macro-local). Replacing the
    first met1 OBS rectangle with one that starts at 0,0 makes the two
    overlap, which is exactly the O1 condition.
    """
    return re.sub(r'(LAYER met1 ;\n)(\s+RECT 0\.140 0\.000 5\.140 0\.140 ;)',
                  r'\1        RECT 0.000 0.000 5.140 0.140 ;', txt, count=1)


def obs_blocks_pin(txt):
    """Surround A's met1 PIN with a ring of OBS on all four sides."""
    s, e = obs_block_span(txt)
    ring = ('      LAYER met1 ;\n'
            '        RECT -2.000 -2.000 2.000 0.000 ;\n'   # below
            '        RECT -2.000 0.140 2.000 2.140 ;\n'     # above
            '        RECT -2.000 0.000 0.000 0.140 ;\n'     # left
            '        RECT 0.140 0.000 2.140 0.140 ;\n')     # right
    return txt[:s] + ring + txt[s:e] + txt[e:]


def obs_missing(txt):
    """Drop the first met1 OBS rect, leaving a strip of invisible metal."""
    return re.sub(r'\n\s+RECT 0\.140 0\.000 5\.140 0\.140 ;', '', txt, count=1)


def obs_on_met4(txt):
    """Add a met4 OBS to C3 — the PDN layer must stay clear."""
    s, e = obs_block_span(txt)
    return (txt[:s] + '      LAYER met4 ;\n'
            '        RECT 0.000 0.000 10.140 8.240 ;\n' + txt[s:])


CASES = [
    ('obs_covers_pin', 'A', 'E', obs_covers_pin, 'O1'),
    ('obs_blocks_pin', 'A', 'E', obs_blocks_pin, 'O2'),
    ('obs_missing',    'A', 'E', obs_missing,    'E1'),
    ('obs_on_met4',    'C3', 'G', obs_on_met4,   'O6'),
]


def main():
    print('%-18s %-9s %-5s %-6s %s'
          % ('case', 'expects', 'hits', 'caught', 'problems'))
    print('-' * 100)
    all_ok = True
    for name, tag, rule, fn, expect in CASES:
        lp, gp = write(name, tag, fn(load(tag)))
        info, problems = V.verify_macro(tag, rule, lef_path=lp, gds_path=gp)
        hits = sorted({p.split()[0] for p in problems})
        caught = expect in hits
        if not caught:
            all_ok = False
        print('%-18s %-9s %-5s %-6s %s'
              % (name, expect, ','.join(hits) or '-', caught,
                 (problems[0][:70] + '…') if problems else '(none!)'))

    # ---- the unperturbed originals must still pass
    print()
    idx = V.json.load(open(os.path.join(OUT, 'macro_index.json'),
                           encoding='utf-8'))
    clean_bad = []
    for tag in V.TAGS:
        _, probs = V.verify_macro(tag, idx[tag]['obs_rule'])
        if probs:
            clean_bad.append((tag, probs[0]))
    print('unperturbed originals:', 'PASS' if not clean_bad else 'FAIL')
    for tag, p in clean_bad:
        print('  !', tag, p)

    shutil.rmtree(WORK, ignore_errors=True)
    ok = all_ok and not clean_bad
    print()
    print('OBS NEGATIVE CONTROL:',
          'PASS (all four perturbations detected, originals clean)' if ok
          else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
