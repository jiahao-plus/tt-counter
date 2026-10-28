#!/usr/bin/env python3
"""p3_patch_config.py — 向 src/config.json 添加七宏的 MACROS 配置。

**关键实现约束**：Tiny Tapeout 的 config.json 用重复的 "//" 键写注释。
用 json.load + json.dump 往返会把所有 "//" 注释合并成一条（Python 的 dict
不允许重复键），彻底破坏该文件的注释结构。第一版补丁脚本就是这么做的，
发现后已撤销。

本脚本改为**文本插入**：在最后一个 "}" 之前插入新的键值对，其余内容
逐字节保留。写入前用 json.loads 校验结果仍是合法 JSON。

语法来源：Tiny Tapeout 官方 silicon-art 指南（实测抓取）
  "MACROS": {
    "<macro>": {
      "instances": { "<inst>": { "location": [x, y], "orientation": "N" } },
      "gds": ["dir::../macros/out/struct_X.gds"],
      "lef": ["dir::../macros/out/struct_X.lef"]
    }
  }

**不设置 ERROR_ON_DISCONNECTED_PINS:false** —— 那是全局开关，会同时掩盖
A/B/C1 三个电气宏的引脚错误。改用 IGNORE_DISCONNECTED_MODULES 精确豁免
C3/C4/D/E 四个无端口几何宏。

也不设置 RUN_LVS / RUN_PDN / ERROR_ON_PDN_VIOLATIONS —— 保持默认（开启）。

用法：python3 macros/p3_patch_config.py [--check]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CFG = os.path.join(ROOT, 'src', 'config.json')
PLACEMENT = os.path.join(ROOT, 'v2_validation', 'p3_placement.json')

NON_ELECTRICAL = {'research_near', 'research_cross', 'research_dense',
                  'research_fiducial'}

MARKER = '"_v2_macros_injected"'

# The marker key is used only for idempotent re-patching. LibreLane warns about
# unknown keys, so the marker is stripped on the way out; a clean config.json
# never contains it. Re-running this script is still idempotent because the
# MACROS block itself is detected and replaced.
STRIP_MARKER_ON_WRITE = True


def build_macros():
    plan = json.load(open(PLACEMENT, encoding='utf-8'))
    macros = {}
    for p in plan['placements']:
        macros[p['macro_name']] = {
            'instances': {
                p['instance']: {
                    'location': [p['x_um'], p['y_um']],
                    'orientation': p['orientation'],
                }
            },
            'gds': ['dir::../macros/out/struct_%s.gds' % p['structure_id']],
            'lef': ['dir::../macros/out/struct_%s.lef' % p['structure_id']],
        }
    return macros


def main():
    check_only = '--check' in sys.argv
    text = open(CFG, encoding='utf-8', newline='').read()

    macros = build_macros()
    ignored = []
    for name, m in macros.items():
        if name in NON_ELECTRICAL:
            ignored.append(name)
            ignored.extend(m['instances'].keys())

    # every gds/lef must exist
    missing = []
    for name, m in macros.items():
        for key in ('gds', 'lef'):
            rel = m[key][0].replace('dir::', '')
            p = os.path.normpath(os.path.join(ROOT, 'src', rel))
            if not os.path.exists(p):
                missing.append(p)
    if missing:
        print('FAIL: missing macro files:')
        for p in missing:
            print('  ', p)
        return 1

    print('macros to configure : %d' % len(macros))
    for name in sorted(macros):
        m = macros[name]
        inst = list(m['instances'])[0]
        loc = m['instances'][inst]['location']
        print('  %-20s inst=%-16s loc=[%6.2f, %6.2f] %s'
              % (name, inst, loc[0], loc[1],
                 'NON_ELECTRICAL' if name in NON_ELECTRICAL else 'electrical'))
    print('IGNORE_DISCONNECTED_MODULES: %s' % ignored)
    print('ERROR_ON_DISCONNECTED_PINS: NOT SET (would be a global mute)')

    # No marker key in the written block: LibreLane warns on unknown keys.
    # The explanation lives here in the script instead.
    block = (
        ',\n'
        '  "MACROS": %s,\n'
        '  "IGNORE_DISCONNECTED_MODULES": %s\n'
        % (json.dumps(macros, indent=4, ensure_ascii=False).replace('\n', '\n  '),
           json.dumps(ignored, ensure_ascii=False))
    )

    # idempotent: strip a previously injected block first
    # Idempotency: strip any previously injected block (marker + MACROS +
    # IGNORE) before re-inserting. The previous version deleted from the marker
    # to end of file, which would also have eaten MACROS; this version matches
    # the exact three keys it manages.
    def _strip_injected(t):
        """Remove the three keys this script owns, using brace/bracket counting.

        A non-greedy `.*?\\n\\s*}` regex stops at the first nested closing brace
        and leaves half of the MACROS object behind — that produced invalid JSON
        on the second run. Counting is the only reliable way here.
        """
        def cut_key(text, key):
            # The key may or may not be preceded by a comma: whichever key lands
            # first in the injected block has no comma before it. Matching a
            # required comma is why an earlier attempt left MACROS in place
            # (it removed 0 chars) and produced invalid JSON.
            m = re.search(r',?\s*\n\s*"%s"\s*:\s*' % re.escape(key), text)
            if not m:
                return text
            i = m.end()
            if i >= len(text):
                return text
            opener = text[i]
            if opener not in '{[':
                # string / scalar: run to end of line
                j = text.find('\n', i)
                return text[:m.start()] + text[j if j >= 0 else len(text):]
            closer = '}' if opener == '{' else ']'
            depth = 0
            j = i
            while j < len(text):
                c = text[j]
                if c == opener:
                    depth += 1
                elif c == closer:
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            return text[:m.start()] + text[j:]

        t = cut_key(t, '_v2_macros_injected')
        t = cut_key(t, 'MACROS')
        t = cut_key(t, 'IGNORE_DISCONNECTED_MODULES')
        # a dangling comma before the closing brace would be invalid
        t = re.sub(r',\s*(\n\s*\}\s*$)', r'\1', t, flags=re.S)
        return t

    if MARKER in text or '"MACROS"' in text:
        text = _strip_injected(text)

    # insert before the final closing brace
    idx = text.rstrip().rfind('}')
    if idx < 0:
        print('FAIL: no closing brace in', CFG); return 1
    new_text = text[:idx].rstrip()
    if not new_text.endswith(','):
        new_text += block
    else:
        new_text += block.lstrip(',')
    new_text += '\n}\n'

    # validate
    try:
        parsed = json.loads(new_text)
    except Exception as e:
        print('FAIL: result is not valid JSON:', e)
        return 1
    assert len(parsed['MACROS']) == len(macros)
    assert 'ERROR_ON_DISCONNECTED_PINS' not in parsed
    assert 'RUN_LVS' not in parsed
    assert 'RUN_PDN' not in parsed
    # comments preserved?
    n_comment_keys = text.count('"//"')
    if ('"//"' not in new_text) or new_text.count('"//"') < n_comment_keys:
        print('FAIL: comment keys lost (%d -> %d)'
              % (n_comment_keys, new_text.count('"//"')))
        return 1

    if check_only:
        print()
        print('--check: JSON valid, %d "//" comment keys preserved, '
              '%d macros' % (new_text.count('"//"'), len(parsed['MACROS'])))
        return 0

    open(CFG, 'w', encoding='utf-8', newline='\n').write(new_text)
    print()
    print('patched %s by TEXT INJECTION (comments preserved: %d "//" keys)'
          % (CFG, new_text.count('"//"')))
    print('  MACROS: %d   IGNORE_DISCONNECTED_MODULES: %d'
          % (len(parsed['MACROS']), len(parsed['IGNORE_DISCONNECTED_MODULES'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
