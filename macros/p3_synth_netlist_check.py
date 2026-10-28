#!/usr/bin/env python3
"""p3_synth_netlist_check.py — 综合后网表的七宏实例检查。

官方失败（OpenROAD.CheckMacroInstances）的根因是综合把四个电气宏删掉了。
本脚本生成**真实综合后网表**，逐实例检查它是否真的还在、名字对不对、
端口连到哪个 wire。

流程刻意贴近官方：yosys `synth` -> `flatten` -> `opt`，而不是只跑
proc/opt（我之前只跑 proc;opt，所以本地"通过"而官方失败）。

局限（必须写进报告）：
  本地 yosys 是 0.69（conda-forge），官方 LibreLane 3.0.14 用 yosys 0.62。
  行为在 keep 属性上一致（已用对照实验确认），但**不是完全等效**。

输出：
  v2_validation/synth_netlist.v         综合后网表
  v2_validation/P3_SYNTH_INSTANCES.json 实例检查结果
  v2_validation/P3_SYNTH_INSTANCES.md
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VAL = os.path.join(ROOT, 'v2_validation')
NETLIST = os.path.join(VAL, 'synth_netlist.v')

# instance name -> (macro cell, required ports)
#
# α′ interface: A / B / C1 expose exactly one port, `net`; everything else has
# no ports. The port name here must match the LEF PIN name and the Verilog port
# name character for character — that is what p3_assert_pin_port_contract.py
# enforces across all three sources.
EXPECTED = {
    'u_rs_via1':     ('research_via1',     ['net']),
    'u_rs_via2':     ('research_via2',     ['net']),
    'u_rs_branch':   ('research_branch',   ['net']),
    'u_rs_near':     ('research_near',     []),
    'u_rs_cross':    ('research_cross',    []),
    'u_rs_dense':    ('research_dense',    []),
    'u_rs_fiducial': ('research_fiducial', []),
}

YS = """
read_verilog -sv src/project.v src/pwm.v src/LFSR_Design.v src/research_macros.v
synth -top tt_um_jiahao_plus_counter
flatten
opt
write_verilog -noattr {netlist}
stat
"""


def run_yosys():
    script = YS.format(netlist=NETLIST.replace('\\', '/'))
    p = subprocess.run(['yosys', '-p', script], cwd=ROOT,
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def parse_instances(netlist_path):
    """Find `<cell> <inst> ( .port(net), ... );` in the written netlist."""
    txt = open(netlist_path, encoding='utf-8', errors='replace').read()
    found = {}
    for cell in {c for c, _ in EXPECTED.values()}:
        for m in re.finditer(
                r'\b%s\s+(\w+)\s*\((.*?)\)\s*;' % re.escape(cell), txt, re.S):
            inst, body = m.group(1), m.group(2)
            ports = dict(re.findall(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', body))
            found[inst] = {'cell': cell, 'ports': ports}
    return found


def main():
    os.makedirs(VAL, exist_ok=True)
    rc, log = run_yosys()
    open(os.path.join(VAL, 'synth_full.log'), 'w',
         encoding='utf-8', newline='\n').write(log)

    if not os.path.exists(NETLIST):
        print('FAIL: yosys did not write the netlist'); return 1

    found = parse_instances(NETLIST)
    rows, problems = [], []

    for inst, (cell, ports) in EXPECTED.items():
        got = found.get(inst)
        if not got:
            problems.append('%s (%s): MISSING from synthesized netlist'
                            % (inst, cell))
            rows.append({'instance': inst, 'cell': cell, 'present': False,
                         'cell_ok': False, 'ports_ok': False, 'ports': {}})
            continue
        cell_ok = (got['cell'] == cell)
        if not cell_ok:
            problems.append('%s: cell %s != expected %s'
                            % (inst, got['cell'], cell))
        missing_ports = [p for p in ports if p not in got['ports']]
        if missing_ports:
            problems.append('%s: missing ports %s' % (inst, missing_ports))
        unconnected = [p for p in ports
                       if p in got['ports'] and got['ports'][p] in ('', '()')]
        if unconnected:
            problems.append('%s: ports left unconnected %s' % (inst, unconnected))
        rows.append({'instance': inst, 'cell': cell, 'present': True,
                     'cell_ok': cell_ok,
                     'ports_ok': not missing_ports and not unconnected,
                     'ports': got['ports']})

    # n_instances seen per cell in the stat block
    stat_counts = {}
    for m in re.finditer(r'^\s+(\d+)\s+(research_\w+)\s*$', log, re.M):
        stat_counts[m.group(2)] = int(m.group(1))

    res = {
        'yosys_version': subprocess.run(['yosys', '-V'], capture_output=True,
                                        text=True).stdout.strip(),
        'flow': 'synth -top ...; flatten; opt; write_verilog -noattr',
        'equivalence_caveat': 'Local yosys differs from the official '
                              'LibreLane 3.0.14 / yosys 0.62 toolchain. The '
                              'keep attribute behaves identically in a '
                              'control experiment, but this is NOT a '
                              'byte-equivalent reproduction of the official '
                              'synthesis.',
        'netlist': NETLIST,
        'stat_counts': stat_counts,
        'instances': rows,
        'problems': problems,
        'all_present': len(problems) == 0,
    }
    json.dump(res, open(os.path.join(VAL, 'P3_SYNTH_INSTANCES.json'), 'w',
                        encoding='utf-8'), indent=1, ensure_ascii=False)

    md = ['# 综合后网表的七宏实例检查', '',
          '自动生成：`macros/p3_synth_netlist_check.py`  ',
          '流程：`synth` → `flatten` → `opt` → `write_verilog`（贴近官方，',
          '而不是只跑 `proc; opt`）', '',
          '| 实例 | 宏 | 存在 | cell 正确 | 端口正确 | 端口连接 |',
          '|---|---|---|---|---|---|']
    for r in rows:
        ports = ', '.join('%s=%s' % (k, v) for k, v in r['ports'].items()) or '—'
        md.append('| `%s` | `%s` | %s | %s | %s | %s |'
                  % (r['instance'], r['cell'],
                     '✓' if r['present'] else '✗',
                     '✓' if r.get('cell_ok') else '✗',
                     '✓' if r.get('ports_ok') else '✗', ports))
    md += ['', '## 结论', '']
    if problems:
        md.append('**FAIL** — %d 个问题：' % len(problems))
        for p in problems:
            md.append('- %s' % p)
    else:
        md.append('**PASS** — 七个实例在 synth + flatten + opt 之后全部存在，')
        md.append('cell 类型与端口连接均正确。')
    md += ['', '> `(* keep *)` 只保住了实例、名字和端口连接。它**不**证明',
           '> 物理宏接线正确——那是 LVS 的问题，仍未验证。']
    open(os.path.join(VAL, 'P3_SYNTH_INSTANCES.md'), 'w',
         encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')

    print('yosys:', res['yosys_version'][:60])
    print('%-16s %-18s %-6s %-6s %s'
          % ('instance', 'cell', 'exists', 'ports', 'connections'))
    for r in rows:
        conn = ', '.join('%s=%s' % (k, v) for k, v in r['ports'].items()) or '-'
        print('%-16s %-18s %-6s %-6s %s'
              % (r['instance'], r['cell'],
                 'YES' if r['present'] else 'NO',
                 'OK' if r.get('ports_ok') else 'BAD', conn[:50]))
    print()
    if problems:
        print('FAIL (%d):' % len(problems))
        for p in problems:
            print('  !', p)
    else:
        print('ALL SEVEN INSTANCES PRESENT AFTER synth+flatten+opt')
    print('netlist:', NETLIST)
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
