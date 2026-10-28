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
A/B/C1/C3 四个电气宏的引脚错误。改用 IGNORE_DISCONNECTED_MODULES 精确豁免
C4/D/E 三个非电气宏。

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

NON_ELECTRICAL = {'research_cross', 'research_dense', 'research_fiducial'}

MARKER = '"_v2_macros_injected"'


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

    block = (
        ',\n'
        '  "_v2_macros_injected": "Added by macros/p3_patch_config.py for the '
        'V2 2x2 research structures. ERROR_ON_DISCONNECTED_PINS is deliberately '
        'NOT set: only IGNORE_DISCONNECTED_MODULES is used so the four '
        'electrical macros keep real pin checks.",\n'
        '  "MACROS": %s,\n'
        '  "IGNORE_DISCONNECTED_MODULES": %s\n'
        % (json.dumps(macros, indent=4, ensure_ascii=False).replace('\n', '\n  '),
           json.dumps(ignored, ensure_ascii=False))
    )

    # idempotent: strip a previously injected block first
    if MARKER in text:
        text = re.sub(r',\n  "_v2_macros_injected".*?\n?$', '\n', text,
                      flags=re.S)
        if not text.rstrip().endswith('}'):
            text = text.rstrip() + '\n}\n'

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
