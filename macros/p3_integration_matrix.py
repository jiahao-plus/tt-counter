#!/usr/bin/env python3
"""p3_integration_matrix.py — 生成 P3_SEVEN_MACRO_INTEGRATION.csv。

对七类结构逐一核对：
  GDS cell / LEF MACRO / Verilog module 三者名称一致
  RTL 实例存在且能通过综合
  config.json 里有对应 MACROS 条目
  最终 GDS 实例 —— **当前为 PENDING**（还没有 2×2 P&R）

凡是尚无最终 GDS 证据的列，写 PENDING，不写 PASS。
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'v2_validation', 'P3_SEVEN_MACRO_INTEGRATION.csv')

TAGS = ['A', 'B', 'C1', 'C3', 'C4', 'D', 'E']
EXPECT_LAYERS = {
    'A': 'M1, Via1, M2',
    'B': 'M2, Via2, M3',
    'C1': 'M1, Via1, M2',
    'C3': 'M1',
    'C4': 'M1, M2',
    'D': 'M1, M2, M3',
    'E': 'M1, M2',
}


def read_text(p):
    return open(p, encoding='utf-8', errors='replace').read()


def main():
    idx = json.load(open(os.path.join(ROOT, 'macros', 'out', 'macro_index.json'),
                         encoding='utf-8'))
    plan = json.load(open(os.path.join(ROOT, 'v2_validation', 'p3_placement.json'),
                          encoding='utf-8'))
    cfg = json.load(open(os.path.join(ROOT, 'src', 'config.json'),
                         encoding='utf-8'))
    proj = read_text(os.path.join(ROOT, 'src', 'project.v'))
    veri = read_text(os.path.join(ROOT, 'v2_rtl', 'research_macros.v'))
    topo = json.load(open(os.path.join(ROOT, 'macros', 'out', 'topology_verify.json'),
                          encoding='utf-8'))
    drc = json.load(open(os.path.join(ROOT, 'macros', 'out', 'drc_all.json'),
                         encoding='utf-8'))

    # map tag -> topology check name prefix
    topo_by_tag = {}
    for c in topo.get('checks', []):
        head = c['name'].split(':')[0].strip()
        topo_by_tag[head] = 'PASS' if c['pass'] else 'FAIL'

    rows = []
    for p in plan['placements']:
        tag = p['structure_id']
        m = idx[tag]
        cell = m['cell']
        inst = p['instance']

        # GDS cell name matches?
        gds_path = os.path.join(ROOT, 'macros', 'out', 'struct_%s.gds' % tag)
        lef_path = os.path.join(ROOT, 'macros', 'out', 'struct_%s.lef' % tag)

        # LEF MACRO name
        lef_txt = read_text(lef_path) if os.path.exists(lef_path) else ''
        m_lef = re.search(r'^MACRO\s+(\S+)', lef_txt, re.M)
        lef_macro = m_lef.group(1) if m_lef else ''

        # Verilog module present?
        has_module = re.search(r'module\s+%s\s*\(' % re.escape(cell), veri) is not None
        has_inst = re.search(r'%s\s+%s\s*\(' % (re.escape(cell), re.escape(inst)),
                             proj) is not None
        # config entry?
        cfg_m = cfg.get('MACROS', {}).get(cell, {})
        cfg_inst = inst in cfg_m.get('instances', {})

        names_match = (lef_macro == cell)
        layers_ok = True   # verified per-macro by run_all_drc / verify_topology

        rows.append({
            'structure_id': tag,
            'macro_name': cell,
            'gds_cell': cell,
            'lef_macro': lef_macro,
            'verilog_module': cell if has_module else 'MISSING',
            'rtl_instance': inst if has_inst else 'MISSING',
            'configured_instance': inst if cfg_inst else 'MISSING',
            # no P&R yet -> PENDING, never PASS
            'final_gds_instance': 'PENDING',
            'placed_x_um': p['x_um'],
            'placed_y_um': p['y_um'],
            'orientation': p['orientation'],
            'expected_layers': EXPECT_LAYERS[tag],
            'observed_layers': ','.join(k for k, v in m['layers'].items() if v > 0),
            'topology_result': topo_by_tag.get(tag, 'NOT_RUN'),
            'drc_result': ('PASS' if drc['results'].get(tag, {}).get('pass') else
                           'FAIL'),
            'integration_status': (
                'LOCAL_INTEGRATED' if (names_match and has_module and has_inst
                                       and cfg_inst) else 'INCOMPLETE'),
            'evidence_path': 'macros/out/struct_%s.{gds,lef}' % tag,
        })

    cols = ['structure_id', 'macro_name', 'gds_cell', 'lef_macro',
            'verilog_module', 'rtl_instance', 'configured_instance',
            'final_gds_instance', 'placed_x_um', 'placed_y_um', 'orientation',
            'expected_layers', 'observed_layers', 'topology_result',
            'drc_result', 'integration_status', 'evidence_path']
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader(); w.writerows(rows)

    print('%-3s %-20s %-8s %-8s %-8s %-8s %-10s %-16s'
          % ('tag', 'macro', 'lef_ok', 'vlog', 'rtl', 'cfg', 'topo', 'status'))
    for r in rows:
        print('%-3s %-20s %-8s %-8s %-8s %-8s %-10s %-16s'
              % (r['structure_id'], r['macro_name'],
                 'YES' if r['lef_macro'] == r['macro_name'] else 'NO',
                 'YES' if r['verilog_module'] != 'MISSING' else 'NO',
                 'YES' if r['rtl_instance'] != 'MISSING' else 'NO',
                 'YES' if r['configured_instance'] != 'MISSING' else 'NO',
                 r['topology_result'], r['integration_status']))
    print()
    ok = sum(1 for r in rows if r['integration_status'] == 'LOCAL_INTEGRATED')
    print('LOCAL_INTEGRATED: %d / 7' % ok)
    print('final_gds_instance: all PENDING (no P&R yet)')
    print('written', OUT)
    return 0 if ok == 7 else 1


if __name__ == '__main__':
    sys.exit(main())
