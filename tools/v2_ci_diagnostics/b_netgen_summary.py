"""Part B, Q4: reconcile netgen's own device/nets numbers with the metric.

The 44 metric is authoritative. This script explains, from the artefacts,
WHERE the 21 device difference physically comes from, per cell class.

It uses the Subcircuit summary table in lvs.netgen.rpt, whose rows are
  <class> (<devices>-><instances>)
so we can separate "class exists with different device count" from
"class has a different instance count".
"""
import os
import re

from paths import RUN as BASE
RPT = os.path.join(BASE, '66-netgen-lvs/reports/lvs.netgen.rpt')
txt = open(RPT, encoding='utf-8', errors='replace').read()

i = txt.find('Subcircuit summary:')
j = txt.find('NET mismatches', i)
blk = txt[i:j]

ROW = re.compile(r'^(?P<c1>(?:\S.*?)?)\|(?P<c2>.*)$', re.M)
rows = []
for line in blk.splitlines():
    if '|' not in line:
        continue
    a, b = line.split('|', 1)
    a, b = a.rstrip(), b.strip()
    if a.startswith('Circuit 1') or a.startswith('-'):
        continue
    ca = re.match(r'^(?P<cls>\S+)\s+\((?P<dev>\d+)(?:->(?P<inst>\d+))?\)'
                  r'(?P<rest>.*)$', a)
    cb = re.match(r'^(?P<cls>\S+)\s+\((?P<dev>\d+)(?:->(?P<inst>\d+))?\)'
                  r'(?P<rest>.*)$', b)
    if ca and cb:
        rows.append((ca.group('cls'), int(ca.group('dev')),
                     int(ca.group('inst')) if ca.group('inst') else None,
                     int(cb.group('dev')),
                     int(cb.group('inst')) if cb.group('inst') else None,
                     'Mismatch' in ca.group('rest') or 'Mismatch' in cb.group('rest')))

print('=' * 78)
print('NETGEN SUBCIRCUIT SUMMARY -- parsed')
print('=' * 78)
print('%-34s %8s %8s %8s %8s  %s'
      % ('class', 'C1_dev', 'C1_inst', 'C2_dev', 'C2_inst', 'flag'))
print('-' * 78)
for r in rows:
    print('%-34s %8d %8s %8d %8s  %s'
          % (r[0], r[1], r[2] if r[2] is not None else '-',
             r[3], r[4] if r[4] is not None else '-',
             'MISMATCH' if r[5] else ''))

print()
print('rows parsed: %d' % len(rows))

# Which rows are flagged?
print()
print('=' * 78)
print('FLAGGED CLASSES ONLY -- the physical origin of device_difference = 21')
print('=' * 78)
fl = [r for r in rows if r[5]]
for r in fl:
    print('  %-30s C1: devices=%-6d inst=%-6s | C2: devices=%-6d inst=%-6s'
          % (r[0], r[1], r[2], r[3], r[4]))
    if r[2] is not None and r[4] is not None:
        print('      delta devices = %+d   delta instances = %+d'
              % (r[3] - r[1], r[4] - r[2]))
if not fl:
    print('  (none parsed -- summary format assumption wrong)')

print()
print('=' * 78)
print('TOTALS FROM THE SUMMARY TABLE')
print('=' * 78)
m = re.search(r'^Number of devices:\s*(\d+).*?\|\s*Number of devices:\s*(\d+)',
              blk, re.M)
if m:
    d1, d2 = int(m.group(1)), int(m.group(2))
    print('  Number of devices : C1=%d  C2=%d  |diff|=%d' % (d1, d2, abs(d1 - d2)))
m = re.search(r'^Number of nets:\s*(\d+).*?\|\s*Number of nets:\s*(\d+)',
              blk, re.M)
if m:
    n1, n2 = int(m.group(1)), int(m.group(2))
    print('  Number of nets    : C1=%d  C2=%d  |diff|=%d' % (n1, n2, abs(n1 - n2)))

print()
print('  Compare against the AUTHORITATIVE metric (state_out.json):')
ST = os.path.join(BASE, '66-netgen-lvs/state_out.json')
import json
mm = json.load(open(ST, encoding='utf-8'))['metrics']
for k in ('design__lvs_device_difference__count',
          'design__lvs_net_difference__count',
          'design__lvs_property_fail__count',
          'design__lvs_unmatched_device__count',
          'design__lvs_unmatched_net__count',
          'design__lvs_unmatched_pin__count',
          'design__lvs_error__count'):
    print('    %-44s %s' % (k.replace('design__lvs_', '').replace('__count', ''),
                            mm[k]))
parts = sum(mm['design__lvs_%s__count' % s] for s in
            ('device_difference', 'net_difference', 'property_fail',
             'unmatched_device', 'unmatched_net', 'unmatched_pin'))
print('    %-44s %d (sum of the six components)' % ('total', parts))
