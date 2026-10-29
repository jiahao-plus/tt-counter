"""Q1: Is FP_PRUNE_THRESHOLD actually plumbed into the CutRows step?

Three independent tests, all from third-round artefacts:

  T1  Is the variable a declared LibreLane config key at all?
      -> resolved.json holds every declared key with its resolved value.
  T2  Was it passed to the cut_rows.tcl subprocess?
      -> _env.tcl lists every `set ::env(...)` the step saw.
  T3  Was it passed on the command line?
      -> COMMANDS holds the exact invocation.

If T1 passes but T2 and T3 fail, the variable is declared but unused by this
step, and writing it into src/config.json cannot change the cut result.
"""
import json
import os
import re

from paths import RUN as BASE
STAGE = os.path.join(BASE, '18-openroad-cutrows')

resolved = json.load(open(os.path.join(BASE, 'resolved.json'), encoding='utf-8'))
stage_cfg = json.load(open(os.path.join(STAGE, 'config.json'), encoding='utf-8'))
env = open(os.path.join(STAGE, '_env.tcl'), encoding='utf-8',
           errors='replace').read()
cmd = open(os.path.join(STAGE, 'COMMANDS'), encoding='utf-8',
           errors='replace').read()

KEY = 'FP_PRUNE_THRESHOLD'
print('=' * 78)
print('T1 -- is %s a declared config key?' % KEY)
print('=' * 78)
print('  in resolved.json (411 keys) : %s' % (KEY in resolved))
if KEY in resolved:
    print('  resolved value              : %r' % resolved[KEY])
print('  in 18-cutrows config.json   : %s' % (KEY in stage_cfg))
print('  -> T1 %s' % ('PASS (declared)' if KEY in resolved else 'FAIL'))

print()
print('=' * 78)
print('T2 -- was it passed to the cut_rows.tcl subprocess?')
print('=' * 78)
envvars = re.findall(r'set ::env\(([A-Z_0-9]+)\)', env)
print('  _env.tcl declares %d variables' % len(envvars))
print('  %s present : %s' % (KEY, KEY in envvars))
print('  -> T2 %s' % ('PASS' if KEY in envvars else 'FAIL (not passed)'))
if KEY not in envvars:
    print()
    print('  Related variables that WERE passed:')
    for v in envvars:
        if 'TAP' in v or 'HALO' in v or 'PRUNE' in v or 'CUT' in v:
            m = re.search(r'set ::env\(%s\)\s*(.*)' % v, env)
            print('     %-30s %s' % (v, m.group(1) if m else ''))

print()
print('=' * 78)
print('T3 -- was it on the command line?')
print('=' * 78)
print('  COMMANDS:')
for ln in cmd.strip().splitlines():
    print('     ' + ln.strip())
print('  contains "prune" : %s' % ('prune' in cmd.lower()))
print('  -> T3 %s' % ('PASS' if 'prune' in cmd.lower() else 'FAIL (absent)'))

print()
print('=' * 78)
print('T4 -- what DID the cut_rows command receive?')
print('=' * 78)
log = open(os.path.join(STAGE, 'openroad-cutrows.log'), encoding='utf-8',
           errors='replace').read()
for ln in log.splitlines():
    if ln.startswith('+ cut_rows'):
        print('  ' + ln)
        print()
        print('  NOTE: -halo_width_x / -halo_width_y only. The cut is driven')
        print('  by the macro halo, not by any prune threshold.')

print()
print('=' * 78)
print('VERDICT')
print('=' * 78)
declared = KEY in resolved
passed_env = KEY in envvars
passed_cli = 'prune' in cmd.lower()
if declared and not passed_env and not passed_cli:
    print('  The key is DECLARED in LibreLane but NOT PASSED to this step.')
    print('  Writing FP_PRUNE_THRESHOLD into src/config.json therefore CANNOT')
    print('  be shown to change the CutRows result from local evidence.')
    print()
    print('  Prerequisite 1 ("LibreLane actually recognises the variable and')
    print('  passes it to CutRows") is UNVERIFIED locally.')
else:
    print('  Plumbing confirmed -- threshold would reach the tool.')
